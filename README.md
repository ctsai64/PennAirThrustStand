# Custom Thrust Testing

Use "ThrustTestingAllSensors" code for most up to date program.

This project measures load, motor RPM, voltage, current, and temperture during motor testing.

## Hardware
* HX711 Load Cell Amplifier + Load Cell
* DHT11 Temperature Sensor
* ACS712 30A Current Sensor (We will proably switch this out for a sensor that can take higher current)
* Hall Effect Sensor
* 0–25V Voltage Sensor
* Arduino ESP32

## Wiring Guide

### HX711 Load Cell Amplifier
* VCC -> 5V
* GND -> GND
* DT -> D0
* SCK -> D1

Load Cell Wires:
* Red -> E+
* Black -> E-
* White -> A-
* Green -> A+

### DHT11 Temperature Sensor
* VCC -> 5V
* DATA -> D4
* GND -> GND

### Hall Effect RPM Sensor
* VCC -> 5V
* GND -> GND
* Signal -> D5

### ACS712 Current Sensor
* VCC -> 5V
* GND -> GND
* OUT -> A0

Current Measurement Wiring:
* Power Supply (+) -> Motor (+)
* Power Supply (–) -> ACS712 -> Motor (–)

### Voltage Sensor (0–25V DC)
* VCC -> 5V
* GND -> GND
* OUT -> A2

Voltage Measurement Wiring :
* VIN+ -> Voltage Source Positive
* VIN- -> Voltage Source Ground
