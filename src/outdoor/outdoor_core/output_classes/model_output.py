#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct  8 12:19:11 2021

@author: philippkenkel


Function list:
    - fill data
    - fill information
    - tidy data
    - save results /print results
    - save data
    - save file
    - return chosen
    - collect results
"""


import datetime
import os
import random as rnd
import math
import cloudpickle as pic
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.pyplot import legend
from tabulate import tabulate


class ModelOutput:

    """
    Class description
    ----------------

    This class is the main output class. It includes the case data such as
    used solver, calculation time, metadata etc.
    It also includes methods to
        - fill data into its own structure from the given pyomo model instance
        - Save data as .txt-file
        - Save the output as pickle file
        - Collect main results and display them in the console


    """

    def __init__(self, model_instance=None, optimization_mode = None, solver_name=None, run_time=None, gap = None):
        self._data = {}
        self._solver = None
        self._run_time = None
        self._case_time = None
        self._objective_function = None
        self._product_load = None
        self._optimality_gap = None
        self._case_numner = None
        self._meta_data = dict()

        self._optimization_mode_set = {
            "sensitivity",
            "cross-parameter sensitivity",
            "2-stage-recourse",
            "single",
            "wait and see",
            "here and now",
            "multi-objective"
        }

        if optimization_mode in self._optimization_mode_set:
            self._optimization_mode = optimization_mode
        else:
            raise Exception("Optimization mode: '{}' not supported".format(optimization_mode))



        if model_instance is not None:
            self._fill_data(model_instance)
        if solver_name is not None and run_time is not None:
            self._fill_information(solver_name, run_time, gap)

        # stochastic mode None unless otherwise specified
        self.stochastic_mode = None

        # LCA UNITS:

        self.LCA_units = {"terrestrial acidification potential (TAP)":"kg SO2-Eq",
                          "global warming potential (GWP100)":"kg CO2-Eq",
                          "freshwater ecotoxicity potential (FETP)":"kg 1,4-DCB-Eq",
                          "marine ecotoxicity potential (METP)":"kg 1,4-DCB-Eq",
                          "terrestrial ecotoxicity potential (TETP)":"kg 1,4-DCB-Eq",
                          "fossil fuel potential (FFP)":"kg oil-Eq",
                          "freshwater eutrophication potential (FEP)":"kg P-Eq",
                          "marine eutrophication potential (MEP)":"kg N-Eq",
                          "human toxicity potential (HTPc)":"kg 1,4-DCB-Eq",
                          "human toxicity potential (HTPnc)":"kg 1,4-DCB-Eq",
                          "ionising radiation potential (IRP)":"kBq Co-60-Eq",
                          "agricultural land occupation (LOP)":"m2*a crop-Eq",
                          "surplus ore potential (SOP)":"kg Cu-Eq",
                          "ozone depletion potential (ODPinfinite)":"kg CFC-11-Eq",
                          "particulate matter formation potential (PMFP)":"kg PM2.5-Eq",
                          "photochemical oxidant formation potential: humans (HOFP)":"kg NOx-Eq",
                          "photochemical oxidant formation potential: ecosystems (EOFP)":"kg NOx-Eq",
                          "water consumption potential (WCP)":"m3",
                          "acidification: terrestrial":"species.yr",
                          "climate change: freshwater ecosystems":"species.yr",
                          "climate change: terrestrial ecosystems":"species.yr",
                          "ecotoxicity: freshwater":"species.yr",
                          "ecotoxicity: marine":"species.yr",
                          "ecotoxicity: terrestrial":"species.yr",
                          "eutrophication: freshwater":"species.yr",
                          "eutrophication: marine":"species.yr",
                          "land use":"species.yr",
                          "photochemical oxidant formation: terrestrial ecosystems":"species.yr",
                          "water use: aquatic ecosystems":"species.yr",
                          "water use: terrestrial ecosystems":"species.yr",
                          "climate change: human health":"DALYs",
                          "human toxicity: carcinogenic":"DALYs",
                          "human toxicity: non-carcinogenic":"DALYs",
                          "ionising radiation":"DALYs",
                          "ozone depletion":"DALYs",
                          "particulate matter formation":"DALYs",
                          "photochemical oxidant formation: human health":"DALYs",
                          "water use: human health":"DALYs",
                          "energy resources: non-renewable, fossil":"USD 2013",
                          "material resources: metals/minerals":"USD 2013",
                          "ecosystem quality":"species.yr",
                          "human health":"DALYs",
                          "natural resources":"USD 2013",
}

# -----------------------------------------------------------------------------
# -------------------------Private methods ------------------------------------
# -----------------------------------------------------------------------------

    def _fill_data(self, instance):
        """

        Parameters
        ----------
        instance : SupstructureModel Class objective that is already solved


        Description
        -------
        Goes through all block of the Model object and extracts the data
        (Parameter, Variables, Sets, Objectives) to a Python dictionary
        that is called ProcessDesign._data

        """

        for i in instance.component_objects():
            if "pyomo.core.base.var.SimpleVar" in str(type(i)):
                self._data[i.local_name] = i.value
            elif "pyomo.core.base.var.ScalarVar" in str(type(i)):
                self._data[i.local_name] = i.value
            elif "pyomo.core.base.param.SimpleParam" in str(type(i)):
                self._data[i.local_name] = i.value
            elif "pyomo.core.base.param.ScalarParam" in str(type(i)):
                self._data[i.local_name] = i.value
            elif "pyomo.core.base.param.IndexedParam" in str(type(i)):
                self._data[i.local_name] = i.extract_values()
            elif "pyomo.core.base.var.IndexedVar" in str(type(i)):
                self._data[i.local_name] = i.extract_values()
            elif "pyomo.core.base.set.SetProduct_OrderedSet" in str(type(i)):
                self._data[i.local_name] = i.ordered_data()
            elif "pyomo.core.base.sets.SimpleSet" in str(type(i)):
                self._data[i.local_name] = i.value_list
            elif "pyomo.core.base.sets.ScalarSet" in str(type(i)):
                self._data[i.local_name] = i.value_list
            elif "pyomo.core.base.set.OrderedScalarSet" in str(type(i)):
                self._data[i.local_name] = i.ordered_data()
            elif "pyomo.core.base.objective.SimpleObjective" in str(type(i)):
                self._data["Objective Function"] = i.expr.to_string()
            elif "pyomo.core.base.objective.ScalarObjective" in str(type(i)):
                self._data["Objective Function"] = i.expr.to_string()
            else:
                continue

        return self._data

    def _fill_information(self, solver_name, run_time, gap):
        """
        Parameters
        ----------
        solver_name : String
        run_time : Float

        Description
        -------
        Fills important case data of the ProcessDesign Object:
            Solver name, Run time, Case time, Solved Objective function,
            Yearly Product load

        """
        self._solver = solver_name
        self._run_time = run_time
        self._case_time = datetime.datetime.now()
        self._case_time = str(self._case_time)
        self._objective_function = self._data["ObjectiveFunctionName"]
        self._product_load = self._data["MainProductFlow"]
        self._optimality_gap = gap
        self._case_number = self._case_time[0:10] + '--Nr ' + str(rnd.randint(1,10000))


        self._meta_data['Solver name'] = solver_name
        self._meta_data['Run time'] = run_time
        self._meta_data['Optimality gap'] = gap
        self._meta_data['Objective function'] = self._data['ObjectiveFunctionName']
        self._meta_data['Case identifier'] = str(self._case_number)


    def _tidy_data(self, data=None):
        """
        Description
        -----------
        Runs through data file and clears all zero values which are not important
        to save memory space.

        :param data: Dictionary, optional, default is None

        :return: Dictionary, if data is given, otherwise saves the data directly

        """
        if data is None:
            data = self._data

        temp = dict()
        exeptions = ["Y", "Y_DIST", "lin_CAPEX_z", "Y_HEX"]
        for i, j in data.items():
            if "index" not in i:
                if type(j) == dict:
                    temp[i] = dict()
                    for k, m in j.items():
                        if i not in exeptions:
                            if m != 0:
                                temp[i][k] = m
                        else:
                            temp[i][k] = m
                else:
                    temp[i] = j

        # return temp if data is given, otherwise for a single run save it directly in the object
        if data is None:
            self._data = temp
        else:
            return temp

    # Extracting methods to get important results

    def _collect_basic_results(self):
        """
        Description
        ----------
        Calls all collector methods to fill ProcessResults.results dictionary
        with all important results

        Returns
        -------
        TYPE: results dictionary
        """

        model_results = dict()

        basic_results = dict()

        basic_results["Basic results"] = {}
        basic_results["units"] = {}

        basic_results["Basic results"]["Objective Function"] = self._objective_function
        basic_results["units"]["Objective Function"] = 'aa'

        basic_results["Basic results"]["Yearly product load"] = self._data['sourceOrProductLoad']

        basic_results["Basic results"]["Solver run time"] = '{} seconds'.format(round(self._run_time,2))

        basic_results["Basic results"]["Solver name"] = self._solver

        if self._data['sourceOrProductLoad'] == 1:
            basic_results["Basic results"]["Earnings Before Tax income"] = "{} Mil. Euro".format(
                round(self._data["EBIT"], 3))
        else:
            basic_results["Basic results"]["Earnings Before Tax income"] = "{} €/ton".format(
                round(self._data["EBIT"], 3))

        if self._data['sourceOrProductLoad'] >= 1:
            basic_results["Basic results"]["Net production costs"] = "{} euro/ton".format(round(self._data["NPC"], 2))
        else:
            basic_results["Basic results"]["Net production costs"] = "{} euro/ton".format(round(self._data["NPC"]/ self._data['SumOfProductFlows'], 2))

        if self._data['sourceOrProductLoad'] >= 1:
            basic_results["Basic results"]["Net production GHG emissions"] = "{} CO2-eq/ton".format(round(self._data["NPE"], 2))
        else:
            basic_results["Basic results"]["Net production GHG emissions"] = "{} CO2-eq/ton".format(round(self._data["NPE"] / self._data['SumOfProductFlows'], 2))

        if self._data['sourceOrProductLoad'] >= 1:
            basic_results["Basic results"]["Net present FWD"] = "{} H2O-eq/ton".format(round(self._data["NPFWD"], 2))
        else:
            basic_results["Basic results"]["Net production FWD"] = "{} H2O-eq/ton".format(round(self._data["NPFWD"]/ self._data['SumOfProductFlows'], 2))

        # electricity demand and production
        basic_results["Basic results"]["-------"] = ""
        basic_results["Basic results"]["Electricity Demand"] = "{} MW".format(round(self._data["TOTAL_ELECTRICITY_DEMAND"], 2))
        basic_results["Basic results"]["Electricity Purchased"] = "{} MW".format(round(self._data["ENERGY_DEMAND_TOT"]['Electricity']/self._data['H'], 2))
        basic_results["Basic results"]["Electricity Produced"] = "{} MW".format(round(self._data["ELECTRICITY_PRODUCED"], 2))

        # heat demand and production
        basic_results["Basic results"]["------"] = ""
        basic_results["Basic results"]["Total Heat Demand"] = "{} MW".format(round(self._data["TOTAL_HEAT_DEMAND"], 2))
        basic_results["Basic results"]["Total Cooling Demand"] = "{} MW".format(round(self._data["TOTAL_COOLING_DEMAND"], 2))

        basic_results["Basic results"]["Heat Produced"] = "{} MW".format(round(self._data["TOTAL_HEAT_PRODUCED"], 2))
        basic_results["Basic results"]["Heat Sold"] = "{} MW".format(round(self._data["ENERGY_DEMAND_HEAT_PROD_SELL"], 2))
        basic_results["Basic results"]["Heat Exchanged"] = "{} MW".format(round(self._data["EXCHANGE_TOT"], 2))
        basic_results["Basic results"]["Heat Deficit"] = "{} MW".format(round(self._data["ENERGY_DEMAND_DEFICIT"], 2))
        basic_results["Basic results"]["Heat Residual"] = "{} MW".format(round(self._data["ENERGY_DEMAND_RESIDUAL"], 2))


        model_results.update(basic_results)

        chosen_technologies = {"Chosen technologies": self.return_chosen()}
        model_results.update(chosen_technologies)

        return model_results

    def collect_capital_cost_shares(self):
        """
        Decription
        ----------
        Collects data from the ProcessResults._data dictionary.
        Data that is collected are the shares (in %) of different unit-operations
        in the total annual capital investment. Data is returned as dictionary

        Returns
        -------
        capitalcost_shares : Dictionary

        """
        model_data = self._data

        capitalcost_shares = {"Capital costs shares": {}}

        total_costs = model_data["CAPEX"]
        capitalcost_shares["Capital costs shares"]["Total capital costs"] = str(round(total_costs, 3)) + ' Mil. Euro'
        capitalcost_shares["Capital costs shares"][""] = ""

        capitalcost_shares["Capital costs shares"]["Heat pump"] = round(
            model_data.get("ACC_HP", 0) / (total_costs + 1e-9)  * 100, 2
        )

        for i, j in model_data["ACC"].items():
            if j >= 1e-3:
                index_name = model_data["Names"][i]
                capitalcost_shares["Capital costs shares"][index_name] = round(
                    (j + model_data.get("TO_CAPEX", 0).get(i, 0)) / total_costs * 100, 2
                )

        heat_exchange_cost = sum(model_data['HENCOST'][hi] for hi in model_data['HI'])/1000
        if heat_exchange_cost > 0:
            capitalcost_shares["Capital costs shares"]['Heat Exchangers'] = (
                round(heat_exchange_cost / total_costs * 100, 2))

        return capitalcost_shares

    def _collect_LCA_results(self):
        """
        Collects data from the self._data dictionary. Everything related to LCA of UTILITY (heat electricity and cooling)
        :return:
        """

        model_data = self._data
        lca_results_utilities = {"LCA Results": {}}
        impact_cat = model_data['IMPACT_CATEGORIES']

        for i in impact_cat:
            value = round(model_data['IMPACT_TOT'][i], 3) # impact are per ton of product or input material
            try:
                unit = self.LCA_units[i] + '/kg' # all impacts are per kg of product /1000
            except:
                unit = 'NO unit found'

            lca_results_utilities["LCA Results"][i] = str(value) + ' ' + unit
        return lca_results_utilities

    def heat_balance_analysis(self):
        model_data = self._data

        heatBalanceDict = {}
        coolingBalanceDict ={}

        n = len(model_data['HI'])
        for hi in model_data['HI']:
            Q_cool_Heat = sum(model_data['ENERGY_DEMAND_HEAT'][u,hi] for u in model_data['U'])
            Q_heat_produced_used = model_data['ENERGY_DEMAND_HEAT_PROD_USE']
            Q_residual = model_data['ENERGY_DEMAND_HEAT_RESI'][hi]
            Q_exchange = model_data['ENERGY_EXCHANGE'][hi]

            heatBalanceDict[hi] = {'COOLING demand': round(Q_cool_Heat,4),
                                   'Heat produced and used': Q_heat_produced_used,
                                   'Heat residual': Q_residual,
                                   'heat exchanged': Q_exchange,}
            if hi == n:
                heatBalanceDict[hi].update({'required cooling': model_data['ENERGY_DEMAND_COOLING']})

            if hi == 1:
                heatBalanceDict[hi].update({'required cooling': model_data['ENERGY_DEMAND_HEAT_PROD_USE']})

            if hi > 1:
                Q_residual_hi_1 = model_data['ENERGY_DEMAND_HEAT_RESI'][hi-1]
                heatBalanceDict[hi].update({'Residual hi -1': Q_residual_hi_1})

            # i know should be revered but philip switch them and now it's a horrid feature
            Q_Demand_heating = sum(model_data['ENERGY_DEMAND_COOL'][u,hi] for u in model_data['U'])
            Q_deficit = model_data['ENERGY_DEMAND_HEAT_DEFI'][hi]
            coolingBalanceDict[hi] = {'HEATING demand': Q_Demand_heating,
                                      'Deficit': Q_deficit,
                                      'Exchaned': Q_exchange}

        for interval, dictHeat in heatBalanceDict.items():
            if sum(dictHeat.values()) != 0:
                print('Heat interval:', interval)
                print(dictHeat)
                # self._print_results(dictHeat)
                print('')

        for interval, dictCooling in coolingBalanceDict.items():
            if sum(dictCooling.values()) != 0:
                print('interval',interval)
                print(dictCooling)


    def get_detailed_LCA_results(self):

        model_data = self._data
        # make a dataFrame with colums: Utility, Materials and Waste
        # rows: all impact categories
        # values: the impact values

        lca_results = dict()
        lca_results['Utilities'] = dict()
        lca_results['Materials'] = dict()
        lca_results['Waste'] = dict()

        # impacts in kg_CO2_eq / kg of product or input material
        for impCat in model_data['IMPACT_INPUTS_PER_CAT']:
            lca_results['Materials'][impCat] = round( model_data['IMPACT_INPUTS_PER_CAT'][impCat], 3)

        for impCat in model_data['IMPACT_UTILITIES_PER_CAT']:
            lca_results['Utilities'][impCat] = round(model_data['IMPACT_UTILITIES_PER_CAT'][impCat], 3)
            for ut in model_data['UT']:
                utName = "Utilities_" + ut
                try:
                    lca_results[utName][impCat] = round(model_data["IMPACT_UTILITIES"][ut, impCat],3)
                except:
                    lca_results[utName] = dict()
                    lca_results[utName][impCat] = round(model_data["IMPACT_UTILITIES"][ut, impCat], 3)

        for impCat in model_data['IMPACT_WASTE_PER_CAT']:
            lca_results['Waste'][impCat] = round(model_data['IMPACT_WASTE_PER_CAT'][impCat], 3)

        # create a DF
        df_lca = pd.DataFrame(lca_results)

        # Show all rows
        pd.set_option('display.max_rows', None)

        # Show all columns
        pd.set_option('display.max_columns', None)

        # Optionally, ensure the display width is wide enough
        pd.set_option('display.width', None)

        return df_lca, lca_results

    def get_detailed_LCA_results_per_unit(self, impCat, exclude_units=None, data=None):

        if data is None:
            if self._data:
                model_data = self._data
            else:
                # we are dealing with a multi output
                # take the first solution from the list
                print("You have given a multioutput model and have not specified the outputdata in the inputs\n"
                      " selecting the first result in the output files ")
                key = list(self._results_data.keys())[0]
                model_data = self._results_data[key]

        else:
            model_data = data

        # make a dataFrame with colums: Utility, Materials and Waste
        # rows: all impact categories
        # values: the impact values

        if not exclude_units:
            exclude_units = []

        # check if imp.cat in lis t
        if impCat not in model_data['IMPACT_INPUTS_PER_CAT']:
            raise Exception('Impact category not found in the model chose one of the following:\n '
                            '{}'.format(model_data['IMPACT_INPUTS_PER_CAT'].keys()))
        lca_results = dict()


        # get the flow sheet with selected units
        units = self.return_chosen(data= model_data, threshold=1e-5)

        counterHeat = 0
        counterElec = 0
        counterWaste = 0
        counterRM = 0
        lenUnits = len(units) - len(exclude_units)

        heatDeficitDict = self._find_unit_to_exchange_heat(model_data)

        for u, name in units.items():
            if (u not in model_data['U_PP'] and u not in model_data['U_S']
                and u not in model_data['U_DIST'] and name not in exclude_units): # not a product, source or distribution units
                rawMaterialImpact = model_data['IMPACT_INPUTS_U_CAT'][u, impCat]/model_data['sourceOrProductLoad']/1000
                wasteDisposalImpact = model_data['WASTE_U'][u, impCat]/model_data['sourceOrProductLoad']/1000
                electricity, heat = self.utility_impact(u, impCat, heatDeficitDict, data)
                lca_results[name] = {'Raw material': rawMaterialImpact,
                                     'Waste disposal': wasteDisposalImpact,
                                     'Electricity': electricity/model_data['sourceOrProductLoad']/1000,
                                     'Heat': heat/model_data['sourceOrProductLoad']/1000}

                counterHeat += heat/model_data['sourceOrProductLoad']/1000
                counterElec += electricity/model_data['sourceOrProductLoad']/1000
                counterWaste += wasteDisposalImpact
                counterRM += rawMaterialImpact

        cumulativeImpact = counterRM + counterWaste + counterElec + counterHeat
        modelImpact = model_data['IMPACT_TOT'][impCat]

        if round(cumulativeImpact, 3) != round(modelImpact, 3):
            print("")
            print('The impact category is:', impCat)
            print('cumulative impacts calculation:', cumulativeImpact)
            print('model impact:', modelImpact)

        # get the total heat and electricity impact calculated by the model
        modelCalculatedElec = model_data['IMPACT_UTILITIES']['Electricity', impCat]/model_data['sourceOrProductLoad']/1000
        modelCalculatedHeat = (model_data['IMPACT_UTILITIES']['Heat', impCat] + model_data['IMPACT_UTILITIES']['Heat2', impCat])//model_data['sourceOrProductLoad']/1000

        modelCalculatedWaste = model_data['IMPACT_WASTE_PER_CAT'][impCat]
        modelCalculatedRawMaterial = model_data['IMPACT_INPUTS_PER_CAT'][impCat]

        if round(modelCalculatedHeat, 3) != round(counterHeat, 3):
            print('')
            print("Heat", impCat)
            print('The Model heat contribution: {} '
                  '\n post calculated heat contribution: {}'.format(modelCalculatedHeat, counterHeat))

        if round(modelCalculatedElec,3) != round(counterElec,3):
            print('')
            print('Electricity', impCat)
            print('The Model Electricity contribution: {} '
                  '\n post calculated Electricity contribution: {}'.format(modelCalculatedElec, counterElec))

        if round(modelCalculatedWaste, 3) != round(counterWaste, 3):
            print('')
            print('WASTE:', impCat)
            print('The Model Waste contribution: {} '
                  '\n post calculated Electricity contribution: {}'.format(modelCalculatedWaste, counterWaste))

        if round(modelCalculatedRawMaterial, 3) != round(counterRM, 3):
            print('')
            print('Raw material:', impCat)
            print('The Model Waste contribution: {} '
                  '\n post calculated Electricity contribution: {}'.format(modelCalculatedRawMaterial, counterRM))


        for unit, impactDict in lca_results.items():
            sumImpactU = sum(impactDict.values())
            percent = sumImpactU/modelImpact* 100
            print('Unit:{} conributes {} %'.format(unit, percent))
            print('')


        return lca_results

    def _find_unit_to_exchange_heat(self, model_data):

        heatExchangeTot = model_data['EXCHANGE_TOT']

        # Build a dictionary: unit → heat demand
        demandDict = {
            u: model_data['ENERGY_DEMAND_HEAT_UNIT'][u]
            for u in model_data['UU']
        }

        # Sort units by heat demand, from large to small
        # Produces a list of tuples: [(unit, demand), ...]
        sortedDemands = sorted(demandDict.items(), key=lambda x: x[1], reverse=True)

        remainingHeat = heatExchangeTot
        deficitHeatDict = {}

        for u, demand in sortedDemands:

            if remainingHeat > 0:
                # Allocate heat but not more than the unit demands
                allocated = min(demand, remainingHeat)
                remainingHeat -= allocated
            else:
                allocated = 0.0

            # deficit = what the unit still needs
            deficitHeatDict[u] = demand - allocated

        return deficitHeatDict


    def utility_impact(self, u, impCat, heatDeficitDict, data=None):
        """
        Description: Returns the utility impact of a unit depending on if it is a generator or a normal Unit

        :param u:
        :param impCat:
        :param data:
        :return:
        """
        if data is None:
            model_data = self._data
        else:
            model_data = data

        if u in model_data['U_FUR'] or u in model_data['U_TUR']:

            electricity = ((model_data['ENERGY_DEMAND'][u,'Electricity'] * model_data['flh'][u]
                           - model_data['EL_PROD_1'][u] * model_data['flh'][u]) *
                           model_data['util_impact_factors']['Electricity', impCat])

            # does not take into acount that exchange can happen due to produced heat! Only takes into account the demand...
            # so assume heat is sent to all units equally, not really true but closes the balance at least

            #heat1 = ((model_data['ENERGY_DEMAND_HEAT_UNIT'][u] * model_data['flh'][u] -
            #        model_data['ENERGY_DEMAND_HEAT_PROD'][u] * model_data['flh'][u])
            #        * model_data['util_impact_factors']['Heat', impCat])

            heat1 = heatDeficitDict[u] * model_data['flh'][u] * model_data['util_impact_factors']['Heat', impCat]

            #cool = ((model_data['ENERGY_DEMAND_COOL_UNIT'][u] * model_data['flh'][u] -
            #       model_data['ENERGY_DEMAND_HEAT_PROD'][u] * model_data['flh'][u])
            #       * model_data['util_impact_factors']['Heat', impCat])
            cool = 0

            heat = heat1 + cool

        else:
            electricity = ((model_data['ENERGY_DEMAND'][u,'Electricity'] + model_data['ENERGY_DEMAND'][u,'Chilling'] ) * model_data['flh'][u] *
                            model_data['util_impact_factors']['Electricity', impCat])

            #heat1 = (model_data['ENERGY_DEMAND_HEAT_UNIT'][u] * model_data['flh'][u] *
            #         model_data['util_impact_factors']['Heat', impCat])

            heat1 = heatDeficitDict[u] * model_data['flh'][u]  * model_data['util_impact_factors']['Heat', impCat]

            # cool = (model_data['ENERGY_DEMAND_COOL_UNIT'][u] * model_data['flh'][u] *
            #          model_data['util_impact_factors']['Heat', impCat])
            cool = 0

            heat = heat1 + cool

        # utilityImpact = electricity + heat
        return electricity, heat

    def check_heat_consumption(self, data=None):

        if data is None:
            model_data = self._data
        else:
            model_data = data

        unitsSelected = self.return_chosen(data= model_data, threshold=1e-5)

        heatUnits = 0
        heatExchangeTot = model_data['EXCHANGE_TOT']
        exchangeAverage = heatExchangeTot/len(unitsSelected)

        for u in unitsSelected:
            if u in model_data['U_FUR'] or u in model_data['U_TUR']:

                heatUnits += (model_data['ENERGY_DEMAND_HEAT_UNIT'][u] - exchangeAverage) * model_data['flh'][u]
                   # - model_data['ENERGY_DEMAND_HEAT_PROD'][u] * model_data['flh'][u]))

            else:
                heatUnits += (model_data['ENERGY_DEMAND_HEAT_UNIT'][u] - exchangeAverage) * model_data['flh'][u]
                            # (model_data['ENERGY_DEMAND_HEAT_UNIT'][u])

        # modelHeat = model_data['ENERGY_DEMAND_TOT']['Electricity']
        modelHeat = (model_data['H'] *
                     (sum(model_data['ENERGY_DEMAND_HEAT_DEFI'][hi] for hi in model_data['HI'])
                      - model_data['ENERGY_DEMAND_HEAT_PROD_SELL']))

        GREEN_BOLD = "\033[1;36m"
        RESET = "\033[0m"

        # print("heqt sold: ", model_data['ENERGY_DEMAND_HEAT_PROD_SELL'])
        print(f"{GREEN_BOLD}Heat consumption model: {modelHeat}{RESET}")
        print(f"{GREEN_BOLD}Post Heat consumption: {heatUnits}{RESET}")
        print("")

    def check_electricity_consumption(self, data=None):
        if data is None:
            model_data = self._data
        else:
            model_data = data

        unitsSelected = self.return_chosen(data=model_data, threshold=1e-5)

        electricity = 0
        for u in unitsSelected:
            if u in model_data['U_FUR'] or u in model_data['U_TUR']:

                electricity += (model_data['ENERGY_DEMAND'][u, 'Electricity'] * model_data['flh'][u]
                                - model_data['EL_PROD_1'][u] * model_data['flh'][u])

            else:
                electricity += (
                        (model_data['ENERGY_DEMAND'][u, 'Electricity'] + model_data['ENERGY_DEMAND'][u, 'Chilling']) *
                        model_data['flh'][u])

        modelElectricity = model_data['ENERGY_DEMAND_TOT']['Electricity']

        GREEN_BOLD = "\033[1;32m"
        RESET = "\033[0m"

        print(f"{GREEN_BOLD}Electricity consumption model: {modelElectricity}{RESET}")
        print(f"{GREEN_BOLD}Post Electricity consumption: {electricity}{RESET}")

    def plot_impacts_per_unit(self, impact_category, path, bar_width=0.8,
                              sources=None,
                              exclude_units=None, data=None, saveName=None):
        """
        Given a dictionary of form:
            lca_results = {
                "unit1": {"Raw material": val1, "Waste disposal": val2, "Utility": val3},
                "unit2": {...},
                ...
            }
        Create a bar chart with each unit on the x-axis,
        and three side-by-side bars for Raw material, Waste disposal, and Utility.
        """
        # lca_results[name] = {'Raw material': rawMaterialImpact,
        #                      'Waste disposal': wasteDisposalImpact,
        #                      'Utility': utilityImpact}

        # Convert dictionary to DataFrame with units as rows, categories as columns
        #    unit1  Raw material     X
        #           Waste disposal   Y
        #           Utility          Z
        #    unit2  Raw material     ...

        if not exclude_units:
            exclude_units = []

        if not sources:
            sources = ['Heat', 'Electricity', 'Waste disposal', 'Raw material']

        lca_results = self.get_detailed_LCA_results_per_unit(impact_category, exclude_units, data)

        # Filter the dictionary
        for s in sources:
            if s not in lca_results[list(lca_results.keys())[0]]:
                raise ValueError(f"Source '{s}' not found in the LCA results. \n "
                                 f"choose between: {list(lca_results[list(lca_results.keys())[0]].keys())}")

        filtered_lca_dict = {outer_key: {key: value for key, value in inner_dict.items() if key in sources}
                         for outer_key, inner_dict in lca_results.items()}

        df = pd.DataFrame.from_dict(filtered_lca_dict, orient='index')

        # Create the bar plot, side by side
        ax = df.plot(
            kind='bar',
            figsize=(8, 5),
            stacked=True,
            edgecolor='black',
            # title=f"Impacts by Source for {impact_category}"
            legend=False,
            width=bar_width
        )

        # Adjust x-axis labels & add other niceties
        unit = self.LCA_units[impact_category]
        ax.set_ylabel(unit + '/kg')

        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        # Construct the save path
        if saveName:
            if 'png' not in saveName:
                savePath = f"{path}/{saveName}.png"
            else:
                savePath = f"{path}/{saveName}"
        else:
            savePath = f"{path}/LCA_impacts_per_unit.png"

        # Save with bbox_inches='tight' to ensure legend is fully in the image
        # plt.savefig(savePath)
        plt.savefig(savePath, bbox_inches='tight')
        #plt.show()

    def sub_plots_stacked_impacts_per_category(
        self,
        impact_categories,
        path,
        bar_width=0.8,
        sources=None,
        exclude_units=None,
        data=None,
        saveName=None,
        stack_mode_units=True,
        fontSizeLabs=14,
    ):
        """
        Plot stacked contributions for each impact category in its own subplot (2 columns).
        Each subplot shows a single stacked bar per category, where the segments are the contributions.
        A single legend is added to the first subplot only.

        :param impact_categories: A list of impact categories to include
        :param path: Directory in which to save the figure
        :param bar_width: Width of each bar in the chart
        :param sources: Which LCA sources to include (e.g. ["Heat","Electricity","Waste disposal","Raw material"])
        :param exclude_units: List of process units to exclude from LCA results
        :param data: Additional data passed to self.get_detailed_LCA_results_per_unit (if your method needs it)
        :param saveName: File name (png) for saved figure
        :param stack_mode_units: Whether to plot the sums of each unit or the sums of each source
        """

        # Fallbacks
        if not exclude_units:
            exclude_units = []
        if not sources:
            sources = ["Heat", "Electricity", "Waste disposal", "Raw material"]

        # --- Gather data ---
        cat_data = {}
        cat_data_units = {}

        self.check_electricity_consumption(data=data)
        self.check_heat_consumption(data=data)

        for category in impact_categories:
            # Grab the detailed results for this category
            lca_results = self.get_detailed_LCA_results_per_unit(
                category, exclude_units=exclude_units, data=data
            )

            process_units = lca_results.keys()

            # Initialize sums
            summed_sources = {s: 0.0 for s in sources}
            summed_units = {unit: 0.0 for unit in lca_results.keys()}

            # Accumulate across units
            for unit_name, source_dict in lca_results.items():
                summed_units[unit_name] += sum(source_dict.values())
                for s in sources:
                    summed_sources[s] += source_dict.get(s, 0.0)

            cat_data[category] = summed_sources
            cat_data_units[category] = summed_units

        # Convert to DataFrame with categories as index
        df = pd.DataFrame.from_dict(cat_data, orient="index", columns=sources)
        df_units = pd.DataFrame.from_dict(cat_data_units, orient="index")


        # Decide which DataFrame to use
        if stack_mode_units:
            df_norm = df_units
        else:
            df_norm = df

        # --- Set up subplots in 2 columns ---
        num_categories = len(df_norm)
        ncols = 2
        nrows = math.ceil(num_categories / ncols)

        fig, axes = plt.subplots(
            nrows=nrows,
            ncols=ncols,
            figsize=(12, 4 * nrows),  # Adjust width & height as needed
            sharex=False
        )
        # Flatten axes for easy indexing
        axes = axes.flatten()

        # --- Plot each category ---
        for i, (category, row_data) in enumerate(df_norm.iterrows()):
            ax = axes[i]
            # row_data is a Series -> Convert to single-row DataFrame for stacking
            single_row_df = row_data.to_frame().T  # columns = contribution segments
            # single_row_df.index = [category]

            # Plot a stacked bar (only one bar, with stacked segments for each column)
            single_row_df.plot(
                kind="bar",
                stacked=True,
                ax=ax,
                width=bar_width,
                edgecolor="black",
                legend=(i == 0)  # Show legend only on the first subplot
            )

            # ax.set_title(category)
            ylab = self.LCA_units[category] + '/kg'
            ax.set_ylabel(ylab, fontsize=fontSizeLabs)
            xlab = category.capitalize().split('(')[0]
            ax.set_xlabel(xlab, fontsize=fontSizeLabs)

            # Remove the x-axis tick label (since it's just one bar labeled "category" or "0")
            ax.set_xticks([])

            # If you prefer to remove gridlines:
            ax.grid(False)

        # Hide any unused subplots if the number of categories is odd
        if num_categories < len(axes):
            for j in range(num_categories, len(axes)):
                axes[j].set_visible(False)

        plt.tight_layout()

        # --- Save the figure ---
        if saveName:
            if not saveName.lower().endswith(".png"):
                savePath = f"{path}/{saveName}.png"
            else:
                savePath = f"{path}/{saveName}"
        else:
            savePath = f"{path}/Stacked_LCA_impacts_per_category.png"

        plt.savefig(savePath, bbox_inches='tight')


    def plot_stacked_impacts_per_category(
        self,
        impact_categories,
        path,
        bar_width=0.8,
        sources=None,
        exclude_units=None,
        data=None,
        saveName=None,
        stack_mode_units=True,
    ):
        """
        Plot stacked contributions (summed across all units) for each
        impact category in `impact_categories`. Each bar is normalized
        by the average across sources for that category.

        :param impact_categories: A list of impact categories to include
        :param path: Directory in which to save the figure
        :param barWidth: Width of each bar in the chart
        :param sources: Which LCA sources to include (e.g. ["Heat","Electricity","Waste disposal","Raw material"])
        :param exclude_units: List of process units to exclude from LCA results
        :param data: Additional data passed to self.get_detailed_LCA_results_per_unit (if your method needs it)
        :param saveName: File name (png) for saved figure
        """
        # Fallbacks
        if not exclude_units:
            exclude_units = []
        if not sources:
            sources = ["Heat", "Electricity", "Waste disposal", "Raw material"]

        # For each category, get a dict of {unit: {source: value, ...}}.
        # Sum over units so we get total contribution per source for that category.
        cat_data = {}
        cat_data_units = {}
        for category in impact_categories:
            # Grab the detailed results for the category
            lca_results = self.get_detailed_LCA_results_per_unit(
                category,
                exclude_units=exclude_units,
                data=data
            )
            process_units = lca_results.keys()

            # Initialize sums for each source
            summed_sources = {s: 0.0 for s in sources}
            summed_units = {unit: 0.0 for unit in lca_results.keys()}
            # Accumulate across all units
            for unit_name, source_dict in lca_results.items():
                summed_units[unit_name] += sum(source_dict.values())
                for s in sources:
                    summed_sources[s] += source_dict.get(s, 0.0)

            cat_data[category] = summed_sources
            cat_data_units[category] = summed_units

        # Convert to a DataFrame with impact categories as rows, sources as columns
        df = pd.DataFrame.from_dict(cat_data, orient="index", columns=sources)
        df_units = pd.DataFrame.from_dict(cat_data_units, orient="index", columns=process_units)

        # Normalize each category’s row by that row’s average
        if stack_mode_units:
            # # Get the global mean (of absolute values, if you need those)
            # global_mean = df_units.abs().values.mean()
            # # Divide the entire DataFrame by that single factor
            # df_norm = df_units / global_mean

            df_norm = df_units

            # row_averages = abs(df_units.mean(axis=1))
            # df_norm = df_units.div(row_averages, axis=0)
        else:
            # row_averages = abs(df.mean(axis=1))
            # df_norm = df.div(row_averages, axis=0)
            df_norm = df

        # Create stacked bar chart
        ax = df_norm.plot(
            kind="bar",
            stacked=True,
            figsize=(8, 5),
            edgecolor="black",
            width=bar_width
        )

        # Because it’s normalized, label accordingly (dimensionless)
        ax.set_ylabel("Normalized impact")

        # Improve layout
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        # Build path for saving
        if saveName:
            if not saveName.lower().endswith(".png"):
                savePath = f"{path}/{saveName}.png"
            else:
                savePath = f"{path}/{saveName}"
        else:
            savePath = f"{path}/Stacked_LCA_impacts_per_category.png"

        # Save and show
        plt.savefig(savePath, bbox_inches='tight')
        # plt.show()

    def get_impact_factors(self):
        model_data = self._data
        impactIndexes = ['waste_impact_fac', 'impact_inFlow_components', 'util_impact_factors']
        impactDict = {}
        for i in impactIndexes:
            df_impactFactors = pd.DataFrame.from_dict(model_data[i], orient='index')
            impactDict[i] = df_impactFactors

        return impactDict

    def find_negative_impacts(self):
        model_data = self._data
        impactFactorsMaterials = model_data['impact_inFlow_components']
        impactFactorsUtilities = model_data['util_impact_factors']
        impactFactorsWaste = model_data['waste_impact_fac']

        print('------ Negative impacts from materials are:')
        for i in impactFactorsMaterials:
            if impactFactorsMaterials[i] < 0:
                print(i, impactFactorsMaterials[i])
        print("")
        print('----- Negative impacts from Utilities are:')
        for i in impactFactorsUtilities:
            if impactFactorsUtilities[i] < 0:
                print(i, impactFactorsUtilities[i])
        print("")
        print('------ Negative impacts from waste are:')
        for i in impactFactorsWaste:
            if impactFactorsWaste[i] < 0:
                print(i, impactFactorsWaste[i])

    def _collect_economic_results(self):
        """
        Description
        -----------
        Collects data from the ProcessResults._data dictionary.
        Data that is collected are base economic values, and depict the shares
        of the total costs of:
            CAPEX (all unit-operations)
            Raw material purchase
            Electricity costs
            Chilling costs
            Heat integration costs (Heating, Cooling utilities as well as HEN)
            Operating and Maintenance
            Waste water treatment
            Profits from Byproducts

        Returns
        -------
        economic_results : Dictionary

        """

        model_data = self._data

        economic_results = {"Economic results": {}}

        total_costs = model_data["TAC"] / 1000 + 1e-9
        rn = 4 # rounding number
        profits = 0
        wwt = 0

        for i, j in model_data["PROFITS"].items():
            if j < 0:
                wwt += j * model_data["H"] / 1000
            else:
                profits += j * model_data["H"] / 1000

        # so sinks/pools which are negative are waste streams, but we've also got treatment that we now specify and
        # calculate for all the waste streams that are not passed on to other units

        if model_data['WASTE_COST_TOT'] > 0:
            wwt += model_data['WASTE_COST_TOT'] /1000 # in M€

        economic_results["Economic results"]["CAPEX share"] = str(
            round(model_data.get("CAPEX", 1e-6), rn)) + " Mil. Euro"

        economic_results["Economic results"]["Raw material consumption share"] = str(round(
            model_data.get("RM_COST_TOT", 0) / 1000, rn)) + " Mil. Euro"

        economic_results["Economic results"]["Operating and Maintanence share"] = str(round(
            model_data.get("M_COST_TOT", 0), rn)) + " Mil. Euro"

        economic_results["Economic results"]["Electricity share"] = str(
            round((model_data.get("ENERGY_COST", 0).get("Electricity", 0)
                   + model_data.get("ELCOST", 0)) / 1000, rn)) + " Mil. Euro"

        economic_results["Economic results"]["Chilling share"] = str(
            round(model_data.get("ENERGY_COST", 0).get("Chilling", 0) / 1000, rn)) + " Mil. Euro"

        economic_results["Economic results"]["Heat integration share"] = str(
            round(model_data.get("C_TOT", 0) / 1000, rn)) + " Mil. Euro"

        economic_results["Economic results"]["Waste treatment share"] = str(round(wwt, rn)) + " Mil. Euro"

        economic_results["Economic results"]["Profits share"] = str(round(profits, rn)) + " Mil. Euro"

        return economic_results

    def _collect_relative_economic_results(self):
        """
        Description
        -----------
        Collects data from the ProcessResults._data dictionary.
        Data that is collected are base economic values, and depict the shares
        of the total costs of:
            CAPEX (all unit-operations)
            Raw material purchase
            Electricity costs
            Chilling costs
            Heat integration costs (Heating, Cooling utilities as well as HEN)
            Operating and Maintenance
            Waste water treatment
            Profits from Byproducts

        Returns
        -------
        economic_results : Dictionary

        """

        model_data = self._data

        economic_results = {"Economic results": {}}

        total_costs = model_data["TAC"] / 1000 + 1e-9

        profits = 0
        wwt = 0

        for i, j in model_data["PROFITS"].items():
            if j < 0:
                wwt -= j * model_data["H"] / 1000
            else:
                profits -= j * model_data["H"] / 1000

        # so sinks/pools wich are negative are waste streams, but we've also got treatment that we now specify and
        # calculate for all the waste streams that are not passed on to other units

        if model_data['WASTE_COST_TOT'] > 0:
            wwt += model_data['WASTE_COST_TOT'] /1000 # in M€

        economic_results["Economic results"]["CAPEX share"] = round(
            model_data.get("CAPEX", 0) / total_costs * 100, 2
        )

        economic_results["Economic results"]["Raw material consumption share"] = round(
            model_data.get("RM_COST_TOT", 0) / 1000 / total_costs * 100, 2
        )

        economic_results["Economic results"]["Operating and Maintanence share"] = round(
            model_data.get("M_COST_TOT", 0) / total_costs * 100, 2
        )

        economic_results["Economic results"]["Electricity share"] = round(
            (
                model_data.get("ENERGY_COST", 0).get("Electricity", 0)
                + model_data.get("ELCOST", 0)
            )
            / 1000
            / total_costs
            * 100,
            2,
        )

        economic_results["Economic results"]["Chilling share"] = round(
            model_data.get("ENERGY_COST", 0).get("Chilling", 0)
            / 1000
            / total_costs
            * 100,
            2,
        )

        economic_results["Economic results"]["Heat integration share"] = round(
            model_data.get("C_TOT", 0) / 1000 / total_costs * 100, 2
        )

        economic_results["Economic results"]["Waste treatment share"] = round(
            wwt / total_costs * 100, 2
        )

        economic_results["Economic results"]["Profits share"] = round(
            profits / total_costs * 100, 2
        )

        return economic_results

    def _collect_electricity_shares(self):
        """
        Description
        -----------
        Collects data from the ProcessResults._data dictionary.
        Data that is collected are the shares (in %) of different unit-operations
        in the total electricity demand.

        Returns
        -------
        electricity_shares : Dictionary


        """
        model_data = self._data

        electricity_shares = {"Electricity demand shares": {}}

        total_el = model_data.get("ENERGY_DEMAND_HP_EL", 0) * model_data["H"]

        for i, j in model_data["ENERGY_DEMAND"].items():
            if i[1] == "Electricity" and j >= 1e-05:
                total_el += j * model_data.get("flh", 0).get(i[0], 0)

        electricity_shares["Electricity demand shares"]['Total electricity demand'] = str(round(total_el, 2)) + ' MWh'
        electricity_shares["Electricity demand shares"]['']= ''

        electricity_shares["Electricity demand shares"]["Heatpump electricity share"] \
            = str(round(model_data.get("ENERGY_DEMAND_HP_EL", 0) * model_data["H"] / (total_el + 1e-6) * 100, 2)) + ' %'

        for i, j in model_data["ENERGY_DEMAND"].items():
            if i[1] == "Electricity" and j >= 1e-05:
                index_name = model_data["Names"][i[0]]
                electricity_shares["Electricity demand shares"][index_name] = str(round(
                    j * model_data.get("flh", 0).get(i[0], 0) / (total_el + 1e-6) * 100, 2
                )) + ' %'

        return electricity_shares

    def _collect_heatintegration_results(self):
        """
        Description
        -----------

        Collects data from the ProcessResults._data dictionary.
        Data that is collected are basic heat integration data:
            Total heating / cooling demand (in MW)
            Total heat recovery (from unit-operations) (in MW)
            Total High pressure steam production, internal (in MW)
            Total internal usage of this HP steam (rest is sold to market)
            Total Heat supplied by High Temperature heat pump (in MW)
            Net heating and cooling demand (in MW)

        Returns
        -------
        heatintegration_results : Dictionary


        """
        model_data = self._data

        heatintegration_results = {"Heating and cooling": {}}

        total_heating = 0
        total_cooling = 0
        net_heating = 0
        steam = 0

        for i in model_data["ENERGY_DEMAND_HEAT_UNIT"].values():
            if i >= 1e-05:
                total_heating += i

        for i in model_data["ENERGY_DEMAND_COOL_UNIT"].values():
            if i >= 1e-05:
                total_cooling += i

        for i in model_data["ENERGY_DEMAND_HEAT_PROD"].values():
            if i >= 1e-05:
                steam += i

        for i in model_data["ENERGY_DEMAND_HEAT_DEFI"].values():
            if i >= 1e-05:
                net_heating += i

        heatintegration_results["Heating and cooling"]["Total heating demand"] = round(
            total_heating, 2
        )

        heatintegration_results["Heating and cooling"]["Total cooling demand"] = round(
            total_cooling, 2
        )

        heatintegration_results["Heating and cooling"]["Total heat recovery"] = round(
            model_data["EXCHANGE_TOT"], 2
        )

        heatintegration_results["Heating and cooling"]["HP Steam produced"] = round(
            steam, 2
        )

        heatintegration_results["Heating and cooling"][
            "Internally used HP Steam"
        ] = round(model_data.get("ENERGY_DEMAND_HEAT_PROD_USE", 0), 2)

        heatintegration_results["Heating and cooling"][
            "High temperature heat pump heat supply"
        ] = round(model_data.get("ENERGY_DEMAND_HP_USE", 0), 2)

        heatintegration_results["Heating and cooling"]["Net heating demand"] = round(
            net_heating, 2
        )

        coolingDemand = model_data.get("ENERGY_DEMAND_COOLING", 0)
        if not coolingDemand: # avoid NoneType error
            coolingDemand = 0
        heatintegration_results["Heating and cooling"]["Net cooling demand"] = round(coolingDemand, 2)

        return heatintegration_results

    def _collect_GHG_results(self):
        """
        Description
        -----------
        Collects data from the ProcessResults._data dictionary.
        Data that is collected are the annual GHG emissions from:
            Direct emissions in unit-operations (sum in t/y)
            Indirect emissions from Electricity and Chilling (sum in t/y)
            Indirect emissions from Heat (sum in t/y)
            Emissions from building the plant (t/y)
            Emissions from buying raw materials / Negative emissions
                from carbon capture (t/y)
            Avoided burden credits from byproduct selling (t/y)

        Returns
        -------
        GHG_results : Dictionary

        """
        model_data = self._data

        GHG_results = {"Green house gas emission shares": {}}

        ghg_d = 0
        ghg_b = 0
        ghg_ab = 0

        for i in model_data["GWP_U"].values():
            if i is not None and i >= 1e-05:
                ghg_d += i

        for i in model_data["GWP_UNITS"].values():
            if i is not None and i >= 1e-05:
                ghg_b += i

        for i in model_data["GWP_CREDITS"].values():
            if i is not None and i >= 1e-05:
                ghg_ab += i

        GHG_results["Green house gas emission shares"]["Direct emissions"] = round(
            ghg_d, 0
        )

        GHG_results["Green house gas emission shares"]["Electricity"] = round(
            model_data.get("GWP_UT", 0).get("Electricity", 0), 0
        )

        GHG_results["Green house gas emission shares"]["Heat"] = round(
            model_data.get("GWP_UT", 0).get("Heat", 0), 0
        )

        GHG_results["Green house gas emission shares"]["Chilling"] = round(
            model_data.get("GWP_UT", 0).get("Chilling", 0), 0
        )

        GHG_results["Green house gas emission shares"][
            "Plant building emissions"
        ] = round(ghg_b, 0)

        GHG_results["Green house gas emission shares"][
            "Raw Materials / Carbon Capture"
        ] = round(-model_data["GWP_CAPTURE"], 0)

        GHG_results["Green house gas emission shares"][
            "Avoided burden for byproducts"
        ] = round(-ghg_ab, 0)

        return GHG_results

    def _collect_FWD_results(self):
        """
        Description
        -----------
        Collects data from the ProcessResults._data dictionary.
        Data that is collected are the annual fresh water demand from:
            Indirect demand from Electricity and Chilling (sum in t/y)
            Indirect demand from Heat (sum in t/y)
            Demand from buying raw materials
            Avoided burden credits from byproduct selling (t/y)

        Returns
        -------
        FWD_results: Dictionary
        """

        model_data = self._data

        FWD_results = {"Fresh water demand shares": {}}

        FWD_results["Fresh water demand shares"][
            "Indirect demand from raw materials"
        ] = round(-model_data.get("FWD_S", 0), 0)

        FWD_results["Fresh water demand shares"][
            "Utilities (Electricity and chilling)"
        ] = round(model_data.get("FWD_UT1", 0), 0)

        FWD_results["Fresh water demand shares"]["Utilities (Heating)"] = round(
            model_data.get("FWD_UT2", 0), 0
        )

        FWD_results["Fresh water demand shares"][
            "Avoided burden from byproducds"
        ] = round(-model_data.get("FWD_C", 0), 0)

        return FWD_results

    def _collect_energy_data(self):

        rn = 2  # rounding number
        model_data = self._data

        energy_data = {"Energy data": {}}

        # the keys of the units are UUID which are not very readable, so we convert them to names
        heat_demand = {model_data["Names"][k]: round(v * model_data.get("flh", 0).get(k, 8000), rn) for k, v in
                       model_data["ENERGY_DEMAND_HEAT_UNIT"].items() if v >= 1e-05}

        # the same for cooling demand
        cool_demand = {model_data["Names"][k]: round(v* model_data.get("flh", 0).get(k, 8000), rn) for k, v in
                       model_data["ENERGY_DEMAND_COOL_UNIT"].items() if v >= 1e-05}

        total_el = model_data.get("ENERGY_DEMAND_HP_EL", 0) * model_data["H"]

        for i, j in model_data["ENERGY_DEMAND"].items():
            if i[1] == "Electricity" and abs(j) >= 1e-05:
                total_el += round(j * model_data.get("flh", 0).get(i[0], 0), rn)

        energy_data["Energy data"]["heat (MWh)"] = heat_demand
        energy_data["Energy data"]["cooling (MWh)"] = cool_demand
        energy_data["Energy data"]["electricity (MWh)"] = total_el

        return energy_data

    def _collect_mass_flows(self):

        model_data = self._data
        mass_flow_data = {"Mass flows": {}}

        for i, j in model_data["FLOW_FT"].items():
            if j > 1e-04:
                namePair = [model_data["Names"].get(name, name) for name in i]
                nameTuple = tuple(namePair)
                mass_flow_data["Mass flows"][nameTuple] = str(round(j, 2)) + " t/h"

        for i, j in model_data["FLOW_ADD"].items():
            if j > 1e-04:
                namePair = [model_data["Names"].get(name, name) for name in i]
                nameTuple = tuple(namePair)
                mass_flow_data["Mass flows"][nameTuple] = str(round(j, 2)) + " t/h"

        return mass_flow_data

    def _collect_techno_economic_results(self):
        self.results = dict()

        model_data = self.model_output._data

        base_data = self.model_output._collect_results()

        self.results.update(base_data)
        chosen_technologies = {"Chosen technologies": self.model_output.return_chosen()}
        self.results.update(chosen_technologies)

        self.results.update(self._collect_economic_results(model_data))
        self.results.update(self.collect_capital_cost_shares(model_data))
        self.results.update(self._collect_electricity_shares(model_data))
        self.results.update(self._collect_heatintegration_results(model_data))
        self.results.update(self._collect_energy_data(model_data))

        return self.results

    def _collect_environmental_data(self):

        self.results = dict()
        model_data = self.model_output._data
        self.results.update(self._collect_GHG_results(model_data))
        self.results.update(self._collect_FWD_results(model_data))

        return self.results

    def _collect_results(self):
        """
        Description
        ----------
        Calls all collector methods to fill ProcessResults.results dictionary
        with all important results

        Returns
        -------
        TYPE: results dictionary


        """

        self.results = {}

        self.results.update(self._collect_basic_results())

        chosen_technologies = {'Chosen technologies': self.return_chosen()}
        self.results.update(chosen_technologies)

        self.results.update(self._collect_economic_results())
        self.results.update(self.collect_capital_cost_shares())
        self.results.update(self._collect_electricity_shares())
        self.results.update(self._collect_heatintegration_results())
        # self.results.update(self._collect_GHG_results())
        # self.results.update(self._collect_FWD_results())
        self.results.update(self._collect_energy_data())
        self.results.update(self._collect_mass_flows())
        self.results.update(self._collect_LCA_results())

    def _save_results(self, model_results, path, saveName=None):
        """
        Parameters
        ----------
        path : String type of where to save the results as .txt file

        Decription
        -------
        Collects all important results from the ProcessResults Class object and
        saves the data as tables in a text file.

        """
        all_results = model_results

        if not os.path.exists(path):
            os.makedirs(path)

        if saveName:
            path = path + "/" + saveName + ".txt"
        else:
            path = path + "/results" + self._case_number + ".txt"


        with open(path, encoding="utf-8", mode="w") as f:

            for i, j in all_results.items():
                table = tabulate(j.items())

                f.write("\n")
                f.write(i)
                f.write("-------- \n")
                f.write(table)
                f.write("\n")
                f.write("\n \n")

            print("")

    def _print_results(self, model_data):
        """
        Description
        -------
        Collects all important results data and prints them as tables to the
        console.

        """

        all_results = model_data

        for i, j in all_results.items():
            print("")
            print("")
            print(i)
            print("--------------")
            print(tabulate(j.items()))
            print("")

# -----------------------------------------------------------------------------
# -------------------------Public methods -------------------------------------
# -----------------------------------------------------------------------------

    def get_results(self, pprint=True, path=None, saveName=None):
        """

        Parameters
        ----------
        pprint : Boolean, optional, default is True
            DESCRIPTION: Defines if results should be printed to console
        save : String, optional
            DESCRIPTION: Defines path where results should be saved, if kept
            blank results are not saved as .txt-file.

        Description
        -----------
        Collects the most important model results
        by calling private function '_collect_results'.
        Afterwards optionally prints them and saves them.

        """
        self._collect_results()
        model_results = self.results

        if pprint is True:
            self._print_results(model_results)

        if path is not None:
            self._save_results(model_results, path, saveName=saveName)

    def save_data(self, path):
        """
        Parameters
        ----------
        path : String type of where to save the complete data as .txt file


        Decription
        -------
        Collects all data from the ProcessResults Class object and saves the
        data as tables in a text file.

        """

        if not os.path.exists(path):
            os.makedirs(path)

        path = path + "/" + "input_file " + self._case_number + "_data.txt"

        with open(path, encoding="utf-8", mode="w") as f:

            for i, j in self._data.items():
                f.write(f"{i}: {j} \n \n")

    def save_file(self, path, option="raw"):
        """
        Parameters
        ----------
        path : String type of where to save the ProcessResults object as pickle
            class object.
        option: String, default is 'raw' which saves all data also including zero
            values. If this value is set to 'tidy' an cleaning algorithm deletes
            zero values which saves data space.

        Description
        ----------
        Saves the output file as a pickle-file, which can be laoded into an
        Analyzer-Object on another machine or at a different time.

        """
        if option == "tidy":
            self._tidy_data()

        path = path + "/" + "data_file " + self._case_number + ".pkl"

        with open(path, "wb") as output:
            pic.dump(self, output)


    def return_chosen(self, data=None, threshold=1e-5):
        """
        Returns
        -------
        chosen : Dictionary

        Description
        -----------
        Checks in the data structure which unit-operations are chosen based on
        binary variables and minimal mass flows. Afterwards saves the results
        and returns a dictionary with the chosen index numbers and defined names.

        """

        if data is None:
            flow = self._data["FLOW_SUM"]
            flow_s = self._data["FLOW_SOURCE"]
            data = self._data
        else:
            flow = data["FLOW_SUM"]
            flow_s = data["FLOW_SOURCE"]

        # if the key of flow is a tuple then the solution id from the stochastic model
        # Extract the maximum value of the flows for each scenario
        if isinstance(list(flow.keys())[0], tuple):
            flow = self.find_max_value_of_scenarios(dict=flow, unitNr=data['U'])
            flow_s = self.find_max_value_of_scenarios(dict=flow_s, unitNr=data['U_S'])


        y = data["Y"]
        names = data["Names"]
        chosen = {}

        for i, j in y.items():
            if j == 1:
                try:
                    if flow[i] >= threshold:
                        chosen[i] = names[i]
                except:
                    pass

            else:
                try:
                    if flow_s[i] >= threshold:
                        chosen[i] = names[i]
                except:
                    pass

        return chosen

    def find_max_value_of_scenarios(self, dict, unitNr =None):
        """"
        if the data is encased in a tuple (unitNr, ScenarioNr) then this function splits the data into a dictionary that
        contains the maximum value of each unitNr across all scenarios
        """
        scenario_values = self._data['SC']

        if unitNr is  None:
            units = self._data['U']
        else:
            units = unitNr

        unitDict = {}
        for u in units:
            scList = []
            for s in scenario_values:
                scList.append(dict[u, s])
            unitDict[u] = max(scList)
        return unitDict

    def plot_capex_pie_chart(self, savePath=None, saveName=None):
        """
        :return: A pie chart of the capital costs of the chosen flow sheet
        """
        CT = self.collect_capital_cost_shares()
        capexShares = CT['Capital costs shares']

        # create the pie chart
        fig, ax = plt.subplots(figsize=(10, 10))
        colors = plt.cm.viridis_r(np.linspace(0, 1, len(capexShares)))  # Attractive color palette
        wedges, texts, autotexts = ax.pie(list(capexShares.values()),
                                          autopct='%1.1f%%', shadow=True, startangle=140,
                                          colors=colors, explode=[0.02] * len(capexShares))  # Explode effect

        # Legend with labels, adjusted position
        ax.legend(wedges, capexShares.keys(),
                  title="Unit processes",
                  loc="lower right",
                  bbox_to_anchor=(1.10, 0.88))  # Adjust this for legend position

        # Styling
        plt.setp(autotexts, size=10, weight="bold", color="white")
        ax.set_title('Capital Costs Distribution', fontsize=16, weight='bold')

        ax.axis('equal')  # Equal aspect ratio ensures the pie is circular.

        # save the pie chart
        if savePath:
            if saveName:
                saveLocation = f'{savePath}/{saveName}_Capex_pie_chart.png'
            else:
                saveLocation = f'{savePath}/Capex_pie_chart.png'
            plt.savefig(saveLocation, format='png', dpi=300)  # High-resolution saving for publication
        plt.show()

    def get_LCA_references(self):
        """
        Get's the chosen references to calculate the impact of a given activity
        and prints it to the consul
        """
        print("---- Method 'get_LCA_references' Still under construction  -----")

        return

    # ---------------------------- Pickle methods --------------------------------
    # methodes to save and load the object as pickle file

    def save_with_pickel(self, path, saveName=None, option="raw"):
        """
        Parameters
        ----------
        path : String type of where to save the ProcessResults object as pickle
            class object.

        saveName : String type of the name of the saved file, default is None

        option: String, default is 'raw' which saves all data also including zero
            values. If this value is set to 'tidy' an cleaning algorithm deletes
            zero values which saves data space.
            it can also be 'small' which saves only the most important data of the object, usefull for MultiModelOutput
            objects so Objects are not save in nested Objects (makes the file smaller)

        Description
        ----------
        Saves the output file as a pickle-file, which can be laoded into an
        Analyzer-Object on another machine or at a different time.
        """
        # check if the option is valid
        options = ['raw', 'tidy', 'small']
        if option not in options:
            raise ValueError('option must be either:', options)

        # if the attribute self.ph exists delete it
        if hasattr(self, 'ph'):
            del self.ph

        if not os.path.exists(path):
            os.makedirs(path)

        if option == "tidy":
            if hasattr(self, '_results_data'):
                for i in self._results_data.values():
                    i._tidy_data()

        elif option == "small":
            resultsSmall = {}
            for sc, obj in self._results_data.items():
                resultsSmall[sc] = obj._data
            # delete the _results_data attribute to save memory
            # del self._results_data
            self._results_data = resultsSmall

        else:
            pass


        if saveName:
            if 'pkl' in saveName:
                path = path + "/" + saveName
            else:
                path = path + "/" + saveName + ".pkl"

        else:
            saveName = "data_file_" + self._case_time[0:-10]
            path = path + "/" + saveName + ".pkl"

        with open(path, "wb") as output:
            pic.dump(self, output, protocol=4)

        # print location of saved file in purple
        print('\033[95m' + f"Data saved at: {path}")

    def save_chunks_with_pickel(self, path, nChunks, saveName, option="small"):
        """
        This methode is used to save the object in chunks. This is useful if the object is too large to be saved/loaded
        in one go .

        Parameters
        ----------
        path : String type of where to save the ProcessResults object as pickle
            class object.

        nChunks : int, number of chunks to save the object in

        saveName : String type of the name of the saved file, default is None

        option: String, default is 'raw' which saves all data also including zero
            values. If this value is set to 'tidy' an cleaning algorithm deletes
            zero values which saves data space.
            'small' saves only the most important data of the object, usefull for MultiModelOutput


        Description
        ----------
        Saves the output file as a pickle-file, which can be laoded into an
        Analyzer-Object on another machine or at a different time.
        """

        def divide_dict(dictionary, num, option='small'):
            """
            This function divides a dictionary into n sub-dictionaries
            :param dictionary:
            :param num:
            :param option:
            :return:
            """

            if option == "small":
                resultsSmall = {}
                for sc, obj in dictionary.items():
                    resultsSmall[sc] = obj._data
                dictionary = resultsSmall

            keys = list(dictionary.keys())
            subDicts = [{} for _ in range(num)]

            for i, key in enumerate(keys):
                subDicts[i % num][key] = dictionary[key]

            return subDicts

        # if the attribute self.ph exists, delete it
        if hasattr(self, 'ph'):
            del self.ph

        if not os.path.exists(path):
            os.makedirs(path)

        # add one chunk. chunk 0 is the file containting everything but the _data_Files
        solutionDataDict = self._results_data
        # divide the data into nChunks
        dividedDataDict = divide_dict(solutionDataDict, nChunks, option)

        # delete the _results_data attribute to save memory
        del self._results_data

        originalSaveName = saveName
        originalPath = path
        nChunks += 1 # because the first chunk is the main object without the _results_data attribute
        for chunk in range(nChunks):
            newSaveName = originalSaveName
            if 'pkl' in saveName:
                newSaveName = newSaveName.split('.pkl')[0]
                newSaveName = newSaveName + f'_chunk_{chunk}.pkl'
            else:
                newSaveName = newSaveName + f'_chunk_{chunk}.pkl'

            path = originalPath + "/" + newSaveName

            if chunk == 0:
                with open(path, "wb") as output:
                    pic.dump(self, output, protocol=4)
            else:
                with open(path, "wb") as output:
                    pic.dump(dividedDataDict[chunk-1], output, protocol=4) # -1 because the first chunk is the main object


        # print location of saved file in purple
        print('\033[95m' + f"Data saved at: {path}")

    @classmethod
    def load_from_pickle(cls, path):
        """
        Parameters
        ----------
        filepath : String type of the path to the pickle file to load

        Description
        ----------
        Loads the object from a pickle file and returns it.

        Returns
        -------
        MultiModelOutput instance
        """

        with open(path, "rb") as input_file:
            loaded_object = pic.load(input_file)

        return loaded_object

    @classmethod
    def load_chunks_from_pickle(cls, path, saveName, nChunks, saveAs = 'dict'):
        """
        Load the object from the pickle file. The object is saved in chunks. This method loads all the chunks and
        combines them into one object.

        Parameters
        ----------
        path : String type of the path to the pickle file to load
        saveName : String type of the name of the saved file, default is None
        nChunks : int, number of chunks to load
        saveAs : String, default is 'dict'. If 'dict' the results are saved as a dictionary, if 'object' the results are saved as an object
        so either {'sc_i': object} or {'sc_i': dict} where dict is the raw data output

        Description
        ----------
        Loads the object from a pickle file and returns it.

        Returns
        -------
        MultiModelOutput instance
        """

        # check if saveAs is a valid option
        if saveAs not in ['dict', 'object']:
            raise ValueError('saveAs must be either "dict" or "object"')

        if 'pkl' in saveName:
            originalSaveName = saveName.split('.pkl')[0]
        else:
            originalSaveName = saveName

        originalPath = path
        nChunks += 1  # because the first chunk is the main object without the _results_data attribute
        for i in range(nChunks):
            saveName = originalSaveName + f'_chunk_{i}.pkl'
            filePath = originalPath + "/" + saveName
            print('loading chunk:', i)
            with open(filePath, "rb") as input_file:
                loadedObject = pic.load(input_file)
                if i == 0:
                    combinedObject = loadedObject
                    resultsData = {}
                else:
                    if saveAs == 'dict':
                        for key, object in loadedObject.items():
                            resultsData[key] = object._data
                    else:
                        resultsData.update(loadedObject)
                    #print(resultsData)

        # sort the dictionary combinedObject._results_data based on the keys
        # resultsSorted = dict(sorted(resultsData.items()))
        # combinedObject._results_data = resultsSorted
        combinedObject._results_data = resultsData

        return combinedObject

    def update_from_loaded(self, loaded_object):
        """
        Parameters
        ----------
        loaded_object : MultiModelOutput instance

        Description
        ----------
        Updates the current instance with the attributes of the loaded object.
        """
        self.__dict__.update(loaded_object.__dict__)



