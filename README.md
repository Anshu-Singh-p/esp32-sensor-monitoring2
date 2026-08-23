# 📡 ESP32 Full-Stack Sensor Monitoring & Threshold-Alert Dashboard

A complete, full-stack, real-time sensor monitoring and threshold-alert dashboard. An **ESP32** microcontroller collects data from three dedicated sensors over I²C, transmits the telemetry via Wi-Fi to a Python backend, where data is validated, filtered, evaluated against configurable thresholds, saved to an SQLite database, and streamed live via WebSocket/SSE to a clinical-grade web dashboard.

---

## 🔬 Strictly Monitored Sensors

1. **MAX30102**: Pulse oximetry & heart rate optical sensor (Heart Rate BPM, $\text{SpO}_2\%$, Raw IR, Raw Red, Signal Quality %, Finger Contact status).
2. **MPU6050**: 6-DOF inertial measurement unit (3-Axis Accelerometer $A_x, A_y, A_z$, Accel Magnitude, 3-Axis Gyroscope $G_x, G_y, G_z$, Gyro Magnitude, Activity Classification, Multi-stage "Possible Fall / Sudden Motion Event" detector).
3. **BME280 or BMP280**: Environmental atmospheric sensor (Ambient Temperature °C, Atmospheric Pressure hPa, and Relative Humidity % *only when BME280 is present*; automatically hidden for BMP280).

> [!NOTE]
> Unrelated parameters (such as ECG, blood pressure, glucose, respiratory rate, or AQI/CO2/VOC) are strictly excluded from the pipeline and dashboard.

---

## 🏗️ 1. System Architecture

```text
  ┌───────────────────────────────────────────────────────────┐
  │                      ESP32 HARDWARE                       │
  │  MAX30102 (PPG) • MPU6050 (6-DOF) • BME280/BMP280 (Env)  │
  └─────────────────────────────┬─────────────────────────────┘
                                │ Wi-Fi (HTTP POST JSON)
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │                   PYTHON BACKEND SERVER                   │
  │  ├── REST API Routing (POST /api/sensor-data, etc.)       │
  │  ├── Validation against Physical Operating Limits        │
  │  ├── Signal Quality & Optical Finger Detection            │
  │  ├── Noise Filters (Median + Moving Average)              │
  │  ├── Multi-Stage Fall & Motion Classifier                 │
  │  ├── Debounce (N-Sample) & Hysteresis Threshold Engine    │
  │  ├── Alert Manager (ACTIVE / ACKNOWLEDGED / RESOLVED)     │
  │  └── SQLite Database (sensor_readings, alerts, settings)  │
  └─────────────────────────────┬─────────────────────────────┘
                                │ Real-Time WebSocket / SSE
                                ▼
  ┌───────────────────────────────────────────────────────────┐
  │                     WEB DASHBOARD                         │
  │  ├── Live Vital Cards (HR, SpO2, Optical Quality)        │
  │  ├── Motion Grid (Accel, Gyro, Activity, Fall Banner)     │
  │  ├── Environmental Grid (Temp, Pressure, Auto-Hum)        │
  │  ├── Multi-Series Time-Series Graphs (1m to 24h)          │
  │  ├── Interactive Alert Queue & Hardware Status            │
  │  └── Threshold Configuration Modal & Simulator Controls   │
  └───────────────────────────────────────────────────────────┘
```

---

## 🔌 2. Hardware Requirements & Wiring

### Components
- **ESP32 Microcontroller** (ESP32-WROOM-32, NodeMCU ESP32, ESP32-S3, etc.)
- **MAX30102** Pulse Oximeter & Heart-Rate Sensor Module
- **MPU6050** 6-Axis Accelerometer & Gyroscope Module
- **BME280** (or **BMP280**) Sensor Module
- Jumper wires and breadboard

### Wiring Diagram (I²C Bus)

All three sensors share the standard ESP32 I²C bus:

| ESP32 Pin | Sensor Pin (MAX30102) | Sensor Pin (MPU6050) | Sensor Pin (BME280 / BMP280) |
| :--- | :--- | :--- | :--- |
| **3V3** | `VIN` / `VCC` | `VCC` | `VCC` |
| **GND** | `GND` | `GND` | `GND` |
| **GPIO 21** | `SDA` | `SDA` | `SDA` |
| **GPIO 22** | `SCL` | `SCL` | `SCL` |

