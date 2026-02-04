# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 11:25:35 2020


@author: Celina geändert am 01.09.2020:
    Templates werden nicht eingelesen genauso wie "Tabelle1" sondern nur die neu hinzugefügten Tabellen
"""

import copy
import warnings

import pandas as pd

from .wrapp_parameters_optimisation_mode import wrapp_stochastic_data, wrapp_sensitivity_data, wrapp_multi_objective_data
from .wrapp_processes import wrapp_processUnits, wrapp_productPoolUnits, wrapp_sourceUnits, wrapp_distributors
from .wrapp_system import wrapp_SystemData
from ..outdoor_core.utils.progress_bar import print_progress_bar  # , print_progress_bar
from ..outdoor_core.utils.timer import time_printer


# function for Pandafunction to read an excelfile:

def get_DataFromExcel(path=None,
                      optimization_mode=None,
                      cross_sensitivity_params=None,
                      stochastic_mode=None,
                      scenario_size=None,
                      seed=66,
                      scenarioDataFiles=None,):

    """
    Description
    -----------
    - Function to read all spreadsheets of an exceldata
    - put data from excel in Super Structure
    - One spreadsheet = one process
    - Hidden spreadsheets with the name:
      Tabelle1, Template_CC, Template_Stö, etc. will be skipped

    Context
    ----------
    -wrapp.ProcessUnits: to fill the Super Structure for all processes
    -wrapp.SystemData: to fill the Super Structure with the system datas
    -add_Units: add Process(Object) to Objectlist

    Parameters
    ----------
    PathName : String, Path to Exceldata
    optimization_mode : String, optional, overrides the optimisation mode defined in the Excel file
    cross_sensitivity_params : Dict, optional, overrides the cross sensitivity parameters defined in the Excel file
    stochastic_mode : String, optional, switch to use mpi-sspy for stochastic optimization
    seed : int, optional, seed for the random number generator default is 66
    scenario_size : int, optional, number of scenarios for the stochastic optimization
    dataFilesScenarios : Dict, optional, Dict of data files for the scenarios in the stochastic optimization

    Returns
    -------
    Superstructure_Object

    """
    print('PATH NAME IS:::')
    print(path)

    timer = time_printer(programm_step='Extract data from excel')
    # Disable the specific warning about Data Validation extension to make code run faster
    warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
    dataframe = pd.read_excel(path, sheet_name = None)

    PU_ObjectList  =[]

    ## Hidden tables with specific names will be skipped:
    Hidden_Tables = []
    Hidden_Tables.append('Template_PhysicalProcess')
    Hidden_Tables.append('Template_StoichReactor')
    Hidden_Tables.append('Template_YieldReactor')
    Hidden_Tables.append('Template_SteamGenerator')
    Hidden_Tables.append('Template_ElGenerator')
    Hidden_Tables.append('Template_ProductPool')
    Hidden_Tables.append('DataBank')
    Hidden_Tables.append('Component Databases')
    Hidden_Tables.append('Uncertainty_test_idea')
    Hidden_Tables.append('Uncertainty_old')
    # Hidden_Tables.append('Sensitivity')

    number_of_processes = len(dataframe.keys()) - len(Hidden_Tables)
    count = 0

    # only add data for the stochastic optimization if the optimization mode is not specified in the function call,
    # the optimization mode is then specified in the Excel file that is passed on to the Superstructure_Object

    Superstructure_Object = wrapp_SystemData(dataframe['Systemblatt'],
                                             optimization_mode=optimization_mode)
    _optimization_mode = Superstructure_Object.optimization_mode



    for i in dataframe.keys():
        if i == 'Systemblatt':
            continue

        elif i == 'Uncertainty':
            continue

        elif i == 'Sensitivity':
            continue

        elif i == "Pools":
            pools = wrapp_productPoolUnits(dataframe[i])
            for k in pools:
                PU_ObjectList.append(k)

        elif i == "Sources":
            sources = wrapp_sourceUnits(dataframe[i])
            for k in sources:
                PU_ObjectList.append(k)

        elif i == 'Distributor':
            distributors = wrapp_distributors(dataframe[i])
            for k in distributors:
                PU_ObjectList.append(k)

        elif i in Hidden_Tables:
            continue # skip the hidden tables

        else: # for the unit operations
            PU_ObjectList.append(wrapp_processUnits(dataframe[i]))

        # data_extraction = count / number_of_processes * 100

        print_progress_bar(iteration= count, total= number_of_processes, prefix= 'Data Extraction' )
        count += 1

    print()  # to get a new line after the progress bar
    Superstructure_Object.add_UnitOperations(PU_ObjectList)
    timer = time_printer(timer, 'Extracting data from excel')



    if _optimization_mode == '2-stage-recourse':
        # save the data of the single optimization variable in the object for VSS and EVPI calculation
        Superstructure_Object_duplicate = copy.deepcopy(Superstructure_Object)
        Superstructure_Object.parameters_single_optimization = Superstructure_Object_duplicate

        # set the uncertainty data in the object
        df_stochastic = dataframe['Uncertainty']
        uncertaintyObject = wrapp_stochastic_data(df_stochastic, seed, scenario_size)

        # add an if statement to check what kind of uncertainty model we're dealing with
        if stochastic_mode is None:
            Superstructure_Object.set_uncertainty_data(uncertaintyObject=uncertaintyObject)
            Superstructure_Object.uncertaintyDict = uncertaintyObject.LableDict

        elif stochastic_mode == 'mpi-sppy':
            Superstructure_Object.set_uncertainty_data_mpisspy(uncertaintyObject=uncertaintyObject)
            Superstructure_Object.uncertaintyDict = uncertaintyObject.LableDict
            if scenarioDataFiles is not None:
                # overwrite the scenario data files with the ones from the wait and see analysis
                # if they are passed on to the function call
                # --------------------------
                Superstructure_Object.scenarioDataFiles = scenarioDataFiles

        else:
            raise ValueError('The stochastic mode {} is not recognized. '
                             '\n Please choose either None or "mpi-sppy".'.format(stochastic_mode))

    elif _optimization_mode == "wait and see":
        # save the data of the single optimization variable in the object for VSS and EVPI calculation
        Superstructure_Object_duplicate = copy.deepcopy(Superstructure_Object)
        Superstructure_Object.parameters_single_optimization = Superstructure_Object_duplicate

        # set the uncertainty data in the object
        df_stochastic = dataframe['Uncertainty']
        uncertaintyObject = wrapp_stochastic_data(df_stochastic, seed, scenario_size)

        # create the uncertainty data for the Superstructure_Object
        Superstructure_Object.set_uncertainty_data_mpisspy(uncertaintyObject=uncertaintyObject)
        Superstructure_Object.uncertaintyDict = uncertaintyObject.LableDict

    elif _optimization_mode == 'here and now':
        # save the data of the single optimization variable in the object for VSS and EVPI calculation
        Superstructure_Object_duplicate = copy.deepcopy(Superstructure_Object)
        Superstructure_Object.parameters_single_optimization = Superstructure_Object_duplicate

        # set the uncertainty data in the object
        df_stochastic = dataframe['Uncertainty']
        uncertaintyObject = wrapp_stochastic_data(df_stochastic, seed, scenario_size)

        Superstructure_Object.set_uncertainty_data_mpisspy(uncertaintyObject=uncertaintyObject)
        Superstructure_Object.uncertaintyDict = uncertaintyObject.LableDict

        if scenarioDataFiles is not None:
            # overwrite the scenario data files with the ones from the wait and see analysis
            # if they are passed on to the function call
            # --------------------------
            Superstructure_Object.scenarioDataFiles = scenarioDataFiles

    elif _optimization_mode == 'sensitivity' or _optimization_mode == 'cross-parameter sensitivity':
        # collect the sensitivity data & automatically add it to the Superstructure_Object
        wrapp_sensitivity_data(Superstructure_Object, dataframe['Sensitivity'], cross_sensitivity_params)

    elif _optimization_mode == 'multi-objective':
        # collect the multi-objective data & automatically add it to the Superstructure_Object
        wrapp_multi_objective_data(Superstructure_Object, dataframe['Systemblatt'])

    return Superstructure_Object


