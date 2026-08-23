"""
ESP32 Sensor Monitoring API Routes
Handles REST endpoints for ingestion, history, thresholds, alerts, and device status.
"""

import json
import time
from typing import Dict, Any, Tuple, Optional

from config.thresholds import DEFAULT_API_KEY, REFERENCE_BASELINES, SENSOR_OPERATING_LIMITS
from database.database import db
from models.sensor_models import validate_sensor_payload
from services.signal_quality import signal_quality_service
from services.sensor_processor import sensor_processor
from services.threshold_engine import threshold_engine
from services.alert_manager import alert_manager
from services.simulator import esp32_simulator


class SensorAPIRoutes:
    def __init__(self):
        self.api_key = DEFAULT_API_KEY

    def handle_ingest_sensor_data(self, headers: Dict[str, str], body_data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """
        POST /api/sensor-data
        Ingests ESP32 telemetry with authentication, validation, filtering, thresholding, and storage.
        """
        # 1. Authenticate Request
        auth_header = headers.get("x-api-key") or headers.get("X-API-Key")
        payload_key = body_data.get("api_key")
        if (not auth_header or auth_header != self.api_key) and (not payload_key or payload_key != self.api_key):
            return 401, {"error": "Unauthorized. Invalid or missing API key."}

        # 2. Validate Payload
        validated, err = validate_sensor_payload(body_data)
        if err:
            return 400, {"error": f"Invalid sensor payload: {err}"}

        device_id = validated["device_id"]

        # 3. Assess MAX30102 Signal Quality
        is_sig_valid = False
        sig_score = 0.0
        sig_status = "NO_DATA"
        if validated.get("max30102"):
            is_sig_valid, sig_score, sig_status = signal_quality_service.evaluate_max30102(validated["max30102"])
            validated["max30102"]["signal_quality"] = sig_score
            validated["max30102"]["signal_status"] = sig_status
            db.update_sensor_status(device_id, "MAX30102", "CONNECTED")
        else:
            db.update_sensor_status(device_id, "MAX30102", "DISCONNECTED")

        # 4. Update MPU6050 & Environment status
        if validated.get("mpu6050"):
            db.update_sensor_status(device_id, "MPU6050", "CONNECTED")
        else:
            db.update_sensor_status(device_id, "MPU6050", "DISCONNECTED")

        env_type = validated.get("env_sensor_type", "UNKNOWN")
        if env_type in ["BME280", "BMP280"]:
            db.update_sensor_status(device_id, env_type, "CONNECTED")

        # 5. Process Telemetry (Filtering, Derivations, Fall Detection)
        processed = sensor_processor.process_telemetry(validated)

        # 6. Run Threshold Engine
        threshold_evals = threshold_engine.evaluate_all(processed, is_sig_valid)

        # 7. Generate / Update Alerts
        new_alerts = alert_manager.process_threshold_results(device_id, threshold_evals, processed)

        # 8. Flatten and Persist to SQLite
        db_record = {
            "device_id": device_id,
            "timestamp": processed.get("timestamp"),
            "epoch_time": processed.get("epoch_time", time.time()),
            "env_sensor_type": processed.get("env_sensor_type")
        }

        if processed.get("max30102"):
            m = processed["max30102"]
            db_record["heart_rate"] = m.get("filtered_heart_rate", m.get("heart_rate"))
            db_record["spo2"] = m.get("filtered_spo2", m.get("spo2"))
            db_record["raw_ir"] = m.get("ir")
            db_record["raw_red"] = m.get("red")
            db_record["signal_quality"] = m.get("signal_quality")
            db_record["finger_detected"] = m.get("finger_detected")

        if processed.get("mpu6050"):
            mpu = processed["mpu6050"]
            db_record["accel_x"] = mpu.get("accel_x")
            db_record["accel_y"] = mpu.get("accel_y")
            db_record["accel_z"] = mpu.get("accel_z")
            db_record["accel_magnitude"] = mpu.get("accel_magnitude")
            db_record["gyro_x"] = mpu.get("gyro_x")
            db_record["gyro_y"] = mpu.get("gyro_y")
            db_record["gyro_z"] = mpu.get("gyro_z")
            db_record["gyro_magnitude"] = mpu.get("gyro_magnitude")
            db_record["activity"] = mpu.get("activity")
            db_record["fall_event"] = mpu.get("fall_event")

        if processed.get("environment"):
            env = processed["environment"]
            db_record["temperature"] = env.get("filtered_temperature", env.get("temperature"))
            db_record["humidity"] = env.get("filtered_humidity", env.get("humidity"))
            db_record["pressure"] = env.get("filtered_pressure", env.get("pressure"))

        db.insert_reading(db_record)
        db.update_device_heartbeat(device_id, True)

        response = {
            "status": "success",
            "device_id": device_id,
            "processed_telemetry": processed,
            "threshold_evaluations": threshold_evals,
            "new_alerts_count": len(new_alerts),
            "timestamp": time.time()
        }
        return 200, response

    def handle_get_latest(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/sensor-data/latest"""
        latest = db.get_latest_reading()
        if not latest:
            return 200, {"status": "NO_DATA", "message": "No sensor readings recorded yet."}

        # Reconstruct structured response
        thresholds = threshold_engine.get_thresholds()
        sensor_statuses = db.get_sensor_statuses()
        active_alerts = db.get_alerts("ACTIVE", limit=20)

        # Build clean latest view
        resp = {
            "device_id": latest.get("device_id"),
            "timestamp": latest.get("timestamp"),
            "epoch_time": latest.get("epoch_time"),
            "is_online": (time.time() - (latest.get("epoch_time") or 0)) < 10.0,
            "env_sensor_type": latest.get("env_sensor_type", "BME280"),
            "max30102": {
                "heart_rate": latest.get("heart_rate"),
                "spo2": latest.get("spo2"),
                "raw_ir": latest.get("raw_ir"),
                "raw_red": latest.get("raw_red"),
                "signal_quality": latest.get("signal_quality"),
                "finger_detected": bool(latest.get("finger_detected")),
                "status": threshold_engine.current_states.get("heart_rate", "NORMAL")
            },
            "mpu6050": {
                "accel_x": latest.get("accel_x"),
                "accel_y": latest.get("accel_y"),
                "accel_z": latest.get("accel_z"),
                "accel_magnitude": latest.get("accel_magnitude"),
                "gyro_x": latest.get("gyro_x"),
                "gyro_y": latest.get("gyro_y"),
                "gyro_z": latest.get("gyro_z"),
                "gyro_magnitude": latest.get("gyro_magnitude"),
                "activity": latest.get("activity", "STATIONARY"),
                "fall_event": bool(latest.get("fall_event"))
            },
            "environment": {
                "temperature": latest.get("temperature"),
                "humidity": latest.get("humidity"),  # None for BMP280
                "pressure": latest.get("pressure"),
                "temp_status": threshold_engine.current_states.get("temperature", "NORMAL"),
                "humidity_status": threshold_engine.current_states.get("humidity", "NORMAL") if latest.get("humidity") is not None else None,
                "pressure_status": threshold_engine.current_states.get("pressure", "NORMAL")
            },
            "sensor_statuses": sensor_statuses,
            "active_alerts": active_alerts
        }
        return 200, resp

    def handle_get_history(self, range_str: str = "5m") -> Tuple[int, Dict[str, Any]]:
        """GET /api/sensor-data/history?range=1m|5m|15m|1h|24h"""
        rows = db.get_history(range_str)
        return 200, {"range": range_str, "count": len(rows), "data": rows}

    def handle_get_alerts(self, status_filter: Optional[str] = None) -> Tuple[int, Dict[str, Any]]:
        """GET /api/alerts?status=ACTIVE|ACKNOWLEDGED|RESOLVED"""
        alerts = db.get_alerts(status_filter)
        return 200, {"alerts": alerts, "count": len(alerts)}

    def handle_update_alert_status(self, alert_id: str, new_status: str) -> Tuple[int, Dict[str, Any]]:
        """PUT /api/alerts/{id}/status"""
        if new_status not in ["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]:
            return 400, {"error": "Invalid status. Must be ACTIVE, ACKNOWLEDGED, or RESOLVED."}
        success = db.update_alert_status(alert_id, new_status)
        if success:
            return 200, {"status": "updated", "alert_id": alert_id, "new_status": new_status}
        return 404, {"error": f"Alert '{alert_id}' not found."}

    def handle_get_thresholds(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/thresholds"""
        active_th = threshold_engine.get_thresholds()
        return 200, {
            "configurable_thresholds": active_th,
            "reference_baselines": REFERENCE_BASELINES,
            "physical_sensor_limits": SENSOR_OPERATING_LIMITS
        }

    def handle_update_thresholds(self, body_data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """PUT /api/thresholds"""
        if not isinstance(body_data, dict):
            return 400, {"error": "Body must be a JSON object mapping parameters to threshold configurations."}

        for param, cfg in body_data.items():
            if isinstance(cfg, dict):
                db.save_threshold(param, cfg)

        return 200, {
            "status": "updated",
            "message": "Thresholds persisted to database.",
            "current_thresholds": threshold_engine.get_thresholds()
        }

    def handle_get_device_status(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/device/status"""
        latest = db.get_latest_reading()
        now = time.time()
        last_epoch = latest.get("epoch_time") if latest else 0
        seconds_ago = round(now - last_epoch, 1) if last_epoch else None
        is_online = (seconds_ago is not None and seconds_ago < 8.0)

        sensor_statuses = db.get_sensor_statuses()

        return 200, {
            "device_id": "ESP32_01",
            "status": "ONLINE" if is_online else "OFFLINE",
            "last_packet_seconds_ago": seconds_ago,
            "last_valid_timestamp": latest.get("timestamp") if latest else None,
            "sensors": sensor_statuses,
            "env_sensor_type": latest.get("env_sensor_type", "BME280") if latest else "BME280"
        }

    def handle_simulator_scenario(self, body_data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """POST /api/simulator/scenario"""
        scenario = body_data.get("scenario", "NORMAL")
        active = esp32_simulator.set_scenario(scenario)
        return 200, {"status": "scenario_set", "scenario": active}


sensor_api_routes = SensorAPIRoutes()
