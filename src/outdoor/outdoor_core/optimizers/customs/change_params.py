#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 15 11:54:16 2021

@author: philippkenkel
"""

from ...utils.timer import time_printer
#from pyomo.environ import *
from numpy import linspace

from .change_functions.parameter_changer_functions import * # contains all funcitions to change the parameters in the model instance called in change_parameter
# from pyomo.environ import *
from numpy import linspace

from .change_functions.parameter_changer_functions import *  # contains all funcitions to change the parameters in the model instance called in change_parameter
from ...utils.timer import time_printer
import re


# from .change_functions.utility_cost_changer import change_utility_costs
# from .change_functions.capital_cost_changer import change_capital_costs
# from .change_functions.concentration_demand_changer import (
#     change_concentration_demand,
# )
# from .change_functions.heat_demand_changer import change_heat_demand
#
# from .change_functions.opex_changer import change_opex_factor
# from .change_functions.simple_capex_changer import change_simple_capex





def calculate_sensitive_parameters(data_input):

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
            unitUid = i['unitUid'][0:3]
            paramName = paramName + "_" + str(n) + ""

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


def error_func(*args):
    raise ValueError("Parameter {} not in Variation Parameter set defining all changer functions".format(args[-1]))


def change_parameter(Instance, parameter, value, metadata=None, superstructure=None, printTimer=True):

    timer = time_printer(programm_step = 'Changing parameter {}'.format(parameter), printTimer=printTimer)

    function_dictionary = {
        # these are also parameters that can be changed in the stochastic mode
        'Split factors (myu)': change_myu_parameter,
        'Feed Composition (phi)': change_phi_parameter,
        'Conversion factor (theta)': change_theta_parameter,
        'Stoichiometric factor (gamma)': change_stoich_parameter,
        'Yield factor (xi)': change_xi_parameter,
        'Costs (materialcosts)': change_material_costs,
        'Price (ProductPrice)': change_product_price,

        "Electricity price (delta_ut)": change_utility_costs,
        "Chilling price (delta_ut)": change_utility_costs,

        "Heating price super (delta_q)": change_heat_costs,
        "Heating price high (delta_q)": change_heat_costs,
        "Heating price medium (delta_q)": change_heat_costs,
        "Heating price low (delta_q)": change_heat_costs,

        'Heating demand 1 (tau_h)': change_heating_demand,
        'Heating demand 2 (tau_h)': change_heating_demand,
        'Electricity demand (tau)': change_utility_demand,
        'Chilling demand (tau)': change_utility_demand,

        'Component concentration (conc)': change_concentration_demand,
        'Reference Capital costs (C_Ref)': change_capital_costs,
        'Operating and maintenance (K_OM)': change_opex_factor,


        # "component_concentration": change_concentration_demand,
        # "heating_demand": change_heat_demand,
        # "opex": change_opex_factor,
        # "simple_capex": change_simple_capex,
        # "product_price": change_product_price,
    }

    # list of possible parameters which are mutable
    paramList = list(function_dictionary.keys())

    if "electricity_price" in parameter:
        parameter = "Electricity price (delta_ut)"
    else:
        for p in paramList:
            if p in parameter:
                parameter = p
                break

    function_dictionary.get(parameter, error_func)(Instance, value, metadata, superstructure, parameter)
    #timer = time_printer(timer, 'Change parameter')
    return Instance


def prepare_mutable_parameters(ModelInstance, input_data):
    def set_mutable(instance, parameter):
        # for parameters where more than 1 model.parameter is changed at the same time
        if parameter == "Reference Capital costs (C_Ref)":
            instance.lin_CAPEX_x._mutable = True
            instance.lin_CAPEX_y._mutable = True
        elif parameter == "Heating demand (tau_h)":
            instance.tau_h._mutable = True
            instance.tau_c._mutable = True
            instance.tau._mutable = True

    for i in input_data:
        param_name = i.iloc[0]
        if param_name == "Reference Capital costs (C_Ref)" or param_name == "Heating demand (tau_h)":
            # if more than one parameter is changed at the same time, we need to set them mutable using the
            # set_mutable function
            set_mutable(ModelInstance, param_name)

        elif param_name == "electricity_price":

            param = getattr(ModelInstance, "delta_ut")  # Dynamically access the parameter
            # change the parameter to mutable
            param._mutable = True

        else:
            #param_id = param_name.split("(")[-1][0:-1] # Get the parameter name in between the brackets
            param_id = extract_string_between_brackets(param_name)
            param = getattr(ModelInstance, param_id)  # Dynamically access the parameter
            # change the parameter to mutable
            param._mutable = True

    return ModelInstance


def extract_string_between_brackets(s):
    # Regular expression pattern to match text within parentheses
    pattern = r'\((.*?)\)'
    # Search for the pattern in the input string
    match = re.search(pattern, s)
    # If a match is found, return the matched group, otherwise return None
    return match.group(1) if match else None
