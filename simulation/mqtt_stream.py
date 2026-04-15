import paho.mqtt.client as mqtt
import json
import time
import random

# Connect to the Mosquitto broker inside Docker (localhost:1883)
# We use Callback API v1 for legacy compatibility with older paho-mqtt versions.
client = mqtt.Client(client_id="PythonSimulator", protocol=mqtt.MQTTv311)
try:
    client.connect("localhost", 1883, 60)
except Exception as e:
    print(f"Could not connect to broker: {e}")
    exit(1)

print("Publishing dummy data to 'solar/data' every 2 seconds...")
print("Check your http://localhost:8080/ dashboard to see the live feed!")

try:
    while True:
        # Generate realistic baseline data
        payload = {
            "timestamp": int(time.time()),
            "pv_voltage": round(random.uniform(17.5, 18.2), 2),
            "pv_current": round(random.uniform(3.5, 4.5), 2),
            "batt_voltage": round(random.uniform(12.8, 13.5), 2),
            "load_current": round(random.uniform(1.0, 1.8), 2),
            "temperature": round(random.uniform(30.0, 35.0), 2),
            "irradiance_lux": round(random.uniform(85000, 95000), 2)
        }
        
        # Introduce a random fault (F1 Partial Shading) every 20 seconds to see the ML predict "Critical"
        if int(time.time()) % 20 < 4: 
            payload["pv_current"] = 0.5  # Irradiance is high, but current drops!
        
        client.publish("solar/data", json.dumps(payload), qos=1)
        print(f"Published: {payload}")
        time.sleep(2)
        
except KeyboardInterrupt:
    print("\nStopped simulator.")
    client.disconnect()
