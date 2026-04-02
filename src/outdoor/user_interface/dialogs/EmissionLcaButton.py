from PyQt5.QtWidgets import QPushButton, QDialog

from outdoor.user_interface.data.ComponentEmissionDTO import ComponentEmissionDTO
from outdoor.user_interface.dialogs.LCADialog import LCADialog


class EmissionLcaButton(QPushButton):
    """
    Button to manage LCA emissions data independently for chemical components.
    Works with ComponentEmissionDTO to store LCA impact data separately.
    """
    def __init__(self, parent, emissionData: ComponentEmissionDTO, centralDataManager):
        super().__init__(parent)
        self.emissionData = emissionData
        self.centralDataManager = centralDataManager

    def lcaAction(self):
        """Open LCA dialog to manage emissions data"""
        dialog = LCADialog(self.emissionData, centralDataManager=self.centralDataManager)
        result = dialog.exec_()

        if result == QDialog.Rejected or result == QDialog.Accepted:
            self.changeColorBnt()
            # Save the emission data to central data manager
            self._saveEmissionData()

    def _saveEmissionData(self):
        """Save the emission data to the central data manager"""
        try:
            # Update the emission data in the list
            self.centralDataManager.componentEmissionData = [
                dto if dto.uid != self.emissionData.uid else self.emissionData
                for dto in self.centralDataManager.componentEmissionData
            ]
            self.centralDataManager.logger.debug(
                f"Emission data saved for component {self.emissionData.name}")
        except Exception as e:
            self.centralDataManager.logger.error(f"Error saving emission data: {e}")

    def changeColorBnt(self):
        """Update button color and text based on data status"""
        if self.emissionData.calculated:
            self.setText("Calculated")
            # Blue for calculated
            self.setStyleSheet("background-color: #0000FF")
        elif len(self.emissionData.LCA.get('exchanges', [])) > 0:
            self.setText("Defined")
            # Green for defined
            self.setStyleSheet("background-color: #00FF00")
        else:
            self.setText("Not Defined")
            # Red for not defined
            self.setStyleSheet("background-color: #FF0000")

