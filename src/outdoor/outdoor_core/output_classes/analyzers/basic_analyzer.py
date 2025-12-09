#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 26 15:12:24 2022

@author: philippkenkel
"""

import copy
import datetime
import itertools
import os
import sys
import time
import re
import cloudpickle as pic
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pydot
from tabulate import tabulate


class BasicModelAnalyzer:
    """
    Class description
    -----------------
    This class provides a set of methods to analyse the output of a superstructure
    optimization. It works as a basic analyser which can process the ModelOutput
    class, therefore is written for single-run optimization.

    Model data can be loaded by the load_model_ouput() method.

    It includes a series of private methods which collect data on costs,
    environmental burdens as well as mass and energy balances.

    It also includes public methods to present the results e.g. techno-economics
    as bar graphs or the resulting flow sheets based on mass balances.

    """
    def __init__(self, model_output=None, deepcopy=True):
        # todo: DO I need a deepcopy here?
        if deepcopy:
            self.model_output = copy.deepcopy(model_output)
        elif deepcopy is False:
            self.model_output = model_output
        else:
            raise ValueError("deepcopy must be either True or False")

# -----------------------------------------------------------------------------
# -------------------------Private methods ------------------------------------
# -----------------------------------------------------------------------------

    def _collect_capitalcost_shares(self, model_data):
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
        capitalcost_shares = {"Capital costs shares": {}}

        total_costs = model_data["CAPEX"]

        capitalcost_shares["Capital costs shares"]["Heat pump"] = round(
            model_data.get("ACC_HP", 0) / total_costs * 100, 2
        )

        for i, j in model_data["ACC"].items():
            if j >= 1e-3:
                index_name = model_data["Names"][i]
                capitalcost_shares["Capital costs shares"][index_name] = round(
                    (j + model_data.get("TO_CAPEX", 0).get(i, 0)) / total_costs * 100, 2
                )

        return capitalcost_shares

    def _collect_economic_results(self, model_data):
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
        economic_results = {"Economic results": {}}

        total_costs = model_data["TAC"] / 1000

        profits = 0
        wwt = 0

        for i, j in model_data["PROFITS"].items():
            if j < 0:
                wwt -= j * model_data["H"] / 1000
            else:
                profits -= j * model_data["H"] / 1000

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

        economic_results["Economic results"]["Heat supply/integration share"] = round(
            model_data.get("C_TOT", 0) / 1000 / total_costs * 100, 2
        )

        economic_results["Economic results"]["Waste treatment share"] = round(
            wwt / total_costs * 100, 2
        )

        economic_results["Economic results"]["Profits share"] = round(
            profits / total_costs * 100, 2
        )

        return economic_results

    def _collect_electricity_shares(self, model_data):
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
        electricity_shares = {"Electricity demand shares": {}}

        total_el = model_data.get("ENERGY_DEMAND_HP_EL", 0) * model_data["H"]

        for i, j in model_data["ENERGY_DEMAND"].items():
            if i[1] == "Electricity" and j >= 1e-05:
                total_el += j * model_data.get("flh", 0).get(i[0], 0)

        electricity_shares["Electricity demand shares"][
            "Heatpump electricity share"
        ] = round(
            model_data.get("ENERGY_DEMAND_HP_EL", 0) * model_data["H"] / total_el * 100,
            2,
        )

        for i, j in model_data["ENERGY_DEMAND"].items():
            if i[1] == "Electricity" and j >= 1e-05:
                index_name = model_data["Names"][i[0]]
                electricity_shares["Electricity demand shares"][index_name] = round(
                    j * model_data.get("flh", 0).get(i[0], 0) / total_el * 100, 2
                )

        return electricity_shares

    def _collect_heatintegration_results(self, model_data):
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

        heatintegration_results["Heating and cooling"]["Net cooling demand"] = round(
            model_data.get("ENERGY_DEMAND_COOLING", 0), 2
        )

        return heatintegration_results

    def _collect_GHG_results(self, model_data):
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

    def _collect_FWD_results(self, model_data):
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

    def _collect_energy_data(self, model_data):
        energy_data = {"Energy data": {}}

        heat_demand = model_data["ENERGY_DEMAND_HEAT_UNIT"]
        cool_demand = model_data["ENERGY_DEMAND_COOL_UNIT"]

        total_el = model_data.get("ENERGY_DEMAND_HP_EL", 0) * model_data["H"]

        for i, j in model_data["ENERGY_DEMAND"].items():
            if i[1] == "Electricity" and abs(j) >= 1e-05:
                total_el += j * model_data.get("flh", 0).get(i[0], 0)

        energy_data["Energy data"]["heat"] = heat_demand
        energy_data["Energy data"]["cooling"] = cool_demand
        energy_data["Energy data"]["electricity"] = total_el

        return energy_data

    def _collect_mass_flows(self, model_data, nDecimals=2):
        """
        :param model_data:  dictionary with all the data from the optimization
        :return: mass_flow_data: dictionary with the exiting mass flows of the unit operations
        """

        mass_flow_data = {"Mass flows": {}}
        # for stochastic flows the data is structured differently, there are 2 different formats, from the Extensive form
        # and from the Progressive Hedging algorithm with mpi-sppy, you can differentiate between them by checking if the key 'SC' is in the dictionary

        if list(model_data.keys())[0] == 'sc1':
            scenarioKeys = list(model_data.keys())
            for key in model_data['sc1']["FLOW_FT"].keys():
                scFT = []
                for sc in scenarioKeys:
                    flow = model_data[sc]["FLOW_FT"][key]
                    scFT.append(flow)
                if max(scFT) > 1e-04:
                    mass_flow_data["Mass flows"].update({key+('sc' + '{}'.format(i+1),): round(value, nDecimals) for i, value in enumerate(scFT)})

            for key in model_data['sc1']["FLOW_ADD"].keys():
                scAdd = []
                for sc in scenarioKeys:
                    flow = model_data[sc]["FLOW_ADD"][key]
                    scAdd.append(flow)
                if max(scAdd) > 1e-04:
                    mass_flow_data["Mass flows"].update({key+('sc' + '{}'.format(i+1),): round(value, nDecimals) for i, value in enumerate(scAdd)})


        elif 'SC' in model_data.keys():
            step = len(model_data['SC'])
            pointerStart = 0
            pointerEnd = step
            for _ in range(0, len(model_data["FLOW_FT"]), step):
                selectionDict = itertools.islice(model_data["FLOW_FT"].items(), pointerStart, pointerEnd)
                # the parameters per scenario are grouped together in the data structure,
                # hence the pointer is moved up to get the appropriate data
                pointerStart += step
                pointerEnd += step
                selectionList = list(selectionDict)
                meaxOfScenario = max(selectionList, key=lambda x: x[1])  # the second element of the tuple is the value we want to compare

                if meaxOfScenario[1] > 1e-04: # that is, at least one stream is flowing in a particular unit in a particular scenario
                    for i, j in selectionList:
                        mass_flow_data["Mass flows"][i] = round(j, nDecimals)

            pointerStart = 0
            pointerEnd = step
            for _ in range(0, len(model_data["FLOW_ADD"]), step):
                selectionDict = itertools.islice(model_data["FLOW_ADD"].items(), pointerStart, pointerEnd)
                # the parameters per scenario are grouped together in the data structure,
                # hence the pointer is moved up to get the appropriate data
                pointerStart += step
                pointerEnd += step
                selectionList = list(selectionDict)
                meaxOfScenario = max(selectionList, key=lambda x: x[1])  # the second element of the tuple is the value we want to compare

                if meaxOfScenario[1] > 1e-04:  # that is, at least one stream is flowing in a particular unit scenario through that unit operation
                    for i, j in selectionList:
                        mass_flow_data["Mass flows"][i] = round(j, nDecimals)

        else: # for single run optimization
            for i, j in model_data["FLOW_FT"].items():
                if j > 1e-05:
                    mass_flow_data["Mass flows"][i] = round(j, nDecimals)

            for i, j in model_data["FLOW_ADD"].items():
                if j > 1e-05:
                    mass_flow_data["Mass flows"][i] = round(j, nDecimals)

        return mass_flow_data

    def _collect_mass_flows_stochastic(self, model_data, nDecimals=2):
        mass_flow_data = {"Mass flows": {}}

        for i, j in model_data["FLOW_FT"].items():
            if j > 1e-06:
                mass_flow_data["Mass flows"][i] = round(j, nDecimals)

        for i, j in model_data["FLOW_ADD"].items():
            if j > 1e-06:
                mass_flow_data["Mass flows"][i] = round(j, nDecimals)

        return mass_flow_data

    def _collect_techno_economic_results(self):
        self.results = dict()

        model_data = self.model_output._data

        base_data = self.model_output._collect_results()

        self.results.update(base_data)
        chosen_technologies = {"Chosen technologies": self.model_output.return_chosen()}
        self.results.update(chosen_technologies)

        self.results.update(self._collect_economic_results(model_data))
        self.results.update(self._collect_capitalcost_shares(model_data))
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
        self.results.update(self._collect_capitalcost_shares())
        self.results.update(self._collect_electricity_shares())
        self.results.update(self._collect_heatintegration_results())
        self.results.update(self._collect_GHG_results())
        self.results.update(self._collect_FWD_results())
        self.results.update(self._collect_energy_data())
        self.results.update(self._collect_mass_flows())

    def _print_results(self, data=None):
        """
        Description
        -------
        Collects all important results data and prints them as tables to the
        console.

        """

        all_results = data

        for i, j in all_results.items():
            print("")
            print("")
            print(i)
            print("--------------")
            print(tabulate(j.items()))
            print("")

    def _save_results(self, data, path, suffix=None):
        """

        Parameters
        ----------
        path : String type of where to save the results as .txt file

        Decription
        -------
        Collects all important results from the ProcessResults Class object and
        saves the data as tables in a text file.

        """
        all_results = data

        if not os.path.exists(path):
            os.makedirs(path)

        if suffix is None:
            suffix = "optimisation_results_"

        path = path + "/" + suffix + self.model_output._case_number + ".txt"

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

    # -----------------------------------------------------------------------------
    # -------------------------Public methods -------------------------------------
    # -----------------------------------------------------------------------------

    def set_model_output(self, model_output):
        """
        Parameters
        ----------
        model_output : ModelOutput class which stores the data of the optimization.

        """
        self.model_output = copy.deepcopy(model_output)

    def load_model_output(self, path):
        """
        Parameters
        ----------
        path : String
            Path string from where to load pickle file

        """

        timer = time.time()

        with open(path, "rb") as file:
            self.model_output = pic.load(file)

        timer = time.time() - timer
        print(f"File loading time was {timer} seconds")

    def techno_economic_analysis(self, pprint=True, savePath=None):
        """

        Parameters
        ----------
        pprint : Boolean, optional, default is True
            DESCRIPTION: Defines if results should be printed to console
        save : String, optional default is None
            DESCRIPTION: The path where the techno-economic results should be saved.

        Description
        -------
        Calls the private _collect_techno_economic_results() method and
        prints / saves the results based on input.

        """

        data = self._collect_techno_economic_results()

        if pprint is True:
            self._print_results(data)

        if savePath is not None:
            suffix = "/techno_economic_results"
            self._save_results(data=data, path=savePath, suffix=suffix)

    def environmental_analysis(self, pprint=True, save=None):
        """
        Parameters
        ----------
        pprint : Boolean, optional, default is True
            DESCRIPTION: Defines if results should be printed to console
        save : String, optional default is None
            DESCRIPTION: The path where the environmental results should be saved.

        Description
        -------
        Calls the private _collect_environmental_data() method and
        prints / saves the results based on input.

        """
        data = self._collect_environmental_data()

        if pprint is True:
            self._print_results(data)

        if save is not None:
            suffix = "/environmental_results"
            self._save_results(data=data, path=save, suffix=suffix)

    def LCA_analysis_plot(self, impactCategory, saveName, log_scale=False):
        """
        Description
        -----------
        Calls the LCA analysis method from the ModelOutput class
        and plots the results on a bar chart so you can see the effects
        of a chosen impact category. Bars are placed side by side in viridis colors.

        Parameters
        ----------
        impactCategory : str
            Name of the impact category to analyze.
        saveName : str
            File name (without extension) to which the plot is saved.
        log_scale : bool, optional
            If True, y-axis is in log scale. If False (default), uses a linear scale.
        """

        # 1) Collect data
        _, resultsDict = self.model_output.get_detailed_LCA_results()
        keysImpacts = list(resultsDict.keys())
        resultsImpactCategory = {
            key: resultsDict[key][impactCategory] for key in keysImpacts
        }

        # 2) Convert to a Pandas Series, then to DataFrame
        series = pd.Series(
            data=resultsImpactCategory,
            index=resultsImpactCategory.keys(),
            name="Values"
        )
        df = pd.DataFrame(series)  # shape: (nKeys, 1)
        df_t = df.T  # shape: (1, nKeys)

        # 3) Plot side-by-side bars
        fig, ax = plt.subplots(figsize=(6, 4), dpi=160)

        # Use the viridis colormap
        my_colors = plt.cm.viridis(np.linspace(0.0, 1.0, df_t.shape[1]))

        df_t.plot(
            kind="bar",
            stacked=False,  # side by side bars
            rot=0,  # no rotation on x-axis labels (only one row)
            color=my_colors,
            edgecolor="k",
            legend=False,
            ax=ax,
            title=f"{impactCategory}"
        )

        # 4) Final touches
        # Switch to log scale if requested
        if log_scale:
            ax.set_yscale("symlog")
            #ax.set_yscale("log")

        ax.set_xlabel("")
        ax.set_ylabel("Value")
        plt.tight_layout()

        # 5) Save the plot
        plt.savefig(saveName + ".png", dpi=160, bbox_inches="tight")
        plt.show()

    def create_plot_bar(self, user_input, save=False, Path=None, gui=False):
        """

        Parameters
        ----------
        user_input : String based on defined set. Permitted values are:
                'Economic results', 'Capital cost shares', 'Fresh water demand shares',
                'Green house gas emission shares', 'heating and cooling' and
                'Electricity demand shares'
        save : Boolean, optional default is False
            DESCRIPTION: Decides if bar-plot should be saved
        Path : String, optional default is None
            DESCRIPTION: Defines the path were the graph should be saved
        gui : Boolean, optional default is False
            DESCRIPTION: TO BE DETERMINED / UNDER CONSTRUCTION

        Returns
        -------
        fig : TYPE
            DESCRIPTION.

        Description
        -----------

        Based on the input the method collects the required data and prepares
        a bar-plot graph which presents the different shares of the present
        unit-operation on the chosen parameter.

        """

        INPUT_SET = {
            "Economic results",
            "Capital costs shares",
            "Fresh water demand shares",
            "Green house gas emission shares",
            "Heating and cooling",
            "Electricity demand shares",
        }

        if user_input not in INPUT_SET:
            print('The user input is not correct, please only select from:')
            print(INPUT_SET)
            sys.exit()


        fig = plt.figure()
        ax1 = fig.add_subplot()
        dict1 = self._collect_techno_economic_results()
        model_data = self.model_output._data
        dict1.update(self._collect_GHG_results(model_data))
        dict1.update(self._collect_FWD_results(model_data))

        data = dict1[user_input]

        labels = list()
        values = list()

        for i, j in data.items():
            labels.append(i)
            values.append(j)

        value_sum = round(sum(values))

        series = pd.Series(data=data, index=data.keys(), name=" ")

        plot_labels = {
            "Breakdown": None,
            "titel": user_input,
            "total": " ",
        }

        if value_sum == 100:
            plot_labels["Breakdown"] = "Breakdown (%)"

            if user_input == "Economic results":
                NPC = round(model_data["NPC"])
                plot_labels["total"] = f"NPC are {NPC} €/ ton"

        else:
            if user_input == "Heating and cooling":
                plot_labels["Breakdown"] = "Amounts in MW"

            else:
                plot_labels["Breakdown"] = "Breakdown"

        if plot_labels["total"]:
            total = plot_labels["total"]
        else:
            total = None

        titel = plot_labels["titel"]

        plt.rcParams["figure.dpi"] = 160

        my_colors = plt.cm.Greys(np.linspace(0.0, 0.7, len(values)))

        axes = pd.DataFrame(series).T.plot(
            kind="bar",
            stacked=True,
            rot="horizontal",
            figsize=(3, 4),
            title=f" {titel}, {total}",
            edgecolor="k",
            color=my_colors,
            legend=None,
            ax=ax1,
        )

        ax1.tick_params(
            axis="x", which="both", bottom=False, top=False, labelbottom=False
        )

        axes.spines["top"].set_visible(False)

        colLabels = [plot_labels["Breakdown"] for i in range(len(values))]
        array = np.array(values, dtype=float).reshape((len(values), 1))

        ax1.table(
            cellText=array,
            rowLabels=labels,
            rowColours=my_colors,
            colLabels=colLabels,
            cellLoc="center",
            loc="bottom",
        )

        # Save input file if save statement = True
        if save is True:
            date_time_now = datetime.datetime.now().strftime("%Y_%m_%d__%H-%M-%S")

            if Path is None:
                my_path = os.path.abspath(__file__)
                plt.savefig(
                    "/{}_Chart_{}.pdf".format(date_time_now, user_input),
                    dpi=160,
                    bbox_inches="tight",
                )
                print("Saved in {}".format(my_path))

            if Path is not None:
                assert os.path.exists(
                    Path
                ), "This file path does not seem to exist: " + str(Path)
                plt.savefig(
                    Path.rstrip(".py")
                    + "/{}_Chart_{}.pdf".format(date_time_now, user_input),
                    dpi=160,
                    bbox_inches="tight",
                )
                print("Saved in {}".format(Path))

        # Create temp-file for presentation in GUI
        if gui is True:
            plt.savefig("temp/new.png", dpi=160, bbox_inches="tight")

        return fig

    def create_flowsheet(self, path, saveName=None, dataScenario=None, multiObjectiveData=None):

        """
        Parameters
        ----------
        path : String
            DESCRIPTION: Defines where the flowsheet image should be saved

        Description
        -------
        This method prepares the flowsheet image of the optimized superstructre.

        """
        def make_node(graph, name, shape, orientation=0 , color = 'black'):
            """
            Parameters
            ----------
            graph : Dot class
            name : String

            shape : String (Options check documentation of graphviz module)

            Returns
            -------
            node : Pydot Node object

            """

            node = pydot.Node(name, height=0.5, width=2, fixedsize=True, shape=shape, orientation=-orientation,
                              color=color)

            graph.add_node(node)

            return node

        def make_link(graph, a_node, b_node, label=None, width=1, style="solid" , color= 'black'):
            """

            Parameters
            ----------
            graph : Dot object
            a_node : pydot node object (starting point)
            b_node : pydot node object (ending point)
            label : Label (can be string but also float etc. )
            width :
                DESCRIPTION. The default is 1.
            style : TYPE, optional
                DESCRIPTION. The default is 'solid'. For options check
                            documentation of graphviz module

            Returns
            -------
            edge : pydot Edge object

            """
            edge = pydot.Edge(a_node, b_node)
            edge.set_penwidth(width)
            edge.set_style(style)
            edge.set_color(color)

            if label is not None:
                edge.set_label(label)

            graph.add_edge(edge)

            return edge

        data = dict()
        nodes = dict()
        edges = dict()

        if dataScenario:
            # if we want to plot a specific scenario (e.g. for the wait and see approach or multi-objective
            # optimization)
            model_data = dataScenario

        elif multiObjectiveData:
            model_data = multiObjectiveData
            # todo, skechy fix, we need to update the model data to the multi-objective data elsewere in the code
            self.model_output._data = model_data # we need to update the model data to the multi-objective data

        else: # otherwise we plot the nominal scenario for the single-objective optimization or mpi-sppy optimization
            # otherwise we plot the nominal scenario for the single-objective optimization
            model_data = self.model_output._data

        data = self._collect_mass_flows(model_data=model_data, nDecimals=4)["Mass flows"]
        flowchart = pydot.Dot(
            "flowchart", rankdir="LR", ratio="compress", size="15!,1", dpi="500"
        )

        if self.model_output.stochastic_mode == "mpi-sppy" or multiObjectiveData:
            model_data = model_data['sc1']

        for i, j in data.items():

            for v in i[0:2]: # i[0:2] is the tuple of the unit-operation, we don't need the scenario label

                if v not in nodes.keys():

                    if isinstance(list(model_data["Names"].keys())[0], str):

                        # stupid fix for the case where the names are strings
                        # (when loading from json the keys of model_data["Names"] are strings for some reason)
                        # transform the keys to integers to be able to compare them with the unit numbers
                        try:
                            model_data["Names"] = {int(k): v for k, v in model_data["Names"].items()}
                        except:
                            model_data["Names"] = {k: v for k, v in model_data["Names"].items()} # if the keys are already integers or are UIDs

                    if v in model_data["U_S"]:
                        nodes[v] = make_node(
                            flowchart, model_data["Names"][v], shape="ellipse", color='green'
                        )

                    elif v in model_data["U_STOICH_REACTOR"]:

                        if v in model_data["U_TUR"]:
                            nodes[v] = make_node(
                                flowchart, model_data["Names"][v], "doubleoctagon"
                            )

                        elif v in model_data["U_FUR"]:
                            nodes[v] = make_node(
                                flowchart, model_data["Names"][v], "doubleoctagon"
                            )

                        else:
                            nodes[v] = make_node(
                                flowchart, model_data["Names"][v], "octagon"
                            )

                    elif v in model_data["U_YIELD_REACTOR"]:
                        nodes[v] = make_node(
                            flowchart, model_data["Names"][v], "octagon"
                        )

                    elif v in model_data["U_PP"]:
                        nodes[v] = make_node(flowchart, model_data["Names"][v], "house", orientation=270, color= 'blue')

                    elif v in model_data["U_DIST"]:
                        nodes[v] = make_node(
                            flowchart, model_data["Names"][v], shape="triangle", orientation=270
                        )

                    else:
                        nodes[v] = make_node(flowchart, model_data["Names"][v], "box")

        # if we're dealing with a Stochastic model, we need to create a new dictionary where the labels are the min,
        # mean and max values. For this we to transform the stream data to get the right labels
        if len(list(data.keys())[0]) > 2: # if the first key is a tuple > 2, we're dealing with a stochastic model
            dataStochastic = self.min_mean_max_streams_stochastic(data)
            for i, j in dataStochastic.items():
                # tester = j #for debugging
                edges[i[0], i[1]] = make_link(flowchart, nodes[i[0]], nodes[i[1]], f"{j[0]}", color=j[1], width=j[2])
        else:
            for i, j in data.items():
                if j < 1e-6:
                    flow = round(j * 1e9, 2)
                    labelEdge = f"{flow} mg/h"
                elif j < 1e-3:
                    flow = round(j * 1e6, 2)
                    labelEdge = f"{flow} g/h"
                elif j < 0.1:
                    flow = round(j * 1e3, 2)
                    labelEdge = f"{flow} kg/h"
                else:
                    labelEdge = f"{round(j, 2)} t/h"

                edges[i[0], i[1]] = make_link(flowchart, nodes[i[0]], nodes[i[1]], labelEdge)


        if not os.path.exists(path):
            os.makedirs(path)

        if saveName is None:
            path = path + '/flowchart' + '-' + self.model_output._case_number + '.png'
        else:
            path = path + '/' + saveName + '.png'

        flowchart.write_png(path)

    def min_mean_max_streams_stochastic(self, streamDataDict, nDecimals=5):
        """"
        The data is encased in a tuple (unitNr, unitNr, ScenarioNr) then this function splits the data into a dictionary that
        contains the minimum, mean and maximum value of each connected stream across all scenarios
        """
        def format_flow(value):
            """
            get the right label for the flows
            """
            if value < 1e-6:
                scaled_value = round(value * 1e9, 2)
                unit = " mg/h"
            elif value < 1e-3:
                scaled_value = round(value * 1e6, 2)
                unit = " g/h"
            elif value < 0.1:
                scaled_value = round(value * 1e3, 2)
                unit = " kg/h"
            else:
                scaled_value = round(value, 2)
                unit = " t/h"
            return scaled_value, unit

        # differentiation between the two different data structures (nrml stochastic vs mpi-sppy)
        if hasattr(self.model_output._data, 'SC'):
            scenario_values = self.model_output._data['SC']
            model_output = self.model_output._data
        else:
            scenario_values = list(self.model_output._data.keys())
            model_output = self.model_output._data[scenario_values[0]]

        #units = self.model_output._data['U']
        unitConnestors = model_output['U_CONNECTORS'] + model_output['U_SU']

        unitDict = {}
        colorCode = 'black'
        width = 1 # default width
        for unitNumbers in unitConnestors:
            scList = []
            u = unitNumbers[0]
            uu = unitNumbers[1]
            for s in scenario_values:
                if (u, uu, s) in streamDataDict.keys():
                    scList.append(streamDataDict[u, uu, s])

            if scList: # if the list is not empty continue
                maxValue = round(max(scList), nDecimals)
                minValue = round(min(scList),nDecimals)
                meanValue = round(sum(scList) / len(scList), nDecimals)
                # get the coloring of the edges right according to how much variation their is in the stream
                if maxValue > 0:  # color code the streams that actually have a flow
                    ratio = minValue / maxValue
                    if ratio < 0.125:
                        colorCode = 'red4'  # Very dark red
                        width = 3.5
                    elif ratio < 0.25:
                        colorCode = 'red'
                        width = 3
                    elif ratio < 0.375:
                        colorCode = 'red2'  # A slightly lighter red
                        width = 2.5
                    elif ratio < 0.50:
                        colorCode = 'orange'
                        width = 2
                    elif ratio < 0.625:
                        colorCode = 'darkorange'
                        width = 1.75
                    elif ratio < 0.75:
                        colorCode = 'gold'  # Instead of 'yellow' for better visibility
                        width = 1.5
                    elif ratio < 0.875:
                        colorCode = 'gold'  # A light yellow
                        width = 1.25
                    else:
                        colorCode = 'black'
                        width = 1

                # get the units right for the labels
                # Example usage
                minimumFlow, minUnit = format_flow(minValue)
                meanFlow, meanUnit = format_flow(meanValue)
                maximumFlow, maxUnit = format_flow(maxValue)

                label = (f"min: {minimumFlow}{minUnit}\n"
                         f"mean: {meanFlow}{meanUnit}\n"
                         f"max: {maximumFlow}{maxUnit}")


                # if minValue < 1e-6:
                #     minimumFlow = round(minValue * 1e9, 2)
                #     maximumFlow = round(maxValue * 1e9, 2)
                #     meanFlow = round(meanValue * 1e9, 2)
                #     labelUnit = " mg/h"
                # elif minValue < 1e-3:
                #     minimumFlow = round(minValue * 1e6, 2)
                #     maximumFlow = round(maxValue * 1e6, 2)
                #     meanFlow = round(meanValue * 1e6, 2)
                #     labelUnit = " g/h"
                # elif minValue < 0.1:
                #     minimumFlow = round(minValue * 1e3, 2)
                #     maximumFlow = round(maxValue * 1e3, 2)
                #     meanFlow = round(meanValue * 1e3, 2)
                #     labelUnit = " kg/h"
                # else:
                #     minimumFlow = round(minValue, 2)
                #     maximumFlow = round(maxValue, 2)
                #     meanFlow = round(meanValue, 2)
                #     labelUnit = " t/h"
                #label = f"min: {minimumFlow}{labelUnit}\nmean: {meanFlow}{labelUnit}\nmax: {maximumFlow}{labelUnit}"

                unitDict.update({(u,uu): (label, colorCode, width)})

        return unitDict

    def export_results_to_excel(self, savePath=None, saveName=None):
        """
        Description
        -----------
        Exports the results of the optimization to an excel file
        """

        # get the list of chosen unit operations
        chosenUnits = self.model_output.return_chosen()
        dfDict = {}
        # get the data of each selected unit
        for u in chosenUnits:
            dfUnit = pd.DataFrame(index=[
                self.model_output._data['Names'][u]])  # create a new dataframe for each unit with unit name as index

            if u in self.model_output._data['U_C']:  # if the unit is not an input or output
                # get the CAPEX of the unit
                capexUnit = self.model_output._data['EC'][u]
                dfUnit['CAPEX (M€/y)'] = round(capexUnit, 3)  # M€
                # get Operating and Maintenance
                oAndM = self.model_output._data['K_OM'][u] * self.model_output._data['FCI'][u]
                dfUnit['O&M (M€/y)'] = round(oAndM, 3)  # M€
                # get the raw material flow and cost
                for key, flow in self.model_output._data['FLOW_ADD'].items():
                    if key[1] == u:
                        addedFlow = flow
                        inputName = self.model_output._data['Names'][key[0]]
                        costAddedMaterial = self.model_output._data['materialcosts'][key[0]] * addedFlow

                        dfUnit[inputName + ' (t/h)'] = round(addedFlow, 3)
                        dfUnit[inputName + ' cost (€/y)'] = round(costAddedMaterial, 3)

                # electricity consumption + cost
                electricityDemand = self.model_output._data['ENERGY_DEMAND'][(u, 'Electricity')] * \
                                    self.model_output._data['flh'][u]  # kWh
                costElectricity = electricityDemand * self.model_output._data['delta_ut']['Electricity']  # €
                dfUnit['Electricity Demand (MWh/y)'] = round(electricityDemand, 3)
                dfUnit['Electricity cost (k€/y)'] = round(costElectricity/1000, 3)

                heatDemand = self.model_output._data['ENERGY_DEMAND_HEAT_UNIT'][u]
                dfUnit['Heat (MWh/y)'] = round(heatDemand, 3)
                # dfUnit['Heat cost (€)'] = round(costHeat, 3)

                # the waste costs
                wasteCost = self.model_output._data['WASTE_COST_U'][u]
                dfUnit['Waste cost (k€/y)'] = round(wasteCost, 3)

                # store the dataframe in the dictionary
                dfDict[u] = dfUnit

        # combine all dataframes into a single dataframe
        final_df = pd.concat(dfDict.values())
        # print(final_df)
        # save the dataframe to an excel file

        if savePath is None:
            savePath = os.getcwd()
        if saveName is None:
            saveName = 'excel_output.xlsx'
        if '.xlsx' not in saveName:
            saveName += '.xlsx'

        final_df.to_excel(savePath + '/' + saveName)

    def create_bar_plot_opex(self, path, saveName=None, barColor=None, barwidth=None, modelData=None):
        """
        Creates a bar plot of the operational costs of the entire system
        :param path:
        :param saveName:
        :return:
        """

        # set up optionals if not provided
        if modelData is None:
            model_data = self.model_output._data
        else:
            model_data = modelData

        if barColor is None:
            barColor = 'green'
        if barwidth is None:
            barwidth = 0.3

        # get the operational costs from the model data
        #self.OPEX
        #== self.M_COST_TOT  # operating and maintenance costs
        #+ self.RM_COST_TOT / 1000  # raw material costs
        #+ sum(self.ENERGY_COST[ut] for ut in self.U_UT) / 1000  # utility costs energy
        #+ self.C_TOT / 1000  # selling or buying of energy (from HEN)
        #+ self.ELCOST / 1000  # electricity costs for heat pump
        #+ self.WASTE_COST_TOT / 1000  # waste costs


        rawMaterialCost = model_data['RM_COST_TOT']
        utilityCost = sum(model_data['ENERGY_COST'][ut] for ut in model_data['U_UT'])
        wasteCosts = model_data['WASTE_COST_TOT'] # WASTE_COST_TOT

        # make a bar plot of the operational costs
        labels = ['Raw material costs', 'Utility costs', 'Waste costs']
        costs = [rawMaterialCost, utilityCost, wasteCosts]
        #costs = [round(c/1000, 3) for c in costs]
        plt.bar(labels, costs, color=barColor, width=barwidth)
        plt.ylabel('Costs (k€/y)')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        #plt.title('Operational costs')

        if saveName is None:
            path = path + '/opex_plot' + '.png'
        else:
            path = path + '/' + saveName + '.png'

        # plt.savefig(path)
        plt.savefig(path, bbox_inches='tight')
        #plt.show()

    def sanitize_save_name(self, saveName: str, index: int) -> str:
        """
        Remove a trailing number from saveName (if present) and append a new index.
        """
        match = re.match(r"(.*?)(\d+)$", saveName)
        if match:
            base = match.group(1)
        else:
            base = saveName
        return f"{base}{index}"
