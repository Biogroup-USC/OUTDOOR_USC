import logging
import uuid

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QPushButton, QLabel, QTableWidgetItem, QMenu,
                             QDoubleSpinBox, QLineEdit)
from PyQt5.QtGui import QDoubleValidator


from outdoor.user_interface.data.SensitivityDTO import SensitivityDTO
# from outdoor.user_interface.utils.DoubleDelegate import DoubleDelegate
from outdoor.user_interface.utils.NonFocusableComboBox import NonFocusableComboBox as ComboBox
from outdoor.user_interface.data.ProcessDTO import ProcessType


class SensitivityTab(QWidget):
    """
    This class creates a tab for the chemical components and related data (e.g., molar weight, LHV, heat capacity, etc.)
    This is the tab that defines each chemical component and its properties used throught the flow sheet.
    """
    def __init__(self, centralDataManager, parent=None):
        super().__init__(parent)
        # add the logger
        self.logger = logging.getLogger(__name__)

        # add the central data manager
        self.centralDataManager = centralDataManager
        self.sensitivityList: list[SensitivityDTO] = centralDataManager.sensitivityData
        # self.crossSensitivityList: list[CrossSensitivityDTO] = centralDataManager.crossSensitivityData

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
        self.title = QLabel("Parameter Sensitivity")
        self.title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title)

        # Table for the component data
        self.sensitivityTable = QTableWidget()

        self.columnsList = ["Parameter Type", "Unit Process",
                            "Component", "Target Unit Process",
                            "Reaction", "Lower Bound", "Upper Bound", "Number of Steps"]

        self.columnsShortnames = ["parameterType", "unitUid",
                                  "componentName", "targetUnitProcess",
                                  "reactionUid", "lowerBound", "upperBound", "steps"]

        self.sensitivityTable.setColumnCount(len(self.columnsList))
        self.sensitivityTable.setHorizontalHeaderLabels(self.columnsList)

        # adjust the width of the columns
        self.sensitivityTable.setColumnWidth(0, 230)
        self.sensitivityTable.setColumnWidth(1, 230)
        self.sensitivityTable.setColumnWidth(2, 180)
        self.sensitivityTable.setColumnWidth(3, 210)
        self.sensitivityTable.setColumnWidth(4, 150)
        self.sensitivityTable.setColumnWidth(5, 180)
        self.sensitivityTable.setColumnWidth(6, 180)
        self.sensitivityTable.setColumnWidth(7, 180)


        # save if something is changed in the table, this is done by the wigets in the table itself
        # disconnect the signal to avoid multiple calls
        # self.sensitivityTable.itemChanged.disconnect(self.saveData)

        # Add the table to the layout
        self.layout.addWidget(self.sensitivityTable)
        # Add Row Button
        self.addRowButton = QPushButton("Add Parameter")
        self.addRowButton.clicked.connect(self.addSensitivityRow)
        self.layout.addWidget(self.addRowButton)

        # Ensure the widget can receive focus to detect key presses
        self.setFocusPolicy(Qt.StrongFocus)
        self.setLayout(self.layout)

        # if the central data manager has data, import it
        self.importData()


    def addSensitivityRow(self, data: SensitivityDTO | None = None):
        """
        This method adds a row to the table for the chemical components
        :param data: of type SensitivityDTO, the data to be added to the table, can be None
        :return:
        """
        # set the flag of adding a row to true
        self.addingRowFlag = True

        rowPosition: int
        if data is None or not isinstance(data, SensitivityDTO):
            rowPosition = self.sensitivityTable.rowCount()
            uid = uuid.uuid4().__str__()
            data = SensitivityDTO(rowPosition=rowPosition, uid=uid)
            self.sensitivityList.append(data)
        else:
            rowPosition = data.rowPosition
        self.sensitivityTable.insertRow(rowPosition)

        for key, value in data.as_dict().items():
            if key in self.columnsShortnames:
                index = self.columnsShortnames.index(key)
                if key == 'parameterType':
                    parameterNames = ["Split factors (myu)",
                                      "Feed Composition (phi)",
                                      "Conversion factor (theta)",
                                      "Stoichiometric factor (gamma)",
                                      "Yield factor (xi)",
                                      "Costs (materialcosts)",
                                      "Price (ProductPrice)",
                                      "electricity_price",
                                      "heat_price"]

                    # make a combobox for the parameter type
                    self.comboBoxParameterType = ComboBox()
                    self.comboBoxParameterType.addItems(parameterNames)
                    self.comboBoxParameterType.currentIndexChanged.connect(lambda: [self._selectionSettings(rowPosition),
                                                                                    self.saveData])

                    # adding this item is a bit of a hack otherwise the row can't be selected and deleted
                    insert = QTableWidgetItem()
                    insert.setFlags(insert.flags() | Qt.ItemIsEditable)
                    self.sensitivityTable.setItem(rowPosition, index, insert)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.comboBoxParameterType)
                    # set the value of the combobox
                    if value:
                        self.comboBoxParameterType.setCurrentText(value)

                elif key == "unitUid":
                    # make a combobox for the unit process
                    self.comboBoxUnitProcess = ComboBox()
                    unitProcesNames = self.centralDataManager.getProcessNames()
                    self.comboBoxUnitProcess.addItems(unitProcesNames)
                    self.comboBoxUnitProcess.currentIndexChanged.connect(self.saveData)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.comboBoxUnitProcess)

                    if value and value != "n.a.":
                        unitDict = self.centralDataManager.unitProcessData
                        try:
                            unitName = [u.name for u in unitDict.values() if u.uid == value][0]
                        except:
                            self.logger.warning(f"Unit process with uid {value} not found, it was set to n.a.")
                            unitName = "n.a."

                        self.comboBoxUnitProcess.setCurrentText(unitName)

                elif key == "componentName":
                    self.comboBoxComponents = ComboBox()
                    ComponentNames = self.centralDataManager.getChemicalComponentNames()
                    self.comboBoxComponents.addItems(ComponentNames)
                    self.comboBoxComponents.currentIndexChanged.connect(self.saveData)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.comboBoxComponents)
                    if value:
                        self.comboBoxComponents.setCurrentText(value)

                elif key == "targetUnitProcess":
                    self.comboBoxTargetUnitProcess = ComboBox()
                    unitProcesNames = self.centralDataManager.getProcessNames()
                    self.comboBoxTargetUnitProcess.addItems(unitProcesNames)
                    self.comboBoxTargetUnitProcess.currentIndexChanged.connect(self.saveData)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.comboBoxTargetUnitProcess)

                    # add the value to the combobox
                    if value and value != "n.a.":
                        unitDict = self.centralDataManager.unitProcessData
                        try:
                            unitName = [u.name for u in unitDict.values() if u.uid == value][0]
                        except:
                            self.logger.warning(f"Unit process with uid {value} not found, the field targetUnitProcess "
                                                f" was set to n.a.")
                            unitName = "n.a."

                        self.comboBoxTargetUnitProcess.setCurrentText(unitName)

                elif key == "reactionUid":
                    self.comboBoxReaction = ComboBox()
                    reactionNames = self.centralDataManager.getReactionNames()
                    self.comboBoxReaction.addItems(reactionNames)
                    self.comboBoxReaction.currentIndexChanged.connect(self.saveData)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.comboBoxReaction)

                    #set the value
                    if value and value != "n.a.":
                        reactionList = self.centralDataManager.reactionData
                        reactionName = [u.name for u in reactionList if u.uid == value][0]
                        self.comboBoxReaction.setCurrentText(reactionName)


                elif key == "lowerBound":
                    self.lineEditLB = QLineEdit()
                    validator = QDoubleValidator(-999999999, 999999999, 2)
                    self.lineEditLB.setValidator(validator)
                    self.lineEditLB.editingFinished.connect(self.saveData)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.lineEditLB)
                    if value is not None:
                        self.lineEditLB.setText(str(value))

                elif key == "upperBound":
                    self.lineEditUB = QLineEdit()
                    validator = QDoubleValidator(-999999999, 999999999, 2)
                    self.lineEditUB.setValidator(validator)
                    self.lineEditUB.editingFinished.connect(self.saveData)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.lineEditUB)
                    if value is not None:
                        self.lineEditUB.setText(str(value))

                elif key == "steps":
                    self.lineEditSteps = QLineEdit()
                    validator = QDoubleValidator(-999999999, 999999999, 2)
                    self.lineEditSteps.setValidator(validator)
                    self.lineEditSteps.editingFinished.connect(self.saveData)
                    self.sensitivityTable.setCellWidget(rowPosition, index, self.lineEditSteps)
                    if value is not None:
                        self.lineEditSteps.setText(str(value))

                else:
                     self.logger.error(f"Missing logic for {key}")

        # set the flag of adding a row to false
        self.addingRowFlag = False
        # get the selection setting correct for the new row
        self._selectionSettings(rowPosition)

    def _selectionSettings(self, rowPostion):
        """
        Determines what fields are editable based on the parameter type on the specific row in the table
        :param rowPostion: the row position in the table that is being edited
        :return:
        """
        if not self.addingRowFlag: #don't update the row if a row is being added from data
            # get the row position
            row = rowPostion
            # get the parameter type
            paramType = self.sensitivityTable.cellWidget(row, 0).currentText()

            if paramType == "Split factors (myu)": # or paramType == "electricity_price" or paramType == "heat_price":
                # the reactionUID column is not editable and in gray
                self._updateColumnEditability(row, [4])

            elif paramType == "Costs (materialcosts)" or paramType == "Price (ProductPrice)" or paramType == "heat_price":
                # set the reactionUID component and the target Unit UID un-editable, gray and have a value of n.a.
                self._updateColumnEditability(row, [2, 3, 4])

            elif paramType == "electricity_price":
                # all un-editable and gray
                self._updateColumnEditability(row, [1, 2, 3, 4])


            elif paramType == "Feed Composition (phi)" or paramType == "Yield factor (xi)":
                # set the reactionUID column and the target Unit UID un-editable,gray and have a value of n.a
                self._updateColumnEditability(row, [3, 4])

            elif paramType == "Conversion factor (theta)" or paramType == "Stoichiometric factor (gamma)":
                # set the reactionUID column and the target Unit UID un-editable,gray and have a value of n.a.
                self._updateColumnEditability(row, [3])

            else:
                self.logger.error('Missed logic for {}'.format(paramType))

    def _updateColumnEditability(self, rowPosition, deactivateColumns:list):
        """
        Updates the editability of columns based on the given row position, columns to deactivate, and parameter type.
        :param rowPosition: the row position in the table that is being edited
        :param deactivateColumns: list of column indices to be deactivated
        :return:
        """

        for col in range(1, 6):
            widget = self.sensitivityTable.cellWidget(rowPosition, col)
            if col in deactivateColumns:
                if isinstance(widget, ComboBox):
                    if "n.a." not in [widget.itemText(i) for i in range(widget.count())]:
                        widget.addItem("n.a.")
                    widget.setCurrentText("n.a.")
                widget.setEnabled(False)
                hexCode = "#d3d3d3" # a bit darker then light gray
                self._updateBackgroundColor(widget, hexCode)

            else:
                if isinstance(widget, ComboBox):
                    index = widget.findText("n.a.")
                    if index != -1:
                        widget.removeItem(index)
                widget.setEnabled(True)
                self._updateBackgroundColor(widget, "white")

            # todo later, in later stages we could limit the data that is shown,
            #  e.g. for prices, only drop down the output units in the unit column dropdown widgets

            #if col in columnsLimitedData:
            #    # find the value in the first widget (1st column)
            #    paramTypeWidget = self.sensitivityTable.cellWidget(rowPosition, 0)
            #    paramType = paramTypeWidget.currentText()
            #    uniqueDataList = self._getparameterSpecificList(columnNr=col)
            #    # give the combobox the new list
            #    # delete old items in the combobox in the current widget
            #    widget.clear()
            #    for obj in uniqueDataList:
            #        widget.addItem(obj)

            #else:
            #    if isinstance(widget, ComboBox):
            #        index = widget.findText("n.a.")
            #        if index != -1:
            #            widget.removeItem(index)
            #    widget.setEnabled(True)
            #    self._updateBackgroundColor(widget, "white")

    def _getparameterSpecificList(self, columnNr:int = None):
        """
        Returns the processes filtered by the parameter type
        """

        if columnNr == 1 or columnNr == 3:
            unitProcesNames = self.centralDataManager.getOnlyProcesses()
            return unitProcesNames

        if columnNr == 2:
            ComponentNames = self.centralDataManager.getChemicalComponentNames()
            return ComponentNames

        if columnNr == 4:
            reactionNames = self.centralDataManager.getReactionNames()
            return reactionNames

        else:
            return []

    def _updateBackgroundColor(self, widget, color):
        """
        Updates the background color of the given widget while preserving other style properties.
        :param widget: The widget whose background color needs to be updated.
        :param color: The new background color to be set.
        """
        # Get the current style sheet
        current_style = widget.styleSheet()

        # If the current style is empty, set the initial style
        if not current_style:
            current_style = """
                QComboBox {
                    border: 1px solid #cccccc;
                    border-radius: 2px;
                    padding: 5px;
                    background-color: #ffffff;
                    selection-background-color: #b0daff;
                }
            """

        # Split the style sheet into individual properties
        style_properties = [prop.strip() for prop in current_style.split(';') if prop.strip()]

        # Filter out any existing background-color property
        style_properties = [prop for prop in style_properties if not prop.startswith('background-color')]

        # Add the new background-color property
        style_properties.append(f'background-color: {color}')

        # Join the properties back into a single style sheet string
        new_style = '; '.join(style_properties) + ';'

        # Set the updated style sheet back to the widget
        widget.setStyleSheet(new_style)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backspace | Qt.Key_Delete:
            selectedItems = self.sensitivityTable.selectedItems()
            if selectedItems:
                selectedRow = selectedItems[0].row()  # Get the row of the first selected item
                self.sensitivityTable.removeRow(selectedRow)
                target = [u for u in self.sensitivityList if u.rowPosition == selectedRow][0]
                self.sensitivityList.remove(target)
                for c in [u for u in self.sensitivityList if u.rowPosition >= selectedRow]:
                    c.updateRow()
        else:
            super().keyPressEvent(event)

    def doubleClickEvent(self, item):
        print(item.row(), item.column())

    @pyqtSlot()
    def saveData(self):
        if not self.addingRowFlag:
            self.collectData()
            # Save the data to the central data manager
            self.centralDataManager.addData("sensitivityData", self.sensitivityList)
            self.logger.debug("Sensitivity data saved to central data manager")

    def collectData(self):
        # Collect data from the table
        for row in range(self.sensitivityTable.rowCount()):
            edit = [u for u in self.sensitivityList if u.rowPosition == row][0]
            rowData = []
            for column in self.columnsList:
                sindex = self.columnsList.index(column)
                widget = self.sensitivityTable.cellWidget(row, sindex)

                # extract the value from the widget
                if isinstance(widget, ComboBox):
                    value = widget.currentText()
                elif isinstance(widget, QDoubleSpinBox):
                    value = widget.value()
                else:
                    value = widget.text()  # For other types of widgets, adjust as needed

                if column in ["Parameter Type", "Component", "Lower Bound", "Upper Bound", "Number of Steps"]:
                    edit.upadateField(self.columnsShortnames[sindex], value)

                elif column in ["Unit Process", "Target Unit Process"]:
                    if value == "n.a." or value == "":
                        edit.upadateField(self.columnsShortnames[sindex], "n.a.")
                    else:
                        unitDict = self.centralDataManager.unitProcessData
                        id = [u for u in unitDict.values() if u.name == value][0].uid
                        edit.upadateField(self.columnsShortnames[sindex], id)

                elif column == "Reaction":
                    if value == "n.a." or value == "":
                        edit.upadateField(self.columnsShortnames[sindex], "n.a.")
                    else:
                        reactionList = self.centralDataManager.reactionData
                        id = [u for u in reactionList if u.name == value][0].uid
                        edit.upadateField(self.columnsShortnames[sindex], id)

    def sortComponentDTO(self,dto: SensitivityDTO):
        return dto.rowPosition

    def importData(self):
        try:
            tabledata = self.centralDataManager.sensitivityData
            for row in tabledata:
                self.addSensitivityRow(row)
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
        component_pos = self.sensitivityTable.viewport().mapFrom(self, event.pos())

        if self.sensitivityTable.geometry().contains(event.pos()) and action == deleteAction:
            # Determine the row that was clicked in the reactants table
            row = self.sensitivityTable.rowAt(component_pos.y())
            if row != -1:
                self.sensitivityTable.removeRow(row)

            # update the dto list containing the chemical components
            self.centralDataManager.updateData('sensitivityData', row)
            # open a dialog if the component is used in a reaction or unit operation

