/*
 * Phantom Drain Appliance Profiler - ESP32 firmware (Arduino core)
 *
 * Wiring (ESP32 DevKit WROOM-32):
 *   OLED SSD1306 0.96" I2C : SDA -> GPIO21, SCL -> GPIO22, VCC -> 3V3, GND -> GND
 *   10K potentiometer      : middle pin -> GPIO34, outer pins -> 3V3 and GND
 *   Green LED (active)     : GPIO25 -> 220R -> LED -> GND
 *   Amber LED (standby)    : GPIO26 -> 220R -> LED -> GND
 *   Red LED (phantom alert): GPIO27 -> 220R -> LED -> GND
 *
 * The potentiometer simulates the power level that a current clamp (e.g. SCT-013
 * on ADC1) would report. To use a real sensor, replace readPowerW().
 *
 * Libraries: Adafruit SSD1306, Adafruit GFX (Library Manager).
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
// IP of the computer running the FastAPI backend
const char* SERVER_URL = "http://192.168.1.10:8000/api/readings";
const char* APPLIANCE = "ESP32 Prototype";

const int POT_PIN = 34, LED_ACTIVE = 25, LED_STANDBY = 26, LED_ALERT = 27;
const float MAX_W = 120.0;     // potentiometer full scale
const float OFF_W = 2.0;       // same thresholds as the backend
const float ACTIVE_W = 15.0;
const unsigned long PERIOD_MS = 2000;

Adafruit_SSD1306 oled(128, 64, &Wire, -1);
unsigned long lastSend = 0;

float readPowerW() {
  long sum = 0;
  for (int i = 0; i < 16; i++) sum += analogRead(POT_PIN);   // average to reduce noise
  return (sum / 16.0) / 4095.0 * MAX_W;
}

const char* classify(float w) {
  if (w < OFF_W) return "OFF";
  if (w < ACTIVE_W) return "STANDBY";
  return "ACTIVE";
}

void show(float w, const char* st, bool online) {
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.print("Phantom Profiler ");
  oled.print(online ? "WiFi" : "----");
  oled.setTextSize(3);
  oled.setCursor(0, 20);
  oled.print(w, 1);
  oled.setTextSize(1);
  oled.print(" W");
  oled.setTextSize(2);
  oled.setCursor(0, 48);
  oled.print(st);
  if (strcmp(st, "STANDBY") == 0) {
    oled.setTextSize(1);
    oled.setCursor(90, 54);
    oled.print("DRAIN!");
  }
  oled.display();
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_ACTIVE, OUTPUT);
  pinMode(LED_STANDBY, OUTPUT);
  pinMode(LED_ALERT, OUTPUT);
  analogReadResolution(12);
  Wire.begin(21, 22);
  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) Serial.println("OLED not found");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 15000) delay(250);
}

void loop() {
  float w = readPowerW();
  const char* st = classify(w);
  bool standby = strcmp(st, "STANDBY") == 0;

  digitalWrite(LED_ACTIVE, strcmp(st, "ACTIVE") == 0);
  digitalWrite(LED_STANDBY, standby);
  digitalWrite(LED_ALERT, standby);
  show(w, st, WiFi.status() == WL_CONNECTED);

  if (millis() - lastSend >= PERIOD_MS) {
    lastSend = millis();
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(SERVER_URL);
      http.addHeader("Content-Type", "application/json");
      String body = String("{\"appliance\":\"") + APPLIANCE + "\",\"power_w\":" + String(w, 2) + "}";
      int code = http.POST(body);
      Serial.printf("%.2f W %s -> HTTP %d\n", w, st, code);
      http.end();
    } else {
      WiFi.reconnect();
    }
  }
  delay(100);
}
