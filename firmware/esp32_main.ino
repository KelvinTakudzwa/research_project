#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// NETWORK CONFIGURATION
// TODO: User must update these before flashing!
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// SERVER CONFIGURATION
// Replace '192.168.1.XX' with your Computer's Local IP Address
const char* serverName = "http://192.168.1.XX:5000/api/data"; 

void setup() {
  Serial.begin(115200);
  
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
}

void loop() {
  // Check WiFi connection status
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // Begin connection to the Node.js Backend
    http.begin(serverName);
    http.addHeader("Content-Type", "application/json");

    // DATA ACQUISITION LAYER (Simulated for Prototype Phase)
    // In final hardware, these will be replaced by:
    // float pv_volts = pzem.voltage();
    // float batt_volts = analogRead(35) * scaling_factor;
    
    // Create JSON Payload (Capacity: 200 bytes is sufficient for 4 fields)
    StaticJsonDocument<200> doc;
    
    // Generate data matching our Python Simulation ranges
    doc["pv_voltage"] = random(170, 190) / 10.0;   // 17.0 - 19.0 V
    doc["pv_current"] = random(0, 50) / 10.0;      // 0.0 - 5.0 A
    doc["batt_voltage"] = random(110, 144) / 10.0; // 11.0 - 14.4 V
    doc["load_current"] = random(0, 30) / 10.0;    // 0.0 - 3.0 A
    doc["temp"] = random(250, 400) / 10.0;         // 25.0 - 40.0 C

    // Serialize JSON to string
    String requestBody;
    serializeJson(doc, requestBody);

    // SEND DATA via HTTP POST
    int httpResponseCode = http.POST(requestBody);
    
    Serial.print("Sending Data: ");
    Serial.println(requestBody);
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);
    
    http.end(); // Free resources
  }
  else {
    Serial.println("WiFi Disconnected");
  }

  // WAIT LAYER
  // Send data every 60 seconds (1 minute interval)
  delay(60000); 
}
