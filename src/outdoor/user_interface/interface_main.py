import argparse
import os
import pickle
import sys
import pandas as pd
import coloredlogs
from PyQt5.QtWidgets import QTabWidget, QApplication, QMainWindow, QAction, QFileDialog, QDialog, QMessageBox
from pyparsing import empty
import bw2data as bw
from outdoor.user_interface.data.CentralDataManager import CentralDataManager
from outdoor.user_interface.data.SignalManager import SignalManager
from outdoor.user_interface.data.superstructure_frame import SuperstructureFrame
from outdoor.user_interface.data.ConstructSuperstructure import ConstructSuperstructure
from outdoor.user_interface.data.TabManager import TabManager
from outdoor.user_interface.dialogs.ConfigEditor import ConfigEditor
from outdoor.user_interface.WelcomeTab import WelcomeTab
from outdoor.user_interface.tabs.SensitivityTab import SensitivityTab
from outdoor.user_interface.utils.LCACalculationMachine import LCACalculationMachine
from outdoor.user_interface.tabs.ComponentsTab import ComponentsTab
from outdoor.user_interface.tabs.GeneralSystemDataTab import GeneralSystemDataTab
from outdoor.user_interface.tabs.UtilityTab import UtilityTab
from outdoor.user_interface.tabs.SuperstructureMappingTab import SuperstructureMappingTab
from outdoor.user_interface.tabs.ReactionTab import ReactionsTab
from outdoor.user_interface.tabs.ProjectDescriptionTab import ProjectDescriptionTab
from outdoor.user_interface.tabs.UncertaintyTab import UncertaintyTab
from outdoor.user_interface.utils.OutdoorLogger import outdoorLogger
from outdoor.user_interface.data.ProcessDTO import ProcessType
from outdoor.user_interface.dialogs.MethodLCADialog import MethodologyLcaDialog

import logging

