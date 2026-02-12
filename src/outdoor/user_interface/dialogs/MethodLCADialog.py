from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
import bw2data as bd
import logging
#import bw2io as bi
#import multiprocessing


class MethodologyLcaDialog(QDialog):
    def __init__(self, centralDataManager):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.centralDataManager = centralDataManager
        self.setWindowTitle("Select LCA Database")
        self.setFixedWidth(420)
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

        self.selection = None  # will hold the final method choice

        layout = QVBoxLayout(self)

        # existing Bright way projects can already exits, see if you can find them
        layout.addWidget(QLabel("Choose a existing Brightway project:"))
        self.comboProjects = QComboBox()
        self.optionsProjects = [p.name for p in bd.projects]
        self.comboProjects.addItems(self.optionsProjects)
        layout.addWidget(self.comboProjects)

        layout.addWidget(QLabel("Select database (technosphere):"))
        self.comboDatabasesTechno = QComboBox()
        layout.addWidget(self.comboDatabasesTechno)

        layout.addWidget(QLabel("Select database (Biosphere):"))
        self.comboDatabasesBio = QComboBox()
        layout.addWidget(self.comboDatabasesBio)

        layout.addWidget(QLabel("Select methadology:"))
        self.comboMethodology = QComboBox()
        # Visible labels (what the user sees)
        self.default_method_labels = ["ReCiPe 2016 v1.03 midpoint + endpoint (H)",
                                      "ReCiPe 2016 v1.1 midpoint + endpoint (H)",
                                      "ReCiPe 2016 v1.03 [bio=1] (custom: biogenic = fossil)",
                                      "IPCC 2013", ]
        self.comboMethodology.addItems(self.default_method_labels)
        layout.addWidget(self.comboMethodology)

        # ---- Wire project selection -> methodology list ----
        self.comboProjects.currentIndexChanged.connect(self._bd_project_changed)

        # buttons
        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)

    def _accept(self):
        oldDataBaseEIDB = self.centralDataManager.technosphereDatabaseLCA
        oldDataBaseBioDB = self.centralDataManager.biosphereDatabaseLCA

        # collect relevant data
        self.technosphereDatabase = self.comboDatabasesTechno.currentText()
        self.biosphereDatabase = self.comboDatabasesBio.currentText()
        self.selection = self.comboMethodology.currentText()
        # add all the data to the central data-manager
        self.centralDataManager.bdProjectName = self.comboProjects.currentText()
        self.centralDataManager.technosphereDatabaseLCA = self.technosphereDatabase
        self.centralDataManager.biosphereDatabaseLCA = self.biosphereDatabase
        self.centralDataManager.methodSelectionLCA = self.selection

        if oldDataBaseEIDB != self.centralDataManager.technosphereDatabaseLCA:
            # todo 1 create a warning that all the LCA data from the central datamanager will be wipeout!
            # todo 2 give the option to opt out!
            # todo 3 make sure when opening LCA dialog that a database exists to read from, otherwise show a error
            #  widget explaining you need to set up your databases you want to search in
            # todo 4, now link it all up
            pass

        # accept and close the window
        self.accept()

    def use_biogenic_as_one(self) -> bool:
        """Return True if custom [bio=1] is chosen."""
        return self.selection is not None and self.selection.startswith("ReCiPe 2016 v1.03 [bio=1]")

    def _bd_project_changed(self):
        """Update methodology combo based on selected Brightway project."""

        # get the ProjectName
        projectName = self.comboProjects.currentText()
        bd.projects.set_current(projectName)
        # Build list of methods available in that project
        databaseTechno, databaseBio = self._get_valid_databases_from_project(projectName=projectName)
        self._set_database_items(databaseTechno, databaseBio)

    def _set_database_items(self, technosfeerDatabases, biosfeerDatabases):
        """Replace comboMethodology items without triggering weird signals."""
        self.comboDatabasesTechno.blockSignals(True)
        self.comboDatabasesBio.blockSignals(True)
        try:
            # current = self.comboDatabases.currentText()
            self.comboDatabasesTechno.clear()
            self.comboDatabasesTechno.addItems(technosfeerDatabases)
            self.comboDatabasesBio.clear()
            self.comboDatabasesBio.addItems(biosfeerDatabases)
        except:
            self.logger.error("failed to set database items")
            self.comboDatabasesTechno.addItems([])
            self.comboDatabasesBio.addItems([])

        finally:
            self.comboDatabasesTechno.blockSignals(False)
            self.comboDatabasesBio.blockSignals(False)

    def _get_valid_databases_from_project(self, projectName):
        # Check if databases have data
        valid_databases = []
        databaseNames = []
        for dbName in bd.databases:
            db = bd.Database(dbName)
            size = len(db)
            if size > 0:
                valid_databases.append((dbName, size))
                databaseNames.append(dbName)

        if valid_databases:
            self.logger.debug(f"Project '{projectName}' has functional databases:")
            for dbName, size in valid_databases:
                self.logger.debug(f"  - {dbName}: {size} datasets")
        else:
            self.logger.warning(f"Project '{projectName}' has empty databases")

        # clean up the names in the database
        technosfeerDatabases = []
        biosfeerDatabases = []

        for n in databaseNames:
            if 'biosphere' in n:
                biosfeerDatabases.append(n)
            elif 'outdoor' in n:
                continue
            else:
                technosfeerDatabases.append(n)

        return technosfeerDatabases, biosfeerDatabases


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
