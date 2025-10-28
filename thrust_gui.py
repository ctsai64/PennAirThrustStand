import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QCheckBox, QPushButton, QComboBox, 
                             QLabel, QGroupBox, QMessageBox, QFileDialog)
from PyQt5.QtCore import QTimer
import pyqtgraph as pg
from collections import deque
import numpy as np
import csv
from datetime import datetime
from serial_reader import SerialReader


class ThrustStandGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Thrust Stand Monitor")
        self.setGeometry(100, 100, 1400, 900)
        
        # Serial reader
        self.serial_reader = SerialReader()
        
        # Data storage (keep last 500 points)
        self.max_points = 500
        self.time_data = deque(maxlen=self.max_points)
        self.thrust_data = deque(maxlen=self.max_points)
        self.rpm_data = deque(maxlen=self.max_points)
        self.temperature_data = deque(maxlen=self.max_points)
        self.voltage_data = deque(maxlen=self.max_points)
        self.current_data = deque(maxlen=self.max_points)
        self.start_time = 0
        
        # Timer for updating plots
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plots)
        
        # Setup UI
        self.init_ui()
        
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Control panel
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Plot area
        plot_layout = QVBoxLayout()
        
        # Create individual plots
        self.thrust_plot = self.create_plot("Thrust (grams)", "g", (255, 0, 0))
        self.rpm_plot = self.create_plot("RPM", "RPM", (0, 255, 0))
        self.temp_plot = self.create_plot("Temperature (°C)", "°C", (0, 0, 255))
        self.voltage_plot = self.create_plot("Voltage (V)", "V", (255, 255, 0))
        self.current_plot = self.create_plot("Current (A)", "A", (255, 0, 255))
        
        # Add plots to layout
        plot_layout.addWidget(self.thrust_plot['widget'])
        plot_layout.addWidget(self.rpm_plot['widget'])
        plot_layout.addWidget(self.temp_plot['widget'])
        plot_layout.addWidget(self.voltage_plot['widget'])
        plot_layout.addWidget(self.current_plot['widget'])
        
        main_layout.addLayout(plot_layout)
        
        # Store plot references
        self.plots = {
            'thrust': self.thrust_plot,
            'rpm': self.rpm_plot,
            'temperature': self.temp_plot,
            'voltage': self.voltage_plot,
            'current': self.current_plot
        }
        
    def create_control_panel(self):
        """Create the control panel with port selection and checkboxes."""
        control_group = QGroupBox("Controls")
        control_layout = QHBoxLayout()
        
        # Port selection
        port_layout = QVBoxLayout()
        port_label = QLabel("Serial Port:")
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_combo)
        
        refresh_btn = QPushButton("Refresh Ports")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)
        
        control_layout.addLayout(port_layout)
        
        # Connect/Disconnect buttons
        button_layout = QVBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        button_layout.addWidget(self.connect_btn)
        
        self.start_btn = QPushButton("Start Test")
        self.start_btn.clicked.connect(self.start_test)
        self.start_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Test")
        self.stop_btn.clicked.connect(self.stop_test)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)
        
        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.clicked.connect(self.export_to_csv)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        control_layout.addLayout(button_layout)
        
        # Checkboxes for plot visibility
        checkbox_layout = QVBoxLayout()
        checkbox_label = QLabel("Display Graphs:")
        checkbox_layout.addWidget(checkbox_label)
        
        self.checkboxes = {}
        measurements = ['thrust', 'rpm', 'temperature', 'voltage', 'current']
        labels = ['Thrust (g)', 'RPM', 'Temperature (°C)', 'Voltage (V)', 'Current (A)']
        
        for measure, label in zip(measurements, labels):
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.stateChanged.connect(lambda state, m=measure: self.toggle_plot(m, state))
            self.checkboxes[measure] = cb
            checkbox_layout.addWidget(cb)
        
        control_layout.addLayout(checkbox_layout)
        
        # Status label
        status_layout = QVBoxLayout()
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        status_layout.addWidget(self.status_label)
        control_layout.addLayout(status_layout)
        
        control_group.setLayout(control_layout)
        return control_group
    
    def create_plot(self, title, y_label, color):
        """Create a plot widget."""
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('w')
        plot_widget.setTitle(title, color='k', size='12pt')
        plot_widget.setLabel('left', y_label, color='k')
        plot_widget.setLabel('bottom', 'Time (s)', color='k')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Create plot curve
        curve = plot_widget.plot(pen=pg.mkPen(color=color, width=2))
        
        return {
            'widget': plot_widget,
            'curve': curve,
            'visible': True
        }
    
    def refresh_ports(self):
        """Refresh available serial ports."""
        self.port_combo.clear()
        ports = SerialReader.list_ports()
        if ports:
            self.port_combo.addItems(ports)
        else:
            self.port_combo.addItem("No ports available")
    
    def toggle_connection(self):
        """Connect or disconnect from Arduino."""
        if not self.serial_reader.is_connected:
            try:
                port = self.port_combo.currentText()
                if port == "No ports available":
                    QMessageBox.warning(self, "Error", "No serial ports available!")
                    return
                
                self.serial_reader.connect(port)
                self.connect_btn.setText("Disconnect")
                self.start_btn.setEnabled(True)
                self.status_label.setText(f"Status: Connected to {port}")
                self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 12pt;")
                
            except Exception as e:
                QMessageBox.critical(self, "Connection Error", str(e))
        else:
            self.stop_test()
            self.serial_reader.disconnect()
            self.connect_btn.setText("Connect")
            self.start_btn.setEnabled(False)
            self.status_label.setText("Status: Disconnected")
            self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 12pt;")
    
    def start_test(self):
        """Start data acquisition and plotting."""
        # Clear old data
        self.time_data.clear()
        self.thrust_data.clear()
        self.rpm_data.clear()
        self.temperature_data.clear()
        self.voltage_data.clear()
        self.current_data.clear()
        self.start_time = 0
        
        # Enable/disable buttons
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        
        # Start timer (update every 100ms)
        self.timer.start(100)
        self.status_label.setText("Status: Test Running")
        self.status_label.setStyleSheet("color: blue; font-weight: bold; font-size: 12pt;")
    
    def stop_test(self):
        """Stop data acquisition."""
        self.timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.connect_btn.setEnabled(True)
        
        # Enable export if we have data
        if len(self.time_data) > 0:
            self.export_btn.setEnabled(True)
        
        if self.serial_reader.is_connected:
            self.status_label.setText(f"Status: Connected (Test Stopped)")
            self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 12pt;")
    
    def update_plots(self):
        """Read data and update all plots."""
        data = self.serial_reader.read_data()
        
        if data is None:
            return
        
        # Calculate time
        if self.start_time == 0:
            import time
            self.start_time = time.time()
        
        import time
        current_time = time.time() - self.start_time
        self.time_data.append(current_time)
        
        # Store data
        self.thrust_data.append(data.get('thrust', 0) or 0)
        self.rpm_data.append(data.get('rpm', 0) or 0)
        self.temperature_data.append(data.get('temperature', 0) or 0)
        self.voltage_data.append(data.get('voltage', 0) or 0)
        self.current_data.append(data.get('current', 0) or 0)
        
        # Update plots
        time_array = np.array(self.time_data)
        
        if self.plots['thrust']['visible']:
            self.plots['thrust']['curve'].setData(time_array, np.array(self.thrust_data))
        
        if self.plots['rpm']['visible']:
            self.plots['rpm']['curve'].setData(time_array, np.array(self.rpm_data))
        
        if self.plots['temperature']['visible']:
            self.plots['temperature']['curve'].setData(time_array, np.array(self.temperature_data))
        
        if self.plots['voltage']['visible']:
            self.plots['voltage']['curve'].setData(time_array, np.array(self.voltage_data))
        
        if self.plots['current']['visible']:
            self.plots['current']['curve'].setData(time_array, np.array(self.current_data))
    
    def toggle_plot(self, measurement, state):
        """Show or hide a plot."""
        is_checked = state == 2  # Qt.Checked
        self.plots[measurement]['visible'] = is_checked
        self.plots[measurement]['widget'].setVisible(is_checked)
    
    def export_to_csv(self):
        """Export collected data to CSV file."""
        if len(self.time_data) == 0:
            QMessageBox.warning(self, "No Data", "No data to export. Run a test first.")
            return
        
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"thrust_test_{timestamp}.csv"
        
        # Open file dialog
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Test Data",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return  # User cancelled
        
        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['Time (s)', 'Thrust (g)', 'RPM', 'Temperature (°C)', 'Voltage (V)', 'Current (A)'])
                
                # Write data rows
                for i in range(len(self.time_data)):
                    writer.writerow([
                        f"{self.time_data[i]:.3f}",
                        f"{self.thrust_data[i]:.3f}",
                        f"{self.rpm_data[i]:.1f}",
                        f"{self.temperature_data[i]:.2f}",
                        f"{self.voltage_data[i]:.3f}",
                        f"{self.current_data[i]:.3f}"
                    ])
            
            QMessageBox.information(self, "Export Successful", f"Data exported to:\n{filename}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{str(e)}")
    
    def closeEvent(self, event):
        """Clean up when closing the application."""
        if self.serial_reader.is_connected:
            self.serial_reader.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = ThrustStandGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
