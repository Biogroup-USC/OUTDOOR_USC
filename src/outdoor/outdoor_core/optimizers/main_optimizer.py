#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 15 12:19:19 2021

@author: philippkenkel
"""

import pyomo.environ as pyo
from pyomo.opt import TerminationCondition
from numpy import linspace

# from .customs.change_functions.parameter_changer_functions import *  # contains all funcitions to change the parameters in the model instance called in change_parameter
# from ..utils.timer import time_printer
# import re

from ..output_classes.model_output import ModelOutput
from ..output_classes.stochastic_model_output import StochasticModelOutput
from ..utils.timer import time_printer
#from pyomo.util.infeasible import log_infeasible_constraints
#import logging

class SingleOptimizer:
    """
    Class Description
    -----------------
    This Class is the model instance handler. It takes holds the run_optimization
    method which takes any PYOMO concrete model, solves it and return and ModelOuput
    Class object.

    It is also the parent class of the custom Opimizer Classes which are written
    especially for special runs in Superstructure Opimitzation (e.g. Sensitivity etc.)
    """
    def __init__(self, solver_name, solver_interface, optimization_mode= None, solver_path=None,
                 solver_options=None):
        """
        Parameters
        ----------
        solver_name : String
        solver_interface : String
        solver_options : Dict, optional

        Description
        -------
        Constructor of the SingleOptimzer. It checks if the handed solver is in the
        solver library as well as the interface in the interface library. However,
        it does NOT check if the solvers are installed on the maschine.

        """
        # Set the logging level to INFO
        # logging.basicConfig(level=logging.INFO)
        # logging.getLogger('pyomo.core').setLevel(logging.INFO)

        SOLVER_LIBRARY = {"gurobi", "cbc", "scip", "glpk", 'gams'}
        INTERFACE_LIBRARY = {"local", "executable"}

        # setup name
        if solver_name in SOLVER_LIBRARY:
            self.solver_name = solver_name
        else:
            self.solver_name = solver_name
            raise Exception("Solver not in library, correct optimization not garanteed")

        # setup interface
        if solver_interface in INTERFACE_LIBRARY:
            self.solver_interface = solver_interface
        else:
            raise Exception("Solver interface not in library, correct optimization not garanteed")

        # check for gurobi
        if self.solver_name == "gurobi":
            self.solver_io = "python"

        # create solver
        if solver_interface == "local":
            if solver_name == "gurobi":
                self.solver = pyo.SolverFactory(
                    self.solver_name, solver_io=self.solver_io
                    )
            else:
                self.solver = pyo.SolverFactory(self.solver_name)
        else:
            self.solver = pyo.SolverFactory(self.solver_name,
                                            executable=solver_path)


        self.solver = self.set_solver_options(self.solver, solver_options)

        # save optimisation mode
        self.optimization_mode = optimization_mode

    def run_optimization(self,
                         model_instance,
                         tee=True,
                         keepfiles = True,
                         printTimer=True,
                         VSS_EVPI_mode=False,
                         stochastic_optimisation=False,
                         runFeasibilityAnalysis=True):


        """
        Parameters
        ----------
        model_instance : PYOMO Concrete Model

        Returns
        -------
        model_output : ModelOutput

        Description
        -----------
        This is the main optimization method of the optimizer. It calls the
        solver.solve function from pyomo, and stores all results
        (Sets, Params, Var, Objective, Optimimality gap) in the ModelOuput object.

        """

        timer = time_printer(programm_step='Superstructure optimization run', printTimer=printTimer)

        # Solve the model
        results = self.solver.solve(model_instance, keepfiles=keepfiles, tee=tee)


        # Check if the model is infeasible
        if (results.solver.termination_condition == TerminationCondition.infeasibleOrUnbounded or
            results.solver.termination_condition == TerminationCondition.infeasible):

            if not VSS_EVPI_mode:
                # print("\n Model is infeasible or unbounded in constraints: \n")
                # # Log infeasible constraints AFTER solving the model
                # log_infeasible_constraints(model_instance)
                # print('')

                print("Model is infeasible. Running IIS analysis if flag runFeasibilityAnalysis is set to true.")
                if runFeasibilityAnalysis:
                    # Enable IIS computation
                    self.solver.options['ResultFile'] = "iis.ilp"  # Save IIS to a file (optional)
                    self.solver.solve(model_instance, tee=True, options={'IISMethod': 1}, symbolic_solver_labels=True)
                    #results = solver.solve(model_instance, tee=True, options={'IISMethod': 1})

                    # Mark constraints that are part of the IIS
                    #for c in model_instance.component_objects(pyo.Constraint, active=True):
                    #    for index in c:
                    #        if c[index].active:
                    #            print(f"Constraint {c.name} at index {index} is in the IIS.")

                    raise Exception("The model is infeasible, please check the input data is correct. \n"
                                    " TIP check: 1) the minimum and maximum pool/source fluxes \n"
                                    "2) Split fractions of unit processes \n"
                                    "3) The Product load if active")

            else:
                return 'infeasible' # so we can save the conditions where the solution is infeasible in the VSS_EVPI mode
        else:
            # The model may be feasible or have some other issue
            if results.solver.termination_condition == TerminationCondition.optimal:
                pass
                #print("The model is optimal.")
            elif results.solver.termination_condition == TerminationCondition.licensingProblems:
                raise Exception('There seems to be a problem with the licencing of your solver\n'
                                ' please check that the solver is correctly installed on choose another')
            else:
                print("The solver terminated with a different condition.: ", results.solver.termination_condition)

        gap = (
            (results["Problem"][0]["Upper bound"] - results["Problem"][0]["Lower bound"])
            / (results["Problem"][0]["Upper bound"] + 1e-9)) * 100

        if printTimer:
            timer = time_printer(timer, 'Single optimization run', printTimer=printTimer)

        if stochastic_optimisation: # if the run is a stochastic run we need to use the stochastic model output class
            model_output = StochasticModelOutput(model_instance=model_instance, # the model instance now contains the optimised values
                                                 optimization_mode='2-stage-recourse',
                                                 solver_name=self.solver_name, run_time=timer, gap=gap)
        else:
            model_output = ModelOutput(model_instance=model_instance,
                                       optimization_mode='single',
                                       solver_name=self.solver_name,
                                       run_time=timer,
                                       gap=gap)

        return model_output


    def set_solver_options(self, solver, options):
        """
        Parameters
        ----------
        solver : Pyomo solver object

        options : Dict


        Returns
        -------
        solver : Pyomo solver object

        Description
        -----------
        Sets solver options based on the options in the dictionary.

        """

        # lowering the integer feasibility tolerance
        if options is None:
            options = {}
            options['IntFeasTol'] = 1e-8
            #options['NumericFocus'] = 3
        else:
            options.update({'IntFeasTol': 1e-8})

        if options is not None:
            for i, j in options.items():
                solver.options[i] = j
        else:
            pass
        return solver

    # some class functions used for sensitivity analysis type optimization
    # should move them all here honestly TODO Move functions of file change_params here

    def calculate_sensitive_parameters(self, data_input):

        value_dic = dict()

        try:
            # if the input come from the excel file
            for i in data_input:
                paramName = i['Parameter_Type']
                # if the series has a number in the field Unit_Number, get the value of that number
                if isinstance(i['Unit_Number'], int):  # if the value is an integer and i['Unit_Number'] is not 'n.a.'
                    paramName = paramName + "_" + str(int(i['Unit_Number']))
                start = i['Lower_Bound']
                stop = i['Upper_Bound']
                dx = i['Number_of_steps']
                metadata = i.iloc[1:5]
                value_dic[paramName] = (list(linspace(start, stop, dx)), metadata)
            return value_dic

        except:
            # if the input come from the interface file

            for n, i in enumerate(data_input):
                paramName = i['parameterType']
                unitUid = i['unitUid']
                unitName = self.superstructure.UnitNames['Names'].get(unitUid, '')
                paramName = paramName + "_"  + unitName

                start = i['lowerBound']
                stop = i['upperBound']
                dx = int(i['steps'])
                metadata = i.iloc[1:5]
                # Rename column(s)
                # change the column names of the metadata to that of the
                # excel file so no downstream functions get blocked
                # change column name "unitUid" to "Unit_Number"
                # (metadata['Unit_Number'], (metadata['Component'], metadata['Reaction_Number']))

                metadata = metadata.rename({
                    "unitUid": "Unit_Number",
                    "targetUnitProcess": "Target_Unit",
                    "componentName": "Component",
                    "reactionUid": "Reaction_Number"
                })

                value_dic[paramName] = (list(linspace(start, stop, dx)), metadata)

            return value_dic
