import json
import time
from collections import deque
import numpy as np
import joblib
from paho.mqtt import client as mqtt_client
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions
from feature_extraction import compute_window_features

# --- InfluxDB config ---
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "YOUR INFLUX TOKEN"
INFLUX_ORG = "smart-machine"
INFLUX_BUCKET = "vibration"

# --- MQTT config ---
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/fan1/vibration"

# --- Health scoring config ---
WINDOW_SECONDS = 5.0
MIN_SAMPLES = 40

model = joblib.load("isolation_forest_model.pkl")
score_min, score_max = np.load("score_range.npy")

def to_health_score(raw_score):
    normalized = (raw_score - score_min) / (score_max - score_min + 1e-9)
    return float(np.clip(normalized, 0, 1) * 100)

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=WriteOptions(batch_size=50, flush_interval=200))

buffer = deque()

msg_count = [0]
last_report = [time.time()]

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
    else:
        print("Failed to connect, return code", rc)

def on_message(client, userdata, msg):
    msg_count[0] += 1
    now_check = time.time()
    if now_check - last_report[0] >= 1.0:
        rate = msg_count[0] / (now_check - last_report[0])
        print(f"[RAW MQTT RATE] {msg_count[0]} messages in {now_check - last_report[0]:.2f}s -> {rate:.1f} Hz")
        msg_count[0] = 0
        last_report[0] = now_check

    try:
        payload = json.loads(msg.payload.decode())
        ax, ay, az = float(payload["ax"]), float(payload["ay"]), float(payload["az"])

        point = (
            Point("vibration")
            .field("ax", ax).field("ay", ay).field("az", az)
            .time(time.time_ns(), WritePrecision.NS)
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print("Wrote point:", payload)

        now = time.time()
        mag = (ax**2 + ay**2 + az**2) ** 0.5
        buffer.append((now, mag))

        if buffer and (now - buffer[0][0]) >= WINDOW_SECONDS:
            samples = [m for (_, m) in buffer]
            if len(samples) >= MIN_SAMPLES:
                fs_actual = len(samples) / WINDOW_SECONDS
                feats = compute_window_features(np.array(samples), fs_actual)
                raw_score = model.decision_function([feats])[0]
                health = to_health_score(raw_score)
                write_api.write(
                    bucket=INFLUX_BUCKET, org=INFLUX_ORG,
                    record=Point("health").field("score", health).time(time.time_ns(), WritePrecision.NS)
                )
                print(f"Health score: {health:.1f}")
            buffer.clear()
    except Exception as e:
        print("Error processing message:", e)

client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, client_id="bridge")
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT)
client.loop_forever()