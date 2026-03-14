import os
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator, QFont, QCursor, QIntValidator, QPixmap, QColor
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel, QWidget, QTableWidget, QTabWidget, \
    QApplication, QHBoxLayout, QTableWidgetItem, QFormLayout, QComboBox, QFrame, QToolTip, QCheckBox, QMessageBox

from outdoor.user_interface.data.CentralDataManager import CentralDataManager
from outdoor.user_interface.data.ProcessDTO import ProcessType, UpdateField
from outdoor.user_interface.utils.NonFocusableComboBox import NonFocusableComboBox


class ResultsProcessesDialog(QDialog):
    """
    Opens a dialog to set the physical processes parameters for the physical processes icon. The dialog allows the user to
    set the name, processing group, reference flow, and exponent. The user can set the reference flow and exponent as
    floating-point numbers. The processing group and name are text fields.
    """

    def __init__(self, resultsData, centralDataManager:CentralDataManager, iconID):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # Set style (existing style setup is fine and will be applied)
        # set style
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
        self.setWindowFlags(Qt.Window)
        self.centralDataManager = centralDataManager
        self.iconID = iconID
        self.UnitType = ProcessType.PHYSICAL
        self.dialogData = resultsData.dialogData if resultsData else {}

        # add the tool tip text for the incoming chemicals buttons they are the same in each tab
        self.tooltipFindChemicalsButton = "These buttons will add the incoming chemicals to the table."
        self.setWindowTitle("Unit Process Parameters")
        self.setGeometry(100, 100, 600, 400)  # Adjust size as needed

        self.subtitleFont = QFont("Arial", 9, QFont.Bold)

        # initialize the separation error to be False
        self.separationErrorDict = {}

        tabWidget = QTabWidget(self)
        tabWidget.addTab(self._CAPEXresults(), "General Parameters")

    def _CAPEXresults(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # Create the form layout for the general parameters
        formLayout = QFormLayout()

        # Name
        self.nameLineEdit = QLineEdit(self.dialogData.get("name", ""))
        formLayout.addRow(QLabel("Name:"), self.nameLineEdit)

        tab.setLayout(layout)
        return tab


