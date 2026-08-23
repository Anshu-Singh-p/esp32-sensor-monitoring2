"""
API Threshold Endpoints (/api/v1/thresholds)
Allows reading and updating threshold parameters for physiological and environmental metrics.
"""

from typing import Dict, Any, Tuple
from threshold.threshold_engine import research_threshold_engine
from config.thresholds import REFERENCE_BASELINES, SENSOR_OPERATING_LIMITS
from database.database import db


class ThresholdRoutes:
    def handle_get_thresholds(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/thresholds"""
        return 200, {
            "status": "success",
            "thresholds": research_threshold_engine.thresholds,
            "reference_baselines": REFERENCE_BASELINES,
            "operating_limits": SENSOR_OPERATING_LIMITS
        }

    def handle_update_threshold(self, parameter: str, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """PUT /api/v1/thresholds/{parameter}"""
        valid_params = ["heart_rate", "spo2", "temperature", "humidity", "pressure", "motion"]
        if parameter.lower() not in valid_params:
            return 400, {"error": f"Invalid parameter '{parameter}'. Must be one of {valid_params}."}

        if not isinstance(body, dict):
            return 400, {"error": "Request body must be a JSON dictionary of threshold parameters."}

        research_threshold_engine.thresholds[parameter.lower()].update(body)
        db.save_threshold(parameter.lower(), research_threshold_engine.thresholds[parameter.lower()])

        return 200, {
            "status": "updated",
            "parameter": parameter.lower(),
            "current_thresholds": research_threshold_engine.thresholds.get(parameter.lower())
        }


threshold_routes = ThresholdRoutes()
