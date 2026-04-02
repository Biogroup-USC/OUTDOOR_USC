from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QTableWidget, QComboBox, \
    QMenu

from outdoor.user_interface.data.ReactionDTO import ReactionDTO


class ReactionDialog(QDialog):
    """
    Opens a dialog to set the input parameters for the input icon. The dialog allows the user to set the source name,
    price input, components, CO2 emission factor, lower limit, and upper limit. The components are entered in a table
    format with two columns: Component Name and % Composition. The user can add multiple rows to enter multiple
    components and their composition in the feedstock.
    """

    def __init__(self, initialData: ReactionDTO, centralDataManager, rowPosition: int):
        super().__init__()

        # Initialize the dialog with the initial data
        self.centralDataManager = centralDataManager
        self.rowPosition = rowPosition
        self.dataDTO = initialData

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
        self.setWindowTitle("Edit Reaction")
        self.setGeometry(100, 100, 800, 500)  # Adjust size as needed

        # Layout
        main_layout = QVBoxLayout(self)

        # edit line: reqction name
        nameLabel = QLabel("Reaction Name:")
        main_layout.addWidget(nameLabel)
        self.nameEdit = QLineEdit()
        main_layout.addWidget(self.nameEdit)

        # Add description label at the top of the dialog
        description_label = QLabel(
            "Please define the reactants and products involved in the reaction, including their stoichiometric coefficients.\n "
            "Carefull the in stoichiometry is Mass based.\n"
            "You can add multiple reactants and products using the buttons, don't forget to save the reaction when done.")
        description_label.setWordWrap(True)
        main_layout.addWidget(description_label)

        tables_layout = QHBoxLayout()
        # Reactants Table
        self.reactantsTable = QTableWidget()
        self.reactantsTable.setColumnCount(2)
        self.reactantsTable.setHorizontalHeaderLabels(["Reactants", "Stoichiometry"])
        self.reactantsTable.setColumnWidth(0, 150)
        self.reactantsTable.setColumnWidth(1, 150)
        tables_layout.addWidget(self.reactantsTable)

        # Add Row Button for Reactants Table
        addReactantButton = QPushButton("Add Reactant", self)
        addReactantButton.clicked.connect(self.addReactantRow)
        main_layout.addWidget(addReactantButton)

        # Products Table
        self.productsTable = QTableWidget()
        self.productsTable.setColumnCount(2)
        self.productsTable.setHorizontalHeaderLabels(["Products", "Stoichiometry"])
        self.productsTable.setColumnWidth(0, 150)
        self.productsTable.setColumnWidth(1, 150)
        tables_layout.addWidget(self.productsTable)

        # Add Row Button for Products Table
        addProductButton = QPushButton("Add Product", self)
        addProductButton.clicked.connect(self.addProductRow)
        main_layout.addWidget(addProductButton)

        # Add tables layout to the main layout
        main_layout.addLayout(tables_layout)

        # Save Button
        saveButton = QPushButton("Save Reaction", self)
        saveButton.clicked.connect(self.saveData)
        main_layout.addWidget(saveButton)

        # Load initial data if available
        self.loadInitialData(initialData)

    def getChemicalList(self):
        # This is a placeholder function to get the list of allowed chemicals
        # Replace with the actual list as needed
        chemicalNames = self.centralDataManager.getChemicalComponentNames()
        return chemicalNames

    def addReactantRow(self):
        # Add a new row to the Reactants Table
        rowPosition = self.reactantsTable.rowCount()
        self.reactantsTable.insertRow(rowPosition)

        # Create a drop-down for "Reactants"
        reactantCombo = QComboBox()
        reactantCombo.addItems(self.getChemicalList())  # Populate the combo box with allowed chemicals
        self.reactantsTable.setCellWidget(rowPosition, 0, reactantCombo)

        # Create a QLineEdit for "Stoichiometry" (editable)
        stoichiometryEdit = QLineEdit()

        # Set a QDoubleValidator to the QLineEdit to allow only double values
        double_validator = QDoubleValidator()
        double_validator.setBottom(0)  # Set the minimum value (e.g., non-negative)
        stoichiometryEdit.setValidator(double_validator)

        # Add the QLineEdit widget to the table
        self.reactantsTable.setCellWidget(rowPosition, 1, stoichiometryEdit)

    def addProductRow(self):
        # Add a new row to the Products Table
        rowPosition = self.productsTable.rowCount()
        self.productsTable.insertRow(rowPosition)

        # Create a drop-down for "Products"
        productCombo = QComboBox()
        productCombo.addItems(self.getChemicalList())  # Populate the combo box with allowed chemicals
        self.productsTable.setCellWidget(rowPosition, 0, productCombo)

        # Create a QLineEdit for "Stoichiometry" (editable)
        stoichiometryEdit = QLineEdit()

        # Set a QDoubleValidator to the QLineEdit to allow only double values
        double_validator = QDoubleValidator()
        double_validator.setBottom(0)  # Set the minimum value (e.g., non-negative)
        stoichiometryEdit.setValidator(double_validator)

        # Add the QLineEdit widget to the table
        self.productsTable.setCellWidget(rowPosition, 1, stoichiometryEdit)

    def loadInitialData(self, data: ReactionDTO):
        """
        Load the initial data from the provided ReactionDTO into the dialog.
        """
        # Set the reaction name if available
        if hasattr(data, "name") and data.name:
            self.nameEdit.setText(data.name)

        # Populate the reactants table with initial data
        if hasattr(data, "reactants") and isinstance(data.reactants, dict):
            for reactant, stoichiometry in data.reactants.items():
                # Add a new row to the reactants table
                rowPosition = self.reactantsTable.rowCount()
                self.reactantsTable.insertRow(rowPosition)

                # Create a drop-down for "Reactants" and set the current text
                reactantCombo = QComboBox()
                reactantCombo.addItems(self.getChemicalList())
                index = reactantCombo.findText(reactant, Qt.MatchFixedString)
                if index >= 0:
                    reactantCombo.setCurrentIndex(index)
                self.reactantsTable.setCellWidget(rowPosition, 0, reactantCombo)

                # Create a QLineEdit for "Stoichiometry" and set its value
                stoichiometryEdit = QLineEdit()
                stoichiometryEdit.setText(str(abs(stoichiometry)))  # Ensure the value is positive
                double_validator = QDoubleValidator()
                double_validator.setBottom(0)  # Set the minimum value (non-negative)
                stoichiometryEdit.setValidator(double_validator)
                self.reactantsTable.setCellWidget(rowPosition, 1, stoichiometryEdit)

        # Populate the products table with initial data
        if hasattr(data, "products") and isinstance(data.products, dict):
            for product, stoichiometry in data.products.items():
                # Add a new row to the products table
                rowPosition = self.productsTable.rowCount()
                self.productsTable.insertRow(rowPosition)

                # Create a drop-down for "Products" and set the current text
                productCombo = QComboBox()
                productCombo.addItems(self.getChemicalList())
                index = productCombo.findText(product, Qt.MatchFixedString)
                if index >= 0:
                    productCombo.setCurrentIndex(index)
                self.productsTable.setCellWidget(rowPosition, 0, productCombo)

                # Create a QLineEdit for "Stoichiometry" and set its value
                stoichiometryEdit = QLineEdit()
                stoichiometryEdit.setText(str(stoichiometry))  # Keep the value as is for products
                double_validator = QDoubleValidator()
                double_validator.setBottom(0)  # Set the minimum value (non-negative)
                stoichiometryEdit.setValidator(double_validator)
                self.productsTable.setCellWidget(rowPosition, 1, stoichiometryEdit)

    def saveData(self, data: ReactionDTO | None = None):
        # Save the data to the DTO
        rowPosition: int
        if data is None or not isinstance(data, ReactionDTO):

            name = self.nameEdit.text()
            reactants = self.extractDataReactants()
            products = self.extractDataProducts()
            reactionEq = self.makeStringEquation(reactants, products)

            # check if the sum of the stoichiometry is zero print a warning dialog
            if sum(reactants.values()) + sum(products.values()) > 0:
                self.warningDialog(errorType="Stoich_critical")
                return
            elif sum(reactants.values()) + sum(products.values()) != 0:
                self.warningDialog(errorType="Stoich_non_critical")
                # no need to return as the user can still save the reaction

            if name == "":
                self.warningDialog(errorType="Name")
                return

            # This is to keep track of the old name of the reaction for if the name is changed
            self.dataDTO.oldName = self.dataDTO.name

            # Update the data in the DTO
            self.dataDTO.upadateField("name", name)
            self.dataDTO.upadateField("reactants", reactants)
            self.dataDTO.upadateField("products", products)
            self.dataDTO.upadateField("reactionEquation", reactionEq)

        self.close()

    def extractDataReactants(self):
        """
        Extracts the data of the Reactants table and returns it as a dictionary
        where the keys are the reactants and the values are their stoichiometry (as floats).
        """
        row_count = self.reactantsTable.rowCount()

        # Initialize an empty dictionary to store the extracted data
        table_data = {}

        # Loop through each row
        for row in range(row_count):
            # Get the widget in the Reactants column
            reactant_widget = self.reactantsTable.cellWidget(row, 0)  # Reactant column
            stoichiometry_widget = self.reactantsTable.cellWidget(row, 1)  # Stoichiometry column

            # Ensure both widgets are valid before attempting to extract data
            if reactant_widget is not None and stoichiometry_widget is not None:
                # Extract the reactant name from the QComboBox
                reactant = reactant_widget.currentText()

                # Extract the stoichiometry value from the QLineEdit
                try:
                    # make the stoichiometry negative for reactants
                    stoichiometry = - float(stoichiometry_widget.text())
                except ValueError:
                    # Handle case where stoichiometry isn't a valid float
                    stoichiometry = 0.0

                # Add the data to the dictionary
                table_data[reactant] = stoichiometry

        return table_data

    def extractDataProducts(self):
        """
        Extracts the data of the Products table and returns it as a dictionary
        where the keys are the reactants and the values are their stoichiometry (as floats).
        """

        row_count = self.productsTable.rowCount()

        # Initialize an empty dictionary to store the extracted data
        table_data = {}

        # Loop through each row
        for row in range(row_count):
            # Get the widget in the Reactants column
            products_widget = self.productsTable.cellWidget(row, 0)  # Reactant column
            stoichiometry_widget = self.productsTable.cellWidget(row, 1)  # Stoichiometry column

            # Ensure both widgets are valid before attempting to extract data
            if products_widget is not None and stoichiometry_widget is not None:
                # Extract the reactant name from the QComboBox
                product = products_widget.currentText()

                # Extract the stoichiometry value from the QLineEdit
                try:
                    stoichiometry = float(stoichiometry_widget.text())

                except ValueError:
                    # Handle case where stoichiometry isn't a valid float
                    stoichiometry = 0.0

                # Add the data to the dictionary
                table_data[product] = stoichiometry

        return table_data

    def makeStringEquation(self, reactants, products):
        """
        Extracts the data of the Reactants and Products tables and returns it as a string
        """

        reactants_str = " + ".join([f"{v} {k}" for k, v in reactants.items()])
        products_str = " + ".join([f"{v} {k}" for k, v in products.items()])
        return f"{reactants_str} -> {products_str}"

    def contextMenuEvent(self, event):
        # Create a context menu
        context_menu = QMenu(self)

        # Add actions for deleting rows from both tables
        deleteAction = context_menu.addAction("Delete Row")

        # Execute the context menu and get the selected action
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        # Determine which table was clicked
        reactants_pos = self.reactantsTable.viewport().mapFrom(self, event.pos())
        products_pos = self.productsTable.viewport().mapFrom(self, event.pos())

        if self.reactantsTable.geometry().contains(event.pos()) and action == deleteAction:
            # Determine the row that was clicked in the reactants table
            row = self.reactantsTable.rowAt(reactants_pos.y())
            if row != -1:
                self.reactantsTable.removeRow(row)

        elif self.productsTable.geometry().contains(event.pos()) and action == deleteAction:
            # Determine the row that was clicked in the products table
            row = self.productsTable.rowAt(products_pos.y())
            if row != -1:
                self.productsTable.removeRow(row)

    def warningDialog(self, errorType: str):
        """
        Makes a warning Dialog if the stoichiometry is not balanced or no reaction name is given
        :param errorType: "Name" or "Stoich"
        :return:
        """
        warningDialog = QDialog()
        layout = QVBoxLayout()

        match errorType:
            case "Stoich_critical":
                label = QLabel("<b>The sum of the mass stoichiometry of products exceeds the stoichiometry of the reactants!\n "
                               "This reaction is not balanced. The mass balance will not close” </b>")

            case "Stoich_non_critical":
                label = QLabel("<b>The sum of the stoichiometry of products and reactants is not equal, "
                               "This will not lead to errors but do be carefull could lead to unexpected results, "
                               "please check that the mass is balanced correctly</b>")

            case "Name":
                label = QLabel("<b>No Reaction name given! Please introduce one </b>")

            case _:
                raise ValueError('Unknown error occurred')

        layout.addWidget(label)
        # Add a button to close the dialog
        close_button = QPushButton("Close")
        close_button.clicked.connect(warningDialog.close)
        layout.addWidget(close_button)

        warningDialog.setLayout(layout)
        warningDialog.exec_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backspace or event.key() == Qt.Key_Delete:
            # Determine which table was clicked
            reactants_pos = self.reactantsTable.viewport().mapFrom(self, event.pos())
            products_pos = self.productsTable.viewport().mapFrom(self, event.pos())

            if self.reactantsTable.geometry().contains(event.pos()):
                # Determine the row that was clicked in the reactants table
                row = self.reactantsTable.rowAt(reactants_pos.y())
                if row != -1:
                    self.reactantsTable.removeRow(row)

            elif self.productsTable.geometry().contains(event.pos()):
                # Determine the row that was clicked in the products table
                row = self.productsTable.rowAt(products_pos.y())
                if row != -1:
                    self.productsTable.removeRow(row)



