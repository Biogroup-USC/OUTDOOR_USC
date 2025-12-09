import logging
import uuid

from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QPushButton, QLabel, QTableWidgetItem, QMenu,
                             QDoubleSpinBox)

from outdoor.user_interface.data.UncertaintyDTO import UncertaintyDTO
from outdoor.user_interface.dialogs.LcaButton import LcaButton
from outdoor.user_interface.utils.DoubleDelegate import DoubleDelegate
from outdoor.user_interface.utils.NonFocusableComboBox import NonFocusableComboBox as ComboBox


class UncertaintyTab(QWidget):
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
        self.uncertaintyList: list[UncertaintyDTO] = centralDataManager.uncertaintyData

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
        self.title = QLabel("Characterization of Uncertainty")
        self.title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title)

        # Table for the component data
        self.uncertaintyTable = QTableWidget()

        self.columnsList = ["Parameter Type", "Unit Process",
                            "Component", "Target Unit Process",
                            "Reaction", "Uncertainty Factor", "Distribution Function"]

        self.columnsShortnames = ["parameterType", "unitUid",
                                  "componentName", "targetUnitProcess",
                                  "reactionUid", "uncertaintyFactor", "distributionType"]

        self.uncertaintyTable.setColumnCount(len(self.columnsList))
        self.uncertaintyTable.setHorizontalHeaderLabels(self.columnsList)

        # adjust the width of the columns
        self.uncertaintyTable.setColumnWidth(0, 230)
        self.uncertaintyTable.setColumnWidth(1, 230)
        self.uncertaintyTable.setColumnWidth(2, 180)
        self.uncertaintyTable.setColumnWidth(3, 210)
        self.uncertaintyTable.setColumnWidth(4, 150)
        self.uncertaintyTable.setColumnWidth(5, 180)
        self.uncertaintyTable.setColumnWidth(6, 180)

        # save if something is changed in the table, this is done by the wigets in the table itself
        # disconnect the signal to avoid multiple calls
        # self.uncertaintyTable.itemChanged.disconnect(self.saveData)

        # Add the table to the layout
        self.layout.addWidget(self.uncertaintyTable)
        # Add Row Button
        self.addRowButton = QPushButton("Add Uncertain Parameter")
        self.addRowButton.clicked.connect(self.addUncertaintyRow)
        self.layout.addWidget(self.addRowButton)

        # Ensure the widget can receive focus to detect key presses
        self.setFocusPolicy(Qt.StrongFocus)
        self.setLayout(self.layout)

        # if the central data manager has data, import it
        self.importData()


    def addUncertaintyRow(self, data: UncertaintyDTO | None = None):
        """
        This method adds a row to the table for the chemical components
        :param data: of type UncertaintyDTO, the data to be added to the table, can be None
        :return:
        """
        # set the flag of adding a row to true
        self.addingRowFlag = True

        rowPosition: int
        if data is None or not isinstance(data, UncertaintyDTO):
            rowPosition = self.uncertaintyTable.rowCount()
            uid = uuid.uuid4().__str__()
            data = UncertaintyDTO(rowPosition=rowPosition, uid=uid)
            self.uncertaintyList.append(data)
        else:
            rowPosition = data.rowPosition
        self.uncertaintyTable.insertRow(rowPosition)

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
                    self.uncertaintyTable.setItem(rowPosition, index, insert)
                    self.uncertaintyTable.setCellWidget(rowPosition, index, self.comboBoxParameterType)
                    # set the value of the combobox
                    if value:
                        self.comboBoxParameterType.setCurrentText(value)

                elif key == "unitUid":
                    # make a combobox for the unit process
                    self.comboBoxUnitProcess = ComboBox()
                    unitProcesNames = self.centralDataManager.getProcessNames()
                    self.comboBoxUnitProcess.addItems(unitProcesNames)
                    self.comboBoxUnitProcess.currentIndexChanged.connect(self.saveData)
                    self.uncertaintyTable.setCellWidget(rowPosition, index, self.comboBoxUnitProcess)

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
                    self.uncertaintyTable.setCellWidget(rowPosition, index, self.comboBoxComponents)
                    if value:
                        self.comboBoxComponents.setCurrentText(value)

                elif key == "targetUnitProcess":
                    self.comboBoxTargetUnitProcess = ComboBox()
                    unitProcesNames = self.centralDataManager.getProcessNames()
                    self.comboBoxTargetUnitProcess.addItems(unitProcesNames)
                    self.comboBoxTargetUnitProcess.currentIndexChanged.connect(self.saveData)
                    self.uncertaintyTable.setCellWidget(rowPosition, index, self.comboBoxTargetUnitProcess)

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
                    self.uncertaintyTable.setCellWidget(rowPosition, index, self.comboBoxReaction)

                    #set the value
                    if value and value != "n.a.":
                        reactionList = self.centralDataManager.reactionData
                        reactionName = [u.name for u in reactionList if u.uid == value][0]
                        self.comboBoxReaction.setCurrentText(reactionName)

                elif key == "uncertaintyFactor":
                    self.doubleSpinBox = QDoubleSpinBox()
                    self.doubleSpinBox.setRange(0.0, 1.0)
                    self.doubleSpinBox.setSingleStep(0.01)
                    self.doubleSpinBox.valueChanged.connect(self.saveData)
                    self.uncertaintyTable.setCellWidget(rowPosition, index, self.doubleSpinBox)
                    if value:
                        self.doubleSpinBox.setValue(float(value))

                elif key == "distributionType":
                    distributionNames = ["Uniform", "Normal"]
                    self.comboBoxDistribution = ComboBox()
                    self.comboBoxDistribution.addItems(distributionNames)
                    self.comboBoxDistribution.currentIndexChanged.connect(self.saveData)
                    self.uncertaintyTable.setCellWidget(rowPosition, index, self.comboBoxDistribution)
                    if value:
                        self.comboBoxDistribution.setCurrentText(value)

                # else:
                #     self.logger.error(f"Missing logic for {key}")

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
            paramType = self.uncertaintyTable.cellWidget(row, 0).currentText()

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
                print('Missed logic for {}'.format(paramType))

    def _updateColumnEditability(self, rowPosition, deactivate_columns):
        """
        Updates the editability of columns based on the given row position, columns to deactivate, and parameter type.
        :param rowPosition: the row position in the table that is being edited
        :param deactivate_columns: list of column indices to be deactivated
        :return:
        """
        for col in range(1, 5):
            widget = self.uncertaintyTable.cellWidget(rowPosition, col)
            if col in deactivate_columns:
                if isinstance(widget, ComboBox):
                    if "n.a." not in [widget.itemText(i) for i in range(widget.count())]:
                        widget.addItem("n.a.")
                    widget.setCurrentText("n.a.")
                widget.setEnabled(False)
                # a bit darker then light gray
                hexCode = "#d3d3d3"
                self._updateBackgroundColor(widget, hexCode)

            else:
                if isinstance(widget, ComboBox):
                    index = widget.findText("n.a.")
                    if index != -1:
                        widget.removeItem(index)
                widget.setEnabled(True)
                self._updateBackgroundColor(widget, "white")

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
            selectedItems = self.uncertaintyTable.selectedItems()
            if selectedItems:
                selectedRow = selectedItems[0].row()  # Get the row of the first selected item
                self.uncertaintyTable.removeRow(selectedRow)
                target = [u for u in self.uncertaintyList if u.rowPosition == selectedRow][0]
                self.uncertaintyList.remove(target)
                for c in [u for u in self.uncertaintyList if u.rowPosition >= selectedRow]:
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
            self.centralDataManager.addData("uncertaintyData", self.uncertaintyList)
            self.logger.debug("Uncertainty data saved to central data manager")

    def collectData(self):
        # Collect data from the table
        for row in range(self.uncertaintyTable.rowCount()):
            edit = [u for u in self.uncertaintyList if u.rowPosition == row][0]
            rowData = []
            for column in self.columnsList:
                sindex = self.columnsList.index(column)
                widget = self.uncertaintyTable.cellWidget(row, sindex)

                # extract the value from the widget
                if isinstance(widget, ComboBox):
                    value = widget.currentText()
                elif isinstance(widget, QDoubleSpinBox):
                    value = widget.value()
                else:
                    value = widget.text()  # For other types of widgets, adjust as needed

                if column in ["Parameter Type", "Component", "Uncertainty Factor", "Distribution Function"]:
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

    def sortComponentDTO(self,dto: UncertaintyDTO):
        return dto.rowPosition

    def importData(self):
        try:
            tabledata = self.centralDataManager.uncertaintyData
            for row in tabledata:
                self.addUncertaintyRow(row)
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
        component_pos = self.uncertaintyTable.viewport().mapFrom(self, event.pos())

        if self.uncertaintyTable.geometry().contains(event.pos()) and action == deleteAction:
            # Determine the row that was clicked in the reactants table
            row = self.uncertaintyTable.rowAt(component_pos.y())
            if row != -1:
                self.uncertaintyTable.removeRow(row)

            # update the dto list containing the chemical components
            self.centralDataManager.updateData('uncertaintyData', row)
            # open a dialog if the component is used in a reaction or unit operation

