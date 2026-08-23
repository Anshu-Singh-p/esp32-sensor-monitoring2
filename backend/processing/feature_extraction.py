"""
Stage 5 — Feature Extraction Module
Extracts physiologically and physically meaningful features from filtered sensor streams.
"""

import math
import time
from collections import deque
from typing import Dict, Any, Tuple


class FeatureExtractor:
    def __init__(self):
        # MPU6050 Multi-Stage Fall Event State Machine
        self.mpu_history = deque(maxlen=40)
        self.fall_state = "IDLE"
        self.impact_time = 0.0
        self.last_fall_event_time = 0.0

        # Rate of change tracking
        self.last_temp_sample = (0.0, 0.0) # (time, temp)
        self.last_press_sample = (0.0, 0.0) # (time, press)

    def extract_features(self, filtered_data: Dict[str, Any]) -> Dict[str, Any]:
        now = filtered_data.get("timestamp", time.time())
        extracted = dict(filtered_data)
        features = {}

        # 1. MAX30102 Features
        if filtered_data.get("max30102"):
            m = filtered_data["max30102"]
            finger = m.get("finger_detected", False)
            ac_red = abs(m.get("ac_red", 0.0))
            ac_ir = abs(m.get("ac_ir", 0.0))
            dc_red = max(1.0, m.get("dc_red", 1.0))
            dc_ir = max(1.0, m.get("dc_ir", 1.0))

            sqi = 0.0
            calculated_spo2 = m.get("filtered_spo2")
            calculated_bpm = m.get("filtered_heart_rate")

            if finger:
                # Calculate Ratio of Ratios: R = (AC_red/DC_red) / (AC_ir/DC_ir)
                r_ratio = (ac_red / dc_red) / max(0.0001, (ac_ir / dc_ir))
                # Empirical SpO2: SpO2 = 110 - 25 * R
                derived_spo2 = min(100.0, max(70.0, 110.0 - 25.0 * r_ratio))
                
                if calculated_spo2 is None:
                    calculated_spo2 = round(derived_spo2, 1)

                # Signal Quality Index (SQI)
                snr = min(1.0, ac_ir / max(1.0, dc_ir * 0.05))
                sqi = round(min(100.0, max(50.0, 75.0 + snr * 25.0)), 1)
            else:
                sqi = 0.0
                calculated_spo2 = None
                calculated_bpm = None

            features["max30102"] = {
                "heart_rate": calculated_bpm,
                "spo2": calculated_spo2,
                "signal_quality_index": sqi,
                "finger_detected": finger,
                "contact_status": "GOOD" if finger and sqi >= 80 else ("POOR" if finger else "NO_CONTACT")
            }

        # 2. MPU6050 Features
        if filtered_data.get("mpu6050"):
            mpu = filtered_data["mpu6050"]
            ax = mpu.get("filtered_ax", mpu.get("accel_x", 0.0))
            ay = mpu.get("filtered_ay", mpu.get("accel_y", 0.0))
            az = mpu.get("filtered_az", mpu.get("accel_z", 1.0))
            gx = mpu.get("filtered_gx", mpu.get("gyro_x", 0.0))
            gy = mpu.get("filtered_gy", mpu.get("gyro_y", 0.0))
            gz = mpu.get("filtered_gz", mpu.get("gyro_z", 0.0))

            accel_mag = round(math.sqrt(ax**2 + ay**2 + az**2), 3)
            gyro_mag = round(math.sqrt(gx**2 + gy**2 + gz**2), 2)

            # Activity State
            delta_a = abs(accel_mag - 1.0)
            if delta_a > 1.2 or gyro_mag > 150.0:
                activity = "HIGH ACTIVITY"
            elif delta_a > 0.35 or gyro_mag > 50.0:
                activity = "NORMAL ACTIVITY"
            elif delta_a > 0.08 or gyro_mag > 12.0:
                activity = "LOW ACTIVITY"
            else:
                activity = "STATIONARY"

            # Multi-stage Fall Detection
            is_fall, fall_desc = self._evaluate_fall_event(accel_mag, gyro_mag, now)

            features["mpu6050"] = {
                "accel_x": ax, "accel_y": ay, "accel_z": az,
                "gyro_x": gx, "gyro_y": gy, "gyro_z": gz,
                "accel_magnitude": accel_mag,
                "gyro_magnitude": gyro_mag,
                "activity": activity,
                "fall_event": is_fall,
                "fall_description": fall_desc
            }

        # 3. Environment Features (BME280 / BMP280)
        if filtered_data.get("environment"):
            env = filtered_data["environment"]
            t = env.get("filtered_temperature", env.get("temperature"))
            p = env.get("filtered_pressure", env.get("pressure"))
            h = env.get("filtered_humidity", env.get("humidity"))

            # Calculate rate of temperature change (°C / min)
            temp_rate = 0.0
            if self.last_temp_sample[0] > 0 and t is not None:
                dt_min = (now - self.last_temp_sample[0]) / 60.0
                if dt_min > 0.05:
                    temp_rate = round((t - self.last_temp_sample[1]) / dt_min, 2)
            if t is not None:
                self.last_temp_sample = (now, t)

            features["environment"] = {
                "temperature": t,
                "pressure": p,
                "humidity": h,
                "rate_of_temp_change_c_min": temp_rate,
                "sensor_type": env.get("type", "BME280")
            }

        extracted["features"] = features
        return extracted

    def _evaluate_fall_event(self, accel_mag: float, gyro_mag: float, current_time: float) -> Tuple[bool, str]:
        if current_time - self.last_fall_event_time < 10.0:
            return False, "COOLDOWN"

        self.mpu_history.append((current_time, accel_mag, gyro_mag))

        if self.fall_state == "IDLE":
            if accel_mag > 2.6 or accel_mag < 0.4:
                self.fall_state = "STAGE1_IMPACT"
                self.impact_time = current_time

        elif self.fall_state == "STAGE1_IMPACT":
            elapsed = current_time - self.impact_time
            if elapsed > 1.2:
                self.fall_state = "IDLE"
            elif gyro_mag > 140.0:
                self.fall_state = "STAGE2_ROTATION"

        elif self.fall_state == "STAGE2_ROTATION":
            elapsed = current_time - self.impact_time
            if elapsed > 4.5:
                self.fall_state = "IDLE"
            elif elapsed >= 1.5:
                recent_samples = [s for s in self.mpu_history if s[0] >= current_time - 1.5]
                if recent_samples:
                    max_gyro = max(s[2] for s in recent_samples)
                    avg_accel = sum(s[1] for s in recent_samples) / len(recent_samples)
                    if max_gyro < 20.0 and 0.75 <= avg_accel <= 1.25:
                        self.fall_state = "IDLE"
                        self.last_fall_event_time = current_time
                        return True, "Possible Fall / Sudden Motion Event: Impact, rotation, and resting state confirmed."

        return False, self.fall_state


feature_extractor = FeatureExtractor()
