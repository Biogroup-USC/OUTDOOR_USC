import difflib
import hashlib
import json
import logging
import sys
from types import TracebackType

import bw2calc as bc
import bw2data as bw
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem

from outdoor.user_interface.data.OutdoorDTO import OutdoorDTO
from outdoor.user_interface.utils.OutdoorLogger import outdoorLogger


class LCADialog(QDialog):
    """
    Opens a dialog to set the input parameters for the input icon. The dialog allows the user to set the source name,
    price input, components, CO2 emission factor, lower limit, and upper limit. The components are entered in a table
    format with two columns: Component Name and % Composition. The user can add multiple rows to enter multiple
    components and their composition in the feedstock.
    """

    def __init__(self, initialData: OutdoorDTO):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initializing LCADialog for {initialData.name} with UID {initialData.uid}")
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
        self.setWindowTitle("LCA Lookup")
        self.setGeometry(100, 100, 600, 900)  # Adjust size as needed
        self.lca_checksum = ""

        bwProjectNames = []
        for project in bw.projects:
            projectName = project.name
            bwProjectNames.append(projectName)

        if not bwProjectNames:
            self.logger.error("No Brightway projects found. Please Install the databases.")
            # close the dialog
            self.close()

        if "outdoor" in bwProjectNames:
            bw.projects.set_current("outdoor")
            self.eidb = bw.Database(self.centralDataManager.technosphereDatabaseLCA)
            self.bios = bw.Database(self.centralDataManager.biosphereDatabaseLCA)
            # check the size of the databases
            if len(self.eidb) < 1 and len(self.bios) < 1:
                self.logger.warning("Project 'outdoor' has empty databases.")
                self.logger.info("Attempting to register the with an other database.")

                bwProjectNames.remove('outdoor')
                for projectName in bwProjectNames:
                    try:
                        bw.projects.set_current(projectName)
                        self.eidb = bw.Database(self.centralDataManager.technosphereDatabaseLCA)
                        self.bios = bw.Database(self.centralDataManager.biosphereDatabaseLCA)
                        if len(self.eidb) > 0 and len(self.bios) > 0:
                            self.logger.info(f"Found valid Ecoinvent databases in project '{projectName}'.")
                            break

                    except Exception as e:
                        self.logger.error(f"Could not setup a brightway project {projectName}: {e}")
                        self.logger.info("Make sure the Installation has been done correctly!!.")

        else:
            self.logger.warning("No Brightway project called 'outdoor' found. "
                                "Attempting to load databases from other projects in BrightWay.")

            for projectName in bwProjectNames:
                try:
                    bw.projects.set_current(projectName)
                    self.eidb = bw.Database(self.centralDataManager.technosphereDatabaseLCA)
                    self.bios = bw.Database(self.centralDataManager.biosphereDatabaseLCA)

                    if len(self.eidb) > 0 and len(self.bios) > 0:
                        self.logger.info(f"Found valid Ecoinvent database in project {projectName}.")
                        break

                except Exception as e:
                    self.logger.error(f"Could not setup a brightway project {projectName}: {e}")
                    self.logger.info("Make sure the Installation has been done correctly!!.")

        self.outd = bw.Database('outdoor')

        # previous version with no checks.
        # self.eidb = bw.Database(self.centralDataManager.technosphereDatabaseLCA)
        # self.bios = bw.Database(self.centralDataManager.biosphereDatabaseLCA)
        # self.outd = bw.Database('outdoor')

        try:
            self.outd.register()
        except Exception as e:
            # Already registered outdoor db
            pass
        layout = QVBoxLayout(self)
        self.dto = initialData
        # Lookup name
        layout.addWidget(QLabel("Search term:"))
        self.searchLine = QLineEdit(self)
        layout.addWidget(self.searchLine)

        # Lookup region
        layout.addWidget(QLabel("Preferred region (ISO):"))
        self.regionLine = QLineEdit("RER")
        layout.addWidget(self.regionLine)

        # Search button
        self.searchButton = QPushButton("Search", self)
        self.searchButton.clicked.connect(self.search)
        layout.addWidget(self.searchButton)

        # Search table
        self.searchColumns = ["Reference", "Unit", "Activity", "Region", "ID"]
        layout.addWidget(QLabel("Search Results:"))
        self.componentsTable = QTableWidget(0, len(self.searchColumns), self)  # Initial rows, 2 columns
        self.componentsTable.setHorizontalHeaderLabels(self.searchColumns)
        self.componentsTable.horizontalHeader().setStretchLastSection(True)
        self.componentsTable.verticalHeader().setVisible(False)

        self.componentsTable.setEditTriggers(self.componentsTable.NoEditTriggers)
        self.componentsTable.setSelectionMode(self.componentsTable.MultiSelection)
        self.componentsTable.setSelectionBehavior(self.componentsTable.SelectRows)
        layout.addWidget(self.componentsTable)

        # Button to put selection into processes table
        self.addRowButton = QPushButton("Add to Process", self)
        self.addRowButton.clicked.connect(self.addLCAProcess)
        layout.addWidget(self.addRowButton)

        # Processes table
        self.lcaColumns = ["Demand", "Unit", "Region", "Reference", "ID"]
        self.selectedProcessesTable = QTableWidget(0, 5, self)
        self.selectedProcessesTable.setHorizontalHeaderLabels(self.lcaColumns)
        self.selectedProcessesTable.horizontalHeader().setStretchLastSection(True)
        self.selectedProcessesTable.verticalHeader().setVisible(False)
        layout.addWidget(QLabel("Processes:"))
        layout.addWidget(self.selectedProcessesTable)

        # persistButton = QPushButton("Persist", self)
        # persistButton.clicked.connect(self.persistProcesses)
        # layout.addWidget(persistButton)

        saveButton = QPushButton("Save Inventory", self)
        saveButton.clicked.connect(self.persistLCA)
        layout.addWidget(saveButton)

        calculateButton = QPushButton("Calculate LCA", self)
        calculateButton.clicked.connect(self.calculateLCA)
        layout.addWidget(calculateButton)
        # for the time being, disable the calculate button.To account for LCA use the "Calculate all LCAs" in the
        # superstructure menu
        calculateButton.setEnabled(False)
        # make the button gray
        calculateButton.setStyleSheet("background-color: #cccccc; color: #666666;")

        self.loadInitialData()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backspace | Qt.Key_Delete:
            all = self.selectedProcessesTable.selectedItems()
            rows = []
            for item in all:
                if item.row() not in rows:
                    rows.append(item.row())
            for row in rows:
                index = self.lcaColumns.index("ID")
                id = self.selectedProcessesTable.item(row, index).text()
                self.dto.LCA['exchanges'].pop(id)
                self.selectedProcessesTable.removeRow(row)

    def search(self):
        self.componentsTable.setRowCount(0)
        name = self.searchLine.text()
        location = self.regionLine.text()
        loc_results = [m for m in self.eidb if name in m['name'] and location in m['location']]
        self.addRowToTable(Type="Blank", Head="Preferred Region", Table="Search")
        for item in sorted(loc_results, key=lambda x: difflib.SequenceMatcher(None, x['name'], name).ratio(),
                           reverse=True):
            self.addRowToTable(Reference=item['name'], Unit=item['unit'], Activity=item['type'],
                               Region=item['location'], ID=item['code'], Table="Search")
        gen_results = [m for m in self.eidb if name in m["name"] and location not in m["location"]]
        self.addRowToTable(Type="Blank", Head="Non-preferred Regions", Table="Search")
        for item in sorted(gen_results, key=lambda x: difflib.SequenceMatcher(None, x['name'], name).ratio(),
                           reverse=True):
            self.addRowToTable(Reference=item['name'], Unit=item['unit'], Activity=item['type'],
                               Region=item['location'], ID=item['code'], Table="Search")
        self.addRowToTable(Type="Blank", Head="Biosphere", Table="Search")
        biosphere_results = [m for m in self.bios if name in m['name']] + [m for m in self.bios if
                                                                           name.capitalize() in m['name']]
        for item in sorted(biosphere_results, key=lambda x: difflib.SequenceMatcher(None, x['name'], name).ratio(),
                           reverse=True):
            self.addRowToTable(Reference=item['name'], Unit=item['unit'], Activity=item['type'],
                               Region=str(item['categories']), ID=item['code'], Table="Search")

        self.logger.info(f"Search on {name} found:\n{len(loc_results)} in {location}."
                         f"\n{len(gen_results)} in other locations"
                         f"\n{len(biosphere_results)} in biosphere")

    def addRowToTable(self, **kwargs):
        rowPosition = 0
        match kwargs["Table"]:
            case "Search":
                columns = self.searchColumns
                rowPosition = self.componentsTable.rowCount()
                table = self.componentsTable
            case "LCA":
                columns = self.lcaColumns
                rowPosition = self.selectedProcessesTable.rowCount()
                table = self.selectedProcessesTable
            case _:
                self.logger.error("Something is wrong with your table.")
                return
        table.insertRow(rowPosition)
        if "Type" in kwargs:
            if kwargs["Type"] == "Blank":
                for col in columns:
                    index = columns.index(col)
                    insert = QTableWidgetItem(kwargs["Head"]) if index == 0 else QTableWidgetItem("---")
                    insert.setBackground(QColor(218, 222, 227))
                    insert.setFlags(Qt.NoItemFlags)
                    table.setItem(rowPosition, index, insert)
                return

        for item in kwargs.items():
            if item[0] in columns:
                col = columns.index(item[0])
                insert = QTableWidgetItem(item[1])
                insert.setFlags(insert.flags() | Qt.ItemIsSelectable)  # Ensure the item is selectable but not editable
                table.setItem(rowPosition, col, insert)

    def addLCAProcess(self):
        selectedItems = self.componentsTable.selectedItems()
        for item in selectedItems:
            if item.column() == 4:
                if item.text() not in self.dto.LCA['exchanges']:
                    self.dto.LCA['exchanges'][item.text()] = {
                        "Reference": self.componentsTable.item(item.row(), 0).text(),
                        "Unit": self.componentsTable.item(item.row(), 1).text(),
                        "Region": self.componentsTable.item(item.row(), 3).text(),
                        "Demand": "0",
                        "Parameter": "bw_param_name",
                        "Type": self.componentsTable.item(item.row(), 2).text(),
                    }
                    self.addRowToTable(Demand=self.dto.LCA['exchanges'][item.text()]["Demand"],
                                       Unit=self.dto.LCA['exchanges'][item.text()]["Unit"],
                                       Region=self.dto.LCA['exchanges'][item.text()]["Region"],
                                       Reference=self.dto.LCA['exchanges'][item.text()]["Reference"],
                                       ID=item.text(),
                                       Table="LCA")
        self.componentsTable.clearSelection()

    def loadInitialData(self):
        self.logger.debug("Loading initial data.")
        try:
            for key, value in self.dto.LCA['exchanges'].items():
                self.addRowToTable(Demand=value["Demand"], Unit=value["Unit"], Region=value["Region"], Reference=value["Reference"], ID=key,
                                   Table="LCA")
            self.lca_checksum = hashlib.sha256(json.dumps(self.dto.LCA['exchanges'],sort_keys=True).encode()).hexdigest()
        except KeyError as e:
            self.logger.debug("No initial data.")
        self.logger.debug("LCA checksum is: " + self.lca_checksum)

    def persistLCA(self):
        try:
            exist = len([m for m in self.outd if m["code"] == self.dto.uid]) > 0
            if not exist:
                process = {
                    "name": self.dto.name,
                    "unit": "unit",
                }
                self.outd.new_activity(self.dto.uid, **process).save()
                act = self.outd.search(self.dto.uid)[0]
                act.new_exchange(
                    input=act,
                    amount=1,
                    type='production',
                ).save()

            act = self.outd.search(self.dto.uid)[0]
            self.logger.debug(f"Persisting LCA data for {self.dto.name} with BW code {act['code']}")
            ext_list = []
            for row in range(self.selectedProcessesTable.rowCount()):
                demand = self.selectedProcessesTable.item(row, 0).text()
                id = self.selectedProcessesTable.item(row, 4).text()
                self.dto.LCA['exchanges'][id]["Demand"] = demand
            for ex in act.exchanges():
                if ex["type"] != "production":
                    ex.delete()
            for id, dic in self.dto.LCA['exchanges'].items():
                if "process" in dic["Type"]:
                    ex = [m for m in self.eidb if m['code'] == id][0]
                    ext_list.append((ex, dic["Demand"], dic["Unit"], dic["Type"]))
                else:
                    ex = [m for m in self.bios if m['code'] == id][0]
                    ext_list.append((ex, dic["Demand"], dic["Unit"], dic["Type"]))

            for tup in ext_list:
                ex = tup[0]
                act.new_exchange(
                    input=(ex['database'], ex['code']),
                    amount=float(tup[1]),
                    unit=ex['unit'],
                    type="biosphere" if ex['database'] == "biosphere3" else "technosphere",
                ).save()
            act.save()
            self.logger.info("Inventory saved.")

            # close the dialog
            self.accept()

        except Exception as e:
            if type(e) is IndexError:
                self.logger.warning("Define the name for the chemical first before saving for Uuid:", self.dto.uid)
            else:
                self.logger.error(e, e.with_traceback(sys.exc_info()[2]))

    def calculateLCA(self):
        self.logger.info("Calculation beginning. Please wait, this may take a moment.")
        midpoint = [m for m in bw.methods if
                    "ReCiPe 2016 v1.03, midpoint (H)" in str(m) and not "no LT" in str(m)]
        endpoints = [m for m in bw.methods if
                     "ReCiPe 2016 v1.03, endpoint (H)" in str(m) and not "no LT" in str(m) and "total" in str(m)]
        methodconfs = midpoint + endpoints
        try:
            activ = [m for m in self.outd if m['code'] == self.dto.uid][0]

            calc_setup = {"inv": [{activ:1}], "ia": methodconfs}
            bw.calculation_setups['setup'] = calc_setup
            mlca = bc.MultiLCA("setup")
            indic = []
            for f in mlca.func_units:
                indic.append(str(f).split('\'')[1])

            cols = []
            for c in mlca.methods:
                cols.append(c[3])

            dfresults = pd.DataFrame(mlca.results, columns=cols, index=indic).to_dict()
            for n, v in dfresults.items():
                for e in v.items():
                    self.dto.LCA['Results'][n.split('(')[0]] = e[1]
                    self.logger.debug(f"Added {n.split('(')[0]} with value {e[1]}")

            self.logger.info("MLCA complete, saving results.")

            self.dto.calculated = True
        except Exception as e:
            self.logger.error(e, e.with_traceback(sys.exc_info()[2]))
            if type(e) is IndexError:
                self.logger.warning("Didn't find the uuid in bw:", self.dto.uid)
            self.dto.calculated = False

    def close(self):
        #TODO add a popup that says "woah honey you got a mismatch between this and brightway"
        #or like... automagically write to brightway on close? I dunno.
        test_sum = hashlib.sha256(json.dumps(self.dto.LCA['exchanges'], sort_keys=True).encode()).hexdigest()
        self.logger.debug(f"Testsum: {test_sum}")
        if test_sum != self.lca_checksum:
            self.logger.debug(
                f"Original LCA checksum: {self.lca_checksum} and new checksum: {test_sum} do not match, deleting impacts.")
            self.dto.LCA['Results'] = {}
            self.dto.calculated = False
