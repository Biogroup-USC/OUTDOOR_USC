"""
Collects the data related to the specific optimization mode (e.g., stochastic, sensitivity, etc.)

contains the following functions:


author: Lucas Van der Hauwaert
date: october 2020
"""
import pandas as pd

from . import wrapping_functions as WF
from ..outdoor_core.input_classes.stochastic import StochasticObject


def wrapp_stochastic_data(dfi, seed=66, scenario_size=None):
    # make the initial stochastic object
    obj = StochasticObject()

    # get all locations of the stochastic data of interest
    generalDataRange = WF.convert_total('B', 3, 'C', 8)
    generalDataFrame = dfi.iloc[generalDataRange]
    # make the first column of the dataframe the index of the dataframe
    generalDataFrame = generalDataFrame.set_index('Unnamed: 1')
    # make the dataframe a series
    generalDataFrame = generalDataFrame.squeeze()

    # get the custom level data
    customLevelRange = WF.convert_total('B', 14, 'B', 21)
    customLevelDataFrame = dfi.iloc[customLevelRange]

    # set the general data
    obj.set_general_data(generalDataFrame, customLevelDataFrame, scenario_size)

    # extract the uncertain parameters from the dataframe
    UncertainParametersRange = WF.convert_total('B', 25, 'K', 52)
    UncertainParametersDataFrame = dfi.iloc[UncertainParametersRange]
    obj.set_uncertain_params_dict(UncertainParametersDataFrame)

    # correct for the composition of the feed stocks that do not change (+ make sure the sum is allways 1)
    phiExclusionRange = WF.convert_total('D', 14, 'J', 21)  # feed composition
    phiExclusionDF = dfi.iloc[phiExclusionRange]
    obj.set_phi_exclusion_list(phiExclusionDF)

   # make the scenario dataframe, depending on the sampling mode
    if obj.SamplingMode == 'Combinatorial':
        # set the grouped parameters (i.e., those with the correlated uncertainty)
        obj.set_group_dict()
        obj.make_scenario_dataframe_combinatorial()

    elif obj.SamplingMode == 'LHS':
        #obj.set_group_dict()
        obj.make_scenario_dataframe_LHS(seed=seed)

    else:
        raise ValueError('Sampling mode not recognized')

    return obj

def wrapp_sensitivity_data(obj, dfi, cross_sensitivity_params):

    sensitivity_data = {}

    if obj.optimization_mode == 'sensitivity':
        DataRange = WF.convert_total('C', 9, 'J', 36)
        dfSensi = dfi.iloc[DataRange]
        # make the first row the column names
        dfSensi.columns = dfSensi.iloc[0]
        dfSensi = dfSensi.drop(dfSensi.index[0])
        # get the range to loop over
        rangeSensitivity = range(len(dfSensi))

    elif obj.optimization_mode == 'cross-parameter sensitivity':
        if cross_sensitivity_params:
            # get the cross sensitivity parameters
            dfSensi = pd.DataFrame(cross_sensitivity_params)
        else:
            DataRange = WF.convert_total('L', 9, 'S', 11)
            dfSensi = dfi.iloc[DataRange]
            # make the first row the column names
            dfSensi.columns = dfSensi.iloc[0]
            dfSensi = dfSensi.drop(dfSensi.index[0])
        # get the range to loop over, which will always be two
        rangeSensitivity = range(2)
    else:
        raise ValueError('The optimization mode {} is not recognized'.format(obj.optimization_mode))

    for i in rangeSensitivity:
        if not pd.isnull(dfSensi.iloc[i, 0]):
            dfSensiRow = dfSensi.iloc[i]
            obj.sensitive_parameters.append(dfSensiRow)

            # p_name = dfSensiRow['Parameter_Type']
            # min_v = dfSensiRow['Lower_Bound']
            # max_v = dfSensiRow['Upper_Bound']

            # steps = dfSensiRow['Number_of_steps']
            # metadata = dfSensiRow.iloc[1:5]
            # # get the metadata to pass it on so we know what indexes to use when acessing the parameters

            # # add the sensitivity parameters to the object
            # # add_sensi_parameters is a dumb function, just skip it and add the parameters directly as a list of series
            # # obj.add_sensi_parameters.append((p_name, min_v, max_v, steps, metadata))

def wrapp_multi_objective_data(obj, dfi):

    MultiCriteriaRange = WF.convert_total('N', 32, 'P',34)
    df9 = dfi.iloc [MultiCriteriaRange]

    dict1 = {}
    dict1[df9.iloc[0,0]] = (df9.iloc[0,1], df9.iloc[0,2])
    dict1[df9.iloc[1,0]] = (df9.iloc[1,1], df9.iloc[1,2])
    dict1[df9.iloc[2,0]] = (df9.iloc[2,1], df9.iloc[2,2])

    obj.set_multiObjectives(dict1)
