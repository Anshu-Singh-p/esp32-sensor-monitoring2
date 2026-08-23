"""
Stage 4 — Signal Filtering Module
Applies sensor-specific digital filtering to attenuate noise, remove DC baselines,
and smooth physiological and environmental waveforms.
"""

import math
from collections import deque
from typing import Dict, Any, Optional


class SensorFilterEngine:
    def __init__(self):
        # MAX30102 DC Baseline Trackers
        self.max_dc_red = 0.0
        self.max_dc_ir = 0.0
        self.dc_alpha = 0.95  # Exponential baseline tracking rate

        # MPU6050 Low-Pass Filter State (alpha = 0.3)
        self.mpu_filtered_ax = 0.0
        self.mpu_filtered_ay = 0.0
        self.mpu_filtered_az = 1.0
        self.mpu_filtered_gx = 0.0
        self.mpu_filtered_gy = 0.0
        self.mpu_filtered_gz = 0.0
        self.mpu_lpf_alpha = 0.35

        # Rolling buffers for moving averages
        self.hr_window = deque(maxlen=6)
        self.spo2_window = deque(maxlen=6)
        self.temp_window = deque(maxlen=5)
        self.press_window = deque(maxlen=5)
        self.hum_window = deque(maxlen=5)

    def filter_telemetry(self, calibrated_data: Dict[str, Any]) -> Dict[str, Any]:
        filtered = dict(calibrated_data)

        # 1. Filter MAX30102
        if calibrated_data.get("max30102"):
            m = calibrated_data["max30102"]
            cal_red = m.get("cal_red") or 0.0
            cal_ir = m.get("cal_ir") or 0.0

            # Dynamic DC Baseline Tracking & AC separation
            if self.max_dc_red == 0.0:
                self.max_dc_red = cal_red
                self.max_dc_ir = cal_ir
            else:
                self.max_dc_red = self.dc_alpha * self.max_dc_red + (1.0 - self.dc_alpha) * cal_red
                self.max_dc_ir = self.dc_alpha * self.max_dc_ir + (1.0 - self.dc_alpha) * cal_ir

            ac_red = cal_red - self.max_dc_red
            ac_ir = cal_ir - self.max_dc_ir

            # Smooth HR & SpO2
            raw_hr = m.get("heart_rate")
            filtered_hr = None
            if raw_hr is not None:
                self.hr_window.append(raw_hr)
                filtered_hr = round(sum(self.hr_window) / len(self.hr_window), 1)

            raw_spo2 = m.get("spo2")
            filtered_spo2 = None
            if raw_spo2 is not None:
                self.spo2_window.append(raw_spo2)
                filtered_spo2 = round(sum(self.spo2_window) / len(self.spo2_window), 1)

            filtered["max30102"]["dc_red"] = round(self.max_dc_red, 1)
            filtered["max30102"]["dc_ir"] = round(self.max_dc_ir, 1)
            filtered["max30102"]["ac_red"] = round(ac_red, 2)
            filtered["max30102"]["ac_ir"] = round(ac_ir, 2)
            filtered["max30102"]["filtered_heart_rate"] = filtered_hr
            filtered["max30102"]["filtered_spo2"] = filtered_spo2

        # 2. Filter MPU6050 (Low-Pass Filter)
        if calibrated_data.get("mpu6050"):
            mpu = calibrated_data["mpu6050"]
            ax, ay, az = mpu["accel_x"], mpu["accel_y"], mpu["accel_z"]
            gx, gy, gz = mpu["gyro_x"], mpu["gyro_y"], mpu["gyro_z"]
            a = self.mpu_lpf_alpha

            self.mpu_filtered_ax = a * ax + (1 - a) * self.mpu_filtered_ax
            self.mpu_filtered_ay = a * ay + (1 - a) * self.mpu_filtered_ay
            self.mpu_filtered_az = a * az + (1 - a) * self.mpu_filtered_az

            self.mpu_filtered_gx = a * gx + (1 - a) * self.mpu_filtered_gx
            self.mpu_filtered_gy = a * gy + (1 - a) * self.mpu_filtered_gy
            self.mpu_filtered_gz = a * gz + (1 - a) * self.mpu_filtered_gz

            filtered["mpu6050"]["filtered_ax"] = round(self.mpu_filtered_ax, 3)
            filtered["mpu6050"]["filtered_ay"] = round(self.mpu_filtered_ay, 3)
            filtered["mpu6050"]["filtered_az"] = round(self.mpu_filtered_az, 3)
            filtered["mpu6050"]["filtered_gx"] = round(self.mpu_filtered_gx, 2)
            filtered["mpu6050"]["filtered_gy"] = round(self.mpu_filtered_gy, 2)
            filtered["mpu6050"]["filtered_gz"] = round(self.mpu_filtered_gz, 2)

        # 3. Filter Environment (BME280 / BMP280)
        if calibrated_data.get("environment"):
            env = calibrated_data["environment"]
            t = env.get("temperature")
            p = env.get("pressure")
            h = env.get("humidity")

            if t is not None:
                self.temp_window.append(t)
                filtered["environment"]["filtered_temperature"] = round(sum(self.temp_window) / len(self.temp_window), 2)

            if p is not None:
                self.press_window.append(p)
                filtered["environment"]["filtered_pressure"] = round(sum(self.press_window) / len(self.press_window), 2)

            if h is not None:
                self.hum_window.append(h)
                filtered["environment"]["filtered_humidity"] = round(sum(self.hum_window) / len(self.hum_window), 2)
            else:
                filtered["environment"]["filtered_humidity"] = None

        return filtered


sensor_filter_engine = SensorFilterEngine()
