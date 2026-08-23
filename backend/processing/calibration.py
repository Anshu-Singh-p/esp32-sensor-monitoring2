"""
Stage 3 — Calibration Module
Applies configurable offset and scale calibration parameters to validated raw sensor streams:
corrected_value = (raw_value - offset) * scale
"""

from typing import Dict, Any, Optional

DEFAULT_CALIBRATION = {
    "max30102": {
        "red_offset": 0.0,
        "red_scale": 1.0,
        "ir_offset": 0.0,
        "ir_scale": 1.0,
        "contact_ir_threshold": 40000.0
    },
    "mpu6050": {
        "ax_offset": 0.0,
        "ax_scale": 1.0,
        "ay_offset": 0.0,
        "ay_scale": 1.0,
        "az_offset": 0.0,
        "az_scale": 1.0,
        "gx_offset": 0.0,
        "gy_offset": 0.0,
        "gz_offset": 0.0
    },
    "bme280_bmp280": {
        "temp_offset": 0.0,
        "temp_scale": 1.0,
        "press_offset": 0.0,
        "press_scale": 1.0,
        "hum_offset": 0.0,
        "hum_scale": 1.0
    }
}


class CalibrationManager:
    def __init__(self):
        self.calibrations = dict(DEFAULT_CALIBRATION)

    def set_calibration(self, sensor: str, params: Dict[str, Any]):
        if sensor in self.calibrations:
            self.calibrations[sensor].update(params)
        else:
            self.calibrations[sensor] = params

    def get_all_calibrations(self) -> Dict[str, Any]:
        return self.calibrations

    def calibrate(self, validated_data: Dict[str, Any]) -> Dict[str, Any]:
        calibrated = dict(validated_data)

        # 1. Calibrate MAX30102
        if validated_data.get("max30102"):
            m_raw = validated_data["max30102"]
            c_cfg = self.calibrations.get("max30102", DEFAULT_CALIBRATION["max30102"])
            
            cal_red = None
            if m_raw.get("red") is not None:
                cal_red = (m_raw["red"] - c_cfg.get("red_offset", 0.0)) * c_cfg.get("red_scale", 1.0)
            
            cal_ir = None
            if m_raw.get("ir") is not None:
                cal_ir = (m_raw["ir"] - c_cfg.get("ir_offset", 0.0)) * c_cfg.get("ir_scale", 1.0)

            contact_thresh = c_cfg.get("contact_ir_threshold", 40000.0)
            finger_detected = (cal_ir is not None and cal_ir >= contact_thresh)

            calibrated["max30102"] = {
                "raw_red": m_raw.get("red"),
                "raw_ir": m_raw.get("ir"),
                "cal_red": cal_red,
                "cal_ir": cal_ir,
                "heart_rate": m_raw.get("heart_rate"),
                "spo2": m_raw.get("spo2"),
                "finger_detected": finger_detected
            }

        # 2. Calibrate MPU6050
        if validated_data.get("mpu6050"):
            mpu = validated_data["mpu6050"]
            c_cfg = self.calibrations.get("mpu6050", DEFAULT_CALIBRATION["mpu6050"])

            cal_ax = (mpu["accel_x"] - c_cfg.get("ax_offset", 0.0)) * c_cfg.get("ax_scale", 1.0)
            cal_ay = (mpu["accel_y"] - c_cfg.get("ay_offset", 0.0)) * c_cfg.get("ay_scale", 1.0)
            cal_az = (mpu["accel_z"] - c_cfg.get("az_offset", 0.0)) * c_cfg.get("az_scale", 1.0)

            cal_gx = mpu["gyro_x"] - c_cfg.get("gx_offset", 0.0)
            cal_gy = mpu["gyro_y"] - c_cfg.get("gy_offset", 0.0)
            cal_gz = mpu["gyro_z"] - c_cfg.get("gz_offset", 0.0)

            calibrated["mpu6050"] = {
                "raw_ax": mpu["accel_x"], "raw_ay": mpu["accel_y"], "raw_az": mpu["accel_z"],
                "accel_x": round(cal_ax, 3),
                "accel_y": round(cal_ay, 3),
                "accel_z": round(cal_az, 3),
                "gyro_x": round(cal_gx, 2),
                "gyro_y": round(cal_gy, 2),
                "gyro_z": round(cal_gz, 2),
                "activity": mpu.get("activity", "STATIONARY")
            }

        # 3. Calibrate Environment (BME280 / BMP280)
        if validated_data.get("environment"):
            env = validated_data["environment"]
            c_cfg = self.calibrations.get("bme280_bmp280", DEFAULT_CALIBRATION["bme280_bmp280"])

            cal_t = (env["temperature"] - c_cfg.get("temp_offset", 0.0)) * c_cfg.get("temp_scale", 1.0)
            cal_p = (env["pressure"] - c_cfg.get("press_offset", 0.0)) * c_cfg.get("press_scale", 1.0)
            cal_h = None
            if env.get("humidity") is not None:
                cal_h = (env["humidity"] - c_cfg.get("hum_offset", 0.0)) * c_cfg.get("hum_scale", 1.0)

            calibrated["environment"] = {
                "raw_temperature": env["temperature"],
                "raw_pressure": env["pressure"],
                "raw_humidity": env.get("humidity"),
                "temperature": round(cal_t, 2),
                "pressure": round(cal_p, 2),
                "humidity": round(cal_h, 2) if cal_h is not None else None,
                "type": env.get("type", "BME280")
            }

        return calibrated


calibration_manager = CalibrationManager()
