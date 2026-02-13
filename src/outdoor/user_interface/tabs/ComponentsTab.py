import logging
import uuid

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QPushButton, QLabel, QTableWidgetItem, QMenu
from outdoor.user_interface.tabs.ReactionTab import ReactionsTab
from outdoor.user_interface.data.ComponentDTO import ComponentDTO
from outdoor.user_interface.dialogs.LcaButton import LcaButton
from outdoor.user_interface.utils.DoubleDelegate import DoubleDelegate
from outdoor.user_interface.data.ProcessDTO import ProcessType
# retrive the logger
from outdoor.user_interface.utils.OutdoorLogger import outdoorLogger


class ComponentsTab(QWidget):
    """
    This class creates a tab for the chemical components and related data (e.g., molar weight, LHV, heat capacity, etc.)
    This is the tab that defines each chemical component and its properties used throught the flow sheet.
    """

    def __init__(self, centralDataManager, tabManager, parent=None):
        super().__init__(parent)
        # add the logger
        self.logger = logging.getLogger(__name__)

        # add the central data manager
        self.centralDataManager = centralDataManager
        self.componentList: list[ComponentDTO] = centralDataManager.componentData

        # add the tab manager
        self.tabManager = tabManager

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

        # Title for the component tab
        self.title = QLabel("Components and related Data")
        self.title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title)

        # Table for the component data
        self.componentsTable = QTableWidget()
        self.componentsTable.setColumnCount(5)
        self.columnsList = [
            "Component", "Lower heating Value (kWh/kg)",
            "Heat capacity (kJ/kg/K)", "Molecular weight (g/mol)",
            "LCA Data"
        ]
        self.columnsShortnames = ["name", "lowerHeat", "heatCapacity", "molecularWeight", "LCA"]
        self.componentsTable.setHorizontalHeaderLabels(self.columnsList)

        # adjust the width of the columns
        self.componentsTable.setColumnWidth(0, 150)
        self.componentsTable.setColumnWidth(1, 230)
        self.componentsTable.setColumnWidth(2, 180)
        self.componentsTable.setColumnWidth(3, 210)
        self.componentsTable.setColumnWidth(4, 150)
        self.componentsTable.itemDoubleClicked.connect(self.doubleClickEvent)

        # Set validators for the numeric columns using a custom delegate class
        self.doubleDelegate = DoubleDelegate(self.componentsTable)
        # self.doubleValidator = QDoubleValidator(0.00, 9999.99, 2)

        # Variable to store old value
        self.oldValue = None
        # save if something is changed in the table
        self.componentsTable.itemChanged.connect(self.handleItemChanged) # saves and updates data
        self.componentsTable.currentItemChanged.connect(self.trackOldValue)

        # Add the table to the layout
        self.layout.addWidget(self.componentsTable)
        # Add Row Button
        self.addRowButton = QPushButton("Add Chemical Component")
        self.addRowButton.clicked.connect(self.addComponentRow)
        self.layout.addWidget(self.addRowButton)


        # Ensure the widget can receive focus to detect key presses
        self.setFocusPolicy(Qt.StrongFocus)
        self.setLayout(self.layout)

        # if the central data manager has data, import it
        self.importData()

        # if self.componentsTable.rowCount() == 0:
        #     self.addComponentRow()

    def addComponentRow(self, data: ComponentDTO | None = None):
        """
        This method adds a row to the table for the chemical components
        :param data: of type ComponentDTO, the data to be added to the table, can be None
        :return:
        """
        # set the flag of adding a row to true
        self.addingRowFlag = True

        rowPosition: int
        if data is None or not isinstance(data, ComponentDTO):
            rowPosition = self.componentsTable.rowCount()
            uid = uuid.uuid4().__str__()
            data = ComponentDTO(rowPosition, uid)
            self.componentList.append(data)
        else:
            rowPosition = data.rowPosition
        self.componentsTable.insertRow(rowPosition)

        for key, value in data.as_dict().items():
            if key in self.columnsShortnames:
                index = self.columnsShortnames.index(key)
                if key == "LCA":
                    if len(value['exchanges']) > 0 and data.calculated: # if there are results, the LCA is defined
                        btn = LcaButton(self.componentsTable, data, centralDataManager=self.centralDataManager)
                        btn.setText("Defined")
                        btn.clicked.connect(btn.lcaAction)
                        # give the button a green button color in the style of the sheet
                        btn.changeColorBnt()
                        self.componentsTable.setCellWidget(rowPosition, index, btn)
                    else:
                        btn = LcaButton(self.componentsTable, data, centralDataManager=self.centralDataManager)
                        btn.setText("Not Defined")
                        btn.clicked.connect(btn.lcaAction)
                        # give the button a yellow button color in the style of the sheet
                        btn.changeColorBnt()
                        self.componentsTable.setCellWidget(rowPosition, index, btn)
                else:
                    insert = QTableWidgetItem(value)
                    insert.setFlags(insert.flags() | Qt.ItemIsEditable)
                    self.componentsTable.setItem(rowPosition, index, insert)

        # set the flag of adding a row to false
        self.addingRowFlag = False


    def doubleClickEvent(self, item):
        print(item.row(), item.column())

    def handleItemChanged(self, item):
        """Handle when an item is changed."""
        if not self.addingRowFlag:
            self.saveData()

            if item.column() == 0:  # only bothered to track changes in the first column (chemical name)
                # get the old and new name of the chemical component
                oldValue = self.oldValue
                newValue = item.text()

                # Reset old value
                self.oldValue = newValue

                ## You can call updateData or saveData here
                self.updateData(oldValue, newValue)

    def saveData(self):
        if not self.addingRowFlag:
            self.collectData()
            # Save the data to the central data manager
            self.centralDataManager.addData("chemicalComponentsData", self.componentList)
            self.logger.debug("Data saved components tab to central data manager")

    def updateData(self, oldChemicalName, newChemicalName):
        if not self.addingRowFlag:

            # go over all the reaction dto's
            if self.centralDataManager.reactionData:
                for reactionDTO in self.centralDataManager.reactionData:
                    # get reactants and products
                    changeFlag = False
                    for component_type in ['reactants', 'products']:
                        components = getattr(reactionDTO, component_type)
                        if oldChemicalName in components:
                            changeFlag = True
                            components[newChemicalName] = components.pop(oldChemicalName)
                            setattr(reactionDTO, component_type, components)
                    if changeFlag:
                        # update the reaction equation
                        reactionDTO.makeStringEquation()
                        # now update the reaction tab by calling the editReaction method without opening the dialog
                        # so the correct reaction equations are shown
                        # self.tabManager.reactionsTab.editReaction(row=reactionDTO.rowPosition, executeDialog=False)

            # go over the unit data
            for dto in self.centralDataManager.unitProcessData.values():
                # only if it has filled in data, go ahead and modify
                if dto.dialogData:
                    # if the dto is an input
                    if dto.type.value == 0:
                        compositionList = [componentsTuple[0] for componentsTuple in dto.dialogData['components']]
                        if oldChemicalName in compositionList:
                            # change the old name with the new name
                            index = compositionList.index(oldChemicalName)
                            #dto.dialogData['components'][index][0] = newChemicalName
                            compositionFraction = dto.dialogData['components'][index][1]
                            newTuple = (newChemicalName, compositionFraction)
                            dto.dialogData['components'][index] = newTuple

                    if dto.type.value >= 1 and dto.type.value < 7: # if anything but input output or distribution
                        lists2Change = ['Components Equipment Costs',
                                       'Components Energy Consumption',
                                       'Components Chilling Consumption',
                                       'Components Heat Consumption 1',
                                       'Components Heat Consumption 2',
                                       'Components Flow1',
                                       'Components Flow2', ]  # separation fraction needs special attention

                        for changeList in lists2Change:
                            compositionList = dto.dialogData[changeList]
                            if oldChemicalName in compositionList:
                                # change the old name with the new name
                                # Change the old name with the new name
                                index = compositionList.index(oldChemicalName)
                                compositionList[index] = newChemicalName
                                dto.dialogData[changeList] = compositionList

                        splitDialogData = dto.dialogData['Separation Fractions']
                        componentsList = [splitData['Component'] for splitData in splitDialogData]
                        if oldChemicalName in componentsList:
                            index = componentsList.index(oldChemicalName)
                            splittingDict = splitDialogData[index]
                            splittingDict['Component'] = newChemicalName
                            dto.dialogData['Separation Fractions'][index] = splittingDict

                        # Update material flow data, where chemical names are also stored
                    materialFlow = dto.materialFlow
                    if materialFlow:  # Protect against empty dictionaries
                        for dict in materialFlow.values():
                            if dict:  # Protect against empty dictionaries
                                for nestedDict in dict.values():
                                    # Collect keys to update
                                    keys_to_update = [key for key in nestedDict.keys() if key == oldChemicalName]
                                    # Update the keys
                                    for key in keys_to_update:
                                        nestedDict[newChemicalName] = nestedDict.pop(key)
                                        # print('Material flow updated!')

                    if dto.type.value in [2, 4, 5, 6]:  # stoichiometric, or the generator types
                        # update the conversion factors
                        reactions = dto.dialogData['Reactions']
                        for reactionTuple in reactions:
                            if oldChemicalName == reactionTuple[-1]:  # if the old name is the main conversion
                                index = reactions.index(reactionTuple)
                                reactionTuple = list(reactionTuple)  # Ensure the tuple is mutable
                                reactionTuple[-1] = newChemicalName
                                reactions[index] = tuple(reactionTuple)  # Convert back to tuple if needed
                        dto.dialogData['Reactions'] = reactions

                        #lists2Change.append('Reactions')

                    if dto.type.value == 3: # if it is a yield type
                        # update the yield components
                        inertComponents = dto.dialogData['Inert Components']
                        product = dto.dialogData['Product']
                        if oldChemicalName in inertComponents:
                            index = inertComponents.index(oldChemicalName)
                            inertComponents[index] = newChemicalName
                            dto.dialogData['Inert Components'] = inertComponents
                        if oldChemicalName == product:
                            dto.dialogData['Product'] = newChemicalName

            self.logger.info("component Data updated in the centralDataManager and relevant tabs")

    def trackOldValue(self, current, previous):
        """Track the old value of the currently selected item."""
        if current and current.column() == 0:  # Check if the item is in the first row
            self.oldValue = current.text()
            # print(self.oldValue) # for debugging

    def collectData(self):
        # Collect data from the table
        for row in range(self.componentsTable.rowCount()):
            edit = [u for u in self.componentList if u.rowPosition == row][0]
            rowData = []
            for column in self.columnsList:
                sindex = self.columnsList.index(column)
                item = self.componentsTable.item(row, sindex)
                if column in ["Component", "Lower heating Value (kWh/kg)", "Heat capacity (kJ/kg/K)", "Molecular weight (g/mol)"]:
                    edit.upadateField(self.columnsShortnames[sindex], item.text())
                if column == "LCA":
                    # this is handled inside the DTO
                    pass

    def sortComponentDTO(self,dto: ComponentDTO):
        return dto.rowPosition
    def importData(self):
        try:
            #tabledata = self.centralDataManager.data["chemicalComponentsData"]
            tabledata = self.componentList
            for row in tabledata:
                self.addComponentRow(row)
        except Exception as e:
            raise e
            pass
            # it only gets here if there aren't any saved rows, like in a new project

    def contextMenuEvent(self, event):
        # Create a context menu
        context_menu = QMenu(self)

        # Add actions for deleting rows from both tables
        deleteAction = context_menu.addAction("Delete Row")

        # Execute the context menu and get the selected action
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        # Determine which table was clicked
        component_pos = self.componentsTable.viewport().mapFrom(self, event.pos())

        if self.componentsTable.geometry().contains(event.pos()) and action == deleteAction:
            # Determine the row that was clicked in the reactants table
            row = self.componentsTable.rowAt(component_pos.y())
            if row != -1:
                self.componentsTable.removeRow(row)

            # update the dto list containing the chemical components
            self.centralDataManager.updateData('componentData', row)
            # open a dialog if the component is used in a reaction or unit operation

