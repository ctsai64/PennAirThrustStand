#include <HX711_ADC.h>
#include <DHT.h>
#include <Servo.h>

// ===============================
// Pin Assignments
// ===============================
const int HX711_dout = 0;
const int HX711_sck  = 1;
const int DHTPIN     = 4;
const int hall       = 5;
const int escPin     = 9;

// ===============================
// Global Variables
// ===============================
volatile unsigned long pulseCount = 0;
unsigned long lastRPMCalc = 0;
float rpm = 0;
const int magnets = 8;
const unsigned long rpmInterval = 1000;

float temperature = 0;

// Throttle control
float throttlePercent = 0.0;  // 0–100%
unsigned long lastThrottleChange = 0;
bool motorRunning = false;

// Auto-procedure state
bool inProcedure = false;
bool rampingDown = false;

// Flags
bool headerPrinted = false;

// ===============================
// Objects
// ===============================
DHT dht(DHTPIN, DHT11);
HX711_ADC LoadCell(HX711_dout, HX711_sck);
Servo esc;

// ===============================
// Function Prototypes
// ===============================
void countPulse();
void calibrate();
void handleSerialInput();
void updateESC();
void changeCalFactor();
void printData();

// ======================================================
// SETUP
// ======================================================
void setup() {
  Serial.begin(9600);
  pinMode(hall, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(hall), countPulse, FALLING);

  dht.begin();
  LoadCell.begin();

  esc.attach(escPin);

  // =========== ESC ARM ===========
  Serial.println("Arming ESC...");
  esc.writeMicroseconds(1000);  
  delay(3000);

  Serial.println("Starting load cell...");
  LoadCell.start(2000, true);

  if (LoadCell.getTareTimeoutFlag() || LoadCell.getSignalTimeoutFlag()) {
    Serial.println("HX711 timeout. Check wiring.");
    while (1);
  }

  LoadCell.setCalFactor(1.0);

  // Calibration process
  calibrate();

  Serial.println("ESC ready.");
  Serial.println("Enter throttle 0–100, 'procedure', 'c' (change cal), or 's' (stop).");
}

// ======================================================
// MAIN LOOP
// ======================================================
void loop() {
  static unsigned long lastPrint = 0;
  const unsigned long serialPrintInterval = 100;

  // Update load cell
  LoadCell.update();

  // Handle PC GUI commands
  if (Serial.available() > 0) handleSerialInput();

  // ============================
  // RPM calculation (every 1 sec)
  // ============================
  if (millis() - lastRPMCalc >= rpmInterval) {
    noInterrupts();
    unsigned long count = pulseCount;
    pulseCount = 0;
    interrupts();

    rpm = (count / (float)magnets) * (60000.0 / rpmInterval);
    temperature = dht.readTemperature();
    lastRPMCalc = millis();
  }

  // ==================================================
  //               AUTO-PROCEDURE LOGIC
  // ==================================================

  // ============= Ramp UP =============
  if (inProcedure && !rampingDown) {
    if (millis() - lastThrottleChange >= 5000) {
      throttlePercent += 5;

      if (throttlePercent >= 100) {
        throttlePercent = 100;
        updateESC();
        Serial.println("Reached 100%, holding...");

        delay(5000);

        rampingDown = true;
        lastThrottleChange = millis();
      } else {
        updateESC();
        lastThrottleChange = millis();
      }
    }
  }

  // ============= Ramp DOWN =============
  if (rampingDown) {
    if (millis() - lastThrottleChange >= 500) {
      throttlePercent -= 5;

      if (throttlePercent <= 0) {
        throttlePercent = 0;
        updateESC();

        // End procedure
        motorRunning = false;
        inProcedure = false;
        rampingDown = false;

        Serial.println("Procedure complete.");
      } else {
        updateESC();
      }

      lastThrottleChange = millis();
    }
  }

  // ==================================================
  // Send Data to GUI
  // ==================================================
  if (millis() - lastPrint >= serialPrintInterval) {
    printData();
    lastPrint = millis();
  }
}

