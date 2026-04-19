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
csv_path = os.path.join(os.path.dirname(__file__), "solar_data_30days.csv")
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
            "pv_current":     round(float(current_row['pv_current']), 2) if not is_fault else 0.5,
            "batt_voltage":   round(float(current_row['batt_voltage']), 2),
            "load_current":   round(float(current_row['load_current']), 2),
            "temperature":    round(float(current_row['temperature']), 2),
            "irradiance_lux": round(float(current_row['irradiance_lux']), 2)
        }

        if is_fault:
            print(f"[FAULT INJECTED] F1 Partial Shading — pv_current=0.5A at {payload['irradiance_lux']} Lux")
        else:
            print(f"Published: {payload}")

        client.publish("solar/data", json.dumps(payload), qos=1)
        time.sleep(2)

except KeyboardInterrupt:
    print("\nStopped simulator.")
    client.disconnect()
