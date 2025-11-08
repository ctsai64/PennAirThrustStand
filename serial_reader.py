# serial_reader.py
import serial
import serial.tools.list_ports
import re
from typing import Optional, Dict
import time
from datetime import datetime


class SerialReader:
    """Handles serial communication with Arduino thrust stand."""
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.is_connected = False
        
    @staticmethod
    def list_ports():
        """List available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def connect(self, port: Optional[str] = None):
        """Connect to the Arduino."""
        if port:
            self.port = port
            
        if not self.port:
            raise ValueError("No port specified")
            
        try:
            # Try to close any existing connection first
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                time.sleep(0.5)
            
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=0.2)
            time.sleep(2)  # Wait for Arduino to reset
            # clear any existing startup noise
            try:
                self.serial_conn.reset_input_buffer()
            except Exception:
                pass
            self.is_connected = True
            return True
        except serial.SerialException as e:
            self.is_connected = False
            if "Access is denied" in str(e) or "PermissionError" in str(e):
                raise Exception(f"Port {self.port} is already in use. Close Arduino IDE Serial Monitor or any other program using this port.")
            else:
                raise Exception(f"Failed to connect to {self.port}: {e}")
        except Exception as e:
            self.is_connected = False
            raise Exception(f"Failed to connect: {e}")
    
    def disconnect(self):
        """Disconnect from Arduino."""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.is_connected = False
    
    def read_data(self) -> Optional[Dict[str, float]]:
        """
        Read and parse data from Arduino.
        Returns dict with keys: timestamp (HH:MM:SS.sss), thrust, rpm, temperature, voltage, current
        """
        if not self.is_connected or not self.serial_conn:
            return None
        
        data = {
            'timestamp': None,
            'thrust': None,
            'rpm': None,
            'temperature': None,
            'voltage': None,
            'current': None
        }
        
        try:
            any_line = False
            # Read a few lines and parse values — this collects latest available fields
            for _ in range(10):  # Read up to 10 lines to catch all sensors
                if self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    any_line = True
                    # Normalize and try to parse numeric at the end after colon
                    try:
                        # Parse load cell / thrust
                        if 'Load' in line or 'load' in line:
                            match = re.search(r'[-+]?\d*\.?\d+', line.split(':')[-1])
                            if match:
                                data['thrust'] = float(match.group())
                        # Parse temperature
                        elif 'Temp' in line or 'temp' in line:
                            match = re.search(r'[-+]?\d*\.?\d+', line.split(':')[-1])
                            if match:
                                data['temperature'] = float(match.group())
                        # Parse RPM
                        elif 'RPM' in line or 'rpm' in line:
                            match = re.search(r'[-+]?\d*\.?\d+', line.split(':')[-1])
                            if match:
                                data['rpm'] = float(match.group())
                        # Parse voltage
                        elif 'Voltage' in line or 'voltage' in line:
                            match = re.search(r'[-+]?\d*\.?\d+', line.split(':')[-1])
                            if match:
                                data['voltage'] = float(match.group())
                        # Parse current
                        elif 'Current' in line or 'current' in line:
                            match = re.search(r'[-+]?\d*\.?\d+', line.split(':')[-1])
                            if match:
                                data['current'] = float(match.group())
                    except Exception:
                        # ignore individual line parse errors
                        continue

            # If we parsed at least one line, attach a real clock timestamp (millisecond precision)
            if any_line:
                now = datetime.now()
                data['timestamp'] = now.strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.sss

            return data
            
        except Exception as e:
            print(f"Error reading data: {e}")
            return None
    
    def send_command(self, command: str):
        """Send a command to Arduino."""
        if self.is_connected and self.serial_conn:
            try:
                self.serial_conn.write((command + '\n').encode())
            except Exception:
                pass
