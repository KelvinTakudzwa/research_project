// ============================================================
// ESP32 Solar Diagnostics System — SIL Sensor Validation
// PlatformIO build entry point (replaces wokwi_sil_test.ino)
//
// PURPOSE: Validates the sensor acquisition subsystem in isolation.
// Tests DS18B20, BH1750, DS3231 RTC, and ADC voltage/current
// reading pipelines independently of the network transport layer.
//
// lib_deps (platformio.ini):
//   - DallasTemperature + OneWire  (DS18B20)
//   - BH1750                        (irradiance sensor)
//   - RTClib                         (DS3231 clock)
//   - ArduinoJson                    (payload serialization)
//   - LiquidCrystal I2C              (LCD1602 display)
// ============================================================

#include <Arduino.h>
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <BH1750.h>
#include <RTClib.h>
#include <ArduinoJson.h>
#include <LiquidCrystal_I2C.h>

// ── GPIO PIN MAP (must match production firmware) ─────────
const int PIN_PV_VOLTAGE   = 34;   // ADC1 ch6 — PV voltage divider
const int PIN_BATT_VOLTAGE = 35;   // ADC1 ch7 — battery voltage divider
const int PIN_PV_CURRENT   = 36;   // ADC1 ch0 (VP) — ACS712 #1
const int PIN_BATT_CURRENT = 39;   // ADC1 ch3 (VN) — ACS712 #2
const int ONE_WIRE_BUS     = 4;    // DS18B20 data pin (1-Wire)
// I2C: SDA=GPIO21, SCL=GPIO22 (BH1750 + DS3231)

// ── CALIBRATION (matches production NVS defaults) ─────────
const float PV_DIVIDER_RATIO   = 7.67f;   // R1=100kΩ, R2=15kΩ
const float BATT_DIVIDER_RATIO = 4.70f;   // R1=100kΩ, R2=27kΩ
const float ACS712_SENSITIVITY = 0.1f;    // 100mV/A (ACS712-20A)
const int   ADC_MIDPOINT       = 2047;    // Default zero-current ADC value

// ── HARDWARE OBJECTS ──────────────────────────────────────
OneWire           oneWire(ONE_WIRE_BUS);
DallasTemperature ds18b20(&oneWire);
BH1750            bh1750;
RTC_DS3231        rtc;
LiquidCrystal_I2C lcd(0x27, 16, 2);   // PCF8574 backpack, 16 cols x 2 rows

int readingCount = 0;
int lcdPage      = 0;   // Cycles: 0=PV  1=Battery  2=Environment

// ── HELPER: Read voltage through a resistor divider ───────
float readVoltage(int pin, float ratio) {
    int   raw        = analogRead(pin);
    float adcVoltage = (raw / 4095.0f) * 3.3f;
    return adcVoltage * ratio;
}

// ── HELPER: Read current from ACS712 ──────────────────────
float readCurrent(int pin, int zeroPoint) {
    int   raw         = analogRead(pin);
    float adcVoltage  = (raw / 4095.0f) * 3.3f;
    float zeroVoltage = (zeroPoint / 4095.0f) * 3.3f;
    return (adcVoltage - zeroVoltage) / ACS712_SENSITIVITY;
}

