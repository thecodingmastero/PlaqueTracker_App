/*
  PlaqueTracker ESP32/Arduino command protocol placeholder.

  The web app currently uses simulated scan data from /api/sensor/start-scan.
  Replace that simulated call with BLE, Serial, or HTTP transport that sends:
    START_SCAN
    STOP_SCAN

  Device response JSON shape:
    {"colorName":"Blue","rgbValue":"#3366FF","estimatedPH":8.2,"confidence":0.91}
*/

bool scanningEnabled = false;

String scanStripColorJson() {
  // TODO: Replace with the real blue/color detection model using sensor RGB values.
  // Example calibration:
  //   blue/purple -> alkaline, green -> neutral, yellow/orange/red -> acidic.
  String colorName = "Blue";
  String rgbValue = "#3366FF";
  float estimatedPH = 8.2;
  float confidence = 0.91;

  return "{\"colorName\":\"" + colorName + "\","
         "\"rgbValue\":\"" + rgbValue + "\","
         "\"estimatedPH\":" + String(estimatedPH, 2) + ","
         "\"confidence\":" + String(confidence, 2) + "}";
}

void handleCommand(String command) {
  command.trim();

  if (command == "START_SCAN") {
    scanningEnabled = true;
    Serial.println(scanStripColorJson());
    return;
  }

  if (command == "STOP_SCAN") {
    scanningEnabled = false;
    Serial.println("{\"status\":\"stopped\"}");
    return;
  }

  Serial.println("{\"status\":\"error\",\"message\":\"unknown command\"}");
}

void setup() {
  Serial.begin(115200);
  Serial.println("{\"status\":\"ready\",\"protocol\":\"PlaqueTracker START_SCAN/STOP_SCAN\"}");
}

void loop() {
  if (Serial.available()) {
    handleCommand(Serial.readStringUntil('\n'));
  }
}
