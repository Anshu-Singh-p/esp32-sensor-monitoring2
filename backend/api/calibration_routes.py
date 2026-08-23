"""
API Calibration Endpoints (/api/v1/calibration)
Allows reading and updating calibration parameters per sensor.
"""

from typing import Dict, Any, Tuple
from processing.calibration import calibration_manager
from database.database import db


class CalibrationRoutes:
    def handle_get_calibration(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/calibration"""
        return 200, {
            "status": "success",
            "calibration": calibration_manager.get_all_calibrations()
        }

    def handle_update_calibration(self, sensor: str, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """PUT /api/v1/calibration/{sensor}"""
        valid_sensors = ["max30102", "mpu6050", "bme280_bmp280"]
        if sensor.lower() not in valid_sensors:
            return 400, {"error": f"Invalid sensor '{sensor}'. Must be one of {valid_sensors}."}

        if not isinstance(body, dict):
            return 400, {"error": "Request body must be a JSON dictionary of calibration parameters."}

        calibration_manager.set_calibration(sensor.lower(), body)
        return 200, {
            "status": "updated",
            "sensor": sensor.lower(),
            "current_calibration": calibration_manager.calibrations.get(sensor.lower())
        }


calibration_routes = CalibrationRoutes()
