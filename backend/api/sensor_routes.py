"""
Stage 1 & Main API Sensor Routes (/api/v1/...)
Coordinates Reception, Validation, Calibration, Filtering, Feature Extraction,
Threshold Evaluation, Storage, and Real-Time Telemetry Broadcasting.
"""

import time
from typing import Dict, Any, Tuple, Optional

from config.thresholds import DEFAULT_API_KEY
from processing.validation import sensor_validator
from processing.calibration import calibration_manager
from processing.filtering import sensor_filter_engine
from processing.feature_extraction import feature_extractor
from threshold.threshold_engine import research_threshold_engine
from services.alert_manager import alert_manager
from services.simulator import esp32_simulator
from database.database import db


class SensorAPIRoutes:
    def __init__(self):
        self.api_key = DEFAULT_API_KEY
        self.start_time = time.time()
        self.packet_count = 0

    def handle_ingest_sensor_data(self, headers: Dict[str, str], body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """POST /api/v1/sensor-data"""
        # Stage 1: Reception & Device Authentication
        auth_header = headers.get("x-api-key") or headers.get("X-API-Key")
        payload_key = body.get("api_key")
        if (not auth_header or auth_header != self.api_key) and (not payload_key or payload_key != self.api_key):
            return 401, {"error": "Unauthorized: Missing or invalid API key."}

        # Stage 2: Data Validation
        validated, val_err = sensor_validator.validate_packet(body)
        if val_err:
            return 400, {"status": "invalid", "reason": val_err}

        device_id = validated["device_id"]
        self.packet_count += 1

        # Stage 3: Calibration
        calibrated = calibration_manager.calibrate(validated)

        # Stage 4: Filtering
        filtered = sensor_filter_engine.filter_telemetry(calibrated)

        # Stage 5: Feature Extraction
        extracted = feature_extractor.extract_features(filtered)

        # Stage 6: Threshold Evaluation
        threshold_evals = research_threshold_engine.evaluate_features(extracted)

        # Stage 7: Alert Generation & Database Storage
        new_alerts = alert_manager.process_threshold_results(device_id, threshold_evals, extracted.get("features", {}))

        features = extracted.get("features", {})
        m_feat = features.get("max30102", {})
        mpu_feat = features.get("mpu6050", {})
        env_feat = features.get("environment", {})

        db_record = {
            "device_id": device_id,
            "timestamp": str(validated.get("timestamp")),
            "epoch_time": validated.get("timestamp", time.time()),
            "heart_rate": m_feat.get("heart_rate"),
            "spo2": m_feat.get("spo2"),
            "raw_ir": calibrated.get("max30102", {}).get("raw_ir"),
            "raw_red": calibrated.get("max30102", {}).get("raw_red"),
            "signal_quality": m_feat.get("signal_quality_index"),
            "finger_detected": m_feat.get("finger_detected"),
            "accel_x": mpu_feat.get("accel_x"),
            "accel_y": mpu_feat.get("accel_y"),
            "accel_z": mpu_feat.get("accel_z"),
            "accel_magnitude": mpu_feat.get("accel_magnitude"),
            "gyro_x": mpu_feat.get("gyro_x"),
            "gyro_y": mpu_feat.get("gyro_y"),
            "gyro_z": mpu_feat.get("gyro_z"),
            "gyro_magnitude": mpu_feat.get("gyro_magnitude"),
            "activity": mpu_feat.get("activity"),
            "fall_event": mpu_feat.get("fall_event"),
            "temperature": env_feat.get("temperature"),
            "humidity": env_feat.get("humidity"),
            "pressure": env_feat.get("pressure"),
            "env_sensor_type": env_feat.get("sensor_type", "BME280")
        }

        db.insert_reading(db_record)
        db.update_device_heartbeat(device_id, True)

        # Sensor status tracking
        if "max30102" in validated:
            db.update_sensor_status(device_id, "MAX30102", "CONNECTED" if m_feat.get("finger_detected") else "NO_CONTACT")
        if "mpu6050" in validated:
            db.update_sensor_status(device_id, "MPU6050", "CONNECTED")
        if "environment" in validated:
            db.update_sensor_status(device_id, env_feat.get("sensor_type", "BME280"), "CONNECTED")

        return 200, {
            "status": "success",
            "device_id": device_id,
            "processed": extracted,
            "threshold_evaluations": threshold_evals,
            "new_alerts": len(new_alerts),
            "timestamp": time.time()
        }

    def handle_get_latest(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/readings/latest"""
        latest = db.get_latest_reading()
        if not latest:
            return 200, {"status": "NO_DATA", "message": "No sensor telemetry available."}

        active_alerts = db.get_alerts("ACTIVE", limit=15)
        sensor_statuses = db.get_sensor_statuses()
        now = time.time()
        last_epoch = latest.get("epoch_time", 0)
        is_online = (now - last_epoch) < 8.0

        resp = {
            "device_id": latest.get("device_id"),
            "timestamp": latest.get("timestamp"),
            "epoch_time": latest.get("epoch_time"),
            "is_online": is_online,
            "env_sensor_type": latest.get("env_sensor_type", "BME280"),
            "max30102": {
                "heart_rate": latest.get("heart_rate"),
                "spo2": latest.get("spo2"),
                "raw_ir": latest.get("raw_ir"),
                "raw_red": latest.get("raw_red"),
                "signal_quality": latest.get("signal_quality"),
                "finger_detected": bool(latest.get("finger_detected")),
                "status": research_threshold_engine.current_states.get("heart_rate", "NORMAL")
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
                "humidity": latest.get("humidity"),
                "pressure": latest.get("pressure"),
                "temp_status": research_threshold_engine.current_states.get("temperature", "NORMAL"),
                "pressure_status": research_threshold_engine.current_states.get("pressure", "NORMAL")
            },
            "active_alerts": active_alerts,
            "sensor_statuses": sensor_statuses
        }
        return 200, resp

    def handle_get_history(self, range_str: str = "5m") -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/readings/history"""
        rows = db.get_history(range_str)
        return 200, {
            "status": "success",
            "range": range_str,
            "count": len(rows),
            "readings": rows
        }

    def handle_get_devices(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/devices"""
        latest = db.get_latest_reading()
        now = time.time()
        is_online = (latest and (now - latest.get("epoch_time", 0)) < 8.0)
        
        devices = [{
            "device_id": "ESP32_01",
            "device_name": "ESP32 Clinical-Grade Station",
            "firmware_version": "v2.6.0-prod",
            "connection_status": "ONLINE" if is_online else "OFFLINE",
            "last_seen": latest.get("epoch_time") if latest else None,
            "sensors": ["MAX30102", "MPU6050", latest.get("env_sensor_type", "BME280") if latest else "BME280"]
        }]
        return 200, {"status": "success", "devices": devices}

    def handle_get_device_detail(self, device_id: str) -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/devices/{device_id}"""
        latest = db.get_latest_reading(device_id)
        if not latest:
            return 404, {"error": f"Device '{device_id}' not found."}
        
        sensor_statuses = db.get_sensor_statuses(device_id)
        now = time.time()
        is_online = (now - latest.get("epoch_time", 0)) < 8.0

        return 200, {
            "device_id": device_id,
            "device_name": "ESP32 Clinical-Grade Station",
            "status": "ONLINE" if is_online else "OFFLINE",
            "last_seen_epoch": latest.get("epoch_time"),
            "sensors": sensor_statuses,
            "latest_reading": latest
        }

    def handle_get_system_status(self) -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/system/status"""
        uptime_sec = round(time.time() - self.start_time, 1)
        latest = db.get_latest_reading()
        return 200, {
            "system_status": "OPERATIONAL",
            "uptime_seconds": uptime_sec,
            "total_packets_processed": self.packet_count,
            "esp32_connected": (latest and (time.time() - latest.get("epoch_time", 0)) < 8.0),
            "simulator_active": True,
            "database": "SQLite (sensor_monitor.db)",
            "pipeline_stages": 8
        }

    def handle_simulator_scenario(self, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """POST /api/v1/simulator/scenario"""
        scenario = body.get("scenario", "NORMAL")
        active = esp32_simulator.set_scenario(scenario)
        return 200, {"status": "scenario_set", "scenario": active}


sensor_api_routes = SensorAPIRoutes()
