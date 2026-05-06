def create_EconomicEvaluation(self):
    """
    Creates PYOMO parameters, variables and constraints for economic evaluation.
    Added:
    - upperFlowLimit[u]: maximum reference flow per single unit
    - N_CAPEX_UNITS[u]: selected number of parallel units
    - FCI scales with the number of required units
    """

    # Parameter
    # ---------

    self.delta_ut = Param(self.U_UT, initialize=0, mutable=True)
    self.delta_q = Param(self.HI, initialize=30, mutable=True)
    self.delta_cool = Param(initialize=15, mutable=True)
    self.ProductPrice = Param(self.U_PP, initialize=0, mutable=True)

    self.DC = Param(self.U, initialize=0, mutable=True)
    self.IDC = Param(self.U, initialize=0, mutable=True)
    self.ACC_Factor = Param(self.U, initialize=0, mutable=True)

    self.HP_ACC_Factor = Param(initialize=1, mutable=True)
    self.HP_Costs = Param(initialize=1, mutable=True)

    self.lin_CAPEX_x = Param(self.U_C, self.J, initialize=0)
    self.lin_CAPEX_y = Param(self.U_C, self.J, initialize=0)
    self.kappa_1_capex = Param(self.U_C, self.I, initialize=0)
    self.kappa_2_capex = Param(self.U_C, initialize=5)

    self.K_OM = Param(self.U_C, initialize=0.04, mutable=True)

    # NEW: maximum allowed reference flow per unit
    # Set this externally for each unit.
    # Large default means "no practical limit".
    self.upperFlowLimit = Param(self.U_C, initialize=1e12, mutable=True)

    # NEW: maximum number of parallel units allowed
    # Increase this if needed.
    self.N_CAPEX = RangeSet(1, 20)

    # NEW: big-M for EC linearisation
    # Should be larger than the maximum expected EC value.
    self.EC_BigM = Param(self.U_C, initialize=1e6, mutable=True)

    # Variables
    # ---------

    self.ENERGY_COST = Var(self.U_UT)
    self.COST_HEAT = Var(self.HI, initialize=0)
    self.COST_UT = Var(initialize=0)
    self.ELCOST = Var()
    self.HEATCOST = Var(self.HI)
    self.C_TOT = Var()
    self.HENCOST = Var(self.HI, within=NonNegativeReals)
    self.UtCosts = Var()

    self.lin_CAPEX_s = Var(self.U_C, self.JI, bounds=(0, 1))
    self.lin_CAPEX_z = Var(self.U_C, self.JI, within=Binary)
    self.lin_CAPEX_lambda = Var(self.U_C, self.J, bounds=(0, 1))
    self.REF_FLOW_CAPEX = Var(self.U_C, within=NonNegativeReals)

    self.EC = Var(self.U_C, within=NonNegativeReals)
    self.FCI = Var(self.U_C, within=NonNegativeReals)
    self.ACC = Var(self.U_C, within=NonNegativeReals)
    self.to_acc = Param(self.U_C, initialize=0, mutable=True)
    self.TO_CAPEX = Var(self.U_C, within=NonNegativeReals)
    self.TO_CAPEX_TOT = Var(within=NonNegativeReals)
    self.ACC_HP = Var(within=NonNegativeReals)
    self.TAC = Var()
    self.CAPEX = Var()

    # NEW: selected number of installed parallel units
    self.N_CAPEX_UNITS_BIN = Var(self.U_C, self.N_CAPEX, within=Binary)

    # NEW: auxiliary variable to linearise EC * selected_number_of_units
    self.EC_SELECTED = Var(self.U_C, self.N_CAPEX, within=NonNegativeReals)

    self.RM_COST_TOT = Var()
    self.M_COST = Var(self.U_C)
    self.M_COST_TOT = Var(within=NonNegativeReals)
    self.OPEX = Var()
    self.PROFITS = Var(self.U_PP)
    self.PROFITS_TOT = Var()

    # Constraints
    # -----------

    def CapexEquation_1_rule(self, u):
        if self.kappa_2_capex[u] == 1:
            return self.REF_FLOW_CAPEX[u] == sum(
                self.FLOW_IN[u, i] * self.kappa_1_capex[u, i] for i in self.I
            )
        elif self.kappa_2_capex[u] == 0:
            return self.REF_FLOW_CAPEX[u] == sum(
                self.FLOW_OUT[u, i] * self.kappa_1_capex[u, i] for i in self.I
            )
        elif self.kappa_2_capex[u] == 2:
            return self.REF_FLOW_CAPEX[u] == self.ENERGY_DEMAND[u, "Electricity"]
        elif self.kappa_2_capex[u] == 3:
            return self.REF_FLOW_CAPEX[u] == self.ENERGY_DEMAND_HEAT_PROD[u]
        elif self.kappa_2_capex[u] == 4:
            return self.REF_FLOW_CAPEX[u] == self.EL_PROD_1[u]
        else:
            return self.REF_FLOW_CAPEX[u] == 0

    def CapexEquation_2_rule(self, u):
        return (
            sum(self.lin_CAPEX_x[u, j] * self.lin_CAPEX_lambda[u, j] for j in self.J)
            == self.REF_FLOW_CAPEX[u]
        )

    def CapexEquation_3_rule(self, u):
        return self.EC[u] == sum(
            self.lin_CAPEX_y[u, j] * self.lin_CAPEX_lambda[u, j] for j in self.J
        )

    def CapexEquation_4_rule(self, u):
        return sum(self.lin_CAPEX_z[u, j] for j in self.JI) == 1

    def CapexEquation_5_rule(self, u, j):
        return self.lin_CAPEX_s[u, j] <= self.lin_CAPEX_z[u, j]

    def CapexEquation_6_rule(self, u, j):
        if j == 1:
            return (
                self.lin_CAPEX_lambda[u, j]
                == self.lin_CAPEX_z[u, j] - self.lin_CAPEX_s[u, j]
            )
        elif j == len(self.J):
            return self.lin_CAPEX_lambda[u, j] == self.lin_CAPEX_s[u, j - 1]
        else:
            return (
                self.lin_CAPEX_lambda[u, j]
                == self.lin_CAPEX_z[u, j]
                - self.lin_CAPEX_s[u, j]
                + self.lin_CAPEX_s[u, j - 1]
            )

    # NEW: exactly one number of parallel units is selected
    def CapexUnitCount_1_rule(self, u):
        return sum(self.N_CAPEX_UNITS_BIN[u, n] for n in self.N_CAPEX) == 1

    # NEW: total reference flow must be covered by selected units
    def CapexUnitCount_2_rule(self, u):
        return self.REF_FLOW_CAPEX[u] <= self.upperFlowLimit[u] * sum(
            n * self.N_CAPEX_UNITS_BIN[u, n] for n in self.N_CAPEX
        )

    # NEW: linearisation of EC_SELECTED[u,n] = EC[u] if n is selected
    def CapexUnitCount_3_rule(self, u, n):
        return self.EC_SELECTED[u, n] <= self.EC_BigM[u] * self.N_CAPEX_UNITS_BIN[u, n]

    def CapexUnitCount_4_rule(self, u, n):
        return self.EC_SELECTED[u, n] <= self.EC[u]

    def CapexUnitCount_5_rule(self, u, n):
        return self.EC_SELECTED[u, n] >= self.EC[u] - self.EC_BigM[u] * (
            1 - self.N_CAPEX_UNITS_BIN[u, n]
        )

    # MODIFIED: FCI now includes number of required units
    def CapexEquation_7_rule(self, u):
        return self.FCI[u] == sum(
            n * self.EC_SELECTED[u, n] * (1 + self.DC[u] + self.IDC[u])
            for n in self.N_CAPEX
        )

    def CapexEquation_8_rule(self, u):
        return self.ACC[u] == self.FCI[u] * self.ACC_Factor[u]

    self.ACC_H = Var(within=NonNegativeReals)

    def CapexEquation_9_rule(self):
        return (
            self.ACC_H
            == self.HP_ACC_Factor * self.HP_Costs * self.ENERGY_DEMAND_HP_USE
        )

    def Cap(self):
        return self.ACC_HP == self.ACC_H / 1000

    self.Xap = Constraint(rule=Cap)

    def CapexEquation_11_rule(self, u):
        return self.TO_CAPEX[u] == self.to_acc[u] * self.EC[u]

    def CapexEquation_12_rule(self):
        return self.TO_CAPEX_TOT == sum(self.TO_CAPEX[u] for u in self.U_C)

    def HEN_CostBalance_4_rule(self, hi):
        return self.HENCOST[hi] <= (
            13.459 * self.ENERGY_EXCHANGE[hi]
            + 3.3893
            + self.alpha_hex * (1 - self.Y_HEX[hi])
        )

    def HEN_CostBalance_4b_rule(self, hi):
        return self.HENCOST[hi] >= (
            13.459 * self.ENERGY_EXCHANGE[hi]
            + 3.3893
            - self.alpha_hex * (1 - self.Y_HEX[hi])
        )

    def HEN_CostBalance_4c_rule(self, hi):
        return self.HENCOST[hi] <= self.Y_HEX[hi] * self.alpha_hex

    def CapexEquation_10_rule(self):
        return (
            self.CAPEX
            == sum(self.ACC[u] for u in self.U_C)
            + self.ACC_HP / 1000
            + self.TO_CAPEX_TOT
            + sum(self.HENCOST[hi] for hi in self.HI) / 1000
        )

    self.CapexEquation_1 = Constraint(self.U_C, rule=CapexEquation_1_rule)
    self.CapexEquation_2 = Constraint(self.U_C, rule=CapexEquation_2_rule)
    self.CapexEquation_3 = Constraint(self.U_C, rule=CapexEquation_3_rule)
    self.CapexEquation_4 = Constraint(self.U_C, rule=CapexEquation_4_rule)
    self.CapexEquation_5 = Constraint(self.U_C, self.JI, rule=CapexEquation_5_rule)
    self.CapexEquation_6 = Constraint(self.U_C, self.J, rule=CapexEquation_6_rule)

    self.CapexUnitCount_1 = Constraint(self.U_C, rule=CapexUnitCount_1_rule)
    self.CapexUnitCount_2 = Constraint(self.U_C, rule=CapexUnitCount_2_rule)
    self.CapexUnitCount_3 = Constraint(self.U_C, self.N_CAPEX, rule=CapexUnitCount_3_rule)
    self.CapexUnitCount_4 = Constraint(self.U_C, self.N_CAPEX, rule=CapexUnitCount_4_rule)
    self.CapexUnitCount_5 = Constraint(self.U_C, self.N_CAPEX, rule=CapexUnitCount_5_rule)

    self.CapexEquation_7 = Constraint(self.U_C, rule=CapexEquation_7_rule)
    self.CapexEquation_8 = Constraint(self.U_C, rule=CapexEquation_8_rule)
    self.CapexEquation_9 = Constraint(rule=CapexEquation_9_rule)

    self.HEN_CostBalance_4 = Constraint(self.HI, rule=HEN_CostBalance_4_rule)
    self.HEN_CostBalance_4b = Constraint(self.HI, rule=HEN_CostBalance_4b_rule)
    self.HEN_CostBalance_4c = Constraint(self.HI, rule=HEN_CostBalance_4c_rule)

    self.CapexEquation_10 = Constraint(rule=CapexEquation_10_rule)
    self.CapexEquation_11 = Constraint(self.U_C, rule=CapexEquation_11_rule)
    self.CapexEquation_12 = Constraint(rule=CapexEquation_12_rule)

    def HEN_CostBalance_1_rule(self, hi):
        return (
            self.HEATCOST[hi]
            == self.ENERGY_DEMAND_HEAT_DEFI[hi] * self.delta_q[hi] * self.H
        )

    def HEN_CostBalance_2_rule(self):
        return self.UtCosts == (
            sum(self.HEATCOST[hi] for hi in self.HI)
            - self.ENERGY_DEMAND_HEAT_PROD_SELL * self.H * self.delta_q[1] * 0.7
            + self.ENERGY_DEMAND_COOLING * self.H * self.delta_cool
        )

    def HEN_CostBalance_3_rule(self):
        return (
            self.ELCOST
            == self.ENERGY_DEMAND_HP_EL * self.delta_ut["Electricity"] * self.H / 1000
        )

    def HEN_CostBalance_6_rule(self):
        return self.C_TOT == self.UtCosts / 1000

    self.HEN_CostBalance_1 = Constraint(self.HI, rule=HEN_CostBalance_1_rule)
    self.HEN_CostBalance_2 = Constraint(rule=HEN_CostBalance_2_rule)
    self.HEN_CostBalance_3 = Constraint(rule=HEN_CostBalance_3_rule)
    self.HEN_CostBalance_6 = Constraint(rule=HEN_CostBalance_6_rule)

    def Ut_CostBalance_1_rule(self, ut):
        return (
            self.ENERGY_COST[ut]
            == self.ENERGY_DEMAND_TOT[ut] * self.delta_ut[ut] / 1000
        )

    self.Ut_CostBalance_1 = Constraint(self.U_UT, rule=Ut_CostBalance_1_rule)

    def RM_CostBalance_1_rule(self):
        return self.RM_COST_TOT == sum(
            self.materialcosts[u_s] * self.FLOW_SOURCE[u_s] * self.flh[u_s] / 1000
            for u_s in self.U_S
        )

    def OM_CostBalance_1_rule(self, u):
        return self.M_COST[u] == self.K_OM[u] * self.FCI[u]

    def OM_CostBalance_2_rule(self):
        return self.M_COST_TOT == sum(self.M_COST[u] for u in self.U_C)

    def Opex_1_rule(self):
        return (
            self.OPEX
            == self.M_COST_TOT
            + self.RM_COST_TOT / 1000
            + sum(self.ENERGY_COST[ut] for ut in self.U_UT) / 1000
            + self.C_TOT / 1000
            + self.ELCOST / 1000
            + self.WASTE_COST_TOT / 1000
        )

    self.RM_CostBalance_1 = Constraint(rule=RM_CostBalance_1_rule)
    self.OM_CostBalance_1 = Constraint(self.U_C, rule=OM_CostBalance_1_rule)
    self.OM_CostBalance_2 = Constraint(rule=OM_CostBalance_2_rule)
    self.OpexEquation = Constraint(rule=Opex_1_rule)

    def Profit_1_rule(self, u):
        return (
            self.PROFITS[u]
            == sum(self.FLOW_IN[u, i] for i in self.I) * self.ProductPrice[u] / 1000
        )

    def Profit_2_rule(self):
        return self.PROFITS_TOT == sum(self.PROFITS[u] for u in self.U_PP) * self.H / 1000

    self.ProfitEquation_1 = Constraint(self.U_PP, rule=Profit_1_rule)
    self.ProfitEquation_2 = Constraint(rule=Profit_2_rule)

    def TAC_1_rule(self):
        return self.TAC == (self.CAPEX + self.OPEX - self.PROFITS_TOT) * 1000

    self.TAC_Equation = Constraint(rule=TAC_1_rule)
