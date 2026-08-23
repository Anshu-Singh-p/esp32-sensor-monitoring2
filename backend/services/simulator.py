"""
ESP32 Hardware-Free Test Simulator
Generates exact telemetry streams matching MAX30102, MPU6050, and BME280/BMP280 sensors.
"""

import time
import math
import random
from typing import Dict, Any


class ESP32Simulator:
    def __init__(self):
        self.scenario = "NORMAL"
        self.tick = 0
        self.fall_step = 0
        self.device_id = "ESP32_01"

    def set_scenario(self, scenario_name: str) -> str:
        valid_scenarios = [
            "NORMAL", "HIGH_HR", "LOW_HR", "LOW_SPO2", "CRITICAL_SPO2",
            "HIGH_MOTION", "POSSIBLE_FALL", "HIGH_TEMP", "HIGH_HUMIDITY",
            "BMP280_MODE", "SENSOR_DISCONNECTED", "NO_FINGER"
        ]
        if scenario_name.upper() in valid_scenarios:
            self.scenario = scenario_name.upper()
        else:
            self.scenario = "NORMAL"
        self.fall_step = 0
        return self.scenario

    def generate_payload(self) -> Dict[str, Any]:
        self.tick += 1
        now_epoch = time.time()
        
        # Base realistic normal metrics
        hr = 74.0 + 3.0 * math.sin(self.tick * 0.2) + random.uniform(-0.5, 0.5)
        spo2 = 98.2 + 0.4 * math.cos(self.tick * 0.15) + random.uniform(-0.1, 0.1)
        raw_ir = 125000 + int(random.uniform(-1500, 1500))
        raw_red = 114000 + int(random.uniform(-1500, 1500))
        finger = True
        sig_qual = 95.0

        # MPU6050 Base (Stationary)
        ax = round(0.01 + random.uniform(-0.02, 0.02), 3)
        ay = round(0.02 + random.uniform(-0.02, 0.02), 3)
        az = round(0.99 + random.uniform(-0.02, 0.02), 3)
        gx = round(0.3 + random.uniform(-0.2, 0.2), 2)
        gy = round(0.2 + random.uniform(-0.2, 0.2), 2)
        gz = round(0.1 + random.uniform(-0.1, 0.1), 2)
        activity = "STATIONARY"

        # Environment Base (BME280)
        temp = round(24.5 + 0.5 * math.sin(self.tick * 0.05) + random.uniform(-0.1, 0.1), 1)
        press = round(1013.2 + random.uniform(-0.3, 0.3), 1)
        hum = round(52.0 + random.uniform(-0.5, 0.5), 1)
        env_is_bmp = False
        max30102_connected = True

        # Scenario overrides
        if self.scenario == "HIGH_HR":
            hr = 116.0 + random.uniform(-1.5, 2.5)
        elif self.scenario == "LOW_HR":
            hr = 49.0 + random.uniform(-1.0, 1.0)
        elif self.scenario == "LOW_SPO2":
            spo2 = 92.4 + random.uniform(-0.4, 0.4)
        elif self.scenario == "CRITICAL_SPO2":
            spo2 = 86.5 + random.uniform(-0.5, 0.5)
        elif self.scenario == "HIGH_MOTION":
            ax = round(0.85 + random.uniform(-0.3, 0.4), 3)
            ay = round(1.10 + random.uniform(-0.4, 0.4), 3)
            az = round(1.40 + random.uniform(-0.3, 0.3), 3)
            gx = round(145.0 + random.uniform(-20, 20), 2)
            gy = round(95.0 + random.uniform(-15, 15), 2)
            gz = round(70.0 + random.uniform(-10, 10), 2)
            activity = "HIGH ACTIVITY"
        elif self.scenario == "POSSIBLE_FALL":
            self.fall_step += 1
            if self.fall_step in [1, 2]:
                # Impact phase
                ax, ay, az = 1.9, 1.8, 2.4
                gx, gy, gz = 165.0, 185.0, 110.0
                activity = "HIGH ACTIVITY"
            elif self.fall_step in [3, 4, 5, 6, 7, 8]:
                # Inactivity / resting on ground
                ax, ay, az = 0.98, 0.05, 0.08  # lying sideways
                gx, gy, gz = 1.2, 0.8, 0.5
                activity = "STATIONARY"
            else:
                self.fall_step = 0
        elif self.scenario == "HIGH_TEMP":
            temp = 36.8 + random.uniform(-0.2, 0.3)
        elif self.scenario == "HIGH_HUMIDITY":
            hum = 78.5 + random.uniform(-0.5, 0.8)
        elif self.scenario == "BMP280_MODE":
            env_is_bmp = True
        elif self.scenario == "SENSOR_DISCONNECTED":
            max30102_connected = False
        elif self.scenario == "NO_FINGER":
            finger = False
            raw_ir = 9500
            raw_red = 8200
            hr = None
            spo2 = None
            sig_qual = 0.0

        payload = {
            "device_id": self.device_id,
            "timestamp": now_epoch,
            "api_key": "ESP32_SECURE_KEY_2026",
            "scenario": self.scenario
        }

        # MAX30102 block
        if max30102_connected:
            payload["max30102"] = {
                "heart_rate": round(hr, 1) if hr is not None else None,
                "spo2": round(spo2, 1) if spo2 is not None else None,
                "ir": raw_ir,
                "red": raw_red,
                "signal_quality": sig_qual,
                "finger_detected": finger
            }

        # MPU6050 block
        accel_mag = round(math.sqrt(ax**2 + ay**2 + az**2), 3)
        gyro_mag = round(math.sqrt(gx**2 + gy**2 + gz**2), 2)
        payload["mpu6050"] = {
            "accel_x": ax,
            "accel_y": ay,
            "accel_z": az,
            "accel_magnitude": accel_mag,
            "gyro_x": gx,
            "gyro_y": gy,
            "gyro_z": gz,
            "gyro_magnitude": gyro_mag,
            "activity": activity
        }

        # Environment block
        if env_is_bmp:
            payload["bmp280"] = {
                "temperature": temp,
                "pressure": press
            }
        else:
            payload["bme280"] = {
                "temperature": temp,
                "pressure": press,
                "humidity": hum
            }

        return payload


esp32_simulator = ESP32Simulator()
