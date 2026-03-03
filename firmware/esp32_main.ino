#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "time.h"

// NETWORK CONFIGURATION
// TODO: User must update these before flashing!
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// SERVER CONFIGURATION
// Replace '192.168.1.XX' with your Computer's Local IP Address
const char* serverName = "http://192.168.1.XX:5000/api/data"; 

// TIME TRACKING
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = 0; // Set to 0, Backend can handle timezone/GMT
const int   daylightOffset_sec = 0;

unsigned long lastSyncMillis = 0;
time_t lastNtpTime = 0;
bool timeSynced = false;

const char* BACKLOG_FILE = "/backlog.txt";

void setup() {
  Serial.begin(115200);
  
  // Initialize LittleFS
  if (!LittleFS.begin(true)) {
    Serial.println("LittleFS Mount Failed");
    return;
  }
  Serial.println("LittleFS Mounted Successfully");

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) { 
    delay(500); 
    Serial.print("."); 
  }
  Serial.println("\nWiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());

  // Init and Sync NTP Time
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
  syncTime();
}

void syncTime() {
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    time(&lastNtpTime); // Get unix epoch
    lastSyncMillis = millis();
    timeSynced = true;
    Serial.println("Time successfully synced via NTP.");
  } else {
    Serial.println("Failed to obtain time.");
  }
}

// Helper: Calculate current Unix timestamp (handles offline fallback via millis)
time_t getCurrentTimestamp() {
  if (!timeSynced) {
    return 0; // Return 0 if we never synced
  }
  // If WiFi is connected, opportunistically re-sync the baseline
  if (WiFi.status() == WL_CONNECTED && (millis() - lastSyncMillis > 3600000)) { // 1 hour
     syncTime();
  }
  
  unsigned long elapsedMillis = millis() - lastSyncMillis;
  return lastNtpTime + (elapsedMillis / 1000);
}

void sendBacklog() {
  if (!LittleFS.exists(BACKLOG_FILE)) return;
  
  File file = LittleFS.open(BACKLOG_FILE, "r");
  if (!file || file.size() == 0) {
    if (file) file.close();
    return;
  }

  Serial.println("Backlog found. Preparing burst transmission...");
  
  // Create JSON Array payload in memory: [{},{},{}]
  String payload = "[";
  bool firstLine = true;
  
  while (file.available()) {
    String line = file.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      if (!firstLine) {
        payload += ",";
      }
      payload += line;
      firstLine = false;
    }
  }
  payload += "]";
  file.close();

  // Send Burst Payload
  HTTPClient http;
  http.begin(serverName);
  http.addHeader("Content-Type", "application/json");
  
  int httpResponseCode = http.POST(payload);
  Serial.print("Burst HTTP Response code: ");
  Serial.println(httpResponseCode);
  
  http.end();

  if (httpResponseCode > 0 && httpResponseCode < 300) {
    Serial.println("Backlog sent successfully. Deleting file...");
    LittleFS.remove(BACKLOG_FILE);
  } else {
    Serial.println("Backlog transmission failed. Will retry later.");
  }
}

void storeLocally(const String& ndjsonLine) {
  File file = LittleFS.open(BACKLOG_FILE, "a");
  if (!file) {
    Serial.println("Failed to open file for appending");
    return;
  }
  file.println(ndjsonLine);
  file.close();
  Serial.println("Data stored locally (NDJSON format).");
}

void loop() {
  // DATA ACQUISITION LAYER (Simulated)
  StaticJsonDocument<250> doc;
  
  doc["pv_voltage"] = random(170, 190) / 10.0;
  doc["pv_current"] = random(0, 50) / 10.0;
  doc["batt_voltage"] = random(110, 144) / 10.0;
  doc["load_current"] = random(0, 30) / 10.0;
  doc["temp"] = random(250, 400) / 10.0;
  
  // Inject calculated timestamp
  doc["timestamp_unix"] = getCurrentTimestamp();

  String requestBody;
  serializeJson(doc, requestBody);

  // Check connection
  if (WiFi.status() == WL_CONNECTED) {
    // If we have connection, first try sending backlog
    sendBacklog();

    // Now send the current reading
    HTTPClient http;
    http.begin(serverName);
    http.addHeader("Content-Type", "application/json");

    int httpResponseCode = http.POST(requestBody);
    
    Serial.print("Sending Live Data: ");
    Serial.println(requestBody);
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);
    
    http.end();

    if (httpResponseCode <= 0 || httpResponseCode >= 300) {
       // Request failed despite WiFi connection (e.g. server down)
       storeLocally(requestBody); 
    }
  } else {
    // No WiFi -> Store Locally Immediately
    Serial.println("WiFi Disconnected. Storing for later...");
    storeLocally(requestBody);
  }

  // WAIT LAYER (1 minute)
  delay(60000); 
}
