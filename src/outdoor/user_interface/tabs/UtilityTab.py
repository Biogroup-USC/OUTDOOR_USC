import logging
import uuid

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import QWidget, QLabel, QTableWidget, QVBoxLayout, QTableWidgetItem, QMenu

from outdoor.user_interface.data.TemperatureDTO import TemperatureDTO
from outdoor.user_interface.data.UtilityDTO import UtilityDTO
from outdoor.user_interface.data.WasteTreatmentDTO import WasteTreatmentDTO
from outdoor.user_interface.dialogs.LcaButton import LcaButton
from outdoor.user_interface.utils.DoubleDelegate import DoubleDelegate


class UtilityTab(QWidget):
    def __init__(self, centralDataManager, parent=None):
        super().__init__(parent)
        # add the logger
        self.logger = logging.getLogger(__name__)

        # add the central data manager
        self.centralDataManager = centralDataManager
        self.utilityData: list[UtilityDTO] = centralDataManager.utilityData
        self.temperatureData: list[TemperatureDTO] = centralDataManager.temperatureData
        self.wasteData: list[WasteTreatmentDTO] = centralDataManager.wasteData
        # set the flag of adding a row to false
        self.addingRowFlag = False

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
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignTop)

        # Title for the component tab
        self.title = QLabel("Utility Data")
        self.title.setMaximumHeight(20)
        self.title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title)

        # Table for the component data
        self.utilitiesTable = QTableWidget()
        self.utilitiesColumns = ["Name", "Costs (€/MWh)", "CO2 Emissions (t/MWh)", "Fresh water depletion (t/MWh)",
                                 "LCA"]
        self.columnShortnames = ["name", "cost", "co2", "fwd", "LCA"]
        self.utilitiesTable.setColumnCount(len(self.utilitiesColumns))
        self.utilitiesTable.setHorizontalHeaderLabels(self.utilitiesColumns)

        # adjust the width of the columns
        self.utilitiesTable.setColumnWidth(0, 150)
        self.utilitiesTable.setColumnWidth(1, 230)
        self.utilitiesTable.setColumnWidth(2, 180)
        self.utilitiesTable.setColumnWidth(3, 210)
        self.utilitiesTable.setColumnWidth(4, 150)

        # self.utilitiesTable.setMaximumHeight(150)  #This is where the problem is when you wanna add new things

        self.temperatureTable = QTableWidget()
        self.temperatureColumns = ["Type", "Temperature °(C)", "Cost (€/MWh)"] # leave "LCA" out for now
        self.tshortNames = ["name", "temp", "cost",] # add "LCA a a later moment is appropriate"

        self.temperatureTable.setColumnCount(len(self.tshortNames))
        self.temperatureTable.setHorizontalHeaderLabels(self.temperatureColumns)
        for n in range(len(self.temperatureColumns)):
            self.temperatureTable.setColumnWidth(n, 110)

        self.wasteTable = QTableWidget()
        self.wasteColumns = ["Type", "Cost (€/t)", "LCA"]
        self.wshortNames = ["name", "cost", "LCA"]
        # add more waste managment types here! Propogates trought the whole program
        self.wasteManagementList = ["Incineration", "Landfill", "WWTP", "Other"]
        # add the list to the centralDataManager
        self.centralDataManager.setWasteManagementTypes(self.wasteManagementList)

        self.wasteTable.setColumnCount(len(self.wshortNames))
        self.wasteTable.setHorizontalHeaderLabels(self.wasteColumns)
        for n in range(len(self.wasteColumns)):
            self.temperatureTable.setColumnWidth(n, 110)


        # Set validators for the numeric columns using a custom delegate class
        self.doubleDelegate = DoubleDelegate(self.utilitiesTable)
        self.doubleDelegateTemp = DoubleDelegate(self.temperatureTable)
        self.doubleDelegateWaste = DoubleDelegate(self.wasteTable)
        # self.doubleValidator = QDoubleValidator(0.00, 9999.99, 2)

        # save if something is changed in the table
        self.utilitiesTable.itemChanged.connect(self.saveData)
        self.temperatureTable.itemChanged.connect(self.saveData)
        self.wasteTable.itemChanged.connect(self.saveData)

        # Add the table to the layout
        self.layout.addWidget(self.utilitiesTable)

        self.tempTitle = QLabel("Temperature Data")
        self.tempTitle.setMaximumHeight(20)
        self.tempTitle.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.tempTitle)

        self.layout.addWidget(self.temperatureTable)
        # Ensure the widget can receive focus to detect key presses

        self.wasteTitle = QLabel("Waste Treatment Data")
        self.wasteTitle.setMaximumHeight(20)
        self.wasteTitle.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.wasteTitle)
        self.layout.addWidget(self.wasteTable)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setLayout(self.layout)

        # if the central data manager has data, import it
        if len(self.utilityData) == 0:
            for name in ['Electricity', 'Heat', 'Chilling']:
                self.utilityData.append(UtilityDTO(utility_name=name, uid=str(uuid.uuid4())))
        if len(self.temperatureData) == 0:
            for name in ["Superheated steam", "High pressure steam", "Medium pressure steam", "Low pressure steam", "Cooling water"]:
                self.temperatureData.append(TemperatureDTO(temperatureName=name, uid=str(uuid.uuid4())))
        if len(self.wasteData) == 0:
            for name in self.wasteManagementList:
                self.wasteData.append(WasteTreatmentDTO(waste_name=name, uid=str(uuid.uuid4())))
        self.importData()


    def _addUtilityRow(self, data: UtilityDTO, rowPosition: int):
        # set the flag of adding a row to true
        self.addingRowFlag = True
        self.utilitiesTable.insertRow(rowPosition)
        for key, value in data.as_dict().items():
            if key in self.columnShortnames:
                index = self.columnShortnames.index(key)
                if key == "LCA":
                    if len(value['exchanges']) > 0 and data.calculated:
                        btn = LcaButton(self.utilitiesTable, data, centralDataManager=self.centralDataManager)
                        btn.setText("Defined")
                        btn.clicked.connect(btn.lcaAction)
                        btn.changeColorBnt()
                        self.utilitiesTable.setCellWidget(rowPosition, index, btn)
                    else:
                        btn = LcaButton(self.utilitiesTable, data, centralDataManager=self.centralDataManager)
                        btn.setText("Not Defined")
                        btn.clicked.connect(btn.lcaAction)
                        btn.changeColorBnt()
                        self.utilitiesTable.setCellWidget(rowPosition, index, btn)
                else:
                    insert = QTableWidgetItem(str(value))
                    insert.setFlags(insert.flags() | Qt.ItemIsEditable)
                    if key == 'name':
                        insert.setFlags(insert.flags() | ~Qt.ItemIsEditable)
                        insert.setBackground(Qt.lightGray)
                    if (key == 'cost') & (data.name == 'Heat'):
                        insert.setFlags(insert.flags() | ~Qt.ItemIsEditable)
                        insert.setBackground(Qt.lightGray)
                    self.utilitiesTable.setItem(rowPosition, index, insert)
        # set the flag of adding a row to false
        self.addingRowFlag = False

    def _addTemperatureRow(self, data: TemperatureDTO, rowPosition: int):
        # set the flag of adding a row to true
        self.addingRowFlag = True
        self.temperatureTable.insertRow(rowPosition)
        for key, value in data.as_dict().items():
            if key in self.tshortNames:
                index = self.tshortNames.index(key)
                if key == "LCA":
                    pass
                    # disable for the time being! not relavent yet!
                    # if len(value['exchanges']) > 0:
                    #     btn = LcaButton(self.temperatureTable, data)
                    #     btn.setText("Defined")
                    #     btn.clicked.connect(btn.lcaAction)
                    #     btn.changeColorBnt()
                    #     self.temperatureTable.setCellWidget(rowPosition, index, btn)
                    #     logging.debug(f"{rowPosition} - {index} - {key}")
                    # else:
                    #     btn = LcaButton(self.temperatureTable, data)
                    #     btn.setText("Not Defined")
                    #     btn.clicked.connect(btn.lcaAction)
                    #     btn.changeColorBnt()
                    #     self.temperatureTable.setCellWidget(rowPosition, index, btn)

                else:
                    insert = QTableWidgetItem(str(value))
                    insert.setFlags(insert.flags() | Qt.ItemIsEditable)
                    if key == 'name':
                        insert.setFlags(insert.flags() | ~Qt.ItemIsEditable)
                        insert.setBackground(Qt.lightGray)
                    self.temperatureTable.setItem(rowPosition, index, insert)
        # set the flag of adding a row to false
        self.addingRowFlag = False

    def _addWasteRow(self, data: WasteTreatmentDTO, rowPosition: int):
        # set the flag of adding a row to true
        self.addingRowFlag = True
        self.wasteTable.insertRow(rowPosition)
        for key, value in data.as_dict().items():
            if key in self.wshortNames:
                index = self.wshortNames.index(key)
                if key == "LCA":
                    if len(value['exchanges']) > 0 and data.calculated:
                        btn = LcaButton(self.wasteTable, data, centralDataManager=self.centralDataManager)
                        btn.setText("Defined")
                        btn.clicked.connect(btn.lcaAction)
                        btn.changeColorBnt()
                        # give the button a green
                        self.wasteTable.setCellWidget(rowPosition, index, btn)
                    else:
                        btn = LcaButton(self.wasteTable, data, centralDataManager=self.centralDataManager)
                        btn.setText("Not Defined")
                        btn.clicked.connect(btn.lcaAction)
                        btn.changeColorBnt()
                        self.wasteTable.setCellWidget(rowPosition, index, btn)

                else:
                    insert = QTableWidgetItem(str(value))
                    insert.setFlags(insert.flags() | Qt.ItemIsEditable)
                    if key == 'name':
                        insert.setFlags(insert.flags() | ~Qt.ItemIsEditable)
                        insert.setBackground(Qt.lightGray)
                    self.wasteTable.setItem(rowPosition, index, insert)
        # set the flag of adding a row to false
        self.addingRowFlag = False

    # def keyPressEvent(self, event):
    #     if event.key() == Qt.Key_Backspace | Qt.Key_Delete:
    #         selectedItems = self.utilitiesTable.selectedItems()
    #         if selectedItems:
    #             selectedRow = selectedItems[0].row()  # Get the row of the first selected item
    #             self.utilitiesTable.removeRow(selectedRow)
    #             target = [u for u in self.componentList if u.rowPosition == selectedRow][0]
    #             self.componentList.remove(target)
    #             for c in [u for u in self.componentList if u.rowPosition >= selectedRow]:
    #                 c.updateRow()
    #     else:
    #         super().keyPressEvent(event)
    #
    # def doubleClickEvent(self, item):
    #     print(item.row(), item.column())

    @pyqtSlot()
    def saveData(self):
        if not self.addingRowFlag:
            self.collectData()
            # # Save the data to the central data manager
            # self.centralDataManager.addData("utilityData")
            self.logger.debug("Save Utility data to the central data manager")

    def collectData(self):
        '''
        This is a truly unhinged way of doing this but here goes.
        So we have two arrays, one of the names of the columns in the table and one with the
        names of the properties on the DTOs that those coloumns refer to. The properties one is called
        'columnShortnames'. So what we do is we iterate through everything in the table. For every row, we step
        through the columns. We get our shortname index, "sindex" and then check if the column we're in
        is in the list we want to deal with. LCA deals with itself. So now, knowing the index of the shortname we can
        get it from the shortname list, and then we use the DTO's update field method with the shortname and the value
        to update. DTOs are expected to implement a method that updates every possible value this way.
        It's so we can dynamically update and change tables and their contents while minimizing rewriting.
        '''
        for row in range(self.utilitiesTable.rowCount()):
            edit = self.utilityData[row]
            for column in self.utilitiesColumns:
                sindex = self.utilitiesColumns.index(column)
                item = self.utilitiesTable.item(row, sindex)
                if column not in ['Name','LCA']:
                    edit.upadateField(self.columnShortnames[sindex], item.text())

        for row in range(self.temperatureTable.rowCount()):
            edit = self.temperatureData[row]
            for column in self.temperatureColumns:
                sindex = self.temperatureColumns.index(column)
                item = self.temperatureTable.item(row, sindex)
                if column not in ['Type', 'LCA']:
                    edit.upadateField(self.tshortNames[sindex], item.text())

        for row in range(self.wasteTable.rowCount()):
            edit = self.wasteData[row]
            for column in self.wasteColumns:
                sindex = self.wasteColumns.index(column)
                item = self.wasteTable.item(row, sindex)
                if column not in ['Type', 'LCA']:
                    edit.upadateField(self.wshortNames[sindex], item.text())

    def importData(self):
        try:
            rows = len(self.utilityData)
            for n in range(rows):
                self._addUtilityRow(self.utilityData[n], n)
        except Exception as e:
            self.logger.info("Probably just trying to import an empty utilitydata list.",e)
        try:
            rows = len(self.temperatureData)
            for n in range(rows):
                self._addTemperatureRow(self.temperatureData[n], n)
            # it only gets here if there aren't any saved rows, like in a new project
        except Exception as e:
            self.logger.info("Honestly I can't fathom how it would get to this error. Congartulations.", e)
        try:
            rows = len(self.wasteData)
            for n in range(rows):
                self._addWasteRow(self.wasteData[n], n)
        except Exception as e:
            self.logger.info("Waste had a problem.",e)
            pass

    def contextMenuEvent(self, event):
        # Create a context menu
        context_menu = QMenu(self)

        # Add actions for deleting rows from both tables
        deleteAction = context_menu.addAction("Delete Row")

        # Execute the context menu and get the selected action
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        # Determine which table was clicked
        component_pos = self.utilitiesTable.viewport().mapFrom(self, event.pos())

        if self.utilitiesTable.geometry().contains(event.pos()) and action == deleteAction:
            # Determine the row that was clicked in the reactants table
            row = self.utilitiesTable.rowAt(component_pos.y())
            if row != -1:
                self.utilitiesTable.removeRow(row)

            # update the dto list containing the chemical components
            self.centralDataManager.updateData('componentData', row)
            # todo make a consistency check to see if the chemical component is used in any reaction or unit operation
            # open a dialog if the component is used in a reaction or unit operation
