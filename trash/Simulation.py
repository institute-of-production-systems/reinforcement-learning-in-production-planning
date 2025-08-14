from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QFrame, QLabel, QPushButton, QScrollArea
)
from PyQt5.QtCore import Qt
import sys


class SimulationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulation GUI")
        self.setGeometry(50, 50, 800, 600)  # Adjusted size for better layout

        # Main container widget
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Control Panel Block
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.Box | QFrame.Plain)
        control_layout = QHBoxLayout(control_frame)
        control_frame.setFixedHeight(60)  # Fix height
        control_frame.setFixedWidth(780)  # Fix width
       
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.pause_btn = QPushButton("Pause")
        self.final_time_label = QLabel("Final Time:")
        self.final_time_label_display = QLabel("00:00:00")
        self.simulation_time_label = QLabel("Simulation Time:")

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.simulation_time_label)
        control_layout.addWidget(self.final_time_label)

        

        main_layout.addWidget(control_frame)

        # Workstation Block 1
        workstation_frame = QFrame()
        workstation_frame.setFrameStyle(QFrame.Box | QFrame.Plain)
        workstation_frame.setLineWidth(3)
        workstation_layout = QVBoxLayout(workstation_frame)
 
        workstation_label = QLabel("Workstation 1")
        workstation_label.setAlignment(Qt.AlignLeft)
        workstation_layout.addWidget(workstation_label)


        #workstation_layout.addWidget(QLabel("Workstation 1", alignment=Qt.AlignLeft))

        # Create a grid layout for multiple boxes
        grid_layout = QGridLayout()

        # Define the titles for the input operation buffers
        box_titles = [
            "<Input Operation Buffer>",
            "<Processed Operations Order-product-Op>",
            "<Output Operation Buffer>",
            "<Physical Input Buffer>",
            "<Processed Components>",
            "<Physical Output Buffer>",
            "<Worker>",
            "<Machine>",
            "<Tool>",
            "<Start Time>",
            "<Remaining Time>",
            "<End Time>"
        ]

        # Create 12 placeholder boxes arranged in 3 rows of 4 columns
        for i in range(12):
            placeholder_frame = QFrame()
            placeholder_frame.setFrameShape(QFrame.Box)
            #placeholder_frame.setFrameShape(QFrame.NoFrame)  # Removes border
            #placeholder_frame.setStyleSheet("")
            placeholder_frame.setFrameShadow(QFrame.Raised)
            placeholder_layout = QVBoxLayout(placeholder_frame)

            # Set the title for the placeholder using the list
            placeholder_title = QLabel(box_titles[i])
            placeholder_title.setAlignment(Qt.AlignCenter)

            # Add title to placeholder layout
            placeholder_layout.addWidget(placeholder_title)

            # Add the placeholder to the grid layout
            grid_layout.addWidget(placeholder_frame, i // 3, i % 3)  # 4 rows, 3 columns

        # Add the grid layout to the workstation layout
        workstation_layout.addLayout(grid_layout)

        # Add workstation 1 to the main layout
        main_layout.addWidget(workstation_frame)

        # Workstation Block 2
        workstation2_frame = QFrame()
        workstation2_frame.setFrameStyle(QFrame.Box | QFrame.Plain)
        workstation2_frame.setLineWidth(3)
        workstation2_layout = QVBoxLayout(workstation2_frame)

        workstation2_label = QLabel("Workstation 2")
        workstation2_label.setAlignment(Qt.AlignLeft)
        workstation2_layout.addWidget(workstation2_label)

        # Create a grid layout for workstation 2
        grid_layout2 = QGridLayout()

        # Define the titles for the input operation buffers
        box_titles = [
            "<Input Operation Buffer>",
            "<Processed Operations Order-product-Op>",
            "<Output Operation Buffer>",
            "<Physical Input Buffer>",
            "<Processed Components>",
            "<Physical Output Buffer>",
            "<Worker>",
            "<Machine>",
            "<Tool>",
            "<Start Time>",
            "<Remaining Time>",
            "<End Time>"
        ]
        # Create 20 placeholder boxes for workstation 2
        for i in range(12):
            placeholder_frame = QFrame()
            placeholder_frame.setFrameShape(QFrame.Box)
            placeholder_frame.setFrameShadow(QFrame.Raised)
            placeholder_layout = QVBoxLayout(placeholder_frame)
  
            # Add a title for each box
            placeholder_title = QLabel(box_titles[i])
            placeholder_title.setAlignment(Qt.AlignCenter)

            # Add title to placeholder layout
            placeholder_layout.addWidget(placeholder_title)

            # Add the placeholder to the grid layout
            grid_layout2.addWidget(placeholder_frame, i // 3, i % 3)  # 4 rows, 3 columns

        # Add the grid layout to the second workstation layout
        workstation2_layout.addLayout(grid_layout2)

        # Add workstation 2 to the main layout
        main_layout.addWidget(workstation2_frame)

        # Create a scroll area to wrap the entire layout
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        # Create a container for the main layout
        scroll_content = QWidget()
        scroll_content.setLayout(main_layout)

        # Set the scrollable content
        scroll_area.setWidget(scroll_content)

        # Set the scroll area as the central widget
        self.setCentralWidget(scroll_area)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimulationGUI()
    window.show()
    sys.exit(app.exec_())
