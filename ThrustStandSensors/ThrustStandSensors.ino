// Load cell, temperature sensor, and RPM measurement
#include <HX711_ADC.h>
#include <DHT.h>

const int HX711_dout = 0; // MCU > HX711 dout pin
const int HX711_sck = 1;  // MCU > HX711 sck pin
const int DHTPIN = 4;
const int hall = 5;

volatile unsigned long pulseCount = 0;
unsigned long lastTime = 0;
float rpm = 0;

const int magnets = 8;                // Number of magnets per revolution
const unsigned long interval = 1000;  // Interval to calculate RPM (ms)

float temp;
unsigned long t = 0;

DHT dht(DHTPIN, DHT11);
HX711_ADC LoadCell(HX711_dout, HX711_sck);

void countPulse() {
  pulseCount++;
}

void setup() {
  Serial.begin(9600);
  pinMode(hall, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(hall), countPulse, FALLING);

  dht.begin();
  LoadCell.begin();

  unsigned long stabilizingtime = 2000;
  bool _tare = true;
  delay(10);

  Serial.println("\nStarting...");
  LoadCell.start(stabilizingtime, _tare);

  if (LoadCell.getTareTimeoutFlag() || LoadCell.getSignalTimeoutFlag()) {
    Serial.println("Timeout, check HX711 wiring!");
    while (1);
  } else {
    LoadCell.setCalFactor(1.0); // Default calibration
    Serial.println("Startup complete");
  }

  while (!LoadCell.update());
  calibrate(); // Start calibration
}

void loop() {
  static bool newDataReady = false;
  const unsigned long serialPrintInterval = 1000; // ms between data prints

  // Update load cell
  if (LoadCell.update()) newDataReady = true;

  // Print data if ready and interval elapsed
  if (newDataReady && millis() - t > serialPrintInterval) {
    newDataReady = false;
    t = millis();

    Serial.println();

    // Load cell
    float i = LoadCell.getData();
    Serial.print("Load cell: ");
    Serial.println(i);

    // Temperature
    temp = dht.readTemperature();
    if (!isnan(temp)) {
      Serial.print("Temperature: ");
      Serial.println(temp);
    }

    // RPM
    unsigned long currentTime = millis();
    if (currentTime - lastTime >= interval) {
      noInterrupts();
      unsigned long count = pulseCount;
      pulseCount = 0;
      interrupts();

      rpm = (count / (float)magnets) * (60000.0 / interval);
      Serial.print("RPM: ");
      Serial.println(rpm, 1);

      lastTime = currentTime;
    }
  }

  // Serial commands
  if (Serial.available() > 0) {
    char inByte = Serial.read();
    if (inByte == 't') LoadCell.tareNoDelay();
    else if (inByte == 'r') calibrate();
    else if (inByte == 'c') changeCalFactor();
  }

  if (LoadCell.getTareStatus()) {
    Serial.println("Tare complete");
  }
}

// ---------- Calibration Functions ---------- //

void calibrate() {
  Serial.println("***");
  Serial.println("Start calibration: place load cell level and empty. Send 't' to tare.");

  bool _resume = false;
  while (!_resume) {
    LoadCell.update();
    if (Serial.available() > 0 && Serial.read() == 't')
      LoadCell.tareNoDelay();
    if (LoadCell.getTareStatus()) {
      Serial.println("Tare complete");
      _resume = true;
    }
  }

  Serial.println("Place known mass, then send its weight (e.g. 100.0).");
  float known_mass = 0;
  _resume = false;
  while (!_resume) {
    LoadCell.update();
    if (Serial.available() > 0) {
      known_mass = Serial.parseFloat();
      if (known_mass > 0) {
        Serial.print("Known mass: ");
        Serial.println(known_mass);
        _resume = true;
      }
    }
  }

  LoadCell.refreshDataSet();
  float newCalibrationValue = LoadCell.getNewCalibration(known_mass);
  Serial.print("New calibration value: ");
  Serial.println(newCalibrationValue);
  LoadCell.setCalFactor(newCalibrationValue);

  Serial.println("*** Calibration complete ***");
}

void changeCalFactor() {
  float oldCal = LoadCell.getCalFactor();
  Serial.println("***");
  Serial.print("Current calibration value: ");
  Serial.println(oldCal);
  Serial.println("Send new value (e.g. 696.0):");

  float newCal = 0;
  bool _resume = false;
  while (!_resume) {
    if (Serial.available() > 0) {
      newCal = Serial.parseFloat();
      if (newCal > 0) {
        LoadCell.setCalFactor(newCal);
        Serial.print("New calibration value: ");
        Serial.println(newCal);
        _resume = true;
      }
    }
  }
  Serial.println("Calibration factor updated.");
  Serial.println("***");
}
