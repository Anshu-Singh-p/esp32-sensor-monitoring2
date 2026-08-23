"""
ESP32 Sensor Monitoring Database Layer (SQLite)
Provides persistent storage for telemetry, alerts, devices, and threshold settings.
"""

import os
import sqlite3
import json
import time
from typing import Dict, List, Any, Optional

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sensor_monitor.db")


class Database:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes database schema and default tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Devices Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT,
                api_key TEXT,
                sensor_config TEXT,
                last_seen REAL,
                is_online INTEGER DEFAULT 0
            )
            """)

            # 2. Sensor Readings Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                epoch_time REAL NOT NULL,
                
                -- MAX30102
                heart_rate REAL,
                spo2 REAL,
                raw_ir INTEGER,
                raw_red INTEGER,
                signal_quality REAL,
                finger_detected INTEGER,
                
                -- MPU6050
                accel_x REAL,
                accel_y REAL,
                accel_z REAL,
                accel_magnitude REAL,
                gyro_x REAL,
                gyro_y REAL,
                gyro_z REAL,
                gyro_magnitude REAL,
                activity TEXT,
                fall_event INTEGER DEFAULT 0,
                
                -- BME280 / BMP280
                temperature REAL,
                humidity REAL,
                pressure REAL,
                env_sensor_type TEXT
            )
            """)

            # Index for fast time-series history queries
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_epoch ON sensor_readings(epoch_time)
            """)

            # 3. Alerts Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                sensor TEXT NOT NULL,
                parameter TEXT NOT NULL,
                value REAL,
                threshold_info TEXT,
                severity TEXT NOT NULL,
                timestamp REAL NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                resolved_at REAL
            )
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, timestamp)
            """)

            # 4. Threshold Settings Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS threshold_settings (
                parameter TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """)

            # 5. Sensor Status Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_status (
                device_id TEXT NOT NULL,
                sensor_name TEXT NOT NULL,
                status TEXT NOT NULL,
                last_valid_reading REAL,
                PRIMARY KEY (device_id, sensor_name)
            )
            """)

            # Seed default device if not present
            cursor.execute("SELECT device_id FROM devices WHERE device_id = 'ESP32_01'")
            if not cursor.fetchone():
                cursor.execute("""
                INSERT INTO devices (device_id, device_name, api_key, sensor_config, last_seen, is_online)
                VALUES ('ESP32_01', 'ESP32 Clinical-Grade Station', 'ESP32_SECURE_KEY_2026', '{"env_sensor":"BME280"}', ?, 1)
                """, (time.time(),))

            conn.commit()

    # ----------------- SENSOR READINGS -----------------

    def insert_reading(self, record: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO sensor_readings (
                device_id, timestamp, epoch_time,
                heart_rate, spo2, raw_ir, raw_red, signal_quality, finger_detected,
                accel_x, accel_y, accel_z, accel_magnitude,
                gyro_x, gyro_y, gyro_z, gyro_magnitude, activity, fall_event,
                temperature, humidity, pressure, env_sensor_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get("device_id", "ESP32_01"),
                record.get("timestamp", ""),
                record.get("epoch_time", time.time()),
                record.get("heart_rate"),
                record.get("spo2"),
                record.get("raw_ir"),
                record.get("raw_red"),
                record.get("signal_quality"),
                1 if record.get("finger_detected") else 0,
                record.get("accel_x"),
                record.get("accel_y"),
                record.get("accel_z"),
                record.get("accel_magnitude"),
                record.get("gyro_x"),
                record.get("gyro_y"),
                record.get("gyro_z"),
                record.get("gyro_magnitude"),
                record.get("activity"),
                1 if record.get("fall_event") else 0,
                record.get("temperature"),
                record.get("humidity"),
                record.get("pressure"),
                record.get("env_sensor_type", "BME280")
            ))
            conn.commit()
            return cursor.lastrowid

    def get_latest_reading(self, device_id: str = "ESP32_01") -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM sensor_readings WHERE device_id = ? ORDER BY epoch_time DESC LIMIT 1
            """, (device_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_history(self, range_str: str = "5m", device_id: str = "ESP32_01") -> List[Dict[str, Any]]:
        range_map = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "24h": 86400
        }
        duration_sec = range_map.get(range_str, 300)
        since_time = time.time() - duration_sec

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM sensor_readings 
            WHERE device_id = ? AND epoch_time >= ?
            ORDER BY epoch_time ASC
            """, (device_id, since_time))
            rows = cursor.fetchall()
            
            # If large dataset, downsample to max 120 points for smooth charting
            max_points = 120
            if len(rows) > max_points:
                step = len(rows) / max_points
                sampled = [dict(rows[int(i * step)]) for i in range(max_points)]
                return sampled
            return [dict(r) for r in rows]

    # ----------------- ALERTS -----------------

    def insert_alert(self, alert: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO alerts (
                id, device_id, sensor, parameter, value, threshold_info,
                severity, timestamp, status, message, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert["id"],
                alert.get("device_id", "ESP32_01"),
                alert["sensor"],
                alert["parameter"],
                alert.get("value"),
                json.dumps(alert.get("threshold_info", {})),
                alert["severity"],
                alert["timestamp"],
                alert.get("status", "ACTIVE"),
                alert["message"],
                alert.get("resolved_at")
            ))
            conn.commit()

    def get_alerts(self, status_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status_filter:
                cursor.execute("""
                SELECT * FROM alerts WHERE status = ? ORDER BY timestamp DESC LIMIT ?
                """, (status_filter, limit))
            else:
                cursor.execute("""
                SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            alerts = []
            for r in rows:
                item = dict(r)
                if item.get("threshold_info"):
                    try:
                        item["threshold_info"] = json.loads(item["threshold_info"])
                    except Exception:
                        pass
                alerts.append(item)
            return alerts

    def update_alert_status(self, alert_id: str, new_status: str) -> bool:
        resolved_time = time.time() if new_status == "RESOLVED" else None
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE alerts SET status = ?, resolved_at = ? WHERE id = ?
            """, (new_status, resolved_time, alert_id))
            conn.commit()
            return cursor.rowcount > 0

    # ----------------- THRESHOLDS -----------------

    def save_threshold(self, parameter: str, config: Dict[str, Any]):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO threshold_settings (parameter, config_json, updated_at)
            VALUES (?, ?, ?)
            """, (parameter, json.dumps(config), time.time()))
            conn.commit()

    def get_all_thresholds(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT parameter, config_json FROM threshold_settings")
            rows = cursor.fetchall()
            thresholds = {}
            for r in rows:
                thresholds[r["parameter"]] = json.loads(r["config_json"])
            return thresholds

    # ----------------- SENSOR & DEVICE STATUS -----------------

    def update_device_heartbeat(self, device_id: str, is_online: bool = True):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE devices SET last_seen = ?, is_online = ? WHERE device_id = ?
            """, (time.time(), 1 if is_online else 0, device_id))
            conn.commit()

    def update_sensor_status(self, device_id: str, sensor_name: str, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO sensor_status (device_id, sensor_name, status, last_valid_reading)
            VALUES (?, ?, ?, ?)
            """, (device_id, sensor_name, status, time.time() if status == "CONNECTED" else None))
            conn.commit()

    def get_sensor_statuses(self, device_id: str = "ESP32_01") -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sensor_name, status, last_valid_reading FROM sensor_status WHERE device_id = ?", (device_id,))
            rows = cursor.fetchall()
            return {r["sensor_name"]: {"status": r["status"], "last_valid_reading": r["last_valid_reading"]} for r in rows}


# Global database instance
db = Database()