// ======================================================
// INTERRUPT: RPM Pulse Counter
// ======================================================
void countPulse() {
  pulseCount++;
}

// ======================================================
//  Precise ESC Output (fixed PWM!)
// ======================================================
void updateESC() {
  throttlePercent = constrain(throttlePercent, 0.0, 100.0);

  // Linear interpolation, float-accurate
  int signal = (int)(1000 + (throttlePercent / 100.0) * 1000);

  esc.writeMicroseconds(signal);
}

// ======================================================
// Calibration routine
// ======================================================
void calibrate() {
  Serial.println("*** Load Cell Calibration ***");
  Serial.println("Place load cell empty. Send 't' to tare.");

  bool done = false;

  while (!done) {
    LoadCell.update();
    if (Serial.available() > 0 && Serial.read() == 't') {
      LoadCell.tareNoDelay();
    }
    if (LoadCell.getTareStatus()) {
      Serial.println("Tare complete.");
      done = true;
    }
  }

  Serial.println("Place known mass and send its value:");

  float known_mass = 0;
  while (known_mass == 0) {
    if (Serial.available() > 0) {
      known_mass = Serial.parseFloat();
    }
  }

  LoadCell.refreshDataSet();
  float newCal = LoadCell.getNewCalibration(known_mass);
  LoadCell.setCalFactor(newCal);

  Serial.print("Calibration complete. Factor = ");
  Serial.println(newCal);

  Serial.println("***");
}

// ======================================================
// Change calibration factor
// ======================================================
void changeCalFactor() {
  float oldCal = LoadCell.getCalFactor();

  Serial.println("***");
  Serial.print("Current calibration: ");
  Serial.println(oldCal);
  Serial.println("Send new value:");

  float newCal = 0;
  while (newCal == 0) {
    if (Serial.available() > 0) {
      newCal = Serial.parseFloat();
    }
  }

  LoadCell.setCalFactor(newCal);

  Serial.print("New calibration set to: ");
  Serial.println(newCal);
  Serial.println("***");
}

// ======================================================
// Serial Command Handling
// ======================================================
void handleSerialInput() {
  String input = Serial.readStringUntil('\n');
  input.trim();

  if (input.equalsIgnoreCase("s")) {
    throttlePercent = 0;
    updateESC();
    motorRunning = false;
    inProcedure = false;
    rampingDown = false;
    Serial.println("Motor stopped.");
    return;
  }

  if (input.equalsIgnoreCase("procedure")) {
    throttlePercent = 0;
    updateESC();

    motorRunning = true;
    inProcedure = true;
    rampingDown = false;

    lastThrottleChange = millis();

    Serial.println("Starting auto procedure...");
    return;
  }

  if (input.equalsIgnoreCase("c")) {
    changeCalFactor();
    return;
  }

  // Manual throttle input (0–100%)
  float val = input.toFloat();
  if (val >= 0 && val <= 100) {
    throttlePercent = val;
    motorRunning = (val > 0);
    inProcedure = false;
    rampingDown = false;
    updateESC();
    return;
  }
}

// ======================================================
// Print CSV output for GUI
// ======================================================
void printData() {
  float thrust = LoadCell.getData();

  float voltage = analogRead(A0) * (5.0 / 1023.0);
  float current = analogRead(A1) * (5.0 / 1023.0);
  float power   = voltage * current;

  unsigned long ms = millis();

  if (!headerPrinted) {
    Serial.println("time,thrust,rpm,temperature,voltage,current,power,throttle");
    headerPrinted = true;
  }

  Serial.print(ms / 1000.0, 2); Serial.print(",");
  Serial.print(thrust, 2);      Serial.print(",");
  Serial.print(rpm, 1);          Serial.print(",");
  Serial.print(temperature, 1);  Serial.print(",");
  Serial.print(voltage, 2);      Serial.print(",");
  Serial.print(current, 2);      Serial.print(",");
  Serial.print(power, 2);        Serial.print(",");
  Serial.print(throttlePercent, 1);
  Serial.println();
}

