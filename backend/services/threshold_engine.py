"""
ESP32 Threshold Engine Service
Evaluates filtered telemetry against configurable thresholds using hysteresis,
debouncing, and consecutive-sample confirmation to eliminate false alarms.
"""

from typing import Dict, Any, List, Optional, Tuple
from config.thresholds import DEFAULT_THRESHOLDS
from database.database import db


class ThresholdEngine:
    def __init__(self):
        # Debounce counters: parameter -> count of consecutive abnormal readings
        self.debounce_counters = {
            "heart_rate_high": 0,
            "heart_rate_low": 0,
            "spo2_caution": 0,
            "spo2_critical": 0,
            "temp_high": 0,
            "temp_low": 0,
            "hum_high": 0,
            "hum_low": 0,
            "press_out": 0
        }
        # Hysteresis state tracking: parameter -> active state
        self.current_states = {
            "heart_rate": "NORMAL",
            "spo2": "NORMAL",
            "temperature": "NORMAL",
            "humidity": "NORMAL",
            "pressure": "NORMAL"
        }

    def get_thresholds(self) -> Dict[str, Any]:
        """Loads thresholds from DB with fallback to default configurations."""
        saved = db.get_all_thresholds()
        merged = {}
        for param, default_cfg in DEFAULT_THRESHOLDS.items():
            merged[param] = saved.get(param, default_cfg)
        return merged

    def evaluate_heart_rate(self, hr: Optional[float], finger: bool, sig_valid: bool, cfg: Dict[str, Any]) -> Dict[str, Any]:
        if not finger or not sig_valid or hr is None:
            self.debounce_counters["heart_rate_high"] = 0
            self.debounce_counters["heart_rate_low"] = 0
            self.current_states["heart_rate"] = "INVALID / NO CONTACT"
            return {
                "parameter": "heart_rate",
                "value": hr,
                "status": "INVALID / NO CONTACT",
                "alert_triggered": False,
                "threshold_info": cfg
            }

        low_th = cfg.get("low_threshold", 60.0)
        high_th = cfg.get("high_threshold", 100.0)
        hyst = cfg.get("hysteresis", 2.0)
        debounce_req = cfg.get("debounce_samples", 4)

        prev_state = self.current_states["heart_rate"]
        new_state = prev_state

        # Check High HR condition
        if hr > high_th:
            self.debounce_counters["heart_rate_high"] += 1
            self.debounce_counters["heart_rate_low"] = 0
            if self.debounce_counters["heart_rate_high"] >= debounce_req:
                new_state = "HIGH"
        # Check Low HR condition
        elif hr < low_th:
            self.debounce_counters["heart_rate_low"] += 1
            self.debounce_counters["heart_rate_high"] = 0
            if self.debounce_counters["heart_rate_low"] >= debounce_req:
                new_state = "LOW"
        # In-between / Normal (with hysteresis clearance)
        else:
            if prev_state == "HIGH" and hr <= (high_th - hyst):
                self.debounce_counters["heart_rate_high"] = 0
                new_state = "NORMAL"
            elif prev_state == "LOW" and hr >= (low_th + hyst):
                self.debounce_counters["heart_rate_low"] = 0
                new_state = "NORMAL"
            elif prev_state == "NORMAL" or prev_state == "INVALID / NO CONTACT":
                self.debounce_counters["heart_rate_high"] = 0
                self.debounce_counters["heart_rate_low"] = 0
                new_state = "NORMAL"

        self.current_states["heart_rate"] = new_state
        alert_triggered = new_state in ["HIGH", "LOW"]

        return {
            "parameter": "heart_rate",
            "value": hr,
            "status": new_state,
            "alert_triggered": alert_triggered,
            "consecutive_abnormal": max(self.debounce_counters["heart_rate_high"], self.debounce_counters["heart_rate_low"]),
            "threshold_info": {
                "low_threshold": low_th,
                "high_threshold": high_th,
                "hysteresis": hyst
            }
        }

    def evaluate_spo2(self, spo2: Optional[float], finger: bool, sig_valid: bool, cfg: Dict[str, Any]) -> Dict[str, Any]:
        if not finger or not sig_valid or spo2 is None:
            self.debounce_counters["spo2_caution"] = 0
            self.debounce_counters["spo2_critical"] = 0
            self.current_states["spo2"] = "INVALID / NO CONTACT"
            return {
                "parameter": "spo2",
                "value": spo2,
                "status": "INVALID / NO CONTACT",
                "alert_triggered": False,
                "threshold_info": cfg
            }

        norm_min = cfg.get("normal_min", 95.0)
        caut_min = cfg.get("caution_min", 90.0)
        hyst = cfg.get("hysteresis", 1.0)
        debounce_req = cfg.get("debounce_samples", 3)

        prev_state = self.current_states["spo2"]
        new_state = prev_state

        if spo2 < caut_min:
            self.debounce_counters["spo2_critical"] += 1
            self.debounce_counters["spo2_caution"] = 0
            if self.debounce_counters["spo2_critical"] >= debounce_req:
                new_state = "CRITICAL"
        elif spo2 < norm_min:
            self.debounce_counters["spo2_caution"] += 1
            self.debounce_counters["spo2_critical"] = 0
            if self.debounce_counters["spo2_caution"] >= debounce_req:
                new_state = "CAUTION"
        else:
            if prev_state == "CRITICAL" and spo2 >= (caut_min + hyst):
                self.debounce_counters["spo2_critical"] = 0
                new_state = "CAUTION" if spo2 < norm_min else "NORMAL"
            elif prev_state == "CAUTION" and spo2 >= (norm_min + hyst):
                self.debounce_counters["spo2_caution"] = 0
                new_state = "NORMAL"
            elif prev_state == "NORMAL" or prev_state == "INVALID / NO CONTACT":
                self.debounce_counters["spo2_caution"] = 0
                self.debounce_counters["spo2_critical"] = 0
                new_state = "NORMAL"

        self.current_states["spo2"] = new_state
        alert_triggered = new_state in ["CAUTION", "CRITICAL"]

        return {
            "parameter": "spo2",
            "value": spo2,
            "status": new_state,
            "alert_triggered": alert_triggered,
            "consecutive_abnormal": max(self.debounce_counters["spo2_caution"], self.debounce_counters["spo2_critical"]),
            "threshold_info": {
                "normal_min": norm_min,
                "caution_min": caut_min,
                "hysteresis": hyst
            }
        }

    def evaluate_temperature(self, temp: Optional[float], cfg: Dict[str, Any]) -> Dict[str, Any]:
        if temp is None:
            return {"parameter": "temperature", "value": None, "status": "INVALID", "alert_triggered": False}

        low_th = cfg.get("low_threshold", 18.0)
        high_th = cfg.get("high_threshold", 32.0)
        debounce_req = cfg.get("debounce_samples", 3)

        if temp > high_th:
            self.debounce_counters["temp_high"] += 1
            self.debounce_counters["temp_low"] = 0
            status = "HIGH" if self.debounce_counters["temp_high"] >= debounce_req else "NORMAL"
        elif temp < low_th:
            self.debounce_counters["temp_low"] += 1
            self.debounce_counters["temp_high"] = 0
            status = "LOW" if self.debounce_counters["temp_low"] >= debounce_req else "NORMAL"
        else:
            self.debounce_counters["temp_high"] = 0
            self.debounce_counters["temp_low"] = 0
            status = "NORMAL"

        self.current_states["temperature"] = status
        return {
            "parameter": "temperature",
            "value": temp,
            "status": status,
            "alert_triggered": status in ["HIGH", "LOW"],
            "threshold_info": {"low_threshold": low_th, "high_threshold": high_th}
        }

    def evaluate_humidity(self, hum: Optional[float], cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if hum is None:
            return None  # BMP280 mode

        low_th = cfg.get("low_threshold", 30.0)
        high_th = cfg.get("high_threshold", 65.0)
        debounce_req = cfg.get("debounce_samples", 3)

        if hum > high_th:
            self.debounce_counters["hum_high"] += 1
            self.debounce_counters["hum_low"] = 0
            status = "HIGH" if self.debounce_counters["hum_high"] >= debounce_req else "NORMAL"
        elif hum < low_th:
            self.debounce_counters["hum_low"] += 1
            self.debounce_counters["hum_high"] = 0
            status = "LOW" if self.debounce_counters["hum_low"] >= debounce_req else "NORMAL"
        else:
            self.debounce_counters["hum_high"] = 0
            self.debounce_counters["hum_low"] = 0
            status = "NORMAL"

        self.current_states["humidity"] = status
        return {
            "parameter": "humidity",
            "value": hum,
            "status": status,
            "alert_triggered": status in ["HIGH", "LOW"],
            "threshold_info": {"low_threshold": low_th, "high_threshold": high_th}
        }

    def evaluate_pressure(self, press: Optional[float], cfg: Dict[str, Any]) -> Dict[str, Any]:
        if press is None:
            return {"parameter": "pressure", "value": None, "status": "INVALID", "alert_triggered": False}

        low_th = cfg.get("low_threshold", 950.0)
        high_th = cfg.get("high_threshold", 1050.0)

        if press < low_th or press > high_th:
            self.debounce_counters["press_out"] += 1
            status = "OUTSIDE CONFIGURED RANGE" if self.debounce_counters["press_out"] >= 3 else "NORMAL"
        else:
            self.debounce_counters["press_out"] = 0
            status = "NORMAL"

        self.current_states["pressure"] = status
        return {
            "parameter": "pressure",
            "value": press,
            "status": status,
            "alert_triggered": status == "OUTSIDE CONFIGURED RANGE",
            "threshold_info": {"low_threshold": low_th, "high_threshold": high_th}
        }

    def evaluate_all(self, telemetry: Dict[str, Any], signal_valid: bool) -> Dict[str, Any]:
        """Runs full threshold matrix across all active sensor streams."""
        thresholds = self.get_thresholds()
        results = {}

        # 1. MAX30102
        if telemetry.get("max30102"):
            m = telemetry["max30102"]
            finger = m.get("finger_detected", False)
            hr = m.get("filtered_heart_rate", m.get("heart_rate"))
            spo2 = m.get("filtered_spo2", m.get("spo2"))

            results["heart_rate"] = self.evaluate_heart_rate(hr, finger, signal_valid, thresholds["heart_rate"])
            results["spo2"] = self.evaluate_spo2(spo2, finger, signal_valid, thresholds["spo2"])

        # 2. MPU6050
        if telemetry.get("mpu6050"):
            mpu = telemetry["mpu6050"]
            results["activity"] = {
                "parameter": "activity",
                "value": mpu.get("activity", "STATIONARY"),
                "status": "NORMAL",
                "alert_triggered": mpu.get("activity") == "HIGH ACTIVITY"
            }
            results["motion_event"] = {
                "parameter": "motion_event",
                "value": mpu.get("fall_event", False),
                "status": "POSSIBLE FALL" if mpu.get("fall_event") else "NORMAL",
                "alert_triggered": bool(mpu.get("fall_event"))
            }

        # 3. Environment (BME280 / BMP280)
        if telemetry.get("environment"):
            env = telemetry["environment"]
            temp = env.get("filtered_temperature", env.get("temperature"))
            press = env.get("filtered_pressure", env.get("pressure"))
            hum = env.get("filtered_humidity", env.get("humidity"))

            results["temperature"] = self.evaluate_temperature(temp, thresholds["temperature"])
            results["pressure"] = self.evaluate_pressure(press, thresholds["pressure"])
            
            hum_eval = self.evaluate_humidity(hum, thresholds["humidity"])
            if hum_eval:
                results["humidity"] = hum_eval

        return results


threshold_engine = ThresholdEngine()