// ── LCD UPDATE — cycles 3 pages per reading ───────────────
void updateLCD(float pvV, float pvI, float battV, float battI,
               float lux, float tempProbe, float soc) {
    char row0[17], row1[17];
    lcd.clear();

    if (lcdPage == 0) {
        float pvPow = pvV * pvI;
        snprintf(row0, sizeof(row0), "PV %5.1fV %4.1fA", pvV, pvI);
        snprintf(row1, sizeof(row1), "Pwr   %6.1f W  ",  pvPow);
    } else if (lcdPage == 1) {
        const char* mode = (battI >=  0.05f) ? "CHG" :
                           (battI <= -0.05f) ? "DSC" : "FLT";
        snprintf(row0, sizeof(row0), "BT %5.1fV %4.1fA", battV, battI);
        snprintf(row1, sizeof(row1), "SoC %3d%%   [%s]", (int)soc, mode);
    } else {
        float irr = (lux > 0.0f) ? lux / 120.0f : 0.0f;
        snprintf(row0, sizeof(row0), "Irr %5.0f W/m2 ", irr);
        snprintf(row1, sizeof(row1), "T:%4.1fC         ", tempProbe);
    }

    lcd.setCursor(0, 0); lcd.print(row0);
    lcd.setCursor(0, 1); lcd.print(row1);
    lcdPage = (lcdPage + 1) % 3;
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("============================================");
    Serial.println(" Solar Diagnostics System — SIL Validation");
    Serial.println("  ESP32 IoT Node — Wokwi Simulation");
    Serial.println("============================================");

    ds18b20.begin();
    int sensorCount = ds18b20.getDeviceCount();
    Serial.print("[DS18B20] Sensors found on OneWire bus: ");
    Serial.println(sensorCount);

    Wire.begin(21, 22);
    if (bh1750.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
        Serial.println("[BH1750]  Irradiance sensor initialised (I2C 0x23).");
    } else {
        Serial.println("[BH1750]  ERROR: Sensor not found!");
    }

    if (!rtc.begin()) {
        Serial.println("[RTC]     ERROR: DS3231 not found on I2C bus!");
    } else {
        Serial.println("[RTC]     DS3231 clock initialised.");
        if (rtc.lostPower()) {
            Serial.println("[RTC]     Clock lost power — setting to compile time.");
            rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
        }
    }

    Serial.println("--------------------------------------------");
    Serial.println("[INIT]    All sensors OK. Starting read loop.");
    Serial.println("--------------------------------------------\n");

    lcd.init();
    lcd.backlight();
    lcd.setCursor(0, 0); lcd.print(" Solar Diag Sys ");
    lcd.setCursor(0, 1); lcd.print("  SIL Validate  ");

    delay(1000);
}

void loop() {
    readingCount++;
    DateTime now = rtc.now();

    ds18b20.requestTemperatures();
    float tempProbe = ds18b20.getTempCByIndex(0);

    float lux = bh1750.readLightLevel();

    float pvVoltage   = readVoltage(PIN_PV_VOLTAGE,   PV_DIVIDER_RATIO);
    float battVoltage = readVoltage(PIN_BATT_VOLTAGE,  BATT_DIVIDER_RATIO);
    float pvCurrent   = readCurrent(PIN_PV_CURRENT,   ADC_MIDPOINT);
    float battCurrent = readCurrent(PIN_BATT_CURRENT, ADC_MIDPOINT);

    float pvPower     = pvVoltage * pvCurrent;
    float netFlux     = pvCurrent - abs(battCurrent);
    float tempAmbient = 25.0f;
    float tempDelta   = tempProbe - tempAmbient;

    float soc = ((battVoltage - 10.5f) / (14.4f - 10.5f)) * 100.0f;
    soc = constrain(soc, 0.0f, 100.0f);

    StaticJsonDocument<512> doc;
    doc["reading"]         = readingCount;
    doc["timestamp"]       = now.timestamp(DateTime::TIMESTAMP_FULL);
    doc["pv_voltage"]      = round(pvVoltage   * 100) / 100.0;
    doc["pv_current"]      = round(pvCurrent   * 100) / 100.0;
    doc["pv_power_watts"]  = round(pvPower     * 100) / 100.0;
    doc["batt_voltage"]    = round(battVoltage * 100) / 100.0;
    doc["batt_current"]    = round(battCurrent * 100) / 100.0;
    doc["soc_percent"]     = round(soc         * 10)  / 10.0;
    doc["irradiance_lux"]  = round(lux);
    doc["temp_probe_c"]    = round(tempProbe   * 10)  / 10.0;
    doc["temp_ambient_c"]  = tempAmbient;
    doc["temp_delta_c"]    = round(tempDelta   * 10)  / 10.0;
    doc["net_energy_flux"] = round(netFlux     * 100) / 100.0;

    Serial.print("[READ #");
    Serial.print(readingCount);
    Serial.print("] ");
    Serial.println(now.timestamp(DateTime::TIMESTAMP_FULL));

    String payload;
    serializeJsonPretty(doc, payload);
    Serial.println(payload);
    Serial.println("--------------------------------------------");
    Serial.flush();

    updateLCD(pvVoltage, pvCurrent, battVoltage, battCurrent,
              lux, tempProbe, soc);

    delay(2000);   // One reading every 2 seconds — 3 LCD pages cycle every 6 seconds
}
