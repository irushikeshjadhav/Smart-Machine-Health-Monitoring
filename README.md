# Smart Machine Health Monitoring System

A vibration-based predictive-maintenance prototype. A small USB-powered fan stands in for industrial rotating equipment (CNC spindles, pumps, conveyor motors). An ESP32 with a 6-axis accelerometer streams live vibration data through an MQTT → InfluxDB → Grafana pipeline, with an unsupervised machine-learning model (Isolation Forest) scoring machine health in real time — trained entirely on healthy data, with no labeled faults required.

---

## Overview

Industrial predictive maintenance systems typically face a hard constraint: labeled examples of equipment failure are rare and expensive to collect. This project demonstrates an approach that works around that constraint entirely — the model learns what "normal" vibration looks like from healthy operating data alone, and flags anything that deviates from it, without ever needing to be shown a labeled fault.

The full pipeline — edge sensing, message brokering, time-series storage, live dashboarding, and machine learning — runs as a reproducible, containerized stack, deployable with a single command.

## Architecture

```
USB Fan + LSM6DS3 Sensor
        │  vibration
        ▼
ESP32 (read sensor → format JSON → publish MQTT, 100Hz)
        │  MQTT: sensors/fan1/vibration
        ▼
Mosquitto (MQTT broker)
        │
        ▼
bridge.py  ──────────────┬─────────────────────────
        │                │
   write raw point   buffer 5s window → extract
   (ax, ay, az)       features → Isolation Forest
        │                │  → health score
        └───────┬────────┘
                 ▼
             InfluxDB (vibration + health measurements)
                 │
                 ▼
             Grafana (time series + health gauge, 5s refresh)
                 │
                 ▼
             User (live dashboard)
```

## Hardware

| Component | Details |
|---|---|
| Microcontroller | ESP32-WROOM-32E DevKitC |
| Sensor | Seeed Grove LSM6DS3 (6-axis accelerometer + gyroscope), I2C address `0x6A` |
| Wiring | Grove 4-pin cable → breadboard → ESP32: Yellow=GPIO22 (SCL), White=GPIO21 (SDA), Red=**3V3** (not 5V), Black=GND |
| Test asset | Small USB-powered fan (clip/clamp-mounted) |
| Sensor mount | Taped to the fan's fixed frame/housing — never the spinning blades |

## Software prerequisites

- Docker + Docker Compose
- Arduino IDE with ESP32 board package, `Seeed_Arduino_LSM6DS3` and `PubSubClient` libraries
- Python 3.10+

## Setup

### 1. Clone and configure environment

```bash
git clone <your-repo-url>
cd smart-machine-health-monitoring
cp .env.example .env
```

Edit `.env` and fill in your InfluxDB token (generated in step 3 below).

### 2. Start the backend stack

```bash
docker compose up -d
docker compose ps   # confirm mosquitto, influxdb, grafana are all running
```

Default ports: Mosquitto `1883`, InfluxDB `8086`, Grafana `3011` (remapped — adjust in `docker-compose.yml` if these conflict with something on your machine).

### 3. Configure InfluxDB

1. Open `http://localhost:8086`, log in with the credentials set in `docker-compose.yml`.
2. Go to **Load Data → API Tokens**, generate an **All Access API Token**.
3. Paste it into your `.env` file.

### 4. Flash the ESP32 firmware

1. Open `firmware/esp32_vibration_publisher/esp32_vibration_publisher.ino` in Arduino IDE.
2. Fill in your WiFi SSID/password and your computer's local IP address (`ipconfig` / `ifconfig`) for `mqtt_server`.
3. Select **Board: ESP32 Dev Module**, select the correct COM port, and upload.
4. Open Serial Monitor (115200 baud) to confirm `IMU OK` and `Connected to MQTT broker`.

### 5. Install Python dependencies and run the bridge

```bash
cd backend
pip install -r requirements.txt   # or: pip install paho-mqtt influxdb-client python-dotenv pandas scikit-learn scipy joblib numpy
python bridge.py
```

You should see live `Wrote point:` messages streaming in as the fan runs.

### 6. Set up Grafana

1. Open `http://localhost:3011`, log in (`admin`/`admin` by default, then set a new password).
2. **Connections → Data sources → Add data source → InfluxDB**: Query language `Flux`, URL `http://influxdb:8086`, Org and Token from your `.env`, default bucket `vibration`.
3. Create a dashboard with two panels:
   - **Time series**: raw `ax`/`ay`/`az` (use `aggregateWindow()` if querying long time ranges, to avoid Grafana's point-count limit)
   - **Gauge**: `health` score, thresholds red < 50 / yellow 50–75 / green > 75

## Training the model

Pre-trained model files are included in `models/`. To retrain from scratch on the included data:

```bash
cd backend
python train_model.py       # trains on data/baseline_normal.csv
python validate_model.py    # validates against data/fault_imbalance.csv
```

To collect your own data instead:
```bash
python export_influx.py -10m now() ../data/baseline_normal.csv   # after a clean, undisturbed baseline recording
python export_influx.py -10m now() ../data/fault_imbalance.csv   # after inducing a fault (e.g. taping a weight to one blade)
```

## How fault detection works

1. Raw `ax`/`ay`/`az` samples are combined into a single vibration magnitude per sample.
2. Every 5 seconds of samples are reduced to 5 statistical features: RMS, kurtosis, crest factor, standard deviation, and dominant FFT frequency.
3. Isolation Forest is trained **only on healthy baseline windows** — no labeled fault data needed. It learns the "shape" of normal vibration by measuring how easily each point can be isolated from its neighbors via random splits.
4. Anomalous windows (physically different from anything seen in training) get isolated in fewer splits, producing a lower anomaly score — this is mapped to a 0–100 health score shown live on the dashboard.

## Results

| Metric | Value |
|---|---|
| Baseline windows trained on | 103 (5-second windows, ~100Hz sample rate) |
| Baseline score range | -0.166 to 0.305 |
| Fault detection rate | 100% of fault windows flagged anomalous |
| Fault score range | -0.154 to -0.053 |
| Baseline magnitude std | 0.136 |
| Fault magnitude std | 0.678 (~5x higher) |

## Known limitations

- Validated against one fault type (blade imbalance) — generalization to other fault modes (bearing wear, misalignment) is untested.
- WiFi network stability affects data continuity; power-saving WiFi behavior on some networks can introduce periodic throttling (mitigated via `WiFi.setSleep(false)` in the firmware).
- Effective sample rate depends on correct InfluxDB point timestamping — points without explicit timestamps can collide and silently overwrite each other under batched writes (see `bridge.py`: `.time(time.time_ns(), WritePrecision.NS)`).

## Project structure

```
├── docker-compose.yml       # Mosquitto + InfluxDB + Grafana stack
├── mosquitto/config/        # Broker configuration
├── firmware/                # ESP32 Arduino sketch
├── backend/                 # Python: MQTT bridge, feature extraction, training, export
├── data/                    # Collected baseline and fault CSV recordings
├── models/                  # Trained Isolation Forest model + score range
└── docs/                    # Architecture diagram, additional documentation
```

## Contributing

Issues and pull requests are welcome — particularly around additional fault types, alternative sensors, or improvements to the feature-extraction pipeline.

## License

MIT License — see `LICENSE` for details.
