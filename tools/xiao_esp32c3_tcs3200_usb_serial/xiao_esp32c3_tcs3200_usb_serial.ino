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

const float GREEN_DOM_RATIO = 1.15f;
const float WARM_BIAS = 1.10f;
const float COOL_BIAS = 1.10f;
const float YELLOW_RG_CLOSE = 0.10f;
const float YELLOW_BLUE_DROP = 0.80f;
const float NEUTRAL_RB_CLOSE = 0.14f;
const float NEUTRAL_G_FLOOR = 0.80f;
const bool PH_HIGH_WHEN_RB_HIGH = false;
const float RB_RATIO_AT_PH4 = 0.65f;
const float RB_RATIO_AT_PH7 = 0.95f;
const float RB_RATIO_AT_PH10 = 1.35f;
const float LOW_PH_MAX = 6.65f;
const float HIGH_PH_MIN = 7.35f;
const float PH_LOW_SIDE_END = 7.00f;
const float PH_LOW_SIDE_GAIN = 0.45f;
const float PH_HIGH_SIDE_START = 7.20f;
const float PH_HIGH_SIDE_GAIN = 0.42f;
const float NEUTRAL_PH_TARGET = 7.0f;
const float NEUTRAL_PULL = 0.85f;

static inline float absf(float x) {
  return (x < 0) ? -x : x;
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

float estimateRawPHFromChannels(float r, float b) {
  float rbRatio = r / (b + 0.001f);
  float estimated = 7.0f;

  if (PH_HIGH_WHEN_RB_HIGH) {
    if (rbRatio <= RB_RATIO_AT_PH7) {
      float span = RB_RATIO_AT_PH7 - RB_RATIO_AT_PH4;
      estimated = 7.0f - (((RB_RATIO_AT_PH7 - rbRatio) / span) * 3.0f);
    } else {
      float span = RB_RATIO_AT_PH10 - RB_RATIO_AT_PH7;
      estimated = 7.0f + (((rbRatio - RB_RATIO_AT_PH7) / span) * 3.0f);
    }
  } else {
    if (rbRatio >= RB_RATIO_AT_PH7) {
      float span = RB_RATIO_AT_PH10 - RB_RATIO_AT_PH7;
      estimated = 7.0f - (((rbRatio - RB_RATIO_AT_PH7) / span) * 3.0f);
    } else {
      float span = RB_RATIO_AT_PH7 - RB_RATIO_AT_PH4;
      estimated = 7.0f + (((RB_RATIO_AT_PH7 - rbRatio) / span) * 3.0f);
    }
  }
  return estimated;
}

float estimatePHFromChannels(float r, float g, float b, const char* label) {
  if (strcmp(label, "NO SIGNAL") == 0) return -1.0f;

  float rawPH = estimateRawPHFromChannels(r, b);
  float corrected = rawPH;
  if (rawPH < PH_LOW_SIDE_END) {
    corrected = PH_LOW_SIDE_END - ((PH_LOW_SIDE_END - rawPH) * PH_LOW_SIDE_GAIN);
  } else if (rawPH > PH_HIGH_SIDE_START) {
    corrected = PH_HIGH_SIDE_START + ((rawPH - PH_HIGH_SIDE_START) * PH_HIGH_SIDE_GAIN);
  }

  if (strcmp(label, "Neutral pH") == 0) {
    corrected = corrected + ((NEUTRAL_PH_TARGET - corrected) * NEUTRAL_PULL);
  }
  return corrected;
}

const char* classifyPH(float r, float g, float b, float estimatedPH) {
  if (r < 1.0f && g < 1.0f && b < 1.0f) return "NO SIGNAL";

  float rgAvg = (r + g) / 2.0f;
  bool rgClose = (absf(r - g) / (rgAvg + 0.001f)) <= YELLOW_RG_CLOSE;
  bool blueLower = (b <= rgAvg * YELLOW_BLUE_DROP);
  if (rgClose && blueLower) return "pH unclear";

  if (estimatedPH <= LOW_PH_MAX) return "Low pH";
  if (estimatedPH >= HIGH_PH_MIN) return "High pH";
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
  float rawPH = estimateRawPHFromChannels(r, b);
  const char* label = classifyPH(r, g, b, rawPH);
  float pH = estimatePHFromChannels(r, g, b, label);
  float minRB = (r < b) ? r : b;

  Serial.print("t=");
  Serial.print(millis());
  Serial.print("  R=");
  Serial.print(r, 1);
  Serial.print("Hz G=");
  Serial.print(g, 1);
  Serial.print("Hz B=");
  Serial.print(b, 1);
  Serial.print("Hz  R/B=");
  Serial.print(r / (b + 0.001f), 3);
  Serial.print(" raw_pH=");
  Serial.print(rawPH, 2);
  Serial.print("  G/min(R,B)=");
  Serial.print(g / (minRB + 0.001f), 3);
  Serial.print("Hz  OUTstate=");
  Serial.print(outState);
  Serial.print("  => ");
  Serial.print(label);
  Serial.print("  est_pH=");
  Serial.println(pH, 2);

  delay(LOOP_DELAY_MS);
}
