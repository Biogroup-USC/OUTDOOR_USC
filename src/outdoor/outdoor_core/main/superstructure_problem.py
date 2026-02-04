import copy

import numpy as np
from pyomo.environ import *

from ..model.optimisation_model_2_stage_recourse import SuperstructureModel_2_Stage_recourse
from ..model.optimization_model import SuperstructureModel
from ..optimizers.customs.change_params import prepare_mutable_parameters
from ..optimizers.customs.custom_optimizer import (MCDAOptimizer, MultiObjectiveOptimizer, SensitivityOptimizer,
                                                   TwoWaySensitivityOptimizer, StochasticRecourseOptimizer,
                                                   WaitAndSeeOptimizer, StochasticRecourseOptimizer_mpi_sppy,
                                                   HereAndNowOptimizer,)
from ..optimizers.main_optimizer import SingleOptimizer
from ..utils.timer import time_printer


# import sys
#
# import logging


class SuperstructureProblem:
    """
    Class Description
    -----------------

    This Class is the main handler of OUTDOORS modeling and optimization framework.
    It is created, and afterward the main "solve_optimization_problem" is called
    with given input data, solver name etc.

    This class calls different classes which
        - Create the model  (SuperstructureModel Class)
        - Populate the model to a model instancen (PYOMO ConcreteModel)
        - Creates the appropriate Optimizer Class obects
        - Hands the model instance to the Optimizer, which solves the model
        using the defined external solver and returns a ModelOutput Class object.
    """

    def __init__(self, parser_type="Superstructure"):
        """

        Parameters
        ----------
        parser_type : String, optional
            DESCRIPTION: Takes the type of which data is parsed. Permitted values
                are "Superstructure" and "External". RIGHT NOW THERE IS NO ALGORITHM
                WHICH WORKS WITH EXTERNAL.

        """

        PARSER_SET = {"Superstructure", "External"}
        if parser_type in PARSER_SET:
            self.parser = parser_type
        else:
            raise Exception(
                f"Parser type not recognized, \
                please use one of the following key words:{PARSER_SET}"
            )

        self.CheckNoneVariables = []
        self.stochastic_mode = None


    def solve_optimization_problem(
        self,
        input_data=None,
        optimization_mode=None,
        solver="gurobi",
        interface="local",
        solver_path=None,
        options=None,
        calculation_EVPI=True,
        calculation_VSS=True,
        count_variables_constraints=False,
        cross_sensitivity_parameters=None,
        mpi_sppy_options=None,
        outputFileDesignSpace=None,
        multi_objective_options=None,
        modelObjective=None,
    ):
        """

        Parameters
        ----------
        input_data : Superstructure Object, optional
            DESCRIPTION: Input data, if parser type=Superstructure, has to be
                a Superstructure Class object.
        optimization_mode : string, optional
            DESCRIPTION. The default is "single". Other permitted values are:
                'sensitivity', 'cross-parameter', 'multi-objective'
        solver : string, optional
            DESCRIPTION. The default is "gurobi". Solver name to use, solver must
                be installed.
        interface : string optional
            DESCRIPTION. The default is "local". Permitted values ares:
                'local', 'executable'. Local are installed solver packages,
                executables are .exe-files which can be used directly.
        solver_path : string optional
            DESCRIPTION: If 'executable' is choses as solver interface, a path
                has to be defined where the .exe-file is located on the machine.
        options : Dictionarry, optional
            DESCRIPTION. The default is None. Solver options as dictionary.
                Keys are options, values are values. Keys have to be permitted by
                chosen solver.
        stochastic_mode : string, optional (only for 2-stage-recourse) defines if you want to use mpi-sspy


        Returns
        -------
        model_output : ModelOutput / MultiModelOutput

        Description
        -----------

        The main optimization function. It prepares the model instance,
        Optimizer and optionals. Afterwards solves the model instance by calling
        the Optimizer run_optimization function. Calls the following functions
        in order:
            1) setup_model_instance()
            2) set_mode_options()
            3) setup_optimizer()
            4) optimizer.run_optimization()

        """

        # change the model objective in the inputdata if given as a input to the methode
        if modelObjective:
            #input_data
            pass

        # check if the stochastic mode is set correctly for the 2-stage-recourse optimization mode
        self.stochastic_mode = input_data.stochasticMode

        # give the design space output file to the superstructure object
        if outputFileDesignSpace is not None:
            input_data.outputFileDesignSpace = outputFileDesignSpace

        # what are the permitted optimization modes
        OptimisationPermissionList = ["single",
                                      "multi-objective",
                                      "multi-objective MCDA",
                                      "sensitivity",
                                      "cross-parameter sensitivity",
                                      "2-stage-recourse",
                                      "wait and see",
                                      "here and now"]

        if optimization_mode is None:
            optimization_mode = input_data.optimization_mode
            self._optimization_mode = input_data.optimization_mode
        else:
            if optimization_mode not in OptimisationPermissionList:
                raise Exception("Optimization mode not in library, please choose between: " + str(OptimisationPermissionList))
            else:
                self._optimization_mode = optimization_mode

        solving_time = time_printer(programm_step="Superstructure optimization procedure")

        # make a copy of the input data if the optimization mode is 2-stage-recourse
        input_data_rerun = {}
        if optimization_mode == "2-stage-recourse":
            input_data_rerun = copy.deepcopy(input_data)


        if self.parser == "Superstructure":

            if optimization_mode == "2-stage-recourse" and self.stochastic_mode == "mpi-sppy":
                model_instance = None  # we do not need to create a model instance for the mpi-sppy mode
            elif optimization_mode == "wait and see" or optimization_mode == "here and now":
                model_instance = None  # we do not need to create a model instance for the wait and see mode
            else:
                # populate the model instance with the input data
                model_instance = self.setup_model_instance(input_data, optimization_mode)

            if count_variables_constraints:
                self.print_count_variables_constraints(model_instance)
            # check for nan Values
            # check_nan = self.find_nan_parameters_in_model_instance(model_instance)
            # self.CheckNoneVariables = check_nan
            # set model options
            mode_options = self.set_mode_options(optimization_mode, input_data, multi_objective_options)
            # pass on stochastic optimization options dictionary
            stochastic_options = {'calculation_EVPI': calculation_EVPI, 'calculation_VSS': calculation_VSS}
            # settings optimisation problem
            optimizer = self.setup_optimizer(solver,
                                             interface,
                                             solver_path,
                                             options, optimization_mode, mode_options,
                                             input_data, stochastic_options,
                                             mpi_sppy_options=mpi_sppy_options) #add options for mpi-sppy None if not mpi-sppy
            # run the optimization
            model_output = optimizer.run_optimization(model_instance)

            # for the stochastic recourse model, we need to run the model again if infeasible scenarios were found
            # the model_output is a dictionary with the infeasible scenarios
            if isinstance(model_output, dict):
                # this means that the stochastic recourse model was run and infeasible scenarios were found
                # curate the data file and run the stochastic model
                # we need to run the stochastic model again
                if model_output["Status"] == "remake_stochastic_model_instance":
                    infeasibleScenarios = model_output["infeasibleScenarios"]
                    # we need to run the stochastic model again
                    model_instance = self.setup_model_instance(input_data_rerun, optimization_mode, infeasibleScenarios)
                    optimizer_rerun = self.setup_optimizer(solver, interface, solver_path, options, optimization_mode,
                                             mode_options, input_data_rerun, stochastic_options, remakeMetadata=model_output)
                    model_output = optimizer_rerun.run_optimization(model_instance)


            time_printer(solving_time, "Superstructure optimization procedure")
            return model_output

        else:
            raise Exception("Currently there is no routine for external data parsing implemented")


    def setup_model_instance(self, input_data, optimization_mode, infeasibleScenarios=None, printTimer=True):
        """

        Parameters
        ----------
        input_data : Superstructure Class object

        optimization_mode : String
            DESCRIPTION: If optimization_mode is 'sensitivity' or
                'cross-parameter sensitivity' this function prepares the mutable
                parameters of the model instance. Otherwise all parameters are
                kept as non-mutable.


        Returns
        -------
        model_instance : Pyomo ConcreteModel

        Description
        -----------
        Creates model instance by first creating data file
        from Superstructure, then creating SuperstructureModel objects.
        Afterwards prepares mutable parameters (if required) and populates model

        """

        timer = time_printer(programm_step="DataFile, Model- and ModelInstance setup", printTimer=printTimer)


        data_file = input_data.create_DataFile()

        if infeasibleScenarios is not None:
            # if the problem is a stochastic problem, we need to get rid of the parameters from infeasible scenarios
            data_file, defaultScenario = self.curate_stochastic_data_file(data_file, infeasibleScenarios)
            input_data.DefaultScenario = defaultScenario

        if optimization_mode == "2-stage-recourse" and self.stochastic_mode == None:
            model = SuperstructureModel_2_Stage_recourse(input_data)
        else: # single, multi or sensitivity optimisation or mpi-sspy mode for 2-stage-recourse
            model = SuperstructureModel(input_data)

        model.create_ModelEquations()

        if optimization_mode == "sensitivity" or optimization_mode == "cross-parameter sensitivity":
            mode_options = input_data.sensitive_parameters
            prepare_mutable_parameters(model, mode_options)

        # populate the model instance
        model_instance = model.populateModel(data_file)

        time_printer(timer, "DataFile, Model- and ModelInstance setup")

        return model_instance

    def setup_optimizer(
        self,
        solver,
        interface,
        solver_path,
        options,
        optimization_mode,
        mode_options,
        superstructure,
        stochastic_options,
        printTimer=True,
        remakeMetadata=None,
        mpi_sppy_options=None
    ):
        """


        Parameters
        ----------
        solver : String
            DESCRIPTION: Solver name
        interface : String
            DESCRIPTION: Interface
        solver_path: String
            DESCRIPTION: Path to .exe-file of executable solver
        options : Dictionary
            DESCRIPTION: Solver options
        optimization_mode : String
            DESCRIPTION: Optimization mode. Permitted values are:
                'single', 'multi-objective', 'sensitivity' and
                'cross-parameter sensitivity'.
        mode_options : Dictionary
            DESCRIPTION: Additional information eg on sensitive parameters
        superstructure : Superstructure Class object
            DESCRIPTION.


        Returns
        -------
        optimizer : SingleOptimizer (other custom Optimizers)


        Description
        -----------
        Creates an Optimizer Class object depending on the optimization mode,
        solver and interface. Returns the Optimizer

        """
        MODE_LIBRARY = {"single",
                        "multi-objective",
                        "multi-objective MCDA",
                        "sensitivity",
                        "cross-parameter sensitivity",
                        "2-stage-recourse",
                        "wait and see",
                        "here and now"
                        }

        if optimization_mode not in MODE_LIBRARY:
            print(
                f"Optimization mode is not supported, \n "
                f"please select from: {MODE_LIBRARY}"
            )

        timer = time_printer(programm_step="Optimizer setup", printTimer=printTimer)


        if optimization_mode == "2-stage-recourse" and self.stochastic_mode == None:
            singleInput = superstructure.parameters_single_optimization
            single_model_instance = self.setup_model_instance(singleInput, optimization_mode = 'single',
                                                              printTimer=False)

            optimizer = StochasticRecourseOptimizer(solver_name = solver, solver_interface=interface,
                                                    solver_options=options, input_data=superstructure,
                                                    single_model_instance=single_model_instance,
                                                    stochastic_options=stochastic_options,
                                                    remakeMetadata=remakeMetadata)

        elif optimization_mode == "2-stage-recourse" and self.stochastic_mode == "mpi-sppy":
            optimizer = StochasticRecourseOptimizer_mpi_sppy(solver_name= solver,
                                                             solver_interface=interface,
                                                             inputObject=superstructure,
                                                             mpiOptions=mpi_sppy_options)


        elif optimization_mode == "wait and see":
            # fyi, the variable superstructure is the inputObject of all the data and stuff
            optimizer = WaitAndSeeOptimizer(solver_name=solver, solver_interface=interface,
                                            solver_options=options, inputObject=superstructure)

        elif optimization_mode == "here and now":
            optimizer = HereAndNowOptimizer(solver_name=solver, solver_interface=interface,
                                            solver_options=options, inputObject=superstructure)

        elif optimization_mode == "single":
            optimizer = SingleOptimizer(solver_name=solver, solver_interface=interface,
                                        optimization_mode=optimization_mode, solver_path=solver_path,
                                        solver_options=options)

        elif optimization_mode == "multi-objective MCDA":
            optimizer = MCDAOptimizer(solver, interface, options, mode_options)

        elif optimization_mode == "multi-objective":
            optimizer = MultiObjectiveOptimizer(solver, interface, options, mode_options)

        elif optimization_mode == "sensitivity":
            optimizer = SensitivityOptimizer(solver, interface, options,
                                             mode_options, superstructure)

        elif optimization_mode == "cross-parameter sensitivity":
            optimizer = TwoWaySensitivityOptimizer(
                solver_name=solver,
                solver_interface=interface,
                solver_options=options,
                two_way_data=mode_options,
                superstructure=superstructure)

        else:
            raise ValueError("Optimization mode not supported")

        time_printer(passed_time=timer, programm_step="Optimizer setup", printTimer=printTimer)

        return optimizer

    def set_mode_options(self, optimization_mode, superstructure, multi_objective_options=None):
        """

        Parameters
        ----------
        optimization_mode : String


        Returns
        -------
        mode_options : Dictionary

        Descripion
        ----------
        Collects for Multi-Run Optimizations the required data from the Superstructure
        Object. e.g. sensititive parameters for sensitivity run.

        """
        if optimization_mode == "multi-objective MCDA":
            mode_options = superstructure.multi_objectives
        elif optimization_mode == "multi-objective":
            if multi_objective_options is None:
                raise ValueError("Multi-objective optimization requires you te specifiy 2 objectives and "
                                 "the lv of detail of the pareto front")
            if isinstance(multi_objective_options, dict):
                mode_options = multi_objective_options
            else:
                raise ValueError("Multi-objective options have to be a dictionary")

        elif (
            optimization_mode == "sensitivity" or optimization_mode == "cross-parameter sensitivity"):
            mode_options = superstructure.sensitive_parameters
        else:
            mode_options = None

        return mode_options

    def find_nan_parameters_in_model_instance(self, model, print_nan_parameters=False):
        """
        Check for NaN values in parameters of a Pyomo model.

        Args:
            model: A Pyomo model instance.

        Returns:
            A list of tuples containing component and key for parameters with NaN values.
            Returns an empty list if no NaN values are found.
        """
        nan_parameters = []

        # parameter_declarations = list(model.component_data_objects(Param, active=True))

        # Iterate through all active parameters in the model
        for component in model.component_objects(Param, active=True):
            for key in component:
                param_value = component[key]
                # check if param_value is a string
                # if isinstance(param_value, str):
                #     continue
                try:
                    if np.isnan(param_value) and not isinstance(param_value, str):
                        nan_parameters.append((component, key, param_value))
                except:
                    nan_parameters.append((component, key, param_value))

        if print_nan_parameters:
            if nan_parameters:
                print("The following parameters have None values, check if they are correct:")
                for param in nan_parameters:
                    if isinstance(param[2], str):
                        # if a string delete the value from the list
                        nan_parameters.remove(param)
                    else:
                        print(f"Parameter {param[0].name}[{param[1]}]: {param[2]}")

                # raise ValueError("NaN values in parameters detected. Please check the model.")

        return nan_parameters

    def print_count_variables_constraints(self, model_instance):
        # Initialize a counter for variables
        total_variables = 0
        # Iterate over all variable objects in the model
        for var_object in model_instance.component_objects(Var, active=True):
            # Iterate over the indices of each variable object (if indexed)
            # If the variable is not indexed, this will iterate once
            for _ in var_object:
                total_variables += 1

        # Initialize a counter for constraints
        total_constraints = 0
        # Iterate over all constraints in the model
        for constraint_object in model_instance.component_objects(Constraint, active=True):
            # Iterate over the indices of each constraint object (if indexed)
            # If the constraint is not indexed, this will iterate once
            for _ in constraint_object:
                total_constraints += 1

        print(f"Total number of variables: {total_variables}")
        print(f"Total number of constraints: {total_constraints}")


    # -------------------------------------------------------------------------------------------------------------
    # Class functions for the stochastic optimisation
    # -------------------------------------------------------------------------------------------------------------
    def curate_stochastic_data_file(self, data_file, infeasibleScenarios, parameterList=None):
        """
        gets rid of the parameters which result in infeasible scenarios
        :param data_file: a dictionary with the data that is passed to populate the model instance
        :param parameterList: a list with the parameters which are affected by the infeasible scenarios
        :param infeasibleScenarios: a list with the scenarios which are infeasible
        :return: the curated data file
        """
        # we need to go over the following parameters: phi, myu, xi, materialcosts, ProductPrice, gamma and theta

        if parameterList is None:
            parameterList = ['phi', 'myu', 'xi', 'materialcosts', 'ProductPrice', 'gamma', 'theta', 'Decimal_numbers']

        for sc in infeasibleScenarios:
            data_file[None]['SC'][None].remove(sc)  # remove the scenario from the list of scenarios
            data_file[None]['odds'].pop(sc, None)  # remove the scenario from the odds dictionary
            for param in parameterList:
                if param in data_file[None]: # check if the parameter is in the data file, if not skip it
                    # Create a list of keys to remove
                    keys_to_remove = [key for key in data_file[None][param] if key[-1] == sc]
                    # Pop elements from the dictionary
                    for key in keys_to_remove:
                        data_file[None][param].pop(key, None) # The `None` is to avoid KeyError if the key is not found

        # the default scenario becomes the first scenario in the list
        defaultScenario = data_file[None]['SC'][None][0]
        return data_file, defaultScenario


    # -------------------------------------------------------------------------------------------------------------
    # methods for the stochastic recourse model using mpi-sppy for the 2-stage-recourse optimization
    # attention!! these methodes have been place in custom_optimizer.py (StochasticRecourseOptimizer_mpi_sppy class)
    # file and should not be used here, for debugging purposes only
    # -------------------------------------------------------------------------------------------------------------

    # def scenario_creator(self, scenarioName):
    #     """
    #     This function is used to create instances of a scenario, used to run optimization problems under uncertainty
    #     using mpi-sppy. The function is called by mpi-sppy and should return a Pyomo model instance for the scenario
    #
    #     :param scenario_name:
    #     :param inputObject:
    #     :return: model_instance
    #     """
    #
    #     # retrive the data file for all scenarios
    #     inputObject = self.inputObject
    #     scenarioDataFile = inputObject.scenarioDataFiles
    #
    #     # initialize the model
    #     model = SuperstructureModel(inputObject)
    #
    #     # create the model equations
    #     model.create_ModelEquations()
    #
    #     # get the correct data file for the scenarioDataFile
    #     dataFile = scenarioDataFile[scenarioName]
    #
    #     # populate the model instance
    #     modelInstance = model.populateModel(dataFile)
    #
    #     # introduce the model instance to mpi-sppy
    #     sputils.attach_root_node(modelInstance,
    #                              modelInstance.Objective, # the objective function
    #                              # the first stage variables, which are non-anticipative constraints.
    #                              # i.e., do not change across scenarios. In this case, the binary variables responsible
    #                              # for the selection of the technology
    #                              [modelInstance.Y]) # todo add?  ,modelInstance.Y_DIST
    #
    #     modelInstance._mpisppy_probability = 1.0 / len(scenarioDataFile)
    #
    #     return modelInstance
    #
    #
    # def run_extensive_form(self, options, allScenarioNames):
    #     """
    #     This function runs the extensive form of the optimization problem. The extensive form is a deterministic
    #     optimization problem where all scenarios are considered. The function returns the objective value and the
    #     solution of the extensive form.
    #
    #     :param options: a dictionary with options for the extensive form
    #     :param allScenarioNames: a list with the names of all scenarios
    #     :param scenario_creator: a function which creates the model instance for a scenario
    #     :return: objective value, solution
    #     """
    #
    #     ef = ExtensiveForm(options, allScenarioNames, self.scenario_creator)
    #     results = ef.solve_extensive_form()
    #
    #     objval = ef.get_objective_value()
    #     soln = ef.get_root_solution()
    #
    #     return objval, soln
    #
    #
    # def run_progressive_hedging(self, inputObject, options):
    #     """
    #     This function runs the progressive hedging algorithm for solving the stochastic optimization problem. The
    #     function returns the objective value and the solution of the progressive hedging algorithm.
    #
    #     :param options: a dictionary with options for the progressive hedging algorithm
    #     :param all_scenario_names: a list with the names of all scenarios
    #     :param scenario_creator: a function which creates the model instance for a scenario
    #     :return: objective value, solution
    #     """
    #     allScenarioNames = list(inputObject.scenarioDataFiles.keys())
    #     self.inputObject = inputObject
    #
    #     ph = PH(options,
    #             allScenarioNames,
    #             self.scenario_creator)
    #
    #     ph.ph_main()
    #
    #     variablesR0 = ph.gather_var_values_to_rank0()
    #
    #     # Gather and print all variable values for the first scenario
    #     allVariables = {}
    #     VariableWarningDict = {}
    #     for sc in allScenarioNames:
    #         scenario = ph.local_scenarios[sc]
    #         allVariables.update({sc: {}})
    #         VariableWarningDict.update({sc: {}})
    #         #print(f"\nResults for scenario {allScenarioNames[0]}:")
    #         for var in scenario.component_objects(pyo.Var, active=None):
    #             try:
    #                 var_object = getattr(scenario, str(var))
    #                 for index in var_object:
    #                     allVariables[sc].update({f"{var}[{index}]": pyo.value(var_object[index])})
    #
    #                     # if sc == allScenarioNames[0]: # only print the variables for the first scenario
    #                     #     print(f"{var}[{index}] = {pyo.value(var_object[index])}")
    #
    #             except:
    #                 VariableWarningDict[sc].update({str(var): "Variable not calculated"})
    #                 #print(f"Variable {var_object} is not calculated!!")
    #                 continue
    #
    #
    #     return variablesR0, allVariables, VariableWarningDict
    #
    #
    #
    #