---

## 📊 3. Sensor Specifications & Operating Limits

### MAX30102
- **Operating Limits**: Heart Rate $30 - 240\,\text{BPM}$, $\text{SpO}_2$ $0 - 100\%$, 18-bit ADC optical registers ($0 - 262,143$).
- **Contact Threshold**: Raw $\text{IR} \ge 40,000$ indicates skin placement. Readings below this threshold are marked `INVALID / NO CONTACT`.

### MPU6050
- **Operating Limits**: Full scale $\pm 16g$ acceleration, $\pm 2000^\circ/\text{s}$ gyroscope.
- **Formulas**:
  $$\text{Accel Magnitude} = \sqrt{A_x^2 + A_y^2 + A_z^2}$$
  $$\text{Gyro Magnitude} = \sqrt{G_x^2 + G_y^2 + G_z^2}$$

### BME280 / BMP280
- **BME280 Operating Limits**: Temperature $-40^\circ\text{C}$ to $+85^\circ\text{C}$, Pressure $300 - 1100\,\text{hPa}$, Humidity $0 - 100\%\,\text{RH}$.
- **BMP280 Operating Limits**: Temperature $-40^\circ\text{C}$ to $+85^\circ\text{C}$, Pressure $300 - 1100\,\text{hPa}$ (*No humidity sensor*).

---

## 🎯 4. Threshold & Anti-False-Alert Methodology

To prevent noisy single-sample false alarms, the system implements a strict 3-tier validation:

1. **Debouncing / Consecutive-Sample Confirmation**:
   - An abnormal value must persist for a configurable number of consecutive samples (e.g. 4 samples for Heart Rate, 3 samples for $\text{SpO}_2$) before generating an active alert.
2. **Hysteresis Guard Bands**:
   - Once in an alert state, the reading must clear the threshold by a defined margin (e.g. $\pm 2\,\text{BPM}$ or $+1\%\,\text{SpO}_2$) before resetting to `NORMAL`.
3. **Signal Quality & Optical Contact Gating**:
   - If `finger_detected == False` or `signal_quality < 60%`, physiological alarms are suppressed and flagged as `INVALID / NO CONTACT`.

### Threshold Hierarchy Table

| Parameter | Reference Baseline (Adult Resting) | Configurable Project Default | Physical Sensor Limits |
| :--- | :--- | :--- | :--- |
| **Heart Rate** | $60 - 100\,\text{BPM}$ | Low: $60$, High: $100\,\text{BPM}$ | $30 - 240\,\text{BPM}$ |
| **$\text{SpO}_2$** | $\ge 95\%$ Normal, $90 - 94\%$ Caution | Caution: $90\%$, Normal: $95\%$ | $0 - 100\%$ |
| **Temperature** | $18 - 30^\circ\text{C}$ (Comfort) | Low: $18^\circ\text{C}$, High: $32^\circ\text{C}$ | $-40 - +85^\circ\text{C}$ |
| **Humidity (BME280)**| $30 - 60\%$ (Comfort) | Low: $30\%$, High: $65\%$ | $0 - 100\%$ |
| **Pressure** | $950 - 1050\,\text{hPa}$ (Barometric) | Low: $950$, High: $1050\,\text{hPa}$ | $300 - 1100\,\text{hPa}$ |

---

## 🤸 5. Multi-Stage Fall & Motion Logic (MPU6050)

Rather than triggering on raw acceleration spikes, a 3-stage temporal model is evaluated:
- **Stage 1 (Impact)**: $\text{Accel Magnitude} > 2.6g$ (or sudden dip $< 0.4g$ followed by spike).
- **Stage 2 (Rotational Perturbation)**: $\text{Gyro Magnitude} > 140^\circ/\text{s}$ within $1.2\,\text{s}$ of impact.
- **Stage 3 (Post-Event Inactivity)**: Accelerometer settles to $1.0g \pm 0.25g$ with minimal gyro activity ($< 20^\circ/\text{s}$) for $> 1.5\,\text{s}$.
- **Result**: Triggers **"Possible Fall / Sudden Motion Event"** warning.

