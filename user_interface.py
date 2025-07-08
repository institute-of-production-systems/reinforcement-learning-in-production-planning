import sys
import math
import copy
import base64
import json
import ast
import numpy as np
#import matplotlib
#matplotlib.use('QtAgg')
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap, QStandardItemModel, QStandardItem, QIcon
from PyQt5.QtCore import Qt, QRect, QModelIndex, QSize
from PyQt5.QtWidgets import QWidget, QDialogButtonBox, QRadioButton, QDialog, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtWidgets import QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QListWidget, QComboBox
from PyQt5.QtWidgets import QInputDialog, QMenu, QMessageBox, QListWidgetItem, QGridLayout, QDateTimeEdit
from PyQt5.QtWidgets import QStyledItemDelegate, QHeaderView, QCheckBox, QFrame, QScrollArea, QSlider, QGroupBox, QSizePolicy
from PyQt5.QtWidgets import QWizard, QWizardPage, QTabWidget, QApplication, QMainWindow, QFileDialog, QStyle, QToolBar, QAction
from PyQt5.QtWidgets import QStackedWidget, QFormLayout, QTreeView, QStackedLayout
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from product_instructions import ProductPalette
from order_list import OrderList, Order
from production_system import *
from simulation import ProductionSystemSimulation
from plan_visualizer import SchedulePlotter, TimeSeriesPlotter
from muzero.muzero import MuZero, CPUActor
from file_utils import object_to_dict

import ray
import pickle
import cloudpickle

class OperationDialog(QDialog):
    def __init__(self, operation):
        super().__init__()

        self.operation = operation  # reference to the operation to be modified by inputs

        self.setWindowTitle(f"Inputs and outputs of operation {self.operation.text()}")

        #print(operation.components)
        #self.setFixedSize(800, 400)

        # Dialog buttons
        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Main layout for the dialog
        main_layout = QVBoxLayout()

        # Layout for operation data (columns for components, capabilities, tools, and output)
        operation_data_layout = QHBoxLayout()

        # 1. Components column
        self.components_layout = QVBoxLayout()
        comp_col_label = QLabel("Component names and quantities")
        comp_col_label.setFixedWidth(200)
        self.components_layout.addWidget(comp_col_label)
        self.add_comp_button = QPushButton("Add component")
        #self.add_comp_button.setFixedWidth(100)
        self.add_comp_button.clicked.connect(self.add_component_fields)
        self.components_layout.addWidget(self.add_comp_button)
        self.components_layout.setAlignment(Qt.AlignTop)

        # 2. Capabilities column
        self.capabilities_layout = QVBoxLayout()
        cap_label = QLabel("Capabilities")
        cap_label.setFixedWidth(200)
        self.capabilities_layout.addWidget(cap_label)
        self.add_cap_button = QPushButton("Add capability")
        self.add_cap_button.clicked.connect(self.add_capability_fields)
        self.capabilities_layout.addWidget(self.add_cap_button)
        self.capabilities_layout.setAlignment(Qt.AlignTop)

        # 3. Tools column
        self.tools_layout = QVBoxLayout()
        tools_label = QLabel("Tools")
        tools_label.setFixedWidth(200)
        self.tools_layout.addWidget(tools_label)
        self.add_tool_button = QPushButton("Add tool")
        self.add_tool_button.clicked.connect(self.add_tool_fields)
        self.tools_layout.addWidget(self.add_tool_button)
        self.tools_layout.setAlignment(Qt.AlignTop)

        # 4. Processing time
        self.proc_time_layout = QVBoxLayout()
        proc_time_label = QLabel("Processing time")
        proc_time_label.setFixedWidth(125)
        self.proc_time_layout.addWidget(proc_time_label)
        pt_value_field = QLineEdit("0")
        pt_unit_field = QComboBox()
        pt_unit_field.addItems(['s', 'min', 'h', 'd'])
        pt_unit_field.setFixedWidth(50)
        pt_layout = QHBoxLayout()
        pt_layout.addWidget(pt_value_field)
        pt_layout.addWidget(pt_unit_field)
        pt_layout.setAlignment(Qt.AlignTop)
        self.proc_time_layout.addLayout(pt_layout)
        self.proc_time_layout.setAlignment(Qt.AlignTop)

        # 5. Output name column
        self.output_layout = QVBoxLayout()
        output_label = QLabel("Output name")
        output_label.setFixedWidth(200)
        self.output_layout.addWidget(output_label)
        self.output_field = QLineEdit("Enter output ID")
        self.output_layout.addWidget(self.output_field)
        self.output_layout.setAlignment(Qt.AlignTop)

        # Connect Save button to data saving functions
        self.buttonBox.accepted.connect(self.save_component_data)
        self.buttonBox.accepted.connect(self.save_capability_data)
        self.buttonBox.accepted.connect(self.save_tool_data)
        self.buttonBox.accepted.connect(self.save_processing_time_data)
        self.buttonBox.accepted.connect(self.save_output_id)

        # Add each column layout to the operation data layout
        operation_data_layout.addLayout(self.components_layout)
        operation_data_layout.addLayout(self.capabilities_layout)
        operation_data_layout.addLayout(self.tools_layout)
        operation_data_layout.addLayout(self.proc_time_layout)
        operation_data_layout.addLayout(self.output_layout)

        # Add operation data layout and buttons to the main layout
        main_layout.addLayout(operation_data_layout)
        main_layout.addWidget(self.buttonBox)

        # Placeholders for tool requirement and effect info
        self.temp_tool_req_dict = {}

        # Display all data already stored in the node
        self.load_node_data()

        self.setLayout(main_layout)

    # Method to add component input fields
    def add_component_fields(self):
        # ToDo: Hint for the user to input required lengths of solid raw materials (profiles, rods) in mm!
        # Maybe a general tutorial for dealing with solid raw materials is needed because it's kind of specific and may seem weird.
        component_name_field = QLineEdit("Enter name")
        component_qty_field = QLineEdit("1")
        component_qty_field.setFixedWidth(50)  # To keep the fields aligned
        row_layout = QHBoxLayout()
        row_layout.addWidget(component_name_field)
        row_layout.addWidget(component_qty_field)
        self.components_layout.addLayout(row_layout)

    # Method to add capability input fields
    def add_capability_fields(self):
        capability_field = QLineEdit("Enter capability")
        self.capabilities_layout.addWidget(capability_field)

    def edit_tool_requirements_effects(self, tool_sel_combo):
        # tool requirements and effects = tre
        tre_dialog = QDialog()
        tre_dialog.setWindowTitle(f"Requirements and effects on tool {tool_sel_combo.currentText()}")
        tre_dialog.setMinimumWidth(700)
        tre_layout = QVBoxLayout()  
        add_req_eff_btn = QPushButton("Add requirement and effect")
        tre_layout.addWidget(add_req_eff_btn)
        formula_hint_lbl = QLabel("Property delta after operation is calculated as a * (x ^ b) + c, where x is the property value on operation start.")
        tre_layout.addWidget(formula_hint_lbl)
        tre_table = QTableWidget()
        tre_table.setColumnCount(7)
        tre_table.setHorizontalHeaderLabels(
            ["Property", "Min", "Max", "Unit", "a", "b", "c"]
        )
        tre_table.setColumnWidth(0, 200)
        tre_layout.addWidget(tre_table)
        def add_tre_row():
            row_position = tre_table.rowCount()
            tre_table.insertRow(row_position)
            tre_table.setItem(row_position, 0, QTableWidgetItem("Property"))
            tre_table.setItem(row_position, 1, QTableWidgetItem("0.0"))  # min
            tre_table.setItem(row_position, 2, QTableWidgetItem("0.0"))  # max
            tre_table.setItem(row_position, 3, QTableWidgetItem("Unit"))
            tre_table.setItem(row_position, 4, QTableWidgetItem("0.0"))  # a
            tre_table.setItem(row_position, 5, QTableWidgetItem("0.0"))  # b
            tre_table.setItem(row_position, 6, QTableWidgetItem("0.0"))  # c
        add_req_eff_btn.clicked.connect(add_tre_row)

        # Retrieve tool requirements if available
        if self.operation.tools:
            self.temp_tool_req_dict = self.operation.tools

        if self.temp_tool_req_dict and (tool_sel_combo.currentText() in self.temp_tool_req_dict.keys()):
            print("Temp tool requirement dictionary:")
            print(self.temp_tool_req_dict[tool_sel_combo.currentText()])
            for k,v in self.temp_tool_req_dict[tool_sel_combo.currentText()].items():
                row_position = tre_table.rowCount()
                tre_table.insertRow(row_position)
                tre_table.setItem(row_position, 0, QTableWidgetItem(k))
                tre_table.setItem(row_position, 1, QTableWidgetItem(str(v['Min'])))
                tre_table.setItem(row_position, 2, QTableWidgetItem(str(v['Max'])))
                tre_table.setItem(row_position, 3, QTableWidgetItem(str(v['Unit'])))
                tre_table.setItem(row_position, 4, QTableWidgetItem(str(v['a'])))
                tre_table.setItem(row_position, 5, QTableWidgetItem(str(v['b'])))
                tre_table.setItem(row_position, 6, QTableWidgetItem(str(v['c'])))
                
        
        # Save or cancel tool requirements and effects of selected tool
        def accept_tre():
            tre_dict = {}
            for row in range(tre_table.rowCount()):
                dict_item = {tre_table.item(row,0).text(): {'Min': float(tre_table.item(row,1).text()),
                                                            'Max': float(tre_table.item(row,2).text()),
                                                            'Unit': tre_table.item(row,3).text(),
                                                            'a': float(tre_table.item(row,4).text()),
                                                            'b': float(tre_table.item(row,5).text()),
                                                            'c': float(tre_table.item(row,6).text())    
                }}
                tre_dict.update(dict_item)
            self.temp_tool_req_dict.update({tool_sel_combo.currentText(): tre_dict})
            
        save_tre_btn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(save_tre_btn)
        buttonBox.accepted.connect(tre_dialog.accept)
        buttonBox.accepted.connect(accept_tre)
        buttonBox.rejected.connect(tre_dialog.reject)
        tre_layout.addWidget(buttonBox)

        # ToDo: validity check of property names and values

        tre_dialog.setLayout(tre_layout)
        tre_dialog.exec_()

    # Method to add tool input fields
    def add_tool_fields(self):
        #tool_field = QLineEdit("Tool ID")
        #self.tools_layout.addWidget(tool_field)
        # Layout elements
        tool_req_lt = QHBoxLayout()
        tool_sel_combo = QComboBox()
        tool_req_edit_btn = QPushButton("Edit")
        # Populate with items and connect to dialogs
        tool_sel_combo.addItem("")  # for no tool selected
        tool_id_list = main_window.production_resources_tab.production_system.tools.keys()
        tool_sel_combo.addItems(tool_id_list)
        tool_req_edit_btn.clicked.connect(lambda: self.edit_tool_requirements_effects(tool_sel_combo=tool_sel_combo))
        # Add everything to the layout
        tool_req_lt.addWidget(tool_sel_combo)
        tool_req_lt.addWidget(tool_req_edit_btn)
        self.tools_layout.addLayout(tool_req_lt)

    # Method to save data contained in input fields
    def save_component_data(self):
        comp_data = {}
        for i in range(2, self.components_layout.count()):
            row_layout = self.components_layout.itemAt(i).layout()
            component_name = row_layout.itemAt(0).widget().text()
            component_quantity = int(row_layout.itemAt(1).widget().text())
            if component_quantity > 0:
                comp_data.update({component_name: component_quantity})
            else:
                print("Skipping component with quantity <= 0")
        self.operation.components = comp_data
        print(self.operation.components)

    def save_capability_data(self):
        capa_data = []
        for i in range(2, self.capabilities_layout.count()):
            capability = self.capabilities_layout.itemAt(i).widget().text()
            capa_data.append(capability)
        self.operation.capabilities = capa_data
        print(self.operation.capabilities)

    def save_tool_data(self):
        self.operation.tools = copy(self.temp_tool_req_dict)
        print("Saved operation tools:")
        print(self.operation.tools)

    def save_processing_time_data(self):
        pt_val = 0
        pt_unit = ''
        row_layout = self.proc_time_layout.itemAt(1).layout()
        # ToDo: Definitely check input data format, don't let the program crash because of wrong decimal point separator!
        pt_val = float(row_layout.itemAt(0).widget().text())
        pt_unit = row_layout.itemAt(1).widget().currentText()
        self.operation.processing_time_value = pt_val
        self.operation.processing_time_unit = pt_unit
        print(self.operation.processing_time_value, self.operation.processing_time_unit)

    def save_output_id(self):
        self.operation.output_name = self.output_layout.itemAt(1).widget().text()
        print(self.operation.output_name)

    def load_node_data(self):
        # Components
        if self.operation.components:
            for k,v in self.operation.components.items():
                component_name_field = QLineEdit(k)
                component_qty_field = QLineEdit(str(v))
                component_qty_field.setFixedWidth(50)  # To keep the fields aligned
                row_layout = QHBoxLayout()
                row_layout.addWidget(component_name_field)
                row_layout.addWidget(component_qty_field)
                self.components_layout.addLayout(row_layout)
        if self.operation.capabilities:
            for c in self.operation.capabilities:
                capability_field = QLineEdit(c)
                self.capabilities_layout.addWidget(capability_field)
        if self.operation.tools:
            self.temp_tool_req_dict = self.operation.tools  # ToDo: check if this works correctly
            for tool, req_eff in self.operation.tools.items():
                # ToDo: use combo boxes and load tool requirements and effects to be displayed if we click "Edit"
                # self.temp_tool_req_dict...
                tool_req_lt = QHBoxLayout()
                tool_sel_combo = QComboBox()
                tool_req_edit_btn = QPushButton("Edit")
                # Populate with items and connect to dialogs
                tool_sel_combo.addItem("")  # for no tool selected
                tool_id_list = main_window.production_resources_tab.production_system.tools.keys()
                tool_sel_combo.addItems(tool_id_list)
                # Select right tool
                sel_idx = tool_sel_combo.findText(tool)
                tool_sel_combo.setCurrentIndex(sel_idx)
                print(type(tool_sel_combo))
                # https://docs.python.org/3/faq/programming.html#why-do-lambdas-defined-in-a-loop-with-different-values-all-return-the-same-result
                tool_req_edit_btn.clicked.connect(lambda clicked, tsc=tool_sel_combo: self.edit_tool_requirements_effects(tool_sel_combo=tsc))
                # Add everything to the layout
                tool_req_lt.addWidget(tool_sel_combo)
                tool_req_lt.addWidget(tool_req_edit_btn)
                self.tools_layout.addLayout(tool_req_lt)
        if self.operation.processing_time_value > 0.0:
            self.proc_time_layout.itemAt(1).layout().itemAt(0).widget().setText(str(self.operation.processing_time_value))
            index = self.proc_time_layout.itemAt(1).layout().itemAt(1).widget().findText(self.operation.processing_time_unit)
            self.proc_time_layout.itemAt(1).layout().itemAt(1).widget().setCurrentIndex(index)
        if self.operation.output_name != "":
            self.output_layout.itemAt(1).widget().setText(self.operation.output_name)

class OperationNode(QLabel):
    connect_to_signal = QtCore.pyqtSignal(object)  # Signal to initiate connection with self as the argument
    clicked_signal = QtCore.pyqtSignal(object)  # Signal emitted on node click
    disconnect_from_signal = QtCore.pyqtSignal(object)  # Signal to destroy a connection
    moved_signal = QtCore.pyqtSignal(object)  # Signal emitted on node move

    """Custom QLabel that supports drag-and-drop functionality with precise cursor positioning."""
    def __init__(self, text, node_type, operation_name='', display_pos=None, node_uid=None, components={}, capabilities=[], tools={},
                 processing_time_value=0.0, processing_time_unit='', output_name=''):
        super().__init__(text)
        self.node_type = node_type
        self.operation_name = operation_name
        self.setFixedSize(100, 50)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setStyle()
        self.offset = QtCore.QPoint(0, 0)  # Initialize to track the click offset
        self.dropped = False  # To track whether the node is dropped in the workspace
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_node_menu)
        self.display_pos = display_pos
        self.node_uid = node_uid
        # Operation requirements and outputs
        self.components = components  # key: component name, value: quantity
        self.capabilities = capabilities  # list of capabilities that are required from resources that execute this operation
        self.tools = tools  # dictionary of required tools with requirements and effects
        self.processing_time_value = processing_time_value  # how long the operation takes
        self.processing_time_unit = processing_time_unit
        self.output_name = output_name  # name of the part or subassembly that leaves the operation after processing

    def __getstate__(self):
        # Only include serializable attributes
        #try:
        #    self.__delattr__("show_node_menu")
        #except AttributeError:
        #    pass
        state = {
            'node_type': self.node_type,
            'operation_name': self.operation_name,
            'display_pos': (self.display_pos.x(), self.display_pos.y()) if self.display_pos else None,
            'node_uid': self.node_uid,
            'components': self.components,
            'capabilities': self.capabilities,
            'tools': self.tools,
            'processing_time_value': self.processing_time_value,
            'processing_time_unit': self.processing_time_unit,
            'output_name': self.output_name,
        }
        return state

    def __setstate__(self, state):
        # Re-initialize the object with the saved state
        super().__init__()
        self.node_type = state['node_type']
        self.operation_name = state['operation_name']
        if state['display_pos']:
            self.display_pos = QtCore.QPoint(*state['display_pos'])
        else:
            self.display_pos = None
        self.node_uid = state['node_uid']
        self.components = state['components']
        self.capabilities = state['capabilities']
        self.tools = state['tools']
        self.processing_time_value = state['processing_time_value']
        self.processing_time_unit = state['processing_time_unit']
        self.output_name = state['output_name']
        self.setStyle()
        self.setFixedSize(100, 50)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.offset = QtCore.QPoint(0, 0)
        self.dropped = False
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_node_menu)

    def to_dict(self):
        return {
            "node_type": self.node_type,
            "operation_name": self.operation_name,
            "display_pos": object_to_dict((self.display_pos.x(), self.display_pos.y())),  # QtCore.QPoint
            "node_uid": self.node_uid,
            "components": object_to_dict(self.components),
            "capabilities": object_to_dict(self.capabilities),
            "tools": object_to_dict(self.tools),
            "processing_time_value": self.processing_time_value,
            "processing_time_unit": self.processing_time_unit,
            "output_name": self.output_name
        }

    def setStyle(self):
        """Set style based on node type."""
        if self.node_type == "Assembly":
            self.setStyleSheet("border-radius: 25px; background-color: #009ED7; border: 1px solid #000;")
        elif self.node_type == "Non-additive":
            self.setStyleSheet("background-color: #4ED0FF; border: 1px solid #000;")
        elif self.node_type == "Manufacture":
            self.setStyleSheet("background-color: #C4EFFF; border: 1px solid #000; border-radius: 10px;")

    def mousePressEvent(self, event):
        """Store the offset of the cursor within the label when the dragging starts."""
        if event.button() == QtCore.Qt.LeftButton:
            #print("mousePressEvent on ActivityNode")
            self.offset = event.pos()  # Capture where the cursor is within the label
            self.clicked_signal.emit(self)  # Emit the node itself
        super().mousePressEvent(event)  # Call parent handler for any default behavior

    def mouseMoveEvent(self, event):
        self.moved_signal.emit(self)
        """Start drag event with the label's offset."""
        if event.buttons() == QtCore.Qt.LeftButton:
            #print("mouseMoveEvent on ActivityNode")
            # Set up drag
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            mime_data.setText(self.node_type)  # Set node type as data
            
            # Store information in the mime data
            mime_data.setData("application/offset", 
                              f"{self.offset.x()},{self.offset.y()}".encode())
            mime_data.setData("application/name",
                              f"{self.operation_name}".encode())
            mime_data.setData("operation_components",
                              f"{str(self.components)}".encode())
            mime_data.setData("operation_capabilities",
                              f"{str(self.capabilities)}".encode())
            mime_data.setData("operation_tools",
                              f"{str(self.tools)}".encode())
            mime_data.setData("operation_processing_time_value",
                              f"{self.processing_time_value}".encode())
            mime_data.setData("operation_processing_time_unit",
                              f"{self.processing_time_unit}".encode())
            mime_data.setData("operation_output_name",
                              f"{self.output_name}".encode())
            
            # Record what original node needs to be replaced in connections list
            if self.dropped:
                mime_data.setData("application/original_uid",
                                  f"{self.node_uid}".encode())
            elif not self.dropped:
                mime_data.setData("application/original_uid",
                                  f"-1".encode())

            # Set pixmap to show during drag
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(self.offset)  # Set the hot spot to the click position within the label
            drag.setMimeData(mime_data)
            
            if not self.dropped:
                drag.exec_(QtCore.Qt.CopyAction)
            elif self.dropped:
                drag.exec_(QtCore.Qt.MoveAction)
                #self.destroy()  # Not sure if this is needed
                #print(f"Hiding {self.text()} {self.node_uid}")
                self.setHidden(True)

    def enterEvent(self, event):
        """Highlight border when hovering."""
        self.setStyleSheet(self.styleSheet() + "border: 2px solid #FFA500;")

    def leaveEvent(self, event):
        """Remove highlight border when not hovering."""
        self.setStyle()  # Re-apply the original style

    def show_node_menu(self, position):
        # Right-click context menu for renaming or deleting a product
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        connect_action = menu.addAction("Connect to...")
        connect_action.triggered.connect(lambda: self.connect_to_signal.emit(self))
        disconnect_action = menu.addAction("Disconnect from...")
        disconnect_action.triggered.connect(lambda: self.disconnect_from_signal.emit(self))
        components_action = menu.addAction("Inputs and outputs...")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec_(self.mapToGlobal(position))
        
        if action == rename_action:
            new_name, ok = QInputDialog.getText(self, "Rename node", "Enter new node name:")
            if ok and new_name:
                self.setText(new_name)
                self.operation_name = new_name
        elif action == delete_action:
            self.destroy()
            self.setHidden(True)
        elif action == components_action:
            components_dialog = OperationDialog(operation=self)
            components_dialog.exec()
            #self = components_dialog.operation

class GraphPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.product_selected = False  # whether any product is selected in the list

        # Main layout for the details panel
        layout = QVBoxLayout()

        # Palette at the top with draggable elements
        palette_layout = QHBoxLayout()
        palette_layout.setContentsMargins(0, 0, 0, 10)  # Position palette close to top

        # Draggable symbols for each node type
        self.assembly_symbol = OperationNode("Assembly", "Assembly")
        self.non_productive_symbol = OperationNode("Non-additive", "Non-additive")
        self.manufacture_symbol = OperationNode("Manufacture", "Manufacture")

        # Add symbols to palette
        palette_layout.addWidget(self.assembly_symbol)
        palette_layout.addWidget(self.non_productive_symbol)
        palette_layout.addWidget(self.manufacture_symbol)

        # Workspace area for dropped items
        self.workspace = QLabel("Workspace (Drag & drop operations here)")
        self.workspace.setStyleSheet("background-color: transparent #EFEFEF; border: 1px dashed #666;")
        self.workspace.setAlignment(QtCore.Qt.AlignCenter)
        self.workspace.setAcceptDrops(True)

        # Link workspace events to DetailsPanel's event methods
        self.workspace.dragEnterEvent = self.dragEnterEvent
        self.workspace.dropEvent = self.dropEvent

        # Stretch workspace to fill remaining area
        layout.addLayout(palette_layout)
        layout.addWidget(self.workspace, stretch=1)

        self.connections = []  # List to store connections as tuples (start_node, end_node)
        self.start_connect_node = None  # To hold the initial node in "Connect to..." mode
        self.start_destroy_node = None  # To hold the initial node in "Disconnect from..." mode
        self.node_uid = 0  # To uniquely identify the nodes
        self.just_dropped_node = None  # The node that was just moved around

        # Set layout for the details panel
        self.setLayout(layout)

    def dragEnterEvent(self, event):
        """Accept drag enter events if data contains a node type."""
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if self.product_selected == False:
            if QMessageBox.Ok == QMessageBox.warning(self,
                                          "Product assignment warning",
                                          "A product from the list must be selected to save graphs properly!",
                                          QMessageBox.Ok):
                pass

        node_type = event.mimeData().text()
        offset_data = event.mimeData().data("application/offset").data().decode()
        offset_x, offset_y = map(int, offset_data.split(","))
        
        drop_position = event.pos()
        #print(f"Drop position {drop_position}")
        adjusted_position = drop_position - QtCore.QPoint(offset_x, offset_y)
        
        name_data = event.mimeData().data("application/name").data().decode()
        uid_data = event.mimeData().data("application/original_uid").data().decode()
        comp_data = event.mimeData().data("operation_components").data().decode()
        capa_data = event.mimeData().data("operation_capabilities").data().decode()
        tool_data = event.mimeData().data("operation_tools").data().decode()
        ptv_data = event.mimeData().data("operation_processing_time_value").data().decode()
        ptu_data = event.mimeData().data("operation_processing_time_unit").data().decode()
        out_data = event.mimeData().data("operation_output_name").data().decode()
        
        #print('encoded comp data:')
        #print(comp_data)

        dropped_label = OperationNode(node_type if name_data == "" else name_data,
                                     node_type,
                                     display_pos=adjusted_position,
                                     node_uid=self.node_uid if int(uid_data) == -1 else int(uid_data),
                                     components=ast.literal_eval(comp_data),
                                     capabilities=ast.literal_eval(capa_data),
                                     tools=ast.literal_eval(tool_data),
                                     processing_time_value=float(ptv_data),
                                     processing_time_unit=ptu_data,
                                     output_name=out_data)
        # Any node dropped into the product's workspace gets a new unique number
        self.node_uid = self.node_uid + 1
        dropped_label.operation_name = name_data

        self.add_node(dropped_label)  # Register the new node

        self.just_dropped_node = dropped_label
        
        # Put the dropped label exactly where it was dropped
        dropped_label.move(adjusted_position)
        dropped_label.setParent(self.workspace)

        # Change mouseMoveEvent of the dropped label so it doesn't get copied but can be dragged around within the workspace
        dropped_label.dropped = True

        dropped_label.show()

        self.update()

        event.accept()

    def add_node(self, node):
        # Connect the node's signal to the initiate_connection method
        node.connect_to_signal.connect(self.initiate_connection)
        node.disconnect_from_signal.connect(self.destroy_connection)
        node.clicked_signal.connect(self.handle_node_click)  # Connect click signal to handler
        node.setParent(self)

    def handle_node_click(self, target_node):
        """Handle clicks on nodes for connection if in 'Connect to...' mode."""
        if self.start_connect_node and target_node != self.start_connect_node:
            # Store the connection and reset start_node
            self.connections.append((self.start_connect_node, target_node))
            #print(f"Connected {self.start_connect_node.text()} to {target_node.text()}.")
            self.start_connect_node = None  # Reset to exit connection mode
            self.update()  # Redraw to show connection
        if self.start_destroy_node and target_node != self.start_destroy_node:
            # Remove the connection and reset start_node
            self.connections = [c for c in self.connections if c != (self.start_destroy_node, target_node)]
            #print(f"Disconnected {self.start_destroy_node.text()} from {target_node.text()}.")
            self.start_destroy_node = None
            self.update()

    def initiate_connection(self, start_node):
        """Initiate connection mode from the selected start node."""
        self.start_connect_node = start_node
        #print(f"Initiated connection from: {start_node.text()}. Select another node.")

    def destroy_connection(self, start_node):
        """Enter connection destruction mode from the selected start node."""
        self.start_destroy_node = start_node
        #print(f"Destroying connection from: {start_node.text()}. Select another node.")

    def paintEvent(self, event):
        """Draw arrows for each connection."""
        #print("\nPaint event")

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Erase previously drawn lines
        painter.eraseRect(self.rect())

        # Then redraw all existing connections
        pen = QPen(QColor(100, 100, 100), 2, Qt.SolidLine)
        painter.setPen(pen)

        # Refresh the connection list
        # In case of moved nodes
        for i,e in enumerate(self.connections):
            if self.just_dropped_node is None:
                break
            #print("Checking a connection for hidden nodes:")
            #print(f"Connection: {e[0].text()} {e[0].node_uid} (hidden = {e[0].isHidden()}) --> {e[1].text()} {e[1].node_uid} (hidden = {e[1].isHidden()})")
            if e[0].isHidden():
                #print("Start node is hidden")
                if self.just_dropped_node.node_uid == e[0].node_uid:
                    temp = list(self.connections[i])
                    temp[0] = self.just_dropped_node
                    self.connections[i] = tuple(temp)
            if e[1].isHidden():
                #print("End node is hidden")
                if self.just_dropped_node.node_uid == e[1].node_uid:
                    temp = list(self.connections[i])
                    temp[1] = self.just_dropped_node
                    self.connections[i] = tuple(temp)
        # In case of deleted nodes
        self.connections = [(source,target) for (source,target) in copy(self.connections) if source.isHidden()==False and target.isHidden()==False]

        print("--- Connection list after eliminating hidden nodes: ---")

        for start_node, end_node in self.connections:
            # Print out the list of connections with relevant data
            print(f"Connection: {start_node.text()} {start_node.node_uid} (hidden = {start_node.isHidden()}) --> {end_node.text()} {end_node.node_uid} (hidden = {end_node.isHidden()})")
            if start_node.isHidden() or end_node.isHidden():
                continue
            self.draw_arrow(painter, start_node, end_node, pen.color())
            
    def draw_arrow(self, painter, start_node, end_node, color):
        """Draws an arrow from start_node to end_node using the painter."""

        #start_pos = start_node.display_pos + QtCore.QPoint(10, 70)
        #end_pos = end_node.display_pos + QtCore.QPoint(10, 70)
        start_pos = start_node.geometry().center() + QtCore.QPoint(10, 70)
        end_pos = end_node.geometry().center() + QtCore.QPoint(10, 70)

        #print(f"Draw arrow from {start_node.text()} at {start_pos} to {end_node.text()} {end_pos}")

        # Draw the line from start to end
        painter.drawLine(start_pos, end_pos)

        # Calculate the midpoint of the line
        mid_x = (start_pos.x() + end_pos.x()) / 2.0
        mid_y = (start_pos.y() + end_pos.y()) / 2.0
        mid_pos = QtCore.QPointF(mid_x, mid_y)

        # Calculate arrowhead angle
        dx = end_pos.x() - start_pos.x()
        dy = end_pos.y() - start_pos.y()
        angle = math.atan2(dy, dx)

        # Arrowhead parameters
        arrow_size = 10
        arrow_angle = math.radians(30)  # 30 degrees for the arrowhead angle

        # Calculate the two points of the arrowhead
        p1 = mid_pos - QtCore.QPointF(
            arrow_size * math.cos(angle + arrow_angle),
            arrow_size * math.sin(angle + arrow_angle)
        )
        p2 = mid_pos - QtCore.QPointF(
            arrow_size * math.cos(angle - arrow_angle),
            arrow_size * math.sin(angle - arrow_angle)
        )

        # Create and fill the arrowhead path
        path = QtGui.QPainterPath()
        path.moveTo(mid_pos)
        path.lineTo(p1)
        path.lineTo(p2)
        path.lineTo(mid_pos)
        painter.fillPath(path, color)

class ProductInstructionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        ##########################
        ### Display and layout ###
        ##########################

        main_layout = QHBoxLayout()

        # Left panel: list of products and button
        left_panel = QVBoxLayout()
        self.new_product_button = QPushButton("Create new product instruction")
        self.new_product_button.clicked.connect(self.create_new_product)

        self.product_list_widget = QListWidget()
        #self.product_list_widget.itemClicked.connect(self.show_product_graph)
        self.product_list_widget.currentItemChanged.connect(self.update_product_graph_display)
        self.product_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.product_list_widget.customContextMenuRequested.connect(self.show_product_menu)

        left_panel.addWidget(self.new_product_button)
        left_panel.addWidget(self.product_list_widget)

        # Details panel with drag-and-drop workspace
        self.graph_panel = GraphPanel()
        
        # Set layout structure
        main_layout.addLayout(left_panel, 1)
        main_layout.addWidget(self.graph_panel, 3)  # Stretch details panel to fill more space

        self.setLayout(main_layout)

        #######################
        ### Data management ###
        #######################

        # Datastructures to store product instructions
        self.product_palette = ProductPalette()
        
        # Load all serialized production graphs if there are any in /production_system_data


    def create_new_product(self):
        # Function to create a new product entry
        product_name = f"Product {self.product_list_widget.count() + 1}"
        item = QListWidgetItem(product_name)
        self.product_list_widget.addItem(item)
        self.product_palette.add_product_graph(product_name, [])

    def update_product_graph_display(self, current_item, previous_item):
        '''
        Displays the product graph of the clicked product
        '''
        self.graph_panel.product_selected = True

        # Save product graph of previously selected product (for visualization)
        if previous_item:
            self.clean_up_product_palette()
            self.product_palette.add_product_graph(previous_item.text(), self.graph_panel.connections)
        
        # Clear the workspace from operation nodes and from arrows

        # ToDo: Caution: nodes without connections will be lost!!!
        for obj in self.graph_panel.workspace.children():
            if isinstance(obj, OperationNode):
                obj.setHidden(True)

        for connection in self.graph_panel.connections:
            connection[0].setHidden(True)
            connection[1].setHidden(True)
            self.graph_panel.update()

        # Show and load the GraphPanel with the selected product's graph
        sel_prod_id = current_item.text()
        try:
            # Logic to load and display the production graph for the clicked product
            for connection in self.product_palette.product_palette[sel_prod_id]:
                connection[0].setHidden(False)
                connection[1].setHidden(False)
                self.graph_panel.connections.append(connection)
        except KeyError:
            print(f"Product {sel_prod_id} has no production graph!")

    def save_product_graph(self, item):
        '''
        Saves product graph when closing the program
        '''
        pass

    def clear_product_graph(self, item):
        # Remove all components on the currently displayed workspace, erase stored datastructures of the graph
        pass

    def show_product_menu(self, position):
        # Right-click context menu for renaming or deleting a product
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec_(self.product_list_widget.viewport().mapToGlobal(position))
        
        if action == rename_action:
            item = self.product_list_widget.itemAt(position)
            new_name, ok = QInputDialog.getText(self, "Rename Product", "Enter new product name:")
            if ok and new_name:
                item.setText(new_name)
        elif action == delete_action:
            item = self.product_list_widget.itemAt(position)
            row = self.product_list_widget.row(item)
            self.product_list_widget.takeItem(row)

    def rename_product(self, item):
        """Rename the selected product."""
        old_name = item.text()  # Get the current product name
        new_name, ok = QInputDialog.getText(self, "Rename Product", "New name:")

        if ok and new_name and new_name != old_name:
            item.setText(new_name)

            # Move connections from old name to new name in ProductPalette
            if old_name in self.product_palette.product_palette:
                self.product_palette.product_palette[new_name] = self.product_palette.product_palette.pop(old_name)

            self.clean_up_product_palette()

    def delete_product(self, item):
        """Delete the selected product from the list."""
        if not item:
            return  # No item selected
        
        product_name = item.text()

        # Remove from UI
        row = self.product_list_widget.row(item)
        self.product_list_widget.takeItem(row)

        # Remove from ProductPalette
        if product_name in self.product_palette.product_palette:
            del self.product_palette.product_palette[product_name]
            print(f"Deleted {product_name} from ProductPalette")  # Debugging

        # Ensure cleanup runs so JSON is updated before saving
        self.clean_up_product_palette()

        # Force UI refresh to reflect deletion
        self.product_list_widget.repaint()

    def clean_up_product_palette(self):
        """Remove all product instructions with product names not shown in the product list on the left."""
        visible_items = [self.product_list_widget.item(x).text() for x in range(self.product_list_widget.count())]

        #keep_palette = [(id, cl) for (id, cl) in self.product_palette.product_palette.items() if id in visible_items]
        #self.product_palette = ProductPalette(dict(keep_palette))

        # Filter out deleted products
        self.product_palette.product_palette = {
            product_id: self.product_palette.product_palette[product_id]
            for product_id in visible_items if product_id in self.product_palette.product_palette
        }



class OrderDetailsDialog(QDialog):
    def __init__(self, order):
        super().__init__()
        self.order = order  # reference to the order to be modified by inputs
        self.setWindowTitle(f"Product list of order {self.order.order_id}")

        # Dialog buttons
        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Main layout for the dialog
        main_layout = QVBoxLayout()

        # Horizontal layout for product list managing buttons
        prod_list_button_layout = QHBoxLayout()
        self.add_prod_button = QPushButton("Add product")
        self.add_prod_button.clicked.connect(self.add_product_row)
        prod_list_button_layout.addWidget(self.add_prod_button)

        # Horizontal layout for product list columns (input fields)
        prod_list_col_layout = QHBoxLayout()
        
        # Products column
        self.products_layout = QVBoxLayout()
        prod_col_label = QLabel("Product ID")
        prod_col_label.setFixedWidth(200)
        self.products_layout.addWidget(prod_col_label)
        self.products_layout.setAlignment(Qt.AlignTop)

        # Quantities column
        self.quantities_layout = QVBoxLayout()
        qty_label = QLabel("Quantity")
        qty_label.setFixedWidth(50)
        self.quantities_layout.addWidget(qty_label)
        self.quantities_layout.setAlignment(Qt.AlignTop)

        prod_list_col_layout.addLayout(self.products_layout)
        prod_list_col_layout.addLayout(self.quantities_layout)

        # Connect Save button to data saving functions
        self.buttonBox.accepted.connect(self.save_product_list)

        main_layout.addLayout(prod_list_button_layout)
        main_layout.addLayout(prod_list_col_layout)
        main_layout.addWidget(self.buttonBox)

        # Load already stored order details data
        self.load_order_data()

        self.setLayout(main_layout)

    def add_product_row(self):
        product_selection = QComboBox()
        # get product palette from product instructions tab
        # ToDo: Caution: maybe it's better to get the items actually displayed in the list (in case the datastructure wasn't updated?)
        products = list(main_window.product_instructions_tab.product_palette.product_palette.keys())
        product_selection.addItems(products)
        product_selection.setFixedHeight(20)
        self.products_layout.addWidget(product_selection)
        quantity_edit = QLineEdit("1")
        quantity_edit.setFixedHeight(20)
        self.quantities_layout.addWidget(quantity_edit)

    def save_product_list(self):
        prod_qty_dict = {}
        for i in range(1, self.products_layout.count()):
            p = self.products_layout.itemAt(i).widget().currentText()
            q = int(self.quantities_layout.itemAt(i).widget().text())
            if q > 0:
                prod_qty_dict.update({p: q})
            else:
                print("Skipping product with quantity <= 0")
        self.order.products = prod_qty_dict
        print(self.order.products)

    def load_order_data(self):
        product_set = list(main_window.product_instructions_tab.product_palette.product_palette.keys())
        if self.order.products:
            for k,v in self.order.products.items():
                product_name_field = QComboBox()
                product_name_field.addItems(product_set)
                p = product_name_field.findText(k)
                product_name_field.setCurrentIndex(p)
                product_qty_field = QLineEdit(str(v))
                product_qty_field.setFixedWidth(50)
                self.products_layout.addWidget(product_name_field)
                self.quantities_layout.addWidget(product_qty_field)
        # TODO: also for release and deadlines or unnecessary because stored in widgets anyway?

class OrderDataTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        order_data_tab_layout = QVBoxLayout()  # main layout of order data tab
        column_names_layout = QHBoxLayout()  # layout just for column names
        self.order_grid_layout = QGridLayout()  # contains horizontal "rows" for each order
        order_button_layout = QHBoxLayout()  # buttons above all orders to add new orders or edit advanced order parameters
        order_id_column = QVBoxLayout()
        products_column = QVBoxLayout()
        release_column = QVBoxLayout()
        deadline_column = QVBoxLayout()

        self.col_label_h = 20

        add_order_button = QPushButton("Add order")
        add_order_button.clicked.connect(lambda: self.add_new_order(provided_order=None))
        order_button_layout.addWidget(add_order_button)
        
        order_id_col_label = QLabel("Orders")
        self.order_id_col_w = 200
        order_id_col_label.setFixedWidth(self.order_id_col_w)
        order_id_col_label.setFixedHeight(self.col_label_h)
        order_id_column.addWidget(order_id_col_label)

        prod_col_label = QLabel("Products and quantities")
        self.prod_col_label_w = 200
        prod_col_label.setFixedWidth(self.prod_col_label_w)
        prod_col_label.setFixedHeight(self.col_label_h)
        products_column.addWidget(prod_col_label)

        release_col_label = QLabel("Release date")
        self.rel_col_label_w = 115
        release_col_label.setFixedWidth(self.rel_col_label_w)
        release_col_label.setFixedHeight(self.col_label_h)
        release_column.addWidget(release_col_label)

        deadline_col_label = QLabel("Deadline")
        self.dl_col_label_w = 115
        deadline_col_label.setFixedWidth(self.dl_col_label_w)
        deadline_col_label.setFixedHeight(self.col_label_h)
        deadline_column.addWidget(deadline_col_label)

        column_names_layout.addLayout(order_id_column)
        column_names_layout.addLayout(products_column)
        column_names_layout.addLayout(release_column)
        column_names_layout.addLayout(deadline_column)
        column_names_layout.setAlignment(Qt.AlignTop)

        self.order_grid_layout.setAlignment(Qt.AlignTop)

        order_data_tab_layout.addLayout(order_button_layout)
        order_data_tab_layout.addLayout(column_names_layout)
        order_data_tab_layout.addLayout(self.order_grid_layout)
        order_data_tab_layout.setAlignment(Qt.AlignTop)

        self.setLayout(order_data_tab_layout)

        self.currently_edited_row = -1
        self.temp_order_ids = []

        self.order_list = OrderList()

    def add_new_order(self, provided_order : Order = None):
        '''Adds a new row to the order overview (order_grid_layout)'''
        order_display_name = f"Order {self.order_grid_layout.rowCount()}" if not provided_order else provided_order.order_id  # starts with 1 on init for some reason!
        self.order_list.add_order(order_display_name, Order(order_id=order_display_name) if not provided_order else provided_order)  # add empty order
        self.temp_order_ids.append(order_display_name)
        order_id_field = QLineEdit(order_display_name)
        
        order_id_field.editingFinished.connect(self.editingFinished)
        order_id_field.editingFinished.connect(self.rename_order)
        #order_id_field.textChanged
        #order_id_field.textEdited
        order_id_field.setFixedWidth(self.order_id_col_w)
        order_id_field.setAlignment(Qt.AlignTop)

        edit_prod_list_button = QPushButton("Edit product list")
        edit_prod_list_button.setFixedWidth(self.prod_col_label_w)
        edit_prod_list_button.clicked.connect(self.buttonClicked)
        edit_prod_list_button.clicked.connect(self.show_order_details_dialog)

        release_time = QtCore.QDateTime.currentDateTime() if not provided_order else QtCore.QDateTime.fromString(provided_order.release_time, 'dd.MM.yyyy HH:mm')
        order_release_field = QDateTimeEdit(release_time)
        order_release_field.setFixedWidth(self.rel_col_label_w)
        order_release_field.setAlignment(Qt.AlignTop)

        deadline = QtCore.QDateTime.currentDateTime() if not provided_order else QtCore.QDateTime.fromString(provided_order.deadline, 'dd.MM.yyyy HH:mm')
        order_deadline_field = QDateTimeEdit(deadline)
        order_deadline_field.setFixedWidth(self.dl_col_label_w)
        order_deadline_field.setAlignment(Qt.AlignTop)

        i = self.order_grid_layout.rowCount()
        j = self.order_grid_layout.columnCount()
        self.order_grid_layout.addWidget(order_id_field, i, 0)
        self.order_grid_layout.addWidget(edit_prod_list_button, i, 1)
        self.order_grid_layout.addWidget(order_release_field, i, 2)
        self.order_grid_layout.addWidget(order_deadline_field, i, 3)

    def show_order_details_dialog(self):
        # Get order id by the edited row idx
        order_id = self.order_grid_layout.itemAtPosition(self.currently_edited_row, 0).widget().text()
        order = self.order_list.order_list[order_id]
        order_details_dialog = OrderDetailsDialog(order=order)
        order_details_dialog.exec()

    def buttonClicked(self):
        button = self.sender()
        idx = self.order_grid_layout.indexOf(button)
        location = self.order_grid_layout.getItemPosition(idx)
        self.currently_edited_row = location[0]

    def editingFinished(self):
        order_name_input = self.sender()
        idx = self.order_grid_layout.indexOf(order_name_input)
        location = self.order_grid_layout.getItemPosition(idx)
        self.currently_edited_row = location[0]
        #print(self.currently_edited_row)

    def rename_order(self):
        order = self.order_list.order_list[self.temp_order_ids[self.currently_edited_row - 1]]
        order_id_after = self.order_grid_layout.itemAtPosition(self.currently_edited_row, 0).widget().text()
        order.order_id = order_id_after
        self.temp_order_ids[self.currently_edited_row - 1] = order_id_after
        self.order_list.add_order(order_id_after, order)
        self.clean_up_order_list()

    def clean_up_order_list(self):
        """Removes all orders whose IDs are not displayed from order list"""
        visible_orders = [self.order_grid_layout.itemAtPosition(i, 0).widget().text() for i in range(1, self.order_grid_layout.rowCount())]
        keep_orders = [(id, ordr) for (id, ordr) in self.order_list.order_list.items() if id in visible_orders]
        self.order_list = OrderList(dict(keep_orders))

    def complete_order_data(self):
        """Reads order release dates and order deadlines to complete the OrderList to be used by other tabs"""
        orders = {}
        #print(self.order_grid_layout.rowCount())
        for i in range(1, self.order_grid_layout.rowCount()):
            order_id = self.order_grid_layout.itemAtPosition(i, 0).widget().text()
            products = self.order_list.order_list[order_id].products
            release_time_widget = self.order_grid_layout.itemAtPosition(i, 2).widget()
            release_time = release_time_widget.dateTime().toString(release_time_widget.displayFormat())
            deadline_widget = self.order_grid_layout.itemAtPosition(i, 3).widget()
            deadline = deadline_widget.dateTime().toString(deadline_widget.displayFormat())
            order_obj = Order(order_id=order_id, products=products, release_time=release_time, deadline=deadline)
            orders.update({order_id: order_obj})
        self.order_list = OrderList(order_list=orders)
        return self.order_list

class CheckableComboBox(QComboBox):

    # Subclass Delegate to increase item height
    class Delegate(QStyledItemDelegate):
        def sizeHint(self, option, index):
            size = super().sizeHint(option, index)
            size.setHeight(20)
            return size

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make the combo editable to set a custom text, but readonly
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        # Make the lineedit the same color as QPushButton
        palette = QtGui.QPalette()
        palette.setBrush(QtGui.QPalette.Base, palette.button())
        self.lineEdit().setPalette(palette)

        # Use custom delegate
        self.setItemDelegate(CheckableComboBox.Delegate())

        # Update the text when an item is toggled
        self.model().dataChanged.connect(self.updateText)

        # Hide and show popup when clicking the line edit
        self.lineEdit().installEventFilter(self)
        self.closeOnLineEditClick = False

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

    def resizeEvent(self, event):
        # Recompute text to elide as needed
        self.updateText()
        super().resizeEvent(event)

    def eventFilter(self, object, event):

        if object == self.lineEdit():
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                if self.closeOnLineEditClick:
                    self.hidePopup()
                else:
                    self.showPopup()
                return True
            return False

        if object == self.view().viewport():
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                index = self.view().indexAt(event.pos())
                item = self.model().item(index.row())

                if item.checkState() == Qt.Checked:
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setCheckState(Qt.Checked)
                return True
        return False

    def showPopup(self):
        super().showPopup()
        # When the popup is displayed, a click on the lineedit should close it
        self.closeOnLineEditClick = True

    def hidePopup(self):
        super().hidePopup()
        # Used to prevent immediate reopening when clicking on the lineEdit
        self.startTimer(100)
        # Refresh the display text when closing
        self.updateText()

    def timerEvent(self, event):
        # After timeout, kill timer, and reenable click on line edit
        self.killTimer(event.timerId())
        self.closeOnLineEditClick = False

    def updateText(self):
        texts = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == Qt.Checked:
                texts.append(self.model().item(i).text())
        text = ", ".join(texts)

        # Compute elided text (with "...")
        metrics = QtGui.QFontMetrics(self.lineEdit().font())
        elidedText = metrics.elidedText(text, Qt.ElideRight, self.lineEdit().width())
        self.lineEdit().setText(elidedText)

    def addItem(self, text, data=None):
        item = QStandardItem()
        item.setText(text)
        if data is None:
            item.setData(text)
        else:
            item.setData(data)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setData(Qt.Unchecked, Qt.CheckStateRole)
        self.model().appendRow(item)

    def addItems(self, texts, datalist=None):
        for i, text in enumerate(texts):
            try:
                data = datalist[i]
            except (TypeError, IndexError):
                data = None
            self.addItem(text, data)

    def currentData(self):
        # Return the list of selected items data
        res = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == Qt.Checked:
                res.append(self.model().item(i).data())
        return res

