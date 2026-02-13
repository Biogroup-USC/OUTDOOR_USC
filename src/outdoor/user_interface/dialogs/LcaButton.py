from PyQt5.QtWidgets import QPushButton, QDialog, QApplication

from outdoor.user_interface.data.OutdoorDTO import OutdoorDTO
from outdoor.user_interface.dialogs.LCADialog import LCADialog


class LcaButton(QPushButton):
    def __init__(self, parent, data: OutdoorDTO, centralDataManager):
        super().__init__(parent)
        self.data = data
        self.centralDataManager = centralDataManager

    def lcaAction(self):
        dialog = LCADialog(self.data, centralDataManager=self.centralDataManager)
        result = dialog.exec_()

        if result == QDialog.Rejected or result == QDialog.Accepted:
            self.changeColorBnt()

    def changeColorBnt(self):
        if self.data.calculated:
            self.setText("Calculated")
            # color green
            self.setStyleSheet("background-color: #0000FF")
        elif len(self.data.LCA['exchanges']) > 0:
            self.setText("Defined")
            # color red
            self.setStyleSheet("background-color: #00FF00")
        else:
            self.setText("Not Defined")
            self.setStyleSheet("background-color: #FF0000")
        # self.setEnabled(True)
        # self.setStyleSheet("background-color: #00FF00")


def refresh_all_lca_buttons() -> int:
    """
    Find and refresh all LcaButton instances across all top-level windows.
    Returns the number of refreshed buttons.
    """
    all_windows = QApplication.topLevelWidgets()
    if not all_windows:
        return 0

    lca_buttons = []
    for window in all_windows:
        buttons = window.findChildren(LcaButton)
        if buttons:
            lca_buttons.extend(buttons)

    for button in lca_buttons:
        button.changeColorBnt()

    return len(lca_buttons)
