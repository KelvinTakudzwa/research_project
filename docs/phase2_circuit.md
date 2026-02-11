# Phase 2: IoT Node Prototype & Circuit Design

## 1. Circuit Design Logic
The IoT Node is built around the **ESP32 DevKit V1**. It interfaces with 4 key sensors to monitor the Solar Mini-Grid.

| Component | Sensor Model | ESP32 Pin | Connection Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| **PV Voltage/Current** | PZEM-004T | GPIO 16 (RX2) <br> GPIO 17 (TX2) | UART (Serial2) | High voltage/current digital AC/DC meter. |
| **Load Current** | ACS712-05A | GPIO 34 (ADC1) | Analog Input | Measures current to the house/load. |
| **Battery Voltage** | Voltage Divider | GPIO 35 (ADC1) | Analog Input | Resistor network to step down 12V to 3.3V. |
| **Temperature** | DHT11 | GPIO 4 | Digital 1-Wire | Monitors battery ambient temp. |

### Circuit Diagram
```mermaid
graph LR
    subgraph ESP32_DevKit_V1
        GPIO16[GPIO 16 (RX2)]
        GPIO17[GPIO 17 (TX2)]
        GPIO34[GPIO 34 (ADC1)]
        GPIO35[GPIO 35 (ADC1)]
        GPIO04[GPIO 4]
    end

    subgraph Sensors
        PZEM[PZEM-004T Module]
        ACS[ACS712 Current Sensor]
        V_DIV[Voltage Divider Circuit]
        DHT[DHT11 Temp Sensor]
    end

    PZEM -- TX --> GPIO16
    PZEM -- RX --> GPIO17
    ACS -- Vout --> GPIO34
    V_DIV -- Vout --> GPIO35
    DHT -- Data --> GPIO04
```

## 2. Distributed Computing Architecture
To optimize the limited resources of the ESP32, we adopt a **Distributed Computing** approach:
*   **Edge Layer (ESP32)**: Responsible *only* for raw data acquisition (ADC sampling, UART reading) and transmission. It does **not** perform heavy math.
*   **Fog/Cloud Layer (Node.js)**: Receives raw data and performs "Feature Engineering" (e.g., SoC Calculation, Moving Averages) before storage.

This lowers the power consumption of the IoT node and allows for more complex algorithms on the server.
