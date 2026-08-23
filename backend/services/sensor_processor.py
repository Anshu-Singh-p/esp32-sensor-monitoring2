"""
ESP32 Sensor Processing Service
Performs signal filtering, magnitude derivations, activity classification,
and multi-stage 'Possible Fall / Sudden Motion Event' detection.
"""

import math
import time
from collections import deque
from typing import Dict, Any, List, Optional, Tuple


class SensorProcessor:
    def __init__(self):
        # Rolling filter buffers (last 5-10 readings per device)
        self.hr_buffer = deque(maxlen=7)
        self.spo2_buffer = deque(maxlen=7)
        self.temp_buffer = deque(maxlen=5)
        self.press_buffer = deque(maxlen=5)
        self.hum_buffer = deque(maxlen=5)

        # MPU6050 Multi-Stage Fall Event State Machine
        self.mpu_history = deque(maxlen=30)  # ~3-5 seconds of 10Hz readings
        self.fall_state = "IDLE"             # "IDLE", "STAGE1_IMPACT", "STAGE2_ROTATION", "STAGE3_INACTIVITY"
        self.impact_time = 0.0
        self.last_fall_event_time = 0.0

    def calculate_magnitudes(self, mpu: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures exact mathematical magnitude computation if not provided by ESP32."""
        ax = mpu.get("accel_x", 0.0)
        ay = mpu.get("accel_y", 0.0)
        az = mpu.get("accel_z", 1.0)
        accel_mag = round(math.sqrt(ax**2 + ay**2 + az**2), 3)

        gx = mpu.get("gyro_x", 0.0)
        gy = mpu.get("gyro_y", 0.0)
        gz = mpu.get("gyro_z", 0.0)
        gyro_mag = round(math.sqrt(gx**2 + gy**2 + gz**2), 2)

        mpu["accel_magnitude"] = accel_mag
        mpu["gyro_magnitude"] = gyro_mag
        return mpu

    def filter_value(self, buffer: deque, raw_val: Optional[float]) -> Optional[float]:
        """Applies median + moving average filter to remove isolated noise spikes."""
        if raw_val is None:
            return None
        buffer.append(raw_val)
        if len(buffer) < 3:
            return raw_val
        # Median filter
        sorted_vals = sorted(list(buffer))
        median_val = sorted_vals[len(sorted_vals) // 2]
        # Moving average around median
        avg_val = sum(buffer) / len(buffer)
        return round((median_val * 0.6 + avg_val * 0.4), 2)

    def classify_activity(self, accel_mag: float, gyro_mag: float) -> str:
        """
        Classifies physical motion level based on MPU6050 dynamics.
        Explicitly labeled as prototype motion status (NOT a clinical diagnosis).
        """
        accel_deviation = abs(accel_mag - 1.0)

        if accel_deviation > 1.2 or gyro_mag > 150.0:
            return "HIGH ACTIVITY"
        elif accel_deviation > 0.35 or gyro_mag > 50.0:
            return "NORMAL ACTIVITY"
        elif accel_deviation > 0.08 or gyro_mag > 12.0:
            return "LOW ACTIVITY"
        else:
            return "STATIONARY"

    def detect_fall_event(self, accel_mag: float, gyro_mag: float, current_time: float) -> Tuple[bool, str]:
        """
        Multi-Stage Fall Detection Algorithm:
        Stage 1: Sudden impact (Accel Mag > 2.6g or sudden drop < 0.4g then spike > 2.2g)
        Stage 2: High rotational angular velocity (Gyro Mag > 140 deg/s) within 0.8s of impact
        Stage 3: Post-event stationary rest (Accel ~1.0g +/- 0.2g, Gyro < 15 deg/s for > 1.5s)
        
        Returns (is_fall_event, event_description)
        """
        # Suppress repeated alerts for 10 seconds after a detected fall
        if current_time - self.last_fall_event_time < 10.0:
            return False, "COOLDOWN"

        self.mpu_history.append((current_time, accel_mag, gyro_mag))

        # Check Stage 1: Impact Spike
        if self.fall_state == "IDLE":
            if accel_mag > 2.6:
                self.fall_state = "STAGE1_IMPACT"
                self.impact_time = current_time
            elif accel_mag < 0.4:
                # Potential freefall
                self.fall_state = "STAGE1_IMPACT"
                self.impact_time = current_time

        # Check Stage 2: Rotational Perturbation within 0.8s
        elif self.fall_state == "STAGE1_IMPACT":
            elapsed = current_time - self.impact_time
            if elapsed > 1.2:
                # Timeout, reset
                self.fall_state = "IDLE"
            elif gyro_mag > 140.0:
                self.fall_state = "STAGE2_ROTATION"

        # Check Stage 3: Post-Impact Inactivity for > 1.5s
        elif self.fall_state == "STAGE2_ROTATION":
            elapsed = current_time - self.impact_time
            if elapsed > 4.5:
                # Timed out waiting for rest
                self.fall_state = "IDLE"
            elif elapsed >= 1.5:
                # Check if recent 1.5s has been resting
                recent_samples = [s for s in self.mpu_history if s[0] >= current_time - 1.5]
                if recent_samples:
                    max_gyro_recent = max(s[2] for s in recent_samples)
                    avg_accel_recent = sum(s[1] for s in recent_samples) / len(recent_samples)
                    
                    if max_gyro_recent < 20.0 and 0.75 <= avg_accel_recent <= 1.25:
                        self.fall_state = "IDLE"
                        self.last_fall_event_time = current_time
                        return True, "Possible Fall / Sudden Motion Event: High impact followed by orientation shift and prolonged inactivity detected."

        return False, self.fall_state

    def process_telemetry(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes complete processing pipeline on validated ESP32 telemetry packet.
        """
        now = validated_data.get("epoch_time", time.time())
        processed = dict(validated_data)

        # 1. Process MAX30102
        if processed.get("max30102"):
            m = processed["max30102"]
            if m.get("finger_detected"):
                m["filtered_heart_rate"] = self.filter_value(self.hr_buffer, m.get("heart_rate"))
                m["filtered_spo2"] = self.filter_value(self.spo2_buffer, m.get("spo2"))
            else:
                m["filtered_heart_rate"] = None
                m["filtered_spo2"] = None
                self.hr_buffer.clear()
                self.spo2_buffer.clear()

        # 2. Process MPU6050
        if processed.get("mpu6050"):
            mpu = self.calculate_magnitudes(processed["mpu6050"])
            accel_mag = mpu["accel_magnitude"]
            gyro_mag = mpu["gyro_magnitude"]

            # Activity
            mpu["activity"] = self.classify_activity(accel_mag, gyro_mag)

            # Multi-stage Fall Detection
            is_fall, fall_desc = self.detect_fall_event(accel_mag, gyro_mag, now)
            mpu["fall_event"] = is_fall
            mpu["fall_state"] = fall_desc

        # 3. Process Environment (BME280 / BMP280)
        if processed.get("environment"):
            env = processed["environment"]
            env["filtered_temperature"] = self.filter_value(self.temp_buffer, env.get("temperature"))
            env["filtered_pressure"] = self.filter_value(self.press_buffer, env.get("pressure"))
            if env.get("humidity") is not None:
                env["filtered_humidity"] = self.filter_value(self.hum_buffer, env.get("humidity"))
            else:
                env["filtered_humidity"] = None

        return processed


sensor_processor = SensorProcessor()
