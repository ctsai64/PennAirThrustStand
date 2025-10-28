import serial
import serial.tools.list_ports
import re
from typing import Optional, Dict
import time


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
            
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset
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
            self.serial_conn.close()
        self.is_connected = False
    
    def read_data(self) -> Optional[Dict[str, float]]:
        """
        Read and parse data from Arduino.
        Returns dict with keys: thrust, rpm, temperature, voltage, current
        """
        if not self.is_connected or not self.serial_conn:
            return None
        
        data = {
            'thrust': None,
            'rpm': None,
            'temperature': None,
            'voltage': None,
            'current': None
        }
        
        try:
            # Read multiple lines to get all sensor values
            for _ in range(10):  # Read up to 10 lines to catch all sensors
                if self.serial_conn.in_waiting:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    
                    if not line:
                        continue
                    
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
            
            return data
            
        except Exception as e:
            print(f"Error reading data: {e}")
            return None
    
    def send_command(self, command: str):
        """Send a command to Arduino."""
        if self.is_connected and self.serial_conn:
            self.serial_conn.write(command.encode())
