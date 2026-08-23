# ESP32 Sensor Acquisition & Communication Firmware

This directory contains the production Arduino/ESP32 C++ firmware for reading data from **MAX30102**, **MPU6050**, and **BME280/BMP280** over I²C and transmitting the telemetry directly to the backend processing pipeline.

---

## 🔌 Hardware Wiring Guide

All 3 sensors communicate across the standard ESP32 I²C bus pins:

| ESP32 Pin | MAX30102 Pin | MPU6050 Pin | BME280 / BMP280 Pin |
| :--- | :--- | :--- | :--- |
| **3V3** | `VCC` / `VIN` | `VCC` | `VCC` |
| **GND** | `GND` | `GND` | `GND` |
| **GPIO 21** | `SDA` | `SDA` | `SDA` |
| **GPIO 22** | `SCL` | `SCL` | `SCL` |

---

## 📦 Required Arduino Libraries

Install the following libraries via the Arduino IDE Library Manager or PlatformIO:

1. **`ArduinoJson`** by Benoît Blanchon (v6.x or v7.x)
2. **`SparkFun MAX3010x Pulse and Proximity Sensor Library`** by SparkFun Electronics
3. **`Adafruit MPU6050`** by Adafruit
4. **`Adafruit BME280 Library`** by Adafruit
5. **`Adafruit BMP280 Library`** by Adafruit
6. **`Adafruit Unified Sensor`** by Adafruit

---

## ⚙️ Configuration & Flashing

1. Open [`include/config.h`](file:///Users/anshusingh/.gemini/antigravity/scratch/edge-ai-health-companion/esp32/include/config.h).
2. Set your Wi-Fi credentials:
   ```cpp
   #define WIFI_SSID     "YOUR_WIFI_SSID"
   #define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
   ```
3. Set your backend server IP address:
   ```cpp
   #define SERVER_INGEST_URL "http://YOUR_SERVER_IP:8080/api/v1/sensor-data"
   ```
4. Connect your ESP32 via USB and upload [`src/main.cpp`](file:///Users/anshusingh/.gemini/antigravity/scratch/edge-ai-health-companion/esp32/src/main.cpp).
5. Open the Serial Monitor at **115200 baud** to view real-time initialization and HTTP transmission logs.
