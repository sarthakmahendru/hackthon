/*
  MountainSentinel reference node (ESP32, Arduino framework)

  STATUS: reference sketch, NOT tested on hardware. It shows how a real node
  posts the same JSON that the simulator sends. Replace the read*() functions
  with your sensor libraries (tipping bucket, capacitive soil sensor, MPU6050,
  BME280, JSN-SR04T ...). In the field you would send over LoRa to a gateway
  that forwards the same JSON to the server.

  Set SERVER_URL to your laptop's address on the same Wi-Fi, for example
  http://192.168.1.20:8000/api/readings  (start the server with:
  uvicorn backend.main:app --host 0.0.0.0 --port 8000)
*/
#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID   = "YOUR_WIFI";
const char* WIFI_PASS   = "YOUR_PASSWORD";
const char* SERVER_URL  = "http://192.168.1.20:8000/api/readings";
const char* API_KEY     = "";            // fill in only if INGEST_API_KEY is set on the server

const char* NODE_ID     = "node-real-01";
const char* NODE_NAME   = "Real node 01";
const float NODE_LAT    = 30.5550;
const float NODE_LON    = 79.5644;
const unsigned long SEND_EVERY_MS = 10000;

// ---- TODO: replace with real sensor code -----------------------------
float readRain1h()      { return 0.0; }   // mm in the last hour (count bucket tips)
float readRain24h()     { return 0.0; }   // mm in the last 24 hours
float readSoilPct()     { return 40.0; }  // capacitive sensor, calibrated to 0..100 %
float readTiltDeg()     { return 0.2; }   // angle change from install baseline (MPU6050)
float readVibrationG()  { return 0.001; } // peak acceleration in g (MPU6050)
float readTempC()       { return 20.0; }  // BME280
float readHumidity()    { return 60.0; }  // BME280
float readSmokePpm()    { return 10.0; }  // smoke / particulate sensor
float readWaterCm()     { return 55.0; }  // ultrasonic distance converted to water level
float readBatteryPct()  { return 90.0; }
// ----------------------------------------------------------------------

void connectWifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
}

void setup() {
  Serial.begin(115200);
  connectWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();

  char body[512];
  snprintf(body, sizeof(body),
    "{\"node_id\":\"%s\",\"node_name\":\"%s\",\"lat\":%.5f,\"lon\":%.5f,"
    "\"rain_1h_mm\":%.2f,\"rain_24h_mm\":%.1f,\"soil_moisture_pct\":%.1f,"
    "\"tilt_deg\":%.3f,\"vibration_g\":%.4f,\"temperature_c\":%.1f,"
    "\"humidity_pct\":%.1f,\"smoke_ppm\":%.1f,\"water_level_cm\":%.1f,"
    "\"battery_pct\":%.1f}",
    NODE_ID, NODE_NAME, NODE_LAT, NODE_LON,
    readRain1h(), readRain24h(), readSoilPct(),
    readTiltDeg(), readVibrationG(), readTempC(),
    readHumidity(), readSmokePpm(), readWaterCm(),
    readBatteryPct());

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  if (strlen(API_KEY) > 0) http.addHeader("X-API-Key", API_KEY);
  int code = http.POST((uint8_t*)body, strlen(body));
  Serial.printf("POST -> %d\n", code);
  http.end();

  delay(SEND_EVERY_MS);
}
