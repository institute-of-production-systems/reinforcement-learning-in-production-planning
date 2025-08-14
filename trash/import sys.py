

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QLineEdit, QPushButton, QHBoxLayout, QLabel, QComboBox
from PyQt5.QtCore import QDateTime


class WorkstationManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Order and Workstation Manager")
        self.setGeometry(200, 200, 800, 300)

        self.initUI()

    def initUI(self):
        # Set up the central widget and layout
        self.central_widget = QWidget()
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)

        # Title of the section
        self.title_label = QLabel("Add Order")
        self.layout.addWidget(self.title_label)

        # Create a horizontal layout for Order ID, Workstation, and Available Workers
        order_layout = QHBoxLayout()

        # Order ID section
        self.order_id_label = QLabel("Order ID")
        self.order_id_input = QLineEdit("Order 1")  # Pre-filled order ID
        order_layout.addWidget(self.order_id_label)
        order_layout.addWidget(self.order_id_input)

        # Workstation section
        self.workstation_label = QLabel("Workstation")
        self.workstation_combo = QComboBox()
        self.workstation_combo.addItems(["Workstation 1", "Workstation 2", "Workstation 3"])
        order_layout.addWidget(self.workstation_label)
        order_layout.addWidget(self.workstation_combo)

        # Available Workers section
        self.workers_label = QLabel("Available Workers")
        self.workers_input = QLineEdit()  # Manual input for available workers
        order_layout.addWidget(self.workers_label)
        order_layout.addWidget(self.workers_input)

        # Add order button
        self.add_order_button = QPushButton("Add Order")
        self.add_order_button.clicked.connect(self.add_order)
        self.layout.addLayout(order_layout)
        self.layout.addWidget(self.add_order_button)

        # Display orders in a table below
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(3)  # Now we have 3 columns: Order ID, Workstation, and Available Workers
        self.orders_table.setHorizontalHeaderLabels(
            ["Order ID", "Workstation", "Available Workers"]
        )

        self.layout.addWidget(self.orders_table)

    def add_order(self):
        """
        Add the order data to the table when the button is clicked.
        """
        order_id = self.order_id_input.text()
        workstation = self.workstation_combo.currentText()
        workers = self.workers_input.text()

        # Add a new row in the table with order details
        row_position = self.orders_table.rowCount()
        self.orders_table.insertRow(row_position)

        self.orders_table.setItem(row_position, 0, QTableWidgetItem(order_id))
        self.orders_table.setItem(row_position, 1, QTableWidgetItem(workstation))
        self.orders_table.setItem(row_position, 2, QTableWidgetItem(workers))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WorkstationManagerApp()
    window.show()
    sys.exit(app.exec_())

