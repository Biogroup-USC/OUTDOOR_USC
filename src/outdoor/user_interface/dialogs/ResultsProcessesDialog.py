import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QLabel, QWidget, QTableWidget, QTabWidget, \
    QTableWidgetItem, QFormLayout

from outdoor.user_interface.data.CentralDataManager import CentralDataManager
from outdoor.user_interface.data.ProcessDTO import ProcessType


class ResultsProcessesDialog(QDialog):
    """
    Opens a dialog to set the physical processes parameters for the physical processes icon. The dialog allows the user to
    set the name, processing group, reference flow, and exponent. The user can set the reference flow and exponent as
    floating-point numbers. The processing group and name are text fields.
    """

    def __init__(self, resultsData, centralDataManager:CentralDataManager, iconID):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # Set style (existing style setup is fine and will be applied)
        # set style
        self.setStyleSheet("""
                                                          QDialog {
                                                              background-color: #f2f2f2;
                                                          }
                                                          QLabel {
                                                              color: #333333;
                                                          }
                                                          QLineEdit {
                                                              border: 1px solid #cccccc;
                                                              border-radius: 2px;
                                                              padding: 5px;
                                                              background-color: #ffffff;
                                                              selection-background-color: #b0daff;
                                                          }
                                                          QPushButton {
                                                              color: #ffffff;
                                                              background-color: #5a9;
                                                              border-style: outset;
                                                              border-width: 2px;
                                                              border-radius: 10px;
                                                              border-color: beige;
                                                              font: bold 14px;
                                                              padding: 6px;
                                                          }
                                                          QPushButton:hover {
                                                              background-color: #78d;
                                                          }
                                                          QPushButton:pressed {
                                                              background-color: #569;
                                                              border-style: inset;
                                                          }
                                                          QTableWidget {
                                                              border: 1px solid #cccccc;
                                                              selection-background-color: #b0daff;
                                                          }
                                                      """)
        self.setWindowFlags(Qt.Window)
        self.centralDataManager = centralDataManager
        self.iconID = iconID
        self.UnitType = ProcessType.PHYSICAL
        self.dialogData = resultsData.dialogData if resultsData else {}
        self.modelOutput = centralDataManager.modelOutput

        # add the tool tip text for the incoming chemicals buttons they are the same in each tab
        self.tooltipFindChemicalsButton = "These buttons will add the incoming chemicals to the table."
        self.setWindowTitle("Unit Process Parameters")
        self.setGeometry(100, 100, 600, 400)  # Adjust size as needed

        self.subtitleFont = QFont("Arial", 9, QFont.Bold)

        # initialize the separation error to be False
        self.separationErrorDict = {}

        tabWidget = QTabWidget(self)
        tabWidget.addTab(self._CAPEXresults(), "CAPEX")
        tabWidget.addTab(self._OPExResults(), "OPEX")
        tabWidget.addTab(self._massBalanceResults(), "Mass Balance")
        tabWidget.addTab(self._LCaResults(), "Env. Impact")

        # Set the tab widget as the main layout
        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(tabWidget)
        self.setLayout(mainLayout)

    def _CAPEXresults(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # Create the form layout for the general parameters
        formLayout = QFormLayout()

        # Name
        self.nameLineEdit = QLineEdit(self.dialogData.get("name", ""))
        self.nameLineEdit.setReadOnly(True)
        formLayout.addRow(QLabel("Name:"), self.nameLineEdit)

        # Extract CAPEX data from modelOutput
        try:
            if self.modelOutput and self.iconID in self.modelOutput._data.get('ACC', {}):
                # Get the total CAPEX
                totalCapex = self.modelOutput._data.get('CAPEX',0)
                CAPEXTotalLineEdit = QLineEdit(f"{round(totalCapex, 3)} M€/y")
                CAPEXTotalLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Total CAPEX:"), CAPEXTotalLineEdit)


                # CAPEX of the unit
                capexUnit = (self.modelOutput._data['ACC'][self.iconID]   # annual CAPEX from the unit itself
                             + self.modelOutput._data.get("TO_CAPEX", 0).get(self.iconID, 0)) # + reoccurring CAPEX from
                capexLineEdit = QLineEdit(f"{round(capexUnit, 3)} M€/y")
                capexLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Annual CAPEX:"), capexLineEdit)

                #share of CAPEX in total investment
                if totalCapex > 1e-6:
                    capexShare = (capexUnit / totalCapex) * 100
                    capexShareLineEdit = QLineEdit(f"{round(capexShare, 2)} %")
                    capexShareLineEdit.setReadOnly(True)
                    formLayout.addRow(QLabel("CAPEX share of total investment:"), capexShareLineEdit)

                # FCI (Fixed Capital Investment)
                fciUnit = self.modelOutput._data.get('FCI', {}).get(self.iconID, 0)
                fciLineEdit = QLineEdit(f"{round(fciUnit, 3)} M€")
                fciLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Total Fixed Capital Investment (FCI):"), fciLineEdit)

                # Additional CAPEX from other sources if available
                toCapex = self.modelOutput._data.get('TO_CAPEX', {}).get(self.iconID, 0)
                if toCapex > 1e-6:
                    toCapexLineEdit = QLineEdit(f"{round(toCapex, 3)} M€")
                    toCapexLineEdit.setReadOnly(True)
                    formLayout.addRow(QLabel("Additional CAPEX:"), toCapexLineEdit)

        except Exception as e:
            self.logger.error(f"Error extracting CAPEX data: {e}")
            emptyLabel = QLabel("No CAPEX data available")
            formLayout.addRow(emptyLabel)

        layout.addLayout(formLayout)
        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _OPExResults(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # Create the form layout for operating costs
        formLayout = QFormLayout()

        try:
            if self.modelOutput and self.iconID in self.modelOutput._data.get('U_C', []):
                # Operating and Maintenance costs
                kOm = self.modelOutput._data.get('K_OM', {}).get(self.iconID, 0)
                fci = self.modelOutput._data.get('FCI', {}).get(self.iconID, 1)
                oAndM = kOm * fci
                oAndMLineEdit = QLineEdit(f"{round(oAndM, 3)} M€/y")
                oAndMLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Operating & Maintenance:"), oAndMLineEdit)

                # Electricity consumption and cost
                electricityDemand = self.modelOutput._data.get('ENERGY_DEMAND', {}).get((self.iconID, 'Electricity'), 0) * \
                                   self.modelOutput._data.get('flh', {}).get(self.iconID, 1)  # kWh/y
                costElectricity = electricityDemand * self.modelOutput._data.get('delta_ut', {}).get('Electricity', 0)  # €/y
                elecDemandLineEdit = QLineEdit(f"{round(electricityDemand / 1e6, 3)} GWh/y")
                elecDemandLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Electricity Demand:"), elecDemandLineEdit)

                elecCostLineEdit = QLineEdit(f"{round(costElectricity / 1000, 3)} k€/y")
                elecCostLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Electricity Cost:"), elecCostLineEdit)

                # Heat demand
                heatDemand = self.modelOutput._data.get('ENERGY_DEMAND_HEAT_UNIT', {}).get(self.iconID, 0)
                heatLineEdit = QLineEdit(f"{round(heatDemand, 3)} MWh/y")
                heatLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Heat Demand:"), heatLineEdit)

                # Waste cost
                wasteCost = self.modelOutput._data.get('WASTE_COST_U', {}).get(self.iconID, 0)
                wasteCostLineEdit = QLineEdit(f"{round(wasteCost, 3)} k€/y")
                wasteCostLineEdit.setReadOnly(True)
                formLayout.addRow(QLabel("Waste Cost:"), wasteCostLineEdit)

                # Raw material flows and costs
                rawMaterialsTitle = QLabel("Raw Materials:")
                rawMaterialsTitle.setFont(self.subtitleFont)
                formLayout.addRow(rawMaterialsTitle)

                for key, flow in self.modelOutput._data.get('FLOW_ADD', {}).items():
                    if key[1] == self.iconID and flow > 1e-6:
                        inputName = self.modelOutput._data.get('Names', {}).get(key[0], f"Material {key[0]}")
                        costAddedMaterial = self.modelOutput._data.get('materialcosts', {}).get(key[0], 0) * flow

                        flowLabel = QLineEdit(f"{round(flow, 3)} t/h")
                        flowLabel.setReadOnly(True)
                        formLayout.addRow(QLabel(f"{inputName} (input):"), flowLabel)

                        costLabel = QLineEdit(f"{round(costAddedMaterial, 3)} €/y")
                        costLabel.setReadOnly(True)
                        formLayout.addRow(QLabel(f"{inputName} cost:"), costLabel)

        except Exception as e:
            self.logger.error(f"Error extracting OPEX data: {e}")
            emptyLabel = QLabel("No OPEX data available")
            formLayout.addRow(emptyLabel)

        layout.addLayout(formLayout)
        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _massBalanceResults(self):
        tab = QWidget()
        layout = QVBoxLayout()

        try:
            if self.modelOutput:
                # Create a table to display mass flows
                table = QTableWidget()
                table.setColumnCount(3)
                table.setHorizontalHeaderLabels(["Stream Type", "Source/Destination", "Flow (t/h)"])
                table.setColumnWidth(0, 150)
                table.setColumnWidth(1, 200)
                table.setColumnWidth(2, 100)

                rowCount = 0

                # Get all mass flows
                flowFt = self.modelOutput._data.get('FLOW_FT', {})
                flowAdd = self.modelOutput._data.get('FLOW_ADD', {})
                names = self.modelOutput._data.get('Names', {})

                # Incoming flows (flows TO this unit)
                incomingFlows = []
                for key, flow in flowFt.items():
                    if key[1] == self.iconID and flow > 1e-6:  # incoming flows
                        sourceName = names.get(key[0], f"Unit {key[0]}")
                        incomingFlows.append((sourceName, "Process Stream", flow))

                for key, flow in flowAdd.items():
                    if key[1] == self.iconID and flow > 1e-6:  # added flows (raw materials)
                        sourceName = names.get(key[0], f"Material {key[0]}")
                        incomingFlows.append((sourceName, "Added Material", flow))

                # Outgoing flows (flows FROM this unit)
                outgoingFlows = []
                for key, flow in flowFt.items():
                    if key[0] == self.iconID and flow > 1e-6:  # outgoing flows
                        destName = names.get(key[1], f"Unit {key[1]}")
                        outgoingFlows.append((destName, "Process Stream", flow))

                # Add incoming flows to table
                if incomingFlows:
                    incomingLabel = QTableWidgetItem("INCOMING")
                    incomingLabel.setFont(self.subtitleFont)
                    table.insertRow(rowCount)
                    table.setItem(rowCount, 0, incomingLabel)
                    rowCount += 1

                    for source, streamType, flow in incomingFlows:
                        table.insertRow(rowCount)
                        table.setItem(rowCount, 0, QTableWidgetItem(streamType))
                        table.setItem(rowCount, 1, QTableWidgetItem(source))
                        table.setItem(rowCount, 2, QTableWidgetItem(f"{round(flow, 4)}"))
                        rowCount += 1

                # Add outgoing flows to table
                if outgoingFlows:
                    outgoingLabel = QTableWidgetItem("OUTGOING")
                    outgoingLabel.setFont(self.subtitleFont)
                    table.insertRow(rowCount)
                    table.setItem(rowCount, 0, outgoingLabel)
                    rowCount += 1

                    for dest, streamType, flow in outgoingFlows:
                        table.insertRow(rowCount)
                        table.setItem(rowCount, 0, QTableWidgetItem(streamType))
                        table.setItem(rowCount, 1, QTableWidgetItem(dest))
                        table.setItem(rowCount, 2, QTableWidgetItem(f"{round(flow, 4)}"))
                        rowCount += 1

                if rowCount == 0:
                    table.insertRow(0)
                    table.setItem(0, 0, QTableWidgetItem("No mass flows"))

                layout.addWidget(table)

        except Exception as e:
            self.logger.error(f"Error extracting mass balance data: {e}")
            emptyLabel = QLabel("No mass balance data available")
            layout.addWidget(emptyLabel)

        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def _LCaResults(self):
        # Fixme still not working as should

        tab = QWidget()
        layout = QVBoxLayout()

        try:
            if self.modelOutput:
                # Create a form layout for LCA results
                formLayout = QFormLayout()

                # Get all impact categories from the model
                impactCategories = self.modelOutput._data.get('IMPACT_INPUTS_U_CAT', {})

                if impactCategories:
                    # Group impacts by unit
                    unitImpacts = {}
                    for (unitID, impactCat), value in impactCategories.items():
                        if unitID == self.iconID and value > 1e-9:
                            if impactCat not in unitImpacts:
                                unitImpacts[impactCat] = value

                    if unitImpacts:
                        for impactCat, value in unitImpacts.items():
                            # Get the unit for this impact category from the LCA_units dictionary
                            lca_units_dict = self.modelOutput.LCA_units if hasattr(self.modelOutput, 'LCA_units') else {}
                            unit = lca_units_dict.get(impactCat, "unit")

                            impactLineEdit = QLineEdit(f"{round(value, 6)} {unit}")
                            impactLineEdit.setReadOnly(True)
                            formLayout.addRow(QLabel(f"{impactCat}:"), impactLineEdit)
                    else:
                        noDataLabel = QLabel("No LCA data available for this unit")
                        formLayout.addRow(noDataLabel)
                else:
                    # Try to get from alternative location or provide info message
                    noDataLabel = QLabel("LCA data not found in model output")
                    formLayout.addRow(noDataLabel)

                layout.addLayout(formLayout)

        except Exception as e:
            self.logger.error(f"Error extracting LCA data: {e}")
            emptyLabel = QLabel("No environmental impact data available")
            layout.addWidget(emptyLabel)

        layout.addStretch()
        tab.setLayout(layout)
        return tab




