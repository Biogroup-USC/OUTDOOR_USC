#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 15 12:19:19 2021

@author: philippkenkel and Lucas Van der Hauwaert
"""


import copy
import logging
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pyomo.environ as pyo
from pyomo.environ import *
from shapely.geometry import MultiPoint, Point
import random

from .change_objective import change_objective_function
from .change_params import (
    calculate_sensitive_parameters,
    change_parameter,
)
from ..main_optimizer import SingleOptimizer
from ...model.optimization_model import SuperstructureModel
from ...output_classes.multi_model_output import MultiModelOutput
from ...output_classes.stochastic_model_output import StochasticModelOutput_mpi_sppy
from ...utils.progress_bar import print_progress_bar
from ...utils.timer import time_printer


class MCDAOptimizer(SingleOptimizer):
    def __init__(self, solver_name, solver_interface, solver_options=None, mcda_data=None):
        super().__init__(solver_name, solver_interface, solver_options)
        self.mcda_data = mcda_data
        self.single_optimizer = SingleOptimizer(solver_name, solver_interface, solver_options)

    def run_optimization(self,
                         model_instance,
                         optimization_mode=None,
                         solver="gurobi",
                         interface="local",
                         solver_path=None,
                         options=None,
                         count_variables_constraints=False,

                         ):

        timer = time_printer(programm_step="MCDA optimization")

        model_output = MultiModelOutput(optimization_mode="multi-objective")

        for k, v in self.mcda_data.items():
            change_objective_function(model_instance, k)
            single_solved = self.single_optimizer.run_optimization(model_instance)
            single_solved._tidy_data()
            model_output.add_process(k, single_solved)

        print("MCDA reformulation")
        change_objective_function(model_instance, "MCDA", model_output, self.mcda_data)
        single_solved = self.single_optimizer.run_optimization(model_instance)
        single_solved._tidy_data()
        model_output.add_process("MCDA", single_solved)
        model_output.set_multi_criteria_data(self.mcda_data)

        timer = time_printer(timer, "MCDA optimization")
        model_output.fill_information(timer)
        return model_output

class MultiObjectiveOptimizer(SingleOptimizer):
    """
    This class is used to solve a multi-objective optimization problem between two objectives
    with the goal of finding the pareto front
    """
    def __init__(self, solver_name, solver_interface, solver_options=None, multi_data=None):
        super().__init__(solver_name, solver_interface, solver_options)
        self.multi_data = multi_data
        self.single_optimizer = SingleOptimizer(solver_name, solver_interface, solver_options)

    def run_optimization(self,
                         model_instance,
                         optimization_mode=None,
                         solver="gurobi",
                         interface="local",
                         solver_path=None,
                         options=None,
                         count_variables_constraints=False,
                         ):

        # set up:
        model_instance_original = copy.deepcopy(model_instance)
        model_output = MultiModelOutput(optimization_mode="multi-objective")
        model_output.multi_data = self.multi_data  # multi_data is actually the options of the multi-objective optimization
        objective1 = self.multi_data["objective1"] # the objective function that becomes constrained bounds
        objective2 = self.multi_data["objective2"] #  the objective function that is the model objective
        paretoPoints = self.multi_data["paretoPoints"]

        # get the bounds of the first objective function
        manualBoundsObjective1 = self.multi_data["bounds_objective1"]
        # start the timer
        time_printer(programm_step="Multi-objective optimization")

        # if there are bounds set them:
        lowerBound = manualBoundsObjective1[0]
        upperBound = manualBoundsObjective1[1]

        if lowerBound is not None:
            self.bound_region_objective(model_instance, objective1, lowerBound, "lower")
        if upperBound is not None:
            self.bound_region_objective(model_instance, objective1, upperBound, "upper")


        # run the optimization for the first objective
        self.change_model_objective(model_instance, objective1)
        single_solved_obj1 = self.single_optimizer.run_optimization(model_instance)
        single_solved_obj1._tidy_data()
        # model_output.add_process("maxObjective1", single_solved_obj1)

        # run the optimization for the second objective
        self.change_model_objective(model_instance, objective2)
        single_solved_obj2 = self.single_optimizer.run_optimization(model_instance)
        single_solved_obj2._tidy_data()
        # model_output.add_process("maxObjective2", single_solved_obj2)

        # get the result of the first objective from the second optimization problem
        if objective1 in single_solved_obj1._data["IMPACT_CATEGORIES"]:
            bound_1 = single_solved_obj1._data["IMPACT_TOT"][objective1]
            bound_2 = single_solved_obj2._data["IMPACT_TOT"][objective1]
        else:
            bound_1 = single_solved_obj1._data[objective1] # upper bound of the first objective
            bound_2 = single_solved_obj2._data[objective1] # lower bound of the second objective

        if bound_1 == bound_2:
            # print in Green:
            print("\033[1;32m" + "The two objectives {} and {} are not conflicting \n "
                                 "The results of the single optimization problem is returned".format(objective1, objective2) + "\033[0m")
            model_output.add_process("maxObjective1", single_solved_obj1)
            return model_output

        # now divide the bounds into pareto points and run the optimization for each bound
        bounds = np.linspace(bound_1, bound_2, paretoPoints)
        unfeasibleBounds = []
        # change the objective function to the second objective
        self.change_model_objective(model_instance, objective2)
        count = 0
        for bound in bounds:
            count += 1
            outputName = "pareto_bound_" + str(count)
            # change the bounds of the first objective,
            # DON'T MAKE THE CONSTRAINT NAME -> need to be replaced each iteration
            self.bound_objective(model_instance, objective1, bound)
            try:
                single_solved = self.single_optimizer.run_optimization(model_instance, runFeasibilityAnalysis=False,
                                                                       tee=False)
                single_solved._tidy_data()
                model_output.add_process(outputName, single_solved)
            except:
                # print the error message in orange
                unfeasibleBounds.append(bound)
                print("\033[93m" + "The optimization problem is infeasible for the bound: {}"
                                   " \n of objective {}".format(bound, objective1) + "\033[0m")
        print('the bounds are:', bounds)
        print("\033[93m" + "The infeasible for the bounds are: {}"
                           " \n for objective {}".format(unfeasibleBounds, objective1) + "\033[0m")

        # not just the pareto front but an entire design space
        ############################################################################################################
        # see if we want to do design space exploration
        if 'design_space_mode' in self.multi_data.keys():
            if self.multi_data['design_space_mode'] == True:
                design_space_mode = True
            else:
                design_space_mode = False
        else:
            design_space_mode = False

        if design_space_mode:
            # run 4 single optimizations to get the design space
            timer = time_printer(programm_step="Design space exploration")

            # get the bounds
            if 'design_space_bounds' not in self.multi_data.keys():
                design_space_bounds = {}
                design_space_bounds['min_obj1'] = None
                design_space_bounds['max_obj1'] = None
                design_space_bounds['min_obj2'] = None
                design_space_bounds['max_obj2'] = None
            else:
                design_space_bounds = self.multi_data['design_space_bounds']

            # create an instance that is bound by the design space options
            bound_instance = self.create_bounded_design_space(model_instance_original, design_space_bounds)

            # get the 4 corners of the trapezoid
            self.change_model_objective(bound_instance, objective1)
            opt_1 = self.single_optimizer.run_optimization(bound_instance)
            opt_1._tidy_data()

            self.change_model_objective(bound_instance, objective1, flipSense=True)
            opt_2 = self.single_optimizer.run_optimization(bound_instance)
            opt_2._tidy_data()

            self.change_model_objective(bound_instance, objective2)
            opt_3 = self.single_optimizer.run_optimization(bound_instance)
            opt_3._tidy_data()

            self.change_model_objective(bound_instance, objective2, flipSense=True)
            opt_4 = self.single_optimizer.run_optimization(bound_instance)
            opt_4._tidy_data()

            # Determine the x points for objective1
            x_points_obj_1 = [
                opt_1._data["IMPACT_TOT"][objective1] if objective1 in opt_1._data[
                    "IMPACT_CATEGORIES"] else opt_1._data[objective1],
                opt_2._data["IMPACT_TOT"][objective1] if objective1 in opt_2._data[
                    "IMPACT_CATEGORIES"] else opt_2._data[objective1],
                opt_3._data["IMPACT_TOT"][objective1] if objective1 in opt_3._data[
                    "IMPACT_CATEGORIES"] else opt_3._data[objective1],
                opt_4._data["IMPACT_TOT"][objective1] if objective1 in opt_4._data[
                    "IMPACT_CATEGORIES"] else opt_4._data[objective1]
            ]

            # Determine the y points for objective2
            y_points_obj_2 = [
                opt_1._data["IMPACT_TOT"][objective2] if objective2 in opt_1._data[
                    "IMPACT_CATEGORIES"] else opt_1._data[objective2],
                opt_2._data["IMPACT_TOT"][objective2] if objective2 in opt_2._data[
                    "IMPACT_CATEGORIES"] else opt_2._data[objective2],
                opt_3._data["IMPACT_TOT"][objective2] if objective2 in opt_3._data[
                    "IMPACT_CATEGORIES"] else opt_3._data[objective2],
                opt_4._data["IMPACT_TOT"][objective2] if objective2 in opt_4._data[
                    "IMPACT_CATEGORIES"] else opt_4._data[objective2]
            ]

            # in the sample points: x = objective1, y = objective2
            point1 = (x_points_obj_1[0], y_points_obj_2[0])
            point2 = (x_points_obj_1[1], y_points_obj_2[1])
            point3 = (x_points_obj_1[2], y_points_obj_2[2])
            point4 = (x_points_obj_1[3], y_points_obj_2[3])

            # If the points are in correct trapezoid order:
            # OR if the order is unknown (and you want a convex hull):
            polygon = MultiPoint([point1, point2, point3, point4]).convex_hull
            #  get the sample size from the options
            if 'sample_size' in self.multi_data.keys():
                sample_size = self.multi_data["sample_size"]
            else:
                sample_size = 100
                print("\033[93m" + "The 'sample_size' is not defined in the options, defaulted to 100" + "\033[0m")

            samplePoints = self.sample_uniform_in_polygon(polygon, n_samples=sample_size)
            count = 0
            nEnd = len(samplePoints)


            for point in samplePoints:
                objectiveSwitch = random.choice([1, 0]) # randomly switch the objective function
                count += 1
                objective1_bound = point[0]
                objective2_bound = point[1]

                # make a deep copy of the model made by the design space exploration : bound_instance
                model_instance = bound_instance # copy.deepcopy(bound_instance) I don't think this is necessary
                # bound both objectives
                self.bound_objective(model_instance, objective1, objective1_bound,
                                     flipped=True, constraint_name="bound_Objective1")

                self.bound_objective(model_instance, objective2, objective2_bound,
                                     flipped=True, constraint_name="bound_Objective2")

                # bound will be constantly overwritten to the name of the constraint, SO should not overwrite the space
                # bounds of the feasible region

                # set the objective to the according to the randomized swich objective
                self.change_model_objective(model_instance, objective2)
                # deactivating this part for now
                # if objectiveSwitch:
                #     self.change_model_objective(model_instance, objective2)
                # else:
                #     self.change_model_objective(model_instance, objective1)

                try:
                    single_opt_solved = self.single_optimizer.run_optimization(model_instance, tee=False)
                    single_opt_solved._tidy_data()
                    model_output.add_process("sc{}".format(count), single_opt_solved)
                except:
                    pass # if the optimization is infeasible, we just skip it

        return model_output

    def run_optimization_multi_sensitivity(self):
        pass

    def change_model_objective(self, model_instance, objective, flipSense=False):
        """
        This function is used to change the objective function of the model instance
        :param model_instance: the model instance to change the objective function
        :param objective: the new objective function
        :return: model_instance with the new objective function
        """

        # Determine the sense of the objective
        if flipSense:
            if objective == "EBIT":
                objective_sense = minimize
            else:
                objective_sense = maximize
        else:
            if objective == "EBIT":
                objective_sense = maximize
            else:
                objective_sense = minimize

        model_instance.del_component(model_instance.Objective)

        if objective == "NPC":
            def Objective_rule(Instance):
                return Instance.NPC
            model_instance.Objective = Objective(rule=Objective_rule, sense=objective_sense)

        elif objective == "EBIT":
            def Objective_rule(Instance):
                return Instance.EBIT
            model_instance.Objective = Objective(rule=Objective_rule, sense=objective_sense)

        elif objective == "NPE":
            def Objective_rule(Instance):
                return Instance.NPE
            model_instance.Objective = Objective(rule=Objective_rule, sense=objective_sense)

        elif objective == "FWD":
            def Objective_rule(Instance):
                return Instance.NPFWD
            model_instance.Objective = Objective(rule=Objective_rule, sense=objective_sense)

        else:
            if objective in list(model_instance.IMPACT_CATEGORIES):
                def Objective_rule(Instance):
                    return Instance.IMPACT_TOT[objective]
                model_instance.Objective = Objective(rule=Objective_rule, sense=objective_sense)

            else:
                raise Exception("The objective function {} is not defined in the model instance".format(objective))

        return objective_sense # -1 if maximize, 1 if minimize


    def bound_objective(self, model_instance, objective, bound, flipped=False, constraint_name = "boundObjective"):
        """
        This function is used to bound the objective function of the model instance
        :param model_instance: the model instance to change the objective function
        :param objective: the objective function restricted by the bound
        :param bound: the bound value for the objective function
        :param flipped: boolean to switch the default >= or <= in the constraint
        :return: model_instance with the new objective function
        """

        # Determine the constraint operator based on the flipped parameter
        if flipped:
            if objective == "EBIT":
                operator = lambda x, y: x <= y
            else:
                operator = lambda x, y: x >= y
        else:
            if objective == "EBIT":
                operator = lambda x, y: x >= y
            else:
                operator = lambda x, y: x <= y # fixme!! important bug when the NPc is negative the > needs to be flipped!!!!!!!!!!!!!

        # Create a new objective function and bounds
        if objective == "NPC":
            def bound_objective_rule(Instance):
                return operator(Instance.NPC, bound)

        elif objective == "EBIT":
            def bound_objective_rule(Instance):
                return operator(Instance.EBIT, bound)

        elif objective == "NPE":
            def bound_objective_rule(Instance):
                return operator(Instance.NPE, bound)

        elif objective == "FWD":
            def bound_objective_rule(Instance):
                return operator(Instance.NPFWD, bound)
        else:
            if objective in model_instance.impact_categories_list:
                def bound_objective_rule(Instance):
                    return operator(Instance.IMPACT_TOT[objective], bound)
            else:
                raise Exception("The objective function {} is not defined in the model instance".format(objective))

        # set the bound constraint
        setattr(model_instance, constraint_name, Constraint(rule=bound_objective_rule))

    def bound_region_objective(self, model_instance, objective, bound, boundType):
        """
        This function is used to bound the objective function to a predetermined region!
        :param model_instance: the model instance to change the objective function
        :param objective: the objective function restricted by the bound
        :param bound: the bound value for the objective function
        :param flipped: boolean to switch the default >= or <= in the constraint
        :return: model_instance with the new objective function
        """


        # Create a new objective function and bounds
        if objective == "NPC" and boundType == "upper":
            def bound_objective_rule_NPC_upper(Instance):
                return Instance.NPC <= bound
            setattr(model_instance, "bound_NPC_upper", Constraint(rule=bound_objective_rule_NPC_upper))

        elif objective == "NPC" and boundType == "lower":
            def bound_objective_rule_NPC_lower(Instance):
                return Instance.NPC >= bound
            setattr(model_instance, "bound_NPC_lower", Constraint(rule=bound_objective_rule_NPC_lower))

        elif objective == "EBIT" and boundType == "upper":
            def bound_objective_rule_EBIT_upper(Instance):
                return Instance.EBIT <= bound
            setattr(model_instance, "bound_EBIT_upper", Constraint(rule=bound_objective_rule_EBIT_upper))

        elif objective == "EBIT" and boundType == "lower":
            def bound_objective_rule_EBIT_lower(Instance):
                return Instance.EBIT >= bound
            setattr(model_instance, "bound_EBIT_lower", Constraint(rule=bound_objective_rule_EBIT_lower))

        elif objective == "NPE" and boundType == "upper":
            def bound_objective_rule_NPE_upper(Instance):
                return Instance.NPE <= bound
            setattr(model_instance, "bound_NPE_upper", Constraint(rule=bound_objective_rule_NPE_upper))

        elif objective == "NPE" and boundType == "lower":
            def bound_objective_rule_NPE_lower(Instance):
                return Instance.NPE >= bound
            setattr(model_instance, "bound_NPE_lower", Constraint(rule=bound_objective_rule_NPE_lower))

        elif objective == "FWD" and boundType == "upper":
            def bound_objective_rule_FWD_upper(Instance):
                return Instance.NPFWD <= bound
            setattr(model_instance, "bound_FWD_upper", Constraint(rule=bound_objective_rule_FWD_upper))

        elif objective == "FWD" and boundType == "lower":
            def bound_objective_rule_FWD_lower(Instance):
                return Instance.NPFWD >= bound
            setattr(model_instance, "bound_FWD_lower", Constraint(rule=bound_objective_rule_FWD_lower))

        else:
            if objective in model_instance.impact_categories_list and boundType == "upper":
                def bound_objective_rule_impact_upper(Instance):
                    return Instance.IMPACT_TOT[objective] <= bound
                setattr(model_instance, "bound_impact_upper", Constraint(rule=bound_objective_rule_impact_upper))

            elif objective in model_instance.impact_categories_list and boundType == "lower":
                def bound_objective_rule_impact_lower(Instance):
                    return Instance.IMPACT_TOT[objective] >= bound
                setattr(model_instance, "bound_impact_lower", Constraint(rule=bound_objective_rule_impact_lower))

            else:
                raise Exception("The objective function {} is not defined in the model instance".format(objective))

    def sample_uniform_in_polygon(self, poly, n_samples=1000):
        """
        Sample n_samples points uniformly in the 2D polygon poly.
        Returns a list of (x, y) coordinates.
        """
        minx, miny, maxx, maxy = poly.bounds
        samples = []
        random.seed(42)

        while len(samples) < n_samples:
            # 1. Sample a random point in the bounding box
            x_rand = random.uniform(minx, maxx)
            y_rand = random.uniform(miny, maxy)

            # 2. Check if it lies within the polygon
            p = Point(x_rand, y_rand)
            if poly.contains(p):
                samples.append((x_rand, y_rand))

        return samples

    def create_bounded_design_space(self, model_instance, bounds_design_space):

        # deep copy the model instance so that the original model instance is not changed
        model_instance_copy = copy.deepcopy(model_instance)

        objective1 = self.multi_data["objective1"]
        objective2 = self.multi_data["objective2"]

        # get the bounds of the objective functions
        min_obj_1 = bounds_design_space['min_obj1']
        max_obj_1 = bounds_design_space['max_obj1']
        min_obj_2 = bounds_design_space['min_obj2']
        max_obj_2 = bounds_design_space['max_obj2']

        if min_obj_1 is not None:
            self.bound_region_objective(model_instance_copy, objective1, min_obj_1, "lower")
        if max_obj_1 is not None:
            self.bound_region_objective(model_instance_copy, objective1, max_obj_1, "upper")
        if min_obj_2 is not None:
            self.bound_region_objective(model_instance_copy, objective2, min_obj_2, "lower")
        if max_obj_2 is not None:
            self.bound_region_objective(model_instance_copy, objective2, max_obj_2, "upper")

        return model_instance_copy


    def _create_model_bounded_old(self, model_output, model_instance_original, objective, bounds, saveName,
                              flipSenseObjective):
        """
        This function is used to create a model instance with the same structure as the original model instance,
        but bounded according to the options of the multi-objective optimization for the design space exploration

        :param model_output: the model output object to store the results
        :param model_instance_original: the original unmodified model instance
        :param objective: the objective function to bound
        :param bounds: the bounds for the objective function tuple
        :param saveName: the name to save the results in the model output object
        :param flipSense: boolean to switch the default >= or <= in the constraint of ma

        :return: model_instance
        """
        min_obj = bounds[0]
        max_obj = bounds[1]

        # deep copy the model instance so that the original model instance is not changed
        model_instance = copy.deepcopy(model_instance_original)

        # get the sense of the objective function
        sense_opt = self.change_model_objective(model_instance, objective, flipSense=flipSenseObjective)

        if sense_opt == -1 and max_obj is not None:  # maximize
            self.bound_objective(model_instance, objective, max_obj)

        elif sense_opt == 1 and min_obj is not None:  # minimize
            self.bound_objective(model_instance, objective, min_obj, flipped=True)

        try:
            optimized_instance = self.single_optimizer.run_optimization(model_instance)
            optimized_instance._tidy_data()
            model_output.add_process(saveName, optimized_instance)
        except:
            if min_obj is not None and max_obj is not None:
                raise Exception("The optimization problem is infeasible for the bound: {}"
                                " \n of objective {}, please choose another".format((min_obj, max_obj), objective))
            else:
                raise Exception("The optimization problem is infeasible, check for model "
                                "inconsistencies".format((min_obj, max_obj), objective))

        return optimized_instance

    def _create_model_bounded(self, model_output, model_instance_original,
                              objective2bound, bound, flipBound,
                              objective2Change, flipObjective,
                              saveName):
        """
        This function is used to create a model instance with the same structure as the original model instance,
        but bounded according to the options of the multi-objective optimization for the design space exploration

        :param model_output: the model output object to store the results
        :param model_instance_original: the original unmodified model instance
        :param objective2Change: the objective function to change
        :param objective2bound: the objective function to bound
        :param bounds: the bound for the objective function float
        :param saveName: the name to save the results in the model output object
        :param flipSense: boolean to switch the default >= or <= in the constraint

        :return: optimized_instance, a single optimization model output object
        """

        # deep copy the model instance so that the original model instance is not changed
        model_instance = copy.deepcopy(model_instance_original)

        # get the sense of the objective function
        self.change_model_objective(model_instance, objective2Change, flipSense=flipObjective)

        if bound is not None:  # maximize
            self.bound_objective(model_instance, objective2bound, bound, flipped=flipBound)

        try:
            optimized_instance = self.single_optimizer.run_optimization(model_instance)
            optimized_instance._tidy_data()
            model_output.add_process(saveName, optimized_instance)
        except:
            if bound is not None:
                raise Exception("The optimization problem is infeasible for the bound: {}"
                                " \n of objective {}, please choose another".format(bound, objective2bound))
            else:
                raise Exception("The optimization problem is infeasible, check for model "
                                "inconsistencies")

        return optimized_instance

class SensitivityOptimizer(SingleOptimizer):
    def __init__(
        self,
        solver_name,
        solver_interface,
        solver_options=None,
        sensi_data=None,
        superstructure=None,
    ):
        super().__init__(solver_name, solver_interface, solver_options)

        self.sensi_data = sensi_data
        self.superstructure = superstructure

        self.single_optimizer = SingleOptimizer(solver_name, solver_interface, solver_options)

    def run_optimization(self, model_instance,
                         optimization_mode = None,
                         solver = "gurobi",
                         interface = "local",
                         solver_path = None,
                         options = None,
                         count_variables_constraints = False):

        timer1 = time_printer(programm_step="Sensitivity optimization")
        sensi_data_Dict_lists = self.calculate_sensitive_parameters(self.sensi_data)

        initial_model_instance = model_instance.clone()
        time_printer(passed_time=timer1, programm_step="Create initial ModelInstance copy")
        model_output = MultiModelOutput(optimization_mode="sensitivity")

        superstructureData = self.superstructure


        for parameterName, (value_list, metadata) in sensi_data_Dict_lists.items():
            for val in value_list:
                model_instance = change_parameter(Instance=model_instance,
                                                  parameter=parameterName,
                                                  value=val, metadata=metadata,
                                                  superstructure= superstructureData)

                single_solved = self.single_optimizer.run_optimization(model_instance)

                single_solved._tidy_data()
                model_output.add_process((parameterName, val), single_solved)

            model_instance = initial_model_instance

        model_output.set_sensitivity_data(self.sensi_data)
        timer = time_printer(timer1, "Sensitivity optimization")
        model_output.fill_information(timer)
        return model_output

    def _solve_single_optimisation(self, model_instance, senitivityData):
        """
        This function is used to solve the single optimisation problem for each parameter in the sensitivity analysis
        :param model_instance:
        :param senitivityData:
        :return:

        # NOT REALLY WORKING LORD HELP ME PLEASE
        the idea is to use this function to run parralell computing using follwong code:
         # Using ProcessPoolExecutor to solve models in parallel
        with ProcessPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.solve_single_optimisation, model_instance) for data in data_list]
            results = [future.result() for future in futures]

        """
        # parameterName = senitivityData
        # for parameterName, (value_list, metadata) in sensi_data_Dict_lists.items():
        #     for val in value_list:
        #         model_instance = change_parameter(Instance=model_instance,
        #                                           parameter=parameterName,
        #                                           value=val, metadata=metadata,
        #                                           superstructure= superstructureData)
        #
        #         single_solved = self.single_optimizer.run_optimization(model_instance)
        #
        #         single_solved._tidy_data()
        #         model_output.add_process((parameterName, val), single_solved)
        #
        #     model_instance = initial_model_instance
        pass

class TwoWaySensitivityOptimizer(SingleOptimizer):
    def __init__(
        self,
        solver_name,
        solver_interface,
        solver_options=None,
        two_way_data=None,
        superstructure=None,
    ):

        super().__init__(solver_name, solver_interface, solver_options)

        self.cross_parameters = two_way_data
        self.superstructure = superstructure

        self.single_optimizer = SingleOptimizer(
            solver_name, solver_interface, solver_options
        )

    def run_optimization(self,
                         model_instance,
                         optimization_mode=None,
                         solver="gurobi",
                         interface="local",
                         solver_path=None,
                         options=None,
                         count_variables_constraints=False,
                         parralellComputing = False
                         ):

        timer1 = time_printer(programm_step="Two-way sensitivity optimimization")
        self.cross_parameters = self.calculate_sensitive_parameters(self.cross_parameters)

        model_output = MultiModelOutput(optimization_mode="cross-parameter sensitivity")

        index_names = list()
        dic_1 = dict()
        dic_2 = dict()

        for i in self.cross_parameters.keys():
            index_names.append(i)

        for i, j in self.cross_parameters.items():
            if i == index_names[0]:
                dic_1[i] = j
            elif i == index_names[1]:
                dic_2[i] = j

        paramName1 = list(dic_1.keys())[0]
        paramName2 = list(dic_2.keys())[0]

        parmaValues1 = list(dic_1.values())[0][0]
        paramValues2 = list(dic_2.values())[0][0]

        metadata1 = list(dic_1.values())[0][1]
        metadata2 = list(dic_2.values())[0][1]

        if parralellComputing:
            # todo make parallel computing work
            # Using ProcessPoolExecutor to solve models in parallel
            with ProcessPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(self._solve_model_instance,
                                           paramName1, paramName2,
                                           paramVal1, paramVal2,
                                           metadata1, metadata2,
                                           model_instance, model_output)
                           for paramVal1 in parmaValues1 for paramVal2 in paramValues2]

                results = [future.result() for future in futures]
            print(results)
        # model_output.add_process((paramName1, paramVal1, paramName2, paramVal2), single_solved)

        else:
            for i in parmaValues1:
                for j in paramValues2:
                    self._solve_model_instance(paramName1, paramName2,
                                                 i, j,
                                                 metadata1, metadata2,
                                                 model_instance, model_output)



        timer = time_printer(timer1, "Ending Two-way sensitivity Analysis")
        model_output.fill_information(timer)
        return model_output

    def _solve_model_instance(self, paramName1, paramName2,
                              paramVal1, paramVal2,
                              metadata1, metadata2,
                              model_instance, model_output):
        """
        This function is used to solve the model instance for a given parameter set
        :param param1:
        :param param2:
        :param model_instance:
        :param superstructure:
        :return:

        """
        superstructure = self.superstructure

        model_instance = change_parameter(Instance=model_instance,
                                          parameter=paramName1,
                                          value=paramVal1, metadata=metadata1,
                                          superstructure=superstructure,
                                          printTimer=False)

        model_instance = change_parameter(Instance=model_instance,
                                          parameter=paramName2,
                                          value=paramVal2, metadata=metadata2,
                                          superstructure=superstructure,
                                          printTimer=False)

        single_solved = self.single_optimizer.run_optimization(model_instance,
                                                               tee=False,
                                                               keepfiles=True,
                                                               printTimer=False)
        single_solved._tidy_data()
        model_output.add_process((paramName1, paramVal1, paramName2, paramVal2), single_solved)
        return (paramName1, paramVal1, paramName2, paramVal2), single_solved


class StochasticRecourseOptimizer(SingleOptimizer):
    # NOT USED ANYMORE IN THE NEW VERSION, SEE StochasticOptimizer_mpi_sppy!!
    # keep it for now, just in case I need code snippets from it
    def __init__(
        self,
        solver_name,
        solver_interface,
        input_data,
        solver_options=None,
        single_model_instance=None,
        stochastic_options=None,
        remakeMetadata = None
    ):

        super().__init__(solver_name, solver_interface, solver_options)
        self.single_optimizer = SingleOptimizer(solver_name, solver_interface, solver_options)
        self.input_data = input_data
        self.single_model_instance_4_EVPI = single_model_instance.clone()
        self.single_model_instance_4_VSS = single_model_instance.clone()
        self. remakeMetadata = remakeMetadata
        if stochastic_options is None:
            self.stochastic_options = {
                "calculation_EVPI": False,
                "calculation_VSS": False,
            }
        else:
            self.stochastic_options = stochastic_options

    def run_optimization(self,
                         model_instance,
                         optimization_mode=None,
                         solver="gurobi",
                         interface="local",
                         solver_path=None,
                         options=None,
                         count_variables_constraints=False,

                         ):


        # preallocate the variables
        infeasibleScenarios = None
        waitAndSeeSolution = 0
        average_VSS = 0

        # get the input data and stochastic options
        input_data = self.input_data
        calculation_EVPI = self.stochastic_options["calculation_EVPI"]
        calculation_VSS = self.stochastic_options["calculation_VSS"]

        waitAndSeeSolutionDict = {}
        EEVDict = {}

        # calculate the EVPI and VSS, if not on a rerun (i.e. if the remakeMetadata is not None)
        # ---------------------------------------------------------------------------------------
        if self.remakeMetadata:
            EEVList = self.remakeMetadata["EEVList"]
            waitAndSeeSolutionList = self.remakeMetadata["waitAndSeeSolutionList"]
            infeasibleScenarios = self.remakeMetadata["infeasibleScenarios"]
        else:
            # make a deep copy of the input data so the stochastic parameters can be transformed to final dataformat
            Stochastic_input_EVPI = copy.deepcopy(input_data)
            Stochastic_input_EVPI.create_DataFile()
            Stochastic_input_vss = copy.deepcopy(Stochastic_input_EVPI)

            if calculation_EVPI:
                # timer for the EVPI calculation
                startEVPI = time_printer(programm_step="EPVI calculation")
                # create the Data_File Dictionary in the object input_data

                waitAndSeeSolutionDict, infeasibleScenarios = self.get_WaitAndSee(Stochastic_input_EVPI)
                time_printer(passed_time=startEVPI, programm_step="EPVI calculation")

            if calculation_VSS:
                startVSS = time_printer(programm_step="VSS calculation")
                # calculate the VSS
                EEVDict = self.get_EEV(Stochastic_input_vss)
                time_printer(passed_time=startVSS, programm_step="VSS calculation")

            # ---------------------------------------------------------------------------------------

            # continue with the stochastic optimization
            # if there are infeasible scenarios, we need to remove them from the input data
            if infeasibleScenarios: # if the list is not empty
                print("\033[1;32m" + "unfeasible scenarios detected, removing them from the input data and "
                                     "reconstructing the model" + "\033[0m")

                #model_instance = self.curate_stochastic_model_intance(model_instance, infeasibleScenarios)
                #model_output = ("remake_stochastic_model_instance", infeasibleScenarios)
                # make a dictionary of all the values we need to pass on to the model output, needed for the rerun:
                # infeasibleScenarios, EEVList, waitAndSeeSolutionList
                model_output = {"infeasibleScenarios": infeasibleScenarios,
                                "EEVList": EEVDict,
                                "waitAndSeeSolutionList": waitAndSeeSolutionDict,
                                "Status": "remake_stochastic_model_instance" }
                return model_output


        # run the optimization
        model_output = self.single_optimizer.run_optimization(model_instance=model_instance,
                                                              stochastic_optimisation=True)

        # pass on the uncertainty data to the model output
        model_output.uncertaintyDict = input_data.uncertaintyDict
        #time_printer(solving_time, "Superstructure optimization procedure")

        objectiveName = model_output._objective_function
        expected_value = model_output._data[objectiveName]

        # pass on the EVPI and VSS to the model output

        if calculation_EVPI:
            waitAndSeeSolution = self.calculate_final_EEV_or_WS(model_output._data['odds'], waitAndSeeSolutionDict)
            # Use ANSI escape codes to make the text purple and bold
            print("\033[95m\033[1mThe EVwPI is:", waitAndSeeSolution, "\033[0m")

            # pass on the EVPI
            if model_output._data['objective_sense'] == 1: # 1 if optimisation is maximised 0 if minimized 1
                model_output.EVPI = waitAndSeeSolution - expected_value
            else:
                model_output.EVPI = expected_value - waitAndSeeSolution
            model_output.infeasibleScenarios = infeasibleScenarios

        if calculation_VSS:
            # EEV = self.curate_EEV(EEVList, expected_value)
            EEV = self.calculate_final_EEV_or_WS(model_output._data['odds'], EEVDict)
            # print the EEV
            print("\033[95m\033[1mThe EEV is:", EEV, "\033[0m")
            if model_output._data['objective_sense'] == 1: # 1 if optimisation is maximised 0 if minimized
                model_output.VSS = expected_value - EEV
            else:
                model_output.VSS = EEV - expected_value

        # pass on the default scenario if it changed
        # (extra parameter is data to the input data object in this case)
        if hasattr(input_data, 'DefaultScenario'):
            model_output.DefaultScenario = input_data.DefaultScenario
        else:
            model_output.DefaultScenario = 'sc1'

        # self.debug_EVPI(model_output, Stochastic_input_EVPI, solver, interface, solver_path, options)
        # self.debug_VSS(model_output, Stochastic_input_EVPI, solver, interface, solver_path, options)


        return model_output

    def calculate_final_EEV_or_WS(self, probabilities, metricDict):
        """
        This function calculates the EVPI based on the probabilities of the scenarios
        :param probabilities: Dict of probabilities of each scenario
        :param metricDict: Dict of wait and see solutions or Expected results of Expected values
        :return: metric: the weighted sum of the EVPI or EEV
        """
        metric = 0
        for key, value in probabilities.items():
            prob = value
            i = metricDict[key]
            metric += prob * i
        return metric

    def get_WaitAndSee(self, input_data=None):
        """
        This function is used to calculates the EVPI of a stochastic problem.
        :param input_data: of the signal optimization run
        :param solver:
        :param interface:
        :param solver_path:
        :param options:
        :return: EVPI

        """

        # get data from the object
        #model_instance_EVPI = copy.deepcopy(self.single_model_instance)
        model_instance_EVPI = self.single_model_instance_4_EVPI
        singleInput = self.input_data.parameters_single_optimization
        optimizer = self.single_optimizer

        # the next step is to run individual optimizations for each scenario and save the results in a list
        # first we need to get the scenarios from the input data
        scenarios = input_data.Scenarios['SC']

        # now we need to run the single run optimization for each scenario
        # we need to save the objective values in a list
        WaitAndSeeDict = {}
        objectiveValueList_EVPI = []
        infeasibleScenarios = []
        selectedTechnologies = []

        # Green and bold text
        print("\033[1;32m" + "Calculating the objective values for each scenario to calculate the EVPI\n"
                             "Please be patient, this might take a while" + "\033[0m")

        # Suppress the specific warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.ERROR)
        total_scenarios = len(scenarios)

        for index, sc in enumerate(scenarios):

            # model for EVPI calculation, the only difference is that the boolean variables are not fixed
            # i.e. all model variables are optimised according to the scenario parameters
            modelInstanceScemarioEVPI = self.set_parameters_of_scenario(scenario=sc, singleInput=singleInput,
                                                               stochasticInput=input_data, model=model_instance_EVPI)

            # run the optimization
            modelOutputScenario_EVPI = optimizer.run_optimization(model_instance=modelInstanceScemarioEVPI, tee=False,
                                                                  keepfiles=False, printTimer=False, VSS_EVPI_mode=True)

            if modelOutputScenario_EVPI == 'infeasible':
                infeasibleScenarios.append(sc)
            else: # save the results
                objectiveName = modelOutputScenario_EVPI._objective_function
                objectiveValueList_EVPI.append(modelOutputScenario_EVPI._data[objectiveName])

                WaitAndSeeDict.update({sc: modelOutputScenario_EVPI._data[objectiveName]})
                chosenTechnology = modelOutputScenario_EVPI.return_chosen()
                selectedTechnologies.append(chosenTechnology)

            # print the progress bar
            print_progress_bar(iteration=index, total=total_scenarios, prefix='EVPI', suffix='')


        # now we have the objective values for each scenario in a list
        # the next step is to calculate the EVPI
        #EVPI = np.mean(objectiveValueList_EVPI)

        # Print a newline character to ensure the next console output is on a new line.
        print()
        # reactivate the warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.WARNING)
        # count the unique sets of selected technologies
        self.count_unique_sets(selectedTechnologies)

        # make a set of infeasible scenarios to get rid of duplicates
        infeasibleScenarios = set(infeasibleScenarios)

        return WaitAndSeeDict, infeasibleScenarios

    def get_EEV(self, stochastic_input_data=None):
        """
        This function is used to calculate the VSS of a stochastic problem.
        :param stochastic_model_output: is the model output of the stochastic optimisation
        :param input_data of the signal optimisation run::
        :param optimization_mode:
        :param solver:
        :param interface:
        :param solver_path:
        :param options:
        :return:
        """

        def MassBalance_3_rule(self, u_s, u):
            return self.FLOW_ADD[u_s, u] <= self.alpha[u] * self.Y[u]  # Big M constraint

        def MassBalance_6_rule(self, u, uu, i):
            if (u, uu) not in self.U_DIST_SUB:
                    if (u, uu) in self.U_CONNECTORS:
                        return self.FLOW[u, uu, i] <= self.myu[u, uu, i] * self.FLOW_OUT[
                            u, i
                            ] + self.alpha[u] * (1 - self.Y[uu])
                    else:
                        return Constraint.Skip

            else:
                return self.FLOW[u, uu, i] <= sum(
                    self.FLOW_DIST[u, uu, uk, k, i]
                    for (uk, k) in self.DC_SET
                    if (u, uu, uk, k) in self.U_DIST_SUB2
                ) + self.alpha[u] * (1 - self.Y[uu])

        def MassBalance_7_rule(self, u, uu, i):
            if (u,uu) in self.U_CONNECTORS:
                return self.FLOW[u, uu, i] <= self.alpha[u] * self.Y[uu]
            else:
                return Constraint.Skip

        def MassBalance_8_rule(self, u, uu, i):
            if (u, uu) not in self.U_DIST_SUB:
                if (u, uu) in self.U_CONNECTORS:
                    return self.FLOW[u, uu, i] >= self.myu[u, uu, i] * self.FLOW_OUT[
                        u, i
                        ] - self.alpha[u] * (1 - self.Y[uu])
                else:
                    return Constraint.Skip
            else:
                return self.FLOW[u, uu, i] >= sum(
                    self.FLOW_DIST[u, uu, uk, k, i]
                    for (uk, k) in self.DC_SET
                    if (u, uu, uk, k) in self.U_DIST_SUB2
                ) - self.alpha[u] * (1 - self.Y[uu])

        def GWP_6_rule(self, u):
            return self.GWP_UNITS[u] == self.em_fac_unit[u] / self.LT[u] * self.Y[u]

        def ProcessGroup_logic_1_rule(self, u, uu):

            ind = False

            for i, j in self.groups.items():

                if u in j and uu in j:
                    return self.Y[u] == self.Y[uu]
                    ind = True

            if ind == False:
                return Constraint.Skip

        def ProcessGroup_logic_2_rule(self, u, k):

            ind = False

            for i, j in self.connections.items():
                if u == i:
                    if j[k]:
                        return sum(self.Y[uu] for uu in j[k]) >= self.Y[u]
                        ind = True

            if ind == False:
                return Constraint.Skip

        # start with the VSS calculation by setting up a model instance with the single optimization data parameters
        # first run the single run optimization to get the unit operations
        singleInput = self.input_data.parameters_single_optimization
        # singleInput.optimization_mode = "single" # just to make sure
        optimization_mode = "single"
        # populate the model instance with the input data
        model_instance_deterministic_average = self.single_model_instance_4_VSS
        model_instance_variable_params = model_instance_deterministic_average.clone()

        # STEP 1: solve the deterministic model with the average values (i.e. the expected value)
        # -----------------------------------------------------------------------------------------------
        # solve the deterministic model with the average values of the stochastic parameters (i.e. the expected value)

        # settings optimization problem, the optimizer is the single run optimiser
        optimizer = self.single_optimizer

        # run the optimisation
        # EVV expected value problem or mean value problem

        model_output_VSS_average = optimizer.run_optimization(model_instance=model_instance_deterministic_average,
                                                              tee=False, printTimer=False, VSS_EVPI_mode=True)

        if model_output_VSS_average == 'infeasible':
            raise Exception("The model to calculate the VSS is infeasible, please check the input data for the single optimisation problem is correct ")

        # extract the first stage decisions from the model output, i.e. the boolean variables
        BooleanVariables = model_output_VSS_average._data['Y']

        # STEP 2: make the model instance for the VSS calculation with 1st stage decisions fixed
        # -------------------------------------------------------------------------------------------------
        # now make the model where the boolean variables are fixed as parameters
        # loop of ther BooleanVariables and transform the item in the dict to the absolute value
        for key, value in BooleanVariables.items():
            if value is not None:
                BooleanVariables[key] = abs(value)

        # change the model instance copy and fix the boolean variables as parameters
        model_instance_variable_params.del_component(model_instance_variable_params.Y)
        model_instance_variable_params.Y = Param(model_instance_variable_params.U, initialize=BooleanVariables,
                                                 mutable=True, within=Any)

        # delete and redefine the constraints which are affected by the boolean variables
        model_instance_variable_params.del_component(model_instance_variable_params.MassBalance_3)
        model_instance_variable_params.del_component(model_instance_variable_params.MassBalance_6)
        model_instance_variable_params.del_component(model_instance_variable_params.MassBalance_7)
        model_instance_variable_params.del_component(model_instance_variable_params.MassBalance_8)
        model_instance_variable_params.del_component(model_instance_variable_params.EnvironmentalEquation6)  # GWP_6
        model_instance_variable_params.del_component(model_instance_variable_params.ProcessGroup_logic_1)
        model_instance_variable_params.del_component(model_instance_variable_params.ProcessGroup_logic_2)

        # define the constraints again
        model_instance_variable_params.MassBalance_33 = Constraint(model_instance_variable_params.U_SU, rule=MassBalance_3_rule)
        model_instance_variable_params.MassBalance_66 = Constraint(model_instance_variable_params.U, model_instance_variable_params.UU, model_instance_variable_params.I, rule=MassBalance_6_rule)
        model_instance_variable_params.MassBalance_77 = Constraint(model_instance_variable_params.U, model_instance_variable_params.UU, model_instance_variable_params.I, rule=MassBalance_7_rule)
        model_instance_variable_params.MassBalance_88 = Constraint(model_instance_variable_params.U, model_instance_variable_params.UU, model_instance_variable_params.I, rule=MassBalance_8_rule)
        model_instance_variable_params.EnvironmentalEquation66 = Constraint(model_instance_variable_params.U_C, rule=GWP_6_rule)
        model_instance_variable_params.ProcessGroup_logic_11 = Constraint(model_instance_variable_params.U, model_instance_variable_params.UU, rule=ProcessGroup_logic_1_rule)
        numbers = [1, 2, 3]
        model_instance_variable_params.ProcessGroup_logic_22 = Constraint(model_instance_variable_params.U, numbers, rule=ProcessGroup_logic_2_rule)


        # STEP 3: loop over all scenarios and solve the model for each scenario save the results in a list
        # -------------------------------------------------------------------------------------------------
        # now we need to run the single run optimisation for each scenario and save the results in a list
        # now we have the model instance with the fixed boolean variables as parameters
        # the next step is to run individual optimisations for each scenario and save the results in a list
        # first we need to get the scenarios from the input data
        scenarios = stochastic_input_data.Scenarios['SC']
        total_scenarios = len(scenarios)

        # now we need to run the single run optimisation for each scenario
        # preallocate the variables
        EEVDict = {} # dictionary of the EEV for each scenario EEV = Expected results of the Expected Value problem
        objectiveValueList_VSS = []
        infeasibleScenarios = []

        # Green and bold text, warning this might take a while
        print("\033[1;32m" + "Calculating the objective values for each scenario to calculate the VSS\n"
                             "Please be patient, this might take a while" + "\033[0m")

        # Suppress the specific warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.ERROR)

        # set the options for the single run optimisation
        # set model options

        for index, sc in enumerate(scenarios):
            # model for VSS calculation
            modelInstanceScemario_VSS = self.set_parameters_of_scenario(scenario=sc, singleInput=singleInput,
                                                               stochasticInput=stochastic_input_data, model=model_instance_variable_params)

            # run the optimization
            modelOutputScenario_VSS = optimizer.run_optimization(model_instance=modelInstanceScemario_VSS, tee=False,
                                                                 keepfiles=False, printTimer=False, VSS_EVPI_mode=True)

            if modelOutputScenario_VSS == 'infeasible':
                infeasibleScenarios.append(sc)
            else:
                objectiveName = modelOutputScenario_VSS._objective_function
                objectiveValueList_VSS.append(modelOutputScenario_VSS._data[objectiveName])
                EEVDict.update({sc: modelOutputScenario_VSS._data[objectiveName]})

            # print the progress bar
            print_progress_bar(iteration=index, total=total_scenarios, prefix='EVPI', suffix='')

        # now we have the objective values for each scenario in a Dictionary

        # Print a newline character to ensure the next console output is on a new line.
        print()
        # reactivate the warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.WARNING)

        # make a set of infeasible scenarios to get rid of duplicates
        if infeasibleScenarios:
            infeasibleScenarios = set(infeasibleScenarios)
            # print a warning in red and bold text
            print("\033[1;31m" + "The following scenarios during VSS calculations are infeasible:", infeasibleScenarios, "\n"
             " please check the optimization problem or report the problem to github \033[0m")

        return EEVDict

    def curate_EEV(self, EEV, expectedValueStochastic):
        """"
        The curation of the list of EEV is need because scenarios can exist where |Determinist value| > |Stochastic value|
        which should not be possible. This is due to the fact that the stochastic optimization takes into account the MAXIMUM
        reference flow rate to calculate the CAPEX. if this happens we'll assume that the deterministic value is equal to the stochastic value
        :param EEV: list of EEV
        :param expectedValueStochastic: expected value of the stochastic optimisation
        :return: EEV: mean of the EEV list
        """
        EEV_New = []
        for evv in EEV:
            if abs(evv) > abs(expectedValueStochastic):
                EEV_New.append(expectedValueStochastic)
            else:
                EEV_New.append(evv)
        EEVmean = np.mean(EEV_New)
        return EEVmean

    def set_parameters_of_scenario(self, scenario, singleInput, stochasticInput, model):
        """
        This function is used to set the parameters of the stochastic model instance according to the scenario
        for a single deterministic run.

        :param scenario:
        :param singleInput:
        :param stochasticInput:
        :param model:
        :return: model instance with the parameters of the scenario
        """

        # set the parameters of the single run optimisation
        singleDataFile = singleInput.Data_File
        # set the parameters of the stochastic run optimisation
        stochasticDataFile = stochasticInput.Data_File

        # need to go over the following parameters: phi, myu, xi, materialcosts, ProductPrice, gamma and theta
        # make a list of the parameters
        parameterList = ['phi', 'myu', 'xi', 'materialcosts', 'ProductPrice', 'gamma', 'theta']

        for parameter in parameterList:
            # first check if the parameter is in the single run optimization data
            if parameter in singleDataFile[None]:
                # get the parameter from the single run optimization
                parameterSingle = singleDataFile[None][parameter]
                # get the parameter from the stochastic run optimization
                parameterStochastic = stochasticDataFile[None][parameter]

                # update the model instance
                for index in parameterSingle:
                    if isinstance(index, tuple):
                        newIndex = tuple(list(index) + [scenario])
                    else:
                        newIndex = tuple([index] + [scenario])

                    new_value = parameterStochastic[newIndex]
                    model.__dict__[parameter][index] = new_value

        return model

    def count_unique_sets(self, list_of_dicts):
        """
        This function is used to count the number of unique sets in a list of dictionaries
        :param list_of_dicts: list of dictionaries with the unique sets of technologies
        :return: count: number of unique sets
        """
        # Create an ordered dictionary to store the count of each unique dictionary
        unique_dict_count = {}

        # Iterate through the list of dictionaries
        for dictionary in list_of_dicts:
            # Convert the dictionary to a tuple of key-value pairs for hashing
            dict_as_tuple = tuple(dictionary.items())

            # Check if the tuple representation is already in the unique_dict_count dictionary
            if dict_as_tuple in unique_dict_count:
                # If it's already in the dictionary, increment the count
                unique_dict_count[dict_as_tuple] += 1
            else:
                # If it's not in the dictionary, add it with a count of 1
                unique_dict_count[dict_as_tuple] = 1

        total_sets = len(list_of_dicts)
        for unique_dict, count in unique_dict_count.items():
            percent = round((count / total_sets) * 100, 1)
            print("\033[95m\033[1mDictionary:", dict(unique_dict), "percent (%):", percent, "\033[0m")

class HereAndNowOptimizer(SingleOptimizer):
    def __init__(
        self,
        solver_name,
        solver_interface,
        inputObject,
        solver_options=None,
        scenarioDataFiles=None,
        *args,
    ):
        super().__init__(solver_name, solver_interface, solver_options)

        self.inputObject = inputObject  # superstructure object
        self.single_optimizer = SingleOptimizer(solver_name, solver_interface, solver_options)
        if hasattr(inputObject, 'outputFileDesignSpace'):
            self.designSpaceFile = inputObject.outputFileDesignSpace
        self.scenarioDataFiles = scenarioDataFiles


    def run_optimization(self,
                         optimization_mode=None,
                         solver="gurobi",
                         interface="local",
                         solver_path=None,
                         options=None,
                         count_variables_constraints=False):

        # start timer
        timer1 = time_printer(programm_step="Start wait and see", printTimer=False)

        # get the scenario data files
        if hasattr(self.inputObject, 'scenarioDataFiles'):
            scenarioDataFiles = self.inputObject.scenarioDataFiles
        else:
            scenarioDataFiles = self.scenarioDataFiles


        # create output object to store the results
        model_output = MultiModelOutput(model_instance=None,
                                        optimization_mode=self.inputObject.optimization_mode,  # 'wait and see'
                                        solver_name=self.solver_name,
                                        run_time=None,
                                        gap=None,
                                        dataFiles=scenarioDataFiles)


        # preallocate the list of infeasible scenarios
        infeasibleScenarios = []

        # Green and bold text
        print("\033[1;32m" + "Calculating the objective values for each scenario and each passed on design\n"
                             "Please be patient, this might take a while" + "\033[0m")

        # Suppress the specific warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.ERROR)
        total_scenarios = len(scenarioDataFiles)

        for index, (scenario, dataFile) in enumerate(scenarioDataFiles.items()):
            # create a model instance for the scenario
            # initialize the model
            model = SuperstructureModel(self.inputObject, fixedDesign=True)

            # create the model equations
            model.create_ModelEquations()

            # you need to modify the data file to include the design space parameters Y_Dist and Y
            dataFile[None]['Y'] = self.designSpaceFile['Y']
            dataFile[None]['Y_DIST'] = self.designSpaceFile['Y_DIST']

            # populate the model instance
            modelInstance = model.populateModel(dataFile)

            # run the optimization problem for the scenario
            single_solved = self.single_optimizer.run_optimization(model_instance=modelInstance,
                                                                   tee=False,
                                                                   keepfiles=False,
                                                                   printTimer=False,
                                                                   VSS_EVPI_mode=True)

            if single_solved == 'infeasible':
                infeasibleScenarios.append(scenario)
            else:
                # tidy the data, i.e., delete variables and constraints that are 0
                single_solved._tidy_data()
                # add the results to the model output
                model_output.add_process(scenario, single_solved)

            # print the progress bar
            print_progress_bar(iteration=index, total=total_scenarios, prefix='EVPI', suffix='')

        timer = time_printer(timer1, printTimer=False, programm_step="Ending wait and see")
        model_output.fill_information(timer)

        # Print a newline character to ensure the next console output is on a new line.
        print()
        # reactivate the warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.WARNING)

        # add the uncertainty matrix to the model output
        model_output.uncertaintyMatrix = self.inputObject.uncertaintyMatrix

        return model_output

class WaitAndSeeOptimizer(SingleOptimizer):
    def __init__(
        self,
        solver_name,
        solver_interface,
        inputObject,
        solver_options=None,
    ):
        super().__init__(solver_name, solver_interface, solver_options)

        self.inputObject = inputObject # superstructure object
        self.single_optimizer = SingleOptimizer(solver_name, solver_interface, solver_options)

    def run_optimization(self,
                         optimization_mode = None,
                         solver = "gurobi",
                         interface = "local",
                         solver_path = None,
                         options = None,
                         count_variables_constraints = False):

        # start timer
        timer1 = time_printer(programm_step="Start wait and see", printTimer=False)

        # create output object to store the results
        model_output = MultiModelOutput(model_instance = None,
                                        optimization_mode = self.inputObject.optimization_mode, # 'wait and see'
                                        solver_name = self.solver_name,
                                        run_time = None,
                                        gap = None,
                                        dataFiles=self.inputObject.scenarioDataFiles)

        # get the scenario data files
        scenarioDataFiles = self.inputObject.scenarioDataFiles

        # preallocate the list of infeasible scenarios
        infeasibleScenarios = []

        # Green and bold text
        print("\033[1;32m" + "Calculating the objective values for each scenario to calculate the EVPI\n"
                             "Please be patient, this might take a while" + "\033[0m")

        # Suppress the specific warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.ERROR)
        total_scenarios = len(scenarioDataFiles)

        for index, (scenario, dataFile) in enumerate(scenarioDataFiles.items()):
            # create a model instance for the scenario
            # initialize the model
            model = SuperstructureModel(self.inputObject)

            # create the model equations
            model.create_ModelEquations()

            # populate the model instance
            modelInstance = model.populateModel(dataFile)

            # run the optimization problem for the scenario
            single_solved = self.single_optimizer.run_optimization(model_instance=modelInstance,
                                                                   tee=False,
                                                                   keepfiles=False,
                                                                   printTimer=False,
                                                                   VSS_EVPI_mode=True)

            if single_solved == 'infeasible':
                infeasibleScenarios.append(scenario)
            else:
                # tidy the data, i.e., delete variables and constraints that are 0
                single_solved._tidy_data()
                # add the results to the model output
                model_output.add_process(scenario, single_solved)

            # print the progress bar
            print_progress_bar(iteration=index, total=total_scenarios, prefix='EVPI', suffix='')


        timer = time_printer(timer1, printTimer=False, programm_step="Ending wait and see")
        model_output.fill_information(timer)

        # Print a newline character to ensure the next console output is on a new line.
        print()
        # reactivate the warning if model is infeasible
        logging.getLogger('pyomo.core').setLevel(logging.WARNING)

        # add the uncertainty matrix to the model output
        model_output.uncertaintyMatrix = self.inputObject.uncertaintyMatrix

        return model_output

class StochasticRecourseOptimizer_mpi_sppy(SingleOptimizer):

    def __init__(
        self,
        solver_name,
        solver_interface,
        inputObject,
        mpiOptions,
        solver_options=None,
    ):
        # initialize the single optimizer
        super().__init__(solver_name, solver_interface, solver_options)

        # set the optimization mode
        # todo find where the optimisation mode is passed on, this is not the right place to define it but ok for now
        self.optimization_mode = "2-stage-recourse"

        # initialize the input object
        if inputObject is None:
            raise Exception("No input object is provided")
        else:
            self.inputObject = inputObject

        if mpiOptions is None:
            raise Exception("No mpi-sppy options are provided")
        else:
            self.options = mpiOptions


    def run_optimization(self,*args, **kwargs):

        StartTimer = time_printer(printTimer=False)

        # run the stochastic optimization
        phResults = self.run_progressive_hedging(inputObject=self.inputObject,options=self.options)
        # phResults is a tuple with the following elements: (variablesR0, allVariables, VariableWarningDict)

        timeMpiSppy = time_printer(passed_time=StartTimer,
                                   printTimer=False)



        modelOutput = StochasticModelOutput_mpi_sppy(optimization_mode = '2-stage-recourse', #todo again shady, find where this variable is set and pass it on
                                                     mpi_sppy_results=phResults,
                                                     run_time = timeMpiSppy)
        # add the uncertainty matrix to the model output
        modelOutput.uncertaintyMatrix = self.inputObject.uncertaintyMatrix
        return modelOutput

    def scenario_creator(self, scenarioName):
        """
        This function is used to create instances of a scenario, used to run optimization problems under uncertainty
        using mpi-sppy. The function is called by mpi-sppy and should return a Pyomo model instance for the scenario

        :param scenario_name:
        :param inputObject:
        :return: model_instance
        """
        # takes long to load these modules, so only load them if needed
        import mpisppy.utils.sputils as sputils
        from mpisppy.opt.ef import ExtensiveForm

        # retrive the data file for all scenarios
        inputObject = self.inputObject
        scenarioDataFile = inputObject.scenarioDataFiles

        # initialize the model
        model = SuperstructureModel(inputObject)

        # create the model equations
        model.create_ModelEquations()

        # get the correct data file for the scenarioDataFile
        dataFile = scenarioDataFile[scenarioName]

        # populate the model instance
        modelInstance = model.populateModel(dataFile)

        # introduce the model instance to mpi-sppy
        sputils.attach_root_node(modelInstance,
                                 modelInstance.Objective,  # the objective function
                                 # the first stage variables, which are non-anticipative constraints.
                                 # i.e., do not change across scenarios. In this case, the binary variables responsible
                                 # for the selection of the technology
                                 [modelInstance.Y, modelInstance.DistFraction])  # todo add?  ,modelInstance.Y_DIST OR modelInstance.DistFraction

        modelInstance._mpisppy_probability = 1.0 / len(scenarioDataFile)

        return modelInstance

    def run_extensive_form(self, options, allScenarioNames):
        """
        This function runs the extensive form of the optimization problem. The extensive form is a deterministic
        optimization problem where all scenarios are considered. The function returns the objective value and the
        solution of the extensive form.

        :param options: a dictionary with options for the extensive form
        :param allScenarioNames: a list with the names of all scenarios
        :param scenario_creator: a function which creates the model instance for a scenario
        :return: objective value, solution
        """

        ef = ExtensiveForm(options, allScenarioNames, self.scenario_creator)
        results = ef.solve_extensive_form()

        objval = ef.get_objective_value()
        soln = ef.get_root_solution()

        return objval, soln

    def run_progressive_hedging(self, inputObject, options):
        """
        This function runs the progressive hedging algorithm for solving the stochastic optimization problem. The
        function returns the objective value and the solution of the progressive hedging algorithm.

        :param options: a dictionary with options for the progressive hedging algorithm
        :param all_scenario_names: a list with the names of all scenarios
        :param scenario_creator: a function which creates the model instance for a scenario
        :return: objective value, solution
        """
        # takes long to load these modules, so only load them if needed
        from mpisppy.opt.ph import PH

        allScenarioNames = list(inputObject.scenarioDataFiles.keys())
        self.inputObject = inputObject

        ph = PH(options,
                allScenarioNames,
                self.scenario_creator)

        ph.ph_main()

        variablesR0 = ph.gather_var_values_to_rank0()

        # Gather and print all variable values for the first scenario
        allVariables = {}
        VariableWarningDict = {}
        for sc in allScenarioNames:
            scenario = ph.local_scenarios[sc]
            allVariables.update({sc: {}})
            VariableWarningDict.update({sc: {}})
            # print(f"\nResults for scenario {allScenarioNames[0]}:")
            for var in scenario.component_objects(pyo.Var, active=None):
                try:
                    var_object = getattr(scenario, str(var))
                    for index in var_object:
                        allVariables[sc].update({f"{var}[{index}]": pyo.value(var_object[index])})

                        # if sc == allScenarioNames[0]: # only print the variables for the first scenario
                        #     print(f"{var}[{index}] = {pyo.value(var_object[index])}")

                except:
                    VariableWarningDict[sc].update({str(var): "Variable not calculated"})
                    # print(f"Variable {var_object} is not calculated!!")
                    continue

        return variablesR0, allVariables, VariableWarningDict, ph






