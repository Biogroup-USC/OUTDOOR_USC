from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, \
    QGroupBox, QLabel, QComboBox, QDialog, QApplication
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QMovie
from outdoor.user_interface.utils.LCACalculationMachine import LCACalculationMachine
from outdoor.user_interface.data.ConstructSuperstructure import ConstructSuperstructure
from outdoor.outdoor_core.main.superstructure_problem import SuperstructureProblem
from outdoor.outdoor_core.output_classes.analyzers.basic_analyzer import BasicModelAnalyzer
#from outdoor.user_interface.interactives.Canvas import *
from outdoor.user_interface.interactives.CanvasResults import CanvasResults

import logging
import os



class ResultsTab(QWidget):
    def __init__(self, centralDataManager, signalManager, parent=None):
        """
        This method creates the Results tab with dropdown lists for objective, optimization mode,
        and results options, with a calculate button and a canvas on the right.
        :return: QWidget for the results tab
        """
        # Main layout
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self.centralDataManager = centralDataManager
        self.signalManager = signalManager
        # self.iconLabels = iconLabels
        self.waitingDialog = None

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

        # Save button. Saves the results of the optimization in a txt file and in the centralDataManager
        # You have to specify the path where you want to save the results.
        self.saveResultsButton = QPushButton("Save Results")
        self.saveResultsButton.clicked.connect(self.saveResults)
        self.leftPanel.addWidget(self.saveResultsButton)

        # Add stretch to push controls to the top (keeps the button under Results Options)
        self.leftPanel.addStretch()

        # Right panel as canvas
        self.rightPanel = CanvasResults(centralDataManager=self.centralDataManager,
                                 signalManager=self.signalManager)

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

        # Check if superstructure generation was successful
        if superstructure is None:
            self.logger.error("Failed to generate superstructure. Optimization cancelled.")
            return

        self.logger.info("Superstructure object generated successfully. Proceeding with optimization...")

        # get the drop down value of the optimization mode
        optimizationMode = self.optimizationModeComboBox.currentText()

        # display a message on the canvas that the optimization is running and it might take a while
        self.showWaitingDialog("Running optimization... This may take a while.")

        if optimizationMode == 'Single Objective':
            self.runSingleOptimization(superstructure)
        else:
            self.logger.info("not quite implemented yet, "
                             "under construction! Please select Single Objective for now.")
            self.closeWaitingDialog()



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

        else:
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

            # get the current objective from objectiveComboBox
            selectedObjective = self.objectiveComboBox.currentText()


            if selectedObjective == "EBIT: Earnings Before Income Taxes":
                selectedObjective = "EBIT"
            elif selectedObjective == "NPC: Net Production Costs":
                selectedObjective = "NPC"

            # solve the optimization problem
            modelOutput = abstract_model.solve_optimization_problem(
                input_data=superstructureObj,
                optimization_mode='single',
                solver='gurobi',
                interface='local',
                options=solverOptions,
                modelObjective=selectedObjective
            )

            # save the general results as a txt file, you have to specify the path
            modelOutput.get_results(path=None,
                                    saveName='txt_results')

            # get the results on the canvas
            self.modelOutput = modelOutput
            # give the model output to the central data manager so that it can be accessed by other
            # parts of the application
            self.centralDataManager.setModelOutput(modelOutput)
            # make an "analyzer object" which you can use to plot various results
            self.modelOutputAnalyzer = BasicModelAnalyzer(modelOutput)

            # get the chosen units and place them on the canvas
            # get the unit processes from the solution object
            chosenUnits = self.modelOutput.return_chosen()
            connectedUnits =  self.modelOutputAnalyzer._collect_mass_flows(model_data=self.modelOutput._data,
                                                                           nDecimals=4)["Mass flows"]
            # Clear the canvas before loading new results
            self.rightPanel.clearCanvas()
            # Load the new results onto the canvas
            self.rightPanel.loadInResults(chosenUnits, connectedUnits)

        # catch any exceptions that occur during optimization and display an error dialog
        except Exception as e:
            self.logger.error(f"An error occurred during optimization: {str(e)}")
            self.optimizationErrorDialog(str(e))



        finally:
            # Reactivate logging
            logging.disable(previous_level)
            # Close the waiting dialog
            self.closeWaitingDialog()

        self.logger.info("Model output generated successfully ...")


    def saveResults(self):
        """
        Save the results of the optimization in a txt file and in the centralDataManager
        You have to specify the path where you want to save the results.
        """
        if hasattr(self, 'modelOutput'):
            # Save to centralDataManager
            self.centralDataManager.set_data('modelOutput', self.modelOutput)
            self.logger.info("Model output saved to centralDataManager successfully.")

            # Save to txt file
            savePath = "path/to/save/results"  # Specify your path here
            self.modelOutput.get_results(path=savePath, saveName='txt_results')
            self.logger.info(f"Model output saved to {savePath} as txt_results.txt successfully.")
        else:
            self.logger.warning("No model output available to save. Please run the optimization first.")


    def showWaitingDialog(self, message):
        """
        Show a waiting message as a dialog while the optimization is running.
        :param message: The message to display
        """
        # Disable all controls in the left panel
        self.disableAllControls()

        # Create a custom dialog with spinning wheel
        self.waitingDialog = QDialog(self)
        self.waitingDialog.setWindowTitle("Optimization in Progress")
        self.waitingDialog.setWindowFlags(self.waitingDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint & ~Qt.WindowCloseButtonHint)
        self.waitingDialog.setFixedSize(300, 150)

        # Create layout
        layout = QVBoxLayout(self.waitingDialog)

        # Create label for the spinner
        waitingLabel = QLabel()
        waitingLabel.setAlignment(Qt.AlignCenter)

        # Create label for the text
        textLabel = QLabel(message)
        textLabel.setAlignment(Qt.AlignCenter)
        textLabel.setWordWrap(True)

        # Add loading spinner animation
        # loading.gif is located in the utils directory
        gifPath = os.path.join(os.path.dirname(__file__), "..", "utils", "loading.gif")
        if os.path.exists(gifPath):
            movie = QMovie(gifPath)
            movie.setScaledSize(QSize(50, 50))
            waitingLabel.setMovie(movie)
            movie.start()

        # Add widgets to layout
        layout.addWidget(waitingLabel)
        layout.addWidget(textLabel)

        # Show the dialog
        self.waitingDialog.setModal(True)
        self.waitingDialog.show()
        QApplication.instance().processEvents()

    def disableAllControls(self):
        """
        Disable all interactive controls in the left panel and canvas during optimization.
        """
        self.objectiveComboBox.setEnabled(False)
        self.optimizationModeComboBox.setEnabled(False)
        self.secondObjectiveComboBox.setEnabled(False)
        self.resultsOptionsComboBox.setEnabled(False)
        self.runButton.setEnabled(False)
        self.saveResultsButton.setEnabled(False)
        # Disable the canvas
        self.rightPanel.setEnabled(False)

    def enableAllControls(self):
        """
        Re-enable all interactive controls in the left panel and canvas after optimization.
        """
        self.objectiveComboBox.setEnabled(True)
        self.optimizationModeComboBox.setEnabled(True)
        # Only enable second objective if multi-objective is selected
        if self.optimizationModeComboBox.currentText() == 'Multi-Objective':
            self.secondObjectiveComboBox.setEnabled(True)
        else:
            self.secondObjectiveComboBox.setEnabled(False)
        self.resultsOptionsComboBox.setEnabled(True)
        self.runButton.setEnabled(True)
        self.saveResultsButton.setEnabled(True)
        # Re-enable the canvas
        self.rightPanel.setEnabled(True)

    def closeWaitingDialog(self):
        """
        Close the waiting dialog when optimization is complete.
        """
        if self.waitingDialog:
            self.waitingDialog.close()
            self.waitingDialog = None
            # Re-enable all controls
            self.enableAllControls()
            QApplication.instance().processEvents()

    def optimizationErrorDialog(self, errorMessage):
        """
        Show a professional error dialog if optimization fails.
        :param errorMessage: The error message to display
        """
        errorDialog = QDialog(self)
        errorDialog.setWindowTitle("Optimization Error")
        errorDialog.setWindowFlags(errorDialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        errorDialog.setFixedSize(500, 250)

        # Create layout
        layout = QVBoxLayout(errorDialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title label
        titleLabel = QLabel("Optimization Failed")
        titleFont = titleLabel.font()
        titleFont.setPointSize(12)
        titleFont.setBold(True)
        titleLabel.setFont(titleFont)
        titleLabel.setAlignment(Qt.AlignLeft)

        # Separator line
        separator = QLabel("━" * 50)
        separator.setStyleSheet("color: #cccccc;")

        # Error message label
        messageLabel = QLabel("The following error occurred during optimization:")
        messageLabel.setStyleSheet("color: #333333; font-weight: bold;")

        # Error details (scrollable text area)
        errorDetailLabel = QLabel(errorMessage)
        errorDetailLabel.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        errorDetailLabel.setWordWrap(True)
        errorDetailLabel.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 2px;
                padding: 10px;
                color: #d32f2f;
                font-family: 'Courier New', monospace;
                font-size: 9pt;
            }
        """)

        # Add stretch to push error details up
        errorDetailLabel.setMinimumHeight(80)

        # OK button
        okButton = QPushButton("OK")
        okButton.setFixedWidth(100)
        okButton.clicked.connect(errorDialog.accept)
        okButton.setStyleSheet("""
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
        """)

        # Button layout
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)

        # Add all widgets to layout
        layout.addWidget(titleLabel)
        layout.addWidget(separator)
        layout.addWidget(messageLabel)
        layout.addWidget(errorDetailLabel)
        layout.addLayout(buttonLayout)

        # Apply dialog stylesheet
        errorDialog.setStyleSheet("""
            QDialog {
                background-color: #f2f2f2;
            }
        """)

        # Show the dialog
        errorDialog.exec_()




