"""
ESP32 Sensor Payload Validation and Data Models
Ensures strictly valid data ingestion from MAX30102, MPU6050, and BME280/BMP280.
"""

from typing import Optional, Dict, Any, Tuple
import datetime


class SensorValidationError(Exception):
    pass


def validate_float(val: Any, name: str, min_val: float, max_val: float, allow_none: bool = False) -> Optional[float]:
    if val is None:
        if allow_none:
            return None
        raise SensorValidationError(f"Field '{name}' cannot be null.")
    try:
        f_val = float(val)
    except (ValueError, TypeError):
        raise SensorValidationError(f"Field '{name}' must be a valid numeric value, got '{val}'.")
    
    if f_val < min_val or f_val > max_val:
        raise SensorValidationError(f"Field '{name}' value {f_val} is outside physical operating limits [{min_val}, {max_val}].")
    return f_val


def validate_int(val: Any, name: str, min_val: int, max_val: int, allow_none: bool = False) -> Optional[int]:
    if val is None:
        if allow_none:
            return None
        raise SensorValidationError(f"Field '{name}' cannot be null.")
    try:
        i_val = int(val)
    except (ValueError, TypeError):
        raise SensorValidationError(f"Field '{name}' must be an integer, got '{val}'.")
    
    if i_val < min_val or i_val > max_val:
        raise SensorValidationError(f"Field '{name}' value {i_val} is outside valid limits [{min_val}, {max_val}].")
    return i_val


def validate_sensor_payload(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Validates complete ESP32 payload against physical sensor limits and schema rules.
    Returns (cleaned_dict, error_message).
    """
    if not isinstance(data, dict):
        return {}, "Payload must be a valid JSON object."

    device_id = data.get("device_id")
    if not device_id or not isinstance(device_id, str):
        return {}, "Missing or invalid 'device_id'."

    timestamp_raw = data.get("timestamp")
    epoch_time = None
    if timestamp_raw:
        try:
            # Parse ISO-8601 or unix timestamp
            if isinstance(timestamp_raw, (int, float)):
                epoch_time = float(timestamp_raw)
                timestamp_str = datetime.datetime.fromtimestamp(epoch_time, tz=datetime.timezone.utc).isoformat()
            else:
                dt = datetime.datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
                epoch_time = dt.timestamp()
                timestamp_str = str(timestamp_raw)
        except Exception:
            epoch_time = datetime.datetime.now(datetime.timezone.utc).timestamp()
            timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    else:
        epoch_time = datetime.datetime.now(datetime.timezone.utc).timestamp()
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cleaned = {
        "device_id": device_id.strip(),
        "timestamp": timestamp_str,
        "epoch_time": epoch_time,
        "max30102": None,
        "mpu6050": None,
        "environment": None,
        "env_sensor_type": "UNKNOWN"
    }

    # 1. Validate MAX30102
    max_raw = data.get("max30102")
    if max_raw and isinstance(max_raw, dict):
        try:
            hr = validate_float(max_raw.get("heart_rate"), "heart_rate", 30.0, 240.0, allow_none=True)
            spo2 = validate_float(max_raw.get("spo2"), "spo2", 0.0, 100.0, allow_none=True)
            ir = validate_int(max_raw.get("ir"), "ir", 0, 262143, allow_none=True)
            red = validate_int(max_raw.get("red"), "red", 0, 262143, allow_none=True)
            sig_qual = validate_float(max_raw.get("signal_quality"), "signal_quality", 0.0, 100.0, allow_none=True)
            finger = bool(max_raw.get("finger_detected", False))

            cleaned["max30102"] = {
                "heart_rate": hr,
                "spo2": spo2,
                "ir": ir,
                "red": red,
                "signal_quality": sig_qual if sig_qual is not None else (90.0 if finger else 0.0),
                "finger_detected": finger
            }
        except SensorValidationError as e:
            return {}, f"MAX30102 validation error: {str(e)}"

    # 2. Validate MPU6050
    mpu_raw = data.get("mpu6050")
    if mpu_raw and isinstance(mpu_raw, dict):
        try:
            ax = validate_float(mpu_raw.get("accel_x"), "accel_x", -16.0, 16.0)
            ay = validate_float(mpu_raw.get("accel_y"), "accel_y", -16.0, 16.0)
            az = validate_float(mpu_raw.get("accel_z"), "accel_z", -16.0, 16.0)
            accel_mag = validate_float(mpu_raw.get("accel_magnitude"), "accel_magnitude", 0.0, 30.0, allow_none=True)

            gx = validate_float(mpu_raw.get("gyro_x"), "gyro_x", -2000.0, 2000.0)
            gy = validate_float(mpu_raw.get("gyro_y"), "gyro_y", -2000.0, 2000.0)
            gz = validate_float(mpu_raw.get("gyro_z"), "gyro_z", -2000.0, 2000.0)
            gyro_mag = validate_float(mpu_raw.get("gyro_magnitude"), "gyro_magnitude", 0.0, 4000.0, allow_none=True)
            activity = str(mpu_raw.get("activity", "STATIONARY")).upper()

            cleaned["mpu6050"] = {
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
        except SensorValidationError as e:
            return {}, f"MPU6050 validation error: {str(e)}"

    # 3. Validate BME280 / BMP280
    bme_raw = data.get("bme280")
    bmp_raw = data.get("bmp280")

    if bme_raw and isinstance(bme_raw, dict):
        try:
            temp = validate_float(bme_raw.get("temperature"), "temperature", -40.0, 85.0)
            press = validate_float(bme_raw.get("pressure"), "pressure", 300.0, 1100.0)
            hum = validate_float(bme_raw.get("humidity"), "humidity", 0.0, 100.0)

            cleaned["environment"] = {
                "temperature": temp,
                "pressure": press,
                "humidity": hum
            }
            cleaned["env_sensor_type"] = "BME280"
        except SensorValidationError as e:
            return {}, f"BME280 validation error: {str(e)}"

    elif bmp_raw and isinstance(bmp_raw, dict):
        try:
            temp = validate_float(bmp_raw.get("temperature"), "temperature", -40.0, 85.0)
            press = validate_float(bmp_raw.get("pressure"), "pressure", 300.0, 1100.0)
            # Humidity is explicitly not supported on BMP280
            cleaned["environment"] = {
                "temperature": temp,
                "pressure": press,
                "humidity": None
            }
            cleaned["env_sensor_type"] = "BMP280"
        except SensorValidationError as e:
            return {}, f"BMP280 validation error: {str(e)}"

    return cleaned, None
