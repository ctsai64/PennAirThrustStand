import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QCheckBox, QPushButton, QComboBox, 
                             QLabel, QGroupBox, QMessageBox, QFileDialog, QLineEdit, 
                             QTabWidget, QListWidget, QTableWidget, QTableWidgetItem)
import os
import glob
from PyQt5.QtCore import QTimer, QPointF
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
        self.setGeometry(100, 100, 1600, 900)
        
        # Serial reader
        self.serial_reader = SerialReader()
        
        # Data storage (keep all points; unbounded growth)
        self.max_points = None
        self.time_data = deque()
        self.thrust_data = deque()
        self.rpm_data = deque()
        self.temperature_data = deque()
        self.voltage_data = deque()
        self.current_data = deque()
        self.power_data = deque()
        # Full history arrays (not truncated)
        self.time_history = []
        self.thrust_history = []
        self.rpm_history = []
        self.temperature_history = []
        self.voltage_history = []
        self.current_history = []
        self.power_history = []
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

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Live tab content
        live_tab = QWidget()
        live_layout = QVBoxLayout()
        live_tab.setLayout(live_layout)

        # Control panel
        control_panel = self.create_control_panel()
        live_layout.addWidget(control_panel)

        # Create horizontal layout for plots and live data
        content_layout = QHBoxLayout()
        
        # Plot area (left side) - use grid for square graphs
        plot_layout = QVBoxLayout()
        
        # Row 1: Thrust and RPM
        row1_layout = QHBoxLayout()
        # Row 2: Temperature and Voltage
        row2_layout = QHBoxLayout()
        # Row 3: Current and Power
        row3_layout = QHBoxLayout()
        
        # Create individual plots with square aspect
        self.thrust_plot = self.create_plot("Thrust (grams)", "g", (255, 0, 0))
        self.rpm_plot = self.create_plot("RPM", "RPM", (0, 255, 0))
        self.temp_plot = self.create_plot("Temperature (°C)", "°C", (0, 0, 255))
        self.voltage_plot = self.create_plot("Voltage (V)", "V", (255, 165, 0))
        self.current_plot = self.create_plot("Current (A)", "A", (255, 0, 255))
        self.power_plot = self.create_plot("Power (W)", "W", (0, 0, 0))
        
        # Arrange plots in grid (2x2 + 1)
        row1_layout.addWidget(self.thrust_plot['widget'])
        row1_layout.addWidget(self.rpm_plot['widget'])
        
        row2_layout.addWidget(self.temp_plot['widget'])
        row2_layout.addWidget(self.voltage_plot['widget'])
        
        row3_layout.addWidget(self.current_plot['widget'])
        row3_layout.addWidget(self.power_plot['widget'])
        
        plot_layout.addLayout(row1_layout)
        plot_layout.addLayout(row2_layout)
        plot_layout.addLayout(row3_layout)
        
        content_layout.addLayout(plot_layout, 3)  # 75% width
        
        # Live data display panel (right side)
        live_data_panel = self.create_live_data_panel()
        content_layout.addWidget(live_data_panel, 1)  # 25% width
        
        live_layout.addLayout(content_layout)

        self.tabs.addTab(live_tab, "Live")

        # History tab
        history_tab = self.create_history_tab()
        self.tabs.addTab(history_tab, "History")
        
        # Store plot references
        self.plots = {
            'thrust': self.thrust_plot,
            'rpm': self.rpm_plot,
            'temperature': self.temp_plot,
            'voltage': self.voltage_plot,
            'current': self.current_plot,
            'power': self.power_plot
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
        
        self.autoscale_btn = QPushButton("Auto-Scale All")
        self.autoscale_btn.clicked.connect(self.autoscale_plots)
        self.autoscale_btn.setMinimumHeight(44)
        self.autoscale_btn.setStyleSheet("font-size: 14pt; padding: 8px 16px;")
        button_layout.addWidget(self.autoscale_btn)
        
        control_layout.addLayout(button_layout)

        # Test metadata inputs
        meta_layout = QVBoxLayout()
        meta_label = QLabel("Test Metadata:")
        meta_layout.addWidget(meta_label)
        self.motor_name_input = QLineEdit()
        self.motor_name_input.setPlaceholderText("Motor name/model")
        meta_layout.addWidget(QLabel("Motor:"))
        meta_layout.addWidget(self.motor_name_input)
        self.prop_type_input = QLineEdit()
        self.prop_type_input.setPlaceholderText("Propeller type/size")
        meta_layout.addWidget(QLabel("Propeller:"))
        meta_layout.addWidget(self.prop_type_input)
        control_layout.addLayout(meta_layout)
        
        # Checkboxes for plot visibility
        checkbox_layout = QVBoxLayout()
        checkbox_label = QLabel("Display Graphs:")
        checkbox_layout.addWidget(checkbox_label)
        
        self.checkboxes = {}
        measurements = ['thrust', 'rpm', 'temperature', 'voltage', 'current', 'power']
        labels = ['Thrust (g)', 'RPM', 'Temperature (°C)', 'Voltage (V)', 'Current (A)', 'Power (W)']
        
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

    def create_history_tab(self):
        """Create the history tab listing past CSV exports with graphs and raw data."""
        tab = QWidget()
        layout = QHBoxLayout()
        tab.setLayout(layout)

        # Left: file list and refresh
        left_layout = QVBoxLayout()
        self.history_refresh_btn = QPushButton("Refresh")
        self.history_refresh_btn.clicked.connect(self.refresh_history_files)
        left_layout.addWidget(self.history_refresh_btn)
        self.history_list = QListWidget()
        self.history_list.currentTextChanged.connect(self.load_history_file)
        left_layout.addWidget(self.history_list)

        layout.addLayout(left_layout, 1)

        # Right: plots and table
        right_layout = QVBoxLayout()

        # Plots
        plots_layout = QVBoxLayout()
        row1 = QHBoxLayout(); row2 = QHBoxLayout(); row3 = QHBoxLayout()
        self.h_thrust_plot = self.create_plot("Thrust (grams)", "g", (255, 0, 0))
        self.h_rpm_plot = self.create_plot("RPM", "RPM", (0, 255, 0))
        self.h_temp_plot = self.create_plot("Temperature (°C)", "°C", (0, 0, 255))
        self.h_voltage_plot = self.create_plot("Voltage (V)", "V", (255, 165, 0))
        self.h_current_plot = self.create_plot("Current (A)", "A", (255, 0, 255))
        self.h_power_plot = self.create_plot("Power (W)", "W", (0, 0, 0))
        row1.addWidget(self.h_thrust_plot['widget']); row1.addWidget(self.h_rpm_plot['widget'])
        row2.addWidget(self.h_temp_plot['widget']); row2.addWidget(self.h_voltage_plot['widget'])
        row3.addWidget(self.h_current_plot['widget']); row3.addWidget(self.h_power_plot['widget'])
        plots_layout.addLayout(row1); plots_layout.addLayout(row2); plots_layout.addLayout(row3)
        right_layout.addLayout(plots_layout, 3)

        # Table
        self.history_table = QTableWidget()
        right_layout.addWidget(self.history_table, 2)

        layout.addLayout(right_layout, 3)

        # Initial scan
        self.refresh_history_files()

        return tab

    def refresh_history_files(self):
        """Scan for thrust_test_*.csv files and list them sorted by modified time."""
        pattern = os.path.join(os.getcwd(), "thrust_test_*.csv")
        files = glob.glob(pattern)
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        self.history_list.clear()
        for path in files:
            self.history_list.addItem(path)

    def load_history_file(self, path):
        """Load a CSV file, parse metadata/header, plot and display data table."""
        if not path:
            return
        times = []
        thrusts = []
        rpms = []
        temps = []
        volts = []
        currents = []
        try:
            with open(path, 'r', newline='') as f:
                reader = csv.reader(f)
                header_found = False
                for row in reader:
                    if not row:
                        continue
                    if not header_found:
                        # Look for the data header row
                        if row[0].strip().lower().startswith('time'):
                            header = row
                            header_found = True
                        # ignore metadata rows gracefully
                        continue
                    # Parse data rows
                    try:
                        t = float(row[0])
                        th = float(row[1])
                        r = float(row[2])
                        te = float(row[3])
                        v = float(row[4])
                        c = float(row[5])
                    except Exception:
                        continue
                    times.append(t); thrusts.append(th); rpms.append(r)
                    temps.append(te); volts.append(v); currents.append(c)
        except Exception as e:
            QMessageBox.critical(self, "History Load Error", str(e))
            return

        # Update plots
        time_array = np.array(times) if len(times) > 0 else np.array([])
        def set_curve(plot, data):
            if len(time_array) > 0 and len(data) == len(time_array):
                plot['curve'].setData(time_array, np.array(data))
                plot['widget'].setXRange(max(0, time_array[0]), time_array[-1], padding=0.02)
            else:
                plot['curve'].setData([], [])
        set_curve(self.h_thrust_plot, thrusts)
        set_curve(self.h_rpm_plot, rpms)
        set_curve(self.h_temp_plot, temps)
        set_curve(self.h_voltage_plot, volts)
        set_curve(self.h_current_plot, currents)
        # Power = Voltage * Current
        powers = []
        if len(volts) == len(currents):
            try:
                powers = (np.array(volts, dtype=float) * np.array(currents, dtype=float)).tolist()
            except Exception:
                powers = []
        set_curve(self.h_power_plot, powers)

        # Update table
        cols = ['Time (s)', 'Thrust (g)', 'RPM', 'Temperature (°C)', 'Voltage (V)', 'Current (A)']
        self.history_table.clear()
        self.history_table.setColumnCount(len(cols))
        self.history_table.setHorizontalHeaderLabels(cols)
        self.history_table.setRowCount(len(times))
        for i in range(len(times)):
            values = [f"{times[i]:.3f}", f"{thrusts[i]:.3f}", f"{rpms[i]:.1f}", f"{temps[i]:.2f}", f"{volts[i]:.3f}", f"{currents[i]:.3f}"]
            for j, val in enumerate(values):
                self.history_table.setItem(i, j, QTableWidgetItem(val))
    
    def create_live_data_panel(self):
        """Create live data display panel."""
        data_group = QGroupBox("Live Data")
        data_layout = QVBoxLayout()
        data_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14pt;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin-top: 10px;
                padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        # Create labels for each measurement
        label_style = """
            font-size: 16pt;
            font-weight: bold;
            padding: 10px;
            border-radius: 5px;
            margin: 5px;
        """
        
        # Thrust
        self.thrust_value_label = QLabel("Thrust: --- g")
        self.thrust_value_label.setStyleSheet(label_style + "background-color: #ffebee; color: #c62828;")
        data_layout.addWidget(self.thrust_value_label)
        
        # RPM
        self.rpm_value_label = QLabel("RPM: --- RPM")
        self.rpm_value_label.setStyleSheet(label_style + "background-color: #e8f5e9; color: #2e7d32;")
        data_layout.addWidget(self.rpm_value_label)
        
        # Temperature
        self.temp_value_label = QLabel("Temp: --- °C")
        self.temp_value_label.setStyleSheet(label_style + "background-color: #e3f2fd; color: #1565c0;")
        data_layout.addWidget(self.temp_value_label)
        
        # Voltage
        self.voltage_value_label = QLabel("Voltage: --- V")
        self.voltage_value_label.setStyleSheet(label_style + "background-color: #fff3e0; color: #e65100;")
        data_layout.addWidget(self.voltage_value_label)
        
        # Current
        self.current_value_label = QLabel("Current: --- A")
        self.current_value_label.setStyleSheet(label_style + "background-color: #f3e5f5; color: #6a1b9a;")
        data_layout.addWidget(self.current_value_label)
        
        # Add spacer
        data_layout.addStretch()
        
        data_group.setLayout(data_layout)
        return data_group
    
    def create_plot(self, title, y_label, color):
        """Create a plot widget."""
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('w')
        plot_widget.setTitle(title, color='k', size='12pt')
        plot_widget.setLabel('left', y_label, color='k')
        plot_widget.setLabel('bottom', 'Time (s)', color='k')
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # Set minimum size for more square appearance
        plot_widget.setMinimumHeight(250)
        plot_widget.setMinimumWidth(400)
        
        # Set time axis to start at 0
        plot_widget.setXRange(0, 10, padding=0)
        
        # Create plot curve
        curve = plot_widget.plot(pen=pg.mkPen(color=color, width=2))

        # Hover crosshair and value label
        vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen((150, 150, 150), style=pg.QtCore.Qt.DotLine))
        hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen((150, 150, 150), style=pg.QtCore.Qt.DotLine))
        value_label = pg.TextItem(color=(0, 0, 0))
        # Hover point marker
        marker = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(color[0], color[1], color[2], 200), pen=pg.mkPen('k', width=1))
        plot_widget.addItem(vline, ignoreBounds=True)
        plot_widget.addItem(hline, ignoreBounds=True)
        plot_widget.addItem(value_label)
        plot_widget.addItem(marker)
        vline.hide(); hline.hide(); value_label.hide(); marker.hide()

        def _on_mouse_moved(pos):
            if not plot_widget.sceneBoundingRect().contains(pos):
                vline.hide(); hline.hide(); value_label.hide(); marker.hide()
                return
            mouse_point = plot_widget.plotItem.vb.mapSceneToView(pos)
            x = mouse_point.x(); y = mouse_point.y()
            x_data, y_data = curve.getData()
            if x_data is None or y_data is None:
                vline.hide(); hline.hide(); value_label.hide(); marker.hide()
                return
            try:
                import numpy as _np
                x_data = _np.asarray(x_data, dtype=float)
                y_data = _np.asarray(y_data, dtype=float)
            except Exception:
                vline.hide(); hline.hide(); value_label.hide(); marker.hide()
                return
            if len(x_data) == 0 or len(x_data) != len(y_data):
                vline.hide(); hline.hide(); value_label.hide(); marker.hide()
                return
            # Find nearest data point by x
            idx = _np.searchsorted(x_data, x)
            cand_indices = [max(0, min(idx, len(x_data) - 1))]
            if idx > 0:
                cand_indices.append(idx - 1)
            # Choose closer by x distance
            i_best = min(cand_indices, key=lambda i: abs(x_data[i] - x))
            px = x_data[i_best]; py = y_data[i_best]
            # Only show if cursor is near the data point (within ~20 px)
            scene_pt = plot_widget.plotItem.vb.mapViewToScene(QPointF(px, py))
            dist = (scene_pt - pos).manhattanLength()
            if dist > 60:
                vline.hide(); hline.hide(); value_label.hide(); marker.hide()
                return
            vline.setPos(px); hline.setPos(py)
            value_label.setText(f"x={px:.3f}, y={py:.3f}")
            value_label.setPos(px, py)
            marker.setData([px], [py])
            vline.show(); hline.show(); value_label.show(); marker.show()

        hover_proxy = pg.SignalProxy(plot_widget.scene().sigMouseMoved, rateLimit=60, slot=lambda evt: _on_mouse_moved(evt[0]))
        
        return {
            'widget': plot_widget,
            'curve': curve,
            'visible': True,
            'vline': vline,
            'hline': hline,
            'label': value_label,
            'marker': marker,
            'hover_proxy': hover_proxy
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
        self.power_data.clear()
        self.time_history = []
        self.thrust_history = []
        self.rpm_history = []
        self.temperature_history = []
        self.voltage_history = []
        self.current_history = []
        self.power_history = []
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
        # Record initial data point at t=0
        self.update_plots()
    
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
        self.time_history.append(current_time)
        
        # Store data
        thrust_val = data.get('thrust', 0) or 0
        rpm_val = data.get('rpm', 0) or 0
        temp_val = data.get('temperature', 0) or 0
        voltage_val = data.get('voltage', 0) or 0
        current_val = data.get('current', 0) or 0
        power_val = voltage_val * current_val
        
        self.thrust_data.append(thrust_val)
        self.rpm_data.append(rpm_val)
        self.temperature_data.append(temp_val)
        self.voltage_data.append(voltage_val)
        self.current_data.append(current_val)
        self.power_data.append(power_val)
        self.thrust_history.append(thrust_val)
        self.rpm_history.append(rpm_val)
        self.temperature_history.append(temp_val)
        self.voltage_history.append(voltage_val)
        self.current_history.append(current_val)
        self.power_history.append(power_val)
        
        # Update live value labels
        self.thrust_value_label.setText(f"Thrust: {thrust_val:.2f} g")
        self.rpm_value_label.setText(f"RPM: {rpm_val:.1f} RPM")
        self.temp_value_label.setText(f"Temp: {temp_val:.1f} °C")
        self.voltage_value_label.setText(f"Voltage: {voltage_val:.2f} V")
        self.current_value_label.setText(f"Current: {current_val:.3f} A")
        
        # Update plots
        time_array = np.array(self.time_data)
        
        if self.plots['thrust']['visible']:
            thrust_array = np.array(self.thrust_data)
            self.plots['thrust']['curve'].setData(time_array, thrust_array)
        
        if self.plots['rpm']['visible']:
            rpm_array = np.array(self.rpm_data)
            self.plots['rpm']['curve'].setData(time_array, rpm_array)
        
        if self.plots['temperature']['visible']:
            temp_array = np.array(self.temperature_data)
            self.plots['temperature']['curve'].setData(time_array, temp_array)
        
        if self.plots['voltage']['visible']:
            volt_array = np.array(self.voltage_data)
            self.plots['voltage']['curve'].setData(time_array, volt_array)
        
        if self.plots['current']['visible']:
            curr_array = np.array(self.current_data)
            self.plots['current']['curve'].setData(time_array, curr_array)
        if self.plots['power']['visible']:
            power_array = np.array(self.power_data)
            self.plots['power']['curve'].setData(time_array, power_array)
        
        # Keep time axis from going negative
        if len(time_array) > 0:
            min_time = max(0, time_array[0])
            max_time = max(10, time_array[-1])
            for plot_name, plot_info in self.plots.items():
                if plot_info['visible']:
                    plot_info['widget'].setXRange(min_time, max_time, padding=0.02)
    
    def toggle_plot(self, measurement, state):
        """Show or hide a plot."""
        is_checked = state == 2  # Qt.Checked
        self.plots[measurement]['visible'] = is_checked
        self.plots[measurement]['widget'].setVisible(is_checked)
    
    def autoscale_plots(self):
        """Auto-scale all visible plots to fit data perfectly."""
        if len(self.time_history) == 0:
            QMessageBox.information(self, "No Data", "No data to scale. Start a test first.")
            return
        
        time_array = np.array(self.time_history)
        min_time = max(0, time_array[0])  # Never go negative
        max_time = time_array[-1]
        
        # Auto-scale each visible plot
        data_map = {
            'thrust': self.thrust_history,
            'rpm': self.rpm_history,
            'temperature': self.temperature_history,
            'voltage': self.voltage_history,
            'current': self.current_history,
            'power': self.power_history
        }
        
        for plot_name, plot_info in self.plots.items():
            if plot_info['visible'] and len(data_map[plot_name]) > 0:
                data_array = np.array(data_map[plot_name])
                
                # Set X range (time) - never negative
                plot_info['widget'].setXRange(min_time, max_time, padding=0.02)
                
                # Set Y range with padding
                min_val = np.min(data_array)
                max_val = np.max(data_array)
                
                # Add 5% padding on Y axis
                if max_val != min_val:
                    y_range = max_val - min_val
                    plot_info['widget'].setYRange(
                        min_val - 0.05 * y_range,
                        max_val + 0.05 * y_range,
                        padding=0
                    )
                else:
                    # If all values are the same, center with fixed range
                    plot_info['widget'].setYRange(min_val - 1, max_val + 1, padding=0)
        
        QMessageBox.information(self, "Auto-Scale", "All plots have been auto-scaled to fit data.")
    
    def export_to_csv(self):
        """Export collected data to CSV file."""
        if len(self.time_history) == 0:
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
                
                # Metadata rows
                writer.writerow(['Motor', self.motor_name_input.text() or ''])
                writer.writerow(['Propeller', self.prop_type_input.text() or ''])
                writer.writerow(["Exported", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow([])
                # Header
                writer.writerow(['Time (s)', 'Thrust (g)', 'RPM', 'Temperature (°C)', 'Voltage (V)', 'Current (A)'])
                
                # Write data rows
                for i in range(len(self.time_history)):
                    writer.writerow([
                        f"{self.time_history[i]:.3f}",
                        f"{self.thrust_history[i]:.3f}",
                        f"{self.rpm_history[i]:.1f}",
                        f"{self.temperature_history[i]:.2f}",
                        f"{self.voltage_history[i]:.3f}",
                        f"{self.current_history[i]:.3f}"
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
