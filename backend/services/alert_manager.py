"""
ESP32 Alert Manager Service
Manages alert generation, lifecycle (ACTIVE, ACKNOWLEDGED, RESOLVED),
deduplication, and database persistence.
"""

import time
import uuid
from typing import Dict, Any, List, Optional
from database.database import db


class AlertManager:
    def __init__(self):
        # In-memory tracking of currently active alerts: alert_key -> alert_dict
        self.active_alert_keys = {}

    def process_threshold_results(self, device_id: str, threshold_evals: Dict[str, Any], telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Translates threshold evaluation outcomes into structured alerts.
        """
        now = time.time()
        generated_alerts = []

        # 1. Heart Rate
        hr_eval = threshold_evals.get("heart_rate")
        if hr_eval and hr_eval.get("alert_triggered"):
            status = hr_eval["status"]
            val = hr_eval["value"]
            alert_type = "HIGH_HEART_RATE" if status == "HIGH" else "LOW_HEART_RATE"
            alert_key = f"{device_id}:MAX30102:{alert_type}"

            if alert_key not in self.active_alert_keys:
                alert = {
                    "id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "device_id": device_id,
                    "sensor": "MAX30102",
                    "parameter": "heart_rate",
                    "value": val,
                    "threshold_info": hr_eval.get("threshold_info"),
                    "severity": "WARNING",
                    "timestamp": now,
                    "status": "ACTIVE",
                    "message": f"Heart Rate ({int(val)} BPM) is {status} relative to configured threshold."
                }
                self.active_alert_keys[alert_key] = alert
                db.insert_alert(alert)
                generated_alerts.append(alert)
        else:
            # Auto-resolve if previously active
            self._auto_resolve(device_id, "MAX30102", ["HIGH_HEART_RATE", "LOW_HEART_RATE"])

        # 2. SpO2
        spo2_eval = threshold_evals.get("spo2")
        if spo2_eval and spo2_eval.get("alert_triggered"):
            status = spo2_eval["status"]
            val = spo2_eval["value"]
            alert_type = "CRITICAL_SPO2" if status == "CRITICAL" else "LOW_SPO2"
            severity = "CRITICAL" if status == "CRITICAL" else "WARNING"
            alert_key = f"{device_id}:MAX30102:{alert_type}"

            if alert_key not in self.active_alert_keys:
                alert = {
                    "id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "device_id": device_id,
                    "sensor": "MAX30102",
                    "parameter": "spo2",
                    "value": val,
                    "threshold_info": spo2_eval.get("threshold_info"),
                    "severity": severity,
                    "timestamp": now,
                    "status": "ACTIVE",
                    "message": f"SpO₂ level ({val}%) reached {status} monitoring threshold."
                }
                self.active_alert_keys[alert_key] = alert
                db.insert_alert(alert)
                generated_alerts.append(alert)
        else:
            self._auto_resolve(device_id, "MAX30102", ["CRITICAL_SPO2", "LOW_SPO2"])

        # 3. Possible Fall / Sudden Motion Event
        motion_eval = threshold_evals.get("motion_event")
        if motion_eval and motion_eval.get("alert_triggered"):
            alert_key = f"{device_id}:MPU6050:POSSIBLE_FALL_{int(now // 15)}"
            if alert_key not in self.active_alert_keys:
                mpu = telemetry.get("mpu6050", {})
                alert = {
                    "id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "device_id": device_id,
                    "sensor": "MPU6050",
                    "parameter": "motion_event",
                    "value": mpu.get("accel_magnitude"),
                    "threshold_info": {"type": "Multi-stage impact+rotation+inactivity"},
                    "severity": "CRITICAL",
                    "timestamp": now,
                    "status": "ACTIVE",
                    "message": "Possible Fall / Sudden Motion Event: High acceleration impact and angular displacement followed by resting inactivity."
                }
                self.active_alert_keys[alert_key] = alert
                db.insert_alert(alert)
                generated_alerts.append(alert)

        # 4. Temperature
        temp_eval = threshold_evals.get("temperature")
        if temp_eval and temp_eval.get("alert_triggered"):
            status = temp_eval["status"]
            val = temp_eval["value"]
            alert_type = "HIGH_TEMPERATURE" if status == "HIGH" else "LOW_TEMPERATURE"
            alert_key = f"{device_id}:BME280_BMP280:{alert_type}"

            if alert_key not in self.active_alert_keys:
                alert = {
                    "id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "device_id": device_id,
                    "sensor": telemetry.get("env_sensor_type", "BME280"),
                    "parameter": "temperature",
                    "value": val,
                    "threshold_info": temp_eval.get("threshold_info"),
                    "severity": "WARNING",
                    "timestamp": now,
                    "status": "ACTIVE",
                    "message": f"Ambient temperature ({val}°C) is {status} relative to configured limits."
                }
                self.active_alert_keys[alert_key] = alert
                db.insert_alert(alert)
                generated_alerts.append(alert)
        else:
            self._auto_resolve(device_id, "BME280_BMP280", ["HIGH_TEMPERATURE", "LOW_TEMPERATURE"])

        # 5. Humidity (BME280 only)
        hum_eval = threshold_evals.get("humidity")
        if hum_eval and hum_eval.get("alert_triggered"):
            status = hum_eval["status"]
            val = hum_eval["value"]
            alert_type = "HIGH_HUMIDITY" if status == "HIGH" else "LOW_HUMIDITY"
            alert_key = f"{device_id}:BME280:{alert_type}"

            if alert_key not in self.active_alert_keys:
                alert = {
                    "id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                    "device_id": device_id,
                    "sensor": "BME280",
                    "parameter": "humidity",
                    "value": val,
                    "threshold_info": hum_eval.get("threshold_info"),
                    "severity": "INFO",
                    "timestamp": now,
                    "status": "ACTIVE",
                    "message": f"Ambient relative humidity ({val}%) is {status} relative to configured range."
                }
                self.active_alert_keys[alert_key] = alert
                db.insert_alert(alert)
                generated_alerts.append(alert)
        else:
            self._auto_resolve(device_id, "BME280", ["HIGH_HUMIDITY", "LOW_HUMIDITY"])

        return generated_alerts

    def _auto_resolve(self, device_id: str, sensor: str, alert_types: List[str]):
        """Resolves active alerts when signal normalizes."""
        for at in alert_types:
            key = f"{device_id}:{sensor}:{at}"
            if key in self.active_alert_keys:
                old_alert = self.active_alert_keys.pop(key)
                db.update_alert_status(old_alert["id"], "RESOLVED")

    def register_sensor_disconnect_alert(self, device_id: str, sensor_name: str):
        alert_key = f"{device_id}:{sensor_name}:SENSOR_DISCONNECTED"
        if alert_key not in self.active_alert_keys:
            alert = {
                "id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
                "device_id": device_id,
                "sensor": sensor_name,
                "parameter": "sensor_connection",
                "value": 0,
                "threshold_info": {"status": "DISCONNECTED"},
                "severity": "WARNING",
                "timestamp": time.time(),
                "status": "ACTIVE",
                "message": f"Sensor '{sensor_name}' is disconnected or stopped transmitting valid packets."
            }
            self.active_alert_keys[alert_key] = alert
            db.insert_alert(alert)


alert_manager = AlertManager()