class VerticalHeader(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setDefaultAlignment(Qt.AlignCenter)
        self.setFixedHeight(80)  # Adjust header height for better visibility

    def paintSection(self, painter, rect, logicalIndex):
        # Save the painter's state
        painter.save()

        # Translate and rotate the painter for vertical text
        painter.translate(rect.center().x(), rect.center().y())
        painter.rotate(-90)

        # Create a QRect for the text bounds
        text_rect = QRect(-rect.height() // 2, -rect.width() // 2, rect.height(), rect.width())

        # Get the header text
        text = self.model().headerData(logicalIndex, self.orientation(), Qt.DisplayRole)
        if text:
            painter.drawText(text_rect, Qt.AlignCenter, text)

        # Restore the painter's state
        painter.restore()


class VerticalLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        #self.setStyleSheet("writing-mode: vertical-lr;")  # Set vertical writing mode


class SetupMatrixTable(QWidget):
    def __init__(self, setup_table=None):
        super().__init__()
        self.setup_table = setup_table  # dict of dicts [row][column]
        self.initUI()

    def initUI(self):

        # Create a table widget
        table = QTableWidget()

        # Set the vertical header labels (Editable)
        row_headers = list(self.setup_table.keys()) if self.setup_table is not None else []
        #row_headers.append('No tool')
        table.setRowCount(len(row_headers))
        #row_headers = ["Tool 1", "Tool 2", "Tool 3", "No Tool"]
        table.setVerticalHeaderLabels(row_headers)

        # Set the horizontal header labels (Editable)
        col_headers = row_headers
        table.setColumnCount(len(col_headers))
        #col_headers = ["Tool 1", "Tool 2", "Tool 3", "No Tool"]
        table.setHorizontalHeaderLabels(col_headers)

        # Make headers editable by setting items
        for row in range(table.rowCount()):
            item = QTableWidgetItem(row_headers[row])
            item.setFlags(item.flags() | Qt.ItemIsEditable)  # Allow editing
            table.setVerticalHeaderItem(row, item)

        for col in range(table.columnCount()):
            item = QTableWidgetItem(col_headers[col])
            item.setFlags(item.flags() | Qt.ItemIsEditable)  # Allow editing
            table.setHorizontalHeaderItem(col, item)

        # Populate the table with values for display if there are any
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                try:
                    table_item = QTableWidgetItem(str(self.setup_table[row_headers[row]][col_headers[col]]))
                    table.setItem(row, col, table_item)
                except KeyError:
                    # The provided setup matrix doesn't have any value saved for this row & column, leave the cell empty
                    table_item = QTableWidgetItem('')
                    table.setItem(row, col, table_item)
                    
        # Replace the horizontal header with the custom vertical header
        vertical_header = VerticalHeader(Qt.Horizontal, table)
        table.setHorizontalHeader(vertical_header)

        # Stretch column headers to fit the table width
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        #table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # Set a smaller fixed height for the table
        #table.setFixedHeight(200)  # Adjust this value to make the table smaller or larger

        # Set smaller row heights (optional)
        for row in range(table.rowCount()):
            table.setRowHeight(row, 30)  # Set a smaller row height (default is 20)

        # Create the layout for the "To" label
        main_layout = QVBoxLayout()

        # Create and center the "To" label
        to_label = QLabel("To")
        to_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(to_label)

        # Create a horizontal layout for the table and the "From" label
        table_layout = QHBoxLayout()

        # Create the vertical "From" label
        from_label = VerticalLabel("From")
        from_label.setFixedWidth(30)  # Ensure proper width for the vertical label
        from_label.setFixedHeight(table.height())  # Ensure it has the same height as the table

        # Add the "From" label to the layout
        table_layout.addWidget(from_label)

        # Add the table to the layout
        table_layout.addWidget(table)

        # Add the table_layout to the main layout
        main_layout.addLayout(table_layout)

        # Set the layout of the window
        self.setLayout(main_layout)


class ProductionResourcesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resources_grid_layout = QGridLayout()

        # Worker capabilities list
        worker_capabilities_layout = QVBoxLayout()
        # Horizontal container for label and icon
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)  # Remove default margins
        worker_cap_label = QLabel("Worker capabilities")
        worker_cap_label.setFixedWidth(200)
        icon_path = "images/Worker_capabilities_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        # Add widgets to the container layout
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(worker_cap_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        worker_capabilities_layout.addWidget(container_widget)
        add_cap_button = QPushButton("Add worker capability")
        add_cap_button.clicked.connect(lambda: self.add_new_worker_capability(provided_str=None))
        worker_capabilities_layout.addWidget(add_cap_button)
        self.worker_cap_list_widget = QListWidget()
        self.worker_cap_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        worker_capabilities_layout.addWidget(self.worker_cap_list_widget)

        # Worker list
        workers_layout = QVBoxLayout()
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)  # Remove default margins
        workers_label = QLabel("Workers")
        workers_label.setFixedWidth(200)
        icon_path = "images/Worker_production_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(workers_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        workers_layout.addWidget(container_widget)
        add_wrkr_button = QPushButton("Add worker")
        add_wrkr_button.clicked.connect(lambda: self.add_new_worker(provided_dict=None))
        workers_layout.addWidget(add_wrkr_button)
        self.workers_list_widget = QListWidget()
        self.workers_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        workers_layout.addWidget(self.workers_list_widget)

        # Worker pool list
        worker_pools_layout = QVBoxLayout()
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        worker_pool_label = QLabel("Worker pools")
        worker_pool_label.setFixedWidth(200)
        icon_path = "images/Worker_pools_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(worker_pool_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        worker_pools_layout.addWidget(container_widget)
        add_pool_button = QPushButton("Add worker pool")
        add_pool_button.clicked.connect(lambda: self.add_new_pool(pool_id=None, provided_list=None))
        worker_pools_layout.addWidget(add_pool_button)
        self.worker_pool_list_widget = QListWidget()
        self.worker_pool_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        worker_pools_layout.addWidget(self.worker_pool_list_widget)

        # Machine capabilities
        machine_capabilities_layout = QVBoxLayout()
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        machine_cap_label = QLabel("Machine capabilities")
        machine_cap_label.setFixedWidth(200)
        icon_path = "images/Machine_capabilities_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(machine_cap_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        machine_capabilities_layout.addWidget(container_widget)
        #machine_capabilities_layout.addStretch()
        add_mac_button = QPushButton("Add machine capability")
        add_mac_button.clicked.connect(lambda: self.add_new_machine_capability(provided_str=None))
        machine_capabilities_layout.addWidget(add_mac_button)
        self.machine_cap_list_widget = QListWidget()
        self.machine_cap_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        machine_capabilities_layout.addWidget(self.machine_cap_list_widget)

        # Add Machine 
        machines_layout = QVBoxLayout()
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        machines_label = QLabel("Machines")
        machines_label.setFixedWidth(200)
        icon_path = "images/Machines_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(machines_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        machines_layout.addWidget(container_widget)
        add_machn_button = QPushButton("Add machine")
        add_machn_button.clicked.connect(lambda: self.add_new_machine(provided_dict=None))
        machines_layout.addWidget(add_machn_button)
        self.machines_list_widget = QListWidget()
        self.machines_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        machines_layout.addWidget(self.machines_list_widget)

        # Add Workstation
        workstation_layout = QVBoxLayout()
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        workstation_label = QLabel("Workstations")
        workstation_label.setFixedWidth(200)
        icon_path = "images/Workstations_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(workstation_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        workstation_layout.addWidget(container_widget)
        add_work_button = QPushButton("Add workstation")
        add_work_button.clicked.connect(lambda: self.add_new_workstation(provided_dict=None))
        workstation_layout.addWidget(add_work_button)
        self.workstation_list_widget = QListWidget()
        self.workstation_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        workstation_layout.addWidget(self.workstation_list_widget)

        # Tools
        tools_layout = QVBoxLayout()
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        tools_label = QLabel("Tools")
        tools_label.setFixedWidth(200)
        icon_path = "images/Tools_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(tools_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        tools_layout.addWidget(container_widget)
        add_tool_button = QPushButton("Add tool")
        add_tool_button.clicked.connect(lambda: self.add_new_tool(provided_dict=None))
        tools_layout.addWidget(add_tool_button)
        self.tool_list_widget = QListWidget()
        self.tool_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tools_layout.addWidget(self.tool_list_widget)

        # Tool pools
        toolpools_layout = QVBoxLayout()
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        toolpools_label = QLabel("Tool pools")
        toolpools_label.setFixedWidth(200)
        icon_path = "images/Tool_pools_icon.png"
        icon_label = QtWidgets.QLabel()
        pixmap = QtGui.QPixmap(icon_path).scaled(32, 32, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        icon_label.setPixmap(pixmap)
        container_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignLeft)  # Align logo to the left
        container_layout.addWidget(toolpools_label, alignment=QtCore.Qt.AlignLeft)  # Align label to the left
        container_layout.setAlignment(QtCore.Qt.AlignLeft)
        toolpools_layout.addWidget(container_widget)
        add_toolpool_button = QPushButton("Add tool pool")
        add_toolpool_button.clicked.connect(lambda: self.add_new_toolpool(pool_id=None, provided_list=None))
        toolpools_layout.addWidget(add_toolpool_button)
        self.toolpools_list_widget = QListWidget()
        self.toolpools_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        toolpools_layout.addWidget(self.toolpools_list_widget)

        self.resources_grid_layout.addLayout(worker_capabilities_layout, 0, 0)
        self.resources_grid_layout.addLayout(workers_layout, 0, 1)
        self.resources_grid_layout.addLayout(worker_pools_layout, 0, 2)
        self.resources_grid_layout.addLayout(tools_layout, 0, 3)
        self.resources_grid_layout.addLayout(toolpools_layout, 1, 0)
        self.resources_grid_layout.addLayout(machine_capabilities_layout, 1, 1)
        self.resources_grid_layout.addLayout(machines_layout, 1, 2)
        self.resources_grid_layout.addLayout(workstation_layout, 1, 3)
        self.setLayout(self.resources_grid_layout)

        # Object to store data of Workers, Machines, Workstations, Worker pools, Tool pools etc. (also for display purposes)
        self.production_system = ProductionSystem()

    def add_new_worker_capability(self, provided_str=None):
        cap_name = ''
        if provided_str is None:
            i = self.worker_cap_list_widget.count() + 1
            cap_name = "Worker capability " + str(i)
        else:
            cap_name = provided_str
        item = QListWidgetItem(cap_name)  
        self.worker_cap_list_widget.addItem(item)

        self.worker_cap_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.worker_cap_list_widget.customContextMenuRequested.connect(self.show_capability_menu)

    def show_capability_menu(self, position):
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec_(self.worker_cap_list_widget.viewport().mapToGlobal(position))
        
        if action == rename_action:
            item = self.worker_cap_list_widget.itemAt(position)
            new_name, ok = QInputDialog.getText(self, "Rename worker capability", "Enter new capability name:")
            if ok and new_name:
                item.setText(new_name)
        elif action == delete_action:
            item = self.worker_cap_list_widget.itemAt(position)
            row = self.worker_cap_list_widget.row(item)
            self.worker_cap_list_widget.takeItem(row)

    def add_new_worker(self, provided_dict=None):
        if provided_dict is None:
            i = self.workers_list_widget.count() + 1
            wrkr_name = "Worker " + str(i)
            item = QListWidgetItem(wrkr_name)  
            self.workers_list_widget.addItem(item)
            # ToDo: check this, although it shouldn't cause any key conflicts because of unique numbering
            self.production_system.workers.update({wrkr_name: Worker(worker_id=wrkr_name)})
        else:
            wrkr_name = provided_dict['worker_id']
            item = QListWidgetItem(wrkr_name)  
            self.workers_list_widget.addItem(item)
            wrkr_capas = provided_dict['provided_capabilities']
            self.production_system.workers.update({wrkr_name: Worker(worker_id=wrkr_name, provided_capabilities=wrkr_capas)})
        self.workers_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.workers_list_widget.customContextMenuRequested.connect(self.show_worker_menu)
        

    def show_worker_menu(self,position):
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        edit_action = menu.addAction("Edit...")
        delete_action = menu.addAction("Delete")
       
        action = menu.exec_(self.workers_list_widget.viewport().mapToGlobal(position))

        item = self.workers_list_widget.itemAt(position)

        if action == rename_action:
            old_name = item.text()
            new_name, ok = QInputDialog.getText(self, "Rename worker", "Enter new worker ID:")
            if ok and new_name:
                try:
                    self.production_system.workers.update({new_name: self.production_system.workers.pop(old_name)})
                    self.production_system.workers[new_name].worker_id = new_name
                except KeyError:
                    print("Worker not in production system data yet, just renaming.")
                    self.production_system.workers.update({new_name: Worker(worker_id=new_name)})
                item.setText(new_name)
        elif action == delete_action:
            self.production_system.workers.pop(item.text())
            row = self.workers_list_widget.row(item)
            self.workers_list_widget.takeItem(row)
        elif action == edit_action:
            edit_dialog = QDialog()
            edit_dialog.setWindowTitle(f"Properties of worker {item.text()}")

            # Main layout for the dialog
            worker_edit_layout = QVBoxLayout()
            prov_cap_label = QLabel("Provided capabilities:")
            prov_cap_label.setFixedWidth(400)
            worker_edit_layout.addWidget(prov_cap_label)

            # Button to add a capability of this worker
            def add_worker_cap_row():
                capability_selection = QComboBox()
                lw = self.resources_grid_layout.itemAtPosition(0,0).layout().itemAt(2).widget()
                items = [lw.item(x).text() for x in range(lw.count())]
                wrkr_caps = list(items)
                capability_selection.addItems(wrkr_caps)
                edit_dialog.layout().itemAt(2).layout().addWidget(capability_selection)
            
            add_cap_button = QPushButton("Add capability")
            add_cap_button.clicked.connect(add_worker_cap_row)
            worker_edit_layout.addWidget(add_cap_button)

            # Placeholder for capability drop-downs
            wrkr_cap_lt = QVBoxLayout()  # only for holding the QComboBoxes with selected capabilities
            worker_edit_layout.addLayout(wrkr_cap_lt)

            # To load previously saved worker capabilities
            def load_worker_data():
                if self.production_system.workers:
                    try:
                        worker = self.production_system.workers[item.text()]
                        if worker.provided_capabilities:
                            for c in worker.provided_capabilities:
                                capability_name_field = QComboBox()
                                lw = self.resources_grid_layout.itemAtPosition(0,0).layout().itemAt(2).widget()
                                capas = [lw.item(x).text() for x in range(lw.count())]
                                capability_name_field.addItems(capas)
                                i = capability_name_field.findText(c)
                                capability_name_field.setCurrentIndex(i)
                                edit_dialog.layout().itemAt(2).layout().addWidget(capability_name_field)
                    except KeyError:
                        print(f"No information about worker {item.text()} is stored yet.")
                else:
                    # there are no workers saved yet
                    return

            def save_worker_capability_list():
                capa_list = []
                for i in range(wrkr_cap_lt.count()):
                    c = wrkr_cap_lt.itemAt(i).widget().currentText()
                    capa_list.append(c)
                self.production_system.workers.update({item.text(): Worker(worker_id=item.text(), provided_capabilities=capa_list)})

            def accept():
                save_worker_capability_list()

            # Dialog buttons
            QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
            buttonBox = QDialogButtonBox(QBtn)
            buttonBox.accepted.connect(accept)
            buttonBox.accepted.connect(edit_dialog.accept)
            buttonBox.rejected.connect(edit_dialog.reject)
            worker_edit_layout.addWidget(buttonBox)

            edit_dialog.setLayout(worker_edit_layout)
            load_worker_data()
            edit_dialog.exec()
    
    def add_new_pool(self, pool_id=None, provided_list=None):
        if provided_list is None:
            i = self.worker_pool_list_widget.count() + 1
            wp_name = "Worker pool " + str(i)
            item = QListWidgetItem(wp_name)  
            self.worker_pool_list_widget.addItem(item)
            self.production_system.worker_pools.update({wp_name: []})
        else:
            item = QListWidgetItem(pool_id)  
            self.worker_pool_list_widget.addItem(item)
            self.production_system.worker_pools.update({pool_id: provided_list})
        self.worker_pool_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.worker_pool_list_widget.customContextMenuRequested.connect(self.show_pool_menu)   
        

    def show_pool_menu(self,position):   
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        edit_action = menu.addAction("Edit...")
        delete_action = menu.addAction("Delete") 
        action = menu.exec_(self.worker_pool_list_widget.viewport().mapToGlobal(position))
        item = self.worker_pool_list_widget.itemAt(position)

        if action == rename_action:
            item = self.worker_pool_list_widget.itemAt(position)
            old_name = item.text()
            new_name, ok = QInputDialog.getText(self, "Rename worker pool", "Enter new worker pool ID:")
            if ok and new_name:
                try:
                    self.production_system.worker_pools.update({new_name: self.production_system.worker_pools.pop(old_name)})
                except KeyError:
                    print("Worker pool not in production system data yet, just renaming.")
                item.setText(new_name)
        elif action == delete_action:
            item = self.worker_pool_list_widget.itemAt(position)
            self.production_system.worker_pools.pop(item.text())
            row = self.worker_pool_list_widget.row(item)
            self.worker_pool_list_widget.takeItem(row)
        elif action == edit_action:
            edit_dialog = QDialog()
            edit_dialog.setWindowTitle(f"Properties of worker pool {item.text()}")
            # Main layout for the dialog
            worker_pool_edit_layout = QVBoxLayout()
            assigned_workers_label = QLabel("Assigned workers:")
            assigned_workers_label.setFixedWidth(400)
            worker_pool_edit_layout.addWidget(assigned_workers_label)
            # Button to add a worker to this pool
            def add_worker_row():
                worker_selection = QComboBox()
                lw = self.resources_grid_layout.itemAtPosition(0,1).layout().itemAt(2).widget()
                items = [lw.item(x).text() for x in range(lw.count())]
                wrkrs = list(items)
                worker_selection.addItems(wrkrs)
                edit_dialog.layout().itemAt(2).layout().addWidget(worker_selection)
            add_wrkr_button = QPushButton("Add worker")
            add_wrkr_button.clicked.connect(add_worker_row)
            worker_pool_edit_layout.addWidget(add_wrkr_button)
            # Placeholder for worker drop-downs
            wrkr_lt = QVBoxLayout()
            worker_pool_edit_layout.addLayout(wrkr_lt)

            # To load previously saved workers
            def load_workers():
                if not self.production_system.worker_pools:
                    return
                try:
                    worker_list = self.production_system.worker_pools[item.text()]
                    if worker_list:
                        for w in worker_list:
                            worker_field = QComboBox()
                            lw = self.resources_grid_layout.itemAtPosition(0,1).layout().itemAt(2).widget()
                            wrkrs = [lw.item(x).text() for x in range(lw.count())]
                            worker_field.addItems(wrkrs)
                            i = worker_field.findText(w)
                            worker_field.setCurrentIndex(i)
                            edit_dialog.layout().itemAt(2).layout().addWidget(worker_field)
                except KeyError:
                    print(f"No information about Worker Pool {item.text()} has been stored yet.")

            def save_worker_list():
                wrkr_list = []
                for i in range(wrkr_lt.count()):
                    w = wrkr_lt.itemAt(i).widget().currentText()
                    wrkr_list.append(w)
                self.production_system.worker_pools.update({item.text(): wrkr_list})

            def accept():
                save_worker_list()

            # Dialog buttons
            QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
            buttonBox = QDialogButtonBox(QBtn)
            buttonBox.accepted.connect(accept)
            buttonBox.accepted.connect(edit_dialog.accept)
            buttonBox.rejected.connect(edit_dialog.reject)
            worker_pool_edit_layout.addWidget(buttonBox)
            edit_dialog.setLayout(worker_pool_edit_layout)
            load_workers()
            edit_dialog.exec()

    def add_new_tool(self, provided_dict=None):
        if provided_dict is None:
            i = self.tool_list_widget.count()
            tool_name = "Tool " + str(i)
            item = QListWidgetItem(tool_name)  
            self.tool_list_widget.addItem(item)
            self.production_system.tools.update({tool_name: Tool(tool_id=tool_name)})
        else:
            tool_name = provided_dict['tool_id']
            dyn_prop = provided_dict['dynamic_properties']
            stat_prop = provided_dict['static_properties']
            item = QListWidgetItem(tool_name)  
            self.tool_list_widget.addItem(item)
            self.production_system.tools.update({tool_name: Tool(tool_id=tool_name, dynamic_properties=dyn_prop, static_properties=stat_prop)})
        self.tool_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tool_list_widget.customContextMenuRequested.connect(self.show_tool_menu)
        
    def add_static_tool_property(self, stp_table):
        row_position = stp_table.rowCount()
        stp_table.insertRow(row_position)
        stp_table.setItem(row_position, 0, QTableWidgetItem("Property"))
        stp_table.setItem(row_position, 1, QTableWidgetItem("0.0"))  # value
        stp_table.setItem(row_position, 2, QTableWidgetItem("Unit"))

    def add_dynamic_tool_property(self, dtp_table):
        row_position = dtp_table.rowCount()
        dtp_table.insertRow(row_position)
        dtp_table.setItem(row_position, 0, QTableWidgetItem("Property"))
        dtp_table.setItem(row_position, 1, QTableWidgetItem("0.0"))  # min
        dtp_table.setItem(row_position, 2, QTableWidgetItem("0.0"))  # max
        dtp_table.setItem(row_position, 3, QTableWidgetItem("Unit"))
        dtp_table.setItem(row_position, 4, QTableWidgetItem("0.0"))  # time per unit +
        dtp_table.setItem(row_position, 5, QTableWidgetItem("0.0"))  # energy per unit +
        dtp_table.setItem(row_position, 6, QTableWidgetItem(""))  # cost per unit +
        dtp_table.setItem(row_position, 7, QTableWidgetItem("0.0"))  # time per unit -
        dtp_table.setItem(row_position, 8, QTableWidgetItem("0.0"))  # energy per unit -
        dtp_table.setItem(row_position, 9, QTableWidgetItem(""))  # cost per unit -
        # Costs per unit change will be calculated from required energy and energy prices but can be input manually

    def show_tool_menu(self, position):
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        edit_action = menu.addAction("Edit...")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec_(self.tool_list_widget.viewport().mapToGlobal(position))
        item = self.tool_list_widget.itemAt(position)
        
        if action == rename_action:
            old_name = item.text()
            item = self.tool_list_widget.itemAt(position)
            new_name, ok = QInputDialog.getText(self, "Rename tool", "Enter new tool ID:")
            if ok and new_name:
                try:
                    self.production_system.tools.update({new_name: self.production_system.tools.pop(old_name)})
                    self.production_system.tools[new_name].tool_id = new_name
                except KeyError:
                    print("Tool not in production system data yet, just renaming.")
                    self.production_system.tools.update({new_name: Tool(tool_id=new_name)})
                item.setText(new_name)
        elif action == delete_action:
            item = self.tool_list_widget.itemAt(position)
            self.production_system.tools.pop(item.text())
            row = self.tool_list_widget.row(item)
            self.tool_list_widget.takeItem(row)
        elif action == edit_action:
            edit_dialog = QDialog()
            edit_dialog.setWindowTitle(f"Properties of tool {item.text()}")
            edit_dialog.setMinimumWidth(1000)
            tool_edit_layout = QVBoxLayout()

            # Button to add a static tool property
            add_stat_tool_prop_btn = QPushButton("Add static property")
            tool_edit_layout.addWidget(add_stat_tool_prop_btn)
            # Table for static tool properties
            stp_table = QTableWidget()
            stp_table.setColumnCount(3)
            stp_table.setHorizontalHeaderLabels(["Property", "Value", "Unit"])
            stp_table.setColumnWidth(0, 150)
            stp_table.setColumnWidth(1, 80)
            stp_table.setColumnWidth(2, 80)
            stp_table.setMinimumHeight(100)
            tool_edit_layout.addWidget(stp_table)
            add_stat_tool_prop_btn.clicked.connect(lambda:self.add_static_tool_property(stp_table))
            # Button to add a dynamic tool property
            add_dyn_tool_prop_btn = QPushButton("Add dynamic property")
            tool_edit_layout.addWidget(add_dyn_tool_prop_btn)
            tool_edit_layout.addWidget(QLabel("Costs per unit change will be calculated from required energy and energy prices but can be input manually."))
            # Table for dynamic tool properties
            dtp_table = QTableWidget()
            dtp_table.setColumnCount(10)
            dtp_table.setHorizontalHeaderLabels(["Property", "Min", "Max", "Unit", "Time(+)\n[s/unit]", "Energy(+)\n[Wh/unit]", "Cost(+)\n[€/unit]", "Time(-)\n[s/unit]", "Energy(-)\n[Wh/unit]", "Cost(-)\n[€/unit]"])
            dtp_table.setColumnWidth(0, 150)
            dtp_table.setColumnWidth(1, 80)
            dtp_table.setColumnWidth(2, 80)
            dtp_table.setColumnWidth(3, 80)
            dtp_table.setColumnWidth(4, 80)
            dtp_table.setColumnWidth(5, 80)
            dtp_table.setColumnWidth(6, 80)
            dtp_table.setColumnWidth(7, 80)
            dtp_table.setColumnWidth(8, 80)
            dtp_table.setColumnWidth(9, 80)
            dtp_table.setMinimumHeight(100)
            tool_edit_layout.addWidget(dtp_table)
            add_dyn_tool_prop_btn.clicked.connect(lambda:self.add_dynamic_tool_property(dtp_table))
            # Save and Cancel buttons

            # To load previously saved tool properties
            def load_tool_properties():
                if self.production_system.tools:
                    tool = self.production_system.tools[item.text()]  # gets a Tool object by its ID
                    if tool:
                        print("Loaded from memory:")
                        print(tool.static_properties)
                        print(tool.dynamic_properties)
                        for k,v in tool.static_properties.items():
                            row_position = stp_table.rowCount()
                            stp_table.insertRow(row_position)
                            stp_table.setItem(row_position, 0, QTableWidgetItem(k))
                            stp_table.setItem(row_position, 1, QTableWidgetItem(str(v['Value'])))
                            stp_table.setItem(row_position, 2, QTableWidgetItem(str(v['Unit'])))
                        for k,v in tool.dynamic_properties.items():
                            row_position = dtp_table.rowCount()
                            dtp_table.insertRow(row_position)
                            dtp_table.setItem(row_position, 0, QTableWidgetItem(k))
                            dtp_table.setItem(row_position, 1, QTableWidgetItem(str(v['Min'])))
                            dtp_table.setItem(row_position, 2, QTableWidgetItem(str(v['Max'])))
                            dtp_table.setItem(row_position, 3, QTableWidgetItem(str(v['Unit'])))
                            dtp_table.setItem(row_position, 4, QTableWidgetItem(str(v['Time/unit+'])))
                            dtp_table.setItem(row_position, 5, QTableWidgetItem(str(v['Energy/unit+'])))
                            dtp_table.setItem(row_position, 6, QTableWidgetItem('' if v['Cost/unit+'] is None else str(v['Cost/unit+'])))
                            dtp_table.setItem(row_position, 7, QTableWidgetItem(str(v['Time/unit-'])))
                            dtp_table.setItem(row_position, 8, QTableWidgetItem(str(v['Energy/unit-'])))
                            dtp_table.setItem(row_position, 9, QTableWidgetItem('' if v['Cost/unit-'] is None else str(v['Cost/unit-'])))
                else:
                    # there are no tools saved yet
                    return

            def save_tool_properties():
                stp = dict()
                dtp = dict()
                for row in range(stp_table.rowCount()):
                    stp.update({stp_table.item(row,0).text(): {'Value': float(stp_table.item(row,1).text()),
                                                               'Unit': stp_table.item(row,2).text()}})
                for row in range(dtp_table.rowCount()):
                    dtp.update({dtp_table.item(row,0).text(): {'Min': float(dtp_table.item(row,1).text()),
                                                               'Max': float(dtp_table.item(row,2).text()),
                                                               'Unit': dtp_table.item(row,3).text(),
                                                               'Time/unit+': float(dtp_table.item(row,4).text()),
                                                               'Energy/unit+': float(dtp_table.item(row,5).text()),
                                                               'Cost/unit+': None if dtp_table.item(row,6).text()=='' else float(dtp_table.item(row,6).text()),
                                                               'Time/unit-': float(dtp_table.item(row,7).text()),
                                                               'Energy/unit-': float(dtp_table.item(row,8).text()),
                                                               'Cost/unit-': None if dtp_table.item(row,9).text()=='' else float(dtp_table.item(row,9).text())}})
                self.production_system.tools.update({item.text(): Tool(tool_id=item.text(), static_properties=stp, dynamic_properties=dtp)})

            def accept():
                save_tool_properties()

            # Dialog buttons
            QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
            buttonBox = QDialogButtonBox(QBtn)
            buttonBox.accepted.connect(accept)
            buttonBox.accepted.connect(edit_dialog.accept)
            buttonBox.rejected.connect(edit_dialog.reject)
            tool_edit_layout.addWidget(buttonBox)

            edit_dialog.setLayout(tool_edit_layout)
            load_tool_properties()
            edit_dialog.exec_()

    def add_new_machine_capability(self, provided_str=None):
        cap_name = ''
        if provided_str is None:
            i = self.machine_cap_list_widget.count() + 1
            cap_name = "Machine capability " + str(i)
        else:
            cap_name = provided_str
        item = QListWidgetItem(cap_name)  
        self.machine_cap_list_widget.addItem(item)
        self.machine_cap_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.machine_cap_list_widget.customContextMenuRequested.connect(self.show_machine_capability_menu)

    def show_machine_capability_menu(self, position):
        # Right-click context menu for renaming or deleting a product
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        
        action = menu.exec_(self.machine_cap_list_widget.viewport().mapToGlobal(position))
        
        if action == rename_action:
            item = self.machine_cap_list_widget.itemAt(position)
            new_name, ok = QInputDialog.getText(self, "Rename capability", "Enter new capability name:")
            if ok and new_name:
                item.setText(new_name)
        elif action == delete_action:
            item = self.machine_cap_list_widget.itemAt(position)
            row = self.machine_cap_list_widget.row(item)
            self.machine_cap_list_widget.takeItem(row)
    
    def add_new_machine(self, provided_dict=None):
        if provided_dict is None:
            i = self.machines_list_widget.count() + 1
            machn_name = "Machine " + str(i)
            item = QListWidgetItem(machn_name)  
            self.machines_list_widget.addItem(item)
            self.production_system.machines.update({machn_name: Machine(machine_id=machn_name)})
        else:
            item = QListWidgetItem(provided_dict['machine_id'])
            self.machines_list_widget.addItem(item)
            self.production_system.machines.update({provided_dict['machine_id']: Machine(machine_id=provided_dict['machine_id'],
                                                                        accepted_capabilities=provided_dict['accepted_capabilities'],
                                                                        provided_capabilities=provided_dict['provided_capabilities'],
                                                                        compatible_tools=provided_dict['compatible_tools'],
                                                                        software_setup_time_value=provided_dict['software_setup_time_value'],
                                                                        software_setup_time_unit=provided_dict['software_setup_time_unit'],
                                                                        software_setup_parallel_to_operation=provided_dict['software_setup_parallel_to_operation'],
                                                                        batch_processing=provided_dict['batch_processing'],
                                                                        batch_size=provided_dict['batch_size'],
                                                                        speed_factor=provided_dict['speed_factor'],
                                                                        mtbf_value=provided_dict['mtbf_value'],
                                                                        mtbf_unit=provided_dict['mtbf_unit'],
                                                                        mttr_value=provided_dict['mttr_value'],
                                                                        mttr_unit=provided_dict['mttr_unit'],
                                                                        is_transport=provided_dict['is_transport'],
                                                                        diff_comp_batch=provided_dict['diff_comp_batch'],
                                                                        power_consumption=provided_dict['power_consumption'],
                                                                        hardware_setup_parallel_to_operation=provided_dict['hardware_setup_parallel_to_operation'],
                                                                        hardware_setup_time_unit=provided_dict['hardware_setup_time_unit'],
                                                                        setup_matrix=provided_dict['setup_matrix'],
                                                                        tool_slots=provided_dict['tool_slots'])})
        self.machines_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.machines_list_widget.customContextMenuRequested.connect(self.show_machine_menu)
        

    def show_machine_menu(self,position):
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        edit_action = menu.addAction("Edit...")
        delete_action = menu.addAction("Delete")   
       
        action = menu.exec_(self.machines_list_widget.viewport().mapToGlobal(position))

        item = self.machines_list_widget.itemAt(position)  

        if action == rename_action:
            old_name = item.text()
            new_name, ok = QInputDialog.getText(self, "Rename machine", "Enter new machine ID:")
            if ok and new_name:
                try:
                    self.production_system.machines.update({new_name: self.production_system.machines.pop(old_name)})
                    self.production_system.machines[new_name].machine_id = new_name
                except KeyError:
                    print("Machine not in production system data yet, just renaming.")
                    self.production_system.machines.update({new_name: Machine(machine_id=new_name)})  # ToDo: test this!
                item.setText(new_name)
        elif action == delete_action:
            row = self.machines_list_widget.row(item)
            self.machines_list_widget.takeItem(row)
            self.production_system.machines.pop(item.text())
        elif action == edit_action:
            edit_dialog = QDialog()
            edit_dialog.setWindowTitle(f"Properties of machine {item.text()}")

            # Main layout for the dialog
            machine_edit_layout = QGridLayout()

            # Box for accepted capabilities
            acc_cap_lt = QVBoxLayout()
            acc_cap_label = QLabel("Accepted capabilities:")
            acc_cap_label.setFixedWidth(200)
            lw = self.resources_grid_layout.itemAtPosition(0,0).layout().itemAt(2).widget()  # worker capabilities list widget
            wrkr_caps = [lw.item(x).text() for x in range(lw.count())]
            acc_cap_combo = CheckableComboBox()
            acc_cap_combo.addItems(wrkr_caps)
            acc_cap_lt.addWidget(acc_cap_label)
            acc_cap_lt.addWidget(acc_cap_combo)

            # Box for provided capabilities
            prov_cap_lt = QVBoxLayout()
            prov_cap_label = QLabel("Provided capabilities:")
            prov_cap_label.setFixedWidth(200)
            lw = self.resources_grid_layout.itemAtPosition(1,1).layout().itemAt(2).widget()  # machine capabilities list widget
            m_caps = [lw.item(x).text() for x in range(lw.count())]
            prov_cap_combo = CheckableComboBox()
            prov_cap_combo.addItems(m_caps)
            prov_cap_lt.addWidget(prov_cap_label)
            prov_cap_lt.addWidget(prov_cap_combo)

            # Box for compatible tools
            compat_tools_lt = QVBoxLayout()
            compat_tools_label = QLabel("Compatible tools:")
            compat_tools_label.setFixedWidth(200)
            lw = self.resources_grid_layout.itemAtPosition(0,3).layout().itemAt(2).widget()  # tool list widget
            ctls = [lw.item(x).text() for x in range(lw.count())]
            compat_tools_combo = CheckableComboBox()
            compat_tools_combo.addItems(ctls)
            compat_tools_lt.addWidget(compat_tools_label)
            compat_tools_lt.addWidget(compat_tools_combo)

            # Box for software setup information
            soft_setup_lt = QVBoxLayout()
            soft_setup_label = QLabel("Software setup")
            soft_setup_label.setFixedWidth(200)
            sst_lt = QHBoxLayout()
            sst_value_field = QLineEdit("0.0")
            sst_unit_field = QComboBox()
            sst_unit_field.addItems(['s', 'min', 'h', 'd'])
            sst_unit_field.setFixedWidth(50)
            sst_lt.addWidget(sst_value_field)
            sst_lt.addWidget(sst_unit_field)
            sst_lt.setAlignment(Qt.AlignTop)
            pto_cb = QCheckBox("Parallel to operation")
            soft_setup_lt.addWidget(soft_setup_label)
            soft_setup_lt.addLayout(sst_lt)
            soft_setup_lt.addWidget(pto_cb)
            soft_setup_fr = QFrame()
            soft_setup_fr.setLayout(soft_setup_lt)
            soft_setup_fr.setFrameStyle(QFrame.Box | QFrame.Plain)

            # Box for hardware setup information
            hw_setup_lt = QVBoxLayout()
            hw_setup_label = QLabel("Hardware setup")
            hw_setup_label.setFixedWidth(200)

            # New version with a dialog to specify a setup matrix
            hw_setup_btn = QPushButton("Setup matrix")
            hw_setup_op_parallel = QCheckBox("Parallel to operation")

            self.temp_hst_time_unit = ''
            self.temp_hw_setup_matrix = {}  # to retain setup matrix while editing the machine
            self.temp_tool_slots = {}  # to retain tool slot mapping while editing the machine

            def specify_setup_matrix():
                setup_matrix_dialog = QDialog()
                setup_matrix_dialog.setWindowTitle(f"Specify hardware setup matrix for machine {item.text()}")
                setup_matrix_dialog.setMinimumWidth(300)
                # Main layout of hardware setup dialog: tables and save/cancel
                setup_matrix_dialog_layout = QVBoxLayout()
                # Horizontal layout for the setup matrix and the tool slot assignment table
                sm_horiz_lt = QHBoxLayout()
                # Vertical layout of the left column: time unit selection and the setup table
                sm_col1_vert_lt = QVBoxLayout()
                # Vertical layout of the right column: tool slot assignment
                sm_col2_vert_lt = QVBoxLayout()
                time_unit_hlt = QHBoxLayout()
                time_unit_hlt.addWidget(QLabel("Time unit:"))
                time_unit_cb = QComboBox()
                time_unit_cb.addItems(['s', 'min', 'h', 'd'])
                time_unit_cb.setFixedWidth(50)
                # ToDo: set selected if unit already known
                if self.temp_hst_time_unit != '':
                    time_unit_cb.setCurrentIndex(time_unit_cb.findText(self.temp_hst_time_unit))
                elif self.production_system.machines:
                    machine = self.production_system.machines[item.text()]
                    if machine:
                        time_unit_cb.setCurrentIndex(time_unit_cb.findText(machine.hardware_setup_time_unit))
                time_unit_hlt.addWidget(time_unit_cb)
                time_unit_hlt.setAlignment(Qt.AlignTop)
                # Rows (both setup matrix and tool slot assignment) = machine's selected compatible tools
                sel_compat_tools = [compat_tools_combo.itemText(x) for x in range(compat_tools_combo.count()) if compat_tools_combo.model().data(compat_tools_combo.model().index(x,0), Qt.CheckStateRole)==Qt.Checked]
                index_list = sel_compat_tools + ['No tool']
                # Retrieve hardware setup matrix if available
                setup_matrix_table = None
                if self.temp_hw_setup_matrix:
                    print("Temp hardware setup matrix:")
                    print(self.temp_hw_setup_matrix)
                    # Filter setup matrix by selected compatible tools
                    filtered_setup_matrix = {row: {col: "" for col in index_list} for row in index_list}
                    for row in index_list:
                        for col in index_list:
                            if row in self.temp_hw_setup_matrix.keys():
                                if col in self.temp_hw_setup_matrix[row].keys():
                                    filtered_setup_matrix[row][col] = self.temp_hw_setup_matrix[row][col]
                            else:
                                # new row name has been added, which should also mean that a column with the same name has been added...
                                filtered_setup_matrix[row][col] = ''
                    print("Filtered by compatible tool selection:")
                    print(filtered_setup_matrix)
                    setup_matrix_table = SetupMatrixTable(setup_table=filtered_setup_matrix)
                elif self.production_system.machines:
                    machine = self.production_system.machines[item.text()]
                    if machine:
                        print("Hardware setup matrix loaded from memory:")
                        print(machine.setup_matrix)
                        if machine.setup_matrix != {}:
                            # Filter setup matrix by selected compatible tools
                            filtered_setup_matrix = {row: {col: "" for col in index_list} for row in index_list}
                            for row in index_list:
                                for col in index_list:
                                    if row in machine.setup_matrix.keys():
                                        if col in machine.setup_matrix[row].keys():
                                            filtered_setup_matrix[row][col] = machine.setup_matrix[row][col]
                                    else:
                                        # new row name has been added, which should also mean that a column with the same name has been added...
                                        filtered_setup_matrix[row][col] = ''
                            print("Filtered by compatible tool selection:")
                            print(filtered_setup_matrix)
                            setup_matrix_table = SetupMatrixTable(setup_table=filtered_setup_matrix)
                        else:
                            # No data in production system object yet, and no data in temporary variable regarding hardware setup
                            # We still need to create a table with rows and columns = compatible tools + no tool
                            setup_matrix = {row: {col: "" for col in index_list} for row in index_list}
                            setup_matrix_table = SetupMatrixTable(setup_table=setup_matrix)

                tool_slot_label = QLabel("Tool slots")
                tool_slot_table = QTableWidget()
                tool_slot_table.setColumnCount(2)
                tool_slot_table.setHorizontalHeaderLabels(['Tool', 'Slot'])
                tool_slot_table.setColumnWidth(0, 150)
                tool_slot_table.setColumnWidth(1, 100)
                # Retrieve tool slot mapping if available
                if self.temp_tool_slots:
                    print("Temp tool slots:")
                    print(self.temp_tool_slots)
                    # Add rows only for currently selected compatible tools and get their tool mapping if available
                    for tool in sel_compat_tools:
                        row_position = tool_slot_table.rowCount()
                        tool_slot_table.insertRow(row_position)
                        tool_slot_table.setItem(row_position, 0, QTableWidgetItem(tool))
                        if tool in self.temp_tool_slots.keys():
                            tool_slot_table.setItem(row_position, 1, QTableWidgetItem(self.temp_tool_slots[tool]))
                        else:
                            tool_slot_table.setItem(row_position, 1, QTableWidgetItem(""))
                elif self.production_system.machines:
                    machine = self.production_system.machines[item.text()]
                    if machine:
                        print("Tool slots loaded from memory:")
                        print(machine.tool_slots)
                        if machine.tool_slots != {}:
                            for tool, slot in machine.tool_slots:
                                row_position = tool_slot_table.rowCount()
                                tool_slot_table.insertRow(row_position)
                                tool_slot_table.setItem(row_position, 0, QTableWidgetItem(tool))
                                tool_slot_table.setItem(row_position, 1, QTableWidgetItem(slot))
                        else:
                            # No data regarding tool slot assignment
                            for tool in sel_compat_tools:
                                row_position = tool_slot_table.rowCount()
                                tool_slot_table.insertRow(row_position)
                                tool_slot_table.setItem(row_position, 0, QTableWidgetItem(tool))
                                tool_slot_table.setItem(row_position, 1, QTableWidgetItem(""))
                
                # Save setup matrix and tool slot assignment (also in temp variables?)
                def accept_sm():
                    hw_setup_matrix = {}
                    # Save time unit
                    self.temp_hst_time_unit = time_unit_cb.currentText()
                    # Save hardware setup matrix
                    sm_input_table = setup_matrix_table.layout().itemAt(1).layout().itemAt(1).widget()
                    # For each row and column combination
                    for row in range(sm_input_table.rowCount()):
                        row_header = sm_input_table.verticalHeaderItem(row).text()
                        hw_setup_row_dict = {}
                        for col in range(sm_input_table.columnCount()):       
                            # Get the names of the headers corresponding to the table item
                            col_header = sm_input_table.horizontalHeaderItem(col).text()
                            # Get the value of the table item
                            st_value = sm_input_table.item(row,col).text()
                            # Update target dictionary with the entry
                            if st_value != '' and st_value is not None:
                                hw_setup_row_dict.update({col_header: float(st_value)})
                        hw_setup_matrix.update({row_header: hw_setup_row_dict})
                    self.temp_hw_setup_matrix = hw_setup_matrix
                    # Save tool slot assignment
                    filtered_tool_slots = {}
                    for row in range(tool_slot_table.rowCount()):
                        dict_item = {tool_slot_table.item(row,0).text(): tool_slot_table.item(row,1).text()}
                        filtered_tool_slots.update(dict_item)
                        self.temp_tool_slots = filtered_tool_slots

                # Column 1 of setup matrix dialog
                sm_col1_vert_lt.addLayout(time_unit_hlt)
                sm_col1_vert_lt.addWidget(setup_matrix_table)

                # Column 2 of setup matrix dialog
                sm_col2_vert_lt.addWidget(tool_slot_label)
                sm_col2_vert_lt.addWidget(tool_slot_table)

                sm_horiz_lt.addLayout(sm_col1_vert_lt)
                sm_horiz_lt.addLayout(sm_col2_vert_lt)
                setup_matrix_dialog_layout.addLayout(sm_horiz_lt)

                save_sm_btn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
                buttonBox = QDialogButtonBox(save_sm_btn)
                buttonBox.accepted.connect(setup_matrix_dialog.accept)
                buttonBox.accepted.connect(accept_sm)
                buttonBox.rejected.connect(setup_matrix_dialog.reject)
                setup_matrix_dialog_layout.addWidget(buttonBox)
                setup_matrix_dialog.setLayout(setup_matrix_dialog_layout)
                setup_matrix_dialog.exec()
                

            # Old version with a fixed time value for any setup
            '''
            hst_lt = QHBoxLayout()
            hst_value_field = QLineEdit("0.0")
            hst_unit_field = QComboBox()
            hst_unit_field.addItems(['s', 'min', 'h', 'd'])
            hst_unit_field.setFixedWidth(50)
            hst_lt.addWidget(hst_value_field)
            hst_lt.addWidget(hst_unit_field)
            hst_lt.setAlignment(Qt.AlignTop)
            '''

            hw_setup_lt.addWidget(hw_setup_label)
            #hw_setup_lt.addLayout(hst_lt)
            hw_setup_btn.clicked.connect(specify_setup_matrix)
            hw_setup_lt.addWidget(hw_setup_btn)
            hw_setup_lt.addWidget(hw_setup_op_parallel)
            hw_setup_fr = QFrame()
            hw_setup_fr.setLayout(hw_setup_lt)
            hw_setup_fr.setFrameStyle(QFrame.Box | QFrame.Plain)

            # Box for processing properties
            pp_lt = QVBoxLayout()
            bp_cb = QCheckBox("Batch processing")
            bs_btn = QPushButton("Batch sizes")
            power_lbl = QLabel("Power consumption (W)")
            power_field = QLineEdit("0.0")
            power_lt = QHBoxLayout()
            power_lt.addWidget(power_lbl)
            power_lt.addWidget(power_field)
            self.temp_bs_diff = None  # to retain batch specifications while editing the machine
            self.temp_bs_table = {}  # to retain batch specifications while editing the machine
            def specify_batch_size():
                if not bp_cb.isChecked():
                    # If this machine doesn't support batch processing, no need to let the user input batch specifications
                    return
                bs_dialog = QDialog()
                bs_dialog.setWindowTitle(f"Specify batch size for machine {item.text()}")
                bs_dialog.setMinimumWidth(700)
                bs_layout = QVBoxLayout()
                regex_hint_lbl = QLabel("Use * in the component name as placeholder for any symbols, e.g. M6x8_screw will match *_screw")
                bs_layout.addWidget(regex_hint_lbl)
                diff_comp_comb_cb = QCheckBox("Different components combinable in batch")
                # Retrieve flag from memory if available
                if self.temp_bs_diff is not None:
                    diff_comp_comb_cb.setChecked(self.temp_bs_diff)
                elif self.production_system.machines:
                    machine = self.production_system.machines[item.text()]
                    if machine and (machine.diff_comp_batch is not None):
                        diff_comp_comb_cb.setChecked(machine.diff_comp_batch)
                        self.temp_bs_diff = machine.diff_comp_batch
                
                bs_layout.addWidget(diff_comp_comb_cb)
                add_comp_btn = QPushButton("Add component batch size")
                bs_layout.addWidget(add_comp_btn)
                bs_table = QTableWidget()
                bs_table.setColumnCount(5)
                bs_table.setHorizontalHeaderLabels(
                    ["Component name", "Min. batch size", "Max. batch size", "Quantity step", "Group"]
                )
                bs_table.setColumnWidth(0, 200)
                bs_layout.addWidget(bs_table)
                def add_bs_row():
                    row_position = bs_table.rowCount()
                    bs_table.insertRow(row_position)
                    bs_table.setItem(row_position, 0, QTableWidgetItem("Component"))
                    bs_table.setItem(row_position, 1, QTableWidgetItem("0"))
                    bs_table.setItem(row_position, 2, QTableWidgetItem("0"))
                    bs_table.setItem(row_position, 3, QTableWidgetItem("0"))
                    bs_table.setItem(row_position, 4, QTableWidgetItem(""))  # default combination group
                add_comp_btn.clicked.connect(add_bs_row)
                # Retrieve batch size definitions if available
                if self.temp_bs_table:
                    print("Temp batch size table:")
                    print(self.temp_bs_table)
                    for k,v in self.temp_bs_table.items():
                        row_position = bs_table.rowCount()
                        bs_table.insertRow(row_position)
                        bs_table.setItem(row_position, 0, QTableWidgetItem(k))
                        bs_table.setItem(row_position, 1, QTableWidgetItem(str(v[0])))
                        bs_table.setItem(row_position, 2, QTableWidgetItem(str(v[1])))
                        bs_table.setItem(row_position, 3, QTableWidgetItem(str(v[2])))
                        bs_table.setItem(row_position, 4, QTableWidgetItem(str(v[3])))
                elif self.production_system.machines:
                    machine = self.production_system.machines[item.text()]
                    if machine:
                        print("Loaded from memory:")
                        print(machine.batch_size)
                        for k,v in machine.batch_size.items():
                            row_position = bs_table.rowCount()
                            bs_table.insertRow(row_position)
                            bs_table.setItem(row_position, 0, QTableWidgetItem(k))
                            bs_table.setItem(row_position, 1, QTableWidgetItem(str(v[0])))
                            bs_table.setItem(row_position, 2, QTableWidgetItem(str(v[1])))
                            bs_table.setItem(row_position, 3, QTableWidgetItem(str(v[2])))
                            bs_table.setItem(row_position, 4, QTableWidgetItem(str(v[3])))
                
                # Save or cancel
                def accept_bs():
                    self.temp_bs_diff = diff_comp_comb_cb.isChecked()
                    for row in range(bs_table.rowCount()):
                        dict_item = {bs_table.item(row,0).text(): (int(bs_table.item(row,1).text()),
                                                                   int(bs_table.item(row,2).text()),
                                                                   int(bs_table.item(row,3).text()),
                                                                   bs_table.item(row,4).text())}
                        self.temp_bs_table.update(dict_item)
                    
                save_bs_btn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
                buttonBox = QDialogButtonBox(save_bs_btn)
                buttonBox.accepted.connect(bs_dialog.accept)
                buttonBox.accepted.connect(accept_bs)
                buttonBox.rejected.connect(bs_dialog.reject)
                bs_layout.addWidget(buttonBox)
                bs_dialog.setLayout(bs_layout)
                bs_dialog.exec()
            bs_btn.clicked.connect(specify_batch_size)

            sf_hlt = QHBoxLayout()
            sf_label = QLabel("Speed factor")
            sf_field = QLineEdit("1.0")
            sf_field.setFixedWidth(50)
            sf_hlt.addWidget(sf_label)
            sf_hlt.addWidget(sf_field)
            pp_lt.addWidget(bp_cb)
            pp_lt.addWidget(bs_btn)
            pp_lt.addLayout(power_lt)
            pp_lt.addLayout(sf_hlt)

            # Box for MTBF
            mtbf_lt = QVBoxLayout()
            mtbf_label = QLabel("MTBF")
            mtbf_label.setFixedWidth(200)
            hmtbf_lt = QHBoxLayout()
            hmtbf_value_field = QLineEdit("inf")
            hmtbf_unit_field = QComboBox()
            hmtbf_unit_field.addItems(['s', 'min', 'h', 'd'])
            hmtbf_unit_field.setFixedWidth(50)
            hmtbf_lt.addWidget(hmtbf_value_field)
            hmtbf_lt.addWidget(hmtbf_unit_field)
            hmtbf_lt.setAlignment(Qt.AlignTop)
            mtbf_lt.addWidget(mtbf_label)
            mtbf_lt.addLayout(hmtbf_lt)

            # Box for MTTR
            mttr_lt = QVBoxLayout()
            mttr_label = QLabel("MTTR")
            mttr_label.setFixedWidth(200)
            hmttr_lt = QHBoxLayout()
            hmttr_value_field = QLineEdit("0.0")
            hmttr_unit_field = QComboBox()
            hmttr_unit_field.addItems(['s', 'min', 'h', 'd'])
            hmttr_unit_field.setFixedWidth(50)
            hmttr_lt.addWidget(hmttr_value_field)
            hmttr_lt.addWidget(hmttr_unit_field)
            hmttr_lt.setAlignment(Qt.AlignTop)
            mttr_lt.addWidget(mttr_label)
            mttr_lt.addLayout(hmttr_lt)

            # Put everything into machine edit layout
            machine_edit_layout.addLayout(acc_cap_lt, 0, 0)
            machine_edit_layout.addLayout(prov_cap_lt, 0, 1)
            machine_edit_layout.addLayout(compat_tools_lt, 0, 2)
            machine_edit_layout.addWidget(soft_setup_fr, 1, 0)
            machine_edit_layout.addWidget(hw_setup_fr, 1, 1)  
            machine_edit_layout.addLayout(pp_lt, 1, 2)
            machine_edit_layout.addLayout(mtbf_lt, 2, 0)
            machine_edit_layout.addLayout(mttr_lt, 2, 1)

            def transport_warning():
                QMessageBox.warning(self,
                                          "Transport machine hint",
                                          "Please input the speed factor of this transport machine\n as the actual speed in m/s!",
                                          QMessageBox.Yes)

            # Transport machine flag
            transport_machine_cb = QCheckBox("Transport machine")
            transport_machine_cb.clicked.connect(transport_warning)
            
            # To load previously saved machine info into machine edit dialog (for display purposes)
            def load_machine():
                if not self.production_system.machines:
                    return
                machine = self.production_system.machines[item.text()]
                if machine:
                    for c in machine.accepted_capabilities:
                        c_idx = acc_cap_combo.findText(c)
                        acc_cap_combo.setItemData(c_idx, Qt.Checked, Qt.CheckStateRole)
                    for c in machine.provided_capabilities:
                        c_idx = prov_cap_combo.findText(c)
                        prov_cap_combo.setItemData(c_idx, Qt.Checked, Qt.CheckStateRole)
                    for t in machine.compatible_tools:
                        t_idx = compat_tools_combo.findText(t)
                        compat_tools_combo.setItemData(t_idx, Qt.Checked, Qt.CheckStateRole)
                    sst_value_field.setText(str(machine.software_setup_time_value))
                    sst_unit_field.setCurrentIndex(sst_unit_field.findText(machine.software_setup_time_unit))
                    pto_cb.setChecked(machine.software_setup_parallel_to_operation)
                    #hst_value_field.setText(str(machine.hardware_setup_time_value))
                    #hst_unit_field.setCurrentIndex(hst_unit_field.findText(machine.hardware_setup_time_unit))
                    self.temp_hw_setup_matrix = machine.setup_matrix
                    self.temp_tool_slots = machine.tool_slots
                    hw_setup_op_parallel.setChecked(machine.hardware_setup_parallel_to_operation)
                    bp_cb.setChecked(machine.batch_processing)
                    self.temp_bs_diff = machine.diff_comp_batch
                    self.temp_bs_table = machine.batch_size
                    sf_field.setText(str(machine.speed_factor))
                    hmtbf_value_field.setText(str(machine.mtbf_value))
                    hmtbf_unit_field.setCurrentIndex(hmtbf_unit_field.findText(machine.mtbf_unit))
                    hmttr_value_field.setText(str(machine.mttr_value))
                    hmttr_unit_field.setCurrentIndex(hmttr_unit_field.findText(machine.mttr_unit))
                    transport_machine_cb.setChecked(machine.is_transport)
                    power_field.setText(str(machine.power_consumption))

            def save_machine():
                sel_acc_caps = [acc_cap_combo.itemText(x) for x in range(acc_cap_combo.count()) if acc_cap_combo.model().data(acc_cap_combo.model().index(x,0), Qt.CheckStateRole)==Qt.Checked]
                sel_prov_caps = [prov_cap_combo.itemText(x) for x in range(prov_cap_combo.count()) if prov_cap_combo.model().data(prov_cap_combo.model().index(x,0), Qt.CheckStateRole)==Qt.Checked]
                sel_tools = [compat_tools_combo.itemText(x) for x in range(compat_tools_combo.count()) if compat_tools_combo.model().data(compat_tools_combo.model().index(x,0), Qt.CheckStateRole)==Qt.Checked]
                # ToDo input format checking
                sst_val = float(sst_value_field.text())
                sst_unit = sst_unit_field.currentText()
                ss_po = pto_cb.isChecked()
                #hst_val = float(hst_value_field.text())
                hst_unit = self.temp_hst_time_unit
                hst = self.temp_hw_setup_matrix
                t_slt = self.temp_tool_slots
                hs_po = hw_setup_op_parallel.isChecked()
                bp = bp_cb.isChecked()
                bs = self.temp_bs_table
                sf = float(sf_field.text())
                mtbf_val = float(hmtbf_value_field.text())
                mtbf_unit = hmtbf_unit_field.currentText()
                mttr_val = float(hmttr_value_field.text())
                mttr_unit = hmttr_unit_field.currentText()
                is_transport = transport_machine_cb.isChecked()
                dcb = self.temp_bs_diff
                pow_cons = float(power_field.text())

                # Specify the Machine's attributes according to GUI selections
                machine = Machine(machine_id=item.text(), accepted_capabilities=sel_acc_caps, provided_capabilities=sel_prov_caps, compatible_tools=sel_tools,
                                  software_setup_time_value=sst_val, software_setup_time_unit=sst_unit, software_setup_parallel_to_operation=ss_po,
                                  hardware_setup_time_value=None, hardware_setup_time_unit=hst_unit, batch_processing=bp, batch_size=bs,
                                  speed_factor=sf, mtbf_value=mtbf_val, mtbf_unit=mtbf_unit, mttr_value=mttr_val, mttr_unit=mttr_unit, is_transport=is_transport,
                                  diff_comp_batch=dcb, power_consumption=pow_cons, hardware_setup_parallel_to_operation=hs_po, setup_matrix=hst, tool_slots=t_slt)

                self.production_system.machines.update({item.text(): machine})
                print("--> Saved machine in working memory:")
                print("machine_id:\t\t\t\t", self.production_system.machines[item.text()].machine_id)
                print("accepted_capabilities:\t\t\t", self.production_system.machines[item.text()].accepted_capabilities)
                print("provided_capabilities:\t\t\t", self.production_system.machines[item.text()].provided_capabilities)
                print("compatible_tools:\t\t\t", self.production_system.machines[item.text()].compatible_tools)
                print("software_setup_time:\t\t\t", self.production_system.machines[item.text()].software_setup_time_value, self.production_system.machines[item.text()].software_setup_time_unit)
                print("software_setup_parallel_to_operation:\t", self.production_system.machines[item.text()].software_setup_parallel_to_operation)
                print("setup_matrix:\t\t\t\t", self.production_system.machines[item.text()].setup_matrix, self.production_system.machines[item.text()].hardware_setup_time_unit)
                print("tool_slots:\t\t\t\t", self.production_system.machines[item.text()].tool_slots)
                print("batch_processing:\t\t\t", self.production_system.machines[item.text()].batch_processing)
                print("batch_size:\t\t\t\t", self.production_system.machines[item.text()].batch_size)
                print("power_consumption:\t\t\t", self.production_system.machines[item.text()].power_consumption)
                print("diff_comp_batch:\t\t\t", self.production_system.machines[item.text()].diff_comp_batch)
                print("speed_factor:\t\t\t\t", self.production_system.machines[item.text()].speed_factor)
                print("MTBF:\t\t\t\t\t", self.production_system.machines[item.text()].mtbf_value, self.production_system.machines[item.text()].mtbf_unit)
                print("MTTR:\t\t\t\t\t", self.production_system.machines[item.text()].mttr_value, self.production_system.machines[item.text()].mttr_unit)
                print("is_transport:\t\t\t\t", self.production_system.machines[item.text()].is_transport)

            def accept():
                save_machine()

            layout_2_2 = QVBoxLayout()
            layout_2_2.addWidget(transport_machine_cb)

            # Dialog buttons
            QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
            buttonBox = QDialogButtonBox(QBtn)
            buttonBox.accepted.connect(edit_dialog.accept)
            buttonBox.accepted.connect(accept)
            buttonBox.rejected.connect(edit_dialog.reject)
            layout_2_2.addWidget(buttonBox)
            machine_edit_layout.addLayout(layout_2_2, 2, 2)

            edit_dialog.setLayout(machine_edit_layout)
            load_machine()
            edit_dialog.exec()

    def add_new_workstation(self, provided_dict=None):
        if provided_dict is None:
            i = self.workstation_list_widget.count()     
            stan_name = "Workstation " + str(i)
            item = QListWidgetItem(stan_name)
            self.workstation_list_widget.addItem(item)
            self.production_system.workstations.update({stan_name: Workstation(workstation_id=stan_name)})
        else:
            item = QListWidgetItem(provided_dict['workstation_id'])
            self.workstation_list_widget.addItem(item)
            # prepare buffers separately as they are Buffer objects and not just dictionaries
            ibs = dict()
            for idx, buf in provided_dict['physical_input_buffers'].items():
                ib = Buffer(buffer_location=buf['buffer_location'],
                            idx1=idx,
                            diff_comp_comb=buf['diff_comp_comb'],
                            sequence_type=buf['sequence_type'],  # maybe Enum cast needed
                            comp_specific_sizes=buf['comp_specific_sizes'],
                            identical_buffer=buf['identical_buffer'])
                ibs.update({idx: ib})
            obs = dict()
            for idx, buf in provided_dict['physical_output_buffers'].items():
                ob = Buffer(buffer_location=buf['buffer_location'],
                            idx1=idx,
                            diff_comp_comb=buf['diff_comp_comb'],
                            sequence_type=buf['sequence_type'],  # maybe Enum cast needed
                            comp_specific_sizes=buf['comp_specific_sizes'],
                            identical_buffer=buf['identical_buffer'])
                obs.update({idx: ob})
            self.production_system.workstations.update({provided_dict['workstation_id']: Workstation(workstation_id=provided_dict['workstation_id'],
                                                                                                     machine=provided_dict['machine'],
                                                                                                     permanent_tools=provided_dict['permanent_tools'],
                                                                                                     seized_tools=list(),
                                                                                                     allowed_tool_pools=provided_dict['allowed_tool_pools'],
                                                                                                     input_operation_buffer=list(),
                                                                                                     output_operation_buffer=list(),
                                                                                                     wip_operations=list(),
                                                                                                     physical_input_buffers=ibs,
                                                                                                     physical_output_buffers=obs,
                                                                                                     wip_components=list(),
                                                                                                     allowed_worker_pools=provided_dict['allowed_worker_pools'],
                                                                                                     seized_worker=provided_dict['seized_worker'],
                                                                                                     permanent_worker_assignment=provided_dict['permanent_worker_assignment'],
                                                                                                     tools_in_use=list()
                                                                                                     )})
            self.temp_phys_input_buffers = provided_dict['physical_input_buffers']
            self.temp_phys_output_buffers = provided_dict['physical_output_buffers']
        self.workstation_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.workstation_list_widget.customContextMenuRequested.connect(self.show_workstation_menu)
        

    def show_workstation_menu(self,position):
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        edit_action = menu.addAction("Edit...")
        delete_action = menu.addAction("Delete")   
       
        action = menu.exec_(self.workstation_list_widget.viewport().mapToGlobal(position))

        item = self.workstation_list_widget.itemAt(position)

        if action == rename_action:
            old_name = item.text()
            new_name, ok = QInputDialog.getText(self, "Rename workstation", "Enter new workstation ID:")
            if ok and new_name:
                try:
                    self.production_system.workstations.update({new_name: self.production_system.workstations.pop(old_name)})
                    self.production_system.workstations[new_name].workstation_id = new_name
                except KeyError:
                    print("Workstation not in production system data yet, just renaming.")
                    self.production_system.workstations.update({new_name: Workstation(workstation_id=new_name)})  # ToDo: test this!
                item.setText(new_name)
        elif action == delete_action:
            row = self.workstation_list_widget.row(item)
            self.workstation_list_widget.takeItem(row)
            self.production_system.workstations.pop(item.text())
        elif action == edit_action:
            edit_dialog = QDialog()
            edit_dialog.setWindowTitle(f"Properties of workstation {item.text()}")
            edit_dialog.setMinimumSize(1024, 700)

            # Main layout for the dialog
            workstation_edit_layout = QGridLayout()

            # Box for machine selection
            m_sel_lt = QVBoxLayout()
            m_sel_label = QLabel("Machine:")
            m_sel_label.setMinimumWidth(200)
            mlw = self.resources_grid_layout.itemAtPosition(1,2).layout().itemAt(2).widget()  # machine list widget
            machines = [mlw.item(x).text() for x in range(mlw.count())]
            m_sel_combo = QComboBox()
            m_sel_combo.addItem("")  # empty item in case this is a manual workstation
            m_sel_combo.addItems(machines)
            m_sel_lt.addWidget(m_sel_label)
            m_sel_lt.addWidget(m_sel_combo)

            # Box for worker assignment
            w_assign_lt = QVBoxLayout()
            perm_w_assign_cb = QCheckBox("Permanent worker assignment")
            wlw = self.resources_grid_layout.itemAtPosition(0,1).layout().itemAt(2).widget()  # worker list widget
            workers = [wlw.item(x).text() for x in range(wlw.count())]
            w_assign_combo = QComboBox()
            w_assign_combo.addItem("")  # empty item in case no workers are assigned to this workstation permanently
            w_assign_combo.addItems(workers)
            w_assign_lt.addWidget(perm_w_assign_cb)
            w_assign_lt.addWidget(w_assign_combo)

            # Box for permanent tools assignment
            perm_tools_lt = QVBoxLayout()
            perm_tools_label = QLabel("Permanent tools:")
            perm_tools_label.setMinimumWidth(200)
            tlw = self.resources_grid_layout.itemAtPosition(0,3).layout().itemAt(2).widget()  # tools list widget
            tools = [tlw.item(x).text() for x in range(tlw.count())]
            perm_tools_combo = CheckableComboBox()
            perm_tools_combo.addItems(tools)
            perm_tools_lt.addWidget(perm_tools_label)
            perm_tools_lt.addWidget(perm_tools_combo)

            # Box for allowed resource pools
            allowed_res_pools_lt = QVBoxLayout()
            # Row for allowed worker pools
            allowed_wp_lt = QHBoxLayout()
            allowed_wp_label = QLabel("Allowed worker pools:")
            allowed_wp_label.setMinimumWidth(120)
            wplw = self.resources_grid_layout.itemAtPosition(0,2).layout().itemAt(2).widget()  # worker pools list widget
            worker_pools = [wplw.item(x).text() for x in range(wplw.count())]
            allowed_wp_combo = CheckableComboBox()
            allowed_wp_combo.addItems(worker_pools)
            allowed_wp_lt.addWidget(allowed_wp_label)
            allowed_wp_lt.addWidget(allowed_wp_combo)
            allowed_res_pools_lt.addLayout(allowed_wp_lt)
            # Row for allowed tool pools
            allowed_tp_lt = QHBoxLayout()
            allowed_tp_label = QLabel("Allowed tool pools:")
            allowed_tp_label.setMinimumWidth(120)
            tplw = self.resources_grid_layout.itemAtPosition(1,0).layout().itemAt(2).widget()  # tool pools list widget
            tool_pools = [tplw.item(x).text() for x in range(tplw.count())]
            allowed_tp_combo = CheckableComboBox()
            allowed_tp_combo.addItems(tool_pools)
            allowed_tp_lt.addWidget(allowed_tp_label)
            allowed_tp_lt.addWidget(allowed_tp_combo)
            allowed_res_pools_lt.addLayout(allowed_tp_lt)

            #  Box for input buffers
            #buffer_layout = QVBoxLayout()  # We are using GridLayout, so no separate boxes for in & out buffers required
            input_buffer_lt = QVBoxLayout()
            ib_label = QLabel("Physical input buffers:")
            #ib_label.setStyleSheet("font-weight: bold")
            ib_label.setMinimumWidth(200)
            input_buffer_lt.addWidget(ib_label)
            add_input_buffer_btn = QPushButton("Add buffer")
            add_input_buffer_btn.clicked.connect(lambda: self.add_input_buffer_section(buffer=None))
            input_buffer_lt.addWidget(add_input_buffer_btn)
            # Scroll area for input buffers (ib)
            ib_scroll_area = QScrollArea()
            ib_scroll_area.setWidgetResizable(True)
            ib_scroll_content = QWidget()
            self.ib_scroll_layout = QVBoxLayout(ib_scroll_content)  # Attach the scroll layout
            ib_scroll_area.setWidget(ib_scroll_content)
            input_buffer_lt.addWidget(ib_scroll_area)
            
            #  Box for output buffers
            #buffer_layout = QVBoxLayout()  # We are using GridLayout, so no separate boxes for in & out buffers required
            output_buffer_lt = QVBoxLayout()
            ob_label = QLabel("Physical output buffers:")
            #ob_label.setStyleSheet("font-weight: bold")
            ob_label.setMinimumWidth(200)
            output_buffer_lt.addWidget(ob_label)
            add_output_buffer_btn = QPushButton("Add buffer")
            add_output_buffer_btn.clicked.connect(lambda: self.add_output_buffer_section(buffer=None))
            output_buffer_lt.addWidget(add_output_buffer_btn)
            # Scroll area for output buffers (ob)
            ob_scroll_area = QScrollArea()
            ob_scroll_area.setWidgetResizable(True)
            ob_scroll_content = QWidget()
            self.ob_scroll_layout = QVBoxLayout(ob_scroll_content)  # Attach the scroll layout
            ob_scroll_area.setWidget(ob_scroll_content)
            output_buffer_lt.addWidget(ob_scroll_area)

            self.temp_phys_input_buffers = dict()
            self.temp_phys_output_buffers = dict()

            # To load previously saved workstation info into workstation edit dialog (for display purposes)
            def load_workstation():
                if not self.production_system.workstations:
                    return
                workstation = self.production_system.workstations[item.text()]
                if workstation:
                    m_sel_combo.setCurrentIndex(m_sel_combo.findText(workstation.machine))
                    perm_w_assign_cb.setChecked(workstation.permanent_worker_assignment)
                    w_assign_combo.setCurrentIndex(w_assign_combo.findText(workstation.seized_worker))  # for permanently assigned workers this won't be changed
                    for pt in workstation.permanent_tools:
                        pt_idx = perm_tools_combo.findText(pt)
                        perm_tools_combo.setItemData(pt_idx, Qt.Checked, Qt.CheckStateRole)
                    for awp in workstation.allowed_worker_pools:
                        awp_idx = allowed_wp_combo.findText(awp)
                        allowed_wp_combo.setItemData(awp_idx, Qt.Checked, Qt.CheckStateRole)
                    for atp in workstation.allowed_tool_pools:
                        atp_idx = allowed_tp_combo.findText(atp)
                        allowed_tp_combo.setItemData(atp_idx, Qt.Checked, Qt.CheckStateRole)
                    self.temp_phys_input_buffers = workstation.physical_input_buffers
                    for k,v in self.temp_phys_input_buffers.items():
                        self.add_input_buffer_section(buffer=v)
                    self.temp_phys_output_buffers = workstation.physical_output_buffers
                    for k,v in self.temp_phys_output_buffers.items():
                        self.add_output_buffer_section(buffer=v)
                else:
                    print("No workstation with such name known.")

            
            def save_workstation():
                m = m_sel_combo.currentText()
                pwa = perm_w_assign_cb.isChecked()
                perm_wrkr = w_assign_combo.currentText()
                perm_tls = [perm_tools_combo.itemText(x) for x in range(perm_tools_combo.count()) if perm_tools_combo.model().data(perm_tools_combo.model().index(x,0), Qt.CheckStateRole)==Qt.Checked]
                allowed_wps = [allowed_wp_combo.itemText(x) for x in range(allowed_wp_combo.count()) if allowed_wp_combo.model().data(allowed_wp_combo.model().index(x,0), Qt.CheckStateRole)==Qt.Checked]
                allowed_tps = [allowed_tp_combo.itemText(x) for x in range(allowed_tp_combo.count()) if allowed_tp_combo.model().data(allowed_tp_combo.model().index(x,0), Qt.CheckStateRole)==Qt.Checked]
                
                # Input buffers
                input_buffers = {}
                for i in range(self.ib_scroll_layout.count()):
                    # Buffer label
                    buff_loc = BufferLocation.IN
                    buff_idx1 = i + 1
                    # Sequence type
                    buffer_type = None
                    buffer_type_lt = self.ib_scroll_layout.itemAt(i).widget().layout().itemAt(1).layout()
                    for j in range(buffer_type_lt.count()):
                        if buffer_type_lt.itemAt(j).widget().isChecked():
                            buffer_type = BufferSequenceType(j + 1)
                    # Different components combinable
                    diff_comp_comb = self.ib_scroll_layout.itemAt(i).widget().layout().itemAt(2).widget().isChecked()
                    # Buffer size table
                    bs_table = self.ib_scroll_layout.itemAt(i).widget().layout().itemAt(3).widget()
                    bs_dict = {}
                    for row in range(bs_table.rowCount()):
                        dict_item = {bs_table.item(row,0).text(): {'Max. quantity': int(bs_table.item(row,1).text()),
                                                                   'Quantity step': int(bs_table.item(row,2).text()),
                                                                   'Group': bs_table.item(row,3).text()}}
                        bs_dict.update(dict_item)
                    buffer_save = Buffer(buffer_location=buff_loc, idx1=buff_idx1, sequence_type=buffer_type, diff_comp_comb=diff_comp_comb, comp_specific_sizes=bs_dict)
                    input_buffers.update({buff_idx1: buffer_save})

                # Output buffers    
                output_buffers = {}
                for i in range(self.ob_scroll_layout.count()):
                    # Buffer label
                    buff_loc = BufferLocation.OUT
                    buff_idx1 = i + 1
                    # Sequence type
                    buffer_type = None
                    buffer_type_lt = self.ob_scroll_layout.itemAt(i).widget().layout().itemAt(1).layout()
                    for j in range(buffer_type_lt.count()):
                        if buffer_type_lt.itemAt(j).widget().isChecked():
                            buffer_type = BufferSequenceType(j + 1)
                    # "Identical with" combo box
                    id_with = self.ob_scroll_layout.itemAt(i).widget().layout().itemAt(2).layout().itemAt(1).widget().currentText()
                    # Different components combinable
                    diff_comp_comb = self.ob_scroll_layout.itemAt(i).widget().layout().itemAt(3).widget().isChecked()
                    # Buffer size table
                    bs_table = self.ob_scroll_layout.itemAt(i).widget().layout().itemAt(4).widget()
                    bs_dict = {}
                    for row in range(bs_table.rowCount()):
                        dict_item = {bs_table.item(row,0).text(): {'Max. quantity': int(bs_table.item(row,1).text()),
                                                                   'Quantity step': int(bs_table.item(row,2).text()),
                                                                   'Group': bs_table.item(row,3).text()}}
                        bs_dict.update(dict_item)
                    buffer_save = Buffer(buffer_location=buff_loc, idx1=buff_idx1, sequence_type=buffer_type, diff_comp_comb=diff_comp_comb, comp_specific_sizes=bs_dict, identical_buffer=id_with)
                    output_buffers.update({buff_idx1: buffer_save})

                # Specify the Workstation's attributes according to GUI selections
                workstation = Workstation(workstation_id=item.text(), machine=m, permanent_worker_assignment=pwa, seized_worker=perm_wrkr, permanent_tools=perm_tls,
                                          allowed_worker_pools=allowed_wps, allowed_tool_pools=allowed_tps, physical_input_buffers=input_buffers, physical_output_buffers=output_buffers)

                self.production_system.workstations.update({item.text(): workstation})

                print("--> Saved workstation in working memory:")
                print("workstation_id:", self.production_system.workstations[item.text()].workstation_id)
                print("machine:", self.production_system.workstations[item.text()].machine)
                print("permanent_worker_assignment:", self.production_system.workstations[item.text()].permanent_worker_assignment)
                print("seized_worker:", self.production_system.workstations[item.text()].seized_worker)
                print("permanent_tools:", self.production_system.workstations[item.text()].permanent_tools)
                print("allowed_worker_pools:", self.production_system.workstations[item.text()].allowed_worker_pools)
                print("allowed_tool_pools:", self.production_system.workstations[item.text()].allowed_tool_pools)
                for k,v in self.production_system.workstations[item.text()].physical_input_buffers.items():
                    print("Input buffer", k)
                    print("sequence_type:", v.sequence_type)
                    print("diff_comp_comb:", v.diff_comp_comb)
                    print("comp_specific_sizes:", v.comp_specific_sizes)
                for k,v in self.production_system.workstations[item.text()].physical_output_buffers.items():
                    print("Output buffer", k)
                    print("sequence_type:", v.sequence_type)
                    print("diff_comp_comb:", v.diff_comp_comb)
                    print("comp_specific_sizes:", v.comp_specific_sizes)
                    

            def accept():
                save_workstation()


            # Dialog buttons
            save_cancel_lt = QVBoxLayout()
            QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
            buttonBox = QDialogButtonBox(QBtn)
            buttonBox.accepted.connect(edit_dialog.accept)
            buttonBox.accepted.connect(accept)
            buttonBox.rejected.connect(edit_dialog.reject)
            save_cancel_lt.addWidget(buttonBox)
            
            workstation_edit_layout.addLayout(m_sel_lt,0,0)
            workstation_edit_layout.addLayout(w_assign_lt,0,1)
            workstation_edit_layout.addLayout(perm_tools_lt,1,0)
            workstation_edit_layout.addLayout(allowed_res_pools_lt,1,1)
            workstation_edit_layout.addLayout(input_buffer_lt,2,0)
            workstation_edit_layout.addLayout(output_buffer_lt,2,1)
            workstation_edit_layout.addLayout(save_cancel_lt, 3,1)

            edit_dialog.setLayout(workstation_edit_layout)
            load_workstation()
            edit_dialog.exec_()  

    def add_input_buffer_section(self, buffer):
        section_layout = QVBoxLayout()
        
        # Add a label for the buffer section
        buffer_label = QLabel(f"Input buffer {self.ib_scroll_layout.count() + 1}")
        buffer_label.setStyleSheet("font-weight: bold")  # font-size: 14px;
        section_layout.addWidget(buffer_label)    
        
        # Add radio buttons
        rb_fifo = QRadioButton("FIFO")
        rb_lifo = QRadioButton("LIFO")
        rb_free = QRadioButton("Free sequence")
        rb_solid_raw_material = QRadioButton("Solid raw material")
        buffer_type_lt = QHBoxLayout()
        buffer_type_lt.addWidget(rb_fifo)
        buffer_type_lt.addWidget(rb_lifo)
        buffer_type_lt.addWidget(rb_free)
        buffer_type_lt.addWidget(rb_solid_raw_material)
        if buffer is not None:
            if buffer.sequence_type == BufferSequenceType.FIFO:
                rb_fifo.setChecked(True)
            if buffer.sequence_type == BufferSequenceType.LIFO:
                rb_lifo.setChecked(True)
            if buffer.sequence_type == BufferSequenceType.FREE:
                rb_free.setChecked(True)
            if buffer.sequence_type == BufferSequenceType.SOLID_RAW_MATERIAL:
                rb_solid_raw_material.setChecked(True)
        section_layout.addLayout(buffer_type_lt)

        # Checkbox for different component combinations
        diff_comp_comb_cb = QCheckBox("Different components combinable in buffer")
        if buffer is not None:
            diff_comp_comb_cb.setChecked(buffer.diff_comp_comb)
        section_layout.addWidget(diff_comp_comb_cb)

        # Add a table for component buffers
        cs_table = QTableWidget()
        cs_table.setColumnCount(4)
        cs_table.setHorizontalHeaderLabels(["Component name", "Max. quantity", "Quantity step", "Group"])
        cs_table.setColumnWidth(0, 150)
        cs_table.setColumnWidth(1, 80)
        cs_table.setColumnWidth(2, 80)
        cs_table.setColumnWidth(3, 100)
        cs_table.setMinimumHeight(200)
        if buffer is not None:
            for k,v in buffer.comp_specific_sizes.items():
                row_position = cs_table.rowCount()
                cs_table.insertRow(row_position)
                cs_table.setItem(row_position, 0, QTableWidgetItem(k))
                cs_table.setItem(row_position, 1, QTableWidgetItem(str(v['Max. quantity'])))
                cs_table.setItem(row_position, 2, QTableWidgetItem(str(v['Quantity step'])))
                cs_table.setItem(row_position, 3, QTableWidgetItem(v['Group']))
        section_layout.addWidget(cs_table)

        # Add a button to add rows to the table
        add_comp_buffer_btn = QPushButton("Add component buffer size")
        add_comp_buffer_btn.clicked.connect(lambda:self.add_cs_row(cs_table))
        section_layout.addWidget(add_comp_buffer_btn)

        # Wrap the section layout in a QWidget and add it to the scroll layout
        section_widget = QWidget()
        section_widget.setLayout(section_layout)
        self.ib_scroll_layout.addWidget(section_widget)
        # Force update the scroll area
        self.ib_scroll_layout.parentWidget().update()
        print("Input buffer section added!")  # Debugging line

    def add_output_buffer_section(self, buffer):
        section_layout = QVBoxLayout()
        
        # Add a label for the buffer section
        buffer_label = QLabel(f"Output buffer {self.ob_scroll_layout.count() + 1}")
        buffer_label.setStyleSheet("font-weight: bold")  # font-size: 14px;
        section_layout.addWidget(buffer_label)    
        
        # Add radio buttons
        rb_fifo = QRadioButton("FIFO")
        rb_lifo = QRadioButton("LIFO")
        rb_free = QRadioButton("Free sequence")
        rb_solid_raw_material = QRadioButton("Solid raw material")
        buffer_type_lt = QHBoxLayout()
        buffer_type_lt.addWidget(rb_fifo)
        buffer_type_lt.addWidget(rb_lifo)
        buffer_type_lt.addWidget(rb_free)
        buffer_type_lt.addWidget(rb_solid_raw_material)
        if buffer is not None:
            if buffer.sequence_type == BufferSequenceType.FIFO:
                rb_fifo.setChecked(True)
            if buffer.sequence_type == BufferSequenceType.LIFO:
                rb_lifo.setChecked(True)
            if buffer.sequence_type == BufferSequenceType.FREE:
                rb_free.setChecked(True)
            if buffer.sequence_type == BufferSequenceType.SOLID_RAW_MATERIAL:
                rb_solid_raw_material.setChecked(True)
        section_layout.addLayout(buffer_type_lt)

        # Checkbox for identical buffers
        id_buffer_lt = QHBoxLayout()
        identical_buffer_label = QLabel("Identical with: ")
        id_buffer_lt.addWidget(identical_buffer_label)
        identical_buffer_combo = QComboBox()
        identical_buffer_combo.addItem("")  # empty item in case it's an independent buffer
        # Generate a list of all input buffers in form (workstation_id, in/out, idx 1..), add to combo box
        # Actually we only need input buffers because we set an output buffer identical to another input buffer
        input_buffer_name_list = []
        if self.production_system.workstations:
            for ws in self.production_system.workstations.values():
                for ib in ws.physical_input_buffers.values():
                    input_buffer_name = ws.workstation_id + " : IN : " + str(ib.idx1)
                    input_buffer_name_list.append(input_buffer_name)
        for ibn in input_buffer_name_list:
            identical_buffer_combo.addItem(ibn) 
        id_buffer_lt.addWidget(identical_buffer_combo)
        if buffer is not None:
            # find saved selected combo box option for identical buffer
            identical_buffer_combo.setCurrentIndex(identical_buffer_combo.findText(buffer.identical_buffer))
        section_layout.addLayout(id_buffer_lt)

        # Checkbox for different component combinations
        diff_comp_comb_cb = QCheckBox("Different components combinable in buffer")
        if buffer is not None:
            diff_comp_comb_cb.setChecked(buffer.diff_comp_comb)
        section_layout.addWidget(diff_comp_comb_cb)

        # Add a table for component buffers
        cs_table = QTableWidget()
        cs_table.setColumnCount(4)
        cs_table.setHorizontalHeaderLabels(["Component name", "Max. quantity", "Quantity step", "Group"])
        cs_table.setColumnWidth(0, 150)
        cs_table.setColumnWidth(1, 80)
        cs_table.setColumnWidth(2, 80)
        cs_table.setColumnWidth(3, 100)
        cs_table.setMinimumHeight(200)
        if buffer is not None:
            for k,v in buffer.comp_specific_sizes.items():
                row_position = cs_table.rowCount()
                cs_table.insertRow(row_position)
                cs_table.setItem(row_position, 0, QTableWidgetItem(k))
                cs_table.setItem(row_position, 1, QTableWidgetItem(str(v['Max. quantity'])))
                cs_table.setItem(row_position, 2, QTableWidgetItem(str(v['Quantity step'])))
                cs_table.setItem(row_position, 3, QTableWidgetItem(v['Group']))
        section_layout.addWidget(cs_table)

        # Add a button to add rows to the table
        add_comp_buffer_btn = QPushButton("Add component buffer size")
        add_comp_buffer_btn.clicked.connect(lambda:self.add_cs_row(cs_table))
        section_layout.addWidget(add_comp_buffer_btn)

        # Wrap the section layout in a QWidget and add it to the scroll layout
        section_widget = QWidget()
        section_widget.setLayout(section_layout)
        self.ob_scroll_layout.addWidget(section_widget)
        # Force update the scroll area
        self.ob_scroll_layout.parentWidget().update()
        print("Output buffer section added!")  # Debugging line

    def add_cs_row(self, cs_table):
        row_position = cs_table.rowCount()
        cs_table.insertRow(row_position)
        cs_table.setItem(row_position, 0, QTableWidgetItem("*"))
        cs_table.setItem(row_position, 1, QTableWidgetItem("0"))
        cs_table.setItem(row_position, 2, QTableWidgetItem("0"))
        cs_table.setItem(row_position, 3, QTableWidgetItem(""))
            
    def add_new_toolpool(self, pool_id=None, provided_list=None):
        if provided_list is None:
            i = self.toolpools_list_widget.count() + 1
            tp_name="Tool pool " + str(i)
            item = QListWidgetItem(tp_name)
            self.toolpools_list_widget.addItem(item)
            self.production_system.tool_pools.update({tp_name: []})
        else:
            item = QListWidgetItem(pool_id)
            self.toolpools_list_widget.addItem(item)
            self.production_system.tool_pools.update({pool_id: provided_list})
        self.toolpools_list_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.toolpools_list_widget.customContextMenuRequested.connect(self.show_toolpools_menu)
        
   
    def show_toolpools_menu(self,position):
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        edit_action = menu.addAction("Edit...")
        delete_action = menu.addAction("Delete")
       
        action = menu.exec_(self.toolpools_list_widget.viewport().mapToGlobal(position))

        item = self.toolpools_list_widget.itemAt(position)

        if action == rename_action:
            old_name = item.text()
            new_name, ok = QInputDialog.getText(self, "Rename tool pool", "Enter new tool pool ID:")
            if ok and new_name:
                try:
                    self.production_system.tool_pools.update({new_name: self.production_system.tool_pools.pop(old_name)})
                    # A Tool pool is just a list of Tool IDs with a name, no further data manipulation needed for renaming
                except KeyError:
                    print("Tool pool not in production system data yet, just renaming.")
                    self.production_system.tool_pools.update({new_name: []})
                item.setText(new_name)
        elif action == delete_action:
            self.production_system.tool_pools.pop(item.name())
            row = self.toolpools_list_widget.row(item)
            self.toolpools_list_widget.takeItem(row)
        elif action == edit_action:
            edit_dialog = QDialog()
            edit_dialog.setWindowTitle(f"Properties of tool pool {item.text()}")

            # Main layout for the dialog
            toolpool_edit_layout = QVBoxLayout()
            prov_tool_label = QLabel("Provided tools:")
            prov_tool_label.setFixedWidth(400)
            toolpool_edit_layout.addWidget(prov_tool_label)

            # Button to add a tool to this tool pool
            def add_tool_row():
                tool_selection = QComboBox()
                lw = self.resources_grid_layout.itemAtPosition(0,3).layout().itemAt(2).widget()
                items = [lw.item(x).text() for x in range(lw.count())]
                tls = list(items)
                tool_selection.addItems(tls)
                edit_dialog.layout().itemAt(2).layout().addWidget(tool_selection)
            
            add_tool_button = QPushButton("Add tool")
            add_tool_button.clicked.connect(add_tool_row)
            toolpool_edit_layout.addWidget(add_tool_button)

            # Placeholder for capability drop-downs
            tp_lt = QVBoxLayout()
            toolpool_edit_layout.addLayout(tp_lt)

            # To load previously saved worker capabilities
            def load_tool_data():
                if self.production_system.tool_pools:
                    tool_list = self.production_system.tool_pools[item.text()]
                    if tool_list:
                        for c in tool_list:
                            tool_name_field = QComboBox()
                            lw = self.resources_grid_layout.itemAtPosition(0,3).layout().itemAt(2).widget()
                            tools = [lw.item(x).text() for x in range(lw.count())]
                            tool_name_field.addItems(tools)
                            i = tool_name_field.findText(c)
                            tool_name_field.setCurrentIndex(i)
                            edit_dialog.layout().itemAt(2).layout().addWidget(tool_name_field)
                else:
                    # there are no tools saved yet
                    return

            def save_tool_list():
                '''Important: for each instance of the same tool in a tool pool, a separate list entry is created, their tool_id are the same.'''
                tool_list = []
                for i in range(tp_lt.count()):
                    c = tp_lt.itemAt(i).widget().currentText()
                    tool_list.append(c)
                self.production_system.tool_pools.update({item.text(): tool_list})

            def accept():
                save_tool_list()

            # Dialog buttons
            QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
            buttonBox = QDialogButtonBox(QBtn)
            buttonBox.accepted.connect(accept)
            buttonBox.accepted.connect(edit_dialog.accept)
            buttonBox.rejected.connect(edit_dialog.reject)
            toolpool_edit_layout.addWidget(buttonBox)

            edit_dialog.setLayout(toolpool_edit_layout)
            load_tool_data()
            edit_dialog.exec()

    def populate_widgets_with_loaded_data(self):
        '''Add entries to the lists in the Production Resources tab after production system object is loaded'''
        if self.production_system:
            ps = self.production_system
            # List of unique worker capabilities
            if ps.worker_capabilities:
                self.worker_cap_list_widget.addItems(ps.worker_capabilities)
            if ps.workers:
                self.workers_list_widget.addItems(ps.workers)
            if ps.worker_pools:
                self.worker_pool_list_widget.addItems(list(ps.worker_pools.keys()))
            if ps.tools:
                self.tool_list_widget.addItems(list(ps.tools.keys()))
            if ps.tool_pools:
                self.toolpools_list_widget.addItems(list(ps.tool_pools.keys()))
            if ps.machine_capabilities:
                self.machine_cap_list_widget.addItems(ps.machine_capabilities)
            if ps.machines:
                self.machines_list_widget.addItems(list(ps.machines.keys()))
            if ps.workstations:
                self.workstation_list_widget.addItems(list(ps.workstations.keys()))


class ProbabilityDistributionWidget(QWidget):
    def __init__(self, time_unit=None, p_immed=None, min=None, alpha=None, beta=None):
        super().__init__()
        #self.setWindowTitle('Time Units and Distribution Parameters')
        #self.setGeometry(100, 100, 800, 600)
        
        # Layout Setup
        self.layout = QVBoxLayout(self)

        # Time units combo box
        self.time_units_label = QLabel("Time units")
        self.time_units_combo = QComboBox()
        self.time_units_combo.addItems(['s', 'min', 'h', 'd'])
        if time_unit is not None:
            self.time_units_combo.setCurrentIndex(self.time_units_combo.findText(time_unit))
        self.time_units_combo.currentIndexChanged.connect(self.update_plot)
        
        # Probability of immediate availability slider
        self.prob_label = QLabel("Probability of immediate availability")
        self.prob_slider = QSlider(Qt.Horizontal)
        self.prob_slider.setRange(0, 100)
        self.prob_slider.setValue(100 if p_immed is None else int(p_immed*100))
        self.prob_slider.valueChanged.connect(self.update_plot)
        self.prob_value_label = QLabel("1.00")

        # Lead time distribution parameters
        self.lead_time_label = QLabel("Lead time distribution (Gamma distribution) parameters:")

        self.min_label = QLabel("min")
        self.min_input = QLineEdit("1" if min is None else str(min))
        self.min_input.setValidator(QtGui.QIntValidator(1, 1000))
        self.min_input.textChanged.connect(self.update_plot)

        self.alpha_label = QLabel("alpha")
        self.alpha_input = QLineEdit("1" if alpha is None else str(alpha))
        self.alpha_input.setValidator(QtGui.QIntValidator(1, 100))
        self.alpha_input.textChanged.connect(self.update_plot)

        self.beta_label = QLabel("beta")
        self.beta_input = QLineEdit("0.5" if beta is None else str(beta))
        self.beta_input.setValidator(QtGui.QDoubleValidator(0.1, 10.0, 2))
        self.beta_input.textChanged.connect(self.update_plot)

        # Create layout for parameter section
        param_layout = QVBoxLayout()
        min_layout = QHBoxLayout()
        min_layout.addWidget(self.min_label)
        min_layout.addWidget(self.min_input)
        alpha_layout = QHBoxLayout()
        alpha_layout.addWidget(self.alpha_label)
        alpha_layout.addWidget(self.alpha_input)
        beta_layout = QHBoxLayout()
        beta_layout.addWidget(self.beta_label)
        beta_layout.addWidget(self.beta_input)
        param_layout.addLayout(min_layout)
        param_layout.addLayout(alpha_layout)
        param_layout.addLayout(beta_layout)

        # Horizontal Layout for time units and Probability
        time_units_layout = QHBoxLayout()
        time_units_layout.addWidget(self.time_units_label)
        time_units_layout.addWidget(self.time_units_combo)

        prob_layout = QHBoxLayout()
        prob_layout.addWidget(self.prob_label)
        prob_layout.addWidget(self.prob_slider)
        prob_layout.addWidget(self.prob_value_label)

        # Add all widgets to the main layout
        self.layout.addLayout(time_units_layout)
        self.layout.addLayout(prob_layout)
        self.layout.addWidget(self.lead_time_label)
        self.layout.addLayout(param_layout)

        # Create a canvas to display the plot
        self.canvas = FigureCanvas(plt.figure(figsize=(6, 4)))
        self.canvas.setFixedSize(600, 400)  # Fixed size for the canvas
        self.layout.addWidget(self.canvas)

        self.update_plot()  # Initial plot update

    def update_plot(self):
        # Fetch current inputs, add checks for valid inputs
        try:
            time_unit = self.time_units_combo.currentText()
            prob_val = self.prob_slider.value() / 100

            min_val = int(self.min_input.text()) if self.min_input.text() else 1
            alpha_val = int(self.alpha_input.text()) if self.alpha_input.text() else 1
            beta_val = float(self.beta_input.text()) if self.beta_input.text() else 0.5

            # Update probability label
            self.prob_value_label.setText(f"{prob_val:.2f}")

            # Generate Gamma distribution data
            x = np.linspace(0, 10 * min_val, 1000)
            y = np.random.gamma(alpha_val, beta_val, 10000) + min_val
            counts, bins = np.histogram(y, bins=10 * min_val, range=(0, 10 * min_val), density=True)

            # Scale the first bin to match the desired prob_val
            counts[0] = prob_val

            # Normalize the remaining counts to ensure the sum is 1.0
            counts_sum = np.sum(counts)
            if counts_sum > 0:
                counts[1:] = counts[1:] * (1 - prob_val)

            # Plot the histogram
            self.canvas.figure.clear()
            ax = self.canvas.figure.add_subplot(111)
            ax.bar(bins[:-1], counts, width=np.diff(bins), align='edge', color='#009ED7', edgecolor='black')

            ax.set_xlabel(f"Time ({time_unit})")
            ax.set_ylabel("Probability")
            ax.set_title(f"Gamma Distribution\nmin={min_val}, alpha={alpha_val}, beta={beta_val}")

            self.canvas.draw()
        except ValueError:
            # Ignore errors if inputs are empty or invalid (like alpha being non-integer)
            pass

class SimulationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # Main Layout for System Simulation (Horizontal Layout)
        simulation_layout = QHBoxLayout()  # Horizontal layout for placing both panels side by side

        # Left panel (System-Wide Properties)
        left_widget = QWidget()
        left_panel = QVBoxLayout()

        # Title Label
        title_label = QLabel("System simulation")
        title_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        left_panel.addWidget(title_label)

        # GroupBox for System-Wide Properties (Material Supply, Distances, etc.)
        system_group = QGroupBox("System-wide properties")
        system_layout = QVBoxLayout()  # Vertical layout for buttons

        system_layout.setSpacing(10)  # Reduces space between buttons

        # Supply and Storage Button
        self.supply_storage_btn = QPushButton("Supply and storage")
        self.supply_storage_btn.clicked.connect(self.open_supply_storage)
        system_layout.addWidget(self.supply_storage_btn)

        # Conveyors Button
        self.conveyors_btn = QPushButton("Conveyors")
        self.conveyors_btn.clicked.connect(self.open_conveyors)
        system_layout.addWidget(self.conveyors_btn)

        # Distances Button
        self.distances_btn = QPushButton("Distances")
        self.distances_btn.clicked.connect(self.open_distances)
        system_layout.addWidget(self.distances_btn)

        # Walking Speed Input Field
        system_layout.addWidget(QLabel("Walking speed (m/s):"))
        self.walking_speed_input = QLineEdit()
        #self.walking_speed_input.setPlaceholderText("e.g., 1.0")
        #self.walking_speed_input.setText(str(main_window.production_resources_tab.production_system.walking_speed))
        system_layout.addWidget(self.walking_speed_input)

        # Energy costs input field
        system_layout.addWidget(QLabel("Energy costs (Cent/kWh):"))
        self.energy_costs_input = QLineEdit()
        #self.energy_costs_input.setPlaceholderText("e.g., 20.24")
        #self.energy_costs_input.setText(str(main_window.production_resources_tab.production_system.energy_costs))
        system_layout.addWidget(self.energy_costs_input)

        # Add the system layout to the GroupBox
        system_group.setLayout(system_layout)
        left_panel.addWidget(system_group)

        # Add the left panel to the main layout (simulation_layout)
        left_panel.setAlignment(QtCore.Qt.AlignTop)
        left_widget.setLayout(left_panel)
        left_widget.setFixedWidth(200)
        simulation_layout.addWidget(left_widget)

        # Right panel for Start, Stop, Pause, and Time Inputs (horizontal layout)
        right_panel = QVBoxLayout()

        # GroupBox for Controls (Start, Stop, Pause, and time-related inputs)
        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout()

        # Start, Stop, Pause Buttons
        start_btn = QPushButton("Start")
        start_btn.clicked.connect(self.start_simulation)
        start_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(start_btn)

        stop_btn = QPushButton("Stop")
        stop_btn.clicked.connect(self.stop_simulation)
        stop_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(stop_btn)

        pause_btn = QPushButton("Pause")
        pause_btn.clicked.connect(self.pause_simulation)
        pause_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(pause_btn)

        # Add Time Factor, Start Time, End Time inputs
        time_factor_lbl = QLabel("Time factor:")
        time_factor_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(time_factor_lbl)
        self.time_factor_input = QLineEdit()
        self.time_factor_input.setPlaceholderText("e.g., 1.0")
        self.time_factor_input.setFixedWidth(50)
        controls_layout.addWidget(self.time_factor_input)

        start_time_lbl = QLabel("Start time:")
        start_time_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(start_time_lbl)
        self.start_time_input = QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.start_time_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        #self.start_time_input = QLineEdit()
        #self.start_time_input.setPlaceholderText("YYYY-MM-DD")
        controls_layout.addWidget(self.start_time_input)

        end_time_lbl = QLabel("End time:")
        end_time_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(end_time_lbl)
        self.end_time_input = QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.end_time_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(self.end_time_input)

        # Add the controls layout to the GroupBox
        controls_layout.setAlignment(QtCore.Qt.AlignLeft)
        controls_group.setLayout(controls_layout)
        right_panel.addWidget(controls_group)

        # Add the right panel to the main layout (simulation_layout)
        simulation_layout.addLayout(right_panel)

        # Set alignment to the top-right for the controls panel
        simulation_layout.setAlignment(right_panel, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        simulation_layout.setAlignment(left_panel, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        # Set the Main Layout for the widget
        self.setLayout(simulation_layout)

    # Example methods for button clicks
    def open_supply_storage(self):
        # Supply and Storage Dialog
        supply_storage_wizard = QWizard(self)
        supply_storage_wizard.setWindowTitle("Supply and storage")

        # Set the size of the dialog box (width, height)
        supply_storage_wizard.resize(930, 780)  # Resize dialog on start
        # Alternatively, set a fixed size
        # dialog.setFixedSize(400, 300)  # Makes the dialog non-resizable with fixed width and height

        # Page for Step 1 (material supply behaviour)
        step1_page = QWizardPage()

        step1_layout = QVBoxLayout()
        step1_label = QLabel("Step 1: Define material supply behaviour")
        step1_label.setStyleSheet("font-weight: bold")
        step1_layout.addWidget(step1_label)
        # Scroll area for component/material-specific supply behaviour
        supply1_scroll_area = QScrollArea()
        supply1_scroll_area.setWidgetResizable(True)
        supply1_scroll_content = QWidget()
        self.supply1_scroll_layout = QVBoxLayout(supply1_scroll_content)
        supply1_scroll_area.setWidget(supply1_scroll_content)
        step1_layout.addWidget(supply1_scroll_area)

        # Each line is for a raw material/ component that is an input of operation nodes without incoming edges
        raw_material_name_list = main_window.product_instructions_tab.product_palette.get_raw_material_names()
        #raw_material_name_list = ['a', 'b', 'c']  # for testing

        # Load supply data if available
        def load_supply():
            for raw_material in raw_material_name_list:
                raw_material_supply_layout = QHBoxLayout()
                # Prepare data if available
                alloc_type = None
                tu = None
                ip = None
                min = None
                alpha = None
                beta = None
                if raw_material in main_window.production_resources_tab.production_system.supply_behaviours.keys():
                    sb = main_window.production_resources_tab.production_system.supply_behaviours[raw_material]
                    alloc_type = sb.allocation_type
                    tu = sb.time_unit
                    ip = sb.immediate_probability
                    min = sb.min
                    alpha = sb.alpha
                    beta = sb.beta
                # Raw material or component name
                raw_material_label = QLabel(raw_material)
                raw_material_label.setMinimumWidth(100)
                raw_material_supply_layout.addWidget(raw_material_label)
                # Supply / allocation type
                raw_material_supply_type_combo = QComboBox()
                raw_material_supply_type_combo.addItems(['Order-specific', 'Order-anonymous'])
                if alloc_type is not None:
                    raw_material_supply_type_combo.setCurrentIndex(alloc_type - 1)
                raw_material_supply_layout.addWidget(raw_material_supply_type_combo)
                # Lead time distribution
                raw_material_supply_layout.addWidget(ProbabilityDistributionWidget(time_unit=tu, p_immed=ip, min=min, alpha=alpha, beta=beta))

                # Wrap the section layout in a QWidget and add it to the scroll layout
                raw_material_supply_frame = QFrame()
                raw_material_supply_frame.setLayout(raw_material_supply_layout)
                raw_material_supply_frame.setFrameStyle(QFrame.Box | QFrame.Plain)
                
                self.supply1_scroll_layout.addWidget(raw_material_supply_frame)
                # Force update the scroll area
                self.supply1_scroll_layout.parentWidget().update()

        load_supply()

        step1_page.setLayout(step1_layout)
        
        # Page for Step 2 (inventories)
        step2_page = QWizardPage()

        step2_layout = QVBoxLayout()
        step2_label = QLabel("Step 2: Define inventories and storage")
        step2_label.setStyleSheet("font-weight: bold")
        step2_layout.addWidget(step2_label)
        add_inventory_btn = QPushButton("Add inventory")
        add_inventory_btn.clicked.connect(lambda: add_inventory(inventory=None))
        step2_layout.addWidget(add_inventory_btn)
        # Scroll area for inventories
        supply2_scroll_area = QScrollArea()
        supply2_scroll_area.setWidgetResizable(True)
        supply2_scroll_content = QWidget()
        self.supply2_scroll_layout = QVBoxLayout(supply2_scroll_content)
        supply2_scroll_area.setWidget(supply2_scroll_content)
        step2_layout.addWidget(supply2_scroll_area)

        def add_inventory(inventory):
            section_layout = QVBoxLayout()

            # Add a label for the conveyor section
            inventory_id_input = QLineEdit(f"Inventory {self.supply2_scroll_layout.count() + 1}" if inventory is None else inventory.inventory_id)
            inventory_id_input.setStyleSheet("font-weight: bold")  # font-size: 14px;
            section_layout.addWidget(inventory_id_input)

            # Combo box for material generation type (source/buffer/sink)
            gen_type_combo = QComboBox()
            gen_type_combo.addItems(['Buffer', 'Source', 'Sink'])
            if inventory is not None:
                gen_type_text = ''
                if inventory.generation_type == InventoryGenerationType.BUFFER:
                    gen_type_text = 'Buffer'
                elif inventory.generation_type == InventoryGenerationType.SOURCE:
                    gen_type_text = 'Source'
                elif inventory.generation_type == InventoryGenerationType.SINK:
                    gen_type_text = 'Sink'
                gen_type_combo.setCurrentIndex(gen_type_combo.findText(gen_type_text))
            section_layout.addWidget(gen_type_combo)
            
            # Add radio buttons
            rb_fifo = QRadioButton("FIFO")
            rb_lifo = QRadioButton("LIFO")
            rb_free = QRadioButton("Free sequence")
            rb_solid_raw_material = QRadioButton("Solid raw material")
            inventory_type_lt = QHBoxLayout()
            inventory_type_lt.addWidget(rb_fifo)
            inventory_type_lt.addWidget(rb_lifo)
            inventory_type_lt.addWidget(rb_free)
            inventory_type_lt.addWidget(rb_solid_raw_material)
            if inventory is not None:
                if inventory.sequence_type == BufferSequenceType.FIFO:
                    rb_fifo.setChecked(True)
                if inventory.sequence_type == BufferSequenceType.LIFO:
                    rb_lifo.setChecked(True)
                if inventory.sequence_type == BufferSequenceType.FREE:
                    rb_free.setChecked(True)
                if inventory.sequence_type == BufferSequenceType.SOLID_RAW_MATERIAL:
                    rb_solid_raw_material.setChecked(True)
            section_layout.addLayout(inventory_type_lt)

            # Combobox for identical buffers
            id_buffer_lt = QHBoxLayout()
            identical_buffer_label = QLabel("Identical with: ")
            id_buffer_lt.addWidget(identical_buffer_label)
            identical_buffer_combo = QComboBox()
            identical_buffer_combo.addItem("")  # empty item in case it's an independent buffer

            # Generate a list of all buffers in form (workstation_id, in/out, idx 1..), add to combo box
            # Here we need both input and output buffers, because inventories can be sources, sinks and neutral buffers between workstations
            buffer_name_list = []
            if main_window.production_resources_tab.production_system.workstations:
                for ws in main_window.production_resources_tab.production_system.workstations.values():
                    for ib in ws.physical_input_buffers.values():
                        input_buffer_name = ws.workstation_id + " : IN : " + str(ib.idx1)
                        buffer_name_list.append(input_buffer_name)
                    for ob in ws.physical_output_buffers.values():
                        output_buffer_name = ws.workstation_id + " : OUT : " + str(ob.idx1)
                        buffer_name_list.append(output_buffer_name)
            for ibn in buffer_name_list:
                identical_buffer_combo.addItem(ibn) 
            id_buffer_lt.addWidget(identical_buffer_combo)
            if inventory is not None:
                # find saved selected combo box option for identical buffer
                identical_buffer_combo.setCurrentIndex(identical_buffer_combo.findText(inventory.identical_buffer))
            section_layout.addLayout(id_buffer_lt)

            # Checkbox for different component combinations
            diff_comp_comb_cb = QCheckBox("Different components combinable in buffer")
            if inventory is not None:
                diff_comp_comb_cb.setChecked(inventory.diff_comp_comb)
            section_layout.addWidget(diff_comp_comb_cb)

            # Add a table for component buffers
            cs_table = QTableWidget()
            cs_table.setColumnCount(4)
            cs_table.setHorizontalHeaderLabels(["Component name", "Max. quantity", "Quantity step", "Group"])
            cs_table.setColumnWidth(0, 150)
            cs_table.setColumnWidth(1, 80)
            cs_table.setColumnWidth(2, 80)
            cs_table.setColumnWidth(3, 100)
            cs_table.setMinimumHeight(200)
            if inventory is not None:
                for k,v in inventory.comp_specific_sizes.items():
                    row_position = cs_table.rowCount()
                    cs_table.insertRow(row_position)
                    cs_table.setItem(row_position, 0, QTableWidgetItem(k))
                    cs_table.setItem(row_position, 1, QTableWidgetItem(str(v['Max. quantity'])))
                    cs_table.setItem(row_position, 2, QTableWidgetItem(str(v['Quantity step'])))
                    cs_table.setItem(row_position, 3, QTableWidgetItem(v['Group']))
            section_layout.addWidget(cs_table)

            # Add a button to add rows to the table
            add_comp_buffer_btn = QPushButton("Add component-specific inventory capacity")
            add_comp_buffer_btn.clicked.connect(lambda:add_cs_row(cs_table))
            section_layout.addWidget(add_comp_buffer_btn)

            # Wrap the section layout in a QWidget and add it to the scroll layout
            section_widget = QWidget()
            section_widget.setLayout(section_layout)
            self.supply2_scroll_layout.addWidget(section_widget)
            # Force update the scroll area
            self.supply2_scroll_layout.parentWidget().update()
            print("Inventory section added!")  # Debugging line

        def add_cs_row(cs_table):
            row_position = cs_table.rowCount()
            cs_table.insertRow(row_position)

            # ToDo: Instead of manually typing in component names,
            # here a combo box with all already known component ids can be provided...
            # But maybe it's better not to do it in this case because the number of all
            # components will be pretty large

            cs_table.setItem(row_position, 0, QTableWidgetItem("*"))
            cs_table.setItem(row_position, 1, QTableWidgetItem("0"))
            cs_table.setItem(row_position, 2, QTableWidgetItem("0"))
            cs_table.setItem(row_position, 3, QTableWidgetItem(""))
        
        # Load inventory data if available
        def load_inventories():
            for inv in main_window.production_resources_tab.production_system.inventories.values():
                add_inventory(inv)

        load_inventories()

        step2_page.setLayout(step2_layout)

        supply_storage_wizard.addPage(step1_page)
        supply_storage_wizard.addPage(step2_page)
        
        # Connect saving function (both steps of the wizard) to the "Finish" button
        def save_supply_storage():
            # Save all component-specific supply behaviours
            for i in range(self.supply1_scroll_layout.layout().count()):
                component_id = raw_material_name_list[i]
                allocation_type = SupplyAllocationType.ORDER_SPECIFIC
                if self.supply1_scroll_layout.layout().itemAt(i).widget().layout().itemAt(1).widget().currentText() == 'Order-specific':
                    allocation_type = SupplyAllocationType.ORDER_SPECIFIC
                else:
                    allocation_type = SupplyAllocationType.ORDER_ANONYMOUS
                prob_dist_widget = self.supply1_scroll_layout.layout().itemAt(i).widget().layout().itemAt(2).widget()
                time_unit = prob_dist_widget.time_units_combo.currentText()
                immed_prob = prob_dist_widget.prob_slider.value() / 100.0
                minimum = int(prob_dist_widget.min_input.text())
                alpha = int(prob_dist_widget.alpha_input.text())
                beta = float(prob_dist_widget.beta_input.text())
                sb = SupplyBehaviour(component_id=component_id, allocation_type=allocation_type,
                                     time_unit=time_unit, immediate_probability=immed_prob,
                                     min=minimum, alpha=alpha, beta=beta)
                main_window.production_resources_tab.production_system.supply_behaviours.update({component_id: sb})
            # Save inventories (storages)
            for i in range(self.supply2_scroll_layout.layout().count()):
                # Get inventory section
                section_layout = self.supply2_scroll_layout.layout().itemAt(i).widget().layout()
                inventory_id = section_layout.itemAt(0).widget().text()
                gen_type_int = section_layout.itemAt(1).widget().currentIndex() + 1
                gen_type = InventoryGenerationType(gen_type_int)
                buffer_type = None
                buffer_type_lt = section_layout.itemAt(2).layout()
                for j in range(buffer_type_lt.count()):
                    if buffer_type_lt.itemAt(j).widget().isChecked():
                        buffer_type = BufferSequenceType(j + 1)
                ident_buffer_combo = section_layout.itemAt(3).layout().itemAt(1).widget()
                ident_buffer = ident_buffer_combo.currentText()
                diff_comp_comb = section_layout.itemAt(4).widget().isChecked()
                cs_table = section_layout.itemAt(5).widget()
                cs_dict = {}
                for row in range(cs_table.rowCount()):
                        dict_item = {cs_table.item(row,0).text(): {'Max. quantity': int(cs_table.item(row,1).text()),
                                                                   'Quantity step': int(cs_table.item(row,2).text()),
                                                                   'Group': cs_table.item(row,3).text()}}
                        cs_dict.update(dict_item)
                inventory = Inventory(inventory_id=inventory_id, diff_comp_comb=diff_comp_comb, generation_type=gen_type, sequence_type=buffer_type, comp_specific_sizes=cs_dict, identical_buffer=ident_buffer)
                main_window.production_resources_tab.production_system.inventories.update({inventory_id: inventory})

        supply_storage_wizard.button(QWizard.FinishButton).clicked.connect(save_supply_storage)

        # Show dialog
        supply_storage_wizard.exec_()

    def add_distance_row(self, dist_table=None, loaded_distance=None, workstation_ids=list(), inventory_ids=list()):
        # Combine all workstation ids and inventory ids in a single list
        option_list = workstation_ids + inventory_ids
        row_position = dist_table.rowCount()
        dist_table.insertRow(row_position)
        # Create combo box
        ws_combo_from = QComboBox()
        ws_combo_from.addItems(option_list)
        if loaded_distance is not None:
            ws_combo_from.setCurrentIndex(ws_combo_from.findText(loaded_distance[0]))
        # Set cell widget
        dist_table.setCellWidget(row_position, 0, ws_combo_from)
        ws_combo_to = QComboBox()
        ws_combo_to.addItems(option_list)
        if loaded_distance is not None:
            ws_combo_to.setCurrentIndex(ws_combo_to.findText(loaded_distance[1]))
        dist_table.setCellWidget(row_position, 1, ws_combo_to)
        dist_table.setItem(row_position, 2, QTableWidgetItem("0.0" if loaded_distance is None else str(loaded_distance[2])))

    def open_distances(self):
        distances_edit_dialog = QDialog()
        distances_edit_dialog.setWindowTitle(f"Distances")
        distances_edit_dialog.setMinimumSize(700, 500)
        distances_edit_layout = QVBoxLayout()

        add_dist_btn = QPushButton("Add distance specification")
        distances_edit_layout.addWidget(add_dist_btn)

        distance_scroll_area = QScrollArea()
        distance_scroll_area.setWidgetResizable(True)
        distance_scroll_content = QWidget()
        self.distance_scroll_layout = QVBoxLayout(distance_scroll_content)

        distance_table = QTableWidget()
        distance_table.setColumnCount(3)
        distance_table.setHorizontalHeaderLabels(["From", "To", "Distance (m)"])
        self.distance_scroll_layout.addWidget(distance_table)
        # Get all workstation ids and inventory ids
        workstation_ids = list(main_window.production_resources_tab.production_system.workstations.keys())
        inventory_ids = list(main_window.production_resources_tab.production_system.inventories.keys())
        add_dist_btn.clicked.connect(lambda:self.add_distance_row(dist_table=distance_table, loaded_distance=None, workstation_ids=workstation_ids, inventory_ids=inventory_ids))

        distance_scroll_area.setWidget(distance_scroll_content)
        distances_edit_layout.addWidget(distance_scroll_area)

        # Backend functions
        def load_distances():
            for from_id, targets in main_window.production_resources_tab.production_system.distance_matrix.items():
                for to_id, distance in targets.items():
                    self.add_distance_row(dist_table=distance_table, loaded_distance=(from_id, to_id, distance),
                                          workstation_ids=workstation_ids, inventory_ids=inventory_ids)

        load_distances()

        def save_distances():
            dist_mat = dict()
            for row in range(distance_table.rowCount()):
                from_id = distance_table.cellWidget(row,0).currentText()
                to_id = distance_table.cellWidget(row,1).currentText()
                if from_id in dist_mat.keys():
                    dist_mat[from_id].update({to_id: float(distance_table.item(row,2).text())})
                    # Symmetry:
                    #dist_mat[to_id].update({from_id: float(distance_table.item(row,2).text())})
                else:
                    dist_mat.update({from_id: {to_id: float(distance_table.item(row,2).text())}})
                    # Symmetry:
                    #dist_mat[to_id].update({from_id: float(distance_table.item(row,2).text())})
            main_window.production_resources_tab.production_system.distance_matrix = dist_mat

        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(save_distances)
        buttonBox.accepted.connect(distances_edit_dialog.accept)
        buttonBox.rejected.connect(distances_edit_dialog.reject)
        distances_edit_layout.addWidget(buttonBox)
        distances_edit_dialog.setLayout(distances_edit_layout)
        distances_edit_dialog.exec_()



    def add_cc_row(self, cc_table=QTableWidget, row=None):
        # conveyor capacity
        row_position = cc_table.rowCount()
        cc_table.insertRow(row_position)
        cc_table.setItem(row_position, 0, QTableWidgetItem("*" if row is None else row['Component name']))
        cc_table.setItem(row_position, 1, QTableWidgetItem("0" if row is None else row['Max. quantity']))
        cc_table.setItem(row_position, 2, QTableWidgetItem("0" if row is None else row['Quantity step']))
        cc_table.setItem(row_position, 3, QTableWidgetItem("" if row is None else row['Group']))

    def add_ws_alloc_row(self, ws_alloc_table=QTableWidget, row=None):
        # workstation allocation (to a conveyor)
        row_position = ws_alloc_table.rowCount()
        ws_alloc_table.insertRow(row_position)
        ws_combo = QComboBox()
        # ToDo: get workstation id list from Production resources tab
        ws_combo.addItem("")
        ws_combo.addItem("WS1")
        ws_combo.addItem("WS2")
        ws_combo.addItem("WS3")
        ws_alloc_table.setCellWidget(row_position, 0, ws_combo)
        buffer_combo = QComboBox()
        # ToDo: load buffers from the workstation selected in the first column
        buffer_combo.addItem("")
        buffer_combo.addItem("IN1")
        buffer_combo.addItem("OUT1")
        ws_alloc_table.setCellWidget(row_position, 1, buffer_combo)
        ws_alloc_table.setItem(row_position, 2, QTableWidgetItem("0.0"))

    def add_conveyor(self, loaded_conveyor=None):
        section_layout = QVBoxLayout()
        
        # Add a label for the conveyor section
        conv_id_input = QLineEdit(f"Conveyor {self.conveyor_scroll_layout.count() + 1}" if loaded_conveyor is None else loaded_conveyor.conveyor_id)
        conv_id_input.setStyleSheet("font-weight: bold")  # font-size: 14px;
        section_layout.addWidget(conv_id_input) 

        # Input field for conveyor length
        cl_lt = QHBoxLayout()
        cl_lbl = QLabel("Length (m):")
        cl_lt.addWidget(cl_lbl)
        cl_edit = QLineEdit("0.0" if loaded_conveyor is None else str(loaded_conveyor.length))
        cl_lt.addWidget(cl_edit)
        section_layout.addLayout(cl_lt)

        # Input field for conveyor speed
        cs_lt = QHBoxLayout()
        cs_lbl = QLabel("Speed (m/s):")
        cs_lt.addWidget(cs_lbl)
        cs_edit = QLineEdit("0.0" if loaded_conveyor is None else str(loaded_conveyor.speed))
        cs_lt.addWidget(cs_edit)
        section_layout.addLayout(cs_lt)

        # Checkbox for synchronous transport
        sync_cb = QCheckBox("Synchronous transport of all objects")
        sync_cb.setChecked(False if loaded_conveyor is None else loaded_conveyor.synchronous)
        section_layout.addWidget(sync_cb)

        # Checkbox for upstream setup only when conveyor is empty
        usowe_cb = QCheckBox("Setup of upstream stations requires empty conveyor")
        usowe_cb.setChecked(False if loaded_conveyor is None else loaded_conveyor.upstream_setup_only_when_empty)
        section_layout.addWidget(usowe_cb)

        # Checkbox for object combination
        dcc_cb = QCheckBox("Different components combinable on the conveyor")
        dcc_cb.setChecked(False if loaded_conveyor is None else loaded_conveyor.diff_comp_comb)
        section_layout.addWidget(dcc_cb)

        # Table columns for conveyor capacities and for workstation allocation
        two_table_col_layout = QHBoxLayout()
        conv_capa_layout = QVBoxLayout()
        ws_alloc_layout = QVBoxLayout()

        # Add a table for component-speciic conveyor capacity
        conv_capa_layout.addWidget(QLabel("Component-specific conveyor capacitites:"))
        cc_table = QTableWidget()
        cc_table.setColumnCount(4)
        cc_table.setHorizontalHeaderLabels(["Component name", "Max. quantity", "Quantity step", "Group"])
        cc_table.setColumnWidth(0, 150)
        cc_table.setColumnWidth(1, 80)
        cc_table.setColumnWidth(2, 80)
        cc_table.setColumnWidth(3, 100)
        cc_table.setMinimumHeight(200)
        conv_capa_layout.addWidget(cc_table)
        add_comp_conveyor_btn = QPushButton("Add component-specific conveyor capacity")
        if loaded_conveyor is not None:
            row_position = 0
            for comp_id, capa_spec_dict in loaded_conveyor.max_total_capacity.items():
                cc_table.insertRow(row_position)
                cc_table.setItem(row_position, 0, QTableWidgetItem(comp_id))
                cc_table.setItem(row_position, 1, QTableWidgetItem(str(capa_spec_dict['Max. quantity'])))
                cc_table.setItem(row_position, 2, QTableWidgetItem(str(capa_spec_dict['Quantity step'])))
                cc_table.setItem(row_position, 3, QTableWidgetItem(str(capa_spec_dict['Group'])))
                row_position = row_position + 1
        add_comp_conveyor_btn.clicked.connect(lambda:self.add_cc_row(cc_table, row=None))
        conv_capa_layout.addWidget(add_comp_conveyor_btn)

        # Add a table for workstation allocation
        ws_alloc_layout.addWidget(QLabel("Workstation allocation:"))
        ws_alloc_table = QTableWidget()
        ws_alloc_table.setColumnCount(3)
        ws_alloc_table.setHorizontalHeaderLabels(["Workstation", "Buffer", "At length (m)"])
        ws_alloc_layout.addWidget(ws_alloc_table)
        add_ws_alloc_btn = QPushButton("Add workstation allocation")
        '''
        if loaded_conveyor is not None:
            row_position = 0
            for conv_id, capa_spec_dict in loaded_conveyor.max_total_capacity.items():
                cc_table.insertRow(row_position)
                cc_table.setItem(row_position, 0, QTableWidgetItem(comp_id))
                cc_table.setItem(row_position, 1, QTableWidgetItem(str(capa_spec_dict['Max. quantity'])))
                cc_table.setItem(row_position, 2, QTableWidgetItem(str(capa_spec_dict['Quantity step'])))
                cc_table.setItem(row_position, 3, QTableWidgetItem(str(capa_spec_dict['Group'])))
                row_position = row_position + 1
        '''
        add_ws_alloc_btn.clicked.connect(lambda:self.add_ws_alloc_row(ws_alloc_table, row=None))
        ws_alloc_layout.addWidget(add_ws_alloc_btn)

        two_table_col_layout.addLayout(conv_capa_layout)
        two_table_col_layout.addLayout(ws_alloc_layout)
        section_layout.addLayout(two_table_col_layout)

        # Wrap the section layout in a QWidget and add it to the scroll layout
        section_widget = QWidget()
        section_widget.setLayout(section_layout)
        self.conveyor_scroll_layout.addWidget(section_widget)
        # Force update the scroll area
        self.conveyor_scroll_layout.parentWidget().update()
        print("Conveyor section added!")  # Debugging line

    def open_conveyors(self):
        conveyor_edit_dialog = QDialog()
        conveyor_edit_dialog.setWindowTitle(f"Conveyor connections and properties")
        conveyor_edit_dialog.setMinimumSize(1024, 700)
        conveyor_edit_layout = QVBoxLayout()
        conveyor_label = QLabel("Conveyors:")
        conveyor_label.setMinimumWidth(200)
        conveyor_edit_layout.addWidget(conveyor_label)
        add_conveyor_btn = QPushButton("Add conveyor")
        add_conveyor_btn.clicked.connect(lambda:self.add_conveyor(None))
        conveyor_edit_layout.addWidget(add_conveyor_btn)
        conveyor_scroll_area = QScrollArea()
        conveyor_scroll_area.setWidgetResizable(True)
        conveyor_scroll_content = QWidget()
        self.conveyor_scroll_layout = QVBoxLayout(conveyor_scroll_content)
        conveyor_scroll_area.setWidget(conveyor_scroll_content)
        conveyor_edit_layout.addWidget(conveyor_scroll_area)

        def load_conveyor_data():
            if main_window.production_resources_tab.production_system.conveyors:
                for conv_id, conv_obj in main_window.production_resources_tab.production_system.conveyors.items():
                    self.add_conveyor(loaded_conveyor=conv_obj)

        load_conveyor_data()

        def save_conveyor_data():
            for conv_section_idx in range(self.conveyor_scroll_layout.count()):
                conv_id = self.conveyor_scroll_layout.itemAt(conv_section_idx).widget().layout().itemAt(0).widget().text()
                conv_len = float(self.conveyor_scroll_layout.itemAt(conv_section_idx).widget().layout().itemAt(1).layout().itemAt(1).widget().text())
                conv_speed = float(self.conveyor_scroll_layout.itemAt(conv_section_idx).widget().layout().itemAt(2).layout().itemAt(1).widget().text())
                conv_sync = self.conveyor_scroll_layout.itemAt(conv_section_idx).widget().layout().itemAt(3).widget().isChecked()
                conv_usowe = self.conveyor_scroll_layout.itemAt(conv_section_idx).widget().layout().itemAt(4).widget().isChecked()
                conv_dcc = self.conveyor_scroll_layout.itemAt(conv_section_idx).widget().layout().itemAt(5).widget().isChecked()
                two_table_col_layout = self.conveyor_scroll_layout.itemAt(conv_section_idx).widget().layout().itemAt(6).layout()
                conv_capa_layout = two_table_col_layout.itemAt(0)
                conv_capa_table = conv_capa_layout.itemAt(1).widget()
                max_total_capa_dict = {}
                for row in range(conv_capa_table.rowCount()):
                    row_item = {conv_capa_table.item(row,0).text(): {'Max. quantity': int(conv_capa_table.item(row,1).text()),
                                                              'Quantity step': int(conv_capa_table.item(row,2).text()),
                                                              'Group': conv_capa_table.item(row,3).text()}}
                    max_total_capa_dict.update(row_item)
                # ToDo: conveyor buffer allocation
                ws_alloc_layout = two_table_col_layout.itemAt(1)
                conv_obj = Conveyor(conveyor_id=conv_id, length=conv_len, speed=conv_speed, synchronous=conv_sync, upstream_setup_only_when_empty=conv_usowe,
                                    diff_comp_comb=conv_dcc, max_total_capacity=max_total_capa_dict)
                main_window.production_resources_tab.production_system.conveyors.update({conv_id: conv_obj})  # ToDo: won't work with renaming!

        def accept():
            save_conveyor_data()

        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(accept)
        buttonBox.accepted.connect(conveyor_edit_dialog.accept)
        buttonBox.rejected.connect(conveyor_edit_dialog.reject)
        conveyor_edit_layout.addWidget(buttonBox)
        conveyor_edit_dialog.setLayout(conveyor_edit_layout)
        conveyor_edit_dialog.exec_()

    def start_simulation(self):
        print("Starting Simulation")

    def stop_simulation(self):
        print("Stopping Simulation")

    def pause_simulation(self):
        print("Pausing Simulation")

class UseCaseDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PrOPPlan: load use case")
        self.selected_file = None

        # Layout and widgets
        layout = QVBoxLayout()
        question_layout = QHBoxLayout()

        # Standard question mark icon
        question_icon = self.style().standardIcon(QStyle.SP_MessageBoxQuestion)
        icon_label = QLabel()
        icon_label.setPixmap(question_icon.pixmap(32, 32))
        question_layout.addWidget(icon_label)

        label = QLabel("Do you have a use case file of your production system and want to load it?")
        question_layout.addWidget(label)
        question_layout.addStretch()

        layout.addLayout(question_layout)

        # Buttons layout
        buttons_layout = QHBoxLayout()

        yes_button = QPushButton("Yes")
        no_button = QPushButton("No")

        # Connect buttons to actions
        yes_button.clicked.connect(self.load_file)
        no_button.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(yes_button)
        buttons_layout.addWidget(no_button)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def load_file(self):
        """Opens a file dialog to select a file and stores the selected file path."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select use case file", "", "JSON (*.json);;Text (*.txt);;XML (*.xml);;All Files (*.*)")
        if file_path:
            self.selected_file = file_path
            self.accept()
            return self.selected_file


class QCollapsibleWidget(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        
        self.toggle_button = QPushButton("►")
        self.toggle_button.setFixedWidth(20)
        self.toggle_button.clicked.connect(self.toggle_content)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold")
        
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_area.setLayout(self.content_layout)
        self.content_area.setVisible(False)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self.content_area)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.is_expanded = False
        
    def toggle_content(self):
        self.is_expanded = not self.is_expanded
        self.toggle_button.setText("▼" if self.is_expanded else "►")
        self.content_area.setVisible(self.is_expanded)
        
    def addWidget(self, widget):
        self.content_layout.addWidget(widget)


class ManualPlanningDialog(QDialog):
    def __init__(self, run_id : str, production_system : ProductionSystem, step_count : int, parent=None):
        super().__init__(parent)
        self.production_system = production_system
        self.step_count = step_count
        self.setWindowTitle(f"Simulation control ({run_id})")
        self.setMinimumSize(1200, 800)
        self.showMaximized()
        
        # Main layout
        self.main_layout = QVBoxLayout()

        # Header with step count and timestamp
        self.header_layout = QHBoxLayout()
        
        self.step_label = QLabel(f"Step {step_count}")
        self.step_label.setStyleSheet("font-weight: bold")
        self.header_layout.addWidget(self.step_label)
        
        timestamp_str = QtCore.QDateTime.fromSecsSinceEpoch(production_system.timestamp).toString("dd.MM.yyyy hh:mm")
        self.timestamp_label = QLabel(f"Timestamp: {timestamp_str}")
        self.header_layout.addWidget(self.timestamp_label, alignment=Qt.AlignRight)
        
        self.main_layout.addLayout(self.header_layout)

        # Set stretch ratio for observation group vs lower part (60:40)
        self.obs_group = QGroupBox("Observations")
        self.obs_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.main_layout.addWidget(self.obs_group, stretch=60)

        # Create lower part layout
        self.lower_part_layout = QHBoxLayout()
        self.main_layout.addLayout(self.lower_part_layout, stretch=40)

        # Actions group
        self.actions_group = QGroupBox("Actions") 
        self.actions_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.actions_layout = QVBoxLayout()
        self.actions_group.setLayout(self.actions_layout)

        # Results group
        self.results_group = QGroupBox("Results")
        self.results_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results_layout = QVBoxLayout()
        self.results_group.setLayout(self.results_layout)

        # Buttons to switch between result diagrams
        self.results_buttons_layout = QHBoxLayout()
        self.schedule_btn = QPushButton("Schedule")
        self.utilization_btn = QPushButton("Utilization")
        self.buffers_btn = QPushButton("Buffers")
        self.results_buttons_layout.addWidget(self.schedule_btn)
        self.results_buttons_layout.addWidget(self.utilization_btn)
        self.results_buttons_layout.addWidget(self.buffers_btn)
        self.results_layout.addLayout(self.results_buttons_layout)

        # Stack layout
        self.results_figures_stack = QStackedLayout()


        # Schedule (Gantt) figure (matplotlib)
        #self.schedule_figure = plt.figure(figsize=(16, 8))
        #self.schedule_canvas = FigureCanvas(self.schedule_figure)
        #self.schedule_canvas.setMinimumHeight(400)
        #self.schedule_canvas.setMinimumWidth(800)
        ##self.results_layout.addWidget(self.schedule_canvas)
        #self.results_figures_stack.addWidget(self.schedule_canvas)

        self.schedule_view = QWebEngineView()
        self.results_figures_stack.addWidget(self.schedule_view)

        # Utilization figure (matplotlib)
        #self.utilization_figure = plt.figure(figsize=(16, 8))
        #self.utilization_canvas = FigureCanvas(self.utilization_figure)
        #self.results_figures_stack.addWidget(self.utilization_canvas)

        # Utilization figure (Plotly)
        self.utilization_view = QWebEngineView()
        self.results_figures_stack.addWidget(self.utilization_view)

        # Buffers figure (placeholder)
        #self.buffers_figure = plt.figure(figsize=(16, 8))
        #self.buffers_canvas = FigureCanvas(self.buffers_figure)
        #self.results_figures_stack.addWidget(self.buffers_canvas)

        # Buffers figure (Plotly)
        self.buffers_view = QWebEngineView()
        self.results_figures_stack.addWidget(self.buffers_view)

        self.results_layout.addLayout(self.results_figures_stack)

        self.schedule_btn.clicked.connect(lambda: self.results_figures_stack.setCurrentIndex(0))
        self.utilization_btn.clicked.connect(lambda: self.results_figures_stack.setCurrentIndex(1))
        self.buffers_btn.clicked.connect(lambda: self.results_figures_stack.setCurrentIndex(2))

        # Add groups to lower layout
        self.lower_part_layout.addWidget(self.actions_group, stretch=25)
        self.lower_part_layout.addWidget(self.results_group, stretch=75)
        
        # Observations group
        obs_scroll = QScrollArea()
        obs_scroll.setWidgetResizable(True)
        obs_widget = QWidget()
        obs_layout = QVBoxLayout(obs_widget)
        
        # Workstations section
        ws_section = QCollapsibleWidget("Workstations")
        self.ws_table = QTableWidget()
        self.ws_table.setColumnCount(9)
        self.ws_table.setHorizontalHeaderLabels([
            "Workstation", "Status", "Assigned operations", "Queued ops", "Queued work",
            "Committed operation", "Remaining work",
            "Prod. time ratio", "Setup time ratio"
        ])
        self.ws_table.setRowCount(len(production_system.workstations))
        for row, (ws_id, ws) in enumerate(production_system.workstations.items()):
            self.ws_table.setItem(row, 0, QTableWidgetItem(ws_id))
        # Set column widths
        self.ws_table.setColumnWidth(0, 300)  # Workstation
        self.ws_table.setColumnWidth(1, 300)  # Status
        self.ws_table.setColumnWidth(2, 300)  # Assigned operations
        self.ws_table.setColumnWidth(3, 100)  # Queued ops
        self.ws_table.setColumnWidth(4, 100)  # Queued work (s)
        self.ws_table.setColumnWidth(5, 300)  # Committed operation
        self.ws_table.setColumnWidth(6, 100)  # Remaining work
        self.ws_table.setColumnWidth(7, 100)  # Prod. time ratio
        self.ws_table.setColumnWidth(8, 100)  # Setup time ratio
        ws_section.addWidget(self.ws_table)
        obs_layout.addWidget(ws_section)
        
        # Physical buffers section
        buf_section = QCollapsibleWidget("Physical buffers")
        self.buf_table = QTableWidget()
        self.buf_table.setColumnCount(4)
        self.buf_table.setHorizontalHeaderLabels([
            "Buffer", "Fill level", "Avg. fill level", "Fill level variability"
        ])
        buf_count = sum(len(ws.physical_input_buffers) + len(ws.physical_output_buffers) 
                       for ws in production_system.workstations.values())
        self.buf_table.setRowCount(buf_count)
        row = 0
        for ws_id, ws in production_system.workstations.items():
            for buf_idx, buf in ws.physical_input_buffers.items():
                self.buf_table.setItem(row, 0, QTableWidgetItem(f"{ws_id} : IN : {buf_idx}"))
                row += 1
            for buf_idx, buf in ws.physical_output_buffers.items():
                self.buf_table.setItem(row, 0, QTableWidgetItem(f"{ws_id} : OUT : {buf_idx}"))
                row += 1
        # Set column widths
        self.buf_table.setColumnWidth(0, 300)  # Buffer
        self.buf_table.setColumnWidth(1, 100)  # Fill level
        self.buf_table.setColumnWidth(2, 100)  # Avg. fill level
        self.buf_table.setColumnWidth(3, 120)  # Fill level variability
        buf_section.addWidget(self.buf_table)
        obs_layout.addWidget(buf_section)
        
        # Workers section
        workers_section = QCollapsibleWidget("Workers")
        self.workers_table = QTableWidget()
        self.workers_table.setColumnCount(7)
        self.workers_table.setHorizontalHeaderLabels([
            "Worker", "Location", "Destination", "Status",
            "Prod. time ratio", "Setup time ratio", "Walking time ratio"
        ])
        self.workers_table.setRowCount(len(production_system.workers))
        for row, (worker_id, worker) in enumerate(production_system.workers.items()):
            self.workers_table.setItem(row, 0, QTableWidgetItem(worker_id))
        # Set column width
        self.workers_table.setColumnWidth(0, 300)  # Worker
        self.workers_table.setColumnWidth(1, 300)  # Location
        self.workers_table.setColumnWidth(2, 300)  # Destination
        self.workers_table.setColumnWidth(3, 300)  # Status
        self.workers_table.setColumnWidth(4, 100)  # Prod. time ratio
        self.workers_table.setColumnWidth(5, 100)  # Setup time ratio
        self.workers_table.setColumnWidth(6, 120)  # Walking time ratio
        workers_section.addWidget(self.workers_table)
        obs_layout.addWidget(workers_section)
        
        # Tools section
        tools_section = QCollapsibleWidget("Tools")
        self.tools_table = QTableWidget()
        self.tools_table.setColumnCount(2)
        self.tools_table.setHorizontalHeaderLabels([
            "Tool", "Properties"
        ])
        self.tools_table.setRowCount(len(production_system.tools))
        for row, (tool_id, tool) in enumerate(production_system.tools.items()):
            self.tools_table.setItem(row, 0, QTableWidgetItem(tool_id))
        self.tools_table.setColumnWidth(0, 300)  # Tool
        self.tools_table.setColumnWidth(1, 300)  # Properties
        tools_section.addWidget(self.tools_table)
        obs_layout.addWidget(tools_section)
        
        # Operation timeliness section
        ops_section = QCollapsibleWidget("Operation timeliness")
        self.ops_table = QTableWidget()
        self.ops_table.setColumnCount(4)
        self.ops_table.setHorizontalHeaderLabels([
            "Operation", "Remaining work", "Order deadline in", "Order deadline"
        ])
        op_count = sum(len(order_data['product_progress']) 
                      for order_data in production_system.order_progress.values())
        self.ops_table.setRowCount(op_count)
        row = 0
        for order_id, order_data in production_system.order_progress.items():
            for prod_progress in order_data['product_progress']:
                for op_id, op_data in prod_progress['operation_progress'].items():
                    op_name = f"{op_id} | {prod_progress['product_id']} | {order_id} | {prod_progress['product_instance']}"
                    self.ops_table.setItem(row, 0, QTableWidgetItem(op_name))
                    row += 1
        self.ops_table.setColumnWidth(0, 300)  # Operation
        self.ops_table.setColumnWidth(1, 100)  # Remaining work
        self.ops_table.setColumnWidth(2, 100)  # Order deadline in
        self.ops_table.setColumnWidth(3, 300)  # Order deadline
        ops_section.addWidget(self.ops_table)
        obs_layout.addWidget(ops_section)
        
        obs_scroll.setWidget(obs_widget)
        self.obs_group.setLayout(QVBoxLayout())
        self.obs_group.layout().addWidget(obs_scroll)

        # Legal action vector display and and required action type display
        self.legal_label = QLabel()
        self.actions_layout.addWidget(self.legal_label)
        self.type_label = QLabel()
        self.actions_layout.addWidget(self.type_label)

        # Create a persistent action table
        self.action_table = QTableWidget()
        self.action_table.setColumnCount(3)
        self.action_table.setHorizontalHeaderLabels(["Option", "Action code", "Action explanation"])
        self.actions_layout.addWidget(self.action_table)

        # Schedule group
        self.results_group = QGroupBox("Schedule")
        self.results_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.results_layout = QVBoxLayout()
        self.results_group.setLayout(self.results_layout)
        
        self.setLayout(self.main_layout)

        # Build the initial actions view
        self.update_dialog()

    def advance_simulation_until_decision(self):
        """
        Advances the simulation until the production system returns a non-None required_action_type
        or until it is done.
        Not to confuse with production_system.run_until_decision_point()!
        Here the step counter is also updated to give a sense how much in the production system is happening automatically.
        """
        print('Advancing simulation until next decision point')
        # In this example, we assume that if no action is required, production_system.get_legal_actions()
        # returns only [-1]. Therefore, if that is the case, we automatically advance.
        while not self.production_system.is_done():
            self.step_count += 1
            legal = self.production_system.get_legal_actions()
            if len(legal) == 1 and legal[0] == -1:
                # No decision required at this step; automatically run system.
                # Standard case when there are no alternatives in the material
                # or information flow in the system currently (legal[0] = -1).
                self.production_system.set_action(-1)
            else:
                break  # Next decision point reached.

    def option_clicked(self, selected_action):
        """
        Triggered when one of the action option buttons is clicked.
        It applies the chosen action, processes simulation until the next decision,
        and then updates the Actions group.
        """
        # Apply the chosen action.
        print(f'Chosen action: {self.get_action_explanation(self.production_system, selected_action)}')
        self.production_system.set_action(selected_action)
        print(f'\nAction {selected_action} set successfully')
        # Process the simulation until a new decision is needed.
        self.advance_simulation_until_decision()
        print('Reached a decision point')
        # Update the header (e.g. step count, timestamp) and legal actions.
        self.update_dialog()
        self.update_workstations_table()
        self.update_physical_buffer_table()
        self.update_workers_table()
        self.update_tools_table()
        self.update_ops_table()
        self.update_schedule()
        self.update_utilization_plot()
        self.update_buffer_plot()

    def update_dialog(self):
        """
        Refreshes the header and the Actions group based on the current production system state.
        """
        # Update header information
        self.step_label.setText(f"Step {self.step_count}")
        print('\n>>>>')
        print(f'>>>> Step {self.step_count}')
        print('>>>>\n')
        timestamp_str = QtCore.QDateTime.fromSecsSinceEpoch(self.production_system.timestamp).toString("dd.MM.yyyy hh:mm")
        self.timestamp_label.setText(f"Timestamp: {timestamp_str}")
        print(f"Timestamp: {timestamp_str}")
        
        # Legal actions and action type from production system:
        legal_actions = self.production_system.get_legal_actions()
        self.legal_label.setText(f"Legal action vector: {legal_actions}")
        print(f"Legal action vector: {legal_actions}")
        
        displayed_action_type = (self.production_system.required_action_type.name 
                                 if self.production_system.required_action_type is not None else "None")
        
        self.type_label.setText(f"Required action type: {displayed_action_type}")
        print(f"Required action type: {displayed_action_type}")

        # Update the action table
        self.action_table.setRowCount(0)  # Clear existing rows
        self.action_table.setRowCount(len(legal_actions))
        
        for i, action_code in enumerate(legal_actions):
            # Create the button that displays the option number.
            btn = QPushButton(str(i+1))
            # Use default argument in lambda to capture the current action code.
            btn.clicked.connect(lambda checked, code=action_code: self.option_clicked(code))
            self.action_table.setCellWidget(i, 0, btn)
            self.action_table.setItem(i, 1, QTableWidgetItem(str(action_code)))
            # In a real implementation, compute the explanation based on decoding the action code.
            self.action_table.setItem(i, 2, QTableWidgetItem(self.get_action_explanation(self.production_system, action_code)))
        
        self.action_table.resizeColumnsToContents()
        self.update()  # Force GUI update

    def update_workstations_table(self):
        """
        Updates the Workstations table with current data.
        - "Assigned operations": join of ws.input_operation_buffer.
        - "Committed operation": first element of ws.wip_operations if present.
        - "Remaining work": fetched from production_system.order_progress.
        - "Prod. time ratio" and "Setup time ratio": cumulative time divided by elapsed time.
        """
        elapsed = self.production_system.timestamp - self.production_system.start_timestamp
        if elapsed <= 0:
            elapsed = 1

        for row, (ws_id, ws) in enumerate(self.production_system.workstations.items()):
            # Status
            status = ", ".join([ws.status[i].name for i in range(len(ws.status))]) if ws.status else ""

            # Assigned operations
            assigned = ", ".join([op[0]+'|'+ op[1]+'|'+op[2]+'|'+str(op[3]) for op in ws.input_operation_buffer]) if ws.input_operation_buffer else ""

            # Queued ops (number)
            num_queued_ops = len(ws.input_operation_buffer)

            # Queued work (seconds)
            queued_work_s = 0
            for op in ws.input_operation_buffer:
                op_state = self.production_system.get_operation_state(operation_id=op[0],
                                                                      product_id=op[1],
                                                                      order_id=op[2],
                                                                      instance_idx=op[3])
                queued_work_s += op_state['remaining_work']

            # Committed operations
            #comm_op = ws.wip_operations[0] if ws.wip_operations else ""
            committed = ", ".join([op[0]+'|'+ op[1]+'|'+op[2]+'|'+str(op[3]) for op in ws.wip_operations]) if ws.wip_operations else ""

            # Remaining work
            rem_work = 0
            if committed:
                for op in ws.wip_operations:
                    op_state = self.production_system.get_operation_state(operation_id=op[0],
                                                                      product_id=op[1],
                                                                      order_id=op[2],
                                                                      instance_idx=op[3])
                    rem_work += op_state['remaining_work']

            # Compute ratios
            prod_ratio = ws.busy_time / elapsed if hasattr(ws, "busy_time") else 0.0
            setup_ratio = ws.setup_time / elapsed if hasattr(ws, "setup_time") else 0.0

            # Add values to time series
            # ws.utilization_history.append((self.production_system.timestamp, prod_ratio))

            # Update table
            self.ws_table.setItem(row, 1, QTableWidgetItem(status))
            self.ws_table.setItem(row, 2, QTableWidgetItem(assigned))
            self.ws_table.setItem(row, 3, QTableWidgetItem(str(num_queued_ops)))
            self.ws_table.setItem(row, 4, QTableWidgetItem(str(queued_work_s)))
            self.ws_table.setItem(row, 5, QTableWidgetItem(committed))
            self.ws_table.setItem(row, 6, QTableWidgetItem(str(rem_work)))
            self.ws_table.setItem(row, 7, QTableWidgetItem(f"{prod_ratio:.2f}"))
            self.ws_table.setItem(row, 8, QTableWidgetItem(f"{setup_ratio:.2f}"))

    def update_physical_buffer_table(self):
        """
        Updates the physical buffers table with current data.
        - "Fill level": float value from 0.0 to 1.0 claculated based on buffer size specifications
        - "Avg. fill level": average fill level from simulation start
        - "Fill level variability": variability factor of fill level from simulation start
        """
        row = 0
        for ws_id, ws in self.production_system.workstations.items():
            for buf_idx, buf in list(ws.physical_input_buffers.items()) + list(ws.physical_output_buffers.items()):
                # Fill level
                self.buf_table.setItem(row, 1, QTableWidgetItem(f"{buf.get_fill_level():.2f}"))
                # Avg. fill level
                self.buf_table.setItem(row, 2, QTableWidgetItem(f"{buf.get_average_fill_level():.2f}"))
                # Fill level variability
                self.buf_table.setItem(row, 3, QTableWidgetItem(f"{buf.get_fill_level_variability():.2f}"))
                row += 1

    def update_workers_table(self):
        '''
        Updates the workers table with current data.
        - "Location"
        - "Destination"
        - "Status"
        - "Prod. time ratio"
        - "Setup time ratio"
        - "Walking time ratio"
        '''
        elapsed = self.production_system.timestamp - self.production_system.start_timestamp
        if elapsed <= 0:
            elapsed = 1

        for row, (worker_id, worker) in enumerate(self.production_system.workers.items()):
            location = worker.location
            destination = worker.destination
            status = worker.status.name if worker.status else ""
            prod_ratio = worker.busy_time / elapsed if hasattr(worker, "busy_time") else 0
            setup_ratio = worker.setup_time / elapsed if hasattr(worker, "setup_time") else 0
            walk_ratio = worker.walking_time / elapsed if hasattr(worker, "walking_time") else 0

            # Update table
            self.workers_table.setItem(row, 1, QTableWidgetItem(location))
            self.workers_table.setItem(row, 2, QTableWidgetItem(destination))
            self.workers_table.setItem(row, 3, QTableWidgetItem(status))
            self.workers_table.setItem(row, 4, QTableWidgetItem(f"{prod_ratio:.2f}"))
            self.workers_table.setItem(row, 5, QTableWidgetItem(f"{setup_ratio:.2f}"))
            self.workers_table.setItem(row, 6, QTableWidgetItem(f"{walk_ratio:.2f}"))

    def update_tools_table(self):
        for row, (tool_id, tool) in enumerate(self.production_system.tool_state_tracker.items()):
            self.tools_table.setItem(row, 1, QTableWidgetItem(str(tool)))

    def update_ops_table(self):
        row = 0
        for order_id, order_data in self.production_system.order_progress.items():
            for prod_progress in order_data['product_progress']:
                for op_id, op_data in prod_progress['operation_progress'].items():
                    self.ops_table.setItem(row, 1, QTableWidgetItem(str(op_data['remaining_work'])))
                    self.ops_table.setItem(row, 2, QTableWidgetItem(str(order_data['deadline'] - self.production_system.timestamp)))
                    readable_deadline = datetime.fromtimestamp(order_data['deadline']).strftime(f'%d.%m.%Y %H:%M:%S')
                    self.ops_table.setItem(row, 3, QTableWidgetItem(readable_deadline))
                    row += 1

    def update_schedule(self):
        """
        Updates the Gantt chart in the Schedule group using the current production_system state.
        """

        html = SchedulePlotter.make_gantt_chart(
            production_system=self.production_system
        )
        self.schedule_view.setHtml(html)

        '''
        # Clear the existing figure
        self.schedule_figure.clear()

        # Draw the Gantt chart on the existing figure
        SchedulePlotter.make_gantt_chart(self.production_system, fig=self.schedule_figure)

        # Redraw the canvas
        self.schedule_canvas.draw()
        '''

    def update_utilization_plot(self):
        html = TimeSeriesPlotter.plot_time_series(
            series_dict={ws.workstation_id: ws.utilization_history for ws in self.production_system.workstations.values()},
            ylabel="Utilization",
            title="Workstation Utilization"
        )
        self.utilization_view.setHtml(html)

        '''
        self.utilization_figure.clear()
        TimeSeriesPlotter.plot_time_series(series_dict={ws.workstation_id: ws.utilization_history for ws in self.production_system.workstations.values()},
                                           ylabel="",
                                           title="Utilization",
                                           fig=self.utilization_figure)
        self.utilization_canvas.draw()
        '''

    def update_buffer_plot(self):
        series_dict = {}
        for ws in self.production_system.workstations.values():
            for buf_idx, buf in {**ws.physical_input_buffers, **ws.physical_output_buffers}.items():
                label = f"{ws.workstation_id} : {'IN' if buf.buffer_location==1 else 'OUT'} : {buf.idx1}"
                series_dict[label] = buf.fill_level_history
        html = TimeSeriesPlotter.plot_time_series(
            series_dict=series_dict,
            ylabel="Relative Fill Level",
            title="Buffer Fill Levels"
        )
        self.buffers_view.setHtml(html)

    def get_action_explanation(self, production_system, action):
        '''
        Decodes provided integer action code into a human-readable form.
        '''
        j = action % production_system.action_matrix_n_cols
        i = int((action - j) / production_system.action_matrix_n_cols)
        explanation = ''
        if production_system.required_action_type == ActionType.WORKSTATION_SEQUENCING:
            # workstation --> operation triple or 'skip'
            explanation = production_system.action_matrix_reverse_col_dict[j] + ' --> ' + production_system.action_matrix_reverse_row_dict[i]
        if production_system.required_action_type == ActionType.WORKSTATION_ROUTING:
            # operation triple --> workstation
            explanation = production_system.action_matrix_reverse_row_dict[i] + ' --> ' + production_system.action_matrix_reverse_col_dict[j]
        if production_system.required_action_type == ActionType.TRANSPORT_ROUTING:
            # workstation --> transport machine
            explanation = production_system.action_matrix_reverse_col_dict[j] + ' --> ' + production_system.action_matrix_reverse_row_dict[i]
        if production_system.required_action_type == ActionType.TRANSPORT_SEQUENCING:
            # transport machine --> workstation/inventory or 'skip'
            explanation = production_system.action_matrix_reverse_row_dict[i] + ' --> ' + production_system.action_matrix_reverse_col_dict[j]
        return explanation

class AIOptimizationTab(QWidget):
    def __init__(self):
        super().__init__()

        # Datastructure to store optimization runs
        self.optimization_runs = {}

        self.init_ui()

    def init_ui(self):
        # Create main layout
        layout = QVBoxLayout()
        
        # Add a button to configure new optimization run
        new_run_btn = QPushButton("New optimization run")
        new_run_btn.setFixedWidth(200)
        new_run_btn.clicked.connect(self.show_optimization_wizard)
        layout.addWidget(new_run_btn)

        # Create table widget for optimization runs
        self.runs_table = QTableWidget()
        self.runs_table.setColumnCount(8)
        headers = [
            "ID", 
            "Algorithm", 
            "Observations", 
            "Actions", 
            "Reward",
            "Optimize",
            "Result (reward)",
            "Result (details)"
        ]
        self.runs_table.setHorizontalHeaderLabels(headers)
        
        # Set column widths
        self.runs_table.setColumnWidth(0, 150)  # ID
        self.runs_table.setColumnWidth(1, 100)  # Algorithm
        self.runs_table.setColumnWidth(2, 100)  # Observation space
        self.runs_table.setColumnWidth(3, 100)  # Action space
        self.runs_table.setColumnWidth(4, 100)  # Reward function
        self.runs_table.setColumnWidth(5, 100)  # "Optimize" button
        self.runs_table.setColumnWidth(6, 100)  # Result (reward)
        self.runs_table.setColumnWidth(7, 100)  # Result (details)

        layout.addWidget(self.runs_table)

        # Bottom section with export button
        bottom_layout = QHBoxLayout()
        export_btn = QPushButton("Export .csv protocol")
        bottom_layout.addStretch()
        bottom_layout.addWidget(export_btn)
        
        layout.addLayout(bottom_layout)
        layout.addStretch()
        self.setLayout(layout)

    def show_optimization_wizard(self):
        wizard = OptimizationWizard(self)
        if wizard.exec_() == QWizard.Accepted:
            run_id = wizard.field("run_id")

            # Add new row to the table with configuration
            row_position = self.runs_table.rowCount()
            self.runs_table.insertRow(row_position)
            
            # Set the run ID
            self.runs_table.setItem(row_position, 0, QTableWidgetItem(wizard.field("run_id")))
            
            # Add configure buttons
            for col in [1, 2, 3, 4]:
                btn = QPushButton("Configure")
                if col == 1:  # Algorithm configuration button
                    btn.clicked.connect(lambda checked, row=row_position: self.show_algorithm_config(row))
                if col == 2:  # Observation space configuration button
                    btn.clicked.connect(lambda checked, row=row_position: self.show_observation_space_config(row))
                if col == 3:  # Action space configuration button
                    btn.clicked.connect(lambda checked, row=row_position: self.show_action_space_config(row))
                if col == 4:  # Reward function configuration button
                    btn.clicked.connect(lambda checked, row=row_position: self.show_reward_function_config(row))
                
                self.runs_table.setCellWidget(row_position, col, btn)
            
            # Add "Optimize" button
            optimize_btn = QPushButton("Optimize")
            optimize_btn.clicked.connect(lambda checked, row=row_position: self.run_optimization(row))
            self.runs_table.setCellWidget(row_position, 5, optimize_btn)

            # Set empty results
            self.runs_table.setItem(row_position, 6, QTableWidgetItem("--"))
            details_btn = QPushButton("Details")
            self.runs_table.setCellWidget(row_position, 7, details_btn)

    def show_algorithm_config(self, row):
        # Get run ID from table
        run_id = self.runs_table.item(row, 0).text()

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Algorithm Configuration ({run_id})")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Algorithm selection
        algo_layout = QFormLayout()
        algo_combo = QComboBox()
        algo_combo.addItems(["Manual planning", "RL-MuZero", "Only heuristics"])

        # Set current algorithm if it exists in optimization_runs
        if run_id in self.optimization_runs:
            algo_combo.setCurrentText(self.optimization_runs[run_id]['algorithm'])

        algo_layout.addRow("Algorithm:", algo_combo)
        
        # Stacked widget for parameters
        param_stack = QStackedWidget()

        # Create parameter widgets with saved values
        param_widgets = []  # List of tuples: (algorithm name, widget, {parameter_name: QLineEdit})

        # Manual planning
        manual_widget = QWidget()
        manual_layout = QFormLayout()
        manual_widget.setLayout(manual_layout)
        param_widgets.append(('Manual planning', manual_widget, {}))
        param_stack.addWidget(manual_widget)
        
        # RL-MuZero parameters
        muzero_widget = QWidget()
        muzero_layout = QFormLayout()
        muzero_lr = QLineEdit()
        muzero_df = QLineEdit()
        muzero_na = QLineEdit()
        if run_id in self.optimization_runs and 'parameters' in self.optimization_runs[run_id] and self.optimization_runs[run_id]['algorithm'] == "RL-MuZero":
            saved = self.optimization_runs[run_id]['parameters']
            muzero_lr.setText(saved.get('learning_rate', "0.001"))
            muzero_df.setText(saved.get('discount_factor', "0.99"))
            muzero_na.setText(saved.get('network_architecture', "Default"))
        else:
            muzero_lr.setText("0.001")
            muzero_df.setText("0.99")
            muzero_na.setText("Default")
        muzero_layout.addRow("Learning rate:", muzero_lr)
        muzero_layout.addRow("Discount factor:", muzero_df)
        muzero_layout.addRow("Network architecture:", muzero_na)
        muzero_widget.setLayout(muzero_layout)
        param_widgets.append(('RL-MuZero', muzero_widget, {'learning_rate': muzero_lr,
                                                            'discount_factor': muzero_df,
                                                            'network_architecture': muzero_na}))
        param_stack.addWidget(muzero_widget)
        
        # RL-DQN parameters
        dqn_widget = QWidget()
        dqn_layout = QFormLayout()
        dqn_lr = QLineEdit()
        dqn_epsilon = QLineEdit()
        dqn_buffer = QLineEdit()
        if run_id in self.optimization_runs and 'parameters' in self.optimization_runs[run_id] and self.optimization_runs[run_id]['algorithm'] == "RL-DQN":
            saved = self.optimization_runs[run_id]['parameters']
            dqn_lr.setText(saved.get('learning_rate', "0.001"))
            dqn_epsilon.setText(saved.get('epsilon', "0.1"))
            dqn_buffer.setText(saved.get('buffer_size', "10000"))
        else:
            dqn_lr.setText("0.001")
            dqn_epsilon.setText("0.1")
            dqn_buffer.setText("10000")
        dqn_layout.addRow("Learning rate:", dqn_lr)
        dqn_layout.addRow("Epsilon:", dqn_epsilon)
        dqn_layout.addRow("Buffer size:", dqn_buffer)
        dqn_widget.setLayout(dqn_layout)
        param_widgets.append(('RL-DQN', dqn_widget, {'learning_rate': dqn_lr,
                                                    'epsilon': dqn_epsilon,
                                                    'buffer_size': dqn_buffer}))
        param_stack.addWidget(dqn_widget)
        
        # Heuristic-EDF parameters
        edf_widget = QWidget()
        edf_layout = QFormLayout()
        edf_time = QLineEdit()
        if run_id in self.optimization_runs and 'parameters' in self.optimization_runs[run_id] and self.optimization_runs[run_id]['algorithm'] == "Heuristic-EDF":
            saved = self.optimization_runs[run_id]['parameters']
            edf_time.setText(saved.get('time_window', "24"))
        else:
            edf_time.setText("24")
        edf_layout.addRow("Time window:", edf_time)
        edf_widget.setLayout(edf_layout)
        param_widgets.append(('Heuristic-EDF', edf_widget, {'time_window': edf_time}))
        param_stack.addWidget(edf_widget)
        
        # Heuristic-SPT parameters
        spt_widget = QWidget()
        spt_layout = QFormLayout()
        spt_lookahead = QLineEdit()
        if run_id in self.optimization_runs and 'parameters' in self.optimization_runs[run_id] and self.optimization_runs[run_id]['algorithm'] == "Heuristic-SPT":
            saved = self.optimization_runs[run_id]['parameters']
            spt_lookahead.setText(saved.get('look_ahead', "5"))
        else:
            spt_lookahead.setText("5")
        spt_layout.addRow("Look-ahead:", spt_lookahead)
        spt_widget.setLayout(spt_layout)
        param_widgets.append(('Heuristic-SPT', spt_widget, {'look_ahead': spt_lookahead}))
        param_stack.addWidget(spt_widget)
        
        param_stack.setCurrentIndex(algo_combo.currentIndex())

        # Connect algorithm selection to parameter stack
        algo_combo.currentIndexChanged.connect(param_stack.setCurrentIndex)
        
        layout.addLayout(algo_layout)
        layout.addWidget(param_stack)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            # Save the selected algorithm
            self.optimization_runs[run_id]['algorithm'] = algo_combo.currentText()
            
            # Save the parameters for the selected algorithm
            for algo_name, widget, params in param_widgets:
                if algo_name == algo_combo.currentText():
                    self.optimization_runs[run_id]['parameters'] = {
                        name: field.text() for name, field in params.items()
                    }
            
            # Update the algorithm cell in the table
            self.runs_table.setItem(row, 1, QTableWidgetItem(algo_combo.currentText()))

    def show_observation_space_config(self, row):
        # Get the run ID from the table and the stored observation_space dict
        run_id = self.runs_table.item(row, 0).text()
        stored_obs = self.optimization_runs[run_id]['observation_space']
        
        # Create a new dialog that replicates the ObservationSpaceConfigPage layout
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Observation Space Configuration ({run_id})")
        dialog.resize(600, 500)
        
        # Instantiate the ObservationSpaceConfigPage with the production system.
        # This page populates the raw and aggregated data tree views.
        obs_page = ObservationSpaceConfigPage(production_system=main_window.production_resources_tab.production_system)
        
        # Update raw and aggregated models so that each variable checkbox reflects the stored value.
        for root in [obs_page.raw_data_model.invisibleRootItem(), obs_page.agg_data_model.invisibleRootItem()]:
            for i in range(root.rowCount()):
                var_name = root.child(i, 0).text()
                expose_item = root.child(i, 2)
                if var_name in stored_obs and stored_obs[var_name[1]]:
                    expose_item.setCheckState(Qt.Checked)
                else:
                    expose_item.setCheckState(Qt.Unchecked)
        # Update total entries display
        obs_page.update_total_entries()
        
        # Create dialog layout and add the page and an OK button.
        layout = QVBoxLayout(dialog)
        layout.addWidget(obs_page)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        # Execute dialog and, if accepted, extract the updated observation configuration into optimization_runs.
        if dialog.exec_() == QDialog.Accepted:
            new_obs = {}
            for root in [obs_page.raw_data_model.invisibleRootItem(), obs_page.agg_data_model.invisibleRootItem()]:
                for i in range(root.rowCount()):
                    var_name = root.child(i, 0).text()
                    is_checked = root.child(i, 2).checkState() == Qt.Checked
                    new_obs[var_name] = is_checked
            self.optimization_runs[run_id]['observation_space'] = new_obs
      
    def show_action_space_config(self, row):
        run_id = self.runs_table.item(row, 0).text()
        stored_specs = self.optimization_runs[run_id].get('action_space', {})

        # Create a dialog for action space configuration
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Action Space Configuration ({run_id})")
        dialog.resize(600, 400)

        # Instantiate the ActionSpaceConfigPage (which contains the configuration table)
        action_page = ActionSpaceConfigPage()

        # Load stored data into the table:
        rows = action_page.table.rowCount()
        for i in range(rows):
            # Get decision type from first column
            decision_type = action_page.table.item(i, 0).text()
            # Set the checkbox state in "Direct" column
            direct_checkbox = action_page.table.cellWidget(i, 1)
            if decision_type in stored_specs and stored_specs[decision_type][0]:
                direct_checkbox.setChecked(True)
            else:
                direct_checkbox.setChecked(False)
            # Set the dropdown for "Indirect" column
            indirect_combo = action_page.table.cellWidget(i, 2)
            if decision_type in stored_specs:
                value = stored_specs[decision_type][1]
                index = indirect_combo.findText(value)
                if index != -1:
                    indirect_combo.setCurrentIndex(index)
                else:
                    indirect_combo.setCurrentIndex(0)
            else:
                indirect_combo.setCurrentIndex(0)

        # Set up dialog layout with the page and OK/Cancel buttons
        layout = QVBoxLayout(dialog)
        layout.addWidget(action_page)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        # If accepted, extract the user selections and update optimization_runs
        if dialog.exec_() == QDialog.Accepted:
            new_action = {}
            for i in range(rows):
                decision_type = action_page.table.item(i, 0).text()
                direct_checkbox = action_page.table.cellWidget(i, 1)
                direct_selected = direct_checkbox.isChecked()
                indirect_combo = action_page.table.cellWidget(i, 2)
                indirect_value = indirect_combo.currentText()
                new_action[decision_type] = (direct_selected, indirect_value)
            self.optimization_runs[run_id]['action_space'] = new_action

    def show_reward_function_config(self, row):
        # Get run_id and stored reward function configuration
        run_id = self.runs_table.item(row, 0).text()
        stored_reward = self.optimization_runs[run_id].get('reward_function', {})

        # Create dialog and instantiate RewardFunctionConfigPage
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Reward Function Configuration ({run_id})")
        dialog.resize(600, 400)
        reward_page = RewardFunctionConfigPage()

        # Load stored values into the table
        row_count = reward_page.table.rowCount()
        for i in range(row_count):
            # Column 1: KPI (read-only)
            kpi_item = reward_page.table.item(i, 1)
            kpi_name = kpi_item.text() if kpi_item else ""
            # Column 0: Goal (combo box)
            goal_combo = reward_page.table.cellWidget(i, 0)
            if kpi_name in stored_reward:
                goal_combo.setCurrentText(stored_reward[kpi_name][0])
            else:
                goal_combo.setCurrentIndex(0)
            # Column 2: Scale (QLineEdit)
            scale_line = reward_page.table.cellWidget(i, 2)
            if kpi_name in stored_reward:
                scale_line.setText(str(stored_reward[kpi_name][1]))
            else:
                scale_line.setText("")
            # Column 3: Unit (combo box for rows 0-1, else read-only text)
            if i < 2:
                unit_combo = reward_page.table.cellWidget(i, 3)
                if kpi_name in stored_reward:
                    unit_combo.setCurrentText(stored_reward[kpi_name][2])
                else:
                    unit_combo.setCurrentIndex(0)
            else:
                unit_item = reward_page.table.item(i, 3)
                if kpi_name in stored_reward:
                    unit_item.setText(stored_reward[kpi_name][2])
                else:
                    unit_item.setText("")

        # Set up the dialog layout
        layout = QVBoxLayout(dialog)
        layout.addWidget(reward_page)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        # If dialog accepted, save updates to the optimization run
        if dialog.exec_() == QDialog.Accepted:
            new_reward = {}
            for i in range(row_count):
                kpi_item = reward_page.table.item(i, 1)
                kpi_name = kpi_item.text() if kpi_item else ""
                goal_combo = reward_page.table.cellWidget(i, 0)
                goal = goal_combo.currentText() if goal_combo else ""
                scale_line = reward_page.table.cellWidget(i, 2)
                scale_text = scale_line.text() if scale_line else ""
                try:
                    scale_value = float(scale_text)
                except ValueError:
                    scale_value = 0.0
                if i < 2:
                    unit_combo = reward_page.table.cellWidget(i, 3)
                    unit = unit_combo.currentText() if unit_combo else ""
                else:
                    unit_item = reward_page.table.item(i, 3)
                    unit = unit_item.text() if unit_item else ""
                new_reward[kpi_name] = (goal, scale_value, unit)
            self.optimization_runs[run_id]['reward_function'] = new_reward

    def get_user_choice(self, prompt, options):
        try:
            choice = int(input(f"{prompt} ({'/'.join(map(str, options))}): "))
            if choice in options:
                return choice
            else:
                print("Invalid choice. Please enter a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    def get_unpicklable(self, instance, exception=None, string='', first_only=True):
        """
        Recursively go through all attributes of instance and return a list of whatever
        can't be pickled.

        Set first_only to only print the first problematic element in a list, tuple or
        dict (otherwise there could be lots of duplication).
        """
        problems = []
        if isinstance(instance, tuple) or isinstance(instance, list):
            for k, v in enumerate(instance):
                try:
                    cloudpickle.dumps(v)
                except BaseException as e:
                    problems.extend(self.get_unpicklable(v, e, string + f'[{k}]'))
                    if first_only:
                        break
        elif isinstance(instance, dict):
            for k in instance:
                try:
                    cloudpickle.dumps(k)
                except BaseException as e:
                    problems.extend(self.get_unpicklable(
                        k, e, string + f'[key type={type(k).__name__}]'
                    ))
                    if first_only:
                        break
            for v in instance.values():
                try:
                    cloudpickle.dumps(v)
                except BaseException as e:
                    problems.extend(self.get_unpicklable(
                        v, e, string + f'[val type={type(v).__name__}]'
                    ))
                    if first_only:
                        break
        else:
            for k, v in instance.__dict__.items():
                try:
                    cloudpickle.dumps(v)
                except BaseException as e:
                    problems.extend(self.get_unpicklable(v, e, string + '.' + k))

        # if we get here, it means pickling instance caused an exception (string is not
        # empty), yet no member was a problem (problems is empty), thus instance itself
        # is the problem.
        if string != '' and not problems:
            problems.append(
                string + f" (Type '{type(instance).__name__}' caused: {exception})"
            )

        return problems

    def run_optimization(self, row):
        '''Executes an optimization run according to the provided row of the configuration table'''
        run_id = self.runs_table.item(row, 0).text()
        print(f'\n++++++++ Executing optimization/planning run {run_id} ++++++++\n')

        production_system = main_window.production_resources_tab.production_system

        # Important to call this because OperationNodes
        # in ProductPalette of the ProductionSystem
        # inherit from PyQT QLabels, which aren't
        # serializable by Ray or cloudpickle
        #production_system.make_simulatable()

        # TODO: remove the debug section below if not needed in the future
        # Debug Ray serialization issue

        print(self.get_unpicklable(production_system))
        #import pickle
        #pickle.dumps(production_system)

        #print(production_system.__dict__)
        #print(production_system.__weakref__)
        #print(production_system.__repr__())
        #print(production_system.__str__())

        print(production_system.__class__)

        ray.util.inspect_serializability(production_system)

        import dill
        #dill.detect.trace(True)
        #dill.detect.errors(production_system)
        print(dill.detect.baditems(production_system))
        print(dill.detect.badobjects(production_system))
        print(dill.detect.nestedglobals(production_system.apply_transport_routing_heuristic))
        print(dill.detect.children(production_system, MainWindow))
        print(dill.detect.freevars(production_system))
        print(dill.detect.errors(production_system))
        print(dill.detect.getmodule(production_system))
        print(dill.detect.parents(production_system, MainWindow))

        #with dill.detect.trace("ray_debug.txt", mode="w") as log:
        #    log(dill.detect.errors(production_system))

        # The serialization with Ray essentially fails because of this:
        #cloudpickle.dumps(production_system)

        # End debug Ray serialization issue
        
        # Get optimization run configuration
        algorithm = self.optimization_runs[run_id]['algorithm']
        algo_parameters = self.optimization_runs[run_id]['parameters']
        observation_space_config = self.optimization_runs[run_id]['observation_space']
        action_space_config = self.optimization_runs[run_id]['action_space']
        reward_function_config = self.optimization_runs[run_id]['reward_function']

        # Provide optimization run configuration to the production system object
        production_system.planning_algorithm = algorithm
        production_system.algorithm_parameters = algo_parameters
        production_system.observation_config = observation_space_config
        production_system.action_config = action_space_config
        production_system.reward_config = reward_function_config

        if algorithm == 'Manual planning':
            # Open up a new dialog with human-readable observation and action interface
            step_count = 0
            dialog = ManualPlanningDialog(run_id, production_system, step_count)
            dialog.exec_()

        # Calculate observation shape (flattened)
        observation_dimension = sum([entry[0] for entry in observation_space_config.values() if entry[1]])

        # Calculate action shape (flattened)

        # TODO: Selecting heuristics as actions will require a different action matrix form
        # (additional columns and rows...).
        # Also, if both sequencing and routing at workstations are done using fixed heuristics,
        # big parts of the action matrix become unnecessary.

        action_dimension = production_system.action_matrix_n_rows * production_system.action_matrix_n_cols

        if algorithm == 'RL-MuZero':
            # Prepare MuZeroConfig to override the default config
            # Info can be taken from production system object
            muzero_config = {
                'observation_shape': (1, 1, observation_dimension),
                'action_space': list(range(action_dimension))
            }
            # Call muzero.py train() method, don't forget to hack the __init__ of MuZero class to look for the "game" in simulation.py
            muzero = MuZero(game_name='PrOPPlan', production_system=production_system, config=muzero_config)
            muzero.train() 

        if algorithm == 'Only heuristics':
            raise NotImplementedError()


class OptimizationWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Optimization Run Configuration")
        self.setGeometry(200, 150, 800, 600)
        self.setWizardStyle(QWizard.ModernStyle)
        self.parent = parent

        # Add pages
        self.addPage(AlgorithmConfigPage())
        self.addPage(ObservationSpaceConfigPage(production_system=main_window.production_resources_tab.production_system))
        self.addPage(ActionSpaceConfigPage())
        self.addPage(RewardFunctionConfigPage())

        # Read out top-level inputs without dedicated save buttons
        main_window.read_out_unsaved_inputs()

    # Gets called when the wizard input is accepted to store optimization run config in AIOptimizationTab
    def get_algorithm_parameters(self):
        # Get the algorithm config page (first page)
        algo_page = self.page(0)
        algorithm = algo_page.algo_combo.currentText()
        
        # Get the current parameter widget based on selected algorithm
        param_widget = algo_page.param_stack.widget(algo_page.algo_combo.currentIndex())
        params = {}
        
        if param_widget:
            form_layout = param_widget.layout()
            for i in range(form_layout.rowCount()):
                label_item = form_layout.itemAt(i, QFormLayout.LabelRole)
                field_item = form_layout.itemAt(i, QFormLayout.FieldRole)
                if label_item and field_item:
                    label = label_item.widget().text().replace(":", "").lower().replace(" ", "_")
                    value = field_item.widget().text()
                    params[label] = value
        
        # Get the observation config page (second page)
        obs_page = self.page(1)
        obs_dict = {}

        for root in [obs_page.raw_data_model.invisibleRootItem(),
                     obs_page.agg_data_model.invisibleRootItem()]:
            for i in range(root.rowCount()):
                # Column 0 is the variable name, column 2 is the checkable observable
                var_name = root.child(i, 0).text()
                size_item = int(root.child(i, 1).text())
                is_checked = root.child(i, 2).checkState() == Qt.Checked
                obs_dict[var_name] = (size_item, is_checked)

        # Get the action config page (third page)
        action_page = self.page(2)
        action_dict = {}
        rows = action_page.table.rowCount()
        for row in range(rows):
            # Get decision type from first column (non-editable item)
            decision_type = action_page.table.item(row, 0).text()
            # Get the checkbox for the "Direct" column
            direct_checkbox = action_page.table.cellWidget(row, 1)
            direct_selected = direct_checkbox.isChecked()
            # Get the combo box for the "Indirect" column
            indirect_combo = action_page.table.cellWidget(row, 2)
            indirect_value = indirect_combo.currentText()
            # Populate the dictionary: key is decision type; value is tuple (direct boolean, indirect string)
            action_dict[decision_type] = (direct_selected, indirect_value)

        # RewardFunctionConfigPage is the 4th page
        reward_page = self.page(3)
        reward_dict = {}
        row_count = reward_page.table.rowCount()
        for row in range(row_count):
            # Get KPI name from the non-editable text in the second column
            kpi_name = reward_page.table.item(row, 1).text()
            
            # Get the goal selected in the first column (combo box)
            goal_widget = reward_page.table.cellWidget(row, 0)
            goal = goal_widget.currentText() if goal_widget else ""
            
            # Get the scale value (third column) as float
            scale_widget = reward_page.table.cellWidget(row, 2)
            scale_text = scale_widget.text() if scale_widget else ""
            try:
                scale_value = float(scale_text)
            except ValueError:
                scale_value = 0.0
            
            # Get unit from the last column.
            # For rows with a combo box (first two rows), use that; otherwise, use the cell item's text.
            unit_widget = reward_page.table.cellWidget(row, 3)
            if unit_widget:
                unit = unit_widget.currentText()
            else:
                unit_item = reward_page.table.item(row, 3)
                unit = unit_item.text() if unit_item else ""
            
            reward_dict[kpi_name] = (goal, scale_value, unit)  

        return {
            'algorithm': algorithm,
            'parameters': params,
            'observation_space': obs_dict,
            'action_space': action_dict,
            'reward_function': reward_dict
        }
    
    def accept(self):
        # Get run ID and ensure it's unique
        run_id = self.field("run_id")
        if run_id in self.parent.optimization_runs:
            QMessageBox.warning(self, "Error", "Run ID already exists!")
            return
        
        # Get algorithm configuration
        config = self.get_algorithm_parameters()
        
        # Store in parent's optimization_runs
        self.parent.optimization_runs[run_id] = {
            'algorithm': config['algorithm'],
            'parameters': config['parameters'],
            'observation_space': config['observation_space'],
            'action_space': config['action_space'],
            'reward_function': config['reward_function'],
            'result_reward': None,
            'result_details': None
        }
        
        super().accept()


class AlgorithmConfigPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Algorithm Configuration")
        self.setSubTitle("Input the optimization run ID and algorithm parameters")

        layout = QVBoxLayout()

        # Run ID input
        id_layout = QHBoxLayout()
        id_label = QLabel("Run ID:")
        self.id_input = QLineEdit()
        self.registerField("run_id*", self.id_input)  # Make it mandatory
        id_layout.addWidget(id_label)
        id_layout.addWidget(self.id_input)
        layout.addLayout(id_layout)

        # Algorithm selection
        algo_layout = QHBoxLayout()
        algo_label = QLabel("Algorithm:")
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["Manual planning", "RL-MuZero", "Only heuristics"])
        self.registerField("algorithm", self.algo_combo, "currentText")
        self.algo_combo.currentTextChanged.connect(self.on_algorithm_changed)
        algo_layout.addWidget(algo_label)
        algo_layout.addWidget(self.algo_combo)
        layout.addLayout(algo_layout)

        # Stacked widget for different algorithm parameters
        self.param_stack = QStackedWidget()

        # Manual planning
        manual_widget = QWidget()
        manual_layout = QFormLayout()
        manual_widget.setLayout(manual_layout)
        self.param_stack.addWidget(manual_widget)
        
        # MuZero parameters
        muzero_widget = QWidget()
        muzero_layout = QFormLayout()
        muzero_layout.addRow("Learning rate:", QLineEdit("0.001"))
        muzero_layout.addRow("Discount factor:", QLineEdit("0.99"))
        muzero_layout.addRow("Network architecture:", QLineEdit("Default"))
        muzero_widget.setLayout(muzero_layout)
        self.param_stack.addWidget(muzero_widget)

        # Heuristics
        heuristic_widget = QWidget()
        heuristic_layout = QFormLayout()
        heuristic_widget.setLayout(heuristic_layout)
        self.param_stack.addWidget(heuristic_widget)

        layout.addWidget(self.param_stack)
        self.setLayout(layout)

    def on_algorithm_changed(self, value):
        # Change parameter widget based on selected algorithm
        if value == "Manual planning":
            self.param_stack.setCurrentIndex(0)
        elif value == "RL-MuZero":
            self.param_stack.setCurrentIndex(1)
        elif value == "Only heuristics":
            self.param_stack.setCurrentIndex(2)


class ObservationSpaceConfigPage(QWizardPage):
    def __init__(self, production_system, parent=None):
        super().__init__(parent)
        self.production_system : ProductionSystem = production_system
        self.setTitle(" Observation Space Configuration")
        self.setSubTitle("Configure the observation space parameters")

        # Call make_simulatable of the production system object to prepare correct observation space configuration
        if not self.production_system.is_prepared:
            self.production_system.make_simulatable()
        
        # Main scroll area container
        scroll_area = QScrollArea()
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # First content box: "Raw state variables"
        raw_group = QGroupBox("Raw state variables")
        raw_layout = QVBoxLayout(raw_group)
        # Create a QTreeView to display variables
        self.raw_data_tree_view = QTreeView()
        self.raw_data_model = QStandardItemModel()
        self.raw_data_model.setHorizontalHeaderLabels(["Data", "Number of entries", "Observable"])
        # Create raw data selection with dynamic display of added vector entries of the observation space
        self.populate_raw_data_model(self.production_system, self.raw_data_model.invisibleRootItem(), "ProductionSystem")
        self.raw_data_tree_view.setModel(self.raw_data_model)
        self.raw_data_tree_view.expandAll()
        self.raw_data_tree_view.resizeColumnToContents(0)
        raw_layout.addWidget(self.raw_data_tree_view)
        container_layout.addWidget(raw_group)
        
        # Second content box: "Aggregated state variables"
        agg_group = QGroupBox("Aggregated state variables")
        agg_layout = QVBoxLayout(agg_group)
        self.agg_data_tree_view = QTreeView()
        self.agg_data_model = QStandardItemModel()
        self.agg_data_model.setHorizontalHeaderLabels(["Data", "Number of entries", "Observable"])
        self.populate_agg_data_model(self.production_system, self.agg_data_model.invisibleRootItem(), "ProductionSystem")
        self.agg_data_tree_view.setModel(self.agg_data_model)
        self.agg_data_tree_view.expandAll()
        self.agg_data_tree_view.resizeColumnToContents(0)
        agg_layout.addWidget(self.agg_data_tree_view)
        container_layout.addWidget(agg_group)

        # Observation space size
        size_group = QGroupBox("Observation space size")
        size_layout = QHBoxLayout(size_group)
        size_label = QLabel("Total number of vector entries:")
        self.total_entries_label = QLabel("0")
        self.total_entries_label.setStyleSheet("font-weight: bold")
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.total_entries_label)
        container_layout.addWidget(size_group)
        
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)
        
        # Set the page layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area)

        # Connect the model's itemChanged signal to update the total of vector entries
        self.raw_data_model.itemChanged.connect(self.update_total_entries)
        self.agg_data_model.itemChanged.connect(self.update_total_entries)
        # Initial update in case some items are pre-checked
        self.update_total_entries()
    
    def populate_raw_data_model(self, obj, parent_item, name):
        # Only add these production system attributes as top-level items.
        allowed_vars = list(obj.raw_observation_vector_sizes.keys())
        # allowed_vars = [
        #     'workers', 'worker_pools', 'tool_pools', 'stationary_machines', 'transport_machines',
        #     'workstations', 'product_instructions', 'order_list', 'supply_behaviours', 'inventories',
        #     'distance_matrix', 'order_progress'
        # ]
        for var_name in allowed_vars:
            # Variable name
            name_item = QStandardItem(str(var_name))
            name_item.setEditable(False)
            # Number of vector entries added to the observation space by observing this variable
            size_item = QStandardItem(str(obj.raw_observation_vector_sizes[var_name]))
            # Checkbox for observability
            expose_item = QStandardItem()
            expose_item.setCheckable(True)
            expose_item.setCheckState(Qt.Checked)
            expose_item.setEditable(False)
            parent_item.appendRow([name_item, size_item, expose_item])

    def populate_agg_data_model(self, obj, parent_item, name):
        allowed_vars = list(obj.agg_observation_vector_sizes.keys())
        for var_name in allowed_vars:
            # Variable name
            name_item = QStandardItem(str(var_name))
            name_item.setEditable(False)
            # Number of vector entries added to the observation space by observing this variable
            size_item = QStandardItem(str(obj.agg_observation_vector_sizes[var_name]))
            # Checkbox for observability
            expose_item = QStandardItem()
            expose_item.setCheckable(True)
            expose_item.setCheckState(Qt.Checked)
            expose_item.setEditable(False)
            parent_item.appendRow([name_item, size_item, expose_item])

    def update_total_entries(self, item=None):
        total = 0
        for root in [self.raw_data_model.invisibleRootItem(),
                     self.agg_data_model.invisibleRootItem()]:
            for i in range(root.rowCount()):
                # Column 1 is the number of entries, column 2 is the checkable observable
                size_item = root.child(i, 1)
                expose_item = root.child(i, 2)
                if expose_item.checkState() == Qt.Checked:
                    try:
                        total += int(size_item.text())
                    except ValueError:
                        pass
        self.total_entries_label.setText(str(total))


class ActionSpaceConfigPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Action Space Configuration")
        self.setSubTitle("Configure the action space parameters")
        
        # Create a table with three columns
        self.table = QTableWidget(4, 3)
        self.table.setHorizontalHeaderLabels(["Decision type", "Direct", "Indirect"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Define decision types and dropdown options
        decision_types = [
            "Workstation routing",
            "Workstation sequencing",
            "Transport routing",
            "Transport sequencing"
        ]
        indirect_options = {
            "Workstation routing": ["", "Least queued operations (LQO)", "Least queued and processed operations (LQPO)", "Least queued time (LQT)", "Random"],
            "Workstation sequencing": ["", "FIFO", "Longest processing time (LPT)", "Shortest processing time (SPT)", "Earliest deadline first (EDF)", "Least operations remaining (LOR)", "Most operations remaining (MOR)", "Random"],
            "Transport routing": ["", "Closest transport (CT)", "Least queued transport orders (LQTO)", "Random"],
            "Transport sequencing": ["", "Closest destination (CD)", "FIFO", "Random"]
        }

        # Populate the table rows
        for row, decision in enumerate(decision_types):
            # Decision type (non-editable)
            item = QTableWidgetItem(decision)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item)

            # Direct column: checkbox
            checkbox = QCheckBox()
            # You can set default state if needed, for example:
            # checkbox.setChecked(False)
            self.table.setCellWidget(row, 1, checkbox)

            # Indirect column: combo box with specific options
            combo = QComboBox()
            combo.addItems(indirect_options[decision])
            # Pre-select "Random" if available
            idx = combo.findText("Random")
            if idx != -1:
                combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, 2, combo)

        self.table.resizeColumnsToContents()

        # Add the table to the page layout
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)


class RewardFunctionConfigPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Reward Function Configuration")
        self.setSubTitle("Configure the reward function parameters")
        
        # Create a table with 5 rows and 4 columns
        self.table = QTableWidget(5, 4)
        self.table.setHorizontalHeaderLabels(["Goal", "KPI", "Scale to 1 point", "Unit"])
        self.table.verticalHeader().setVisible(False)
        #self.table.horizontalHeader().setStretchLastSection(True)
        
        # Fixed KPI texts for each row
        kpi_texts = [
            "Mean order lead time",
            "Mean absolute order deadline deviation",
            "Mean productive time ratio of workstations",
            "Mean productive time ratio of workers",
            "Mean buffer fill variability factor"
        ]
        
        # Populate the table rows
        for row in range(5):
            # Column 0: "Goal" - combo box with options
            goal_combo = QComboBox()
            goal_combo.addItems(["Ignore", "Reward", "Punish"])
            self.table.setCellWidget(row, 0, goal_combo)
            
            # Column 1: "KPI" - fixed text, not editable
            kpi_item = QTableWidgetItem(kpi_texts[row])
            kpi_item.setFlags(kpi_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, kpi_item)
            
            # Column 2: "Scale to 1 point" - input field
            scale_edit = QLineEdit()
            scale_edit.setPlaceholderText("e.g., 1.0")
            self.table.setCellWidget(row, 2, scale_edit)
            
            # Column 3: "Unit" - only for rows 0 and 1, add a combo box; else leave empty
            if row in [0, 1]:
                unit_combo = QComboBox()
                unit_combo.addItems(["s", "min", "h", "d"])
                self.table.setCellWidget(row, 3, unit_combo)
            else:
                unit_item = QTableWidgetItem("")
                unit_item.setFlags(unit_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 3, unit_item)
        
        self.table.resizeColumnsToContents()

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout) 


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Set up main window
        self.setWindowTitle("Propplan")
        self.setGeometry(200, 150, 1024, 768)
        self.showMaximized()

        self.use_case_file = None  # path to the use case file

        # Use case file selection dialog
        self.use_case_file = self.show_use_case_file_dialog()

        # Toolbar (menu bar) for various manipulations of general program settings
        #main_toolbar = QToolBar("Main PrOPPlan toolbar")
        #main_toolbar.setIconSize(QSize(16,16))
        #main_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        #self.addToolBar(main_toolbar)
        menu = self.menuBar()

        file_menu = menu.addMenu("File")

        save_use_case_action = QAction("Save use case", self)
        save_use_case_action.triggered.connect(self.onSaveUseCaseButtonClick)
        file_menu.addAction(save_use_case_action)

        load_use_case_action = QAction("Load use case", self)
        load_use_case_action.triggered.connect(self.onLoadUseCaseButtonClick)
        file_menu.addAction(load_use_case_action)

        edit_menu = menu.addMenu("Edit")

        clear_orders_action = QAction("Clear order tab", self)
        clear_orders_action.triggered.connect(self.onClearOrdersButtonClick)
        edit_menu.addAction(clear_orders_action)

        help_menu = menu.addMenu("Help")

        user_manual_action = QAction("User manual", self)
        user_manual_action.triggered.connect(self.onUserManualButtonClick)
        help_menu.addAction(user_manual_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self.onAboutButtonClick)
        help_menu.addAction(about_action)

        # Tab widget to hold all main tabs
        self.tabs = QTabWidget()

        # Production resources tab
        self.production_resources_tab = ProductionResourcesTab()
        self.tabs.addTab(self.production_resources_tab, "Production resources")

        # Production instructions tab
        self.product_instructions_tab = ProductInstructionsTab()
        self.tabs.addTab(self.product_instructions_tab, "Product instructions")

        # Placeholder for other tabs
        self.order_data_tab = OrderDataTab()
        self.tabs.addTab(self.order_data_tab, "Order data")

        # Simulation tab
        self.simulation_tab = SimulationTab()
        self.tabs.addTab(self.simulation_tab, "System simulation")

        # Optimization tab
        self.optimization_tab = AIOptimizationTab()
        self.tabs.addTab(self.optimization_tab, "AI optimization")

        # Set main widget
        self.setCentralWidget(self.tabs)

        # Add a variable to track the previously active tab index and connect the currentChanged signal.
        self.prev_tab_index = self.tabs.currentIndex()
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Read production system (use case) data and populate widgets
        if self.use_case_file:
            self.load_production_system_from_json(path=self.use_case_file)

    def on_tab_changed(self, new_index):
        # If the previously active tab was the OrderDataTab, call complete_order_data()
        if self.tabs.widget(self.prev_tab_index) is self.order_data_tab:
            self.production_resources_tab.production_system.order_list = self.order_data_tab.complete_order_data()
        self.prev_tab_index = new_index

    def show_use_case_file_dialog(self):
        dialog = UseCaseDialog()
        if dialog.exec_() == QDialog.Accepted:
            selected_file = dialog.selected_file
            if selected_file:
                print(f"Selected file: {selected_file}")
                return selected_file
            else:
                print("No file was selected.")
        else:
            print("File selection was skipped.")


    def read_out_unsaved_inputs(self):
        '''
        Used to read inputs in fields on the top level of the GUI which don't have a dedicated save button.
        This should be done before configuring optimization runs and before running them.
        This is also a necessary part of onSaveUseCaseButtonClick().
        '''
        ps = self.production_resources_tab.production_system
        self.product_instructions_tab.clean_up_product_palette()

        # Transform all data except simulation runs into a single JSON file ("use case file")
        # Insert product instructions into production system object
        ps.product_instructions = self.product_instructions_tab.product_palette

        current_product_item = self.product_instructions_tab.product_list_widget.currentItem()
        if current_product_item:
           current_product = current_product_item.text()
        try:
            self.product_instructions_tab.product_palette.product_palette[current_product] = self.product_instructions_tab.graph_panel.connections
            self.product_instructions_tab.product_palette.clean_from_qt()
        except UnboundLocalError:
            print('No products have been selected or input yet.')

        for index in range(self.product_instructions_tab.product_list_widget.count()):
            product_name = self.product_instructions_tab.product_list_widget.item(index).text()
        try:
            if product_name not in self.product_instructions_tab.product_palette.product_palette:
                self.product_instructions_tab.product_palette.product_palette[product_name] = []  # Create an empty graph
        except UnboundLocalError:
            print('No product data have been input yet.')

        # Store all items displayed in Production Resources tab (some are not necessarily stored in a variable, just displayed as list items)
        wc_lw = self.production_resources_tab.resources_grid_layout.itemAtPosition(0,0).layout().itemAt(2).widget()
        ps.worker_capabilities = [wc_lw.item(x).text() for x in range(wc_lw.count())]
        mc_lw = self.production_resources_tab.resources_grid_layout.itemAtPosition(1,1).layout().itemAt(2).widget()
        ps.machine_capabilities = [mc_lw.item(x).text() for x in range(mc_lw.count())]

        # Insert order list into production system object
        ps.order_list = self.order_data_tab.complete_order_data()

        # Record simulation start and end time
        ps.start_timestamp = self.simulation_tab.start_time_input.dateTime().toSecsSinceEpoch()
        ps.end_timestamp = self.simulation_tab.end_time_input.dateTime().toSecsSinceEpoch()
        # Round off seconds
        ps.start_timestamp = ps.start_timestamp - ps.start_timestamp % 60
        ps.end_timestamp = ps.end_timestamp - ps.end_timestamp % 60

        # System-wide parameters
        try:
            ps.walking_speed = float(self.simulation_tab.walking_speed_input.text())
        except ValueError:
            ps.walking_speed = 1.4

        try:
            ps.energy_costs = float(self.simulation_tab.energy_costs_input.text())
        except ValueError:
            ps.energy_costs = 20.0

    def onSaveUseCaseButtonClick(self):
        print("Saving use case...")

        self.read_out_unsaved_inputs()

        # Convert production system object into JSON
        production_system_dict = self.production_resources_tab.production_system.to_dict()

        # Open file system navigator to specify a path to save the use case
        file_path, _ = QFileDialog.getSaveFileName(self, "Specify save path for the use case file", "", "JSON (*.json);;Text (*.txt);;XML (*.xml);;All Files (*.*)")
        with open(file_path, "w") as json_file:
            json.dump(production_system_dict, json_file, indent=4)

    def load_production_system_from_json(self, path):
        """Reads production system data stored in a JSON file on the provided path"""
        # Transform data from use case file into a production system object and populate widgets
        with open(path, "r") as json_file:
            loaded_data = json.load(json_file)
            print(loaded_data)

        # Populate Production Resources tab, write data to production_system object
        for x in loaded_data['worker_capabilities']:
            self.production_resources_tab.add_new_worker_capability(provided_str=x)
        for k,v in loaded_data['workers'].items():
            self.production_resources_tab.add_new_worker(provided_dict=v)
        for k,v in loaded_data['worker_pools'].items():
            self.production_resources_tab.add_new_pool(pool_id=k, provided_list=v)
        for k,v in loaded_data['tools'].items():
            self.production_resources_tab.add_new_tool(provided_dict=v)
        for k,v in loaded_data['tool_pools'].items():
            self.production_resources_tab.add_new_toolpool(pool_id=k, provided_list=v)
        for x in loaded_data['machine_capabilities']:
            self.production_resources_tab.add_new_machine_capability(provided_str=x)
        for k,v in loaded_data['machines'].items():
            self.production_resources_tab.add_new_machine(provided_dict=v)
        for k,v in loaded_data['workstations'].items():
            self.production_resources_tab.add_new_workstation(provided_dict=v)

        # Load product instructions
        product_palette_data = loaded_data["product_instructions"]["product_palette"]
        self.product_instructions_tab.product_palette = ProductPalette(product_palette_data)

        # Track node_uid to make sure that any new nodes will get a unique UID
        max_node_uid = -1

        # For each product, convert the saved connection data (tuples of dicts)
        # into a list of tuples of OperationNode widgets.

        added_uids = []  # list of node uids to avoid duplicate nodes

        def find_node_by_uid_in_con_list(uid, con_list):
            for con in con_list:
                if con[0].node_uid == uid:
                    return con[0]
                if con[1].node_uid == uid:
                    return con[1]
            return None

        for prod_id, connections in product_palette_data.items():
            widget_connections = []
            # Loop over each saved connection for the product.
            for connection in connections:
                # Check if the connection entry is non-empty and has at least two elements.
                if not connection or len(connection) < 2:
                    continue  # Skip this connection if it's empty or incomplete

                # Each valid connection is assumed to be a tuple (or list) of two dictionaries.
                start_data = connection[0]
                end_data = connection[1]

                # Convert saved display_pos (a list) into a QPoint.
                start_pos = QtCore.QPoint(*start_data.get("display_pos", [0, 0]))
                end_pos = QtCore.QPoint(*end_data.get("display_pos", [0, 0]))

                # Create the start OperationNode widget using saved data.
                display_text = start_data["operation_name"] if start_data.get("operation_name") else start_data["node_type"]
                start_node = OperationNode(
                    text=display_text,
                    node_type=start_data.get("node_type", ""),
                    operation_name=start_data.get("operation_name", ""),
                    display_pos=start_pos,
                    node_uid=start_data.get("node_uid", None),
                    components=start_data.get("components", {}),
                    capabilities=start_data.get("capabilities", []),
                    tools=start_data.get("tools", {}),
                    processing_time_value=start_data.get("processing_time_value", 0.0),
                    processing_time_unit=start_data.get("processing_time_unit", ""),
                    output_name=start_data.get("output_name", "")
                )
                if start_node.node_uid > max_node_uid:
                    max_node_uid = start_node.node_uid

                # If a node has already been dropped and added to the workspace, no need to add it again, just need to reference it.
                # Check whether a node with the same UID is already in the connection tuples in the widget_connections
                if start_node.node_uid not in added_uids:
                    added_uids.append(start_node.node_uid)
                    self.product_instructions_tab.graph_panel.add_node(start_node)
                else:
                    # This node UID has already been added to the graph panel
                    start_node = find_node_by_uid_in_con_list(start_node.node_uid, widget_connections)

                # Create the end OperationNode widget using saved data.
                display_text = end_data["operation_name"] if end_data.get("operation_name") else end_data["node_type"]
                end_node = OperationNode(
                    text=display_text,
                    node_type=end_data.get("node_type", ""),
                    operation_name=end_data.get("operation_name", ""),
                    display_pos=end_pos,
                    node_uid=end_data.get("node_uid", None),
                    components=end_data.get("components", {}),
                    capabilities=end_data.get("capabilities", []),
                    tools=end_data.get("tools", {}),
                    processing_time_value=end_data.get("processing_time_value", 0.0),
                    processing_time_unit=end_data.get("processing_time_unit", ""),
                    output_name=end_data.get("output_name", "")
                )
                if end_node.node_uid > max_node_uid:
                    max_node_uid = end_node.node_uid
                
                # If a node has already been dropped and added to the workspace, no need to add it again, just need to reference it.
                # Check whether a node with the same UID is already in the connection tuples in the widget_connections
                if end_node.node_uid not in added_uids:
                    added_uids.append(end_node.node_uid)
                    self.product_instructions_tab.graph_panel.add_node(end_node)
                else:
                    # This node UID has already been added to the graph panel
                    end_node = find_node_by_uid_in_con_list(end_node.node_uid, widget_connections)

                self.product_instructions_tab.graph_panel.node_uid = max_node_uid + 1

                # Mark the nodes as already dropped so their drag behavior is updated.
                start_node.dropped = True
                end_node.dropped = True

                # Place the nodes at their saved positions.
                start_node.move(start_pos)
                end_node.move(end_pos)

                # Set the parent of the nodes to the GraphPanel's workspace.
                start_node.setParent(self.product_instructions_tab.graph_panel.workspace)
                end_node.setParent(self.product_instructions_tab.graph_panel.workspace)

                # Make sure the nodes are visible.
                start_node.show()
                end_node.show()

                # Append the tuple of widget objects to our list.
                widget_connections.append((start_node, end_node))
            
            # Replace the saved (dictionary-based) connections with the widget connections.
            self.product_instructions_tab.product_palette.product_palette[prod_id] = widget_connections

        # Update the product list widget in the left panel.
        self.product_instructions_tab.product_list_widget.clear()
        for prod_id in product_palette_data.keys():
            self.product_instructions_tab.product_list_widget.addItem(prod_id)

        # Optionally, automatically select the first product to trigger update_product_graph_display.
        if self.product_instructions_tab.product_list_widget.count() > 0:
            self.product_instructions_tab.product_list_widget.setCurrentRow(0)
        # self.product_instructions_tab.graph_panel.just_dropped_node = None

        # Finally, update the GraphPanel so that your QPainter-based paintEvent will redraw the arrows,
        # now that the widget connections have been properly created.
        self.product_instructions_tab.graph_panel.update()

        # Also make a reference to product palette for the production system object
        self.production_resources_tab.production_system.product_instructions = self.product_instructions_tab.product_palette

        # Load order data
        order_data = loaded_data['order_list']['order_list']
        order_list = dict()
        for order_id, order_dict in order_data.items():
            order = Order(order_id=order_dict['order_id'],
                          products=order_dict['products'],
                          release_time=order_dict['release_time'],
                          deadline=order_dict['deadline'])
            order_list[order_id] = order
            self.order_data_tab.add_new_order(provided_order=order)

        # Provide loaded order list to the production system object
        self.production_resources_tab.production_system.order_list = OrderList(order_list=order_list)

        # Load simulation parameters (for the SimulationTab)
        self.simulation_tab.start_time_input.setDateTime(QtCore.QDateTime.fromSecsSinceEpoch(loaded_data['start_timestamp']))
        self.simulation_tab.end_time_input.setDateTime(QtCore.QDateTime.fromSecsSinceEpoch(loaded_data['end_timestamp']))

        # Load supply behaviours (a bit complicated...)
        sb_write_dict = {}
        for comp_name, supply_beh in loaded_data['supply_behaviours'].items():
            sb = SupplyBehaviour(component_id=comp_name,
                                 allocation_type=SupplyAllocationType(supply_beh['allocation_type']),
                                 time_unit=supply_beh['time_unit'],
                                 immediate_probability=supply_beh['immediate_probability'],
                                 min=supply_beh['min'],
                                 alpha=supply_beh['alpha'],
                                 beta=supply_beh['beta'])
            sb_write_dict.update({comp_name: sb})
        self.production_resources_tab.production_system.supply_behaviours = sb_write_dict

        # Load inventories
        inv_write_dict = {}
        for inv_id, inv_specs in loaded_data['inventories'].items():
            inv = Inventory(inventory_id=inv_id,
                            diff_comp_comb=inv_specs['diff_comp_comb'],
                            generation_type=InventoryGenerationType(inv_specs['generation_type']),
                            sequence_type=BufferSequenceType(inv_specs['sequence_type'] if inv_specs['sequence_type'] is not None else 3),  # FREE as default if unspecified
                            comp_specific_sizes=inv_specs['comp_specific_sizes'],
                            identical_buffer=inv_specs['identical_buffer'])
            inv_write_dict.update({inv_id: inv})
        self.production_resources_tab.production_system.inventories = inv_write_dict

        # Load distance matrix
        self.production_resources_tab.production_system.distance_matrix = loaded_data['distance_matrix']

        # Set simulation parameters
        self.production_resources_tab.production_system.start_timestamp = loaded_data['start_timestamp']
        self.production_resources_tab.production_system.end_timestamp = loaded_data['end_timestamp']

        # Load system-wide parameters
        self.production_resources_tab.production_system.walking_speed = loaded_data['walking_speed']
        self.production_resources_tab.production_system.energy_costs = loaded_data['energy_costs']

        # Set system-wide parameters in GUI
        self.simulation_tab.walking_speed_input.setText(str(self.production_resources_tab.production_system.walking_speed))
        self.simulation_tab.energy_costs_input.setText(str(self.production_resources_tab.production_system.energy_costs))

    def onLoadUseCaseButtonClick(self):
        print("Load use case")
        use_case_dialog = UseCaseDialog()
        self.use_case_file = use_case_dialog.load_file()
        if self.use_case_file:
            self.load_production_system_from_json(path=self.use_case_file)

    def onClearOrdersButtonClick(self, s):
        print("Clear order tab")

    def onUserManualButtonClick(self, s):
        print("User manual")

    def onAboutButtonClick(self, s):
        print("About")

    def closeEvent(self, event):
        if QMessageBox.Yes == QMessageBox.warning(self,
                                          "Close confirmation",
                                          "You are about to exit Propplan. Save progress?",
                                          QMessageBox.Yes | QMessageBox.No):
            #event.ignore()

            # The behaviour is the same as when the use case is saved from the menu bar, just close the program afterwards
            self.onSaveUseCaseButtonClick()
            event.accept()
        else:
            event.accept()

def main():
    global main_window
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
