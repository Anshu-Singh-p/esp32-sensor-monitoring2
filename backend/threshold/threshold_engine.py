"""
Stage 6 — Research-Based Threshold Engine Module
Evaluates extracted features against research baselines and configurable thresholds
using duration debouncing, hysteresis guard bands, and multi-level severity scoring.
"""

from typing import Dict, Any, Optional
from config.thresholds import DEFAULT_THRESHOLDS


class ResearchThresholdEngine:
    def __init__(self):
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        self.debounce_counters = {
            "hr_high": 0, "hr_low": 0,
            "spo2_caution": 0, "spo2_critical": 0,
            "temp_high": 0, "temp_low": 0,
            "hum_high": 0, "hum_low": 0, "press_out": 0
        }
        self.current_states = {
            "heart_rate": "NORMAL",
            "spo2": "NORMAL",
            "temperature": "NORMAL",
            "humidity": "NORMAL",
            "pressure": "NORMAL"
        }

    def set_thresholds(self, new_thresholds: Dict[str, Any]):
        self.thresholds.update(new_thresholds)

    def evaluate_features(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        features = extracted_data.get("features", {})
        now = extracted_data.get("timestamp", 0.0)
        results = {}

        # 1. Evaluate Heart Rate
        if "max30102" in features:
            m = features["max30102"]
            hr = m.get("heart_rate")
            finger = m.get("finger_detected", False)
            sqi = m.get("signal_quality_index", 0.0)
            cfg = self.thresholds.get("heart_rate", DEFAULT_THRESHOLDS["heart_rate"])

            if not finger or hr is None:
                self.debounce_counters["hr_high"] = 0
                self.debounce_counters["hr_low"] = 0
                self.current_states["heart_rate"] = "INVALID"
                results["heart_rate"] = {
                    "parameter": "heart_rate", "value": None, "unit": "BPM",
                    "status": "INVALID" if not finger else "INSUFFICIENT_SIGNAL",
                    "threshold": {"lower": cfg["low_threshold"], "upper": cfg["high_threshold"]},
                    "timestamp": now, "confidence": 0.0
                }
            else:
                low_th = cfg.get("low_threshold", 60.0)
                high_th = cfg.get("high_threshold", 100.0)
                hyst = cfg.get("hysteresis", 2.0)
                debounce = cfg.get("debounce_samples", 4)
                prev_state = self.current_states["heart_rate"]
                new_state = prev_state

                if hr > high_th:
                    self.debounce_counters["hr_high"] += 1
                    self.debounce_counters["hr_low"] = 0
                    if self.debounce_counters["hr_high"] >= debounce:
                        new_state = "CRITICAL" if hr > 140 else "HIGH"
                elif hr < low_th:
                    self.debounce_counters["hr_low"] += 1
                    self.debounce_counters["hr_high"] = 0
                    if self.debounce_counters["hr_low"] >= debounce:
                        new_state = "CRITICAL" if hr < 40 else "LOW"
                else:
                    if prev_state in ["HIGH", "CRITICAL"] and hr <= (high_th - hyst):
                        self.debounce_counters["hr_high"] = 0
                        new_state = "NORMAL"
                    elif prev_state in ["LOW", "CRITICAL"] and hr >= (low_th + hyst):
                        self.debounce_counters["hr_low"] = 0
                        new_state = "NORMAL"
                    elif prev_state in ["NORMAL", "INVALID"]:
                        self.debounce_counters["hr_high"] = 0
                        self.debounce_counters["hr_low"] = 0
                        new_state = "NORMAL"

                self.current_states["heart_rate"] = new_state
                results["heart_rate"] = {
                    "parameter": "heart_rate", "value": round(hr, 1), "unit": "BPM",
                    "status": new_state,
                    "threshold": {"lower": low_th, "upper": high_th},
                    "timestamp": now, "confidence": round(sqi / 100.0, 2)
                }

        # 2. Evaluate SpO2
        if "max30102" in features:
            m = features["max30102"]
            spo2 = m.get("spo2")
            finger = m.get("finger_detected", False)
            sqi = m.get("signal_quality_index", 0.0)
            cfg = self.thresholds.get("spo2", DEFAULT_THRESHOLDS["spo2"])

            if not finger or spo2 is None:
                self.debounce_counters["spo2_caution"] = 0
                self.debounce_counters["spo2_critical"] = 0
                self.current_states["spo2"] = "INVALID"
                results["spo2"] = {
                    "parameter": "spo2", "value": None, "unit": "%",
                    "status": "INVALID",
                    "threshold": {"normal_min": cfg["normal_min"], "caution_min": cfg["caution_min"]},
                    "timestamp": now, "confidence": 0.0
                }
            else:
                norm_min = cfg.get("normal_min", 95.0)
                caut_min = cfg.get("caution_min", 90.0)
                hyst = cfg.get("hysteresis", 1.0)
                debounce = cfg.get("debounce_samples", 3)
                prev_state = self.current_states["spo2"]
                new_state = prev_state

                if spo2 < caut_min:
                    self.debounce_counters["spo2_critical"] += 1
                    self.debounce_counters["spo2_caution"] = 0
                    if self.debounce_counters["spo2_critical"] >= debounce:
                        new_state = "CRITICAL"
                elif spo2 < norm_min:
                    self.debounce_counters["spo2_caution"] += 1
                    self.debounce_counters["spo2_critical"] = 0
                    if self.debounce_counters["spo2_caution"] >= debounce:
                        new_state = "CAUTION"
                else:
                    if prev_state == "CRITICAL" and spo2 >= (caut_min + hyst):
                        self.debounce_counters["spo2_critical"] = 0
                        new_state = "CAUTION" if spo2 < norm_min else "NORMAL"
                    elif prev_state == "CAUTION" and spo2 >= (norm_min + hyst):
                        self.debounce_counters["spo2_caution"] = 0
                        new_state = "NORMAL"
                    elif prev_state in ["NORMAL", "INVALID"]:
                        self.debounce_counters["spo2_caution"] = 0
                        self.debounce_counters["spo2_critical"] = 0
                        new_state = "NORMAL"

                self.current_states["spo2"] = new_state
                results["spo2"] = {
                    "parameter": "spo2", "value": round(spo2, 1), "unit": "%",
                    "status": new_state,
                    "threshold": {"normal_min": norm_min, "caution_min": caut_min},
                    "timestamp": now, "confidence": round(sqi / 100.0, 2)
                }

        # 3. Evaluate Motion & Fall Events
        if "mpu6050" in features:
            mpu = features["mpu6050"]
            results["activity"] = {
                "parameter": "activity", "value": mpu["activity"], "unit": "state",
                "status": "WARNING" if mpu["activity"] == "HIGH ACTIVITY" else "NORMAL",
                "threshold": {"trigger": "HIGH ACTIVITY"}, "timestamp": now, "confidence": 0.95
            }
            results["fall_event"] = {
                "parameter": "fall_event", "value": mpu["fall_event"], "unit": "boolean",
                "status": "CRITICAL" if mpu["fall_event"] else "NORMAL",
                "threshold": {"type": "Multi-stage impact+rotation+inactivity"},
                "timestamp": now, "confidence": 0.90
            }

        # 4. Evaluate Environment
        if "environment" in features:
            env = features["environment"]
            t = env.get("temperature")
            p = env.get("pressure")
            h = env.get("humidity")

            cfg_t = self.thresholds.get("temperature", DEFAULT_THRESHOLDS["temperature"])
            cfg_p = self.thresholds.get("pressure", DEFAULT_THRESHOLDS["pressure"])
            cfg_h = self.thresholds.get("humidity", DEFAULT_THRESHOLDS["humidity"])

            # Temperature evaluation
            status_t = "NORMAL"
            if t is not None:
                if t > cfg_t["high_threshold"]:
                    status_t = "HIGH"
                elif t < cfg_t["low_threshold"]:
                    status_t = "LOW"
            results["temperature"] = {
                "parameter": "temperature", "value": t, "unit": "°C",
                "status": status_t, "threshold": {"lower": cfg_t["low_threshold"], "upper": cfg_t["high_threshold"]},
                "timestamp": now, "confidence": 0.98
            }

            # Pressure evaluation
            status_p = "NORMAL"
            if p is not None:
                if p < cfg_p["low_threshold"] or p > cfg_p["high_threshold"]:
                    status_p = "OUTSIDE_RANGE"
            results["pressure"] = {
                "parameter": "pressure", "value": p, "unit": "hPa",
                "status": status_p, "threshold": {"lower": cfg_p["low_threshold"], "upper": cfg_p["high_threshold"]},
                "timestamp": now, "confidence": 0.98
            }

            # Humidity evaluation (if BME280)
            if h is not None:
                status_h = "NORMAL"
                if h > cfg_h["high_threshold"]:
                    status_h = "HIGH"
                elif h < cfg_h["low_threshold"]:
                    status_h = "LOW"
                results["humidity"] = {
                    "parameter": "humidity", "value": h, "unit": "%",
                    "status": status_h, "threshold": {"lower": cfg_h["low_threshold"], "upper": cfg_h["high_threshold"]},
                    "timestamp": now, "confidence": 0.98
                }

        return results


research_threshold_engine = ResearchThresholdEngine()
