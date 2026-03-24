// ============================================================
// ESP32 Solar Mini-Grid IoT Node Firmware
// Phase 8: DS3231 RTC + MQTT QoS 1
//
// Libraries required (install via Arduino Library Manager):
//   - "MQTT" by Joel Gaehwiler       (QoS 1 PUBACK support)
//   - "RTClib" by Adafruit            (DS3231 hardware clock)
//   - "ArduinoJson" by Arduino        (JSON serialization)
// ============================================================

#include <WiFi.h>
#include <MQTT.h>          // Joel Gaehwiler — true QoS 1 publishing
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "time.h"
#include <Wire.h>          // I2C bus for DS3231
#include <RTClib.h>        // Adafruit RTClib — DS3231 driver

// ============================================================
// NETWORK & BROKER CONFIGURATION
// TODO: Update WIFI credentials and BROKER IP before flashing!
// ============================================================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Replace with your laptop's LOCAL IP (run `ipconfig` on Windows)
const char* MQTT_BROKER_IP   = "192.168.1.XX";
const int   MQTT_BROKER_PORT = 1883;
const char* MQTT_CLIENT_ID   = "ESP32_SolarNode_01";
const char* MQTT_TOPIC       = "solar/data";

// ============================================================
// DS3231 RTC — Battery-backed hardware clock (Phase 8, Task 2)
// Wiring: SDA → GPIO21, SCL → GPIO22, VCC → 3.3V, GND → GND
// The DS3231 retains the exact time for years using a CR2032 coin battery.
// This eliminates the millis() timestamp corruption seen after power loss.
// ============================================================
const char* NTP_SERVER       = "pool.ntp.org";
const long  GMT_OFFSET_SEC   = 0;
const int   DST_OFFSET_SEC   = 0;

RTC_DS3231    rtc;                // DS3231 hardware RTC object
bool          rtcAvailable = false; // set true if DS3231 found on I2C bus

// millis() fallback (used ONLY if both RTC and NTP fail — last resort)
unsigned long lastSyncMillis = 0;
time_t        lastNtpTime    = 0;
bool          timeSynced     = false;

// ============================================================
// STORE & FORWARD CONFIG
// ============================================================
const char* BACKLOG_FILE    = "/backlog.txt";
const int   BURST_CHUNK_SZ  = 5;   // Publish this many lines per chunk (WDT safety)
const int   PAYLOAD_MAX_SZ  = 512; // Must match MQTT library's max packet size

// ============================================================
// MQTT & WIFI CLIENTS
// ============================================================
WiFiClient   wifiNet;
MQTTClient   mqttClient(PAYLOAD_MAX_SZ); // Set max packet size to 512 bytes

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);

  // Initialize I2C for DS3231
  Wire.begin();

  // Initialize DS3231 RTC
  if (rtc.begin()) {
    rtcAvailable = true;
    Serial.println("[RTC] DS3231 detected on I2C bus.");
    if (rtc.lostPower()) {
      // RTC lost power — clock is invalid. Must sync from NTP.
      Serial.println("[RTC] WARNING: RTC lost power. Timestamp invalid until NTP sync.");
    } else {
      DateTime now = rtc.now();
      Serial.printf("[RTC] Current time: %04d-%02d-%02d %02d:%02d:%02d\n",
        now.year(), now.month(), now.day(), now.hour(), now.minute(), now.second());
    }
  } else {
    rtcAvailable = false;
    Serial.println("[RTC] DS3231 NOT found — will fall back to NTP/millis().");
  }

  // Initialize LittleFS for Store & Forward
  if (!LittleFS.begin(true)) {
    Serial.println("[LittleFS] CRITICAL: Mount failed.");
    return;
  }
  Serial.println("[LittleFS] Mounted.");

  connectWiFi();
  syncNTP(); // Also sets the RTC if Wi-Fi is available
  connectMQTT();
}

// ============================================================
// WIFI CONNECTION
// ============================================================
void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[WiFi] Connecting");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WiFi] Failed. Will retry in loop.");
  }
}

// ============================================================
// NTP SYNC — Also sets the DS3231 hardware clock
// ============================================================
void syncNTP() {
  if (WiFi.status() != WL_CONNECTED) {
    if (rtcAvailable && !rtc.lostPower()) {
      Serial.println("[NTP] Wi-Fi not available. DS3231 providing time.");
    } else {
      Serial.println("[NTP] Wi-Fi not available. No reliable time source.");
    }
    return;
  }

  configTime(GMT_OFFSET_SEC, DST_OFFSET_SEC, NTP_SERVER);
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    time(&lastNtpTime);
    lastSyncMillis = millis();
    timeSynced = true;
    Serial.println("[NTP] Time synced successfully.");

    // KEY STEP: Write NTP time into DS3231 hardware registers
    if (rtcAvailable) {
      rtc.adjust(DateTime(lastNtpTime));
      Serial.println("[RTC] DS3231 clock set from NTP. Coin battery will maintain this time.");
    }
  } else {
    Serial.println("[NTP] NTP sync failed.");
  }
}

// ============================================================
// GET CURRENT TIMESTAMP — Priority: DS3231 > NTP/millis() fallback
// ============================================================
time_t getCurrentTimestamp() {
  // 1st choice: DS3231 hardware clock (accurate even after power loss)
  if (rtcAvailable && !rtc.lostPower()) {
    return (time_t)rtc.now().unixtime();
  }

  // 2nd choice: millis() offset from last NTP sync (drifts over time)
  if (timeSynced) {
    // Re-sync opportunistically every hour while online
    if (WiFi.status() == WL_CONNECTED && (millis() - lastSyncMillis > 3600000)) {
      syncNTP();
    }
    return lastNtpTime + ((millis() - lastSyncMillis) / 1000);
  }

  // Last resort: No reliable time source
  return 0;
}


