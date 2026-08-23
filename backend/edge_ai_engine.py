"""
Edge AI Health Companion - TinyML Anomaly Detection Engine
Runs simulated on-device quantized neural network inferences on sensor telemetry.
"""

import time
import random
from typing import Dict, List, Any, Tuple


class EdgeAIEngine:
    """
    Simulates an on-device Edge AI processor (e.g., ARM Cortex-M55 / ESP32-S3 / Apple Neural Engine / Coral TPU)
    running quantized INT8 models for real-time physiological anomaly detection and environmental hazard triage.
    """

    def __init__(self):
        self.model_name = "EdgeHealth-TinyNet-v3.2-INT8"
        self.hardware_target = "Edge NPU (Dual-Core Vector Ext)"
        self.quantization = "INT8 Quantized (0.42 MB)"
        self.inference_count = 0
        self.last_recalibration = time.time()
        self.calibrated = True

    def run_inference(self, vitals: Dict[str, Any], scenario: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Executes sub-5ms simulated on-device inference on current vitals and air metrics.
        Returns:
            - AI inference metadata (latency, confidence, classification, status)
            - List of active generated alerts
        """
        self.inference_count += 1
        start_ns = time.perf_counter_ns()

        hr = vitals.get("heart_rate", 72)
        spo2 = vitals.get("spo2", 98)
        temp_c = vitals.get("temperature_c", 36.8)
        aqi = vitals.get("aqi", 28)
        co2 = vitals.get("co2_ppm", 420)
        pm25 = vitals.get("pm25", 8.5)
        hrv_ms = vitals.get("hrv_ms", 65)

        alerts = []
        classifications = []
        anomaly_scores = {}

        # 1. Cardiac Rhythm Analysis
        # ----------------------------
        cardiac_score = 0.0
        if scenario == "arrhythmia" or hrv_ms < 22 or hrv_ms > 130:
            cardiac_score = 0.94 + random.uniform(0.01, 0.05)
            classifications.append("Cardiac Arrhythmia / Premature Ventricular Contractions")
            alerts.append({
                "id": "alert_arrhythmia",
                "severity": "critical",
                "category": "cardiac",
                "title": "Irregular Cardiac Rhythm Detected",
                "message": f"Edge AI detected irregular R-R peak intervals (HRV: {hrv_ms}ms, HR: {int(hr)} BPM). Pattern matches premature ventricular contractions.",
                "recommendation": "Sit down immediately, breathe slowly, and prepare to contact your healthcare provider if symptoms persist.",
                "timestamp": time.time(),
                "confidence": round(cardiac_score * 100, 1),
                "edge_engine": "TinyML-ECG-1DCNN"
            })
        elif hr > 115 and scenario != "exercise":
            cardiac_score = 0.82 + random.uniform(0.01, 0.04)
            classifications.append("Resting Tachycardia")
            alerts.append({
                "id": "alert_tachycardia",
                "severity": "warning",
                "category": "cardiac",
                "title": "Elevated Resting Heart Rate",
                "message": f"Heart rate is {int(hr)} BPM during low physical motion. Higher than normal resting baseline.",
                "recommendation": "Hydrate, practice 4-7-8 deep breathing, and avoid caffeine.",
                "timestamp": time.time(),
                "confidence": round(cardiac_score * 100, 1),
                "edge_engine": "TinyML-ECG-1DCNN"
            })
        elif hr < 48:
            cardiac_score = 0.78 + random.uniform(0.01, 0.05)
            classifications.append("Resting Bradycardia")
            alerts.append({
                "id": "alert_bradycardia",
                "severity": "warning",
                "category": "cardiac",
                "title": "Low Heart Rate Detected",
                "message": f"Heart rate dropped to {int(hr)} BPM.",
                "recommendation": "Ensure warm ambient conditions and check for symptoms of lightheadedness or fatigue.",
                "timestamp": time.time(),
                "confidence": round(cardiac_score * 100, 1),
                "edge_engine": "TinyML-ECG-1DCNN"
            })
        else:
            cardiac_score = 0.05 + random.uniform(0.0, 0.03)
            classifications.append("Normal Sinus Rhythm")

        anomaly_scores["cardiac_anomaly"] = round(cardiac_score, 3)

        # 2. Hypoxia & Oxygenation Analysis
        # ---------------------------------
        spo2_score = 0.0
        if spo2 < 90:
            spo2_score = 0.96
            classifications.append("Severe Hypoxia Alert")
            alerts.append({
                "id": "alert_hypoxia_severe",
                "severity": "critical",
                "category": "respiratory",
                "title": "Critical Hypoxia (SpO₂ < 90%)",
                "message": f"Blood oxygen saturation reached critically low level: {spo2}%. Risk of acute oxygen deprivation.",
                "recommendation": "Seek immediate supplemental oxygen or emergency medical attention. Sit upright.",
                "timestamp": time.time(),
                "confidence": 98.2,
                "edge_engine": "TinyML-SpO2-Spectra"
            })
        elif spo2 < 94:
            spo2_score = 0.75 + random.uniform(0.01, 0.05)
            classifications.append("Moderate Hypoxemia Risk")
            alerts.append({
                "id": "alert_hypoxia_mod",
                "severity": "warning",
                "category": "respiratory",
                "title": "Sub-Optimal Oxygen Saturation",
                "message": f"SpO₂ level is currently {spo2}%. Lower than optimal 95-100% threshold.",
                "recommendation": "Take deep diaphragmatic breaths, improve room airflow, or check sensor fit.",
                "timestamp": time.time(),
                "confidence": 89.5,
                "edge_engine": "TinyML-SpO2-Spectra"
            })
        else:
            spo2_score = 0.02

        anomaly_scores["hypoxia_risk"] = round(spo2_score, 3)

        # 3. Thermal Strain / Pyrexia Analysis
        # ------------------------------------
        thermal_score = 0.0
        if temp_c >= 38.5:
            thermal_score = 0.92
            classifications.append("High Grade Pyrexia / Fever")
            alerts.append({
                "id": "alert_fever_high",
                "severity": "critical",
                "category": "thermal",
                "title": "High Fever Detected (> 38.5°C)",
                "message": f"Body core temperature is elevated at {temp_c:.1f}°C ({temp_c * 9/5 + 32:.1f}°F).",
                "recommendation": "Rest in a cool room, apply cold compresses, stay hydrated, and consult medical advice.",
                "timestamp": time.time(),
                "confidence": 96.0,
                "edge_engine": "TinyML-Thermal-Kalman"
            })
        elif temp_c >= 37.6:
            thermal_score = 0.65
            classifications.append("Mild Low-Grade Fever / Heat Strain")
            alerts.append({
                "id": "alert_fever_mild",
                "severity": "warning",
                "category": "thermal",
                "title": "Elevated Body Temperature",
                "message": f"Body temperature is {temp_c:.1f}°C ({temp_c * 9/5 + 32:.1f}°F).",
                "recommendation": "Monitor temperature closely, stay hydrated, and reduce physical exertion.",
                "timestamp": time.time(),
                "confidence": 91.2,
                "edge_engine": "TinyML-Thermal-Kalman"
            })
        elif temp_c < 35.2:
            thermal_score = 0.85
            classifications.append("Hypothermia Risk")
            alerts.append({
                "id": "alert_hypothermia",
                "severity": "warning",
                "category": "thermal",
                "title": "Low Body Temperature Warning",
                "message": f"Body temperature has dropped to {temp_c:.1f}°C ({temp_c * 9/5 + 32:.1f}°F).",
                "recommendation": "Add warm insulation layers, consume warm fluids, and move to a heated space.",
                "timestamp": time.time(),
                "confidence": 93.4,
                "edge_engine": "TinyML-Thermal-Kalman"
            })
        else:
            thermal_score = 0.03

        anomaly_scores["thermal_strain"] = round(thermal_score, 3)

        # 4. Air Quality & Environmental Toxicity Analysis
        # ------------------------------------------------
        env_score = 0.0
        if aqi > 150 or pm25 > 55.0:
            env_score = 0.91
            classifications.append("Unhealthy Particulate Exposure")
            alerts.append({
                "id": "alert_aqi_unhealthy",
                "severity": "critical",
                "category": "environmental",
                "title": f"Hazardous Air Quality (AQI: {int(aqi)})",
                "message": f"Particulate matter PM2.5 is {pm25:.1f} µg/m³. Breathing hazardous micro-particles.",
                "recommendation": "Turn on HEPA air purification, seal windows, or wear an N95 respirator if outdoors.",
                "timestamp": time.time(),
                "confidence": 97.5,
                "edge_engine": "TinyML-AirTox-Ensemble"
            })
        elif aqi > 80 or pm25 > 35.0:
            env_score = 0.60
            classifications.append("Moderate Particulate Warning")
            alerts.append({
                "id": "alert_aqi_moderate",
                "severity": "warning",
                "category": "environmental",
                "title": "Moderate Air Pollution Detected",
                "message": f"AQI is {int(aqi)} with PM2.5 at {pm25:.1f} µg/m³.",
                "recommendation": "Limit intense outdoor cardio and maintain indoor filtration.",
                "timestamp": time.time(),
                "confidence": 88.0,
                "edge_engine": "TinyML-AirTox-Ensemble"
            })

        if co2 > 1400:
            env_score = max(env_score, 0.88)
            classifications.append("High CO₂ Stagnation / Drowsiness Hazard")
            alerts.append({
                "id": "alert_co2_high",
                "severity": "warning",
                "category": "environmental",
                "title": f"High CO₂ Stagnant Air ({int(co2)} ppm)",
                "message": f"Indoor CO₂ has reached {int(co2)} ppm. Causes cognitive degradation, fatigue, and headaches.",
                "recommendation": "Open windows or enable HVAC fresh-air exchange immediately.",
                "timestamp": time.time(),
                "confidence": 95.8,
                "edge_engine": "TinyML-AirTox-Ensemble"
            })

        anomaly_scores["environmental_hazard"] = round(env_score, 3)

        # 5. Multimodal Copilot Synthesis
        # -------------------------------
        copilot_insight = "All physiological and environmental indicators within standard baseline parameters. Edge AI models operating in ultra-low power standby mode."
        if hr > 100 and co2 > 1200:
            copilot_insight = "Multimodal Correlation: Elevated heart rate paired with poor indoor ventilation (CO₂ > 1200ppm). Cognitive fatigue risk is high. Recommend a 5-minute break and fresh air."
        elif hr > 110 and temp_c > 37.5:
            copilot_insight = "Multimodal Correlation: Heart rate and body temperature are simultaneously elevated. Physiological heat stress detected. Begin active hydration."
        elif spo2 < 94 and aqi > 90:
            copilot_insight = "Multimodal Correlation: Sub-optimal blood oxygenation combined with elevated ambient PM2.5 particles. Respiratory irritation likely. Move to a filtered room."
        elif scenario == "exercise":
            copilot_insight = "Exercise Physiology Tracking: Cardio exertion detected. Target heart rate zone active. Oxygenation and thermal regulation remain stable."
        elif len(alerts) > 0:
            copilot_insight = f"Edge AI detected {len(alerts)} active telemetry anomaly. Real-time on-device triage recommendations active."

        # Compute synthetic inference latency (typically 2.8 - 4.6 ms for quantized edge microcontrollers)
        end_ns = time.perf_counter_ns()
        actual_ns = end_ns - start_ns
        simulated_latency_ms = round(3.2 + (actual_ns / 1_000_000.0) % 1.5 + random.uniform(0.1, 0.4), 2)

        max_anomaly = max(anomaly_scores.values()) if anomaly_scores else 0.0
        health_status = "Optimal"
        if max_anomaly > 0.8:
            health_status = "Critical Alert"
        elif max_anomaly > 0.5:
            health_status = "Caution / Warning"
        elif max_anomaly > 0.2:
            health_status = "Minor Drift"

        inference_meta = {
            "model": self.model_name,
            "hardware": self.hardware_target,
            "quantization": self.quantization,
            "latency_ms": simulated_latency_ms,
            "confidence_pct": round(98.2 - max_anomaly * 5.0 + random.uniform(-0.5, 0.5), 1),
            "health_status": health_status,
            "primary_classification": classifications[0] if classifications else "Normal Steady State",
            "anomaly_scores": anomaly_scores,
            "copilot_insight": copilot_insight,
            "inference_count": self.inference_count,
            "memory_usage_kb": 412,
            "battery_drain_mw": round(14.2 + random.uniform(0.2, 0.8), 2)
        }

        return inference_meta, alerts

    def recalibrate(self) -> Dict[str, Any]:
        """Trigger simulated edge sensor baseline recalibration."""
        self.last_recalibration = time.time()
        self.calibrated = True
        return {
            "status": "success",
            "message": "Edge AI baseline recalibration complete. Sensor drift zeroed. INT8 weights verified.",
            "timestamp": self.last_recalibration
        }
