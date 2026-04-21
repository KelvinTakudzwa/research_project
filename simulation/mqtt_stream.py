import paho.mqtt.client as mqtt
import json
import time
import random
import csv
import os

# Use CallbackAPIVersion for paho-mqtt v2 compatibility
try:
    client = mqtt.Client(
        client_id="PythonSimulator",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv311
    )
except AttributeError:
    client = mqtt.Client(client_id="PythonSimulator", protocol=mqtt.MQTTv311)

try:
    client.connect("localhost", 1883, 60)
    client.loop_start()  # Start network daemon to process QoS 1 PUBACKs
except Exception as e:
    print(f"Could not connect to broker: {e}")
    exit(1)

print("Publishing data to 'solar/data' every 2 seconds...")
print("Fault injection: 1 shading event every ~60 seconds (5% rate).")
print("Check your http://localhost:8080/ dashboard to see the live feed!")

# Load realistic daylight data from baseline CSV to appease Isolation Forest physics
csv_path = os.path.join(os.path.dirname(__file__), "..", "ml_engine", "solar_data_30days.csv")
daylight_rows = []
try:
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Only stream daytime data so it looks active
            if float(row['irradiance_lux']) > 10000:
                daylight_rows.append(row)
except Exception as e:
    print(f"Failed to read CSV: {e}")
    exit(1)

fault_counter = 0
row_idx = 0

try:
    while True:
        fault_counter += 1
        is_fault = (fault_counter % 30 == 0)
        
        # Loop through daylight data
        current_row = daylight_rows[row_idx % len(daylight_rows)]
        row_idx += 1

        payload = {
            "timestamp_unix": int(time.time()),
            "pv_voltage":     round(float(current_row['pv_voltage']), 2),
            "pv_current":     round(float(current_row['pv_current']), 2),
            "batt_voltage":   round(float(current_row['batt_voltage']), 2),
            "load_current":   round(float(current_row['load_current']), 2),
            "temp_ambient":   round(float(current_row['temp_ambient']), 2),
            "temp_probe":     round(float(current_row['temp_probe']), 2),
            "irradiance_lux": round(float(current_row['irradiance_lux']), 2)
        }

        if is_fault:
            fault_cycle = int((fault_counter / 30) % 4)
            if fault_cycle == 1:
                # F1 Partial Shading
                payload["pv_current"] = round(0.9 + random.uniform(-0.1, 0.1), 2)
                fault_name = "F1 Partial Shading"
            elif fault_cycle == 2:
                # F2 Inverter Overload
                payload["load_current"] = round(10.0 + random.uniform(-0.5, 0.5), 2)
                payload["temp_probe"] = round(50.0 + random.uniform(-1, 1), 2)
                payload["batt_voltage"] = round(payload["batt_voltage"] - 0.5, 2)
                fault_name = "F2 Inverter Overload"
            elif fault_cycle == 3:
                # F3 Deep Discharge
                payload["batt_voltage"] = round(11.4 + random.uniform(-0.1, 0.0), 2)
                payload["pv_current"] = 0.0
                payload["irradiance_lux"] = 0.0
                fault_name = "F3 Deep Discharge"
            elif fault_cycle == 0:
                # F5 Sensor Fault / Dead
                payload["pv_current"] = 0.0
                payload["load_current"] = 0.0
                fault_name = "F5 Sensor Dead"
                
            print(f"\n[CRITICAL FAULT INJECTED] {fault_name} applied to payload!")
            print(f"Published: {payload}")
        else:
            print(f"Published: {payload}")

        client.publish("solar/data", json.dumps(payload), qos=1)
        time.sleep(2)

except KeyboardInterrupt:
    print("\nStopped simulator.")
    client.disconnect()