// ============================================================
// MQTT CONNECTION (Gaehwiler library — true QoS 1 support)
// ============================================================
void connectMQTT() {
  mqttClient.begin(MQTT_BROKER_IP, MQTT_BROKER_PORT, wifiNet);
  Serial.print("[MQTT] Connecting to broker");
  int attempts = 0;
  while (!mqttClient.connect(MQTT_CLIENT_ID) && attempts < 10) {
    Serial.print(".");
    delay(500);
    attempts++;
  }
  if (mqttClient.connected()) {
    Serial.printf("\n[MQTT] Connected. Publishing to topic: %s (QoS 1)\n", MQTT_TOPIC);
  } else {
    Serial.println("\n[MQTT] Broker unreachable. Will store data locally.");
  }
}

// ============================================================
// STORE LOCALLY (NDJSON append — corruption-safe)
// ============================================================
void storeLocally(const String& ndjsonLine) {
  File file = LittleFS.open(BACKLOG_FILE, "a");
  if (!file) {
    Serial.println("[LittleFS] ERROR: Cannot open backlog for writing.");
    return;
  }
  file.println(ndjsonLine);
  file.close();
  Serial.println("[LittleFS] Reading stored locally.");
}

// ============================================================
// SEND BACKLOG (WDT-safe chunked burst recovery)
// ============================================================
void sendBacklog() {
  if (!LittleFS.exists(BACKLOG_FILE)) return;

  File file = LittleFS.open(BACKLOG_FILE, "r");
  if (!file || file.size() == 0) {
    if (file) file.close();
    return;
  }

  Serial.printf("[LittleFS] Backlog found (%d bytes). Starting chunked burst...\n", file.size());

  // Collect all lines into memory first, then publish in chunks
  std::vector<String> lines;
  while (file.available()) {
    String line = file.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) lines.push_back(line);
  }
  file.close();

  int total   = lines.size();
  int success = 0;

  for (int i = 0; i < total; i++) {
    // Publish each backlog reading as a QoS 1 MQTT message
    bool ok = mqttClient.publish(MQTT_TOPIC, lines[i], false, 1);
    if (ok) {
      success++;
    } else {
      Serial.printf("[MQTT] Publish failed for backlog line %d — stopping burst.\n", i);
      break; // Abort and retry next cycle
    }

    // Chunk boundary: every BURST_CHUNK_SZ lines, yield to watchdog + WiFi stack
    if ((i + 1) % BURST_CHUNK_SZ == 0) {
      mqttClient.loop();    // Process PUBACK handshakes
      yield();              // Feed ESP32 Hardware Watchdog Timer (WDT)
      delay(10);            // Allow WiFi stack to breathe
      Serial.printf("[MQTT] Burst chunk: %d/%d sent.\n", i + 1, total);
    }
  }

  Serial.printf("[MQTT] Burst complete: %d/%d readings delivered.\n", success, total);

  if (success == total) {
    LittleFS.remove(BACKLOG_FILE);
    Serial.println("[LittleFS] Backlog cleared.");
  } else {
    Serial.println("[LittleFS] Partial burst — backlog kept for next retry.");
  }
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  mqttClient.loop(); // Process MQTT keep-alive and PUBACK responses

  // ── DATA ACQUISITION (Simulated sensors) ────────────────
  float sim_pv_voltage = random(170, 190) / 10.0;

  StaticJsonDocument<PAYLOAD_MAX_SZ> doc;
  doc["pv_voltage"]     = sim_pv_voltage;
  doc["pv_current"]     = random(0, 50)  / 10.0;
  doc["batt_voltage"]   = random(110, 144) / 10.0;
  doc["load_current"]   = random(0, 30)  / 10.0;
  doc["temp"]           = random(250, 400) / 10.0;
  // Simulated BH1750 irradiance (scaled from PV voltage proxy)
  doc["irradiance_lux"] = (int)(sim_pv_voltage * 5000) + random(0, 5000);
  doc["timestamp_unix"] = (long)getCurrentTimestamp();

  String payload;
  serializeJson(doc, payload);

  // ── TRANSMISSION ────────────────────────────────────────
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Disconnected — storing reading locally.");
    storeLocally(payload);
    connectWiFi(); // Attempt reconnect
    delay(60000);
    return;
  }

  // WiFi is connected — try to ensure MQTT is also connected
  if (!mqttClient.connected()) {
    Serial.println("[MQTT] Disconnected — reconnecting...");
    connectMQTT();
  }

  if (mqttClient.connected()) {
    // First: drain any backlog from offline period
    sendBacklog();

    // Then: publish current reading via QoS 1
    Serial.print("[MQTT] Publishing: "); Serial.println(payload);
    bool ok = mqttClient.publish(MQTT_TOPIC, payload, false, 1); // QoS 1, non-retained
    if (!ok) {
      Serial.println("[MQTT] Publish failed — storing locally as fallback.");
      storeLocally(payload);
    } else {
      Serial.println("[MQTT] Published OK (QoS 1 PUBACK expected).");
    }
  } else {
    // Broker still unreachable — fall back to LittleFS
    Serial.println("[MQTT] Broker unreachable — storing locally.");
    storeLocally(payload);
  }

  // ── WAIT (1 reading per minute) ─────────────────────────
  delay(60000);
}