class MainWindow(QMainWindow):  # Inherit from QMainWindow

    """
    This class creates the main window for the application and sets up the menu bar and tabbed interface.
    """

    def __init__(self, **kwargs):
        super().__init__()
        # add the logger
        self.logger = logging.getLogger()
        coloredlogs.install(logger=self.logger, level=kwargs['level'],isatty=True)
        logging.getLogger('peewee').setLevel(logging.ERROR)  # This is to make brightway shut up
        logging.getLogger("bw2calc").setLevel(logging.ERROR)  # This is to make brightway shut up
        logging.getLogger("fsspec").setLevel(logging.ERROR)
        self.setWindowTitle("OUTDOOR 2.0 - Open Source Process Simulator")
        self.setGeometry(100, 100, 1200, 800)
        self.ProjectName = ""
        self.ProjectPath = ""
        self.centralDataManager = CentralDataManager()  # Initialize the data manager
        self.signalManager = SignalManager(self.centralDataManager)  # Initialize the output manager
        self.tabManager = TabManager()  # Initialize the tab manager

        menu_bar = self.menuBar()
        fileMenu = menu_bar.addMenu('File')

        # Creating actions for the 'File' menu
        openAction = QAction('Open', self)
        self.saveAction = QAction('Save', self)
        if self.ProjectName == '':
            self.saveAction.setDisabled(True)
        saveAsAction = QAction('Save As', self)

        # Adding actions to the 'File' menu
        fileMenu.addAction(openAction)
        fileMenu.addAction(self.saveAction)
        fileMenu.addAction(saveAsAction)

        # Connect actions to methods here (you'll implement these methods)
        openAction.triggered.connect(self.openFile)
        self.saveAction.triggered.connect(self.saveFile)
        saveAsAction.triggered.connect(self.saveAsFile)

        editMenu = menu_bar.addMenu('Edit')
        self.editAction = QAction('Configuration', self)
        if self.ProjectName == '':
            self.editAction.setDisabled(True)
        self.editAction.triggered.connect(self.editConfigs)
        editMenu.addAction(self.editAction)

        structureMenu = menu_bar.addMenu('Superstructure')
        # add superstructure generation button
        self.superStructureAction = QAction('Generate Superstructure', self)
        self.superStructureAction.triggered.connect(self.generateSuperstructureObject) # connect to method
        structureMenu.addAction(self.superStructureAction)

        lcaMenu = menu_bar.addMenu('LCA')
        # add calculate LCA button
        self.calcLCAAction = QAction('Calculate all LCAs', self)
        self.calcLCAAction.triggered.connect(self.calculateAllLCAs)# connect to method
        # add print reference to consul
        self.printRefLCA = QAction('Print References LCA', self)
        self.printRefLCA.triggered.connect(self.printReferencesLCA)  # connect to method
        # set up database and calculation methode
        self.setUpLcaAction = QAction('Set up', self)
        self.setUpLcaAction.triggered.connect(self.setUpLca)  # connect to method

        lcaMenu.addAction(self.setUpLcaAction)
        lcaMenu.addAction(self.calcLCAAction)
        lcaMenu.addAction(self.printRefLCA)

        self.initTabs()

    def enableSave(self):
        self.saveAction.setEnabled(True)
        self.editAction.setEnabled(True)

    def openFile(self):
        try:
            filepath = QFileDialog(self, caption='Open Saved Project', filter='*.outdr', directory='data/frames')
            filepath.exec()

            self.ProjectPath = filepath.selectedFiles()[0]
            self.ProjectName = self.ProjectPath.split('/')[-1].split('.')[0]

            # sometimes submodules are not imported, use this to force the import of the data module
            # replicate if you get similar errors such as: "no module 'data' found"
            if 'data' not in sys.modules:
                import outdoor.user_interface.data
                sys.modules['data'] = sys.modules['outdoor.user_interface.data']

            with open(self.ProjectPath, 'rb') as file:
                self.centralDataManager = pickle.load(file)
            self.centralDataManager.metadata["PROJECT_NAME"] = self.ProjectName
            self.centralDataManager.loadConfigs()
            self.signalManager = SignalManager(self.centralDataManager)  # Initialize the new output manager
            # check if there are missing attributes in the centralDataManager
            self.checkMissingAttributes()

            self.initTabs()
            self.enableSave()
            self.logger.debug("Opened File: {}".format(self.ProjectPath))

        except Exception as e:
            self.logger.error('Loading in file "{}" failed'.format(self.ProjectPath))
            self.logger.error(e)


    def checkMissingAttributes(self):
        """
        During development some new attributes were added to the DTOs, this method checks if the attributes are missing
        and adds them with default values if they are missing
        :return:
        """

        # check if sensitivity data exists
        if not hasattr(self.centralDataManager, 'sensitivityData'):
            self.centralDataManager.sensitivityData = []

        for unitDTO in self.centralDataManager.unitProcessData.values():
            if unitDTO.type in [ProcessType.BOOLDISTRIBUTOR, ProcessType.DISTRIBUTOR]:
                if not hasattr(unitDTO, 'curvatureLinesDistributor'):
                    unitDTO.curvatureLinesDistributor = {}
                if not hasattr(unitDTO, 'distributorLineUnitMap'):
                    unitDTO.distributorLineUnitMap = {}

            elif unitDTO.type == ProcessType.INPUT:
                if not hasattr(unitDTO, 'curvatureLinesInput'):
                    unitDTO.curvatureLinesInput = {}
                if not hasattr(unitDTO, 'inputLineUnitMap'):
                    unitDTO.inputLineUnitMap = {}

        if not hasattr(self.centralDataManager, 'uncertaintyData'):
            self.centralDataManager.uncertaintyData = []
        # had a problem with the material flow in the DTO, this is a temporary fix

        # having a problem with the LCA objects missing a dictionary with key 'exchanges'
        # this is a temporary fix
        data_lists = [
            self.centralDataManager.componentData,
            self.centralDataManager.utilityData,
            self.centralDataManager.wasteData,
            self.centralDataManager.temperatureData
        ]

        ## TOTAL LCA RESET
        for data_list in data_lists:
            for dto in data_list:
                if not hasattr(dto, 'LCA') or not dto.LCA:
                    dto.LCA = {'Results': {}, 'exchanges': {}}
                    dto.calculated = False
                if not hasattr(dto, 'emptyCategories'):
                    dto.emptyCategories = {
                        'terrestrial acidification potential (TAP)': 0,
                        'global warming potential (GWP100)': 0,
                        'freshwater ecotoxicity potential (FETP)': 0,
                        'marine ecotoxicity potential (METP)': 0,
                        'terrestrial ecotoxicity potential (TETP)': 0,
                        'fossil fuel potential (FFP)': 0,
                        'freshwater eutrophication potential (FEP)': 0,
                        'marine eutrophication potential (MEP)': 0,
                        'human toxicity potential (HTPc)': 0,
                        'human toxicity potential (HTPnc)': 0,
                        'ionising radiation potential (IRP)': 0,
                        'agricultural land occupation (LOP)': 0,
                        'surplus ore potential (SOP)': 0,
                        'ozone depletion potential (ODPinfinite)': 0,
                        'particulate matter formation potential (PMFP)': 0,
                        'photochemical oxidant formation potential: humans (HOFP)': 0,
                        'photochemical oxidant formation potential: ecosystems (EOFP)': 0,
                        'water consumption potential (WCP)': 0,
                        'ecosystem quality': 0,
                        'human health': 0,
                        'natural resources': 0
                    }



    def saveFile(self):
        """
        Save the current project to the file path specified in self.ProjectPath
        :return:
        """
        for unitDTO in self.centralDataManager.unitProcessData.values():
            unitDTO.exitPorts = []
            unitDTO.entryPorts = []

        with open(self.ProjectPath, 'wb') as file:
            pickle.dump(self.centralDataManager, file)
        self.logger.info("Saved File: {}".format(self.ProjectPath))
        self.centralDataManager.metadata["PROJECT_NAME"] = self.ProjectName

    def saveAsFile(self):
        """
        Save the current project to a new file path
        :return:
        """
        try:
            self.ProjectPath = QFileDialog.getSaveFileName(self, 'Save As', filter='*.outdr', directory='data/frames')[
                0]
            self.ProjectName = self.ProjectPath.split('/')[-1].split('.')[0]

            # temporary fix for a bug during saving: can not pickle QT objects!!
            # I'm not using the DTO to acess the ports so this is relatively safe for now
            for unitDTO in self.centralDataManager.unitProcessData.values():
                unitDTO.exitPorts = []
                unitDTO.entryPorts = []

            with open(self.ProjectPath, 'wb') as file:
                pickle.dump(self.centralDataManager, file)

            self.setWindowTitle(self.ProjectName)
            self.enableSave()
            self.logger.debug("Saved File: {}".format(self.ProjectPath))
            self.centralDataManager.metadata["PROJECT_NAME"] = self.ProjectName

        except Exception as e:
            self.logger.error("Save cancelled.", e)

    def editConfigs(self):
        dialog = ConfigEditor(self.centralDataManager)
        if dialog.exec_():
            pass
        else:
            pass
        self.update()

    def initTabs(self, index=None):
        # Create a QTabWidget and set it as the central widget
        tabWidget = QTabWidget()
        self.setCentralWidget(tabWidget)

        # Create the tabs
        welcomeTab = WelcomeTab(centralDataManager=self.centralDataManager)
        projectDescriptionTab = ProjectDescriptionTab(centralDataManager=self.centralDataManager)
        generalSystemDataTab = GeneralSystemDataTab(centralDataManager=self.centralDataManager,
                                                    signalManager=self.signalManager)
        componentsTab = ComponentsTab(centralDataManager=self.centralDataManager, tabManager=self.tabManager)
        reactionsTab = ReactionsTab(centralDataManager=self.centralDataManager)
        utilityTab = UtilityTab(centralDataManager=self.centralDataManager)
        superstructureMappingTab = SuperstructureMappingTab(centralDataManager=self.centralDataManager,
                                                            signalManager=self.signalManager)
        sensitivityTab = SensitivityTab(centralDataManager=self.centralDataManager)
        uncertaintyTab = UncertaintyTab(centralDataManager=self.centralDataManager)

        # add Reaction tab to the tab manager
        self.tabManager.addTab(reactionsTab, "ReactionsTab")
        # add other if necessary e.g.:
        # self.tabManager.addTab(generalSystemDataTab, "GeneralSystemDataTab")


        # Add tabs to the QTabWidget
        tabWidget.addTab(welcomeTab, "Welcome")
        tabWidget.addTab(projectDescriptionTab, "Project Description")
        tabWidget.addTab(generalSystemDataTab, "General System Data")
        tabWidget.addTab(componentsTab, "Chemical Components")
        tabWidget.addTab(reactionsTab, "Reactions")
        tabWidget.addTab(utilityTab, "Utilities")
        tabWidget.addTab(superstructureMappingTab, "Superstructure Mapping")
        tabWidget.addTab(sensitivityTab, "Sensitivity")
        tabWidget.addTab(uncertaintyTab, "Uncertainty")
        if self.ProjectName != '':
            self.setWindowTitle(f'OUTDOOR 2.0 - {self.ProjectName}')

    def generateSuperstructureObject(self):
        """
        Generate the superstructure object from the data in the centralDataManager
        :return:
        """

        # before generating the superstructure object,save the project if the save path is established!
        if self.ProjectPath != '':
            self.saveFile()

        constructorSuperstructure = ConstructSuperstructure(self.centralDataManager)
        if constructorSuperstructure.warningMessage:
            self.logger.error("please be mindful of the following warning Message: {}".format(constructorSuperstructure.warningMessage))
        elif constructorSuperstructure.errorMessage:
            self.logger.error("You must fix the issues from the pop-ups before you can save the superstructure object")
            return


        superstructure = constructorSuperstructure.get_superstructure()

        # save the object in the same location as the project file
        # with the name of the project file + '_superstructure'
        superstructurePath = self.ProjectPath.split('.')[0] + '_superstructure.pkl'
        with open(superstructurePath, 'wb') as file:
            pickle.dump(superstructure, file)

        self.logger.info("Superstructure Object Saved in: {}".format(superstructurePath))

    def calculateAllLCAs(self):
        """
        Instead of manually calculating LCAs as you model them, this does it all at once.
        :return:
        """
        # create a dialog widget so that we can extract the methodology we want to use to calculate the CF
        #dialog = MethodologyLcaDialog(self.centralDataManager)
        #if dialog.exec_() != QDialog.Accepted:
        #    return  # user cancelled

        # create an error message if the LCA methodology has not yet been DEFINED
        if not self.centralDataManager.technosphereDatabaseLCA:
            self._showErrorDialog(message="The options for the LCA calculation "
                                          "has not been set up yet. "
                                          "\n Please set up in the menu top left under LCA")


        LCAmethod = self.centralDataManager.methodSelectionLCA
        if LCAmethod:
            self.logger.info("The selected methodology is: {}".format(LCAmethod))
        else:
            self.logger.error("Error with error selection. terminating caculations")
            return # cancelled

        # perform the calculations
        calculator = LCACalculationMachine(self.centralDataManager)
        calculator.calculateAllLCAs(False)

        self.update()

    def printReferencesLCA(self):
        """
        Prints out the references used to calculate the impacts of the LCA to the consul
        """

        # Do calculations
        self.logger.info("Collecting LCA references..")
        biglist = self.centralDataManager.componentData + self.centralDataManager.wasteData + self.centralDataManager.utilityData
        inventory = {}

        self.outd = bw.Database('outdoor')

        # Rest of your calculation code...
        for component in biglist:
            componentReferences = {}
            componentName = "error"
            if len(component.LCA['exchanges']) > 0:

                try:
                    componentName = component.name
                    for exchange, dict in component.LCA['exchanges'].items():
                        reference = dict.get('Reference')
                        region = dict.get('Region')
                        componentReferences.update({'Reference': reference, 'Region': region})

                except Exception as e:
                    self.logger.error("The following error ocuured: ", e)

                inventory.update({componentName: componentReferences})

        for key, val in inventory.items():
            print(key, val)
        #print(inventory)

    def setUpLca(self):
        # create a dialog widget so that we can extract the methodology we want to use to calculate the CF
        dialog = MethodologyLcaDialog(self.centralDataManager)
        if dialog.exec_() != QDialog.Accepted:
            return  # user cancelled

    def _showErrorDialog(self, message, type='Critical', title='Error'):
        """
        Show an error dialog with the message provided.
        :param message: Message to show in the dialog
        """
        baseErrorMessage = "Error creating the superstructure object: \n"

        errorDialog = QMessageBox()
        if type == 'Critical':
            errorDialog.setIcon(QMessageBox.Critical)
        elif type == 'Warning':
            errorDialog.setIcon(QMessageBox.Warning)
        else:
            errorDialog.setIcon(QMessageBox.Information)

        errorDialog.setWindowTitle(title)
        errorDialog.setText(baseErrorMessage + message)
        errorDialog.exec_()


def checkFocus():
    """
     for debugging purposes, check which widget currently has the focus.
    """
    currentFocusWidget = QApplication.instance().focusWidget()
    if currentFocusWidget:
        print(f"Current focus widget: {currentFocusWidget.objectName()}")
    else:
        print("No widget currently has the focus.")
        currentFocusWidget = []
    return currentFocusWidget


def run_outdoor_interface(**kwargs):
    app = QApplication(sys.argv)
    main_window = MainWindow(**kwargs)
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=str, help="log level", default="DEBUG")
    args = parser.parse_args()

    kwargs = vars(args)
    run_outdoor_interface(**kwargs)