---

## 💻 6. Backend Installation & Execution

### Prerequisites
- Python 3.9+ (Zero third-party pip dependencies required; uses pure Python standard library!).

### Running the Application

1. Open your terminal:
   ```bash
   cd /Users/anshusingh/.gemini/antigravity/scratch/edge-ai-health-companion
   ```

2. Run the quickstart launcher:
   ```bash
   python3 start.py
   ```
   *Or launch backend directly:*
   ```bash
   python3 backend/main.py 8080
   ```

3. Open your browser at:
   ```
   http://localhost:8080
   ```

---

## 🛠️ 7. Hardware-Free Testing Mode

The dashboard includes a built-in scenario generator with 12 presets to test every alert and layout feature without physical hardware:

- `NORMAL`: Resting healthy state.
- `HIGH_HR`: Tachycardia alert test ($> 100\,\text{BPM}$).
- `LOW_HR`: Bradycardia alert test ($< 60\,\text{BPM}$).
- `LOW_SPO2`: Caution oxygen alert test ($90 - 94\%$).
- `CRITICAL_SPO2`: Hypoxia critical alarm test ($< 90\%$).
- `HIGH_MOTION`: High activity inertial tracking.
- `POSSIBLE_FALL`: Impact $\rightarrow$ Rotation $\rightarrow$ Inactivity sequence.
- `HIGH_TEMP`: Thermal threshold alert.
- `HIGH_HUMIDITY`: High humidity warning.
- `BMP280_MODE`: Automatically omits humidity field and collapses UI card.
- `NO_FINGER`: Optical contact rejection test.
- `SENSOR_DISCONNECTED`: Hardware fault simulation.

### Running Automated Test Suite

```bash
python3 tests/test_suite.py
```

---

## 📡 8. REST API Documentation

### `POST /api/sensor-data`
Ingests ESP32 telemetry packet. Requires `X-API-Key: ESP32_SECURE_KEY_2026` header.

**JSON Payload Format (BME280 Example):**
```json
{
  "device_id": "ESP32_01",
  "timestamp": 1787480000.0,
  "api_key": "ESP32_SECURE_KEY_2026",
  "max30102": {
    "heart_rate": 82.0,
    "spo2": 98.0,
    "ir": 123456,
    "red": 112345,
    "signal_quality": 95.0,
    "finger_detected": true
  },
  "mpu6050": {
    "accel_x": 0.02,
    "accel_y": 0.01,
    "accel_z": 0.98,
    "accel_magnitude": 0.98,
    "gyro_x": 0.4,
    "gyro_y": 0.2,
    "gyro_z": 0.1,
    "gyro_magnitude": 0.46,
    "activity": "STATIONARY"
  },
  "bme280": {
    "temperature": 27.4,
    "humidity": 52.0,
    "pressure": 1008.4
  }
}
```

*(If BMP280 is used, replace `bme280` object with `bmp280` omitting the humidity field).*

### Other Endpoints
- `GET /api/sensor-data/latest`: Current snapshot, threshold evaluations, and device connection.
- `GET /api/sensor-data/history?range=1m|5m|15m|1h|24h`: Downsampled time-series for charts.
- `GET /api/alerts?status=ACTIVE|ACKNOWLEDGED|RESOLVED`: Alert queue.
- `PUT /api/alerts/<id>/status`: Update alert status (`{"status": "RESOLVED"}`).
- `GET /api/thresholds`: Returns active, baseline, and sensor limit definitions.
- `PUT /api/thresholds`: Updates threshold parameters in SQLite database.
- `GET /api/device/status`: ESP32 connection heartbeat and sensor connectivity.
- `GET /api/stream`: Real-time Server-Sent Events stream for instant dashboard sync.

---

## ⚠️ 9. Important Medical Disclaimer

> [!WARNING]
> **STUDENT / RESEARCH PROTOTYPE ONLY**: This system is designed solely for educational, engineering, and experimental monitoring purposes. It is **NOT** a certified medical diagnostic device and cannot diagnose, treat, or prevent any illness or disease. MAX30102 readings are optical estimates subject to placement, skin pigmentation, ambient lighting, and motion artifacts.
