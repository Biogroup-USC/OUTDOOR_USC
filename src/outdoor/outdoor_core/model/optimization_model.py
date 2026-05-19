from pyomo.environ import *



class SuperstructureModel(AbstractModel):
    """
    Class description
    -----------------

    This class holds the mathematical model equations to describe a superstructure
    model. It defines classical modeling components like sets, parameter, variables
    and constraints.

    The model inlcudes mass balances, energy balances inlcuding detailed
    heat intergration based on heat intervals, cost functions using piece-wise
    linear capital costs and operational costs based on utilities, raw materials,
    operating and maintenance and other aspects. Additionally GWP and fresh
    water demand are calculated.

    """

    def __init__(self, superstructure_input=None, fixedDesign=False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if superstructure_input is not None:
            self._set_optionals_from_superstructure(superstructure_input)
        else:
            self._set_optionals_from_external(kwargs)

        # if True, the model will make the binary variables parameters for flow choice, therefore fixing the design of
        # the flow-sheet
        self._fixedDesign = fixedDesign

    def _set_optionals_from_superstructure(self, superstructure_input):
        """
        Parameters
        ----------
        superstructure_input : Superstructure Object

        Description
        -----------
        uses a superstructure object to optionals which are:
                - Heat pump implementation (active/TIN/TOUT)
                - Additional logics (Groups/forces connections)
                - Objective name (NPC/NPE/NPFWD)
        """

        # self.productDriven = superstructure_input.productDriven.lower()
        self.loadType = superstructure_input.loadType

        # list of impact categories should be the same as the set created in the model, see self.IMPACT_CATEGORIES
        self.impact_categories_list = superstructure_input.ImpactCategories['IMPACT_CATEGORIES']

        if superstructure_input.HP_active:
            self.heat_pump_options = {
                "active": superstructure_input.HP_active,
                "t_in": superstructure_input.HP_T_IN["Interval"],
                "t_out": superstructure_input.HP_T_OUT["Interval"],
            }
        else:
            self.heat_pump_options = {
                "active": superstructure_input.HP_active,
                "t_in": 0,
                "t_out": 0}

        self.objective_name = superstructure_input.objective
        self.groups = superstructure_input.groups
        self.connections = superstructure_input.connections

        self.loadID = None
        if self.loadType:  # if it's product or substrate load
            loadName = superstructure_input.loadName
            for unit in superstructure_input.UnitsList:
                if unit.Name == loadName:
                    self.loadID = unit.Number

            if not self.loadID:
                raise ValueError('The load Name {} is not valid, check if it is correctly written in the excel '
                                 'file'.format(loadName))
        else:
            self.loadID = None
        # checkList = []
        # for i in superstructure_input.UnitsList:
        #     if i.Type == "ProductPool" and i.ProductType == "MainProduct":
        #         self.main_pool = i.Number
        #         checkList.append(i.Number)
#
        # # create warning if more than one main product pool is defined and the model is product driven
        # if len(checkList) > 1 and self.loadType == 'Product':
        #     raise ValueError("There is more than one product pool defined as the mainProduct. "
        #                      "Please check the superstructure inputs and select only one main product if the process is"
        #                      "Product driven (see general data tab).")
#
        # if len(checkList) == 0 and self.loadType == 'Product':
        #     raise ValueError("There is no main product pool defined. Please check the superstructure inputs and select "
        #                      "one main product if the process is Product driven (see general data tab).")

    def _set_options_from_external(self, **kwargs):
        print("There is no external parsing implemented at the moment.")


    def create_ModelEquations(self):
        """
        Description
        -------
        Calls single methods to build the model in the order:
            - Sets
            - Mass balances
            - Energy balances
            - Economic functions
            - GWP functions
            - FWD functions
            - Logics
            - Objective function
        """

        self.create_Sets()
        self.create_MassBalances()
        self.create_EnergyBalances()
        self.create_WasteCosts()
        self.create_EconomicEvaluation()
        self.create_LCAEquations()
        self.create_DecisionMaking()
        self.create_ObjectiveFunction()

    def populateModel(self, Data_file):
        """
        Parameters
        ----------
        Data_file : Dictionary
            Model data in AbstractModel readable file

        Returns
        -------
        PYOMO ConcreteModel
            filled model instance with equations from SuperstructureModel and
            data from Data_file.

        """
        self.ModelInstance = self.create_instance(Data_file)
        return self.ModelInstance

    # Pyomo Model Methods
    # --------------------

    # **** SETS  ****
    # ----------------

    def create_Sets(self):
        """
        Description
        -------
        Creates all needed Sets for the model including, unit operations, components,
        utilities, reactions, heat intervals etc.

        """

        # Process Unit operations
        # -------------
        self.U = Set()
        self.UU = Set(within=self.U)
        self.U_STOICH_REACTOR = Set(within=self.U)
        self.U_YIELD_REACTOR = Set(within=self.U)
        self.U_SPLITTER = Set(within=self.U)
        self.U_TUR = Set(within=self.U)
        self.U_FUR = Set(within=self.U)
        self.U_PP = Set(within=self.U)
        self.U_C = Set(within=self.U)
        self.U_S = Set(within=self.U)
        self.U_SU = Set(within=self.U_S * self.U)
        self.U_DIST = Set(within=self.U)
        self.U_DIST_SUB = Set(within=self.U_DIST * self.U)
        self.U_CONNECTORS = Set(within=self.U * self.U)

        # waste Management
        self.WASTE_MANAGEMENT_TYPES = Set(initialize=["Incineration", "Landfill", "WWTP"])

        # impact categories of life cycle assessment
        self.IMPACT_CATEGORIES = Set(initialize=["GWP"])

        # Components
        # ----------
        self.I = Set()
        self.M = Set(within=self.I)
        self.YC = Set(within=self.U_YIELD_REACTOR * self.I)

        # Reactions, Utilities, Heat intervals
        # ------------------------------------
        self.R = Set()
        self.UT = Set()
        self.H_UT = Set(within=self.UT)
        self.U_UT = Set(within=self.UT)
        self.HI = Set()

        # Piece-Wise Linear CAPEX
        # -----------------------
        self.J = Set()
        self.JI = Set(within=self.J)

        # Distributor Set for decimal numbers

        def iterator(x):
            nlist = []
            for i in range(x):
                nlist.append(i)
            return nlist

        self.DC_SET = Set(within=self.U_DIST * iterator(100))

        self.U_DIST_SUB2 = Set(within=self.U_DIST_SUB * self.U_DIST * iterator(100))

    # **** MASS BALANCES *****
    # -------------------------

    def create_MassBalances(self):
        """
        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general Mass Balances (eg. FLOWS, PHI, MYU etc.).
        Afterwards Masse Balance Equations are written as PYOMO Constraints.

        """

        # Parameter
        # ---------
        self.ProductLoad = Param(initialize=1, mutable=True)
        self.SubstrateLoad = Param(initialize=1, mutable=True)
        self.sourceOrProductLoad = Param(initialize=1, mutable=True)

        # Flow parameters (Split factor, concentrations, full load hours)
        self.myu = Param(self.U_CONNECTORS, self.I, initialize=0, mutable=True)
        self.conc = Param(self.U, initialize=0, within=Any, mutable=True)
        self.flh = Param(self.U, mutable=True)
        self.MinProduction = Param(self.U_PP, initialize=0, mutable=True)
        self.MaxProduction = Param(self.U_PP, initialize=100000, mutable=True)


        # Reaction parameters(Stoich. / Yield Coefficients)
        self.gamma = Param(self.U_STOICH_REACTOR, self.I, self.R, initialize=0, mutable=True)
        self.theta = Param(self.U_STOICH_REACTOR, self.R, self.M, initialize=0, mutable=True)
        self.xi = Param(self.U_YIELD_REACTOR, self.I, initialize=0, mutable=True)
        self.ic_on = Param(self.U_YIELD_REACTOR, initialize=0)

        # Additional slack parameters (Flow choice, upper bounds, )
        self.kappa_1_lhs_conc = Param(self.U, self.I, initialize=0)
        self.kappa_1_rhs_conc = Param(self.U, self.I, initialize=0)
        self.kappa_2_lhs_conc = Param(self.U, initialize=3)
        self.kappa_2_rhs_conc = Param(self.U, initialize=3)
        self.Names = Param(self.U, within= Any)
        self.alpha = Param(self.U, initialize=100000, mutable=True)

        # upper and lower bounds for source flows
        self.ul = Param(self.U_S, initialize=100000, mutable=True)
        self.ll = Param(self.U_S, initialize=0, mutable=True)

        # component composition parameters
        self.phi = Param(self.U_S, self.I, initialize=0, mutable=True)

        # cost parameters
        self.materialcosts = Param(self.U_S, initialize=0, mutable=True)

        # Decimal_numbers help to model the distributor equations
        # it sets the degree of "detail" for the distributor
        self.Decimal_numbers = Param(self.DC_SET, mutable=True)

        # Variables
        # --------

        self.FLOW = Var(self.U_CONNECTORS, self.I, within=NonNegativeReals)
        self.FLOW_IN = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_OUT = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_WASTE = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_WASTE_TOTAL = Var(self.I, within=NonNegativeReals)
        self.FLOW_ADD = Var(self.U_SU, within=NonNegativeReals)
        self.FLOW_ADD_TOT = Var(self.U, self.I, within=NonNegativeReals)
        self.FLOW_SUM = Var(self.U, within=NonNegativeReals)
        self.FLOW_SOURCE = Var(self.U_S, within=NonNegativeReals)
        self.FLOW_DIST = Var(self.U_DIST_SUB2, self.I, within=NonNegativeReals)
        self.FLOW_FT = Var(self.U_CONNECTORS, within=NonNegativeReals)

        # to get the fractions that the stream is split into for each U_DIST to U (that is connected)
        # this is used as a variable for the second stage of the stochastic model to get the distribution factor
        # equal over all scenarios
        self.DistFraction = Var(self.U_DIST_SUB, within=NonNegativeReals)

        # Binary Variables for flow choice also 1ste Stage Variables of the stochastic models!
        if self._fixedDesign:
            # Binary but can be any value to avoid errors (for values which aren't exactly 0 or 1)
            self.Y = Param(self.U, within=AnyWithNone)
            self.Y_DIST = Param(self.U_DIST_SUB2, within=AnyWithNone)
        else:
            self.Y = Var(self.U, within=Binary)
            self.Y_DIST = Var(self.U_DIST_SUB2, within=Binary)


        # Constraints
        # -----------

        def MassBalance_1_rule(self, u, i):
            return self.FLOW_IN[u, i] == self.FLOW_ADD_TOT[u, i] + sum(self.flh[uu] / self.flh[u] * self.FLOW[uu, u, i] for uu in self.UU if (uu,u) in self.U_CONNECTORS)

        def MassBalance_2_rule(self, u, i):
            return self.FLOW_ADD_TOT[u, i] == sum(
                self.FLOW_ADD[u_s, u] * self.phi[u_s, i]
                for u_s in self.U_S
                if (u_s, u) in self.U_SU
            )

        def MassBalance_3_rule(self, u_s, u):
            return self.FLOW_ADD[u_s, u] <= self.alpha[u] * self.Y[u]  # Big M constraint

        def MassBalance_4_rule(self, u_s):
            return self.FLOW_SOURCE[u_s] == sum(
                self.FLOW_ADD[u_s, u] * self.flh[u] / self.flh[u_s]
                for u in self.U
                if (u_s, u) in self.U_SU
            )
         # upper and lower bounds for source flows
        def MassBalance_13_rule(self, u_s):
            # bounds defined in tons per year (t/h) hence flow times full loading hours
            if u_s == self.loadID and self.loadType == 'Substrate':
                return self.FLOW_SOURCE[self.loadID] <= self.sourceOrProductLoad / self.H
            else:
                return self.FLOW_SOURCE[u_s] <= self.ul[u_s]

        def MassBalance_14_rule(self, u_s):
            # bounds defined in tons per year (t/a) hence flow times full loading hours
            if u_s == self.loadID and self.loadType == 'Substrate':
                return self.FLOW_SOURCE[self.loadID] >= self.sourceOrProductLoad / self.H
            else:
                return self.FLOW_SOURCE[u_s] >= self.ll[u_s]

        def MassBalance_15_rule(self):
            if self.loadType == 'Substrate':
                # if the optimisation is substrate driven the mass flow is predefined, load is in tons/year
                return self.FLOW_SOURCE[self.loadID] == self.sourceOrProductLoad / self.H # in tons/h
            else:
                return Constraint.Skip

        # stoichimoetric and yield reactor equations
        def MassBalance_5_rule(self, u, i):
            if u in self.U_YIELD_REACTOR:
                if self.ic_on[u] == 1:
                    if (u, i) in self.YC:
                        return (
                            self.FLOW_OUT[u, i]
                            == self.FLOW_IN[u, i]
                            + sum(
                                self.FLOW_IN[u, i]
                                for i in self.I
                                if (u, i) not in self.YC
                            )
                            * self.xi[u, i]
                        )
                    else:
                        return (
                            self.FLOW_OUT[u, i]
                            == sum(
                                self.FLOW_IN[u, i]
                                for i in self.I
                                if (u, i) not in self.YC
                            )
                            * self.xi[u, i]
                        )
                else:
                    return (
                        self.FLOW_OUT[u, i]
                        == sum(self.FLOW_IN[u, i] for i in self.I) * self.xi[u, i]
                    )
            elif u in self.U_STOICH_REACTOR:
                return self.FLOW_OUT[u, i] == self.FLOW_IN[u, i] + sum(
                    self.gamma[u, i, r] * self.theta[u, r, m] * self.FLOW_IN[u, m]
                    for r in self.R
                    for m in self.M
                )
            else:
                return self.FLOW_OUT[u, i] == self.FLOW_IN[u, i]

        def MassBalance_9_rule(self, u, i):
            return self.FLOW_WASTE[u, i] == self.FLOW_OUT[u, i] - sum(
                self.FLOW[u, uu, i] for uu in self.UU if (u,uu) in self.U_CONNECTORS
            )

        def MassBalance_10_rule(self, i):
            return self.FLOW_WASTE_TOTAL[i] == sum(
                self.FLOW_WASTE[u, i] for u in self.U
            )

        # concentration constraints
        def MassBalance_11_rule(self, u):
            if self.kappa_2_lhs_conc[u] == 0 and self.kappa_2_rhs_conc[u] == 0:
                return 1e03 * sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I
                ) == 1e03 * self.conc[u] * sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I
                )
            elif self.kappa_2_lhs_conc[u] == 0 and self.kappa_2_rhs_conc[u] == 1:
                return 1e03 * sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I
                ) == 1e03 * self.conc[u] * sum(
                    self.FLOW_IN[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I
                )
            elif self.kappa_2_lhs_conc[u] == 1 and self.kappa_2_rhs_conc[u] == 0:
                return (1e03 * sum(
                        self.FLOW_IN[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I)
                        == 1e03 * self.conc[u] * sum(
                        self.FLOW_OUT[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I
                ))
            elif self.kappa_2_lhs_conc[u] == 1 and self.kappa_2_rhs_conc[u] == 1:
                return 1e03 * sum(self.FLOW_IN[u, i] * self.kappa_1_lhs_conc[u, i] for i in self.I ) == 1e03 * self.conc[u] * sum(self.FLOW_IN[u, i] * self.kappa_1_rhs_conc[u, i] for i in self.I)
            else:
                return Constraint.Skip

        def MassBalance_12_rule(self, u):
            return self.FLOW_SUM[u] == sum(self.FLOW_IN[u, i] for i in self.I)

        # min max production constraints for product pools
        def MassBalance_14a_rule(self, up):
            # bounds defined in tons per year (t/a) hence flow times full loading hours
            return self.FLOW_SUM[up] >= self.MinProduction[up]

        def MassBalance_14b_rule(self, up):
            # bounds defined in tons per year (t/a) hence flow times full loading hours
            return self.FLOW_SUM[up] <= self.MaxProduction[up]

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

        # Distributor Equations

        def MassBalance_15a_rule(self, u, uu, uk, k, i):
            return self.FLOW_DIST[u, uu, uk, k, i] <= self.Decimal_numbers[
                u, k
            ] * self.FLOW_OUT[u, i] + self.alpha[u] * (1 - self.Y_DIST[u, uu, uk, k])

        def MassBalance_15b_rule(self, u, uu, uk, k, i):
            return self.FLOW_DIST[u, uu, uk, k, i] >= self.Decimal_numbers[
                u, k
            ] * self.FLOW_OUT[u, i] - self.alpha[u] * (1 - self.Y_DIST[u, uu, uk, k])

        def MassBalance_15c_rule(self, u, uu, uk, k, i):
            return (
                self.FLOW_DIST[u, uu, uk, k, i]
                <= self.alpha[u] * self.Y_DIST[u, uu, uk, k]
            )

        def MassBalance_16_rule(self, u, i):
            return self.FLOW_OUT[u, i] == sum(
                self.FLOW[u, uu, i] for uu in self.U if (u, uu) in self.U_DIST_SUB
            )

        def MassBalance_17_rule(self, u, uu):
            return self.FLOW_FT[u, uu] == sum(self.FLOW[u, uu, i] for i in self.I)


        def MassBalance_Distribution_Factor(self, u, uu):
            return self.DistFraction[u, uu] == sum(self.Decimal_numbers[u, k] * self.Y_DIST[u, uu, u, k]
                                                   for u1, k in self.DC_SET if u == u1)


        self.MassBalance_1 = Constraint(self.U, self.I, rule=MassBalance_1_rule)
        self.MassBalance_2 = Constraint(self.U, self.I, rule=MassBalance_2_rule)
        self.MassBalance_3 = Constraint(self.U_SU, rule=MassBalance_3_rule)
        self.MassBalance_4 = Constraint(self.U_S, rule=MassBalance_4_rule)
        self.MassBalance_13 = Constraint(self.U_S, rule=MassBalance_13_rule)
        self.MassBalance_14 = Constraint(self.U_S, rule=MassBalance_14_rule)
        #self.MassBalance_15 = Constraint(rule=MassBalance_15_rule)

        self.MassBalance_5 = Constraint(self.U, self.I, rule=MassBalance_5_rule)
        self.MassBalance_6 = Constraint(self.U, self.UU, self.I, rule=MassBalance_6_rule)
        self.MassBalance_7 = Constraint(self.U, self.UU, self.I, rule=MassBalance_7_rule)
        self.MassBalance_8 = Constraint(self.U, self.UU, self.I, rule=MassBalance_8_rule)
        self.MassBalance_9 = Constraint(self.U, self.I, rule=MassBalance_9_rule)
        self.MassBalance_10 = Constraint(self.I, rule=MassBalance_10_rule)
        self.MassBalance_11 = Constraint(self.U, rule=MassBalance_11_rule)
        self.MassBalance_12 = Constraint(self.U, rule=MassBalance_12_rule)
        self.MassBalance_14a = Constraint(self.U_PP, rule=MassBalance_14a_rule)
        self.MassBalance_14b = Constraint(self.U_PP, rule=MassBalance_14b_rule)
        self.MassBalance_15a = Constraint(
            self.U_DIST_SUB2, self.I, rule=MassBalance_15a_rule
        )
        self.MassBalance_15b = Constraint(
            self.U_DIST_SUB2, self.I, rule=MassBalance_15b_rule
        )
        self.MassBalance_15c = Constraint(
            self.U_DIST_SUB2, self.I, rule=MassBalance_15c_rule
        )
        self.MassBalance_16 = Constraint(self.U_DIST, self.I, rule=MassBalance_16_rule)
        self.MassBalance_17 = Constraint(self.U_CONNECTORS, rule=MassBalance_17_rule)

        # Calculates the fractions that go to each stream
        self.Distribution_Equations = Constraint(self.U_DIST_SUB, rule=MassBalance_Distribution_Factor)


    # **** ENERGY BALANCES *****
    # -------------------------

    def create_EnergyBalances(self):
        """
        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general Energy Balances (eg. TAU, REF_FLOW...).
        Afterwards Energy Balance‚ Equations are written as PYOMO Constraints.

        """

        # Parameter
        # ---------

        # Energy demand (El, Heating/Cooling, Interval H and C)
        self.tau = Param(self.U, self.UT, initialize=0, within=Any, mutable=True)
        self.tau_h = Param(self.H_UT, self.U, initialize=0, mutable=True)
        self.tau_c = Param(self.H_UT, self.U, initialize=0, mutable=True)
        self.beta = Param(self.U, self.H_UT, self.HI, initialize=0, mutable=True)

        # Slack Parameters (Flow Choice, HEN, Upper bounds)
        self.kappa_1_ut = Param(self.U, self.UT, self.I, initialize=0)
        self.kappa_2_ut = Param(self.U, self.UT, initialize=3)
        self.kappa_3_heat = Param(self.U, self.HI, initialize=0)
        self.kappa_3_heat2 = Param(self.U, self.HI, initialize=0)
        self.alpha_hex = Param(initialize=100000)

        self.Y_HEX = Var(self.HI, within=Binary)

        # Additional unit operations (Heat Pump, EL / Heat Generator)
        self.COP_HP = Param(initialize=0, mutable=True)
        self.Efficiency_TUR = Param(self.U_TUR, initialize=0, mutable=True)
        self.Efficiency_FUR = Param(self.U_FUR, initialize=0, mutable=True)
        self.LHV = Param(self.I, initialize=0, mutable=True)
        self.H = Param()

        # Variables
        # ---------

        # Reference Flows for Demand calculation
        self.REF_FLOW_UT = Var(self.U, self.UT)

        # Electricity Demand and Production, Heat Pump

        self.ENERGY_DEMAND = Var(self.U, self.U_UT)
        self.ENERGY_DEMAND_TOT = Var(self.U_UT)
        self.EL_PROD_1 = Var(self.U_TUR, within=NonNegativeReals)
        self.ENERGY_DEMAND_HP_EL = Var(within=NonNegativeReals)

        # Heating and cooling demand (Interval, Unit, Resi, Defi, Cooling, Exchange, Production , HP)
        self.ENERGY_DEMAND_HEAT = Var(self.U, self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_COOL = Var(self.U, self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_UNIT = Var(self.U, within=NonNegativeReals)
        self.ENERGY_DEMAND_COOL_UNIT = Var(self.U, within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_RESI = Var(self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_DEFI = Var(self.HI, within=NonNegativeReals)
        self.ENERGY_DEMAND_COOLING = Var(within=NonNegativeReals)
        self.ENERGY_EXCHANGE = Var(self.HI, within=NonNegativeReals)
        self.EXCHANGE_TOT = Var()
        self.ENERGY_DEMAND_HEAT_PROD_USE = Var(within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_PROD_SELL = Var(within=NonNegativeReals)
        self.ENERGY_DEMAND_HEAT_PROD = Var(self.U_FUR, within=NonNegativeReals)
        self.ENERGY_DEMAND_HP = Var(within=NonNegativeReals)
        self.ENERGY_DEMAND_HP_USE = Var(within=NonNegativeReals)

        self.MW = Param(self.I, initialize=1, mutable=True)
        self.CP = Param(self.I, initialize=0, mutable=True)

        # Constraints
        # -----------

        # Utilities other than heating and cooling

        def UtilityBalance_1_rule(self, u, ut):
            if self.kappa_2_ut[u, ut] == 1:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_IN[u, i] * self.kappa_1_ut[u, ut, i] for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 0:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_OUT[u, i] * self.kappa_1_ut[u, ut, i] for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 4:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_OUT[u, i] / self.MW[i] * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 2:
                return self.REF_FLOW_UT[u, ut] == sum(
                    self.FLOW_IN[u, i] / self.MW[i] * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 5:
                return self.REF_FLOW_UT[u, ut] == sum(
                    0.000277   # MWh/MJ conversion factor (1/3600) => uc parameter in thesis Phiilpp Kenkel
                    * self.CP[i]
                    * self.FLOW_IN[u, i]
                    * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            elif self.kappa_2_ut[u, ut] == 6:
                return self.REF_FLOW_UT[u, ut] == sum(
                    0.000277
                    * self.CP[i]
                    * self.FLOW_OUT[u, i]
                    * self.kappa_1_ut[u, ut, i]
                    for i in self.I
                )
            else:
                return self.REF_FLOW_UT[u, ut] == 0

        def UtilityBalance_2_rule(self, u, ut):
            return (self.ENERGY_DEMAND[u, ut] == self.REF_FLOW_UT[u, ut] * self.tau[u, ut])

        def UtilityBalance_3_rule(self, ut):
            if ut == "Electricity":  # in MWh !!
                return self.ENERGY_DEMAND_TOT[ut] == sum(
                    self.ENERGY_DEMAND[u, ut] * self.flh[u] for u in self.U
                ) - sum(self.EL_PROD_1[u] * self.flh[u] for u in self.U_TUR)
            else: # for chilling
                return self.ENERGY_DEMAND_TOT[ut] == sum(
                    self.ENERGY_DEMAND[u, ut] * self.flh[u] for u in self.U
                )

        # Electrictiy Balance for Production from Turbines

        def ElectricityBalance_1_rule(self, u):
            # in MW
            return self.EL_PROD_1[u] == self.Efficiency_TUR[u] * sum(self.LHV[i] * self.FLOW_IN[u, i] for i in self.I)

        self.ElectricityBalance_1 = Constraint(
            self.U_TUR, rule=ElectricityBalance_1_rule
        )
        self.UtilityBalance_1 = Constraint(self.U, self.UT, rule=UtilityBalance_1_rule)
        self.UtilityBalance_2 = Constraint(
            self.U, self.U_UT, rule=UtilityBalance_2_rule
        )
        self.UtilityBalance_3 = Constraint(self.U_UT, rule=UtilityBalance_3_rule)

        # Heat and Cooling Balance (Demand)
        # fixme: Energy and cooling demand got mixed up, but are correctly implemented in the code
        #  (where heat should be, cooling is used and visa versa. Not great for readability!! sloppy
        def HeatBalance_1_rule(self, u, hi):
            return self.ENERGY_DEMAND_HEAT[u, hi] == sum(
                self.beta[u, ut, hi] * self.tau_c[ut, u] * self.REF_FLOW_UT[u, ut]
                for ut in self.H_UT
            )

        def HeatBalance_2_rule(self, u, hi):
            return self.ENERGY_DEMAND_COOL[u, hi] == sum(
                self.beta[u, ut, hi] * self.tau_h[ut, u] * self.REF_FLOW_UT[u, ut]
                for ut in self.H_UT
            )

        # Heating anc Cooling Balance (Either with or without Heat pump)
        # Rigorous HEN Optimization approach

        if self.heat_pump_options["active"] is True:
            hp_tin = self.heat_pump_options["t_in"]
            hp_tout = self.heat_pump_options["t_out"]

            def HeatBalance_3_rule(self, u, hi):
                k = len(self.HI)
                if hi == 1:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_PROD_USE
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                elif hi == hp_tin:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        - self.ENERGY_DEMAND_HP
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                elif hi == k:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_DEMAND_COOLING
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                else:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        == 0
                    )

            def HeatBalance_4_rule(self, u, hi):
                if hi == 1:
                    return (
                        sum(
                            self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                        == 0
                    )
                elif hi == hp_tout:
                    return (
                        sum(
                            self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HP_USE
                        == 0
                    )
                else:
                    return (
                        sum(
                            self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                        == 0
                    )

            def HeatBalance_8_rule(self):
                return self.ENERGY_DEMAND_HP_USE == self.ENERGY_DEMAND_HP / (
                    1 - (1 / self.COP_HP)
                )

            def HeatBalance_9_rule(self):
                return self.ENERGY_DEMAND_HP_EL == self.ENERGY_DEMAND_HP / (
                    self.COP_HP - 1
                )

            self.HeatBalance_8 = Constraint(rule=HeatBalance_8_rule)
            self.HeatBalance_9 = Constraint(rule=HeatBalance_9_rule)

        else:
            def HeatBalance_3_rule(self, u, hi):
                k = len(self.HI)
                if hi == 1:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_PROD_USE
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                elif hi == k:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_DEMAND_COOLING
                        - self.ENERGY_EXCHANGE[hi]
                        == 0
                    )
                else:
                    return (
                        sum(
                            self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                            for u in self.U
                        )
                        + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                        - self.ENERGY_EXCHANGE[hi]
                        - self.ENERGY_DEMAND_HEAT_RESI[hi]
                        == 0
                    )

            def HeatBalance_4_rule(self, u, hi):
                return (
                    sum(
                        self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H
                        for u in self.U
                    )
                    - self.ENERGY_EXCHANGE[hi]
                    - self.ENERGY_DEMAND_HEAT_DEFI[hi]
                    == 0
                )

            def HeatBalance_8_rule(self):
                return self.ENERGY_DEMAND_HP_USE == 0

            def HeatBalance_9_rule(self):
                return self.ENERGY_DEMAND_HP_EL == 0

            self.HeatBalance_8 = Constraint(rule=HeatBalance_8_rule)
            self.HeatBalance_9 = Constraint(rule=HeatBalance_9_rule)

        #  Exchange Constraints, Production and Sell etc.
        def HeatBalance_5_rule(self, hi):
            return self.ENERGY_EXCHANGE[hi] <= sum(
                self.ENERGY_DEMAND_COOL[u, hi] * self.flh[u] / self.H for u in self.U
            )

        def HeatBalance_6_rule(self, hi):
            if hi == 1:
                return (
                    self.ENERGY_EXCHANGE[hi]
                    <= sum(
                        self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                        for u in self.U
                    )
                    + self.ENERGY_DEMAND_HEAT_PROD_USE
                )
            else:
                return (
                    self.ENERGY_EXCHANGE[hi]
                    <= sum(
                        self.ENERGY_DEMAND_HEAT[u, hi] * self.flh[u] / self.H
                        for u in self.U
                    )
                    + self.ENERGY_DEMAND_HEAT_RESI[hi - 1]
                )

        def HeatBalance_7_rule(self):
            return self.EXCHANGE_TOT == sum(self.ENERGY_EXCHANGE[hi] for hi in self.HI)

        def HeatBalance_12_rule(self, hi):
            return self.ENERGY_EXCHANGE[hi] <= self.Y_HEX[hi] * self.alpha_hex

        def HeatBalance_13_rule(self, u):
            return self.ENERGY_DEMAND_HEAT_PROD[u] == self.Efficiency_FUR[u] * sum(
                self.LHV[i] * self.FLOW_IN[u, i] for i in self.I)

        def HeatBalance_14_rule(self, u):
            return self.ENERGY_DEMAND_HEAT_UNIT[u] == sum(
                self.ENERGY_DEMAND_COOL[u, hi] for hi in self.HI
            ) * self.flh[u] / self.H

        def HeatBalance_15_rule(self, u):
            return self.ENERGY_DEMAND_COOL_UNIT[u] == sum(
                self.ENERGY_DEMAND_HEAT[u, hi] for hi in self.HI
            ) * self.flh[u] / self.H

        def HeatBalance_16_rule(self):
            return (
                self.ENERGY_DEMAND_HEAT_PROD_USE
                == sum(
                    self.ENERGY_DEMAND_HEAT_PROD[u] * self.flh[u] / self.H
                    for u in self.U_FUR
                )
                - self.ENERGY_DEMAND_HEAT_PROD_SELL
            )

        self.HeatBalance_1 = Constraint(self.U, self.HI, rule=HeatBalance_1_rule)
        self.HeatBalance_2 = Constraint(self.U, self.HI, rule=HeatBalance_2_rule)
        self.HeatBalance_3 = Constraint(self.U, self.HI, rule=HeatBalance_3_rule)
        self.HeatBalance_4 = Constraint(self.U, self.HI, rule=HeatBalance_4_rule)
        self.HeatBalance_5 = Constraint(self.HI, rule=HeatBalance_5_rule)
        self.HeatBalance_6 = Constraint(self.HI, rule=HeatBalance_6_rule)
        self.HeatBalance_7 = Constraint(rule=HeatBalance_7_rule)

        self.HeatBalance_12 = Constraint(self.HI, rule=HeatBalance_12_rule)
        self.HeatBalance_13 = Constraint(self.U_FUR, rule=HeatBalance_13_rule)
        self.HeatBalance_14 = Constraint(self.U, rule=HeatBalance_14_rule)
        self.HeatBalance_15 = Constraint(self.U, rule=HeatBalance_15_rule)
        self.HeatBalance_16 = Constraint(rule=HeatBalance_16_rule)

        ### extra constraints to print out the energy and heat demand for each unit
        # elec
        self.ELECTRICITY_PRODUCED = Var()
        self.TOTAL_ELECTRICITY_DEMAND = Var()
        # heat
        self.TOTAL_HEAT_DEMAND = Var()
        self.TOTAL_COOLING_DEMAND = Var()
        self.TOTAL_HEAT_PRODUCED = Var()
        self.ENERGY_DEMAND_DEFICIT = Var()
        self.ENERGY_DEMAND_RESIDUAL = Var()

        def Total_Electricity_Demand(self):
            return self.TOTAL_ELECTRICITY_DEMAND == sum(self.ENERGY_DEMAND[u, "Electricity"] for u in self.U)

        def UtilityBalance_Produced_electricity(self):
            return self.ELECTRICITY_PRODUCED == sum(self.EL_PROD_1[u] for u in self.U_TUR)

        # Total heat demand

        def Heat_demand_total(self):
            return self.TOTAL_HEAT_DEMAND == sum(self.ENERGY_DEMAND_HEAT_UNIT[u] for u in self.U)

        def Cooling_demand_total(self):
            return self.TOTAL_COOLING_DEMAND == sum(self.ENERGY_DEMAND_COOL_UNIT[u] for u in self.U)

        def HeatBalance_deficit_heat(self):
            return self.ENERGY_DEMAND_DEFICIT == sum(self.ENERGY_DEMAND_HEAT_DEFI[hi]  for hi in self.HI)

        def HeatBalance_residual_heat(self):
            return self.ENERGY_DEMAND_RESIDUAL == sum(self.ENERGY_DEMAND_HEAT_RESI[hi]  for hi in self.HI)

        def Total_heat_production(self):
            return self.TOTAL_HEAT_PRODUCED == sum(self.ENERGY_DEMAND_HEAT_PROD[u] for u in self.U_FUR)

        # add to constraints
        self.Total_Electricity_Demand = Constraint(rule=Total_Electricity_Demand)
        self.UtilityBalance_Produced_electricity = Constraint(rule=UtilityBalance_Produced_electricity)

        self.Heat_Demand_Total = Constraint(rule=Heat_demand_total)
        self.Cooling_Demand_Total = Constraint(rule=Cooling_demand_total)
        self.HeatBalance_Deficit_Heat = Constraint(rule=HeatBalance_deficit_heat)
        self.HeatBalance_Residual_Heat = Constraint(rule=HeatBalance_residual_heat)
        self.Total_heat_production = Constraint(rule=Total_heat_production)

    # *** Waste Costs ****
    # --------------------
    def create_WasteCosts(self):

        # set parameters
        # initial_waste_cost_factors = {
        #     "Incineration": 0,
        #     "Landfill": 0,
        #     "WWTP": 0
        # }
        self.waste_cost_factor = Param(self.WASTE_MANAGEMENT_TYPES, initialize=0, mutable=True)
        self.waste_type_U = Param(self.U, initialize='Landfill', mutable=True, within=Any)

        # set variables
        self.WASTE_COST_U = Var(self.U, within=NonNegativeReals)
        self.WASTE_COST_TOT = Var(within=NonNegativeReals)

        def Cost_Waste_rule(self, u):
            wasteType = self.waste_type_U[u].value
            return (self.WASTE_COST_U[u] == self.flh[u] *   # units WASTE_COST = k€/year
                    sum(self.FLOW_WASTE[u, i] for i in self.I) * self.waste_cost_factor[wasteType])

        def Cost_Waste_TOT(self):
            return self.WASTE_COST_TOT == sum(self.WASTE_COST_U[u] for u in self.U)/1000

        # add constraints
        self.Cost_Waste = Constraint(self.U, rule=Cost_Waste_rule)
        self.Cost_Waste_TOT = Constraint(rule=Cost_Waste_TOT)

    # **** COST BALANCES ****
    # -------------------------

    def create_EconomicEvaluation(self):
        """
        Description
        -------
        This method creates the PYOMO parameters and variables
        that are necessary for the general Cost Calculation (eg. detla_ut, COST_UT etc.).
        Afterward Cost calculation equations are written as PYOMO Constraints.
        """

        # Parameter
        # ---------

        # Specific costs (Utility, raw materials, Product prices)

        self.delta_ut = Param(self.U_UT, initialize=0, mutable=True)
        self.delta_q = Param(self.HI, initialize=30, mutable=True)
        self.delta_cool = Param(initialize=15, mutable=True)
        self.ProductPrice = Param(self.U_PP, initialize=0, mutable=True)

        # Cost factors (CAPEX, Heat Pump)
        self.DC = Param(self.U, initialize=0, mutable=True)
        self.IDC = Param(self.U, initialize=0, mutable=True)
        self.ACC_Factor = Param(self.U, initialize=0, mutable=True)

        self.HP_ACC_Factor = Param(initialize=1, mutable=True)
        self.HP_Costs = Param(initialize=1, mutable=True)

        # Piecewise Linear CAPEX
        self.lin_CAPEX_x = Param(self.U_C, self.J, initialize=0)
        self.lin_CAPEX_y = Param(self.U_C, self.J, initialize=0)
        self.kappa_1_capex = Param(self.U_C, self.I, initialize=0)
        self.kappa_2_capex = Param(self.U_C, initialize=5)

        # OPEX factors

        self.K_OM = Param(self.U_C, initialize=0.04, mutable=True)

        # Variables
        # ---------

        # Utilitiy Costs ( El, Heat, El-TOT, HEN)
        self.ENERGY_COST = Var(self.U_UT)
        self.COST_HEAT = Var(self.HI, initialize=0)
        self.COST_UT = Var(initialize=0)
        self.ELCOST = Var()
        self.HEATCOST = Var(self.HI)
        self.C_TOT = Var()
        self.HENCOST = Var(self.HI, within=NonNegativeReals)
        self.UtCosts = Var()

        ##      Piece-Wise Linear CAPEX
        # Total reference flow used for CAPEX sizing
        self.REF_FLOW_CAPEX = Var(self.U_C, within=NonNegativeReals)

        # Maximum reference flow allowed per physical parallel unit
        self.upperFlowLimitUnit = Param(self.U_C, initialize=1e12, mutable=True)

        # Maximum number of parallel units allowed
        self.N_CAPEX = RangeSet(1, 5)

        # Binary: whether parallel unit n of technology u exists
        self.Y_PARALLEL_UNIT = Var(self.U_C, self.N_CAPEX, within=Binary)

        # Reference flow assigned to each parallel unit
        self.REF_FLOW_CAPEX_UNIT = Var(self.U_C, self.N_CAPEX,within=NonNegativeReals)

        # Equipment cost of each parallel unit
        self.EC_UNIT = Var(self.U_C,self.N_CAPEX,within=NonNegativeReals)

        # Total equipment cost over all parallel units
        self.EC = Var(self.U_C, within=NonNegativeReals)

        # Fixed capital investment
        self.FCI = Var(self.U_C, within=NonNegativeReals)

        # Piecewise CAPEX variables per parallel unit
        self.lin_CAPEX_s = Var(self.U_C, self.N_CAPEX, self.JI, bounds=(0, 1))
        self.lin_CAPEX_z = Var(self.U_C, self.N_CAPEX, self.JI, within=Binary)
        self.lin_CAPEX_lambda = Var(self.U_C, self.N_CAPEX, self.J, bounds=(0, 1))


        self.ACC = Var(self.U_C, within=NonNegativeReals)
        self.to_acc = Param(self.U_C, initialize=0, mutable=True)
        self.TO_CAPEX = Var(self.U_C, within=NonNegativeReals)
        self.TO_CAPEX_TOT = Var(within=NonNegativeReals)
        self.ACC_HP = Var(within=NonNegativeReals)
        self.TAC = Var()
        self.CAPEX = Var()

        # OPEX (Raw Materials, O&M, , UtilitiesTotal, Profits)
        # self.RM_COST = Var(self.U_C, within=NonNegativeReals) #not used
        self.RM_COST_TOT = Var()  # Var(within=NonNegativeReals) # can also be negative, e.g. gate fees for handeling waste
        self.M_COST = Var(self.U_C)
        self.M_COST_TOT = Var(within=NonNegativeReals)
        # self.O_H = Var()  # doesn't seem to be used
        # self.O_COST = Var()  # doesn't seem to be used
        # self.OM_COST = Var(within=NonNegativeReals)  # doesn't seem to be used
        self.OPEX = Var()
        self.PROFITS = Var(self.U_PP)
        self.PROFITS_TOT = Var()

        # Constraints
        # -----------

        # CAPEX Calculation (Reference Flow, Piece-Wise linear Lambda Constraints)

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

        # total flow = flow through unit 1 + flow through unit 2 + ...
        def CapexParallel_1_rule(self, u):
            return self.REF_FLOW_CAPEX[u] == sum(
                self.REF_FLOW_CAPEX_UNIT[u, n]
                for n in self.N_CAPEX
            )

        # flow through that parallel unit <= upperFlowLimitUnit
        def CapexParallel_2_rule(self, u, n):
            return (
                self.REF_FLOW_CAPEX_UNIT[u, n]
                <= self.upperFlowLimitUnit[u] * self.Y_PARALLEL_UNIT[u, n]
            )

        # a minimum loading / ordering constraint so that earlier units are filled before later units.
        def CapexParallel_FillOrder_rule(self, u, n):
            if n == max(self.N_CAPEX):
                return Constraint.Skip

            return (
                self.REF_FLOW_CAPEX_UNIT[u, n]
                >= self.upperFlowLimitUnit[u] * self.Y_PARALLEL_UNIT[u, n + 1]
            )

        # This avoids strange solutions where unit 3 is active but unit 1 is inactive.
        def CapexParallel_3_rule(self, u, n):
            if n == max(self.N_CAPEX):
                return Constraint.Skip

            return self.Y_PARALLEL_UNIT[u, n] >= self.Y_PARALLEL_UNIT[u, n + 1]

        def CapexEquation_2_rule(self, u, n):
            return (
                sum(
                    self.lin_CAPEX_x[u, j] * self.lin_CAPEX_lambda[u, n, j]
                    for j in self.J
                )
                == self.REF_FLOW_CAPEX_UNIT[u, n]
            )

        def CapexEquation_3_rule(self, u, n):
            return self.EC_UNIT[u, n] == sum(
                self.lin_CAPEX_y[u, j] * self.lin_CAPEX_lambda[u, n, j]
                for j in self.J
            )

        def CapexEquation_4_rule(self, u, n):
            return sum(
                self.lin_CAPEX_z[u, n, j]
                for j in self.JI
            ) == self.Y_PARALLEL_UNIT[u, n]

        def CapexEquation_5_rule(self, u, n, j):
            return self.lin_CAPEX_s[u, n, j] <= self.lin_CAPEX_z[u, n, j]

        def CapexEquation_6_rule(self, u, n, j):
            if j == 1:
                return (
                    self.lin_CAPEX_lambda[u, n, j]
                    == self.lin_CAPEX_z[u, n, j] - self.lin_CAPEX_s[u, n, j]
                )

            elif j == len(self.J):
                return (
                    self.lin_CAPEX_lambda[u, n, j]
                    == self.lin_CAPEX_s[u, n, j - 1]
                )

            else:
                return (
                    self.lin_CAPEX_lambda[u, n, j]
                    == self.lin_CAPEX_z[u, n, j]
                    - self.lin_CAPEX_s[u, n, j]
                    + self.lin_CAPEX_s[u, n, j - 1]
                )

        # sum over all the parallel units, to get the total equipment cost for that technology
        def CapexEquation_EC_Total_rule(self, u):
            return self.EC[u] == sum(
                self.EC_UNIT[u, n]
                for n in self.N_CAPEX
            )

        # Fixed Capital investment, Annual capital costs, Heat Pump, Returning costs, Total
        def CapexEquation_7_rule(self, u):
            return self.FCI[u] == self.EC[u] * (1 + self.DC[u] + self.IDC[u])

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

        # reoccurring costs of equipment
        # --------------------------------
        def CapexEquation_11_rule(self, u):
            return self.TO_CAPEX[u] == self.to_acc[u] * self.EC[u]

        def CapexEquation_12_rule(self):
            return self.TO_CAPEX_TOT == sum(self.TO_CAPEX[u] for u in self.U_C)

        # --------------------------------
        # The three equations below are for the Heat Exchange (HEN) CAPITAL COSTS (CAPEX)
        # not related to the operating costs of HEN, COST-HEN IN k€ !!!! /1000 to get into M€
        # --------------------------------------------------------------------
        def HEN_CostBalance_4_rule(self, hi):
            return self.HENCOST[hi] <= 13.459 * self.ENERGY_EXCHANGE[
                hi
            ] + 3.3893 + self.alpha_hex * (1 - self.Y_HEX[hi])
        def HEN_CostBalance_4b_rule(self, hi):
            return self.HENCOST[hi] >= 13.459 * self.ENERGY_EXCHANGE[
                hi
            ] + 3.3893 - self.alpha_hex * (1 - self.Y_HEX[hi])
        def HEN_CostBalance_4c_rule(self, hi):
            return self.HENCOST[hi] <= self.Y_HEX[hi] * self.alpha_hex
        # --------------------------------------------------------------------

        def CapexEquation_10_rule(self):
            return (
                self.CAPEX
                == sum(self.ACC[u] for u in self.U_C)      # annual capital costs
                + self.ACC_HP/1000                         # heat pump capital costs
                + self.TO_CAPEX_TOT                        # reoccurring costs of equipment
                + sum(self.HENCOST[hi] for hi in self.HI)/1000  # HEN capital costs
            )

        self.CapexEquation_1 = Constraint(
            self.U_C,
            rule=CapexEquation_1_rule
        )

        self.CapexParallel_1 = Constraint(
            self.U_C,
            rule=CapexParallel_1_rule
        )

        self.CapexParallel_2 = Constraint(
            self.U_C,
            self.N_CAPEX,
            rule=CapexParallel_2_rule
        )

        self.CapexParallel_3 = Constraint(
            self.U_C,
            self.N_CAPEX,
            rule=CapexParallel_3_rule
        )

        self.CapexEquation_2 = Constraint(self.U_C, self.N_CAPEX, rule=CapexEquation_2_rule)
        self.CapexEquation_filling = Constraint(self.U_C, self.N_CAPEX, rule= CapexParallel_FillOrder_rule)
        self.CapexEquation_3 = Constraint(self.U_C, self.N_CAPEX,rule=CapexEquation_3_rule)
        self.CapexEquation_4 = Constraint(self.U_C, self.N_CAPEX, rule=CapexEquation_4_rule)
        self.CapexEquation_5 = Constraint( self.U_C, self.N_CAPEX, self.JI, rule=CapexEquation_5_rule)
        self.CapexEquation_6 = Constraint(self.U_C,self.N_CAPEX, self.J, rule=CapexEquation_6_rule)
        self.CapexEquation_EC_Total = Constraint( self.U_C, rule=CapexEquation_EC_Total_rule)
        self.CapexEquation_7 = Constraint(self.U_C, rule=CapexEquation_7_rule)


        self.CapexEquation_8 = Constraint(self.U_C, rule=CapexEquation_8_rule)
        self.CapexEquation_9 = Constraint(rule=CapexEquation_9_rule)

        self.HEN_CostBalance_4 = Constraint(self.HI, rule=HEN_CostBalance_4_rule)
        self.HEN_CostBalance_4b = Constraint(self.HI, rule=HEN_CostBalance_4b_rule)
        self.HEN_CostBalance_4c = Constraint(self.HI, rule=HEN_CostBalance_4c_rule)

        self.CapexEquation_10 = Constraint(rule=CapexEquation_10_rule)
        self.CapexEquation_11 = Constraint(self.U_C, rule=CapexEquation_11_rule)
        self.CapexEquation_12 = Constraint(rule=CapexEquation_12_rule)

        # OPEX Calculation (HEN Costs: Heating / Cooling, CAPEX)

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
                == self.ENERGY_DEMAND_HP_EL
                * self.delta_ut["Electricity"]
                * self.H
                / 1000
            )

        # selling buying of energy see UtCosts (HEN_CostBalance_2_rule)
        def HEN_CostBalance_6_rule(self):
            return self.C_TOT == self.UtCosts/1000


        self.HEN_CostBalance_1 = Constraint(self.HI, rule=HEN_CostBalance_1_rule)
        self.HEN_CostBalance_2 = Constraint(rule=HEN_CostBalance_2_rule)
        self.HEN_CostBalance_3 = Constraint(rule=HEN_CostBalance_3_rule)
        self.HEN_CostBalance_6 = Constraint(rule=HEN_CostBalance_6_rule)

        # Utility Costs (Electricity/Chilling)

        def Ut_CostBalance_1_rule(self, ut):
            return (
                self.ENERGY_COST[ut]
                == self.ENERGY_DEMAND_TOT[ut] * self.delta_ut[ut] / 1000 # euro to million euro conversion
            )

        self.Ut_CostBalance_1 = Constraint(self.U_UT, rule=Ut_CostBalance_1_rule)

        # Raw Materials and Operating and Maintenance

        def RM_CostBalance_1_rule(self):
            return self.RM_COST_TOT == sum(
                self.materialcosts[u_s] * self.FLOW_SOURCE[u_s] * self.flh[u_s] / 1000 # euro to million euro conversion
                for u_s in self.U_S
            )

        def OM_CostBalance_1_rule(self, u):
            return self.M_COST[u] == self.K_OM[u] * self.FCI[u] # in million euro (M€)

        def OM_CostBalance_2_rule(self):
            return self.M_COST_TOT == sum(self.M_COST[u] for u in self.U_C)

        # Total OPEX
        def Opex_1_rule(self): # im M€ (million euro)
            return (
                self.OPEX
                == self.M_COST_TOT                                 # operating and maintenance costs
                + self.RM_COST_TOT/1000                                 # raw material costs
                + sum(self.ENERGY_COST[ut] for ut in self.U_UT)/1000    # utility costs energy
                + self.C_TOT/1000                                    # selling or buying of energy (from HEN)
                + self.ELCOST/1000                                      # electricity costs for heat pump
                + self.WASTE_COST_TOT/1000                               # waste costs
            )

        self.RM_CostBalance_1 = Constraint(rule=RM_CostBalance_1_rule)
        self.OM_CostBalance_1 = Constraint(self.U_C, rule=OM_CostBalance_1_rule)
        self.OM_CostBalance_2 = Constraint(rule=OM_CostBalance_2_rule)
        self.OpexEquation = Constraint(rule=Opex_1_rule)

        # Profits

        def Profit_1_rule(self, u): # profit per 1000€
            return (
                self.PROFITS[u]
                == sum(self.FLOW_IN[u, i] for i in self.I) * self.ProductPrice[u] / 1000
            )

        def Profit_2_rule(self): # profit per M€ (million euro)
            return (
                self.PROFITS_TOT
                == sum(self.PROFITS[u] for u in self.U_PP) * self.H / 1000
            )

        self.ProfitEquation_1 = Constraint(self.U_PP, rule=Profit_1_rule)
        self.ProfitEquation_2 = Constraint(rule=Profit_2_rule)

        # Total Annualized Costs

        def TAC_1_rule(self):
            return self.TAC == (self.CAPEX + self.OPEX - self.PROFITS_TOT) * 1000  # waste costs are in the OPEX

        self.TAC_Equation = Constraint(rule=TAC_1_rule)


    # *** LCA EQUATIONS ***
    # ------------------------
    def create_LCAEquations(self):
        """
        Description
        :return:
        """
        # start with impacts of the inflowing components
        # needs to be introduced like phi variable! look how it is passed on
        self.impact_inFlow_components = Param(self.I, self.IMPACT_CATEGORIES, initialize=0, mutable=True)
        self.IMPACT_INPUTS_U_CAT = Var(self.U, self.IMPACT_CATEGORIES)
        self.IMPACT_INPUTS_PER_CAT = Var(self.IMPACT_CATEGORIES)

        def LCA_Inflow_U_rule(self, u, ImpCat):
            return self.IMPACT_INPUTS_U_CAT[u, ImpCat] == sum(self.FLOW_ADD_TOT[u, i] * self.impact_inFlow_components[i, ImpCat] * self.flh[u]
                                                for i in self.I)
        def LCA_All_Inflow_rule(self, ImpCat):
            return (self.IMPACT_INPUTS_PER_CAT[ImpCat] == sum(self.IMPACT_INPUTS_U_CAT[u, ImpCat] for u in self.U)
                    /self.sourceOrProductLoad/1000)  # to convert to impc/KG of product or source


        self.LCA_InFlow_Units = Constraint(self.U, self.IMPACT_CATEGORIES, rule=LCA_Inflow_U_rule)
        self.LCA_InFlow_Total_Per_Catagories = Constraint(self.IMPACT_CATEGORIES, rule=LCA_All_Inflow_rule)

        # now the impacts of energy and heat consumption
        # set the parameters
        self.util_impact_factors = Param(self.UT, self.IMPACT_CATEGORIES, initialize=0, mutable=True)
        # set the variables
        self.IMPACT_UTILITIES = Var(self.UT, self.IMPACT_CATEGORIES)
        self.IMPACT_UTILITIES_PER_CAT = Var(self.IMPACT_CATEGORIES)

        # util_impact_factors['electricity'] units: kgCO2/MWh and ENERGY_DEMAND_TOTAL['electricity'] units: MW

        # set the constraints
        def LCA_Utility_rule(self, ut, impCat):
            if ut == "Electricity":  # ENERGY_DEMAND_TOT is in MWh! util_impact_factors in kg_CO2/MWh
                return (self.IMPACT_UTILITIES[ut, impCat] == (self.ENERGY_DEMAND_TOT[ut] + self.ENERGY_DEMAND_HP_EL * self.H)
                        * self.util_impact_factors[ut, impCat])
            elif ut == "Chilling":
                return self.IMPACT_UTILITIES[ut, impCat] == self.ENERGY_DEMAND_TOT[ut] * self.util_impact_factors[ut, impCat]

            elif ut == "Heat": # or ut == "Heat2": # not including heat because already included in "ENERGY_DEMAND_HEAT_DEFI"
                return (self.IMPACT_UTILITIES[ut, impCat] == self.H * self.util_impact_factors[ut, impCat] *
                        (sum(self.ENERGY_DEMAND_HEAT_DEFI[hi] for hi in self.HI) - self.ENERGY_DEMAND_HEAT_PROD_SELL))
            else:
                # skip heat 2
                return self.IMPACT_UTILITIES[ut, impCat] == 0

        def LCA_Utility_TOT_rule(self, impCat):
            return (self.IMPACT_UTILITIES_PER_CAT[impCat] == sum(self.IMPACT_UTILITIES[ut, impCat] for ut in self.UT)
                    /self.sourceOrProductLoad/1000) # to convert to impc/KG of product or source


        self.LCA_Utilities = Constraint(self.UT, self.IMPACT_CATEGORIES, rule=LCA_Utility_rule)
        self.LCA_Utilities_TOT = Constraint(self.IMPACT_CATEGORIES, rule=LCA_Utility_TOT_rule)

        # impact of waste
        # set the parameters
        self.waste_impact_fac = Param(self.WASTE_MANAGEMENT_TYPES, self.IMPACT_CATEGORIES, initialize=0, mutable=True)
        # set the variables
        self.WASTE_U = Var(self.U, self.IMPACT_CATEGORIES)
        self.IMPACT_WASTE_PER_CAT = Var(self.IMPACT_CATEGORIES)

        def LCA_Waste_rule(self, u, impCat):
            wasteType = self.waste_type_U[u].value
            return (self.WASTE_U[u, impCat] == self.flh[u] * sum(self.FLOW_WASTE[u, i] * self.waste_impact_fac[wasteType, impCat]
                                                          for i in self.I))
        def LCA_Waste_TOT_rule(self, impCat):
            return (self.IMPACT_WASTE_PER_CAT[impCat] == sum(self.WASTE_U[u, impCat] for u in self.U)
                    /self.sourceOrProductLoad/1000) # to convert to impc/KG of product or source


        self.LCA_Waste = Constraint(self.U, self.IMPACT_CATEGORIES, rule=LCA_Waste_rule)
        self.LCA_Waste_TOT = Constraint(self.IMPACT_CATEGORIES, rule=LCA_Waste_TOT_rule)

        # total impact per category: the sum of all impacts, inflow, utilities and waste
        self.IMPACT_TOT = Var(self.IMPACT_CATEGORIES)

        def LCA_Total_Impact_rule(self, impCat):
            return self.IMPACT_TOT[impCat] == (self.IMPACT_INPUTS_PER_CAT[impCat] + self.IMPACT_UTILITIES_PER_CAT[impCat]
                                               + self.IMPACT_WASTE_PER_CAT[impCat])

        self.LCA_Total_Impact = Constraint(self.IMPACT_CATEGORIES, rule=LCA_Total_Impact_rule)

    # **** DECISION MAKING EQUATIONS *****
    # -------------------------

    def create_DecisionMaking(self):
        """


        Description
        -------
        This function creates additional (optional) logic contraints of
        the flowsheet topology.

        """

        # Parameter
        # --------

        numbers = [1, 2, 3]

        # Variables
        # ---------

        # Constraints
        # -----------

        def ProcessGroup_logic_1_rule(self, u, uu):

            # this constraint is only relevant if the design is not fixed
            if self._fixedDesign:
                return Constraint.Skip

            ind = False

            for i, j in self.groups.items():

                if u in j and uu in j:
                    return self.Y[u] == self.Y[uu]
                    ind = True # what is this?? Unreachable code?

            if ind == False:
                return Constraint.Skip

        def ProcessGroup_logic_2_rule(self, u, k):

            # this constraint is only relevant if the design is not fixed
            if self._fixedDesign:
                return Constraint.Skip

            ind = False

            for i, j in self.connections.items():
                if u == i:
                    if j[k]:
                        # so only 1 connection is allowed
                        # also this currently does not work if you want your input to only go into one unit...,
                        # Might have to build that functionality in the SOURCE tab of the Excel file
                        return sum(self.Y[uu] for uu in j[k]) >= self.Y[u]
                        # ind = True

            if ind == False:
                return Constraint.Skip

        self.ProcessGroup_logic_1 = Constraint(self.U, self.UU, rule=ProcessGroup_logic_1_rule)

        self.ProcessGroup_logic_2 = Constraint(self.U, numbers, rule=ProcessGroup_logic_2_rule)


    # **** OBJECTIVE FUNCTIONS *****
    # -------------------------

    def create_ObjectiveFunction(self):
        """
        Description
        -------
        Defines the main product flow and the objetive function.

        """

        # Parameter
        # ---------

        self.ObjectiveFunctionName = Param(within=Any, initialize=self.objective_name)
        # creat a set of the objective name
        self.ObjectiveFunctionSet = Set(initialize=[self.objective_name])


        # Variables
        # ---------

        self.MainProductFlow = Var(initialize=0)

        self.NPC = Var()
        self.NPFWD = Var()
        self.NPE = Var()
        self.EBIT = Var()
        self.SumOfProductFlows = Var()

        # Constraints
        # -----------

        # Definition of Main Product and Product Load for NPC / NPE Calculation

        def SumOfProducts_rule(self):
            return self.SumOfProductFlows == sum(self.FLOW_IN[U_pp, i]
                                             for U_pp in self.U_PP
                                             for i in self.I
                                             ) * self.H

        self.SumOfProducts_Equation = Constraint(rule=SumOfProducts_rule)


        def MainProduct_1_rule(self):
            # If product driven, else skip this constraint
            if self.loadType == 'Product':
                return self.MainProductFlow == sum(self.FLOW_IN[self.loadID, i] for i in self.I) * self.H
            else:
                return Constraint.Skip

        def MainProduct_2_rule(self):
            if self.loadType == 'Product':
                return self.MainProductFlow == self.sourceOrProductLoad

            else:
                return Constraint.Skip

        self.MainProduct_Equation_1 = Constraint(rule=MainProduct_1_rule)
        self.MainProduct_Equation_2 = Constraint(rule=MainProduct_2_rule)

        # Definition of specific function

        def Specific_NPC_rule(self): # in € per year (euro/ton/year)
            # ProductLoad is 1 is substrate driven, otherwise it is the target production
            # self.TAC == (self.CAPEX + self.OPEX - self.PROFITS_TOT) * 1000
            return self.NPC == (self.TAC * 1000)/self.sourceOrProductLoad # in € per tonne of product per year (so your target production)


        def Specific_EBIT_rule(self):
            if self.loadType:  # in €/ton
                return self.EBIT == (-self.TAC * 1000) / self.sourceOrProductLoad # in M€ (million euro)
            else:   # # in Mil €
                return self.EBIT == (self.PROFITS_TOT - self.CAPEX - self.OPEX)

        self.Specific_NPC_rule = Constraint(rule=Specific_NPC_rule)
        self.Specific_EBIT_rule = Constraint(rule=Specific_EBIT_rule)

        # Definition of the used Objective Function

        if self.objective_name == "NPC":
            def Objective_rule(self):
                return self.NPC

        elif self.objective_name == "EBIT":
                def Objective_rule(self):
                    return self.EBIT

        elif self.objective_name in self.impact_categories_list:
            def Objective_rule(self, objectiveName):
                return self.IMPACT_TOT[objectiveName]

        else:
            def Objective_rule(self):
                return self.NPC


        # define the objective function and the sense of the objective function
        if self.objective_name == "EBIT":
            self.Objective = Objective(rule=Objective_rule, sense=maximize)

        elif self.objective_name in self.impact_categories_list:
            self.Objective = Objective(self.ObjectiveFunctionSet, rule=Objective_rule, sense=minimize)

        else: # want to minimise the other objective functions
            self.Objective = Objective(rule=Objective_rule, sense=minimize)

        self.objective_sense = Var(initialize=0, within=Binary)

        def objective_sense_rule1(self):
            if self.objective_name == "EBIT":
                return self.objective_sense == 1  # 1 for maximizing
            else:
                return self.objective_sense == 0  # 0 for minimizing

        self.objective_sense_rule = Constraint(rule=objective_sense_rule1)
