/*
  PlaqueTracker USB-C only sketch
  Board: Seeed XIAO ESP32-C3 + TCS3200 color sensor

  This sketch does NOT use Wi-Fi. It prints color readings over USB Serial.
  Run tools/arduino_serial_bridge.py on the computer to send readings to Flask.

  Wiring:
    S0  -> D0 / GPIO2
    S1  -> D1 / GPIO3
    S2  -> D2 / GPIO4
    S3  -> D3 / GPIO5
    OUT -> D4 / GPIO6
    LED -> D5 / GPIO7
    VCC -> 3.3V or 5V depending on module support
    GND -> GND
*/

#define S0      D0
#define S1      D1
#define S2      D2
#define S3      D3
#define OUT_PIN D4
#define LED_PIN D5

const uint32_t SETTLE_MS = 40;
const uint32_t MEASURE_MS = 80;
const uint32_t LOOP_DELAY_MS = 500;

// Calibrated from this sensor/strip setup:
//   Red pH 3:    R/B about 3.00, G/min(R,B) about 0.95
//   Orange pH 5: R/B about 2.82-2.96, G/min(R,B) about 1.00
//   Green pH 7:  R/B about 1.41, G/min(R,B) about 1.52
//   Blue pH 9:   R/B about 0.94-1.04, G/min(R,B) about 0.90-0.98
const float GREEN_DOM_MIN = 1.25f;
const float RED_RB_MIN = 2.97f;
const float ORANGE_RB_MIN = 1.80f;
const float BLUE_RB_MAX = 1.20f;

const float RED_PH = 3.0f;
const float ORANGE_PH = 5.0f;
const float GREEN_PH = 7.0f;
const float BLUE_PH = 9.0f;

static inline float absf(float x) {
  return (x < 0) ? -x : x;
}

static inline float clampf(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

float measureFreqHz(uint32_t windowMs) {
  uint32_t start = millis();
  int last = digitalRead(OUT_PIN);
  uint32_t edges = 0;

  while ((millis() - start) < windowMs) {
    int v = digitalRead(OUT_PIN);
    if (last == HIGH && v == LOW) edges++;
    last = v;
  }
  return (edges * 1000.0f) / (float)windowMs;
}

float readChannelHz(bool s2, bool s3) {
  digitalWrite(S2, s2);
  digitalWrite(S3, s3);
  delay(SETTLE_MS);
  return measureFreqHz(MEASURE_MS);
}

float rbRatioFromChannels(float r, float b) {
  return r / (b + 0.001f);
}

float greenDominanceFromChannels(float r, float g, float b) {
  float minRB = (r < b) ? r : b;
  return g / (minRB + 0.001f);
}

float estimateRawPHFromChannels(float r, float g, float b) {
  if (r < 1.0f && g < 1.0f && b < 1.0f) return -1.0f;

  float rbRatio = rbRatioFromChannels(r, b);
  float greenDom = greenDominanceFromChannels(r, g, b);

  if (greenDom >= GREEN_DOM_MIN) {
    float t = clampf((greenDom - GREEN_DOM_MIN) / 0.40f, 0.0f, 1.0f);
    return GREEN_PH - 0.2f + (0.4f * t);
  }

  if (rbRatio >= RED_RB_MIN) {
    float t = clampf((rbRatio - RED_RB_MIN) / 0.15f, 0.0f, 1.0f);
    return 3.4f - (0.6f * t);
  }

  if (rbRatio >= ORANGE_RB_MIN) {
    float t = clampf((rbRatio - ORANGE_RB_MIN) / (RED_RB_MIN - ORANGE_RB_MIN), 0.0f, 1.0f);
    return 5.8f - (1.2f * t);
  }

  if (rbRatio <= BLUE_RB_MAX) {
    float t = clampf((BLUE_RB_MAX - rbRatio) / 0.35f, 0.0f, 1.0f);
    return 8.4f + (1.0f * t);
  }

  return GREEN_PH;
}

float estimatePHFromChannels(float r, float g, float b, const char* label) {
  if (strcmp(label, "NO SIGNAL") == 0) return -1.0f;
  return estimateRawPHFromChannels(r, g, b);
}

const char* classifyPH(float r, float g, float b, float estimatedPH) {
  if (r < 1.0f && g < 1.0f && b < 1.0f) return "NO SIGNAL";
  if (estimatedPH < 6.6f) return "Low pH";
  if (estimatedPH > 7.4f) return "High pH";
  return "Neutral pH";
}

void setup() {
  Serial.begin(115200);
  delay(600);

  pinMode(S0, OUTPUT);
  pinMode(S1, OUTPUT);
  pinMode(S2, OUTPUT);
  pinMode(S3, OUTPUT);
  pinMode(OUT_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);

  digitalWrite(S0, HIGH);
  digitalWrite(S1, LOW);

  Serial.println("PlaqueTracker USB serial sensor starting");
  Serial.println("READY: USB serial sensor output");
}

void loop() {
  float r = readChannelHz(LOW, LOW);
  float g = readChannelHz(HIGH, HIGH);
  float b = readChannelHz(LOW, HIGH);
  int outState = digitalRead(OUT_PIN);
  float rawPH = estimateRawPHFromChannels(r, g, b);
  const char* label = classifyPH(r, g, b, rawPH);
  float pH = estimatePHFromChannels(r, g, b, label);

  Serial.print("t=");
  Serial.print(millis());
  Serial.print("  R=");
  Serial.print(r, 1);
  Serial.print("Hz G=");
  Serial.print(g, 1);
  Serial.print("Hz B=");
  Serial.print(b, 1);
  Serial.print("Hz  R/B=");
  Serial.print(rbRatioFromChannels(r, b), 3);
  Serial.print(" raw_pH=");
  Serial.print(rawPH, 2);
  Serial.print("  G/min(R,B)=");
  Serial.print(greenDominanceFromChannels(r, g, b), 3);
  Serial.print("Hz  OUTstate=");
  Serial.print(outState);
  Serial.print("  => ");
  Serial.print(label);
  Serial.print("  est_pH=");
  Serial.println(pH, 2);

  delay(LOOP_DELAY_MS);
}
