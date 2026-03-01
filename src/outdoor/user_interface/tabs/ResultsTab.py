from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, \
    QGroupBox, QLabel, QComboBox
from outdoor.user_interface.utils.LCACalculationMachine import LCACalculationMachine
from outdoor.user_interface.data.ConstructSuperstructure import ConstructSuperstructure
from outdoor.outdoor_core.main.superstructure_problem import SuperstructureProblem

import logging



class ResultsTab(QWidget):
    def __init__(self, centralDataManager, parent=None):
        """
        This method creates the Results tab with dropdown lists for objective, optimization mode,
        and results options, with a calculate button and a canvas on the right.
        :return: QWidget for the results tab
        """
        # Main layout
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self.centralDataManager = centralDataManager

        self.mainLayout = QHBoxLayout()

        # Left panel for controls
        self.leftPanel = QVBoxLayout()

        # Section 1: Objective Dropdown
        self.objectiveGroup = QGroupBox("Objective")
        self.objectiveLayout = QVBoxLayout()
        self.objectiveLabel = QLabel("Select Objective:")
        self.objectiveComboBox = QComboBox()
        LcaObjectives = LCACalculationMachine(centralDataManager).getImpactCatNames()
        extraObjectives = ["EBIT: Earnings Before Income Taxes", "NPC: Net Production Costs"]
        allObjectives = extraObjectives + LcaObjectives
        self.objectiveComboBox.addItems(allObjectives)
        self.objectiveLayout.addWidget(self.objectiveLabel)
        self.objectiveLayout.addWidget(self.objectiveComboBox)
        self.objectiveGroup.setLayout(self.objectiveLayout)
        self.leftPanel.addWidget(self.objectiveGroup)

        # Section 2: Optimization Mode Dropdown
        self.optimizationModeGroup = QGroupBox("Optimization Mode")
        self.optimizationModeLayout = QVBoxLayout()
        self.optimizationModeLabel = QLabel("Select Optimization Mode:")
        self.optimizationModeComboBox = QComboBox()
        self.optimizationModeComboBox.addItems(['Single Objective', 'Multi-Objective', 'Sensitivity Analysis'])
        self.optimizationModeComboBox.currentTextChanged.connect(self.onOptimizationModeChanged)
        self.optimizationModeLayout.addWidget(self.optimizationModeLabel)
        self.optimizationModeLayout.addWidget(self.optimizationModeComboBox)
        self.optimizationModeGroup.setLayout(self.optimizationModeLayout)
        self.leftPanel.addWidget(self.optimizationModeGroup)

        # Section 2b: Second Objective Dropdown (only enabled for Multi-Objective)
        self.secondObjectiveGroup = QGroupBox("Second Objective")
        self.secondObjectiveLayout = QVBoxLayout()
        self.secondObjectiveLabel = QLabel("Select Second Objective:")
        self.secondObjectiveComboBox = QComboBox()

        self.secondObjectiveComboBox.addItems(allObjectives)
        self.secondObjectiveComboBox.setEnabled(False)  # Disabled by default
        self.secondObjectiveLayout.addWidget(self.secondObjectiveLabel)
        self.secondObjectiveLayout.addWidget(self.secondObjectiveComboBox)
        self.secondObjectiveGroup.setLayout(self.secondObjectiveLayout)
        self.leftPanel.addWidget(self.secondObjectiveGroup)

        # Section 3: Results Options Dropdown
        self.resultsOptionsGroup = QGroupBox("Results Options")
        self.resultsOptionsLayout = QVBoxLayout()
        self.resultsOptionsLabel = QLabel("Select Results Display:")
        self.resultsOptionsComboBox = QComboBox()
        self.resultsOptionsComboBox.addItems(['Overview', 'Detailed Results', 'Comparison', 'Export'])
        self.resultsOptionsLayout.addWidget(self.resultsOptionsLabel)
        self.resultsOptionsLayout.addWidget(self.resultsOptionsComboBox)
        self.resultsOptionsGroup.setLayout(self.resultsOptionsLayout)
        self.leftPanel.addWidget(self.resultsOptionsGroup)

        # Run Optimization button directly under the Results Options group
        self.runButton = QPushButton("Run Optimization")
        self.runButton.clicked.connect(self.onCalculateClicked)
        self.leftPanel.addWidget(self.runButton)

        # Add stretch to push controls to the top (keeps the button under Results Options)
        self.leftPanel.addStretch()

        # Right panel as blank canvas
        self.rightPanel = QWidget()
        self.rightPanel.setStyleSheet("background-color: white;")

        # Adding panels to the main layout
        self.mainLayout.addLayout(self.leftPanel, 1)  # Add left panel with a ratio
        self.mainLayout.addWidget(self.rightPanel, 4)  # Add right panel with a larger ratio

        # Setting the central widget
        self.setLayout(self.mainLayout)

    def onCalculateClicked(self):
        """
        Handle the Calculate / Run Optimization button click event.
        """

       # first get the superstructure object from the canvas
        superstructure = self.generateSuperstructureObject()
        self.logger.info("Superstructure object generated successfully. Proceeding with optimization...")

        # get the drop down value of the optimization mode
        optimizationMode = self.optimizationModeComboBox.currentText()

        if optimizationMode == 'Single Objective':
            self.runSingleOptimization(superstructure)
        else:
            self.logger.info("not quite implemented yet, "
                             "under construction! Please select Single Objective for now.")
            pass



    def generateSuperstructureObject(self):
        """
        get the current superstructure from the canvas and generate a
        superstructure object using the ConstructSuperstructure class.
        """

        constructorSuperstructure = ConstructSuperstructure(self.centralDataManager)
        if constructorSuperstructure.warningMessage:
            self.logger.error("please be mindful of the following warning Message: {}".format(
                constructorSuperstructure.warningMessage))
        elif constructorSuperstructure.errorMessage:
            self.logger.error("You must fix the issues from the pop-ups before you can save the superstructure object")
            return

        superstructure = constructorSuperstructure.get_superstructure()

        return superstructure

    def onOptimizationModeChanged(self, mode):
        """
        Enable or disable the second objective dropdown based on the selected optimization mode.
        :param mode: The selected optimization mode
        """
        if mode == 'Multi-Objective':
            self.secondObjectiveComboBox.setEnabled(True)
        else:
            self.secondObjectiveComboBox.setEnabled(False)

    import logging

    def runSingleOptimization(self, superstructureObj):

        # Store previous global logging state
        previous_level = logging.root.manager.disable

        # Disable INFO and below (DEBUG + INFO)
        logging.disable(logging.INFO)

        try:
            abstract_model = SuperstructureProblem(parser_type='Superstructure')

            solverOptions = {
                "IntFeasTol": 1e-8,
                "NumericFocus": 0,
            }

            model_output = abstract_model.solve_optimization_problem(
                input_data=superstructureObj,
                optimization_mode='single',
                solver='gurobi',
                interface='local',
                options=solverOptions,
            )

        finally:
            # Reactivate logging
            logging.disable(previous_level)

        self.logger.info("Model output generated successfully ...")

