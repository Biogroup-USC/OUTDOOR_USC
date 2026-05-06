"""
Pytest tests for the upperFlowLimit / parallel-unit CAPEX logic.

These tests isolate the new logic added to create_EconomicEvaluation:
- upperFlowLimit[u] limits the reference flow per installed unit
- the model selects the required number of parallel units
- FCI is multiplied by the selected number of units

Run with:
    pytest test_economic_evaluation_upper_flow_limit.py

Requirements:
    pip install pyomo pytest
    plus a MILP solver available to Pyomo, e.g. glpk, cbc, highs
"""

import pytest


from pyomo.environ import (
    ConcreteModel,
    Set,
    RangeSet,
    Param,
    Var,
    Constraint,
    Objective,
    NonNegativeReals,
    Binary,
    minimize,
    value,
    SolverFactory,
)


def available_solver():
    """Return the first available MILP solver."""
    for solver_name in ("highs", "glpk", "cbc"):
        solver = SolverFactory(solver_name)
        if solver.available(exception_flag=False):
            return solver
    return None


def build_test_model(reference_flow, upper_flow_limit, ec=100.0, dc=0.1, idc=0.2, max_units=20):
    """
    Minimal model containing only the new unit-count / FCI logic.

    FCI should become:
        selected_number_of_units * EC * (1 + DC + IDC)
    """
    m = ConcreteModel()

    m.U_C = Set(initialize=["U1"])
    m.N_CAPEX = RangeSet(1, max_units)

    m.REF_FLOW_CAPEX = Var(m.U_C, within=NonNegativeReals)
    m.EC = Var(m.U_C, within=NonNegativeReals)
    m.FCI = Var(m.U_C, within=NonNegativeReals)

    m.upperFlowLimit = Param(m.U_C, initialize={"U1": upper_flow_limit}, mutable=True)
    m.DC = Param(m.U_C, initialize={"U1": dc}, mutable=True)
    m.IDC = Param(m.U_C, initialize={"U1": idc}, mutable=True)
    m.EC_BigM = Param(m.U_C, initialize={"U1": 1e6}, mutable=True)

    m.N_CAPEX_UNITS_BIN = Var(m.U_C, m.N_CAPEX, within=Binary)
    m.EC_SELECTED = Var(m.U_C, m.N_CAPEX, within=NonNegativeReals)

    # Fix inputs for the test case
    m.fix_reference_flow = Constraint(expr=m.REF_FLOW_CAPEX["U1"] == reference_flow)
    m.fix_ec = Constraint(expr=m.EC["U1"] == ec)

    def select_one_unit_count_rule(m, u):
        return sum(m.N_CAPEX_UNITS_BIN[u, n] for n in m.N_CAPEX) == 1

    def flow_must_be_covered_rule(m, u):
        return m.REF_FLOW_CAPEX[u] <= m.upperFlowLimit[u] * sum(
            n * m.N_CAPEX_UNITS_BIN[u, n] for n in m.N_CAPEX
        )

    def ec_selected_upper_binary_rule(m, u, n):
        return m.EC_SELECTED[u, n] <= m.EC_BigM[u] * m.N_CAPEX_UNITS_BIN[u, n]

    def ec_selected_upper_ec_rule(m, u, n):
        return m.EC_SELECTED[u, n] <= m.EC[u]

    def ec_selected_lower_rule(m, u, n):
        return m.EC_SELECTED[u, n] >= m.EC[u] - m.EC_BigM[u] * (
            1 - m.N_CAPEX_UNITS_BIN[u, n]
        )

    def fci_rule(m, u):
        return m.FCI[u] == sum(
            n * m.EC_SELECTED[u, n] * (1 + m.DC[u] + m.IDC[u])
            for n in m.N_CAPEX
        )

    m.select_one_unit_count = Constraint(m.U_C, rule=select_one_unit_count_rule)
    m.flow_must_be_covered = Constraint(m.U_C, rule=flow_must_be_covered_rule)
    m.ec_selected_upper_binary = Constraint(m.U_C, m.N_CAPEX, rule=ec_selected_upper_binary_rule)
    m.ec_selected_upper_ec = Constraint(m.U_C, m.N_CAPEX, rule=ec_selected_upper_ec_rule)
    m.ec_selected_lower = Constraint(m.U_C, m.N_CAPEX, rule=ec_selected_lower_rule)
    m.fci_constraint = Constraint(m.U_C, rule=fci_rule)

    # Minimise FCI so the model chooses the smallest sufficient number of units.
    m.objective = Objective(expr=m.FCI["U1"], sense=minimize)

    return m


@pytest.mark.parametrize(
    "reference_flow, upper_flow_limit, expected_units",
    [
        (50, 100, 1),
        (100, 100, 1),
        (101, 100, 2),
        (250, 100, 3),
        (999, 100, 10),
    ],
)
def test_selected_number_of_units(reference_flow, upper_flow_limit, expected_units):
    solver = available_solver()
    if solver is None:
        pytest.skip("No MILP solver available. Install highs, glpk, or cbc.")

    m = build_test_model(reference_flow, upper_flow_limit)
    result = solver.solve(m)

    assert str(result.solver.termination_condition).lower() == "optimal"

    selected_units = sum(
        n * round(value(m.N_CAPEX_UNITS_BIN["U1", n])) for n in m.N_CAPEX
    )

    assert selected_units == expected_units


def test_fci_is_multiplied_by_selected_units():
    solver = available_solver()
    if solver is None:
        pytest.skip("No MILP solver available. Install highs, glpk, or cbc.")

    m = build_test_model(
        reference_flow=250,
        upper_flow_limit=100,
        ec=100.0,
        dc=0.1,
        idc=0.2,
    )
    result = solver.solve(m)

    assert str(result.solver.termination_condition).lower() == "optimal"

    # 250 / 100 requires 3 units.
    # FCI = 3 * 100 * (1 + 0.1 + 0.2) = 390
    assert value(m.FCI["U1"]) == pytest.approx(390.0)


def test_infeasible_if_required_units_exceed_max_units():
    solver = available_solver()
    if solver is None:
        pytest.skip("No MILP solver available. Install highs, glpk, or cbc.")

    m = build_test_model(
        reference_flow=2500,
        upper_flow_limit=100,
        max_units=20,
    )
    result = solver.solve(m)

    assert str(result.solver.termination_condition).lower() in {
        "infeasible",
        "infeasibleorunbounded",
    }
