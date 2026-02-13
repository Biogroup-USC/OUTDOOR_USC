import logging

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QDoubleValidator, QFont
from PyQt5.QtWidgets import QFormLayout, QComboBox, QFrame, QWidget, QLineEdit, QPushButton, QLabel

# add the looger
from outdoor.user_interface.utils.OutdoorLogger import outdoorLogger


class GeneralSystemDataTab(QWidget):
    """
    This class creates a tab for the general system data
    """
    def __init__(self, centralDataManager, signalManager, parent=None):
        super().__init__(parent)
        # add the logger
        self.logger = logging.getLogger(__name__)

        # add the central data manager
        self.centralDataManager = centralDataManager
        self.signalManager = signalManager

        # set the init flag to true, so data is not saved when the tab is first initialized
        self.initFlag = True

        # Create a new QWidget for the General System Data tab
        self.layout = QFormLayout(self)
        self.layout.setVerticalSpacing(6)
        self.layout.setHorizontalSpacing(12)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.subtitleFont = QFont("Arial", 11, QFont.Bold)
        # Modernized style for the tab
        self.setStyleSheet("""
            QWidget {
                background-color: #f8fafc;
            }
            QLabel {
                color: #334155;
                background: transparent;
            }
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px 8px;
                background-color: #ffffff;
                selection-background-color: #b0daff;
            }
            QLineEdit:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px 8px;
                background-color: #ffffff;
                color: #0f172a;
                padding-right: 20px;
            }
            QComboBox:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                border: none;
            }
            QPushButton {
                color: #ffffff;
                background-color: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 8px;
                font: bold 13px;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QTableWidget {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: #ffffff;
                selection-background-color: #b0daff;
            }
            QLineEdit:disabled {
                background-color: #f5f5f5;
                color: #666666;
            }
            QComboBox:disabled {
                background-color: #f5f5f5;
                color: #666666;
            }
            QLabel#sectionTitle {
                color: #1e293b;
                font-weight: 700;
                font-size: 13px;
                padding: 5px 0px 2px 0px;
            }
        """)

        # Title for the general system data (centered)
        self.createSectionTitle(text="General System Data", centerAlign=False, color="#C7CEEA")

        self.opti_combo = QComboBox(self)
        self.opti_combo.addItems(
            ["Single", "Multi-Objective", "Sensitivity", "Cross-Parameter Sensitivity",
             "2-Stage-Recourse", "Multi-2-Stage-Recourse"])
        self.layout.addRow(QLabel("Optimization Mode:"), self.opti_combo)
        self.opti_combo.currentIndexChanged.connect(self.saveData)

        # Combo box for the objective function
        self.objective_combo = QComboBox(self)

        self.objective_combo.addItems(
            ["EBIT: Earnings Before Income Taxes", "NPC: Net Production Costs", "NPE: Net Produced CO2 Emissions",
             "FWD: Freshwater Demand"]
            + ['terrestrial acidification potential (TAP)',
               'global warming potential (GWP100)',
               'freshwater ecotoxicity potential (FETP)',
               'marine ecotoxicity potential (METP)',
               'terrestrial ecotoxicity potential (TETP)',
               'fossil fuel potential (FFP)',
               'freshwater eutrophication potential (FEP)',
               'marine eutrophication potential (MEP)',
               'human toxicity potential (HTPc)',
               'human toxicity potential (HTPnc)',
               'ionising radiation potential (IRP)',
               'agricultural land occupation (LOP)',
               'surplus ore potential (SOP)',
               'ozone depletion potential (ODPinfinite)',
               'particulate matter formation potential (PMFP)',
               'photochemical oxidant formation potential: humans (HOFP)',
               'photochemical oxidant formation potential: ecosystems (EOFP)',
               'water consumption potential (WCP)',
               'ecosystem quality',
               'human health',
               'natural resources'
        ]
        )
        self.layout.addRow(QLabel("Objective Function:"), self.objective_combo)
        self.objective_combo.currentIndexChanged.connect(self.saveData)

        # Title for the specific production of a product
        self.createSectionTitle(text="Specific Production", color="#B5EAD7")

        # Create a dropdown for "Product or Substrate driven superstructures"
        self.productDrivenDropdown = QComboBox()
        self.productDrivenDropdown.addItems(["Product", "Substrate", "None"])
        self.productDrivenDropdown.setCurrentText("None")

        self.layout.addRow(QLabel("Load Type:"), self.productDrivenDropdown)
        self.productDrivenDropdown.currentIndexChanged.connect(self.saveData)

        self.productSelection = QComboBox()
        self.layout.addRow(QLabel("Main product/Substrate:"), self.productSelection)
        # Initially populate the combo box
        self._updateProductSelectionComboBox()
        # Connect the centralDataManager's signal to the update methods
        self.signalManager.outputListUpdated.connect(self._updateProductSelectionComboBox)
        self.signalManager.inputListUpdated.connect(self._updateProductSelectionComboBox)
        # if changed save data
        self.productSelection.currentIndexChanged.connect(self.saveData)

        self.productLoadLineEdit = QLineEdit()
        self.productLoadLineEdit.setValidator(
            QDoubleValidator(0.00, 999999.99, 2))  # Set validator to restrict to floating-point numbers
        self.layout.addRow(QLabel("Product/Substrate load (t/y):"), self.productLoadLineEdit)  # only floating numbers allowed as input

        # Connect the signal to the slot function
        self.productDrivenDropdown.currentIndexChanged.connect(lambda: self.productDrivenSwitch())

        # connect to the save data function
        self.productLoadLineEdit.textChanged.connect(self.saveData)

        # make title "general CAPEX parameters"
        self.createSectionTitle(text="General CAPEX parameters", color="#E2F0CB")

        # Add fields for the general CAPEX parameters
        self.operatingHoursLineEdit = QLineEdit("8000")
        self.layout.addRow(QLabel("Operating Hours:"), self.operatingHoursLineEdit)
        self.operatingHoursLineEdit.textChanged.connect(self.saveData)

        self.yearOfStudyLineEdit = QLineEdit("2018")
        self.layout.addRow(QLabel("Year of Study:"), self.yearOfStudyLineEdit)
        self.yearOfStudyLineEdit.textChanged.connect(self.saveData)

        self.interestRateLineEdit = QLineEdit("0.05")
        self.layout.addRow(QLabel("Interest rate:"), self.interestRateLineEdit)
        self.interestRateLineEdit.textChanged.connect(self.saveData)

        self.detailLevelLineEdit = QComboBox()
        self.detailLevelLineEdit.addItems(["real", "fine", "rough", "average"])  # Add options to the dropdown
        self.layout.addRow(QLabel("Detail level of linearization of CAPEX:"), self.detailLevelLineEdit)
        self.detailLevelLineEdit.currentIndexChanged.connect(self.saveData)

        self.indirectCostsLineEdit = QLineEdit("1.44")
        self.layout.addRow(QLabel("Indirect costs:"), self.indirectCostsLineEdit)
        self.indirectCostsLineEdit.textChanged.connect(self.saveData)

        self.directCostsLineEdit = QLineEdit("2.6")
        self.layout.addRow(QLabel("Direct costs:"), self.directCostsLineEdit)
        self.directCostsLineEdit.textChanged.connect(self.saveData)

        # todo: add different standard Direct and indirect costs factors for different processing plant types
        #  i.e., Solid, solid-liquid and liquid processing plants
        # reference: page 251 Table 6.9 of the book "Plant Design and Economics for Chemical Engineers, fith edition"
        costFactors = {
            "Solid": {"Direct": 1.69, "Indirect": 1.28},
            "Solid-liquid": {"Direct": 2.02, "Indirect": 1.26},
            "Liquid": {"Direct": 2.60, "Indirect": 1.44}
        }

        # self.omFactorLineEdit = QLineEdit("0.04")
        # self.layout.addRow(QLabel("O&M Factor:"), self.omFactorLineEdit)

        # Heat pump parameters
        # Title for the Heat pump parameters section
        self.createSectionTitle("Heat pump parameters", color="#FFDAC1")

        # Add fields for the heat pump parameters
        self.heatPumpDropdown = QComboBox()
        self.heatPumpDropdown.addItems(["Yes", "No"])  # Add options to the dropdown
        self.layout.addRow(QLabel("Heat pump switch:"), self.heatPumpDropdown)
        self.heatPumpDropdown.currentIndexChanged.connect(self.saveData)

        # Add fields for the heat pump parameters
        self.COPLineEdit = QLineEdit("2.5")
        self.COPLineEdit.setValidator(
            QDoubleValidator(0.00, 999999.99, 2))  # Set validator to restrict to floating-point numbers
        self.layout.addRow(QLabel("Coefficient of performance (COP):"), self.COPLineEdit)
        self.COPLineEdit.textChanged.connect(self.saveData)

        self.costLineEdit = QLineEdit("450")
        self.costLineEdit.setValidator(
            QDoubleValidator(0.00, 999999.99, 2))  # Set validator to restrict to floating-point numbers
        self.layout.addRow(QLabel("Cost per kW installed:"), self.costLineEdit)
        self.costLineEdit.textChanged.connect(self.saveData)


        self.lifetimeLineEdit = QLineEdit("0")
        self.lifetimeLineEdit.setValidator(
            QDoubleValidator(1990, 2018, 0))  # Set validator to restrict to floating-point numbers
        self.layout.addRow(QLabel("Lifetime:"), self.lifetimeLineEdit)
        self.lifetimeLineEdit.textChanged.connect(self.saveData)


        self.TINLineEdit = QLineEdit()
        self.TINLineEdit.setValidator(
            QDoubleValidator(0.00, 999999.99, 2))  # Set validator to restrict to floating-point numbers
        self.layout.addRow(QLabel("Inlet Temperature °C:"), self.TINLineEdit)
        self.TINLineEdit.textChanged.connect(self.saveData)


        self.TOUTLineEdit = QLineEdit()
        self.TOUTLineEdit.setValidator(
            QDoubleValidator(0.00, 999999.99, 2))  # Set validator to restrict to floating-point numbers
        self.layout.addRow(QLabel("Outlet Temperature °C:"), self.TOUTLineEdit)
        self.TOUTLineEdit.textChanged.connect(self.saveData)

        # Connect the signal to the slot function
        self.heatPumpDropdown.currentIndexChanged.connect(lambda: self.heatPumpSwitch())

        # Set the layout on the generalSystemDataWidget
        self.setLayout(self.layout)
        # set the switch
        self.productDrivenSwitch()
        # deactivate the init flag
        self.initFlag = False
        # import existing data
        self.importData()

    def createSectionTitle(self, text, color="#e1e1e1", centerAlign=False):
        title = QLabel(text)
        title.setObjectName("sectionTitle")
        title.setFont(self.subtitleFont)
        if centerAlign:
            title.setAlignment(Qt.AlignCenter)
        frame = QFrame()
        frame.setFrameShape(QFrame.HLine)
        frame.setFrameShadow(QFrame.Sunken)
        self.layout.addRow(title)
        self.layout.addRow(frame)

    def productDrivenSwitch(self):

        if self.productDrivenDropdown.currentText() == "None":
            # If "No" is selected, make the other fields not editable
            self.productSelection.setDisabled(True)
            self.productSelection.addItems([""])
            self.productSelection.setCurrentText("")
            self.productLoadLineEdit.setDisabled(True)
            self.productLoadLineEdit.setText("")
        else:
            # If "Yes" is selected, make the other fields editable
            self.productSelection.setDisabled(False)
            # self.productSelection.removeItem([""])
            self.productLoadLineEdit.setDisabled(False)
            # update the selection list
            self._updateProductSelectionComboBox()

    def heatPumpSwitch(self):
        if self.heatPumpDropdown.currentText() == "No":
            # If "No" is selected, make the other fields not editable
            self.COPLineEdit.setDisabled(True)
            self.costLineEdit.setDisabled(True)
            self.lifetimeLineEdit.setDisabled(True)
            self.TINLineEdit.setDisabled(True)
            self.TOUTLineEdit.setDisabled(True)
            # Set the fields to empty
            self.COPLineEdit.setText("")
            self.costLineEdit.setText("")
            self.lifetimeLineEdit.setText("")
            self.TINLineEdit.setText("")
            self.TOUTLineEdit.setText("")
        else:
            # If "Yes" is selected, make the other fields editable
            self.COPLineEdit.setDisabled(False)
            self.costLineEdit.setDisabled(False)
            self.lifetimeLineEdit.setDisabled(False)
            self.TINLineEdit.setDisabled(False)
            self.TOUTLineEdit.setDisabled(False)


    @pyqtSlot()
    def saveData(self):
        if not self.initFlag: # do not save data when the tab is first initialized
            # Collect data from the table
            generalData = self.collectData()

            # Save the data to the central data manager
            # self.centralDataManager.addData("generalData", generalData) # not a fan of this fumction, convoluted

            # overwrite the data to the central data manager straight away
            self.centralDataManager.generalData = generalData
            self.logger.info("General System Data saved")
            # print(generalData)


    def collectData(self):
        # Collect data from the Widget fields
        if "PROJECT_NAME" in self.centralDataManager.metadata:
            projectName = self.centralDataManager.metadata["PROJECT_NAME"]
        else:
            projectName = "Not Saved"

        data = {
            "projectName": projectName,
            "productDriver": self.productDrivenDropdown.currentText(),
            "objective": self.objective_combo.currentText(),
            "optimizationMode": self.opti_combo.currentText(),
            "mainProduct": self.productSelection.currentText(),
            "productLoad": self.productLoadLineEdit.text(),
            "operatingHours": self.operatingHoursLineEdit.text(),
            "yearOfStudy": self.yearOfStudyLineEdit.text(),
            "interestRate": self.interestRateLineEdit.text(),
            "detailLevel": self.detailLevelLineEdit.currentText(),
            # "omFactor": self.omFactorLineEdit.text(), => not used in the code is unit specific and not general
            "indirectCost": self.indirectCostsLineEdit.text(),
            "directCost": self.directCostsLineEdit.text(),
            "heatPumpSwitch": self.heatPumpDropdown.currentText(),
            "COP": self.COPLineEdit.text(),
            "cost": self.costLineEdit.text(),
            "lifetime": self.lifetimeLineEdit.text(),
            "TIN": self.TINLineEdit.text(),
            "TOUT": self.TOUTLineEdit.text(),
        }
        # print(data["objective"])
        return data

    def importData(self):
        generalData = self.centralDataManager.generalData
        if generalData:
            # update the list selection list
            self._updateProductSelectionComboBox()

            # set the values from the centralDataManager
            self.signalManager.importLists()
            self.objective_combo.setCurrentText(generalData["objective"])
            self.opti_combo.setCurrentText(generalData["optimizationMode"])
            self.productDrivenDropdown.setCurrentText(generalData["productDriver"])
            self.productSelection.setCurrentText(generalData['mainProduct'])
            self.productLoadLineEdit.setText(generalData["productLoad"])
            self.operatingHoursLineEdit.setText(generalData["operatingHours"])
            self.yearOfStudyLineEdit.setText(generalData["yearOfStudy"])
            self.interestRateLineEdit.setText(generalData["interestRate"])
            self.detailLevelLineEdit.setCurrentText(generalData["detailLevel"])
            self.indirectCostsLineEdit.setText(generalData["indirectCost"])
            self.directCostsLineEdit.setText(generalData["directCost"])
            self.heatPumpDropdown.setCurrentText(generalData["heatPumpSwitch"])
            self.COPLineEdit.setText(generalData["COP"])
            self.costLineEdit.setText(generalData["cost"])
            self.lifetimeLineEdit.setText(generalData["lifetime"])
            self.TINLineEdit.setText(generalData["TIN"])
            self.TOUTLineEdit.setText(generalData["TOUT"])

        else:
            self.logger.info("Booting up with no General System Data")

    def _updateProductSelectionComboBox(self):
        """
        This function updates the QComboBox with the current values from centralDataManager.outputList.
        """

        # extract the existing items from the productSelection
        if self.centralDataManager.generalData:
            productOrSubstrate = self.centralDataManager.generalData['mainProduct']
        else: # when opening the app for the first time there is no data, so don't set the current text
            productOrSubstrate = None

        # Clear the existing items
        self.productSelection.clear()
        # Add updated items from centralDataManager
        if self.productDrivenDropdown.currentText() == "Product":
            dropList = self.signalManager.outputList
            self.productSelection.addItems(dropList)
        elif self.productDrivenDropdown.currentText() == "Substrate":
            dropList = self.signalManager.inputList
            self.productSelection.addItems(dropList)
        else:
            dropList = []

        # if it is not the current product of substrate that is deleted, set the current text to the original product
        # or substrate name
        if self.centralDataManager.generalData and productOrSubstrate in dropList:
            self.productSelection.setCurrentText(productOrSubstrate)
