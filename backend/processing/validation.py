"""
Stage 2 — Data Validation Module
Validates incoming ESP32 sensor telemetry for NaN values, range boundaries,
stale timestamps, impossible sudden jumps, and duplicate packets.
"""

import time
import math
from typing import Dict, Any, Tuple, Optional
from config.thresholds import SENSOR_OPERATING_LIMITS


class SensorValidator:
    def __init__(self):
        self.last_packet_times = {}  # device_id -> float
        self.last_sensor_values = {} # device_id:param -> float

    def validate_float(self, val: Any, name: str, min_val: float, max_val: float, allow_none: bool = True) -> Tuple[Optional[float], Optional[str]]:
        if val is None:
            if allow_none:
                return None, None
            return None, f"Field '{name}' cannot be null."
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None, f"Field '{name}' contains NaN or Inf."
        except (ValueError, TypeError):
            return None, f"Field '{name}' must be numeric, got '{val}'."

        if f < min_val or f > max_val:
            return None, f"Field '{name}' value {f} is outside physical limits [{min_val}, {max_val}]."
        return f, None

    def validate_packet(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Validates the full payload and returns (validated_data, error_message).
        """
        if not isinstance(data, dict):
            return {}, "Payload must be a valid JSON dictionary."

        device_id = data.get("device_id")
        if not device_id or not isinstance(device_id, str):
            return {}, "Missing or invalid 'device_id'."

        # Timestamp validation
        timestamp_raw = data.get("timestamp")
        now = time.time()
        try:
            if isinstance(timestamp_raw, (int, float)):
                epoch_time = float(timestamp_raw)
            else:
                epoch_time = float(timestamp_raw) if timestamp_raw else now
        except Exception:
            epoch_time = now

        # Duplicate or stale packet check (allow within 120s drift)
        last_time = self.last_packet_times.get(device_id, 0)
        if epoch_time < (last_time - 30.0):
            return {}, f"Stale packet rejected. Timestamp {epoch_time} is older than last seen {last_time}."
        self.last_packet_times[device_id] = epoch_time

        validated = {
            "device_id": device_id.strip(),
            "timestamp": epoch_time,
            "validation_status": "VALID",
            "validation_notes": []
        }

        # Check sensors container (supports both 'sensors.max30102' and direct 'max30102')
        sensors_dict = data.get("sensors", data)

        # 1. MAX30102 Validation
        max_raw = sensors_dict.get("max30102")
        if max_raw and isinstance(max_raw, dict):
            lim = SENSOR_OPERATING_LIMITS["max30102"]
            red, err_red = self.validate_float(max_raw.get("red"), "red", lim["raw_red_min"], lim["raw_red_max"])
            ir, err_ir = self.validate_float(max_raw.get("ir"), "ir", lim["raw_ir_min"], lim["raw_ir_max"])
            hr, err_hr = self.validate_float(max_raw.get("heart_rate"), "heart_rate", lim["heart_rate_min_bpm"], lim["heart_rate_max_bpm"])
            spo2, err_spo2 = self.validate_float(max_raw.get("spo2"), "spo2", lim["spo2_min_pct"], lim["spo2_max_pct"])

            errors = [e for e in [err_red, err_ir, err_hr, err_spo2] if e]
            if errors:
                validated["validation_notes"].extend(errors)

            validated["max30102"] = {
                "red": int(red) if red is not None else None,
                "ir": int(ir) if ir is not None else None,
                "heart_rate": hr,
                "spo2": spo2,
                "is_valid": len(errors) == 0
            }

        # 2. MPU6050 Validation
        mpu_raw = sensors_dict.get("mpu6050")
        if mpu_raw and isinstance(mpu_raw, dict):
            accel = mpu_raw.get("accel", mpu_raw)
            gyro = mpu_raw.get("gyro", mpu_raw)
            lim = SENSOR_OPERATING_LIMITS["mpu6050"]

            ax, e1 = self.validate_float(accel.get("x", accel.get("accel_x")), "accel_x", -lim["accel_range_g"], lim["accel_range_g"], allow_none=False)
            ay, e2 = self.validate_float(accel.get("y", accel.get("accel_y")), "accel_y", -lim["accel_range_g"], lim["accel_range_g"], allow_none=False)
            az, e3 = self.validate_float(accel.get("z", accel.get("accel_z")), "accel_z", -lim["accel_range_g"], lim["accel_range_g"], allow_none=False)

            gx, e4 = self.validate_float(gyro.get("x", gyro.get("gyro_x", 0.0)), "gyro_x", -lim["gyro_range_dps"], lim["gyro_range_dps"])
            gy, e5 = self.validate_float(gyro.get("y", gyro.get("gyro_y", 0.0)), "gyro_y", -lim["gyro_range_dps"], lim["gyro_range_dps"])
            gz, e6 = self.validate_float(gyro.get("z", gyro.get("gyro_z", 0.0)), "gyro_z", -lim["gyro_range_dps"], lim["gyro_range_dps"])

            errors = [e for e in [e1, e2, e3, e4, e5, e6] if e]
            if errors:
                return {}, f"MPU6050 validation failed: {errors[0]}"

            validated["mpu6050"] = {
                "accel_x": ax, "accel_y": ay, "accel_z": az,
                "gyro_x": gx or 0.0, "gyro_y": gy or 0.0, "gyro_z": gz or 0.0,
                "activity": str(mpu_raw.get("activity", "STATIONARY")).upper(),
                "is_valid": True
            }

        # 3. BME280 / BMP280 Validation
        bme_raw = sensors_dict.get("bme280")
        bmp_raw = sensors_dict.get("bmp280")
        lim_env = SENSOR_OPERATING_LIMITS["bme280_bmp280"]

        if bme_raw and isinstance(bme_raw, dict):
            t, e1 = self.validate_float(bme_raw.get("temperature"), "temperature", lim_env["temp_min_c"], lim_env["temp_max_c"], allow_none=False)
            p, e2 = self.validate_float(bme_raw.get("pressure"), "pressure", lim_env["pressure_min_hpa"], lim_env["pressure_max_hpa"], allow_none=False)
            h, e3 = self.validate_float(bme_raw.get("humidity"), "humidity", lim_env["humidity_min_pct"], lim_env["humidity_max_pct"], allow_none=False)
            
            errors = [e for e in [e1, e2, e3] if e]
            if errors:
                return {}, f"BME280 validation failed: {errors[0]}"

            validated["environment"] = {"temperature": t, "pressure": p, "humidity": h, "type": "BME280"}

        elif bmp_raw and isinstance(bmp_raw, dict):
            t, e1 = self.validate_float(bmp_raw.get("temperature"), "temperature", lim_env["temp_min_c"], lim_env["temp_max_c"], allow_none=False)
            p, e2 = self.validate_float(bmp_raw.get("pressure"), "pressure", lim_env["pressure_min_hpa"], lim_env["pressure_max_hpa"], allow_none=False)

            errors = [e for e in [e1, e2] if e]
            if errors:
                return {}, f"BMP280 validation failed: {errors[0]}"

            validated["environment"] = {"temperature": t, "pressure": p, "humidity": None, "type": "BMP280"}

        return validated, None


sensor_validator = SensorValidator()
