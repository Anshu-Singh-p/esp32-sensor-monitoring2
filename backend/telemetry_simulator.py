"""
Edge AI Health Companion - Telemetry Simulator
Simulates continuous multi-sensor biometric and environmental hardware telemetry.
Generates realistic physiological responses, ECG waveforms, and environmental sensor streams.
"""

import time
import math
import random
from typing import Dict, List, Any
from collections import deque


class TelemetrySimulator:
    def __init__(self):
        self.scenario = "normal"
        self.start_time = time.time()
        self.step_count = 0
        
        # State variables for smooth physiological transitions
        self.target_hr = 72.0
        self.current_hr = 72.0
        
        self.target_spo2 = 98.5
        self.current_spo2 = 98.5
        
        self.target_temp_c = 36.7
        self.current_temp_c = 36.7
        
        self.target_aqi = 28.0
        self.current_aqi = 28.0
        
        self.target_co2 = 440.0
        self.current_co2 = 440.0
        
        self.target_pm25 = 8.5
        self.current_pm25 = 8.5
        
        self.target_pm10 = 14.0
        self.current_pm10 = 14.0
        
        self.target_tvoc = 45.0
        self.current_tvoc = 45.0
        
        self.target_hrv = 65.0
        self.current_hrv = 65.0
        
        self.ambient_temp_c = 22.4
        self.ambient_humidity_pct = 48.0

        # Rolling history buffers for time-series charts (last 60 readings)
        self.history_len = 60
        self.history_timestamps = deque(maxlen=self.history_len)
        self.history_hr = deque(maxlen=self.history_len)
        self.history_spo2 = deque(maxlen=self.history_len)
        self.history_temp_c = deque(maxlen=self.history_len)
        self.history_aqi = deque(maxlen=self.history_len)
        self.history_co2 = deque(maxlen=self.history_len)
        self.history_pm25 = deque(maxlen=self.history_len)

        # Pre-seed history with realistic baseline values
        now = time.time()
        for i in range(self.history_len):
            t_offset = now - (self.history_len - i) * 1.0
            self.history_timestamps.append(t_offset)
            self.history_hr.append(round(70 + 4 * math.sin(i / 5.0) + random.uniform(-1, 1), 1))
            self.history_spo2.append(round(98.2 + 0.5 * math.cos(i / 7.0), 1))
            self.history_temp_c.append(round(36.7 + 0.1 * math.sin(i / 10.0), 2))
            self.history_aqi.append(round(28 + 3 * math.sin(i / 6.0), 1))
            self.history_co2.append(round(430 + 15 * math.sin(i / 8.0), 1))
            self.history_pm25.append(round(8.2 + 1.2 * math.cos(i / 6.0), 1))

        # Phase tracking for ECG waveform synthesis
        self.ecg_phase = 0.0

    def set_scenario(self, scenario_name: str) -> Dict[str, Any]:
        """Switch simulation scenario."""
        valid_scenarios = ["normal", "exercise", "arrhythmia", "hypoxia", "poor_air", "fever"]
        if scenario_name not in valid_scenarios:
            scenario_name = "normal"
        self.scenario = scenario_name

        if scenario_name == "normal":
            self.target_hr = 72.0
            self.target_spo2 = 98.5
            self.target_temp_c = 36.7
            self.target_aqi = 28.0
            self.target_co2 = 440.0
            self.target_pm25 = 8.5
            self.target_pm10 = 14.0
            self.target_tvoc = 45.0
            self.target_hrv = 65.0
        elif scenario_name == "exercise":
            self.target_hr = 142.0
            self.target_spo2 = 97.8
            self.target_temp_c = 37.6
            self.target_aqi = 34.0
            self.target_co2 = 480.0
            self.target_pm25 = 11.0
            self.target_pm10 = 18.0
            self.target_tvoc = 50.0
            self.target_hrv = 38.0
        elif scenario_name == "arrhythmia":
            self.target_hr = 98.0
            self.target_spo2 = 96.2
            self.target_temp_c = 36.8
            self.target_aqi = 30.0
            self.target_co2 = 460.0
            self.target_pm25 = 9.0
            self.target_pm10 = 15.0
            self.target_tvoc = 48.0
            self.target_hrv = 18.0  # severely erratic/low HRV
        elif scenario_name == "hypoxia":
            self.target_hr = 104.0
            self.target_spo2 = 87.5  # Critical hypoxia threshold
            self.target_temp_c = 36.5
            self.target_aqi = 35.0
            self.target_co2 = 450.0
            self.target_pm25 = 9.5
            self.target_pm10 = 16.0
            self.target_tvoc = 46.0
            self.target_hrv = 32.0
        elif scenario_name == "poor_air":
            self.target_hr = 88.0
            self.target_spo2 = 93.8
            self.target_temp_c = 36.9
            self.target_aqi = 168.0  # Hazardous AQI
            self.target_co2 = 1580.0  # High indoor CO2 stagnation
            self.target_pm25 = 68.4
            self.target_pm10 = 112.0
            self.target_tvoc = 240.0
            self.target_hrv = 44.0
        elif scenario_name == "fever":
            self.target_hr = 106.0
            self.target_spo2 = 96.5
            self.target_temp_c = 38.9  # High Pyrexia
            self.target_aqi = 32.0
            self.target_co2 = 490.0
            self.target_pm25 = 10.0
            self.target_pm10 = 16.0
            self.target_tvoc = 52.0
            self.target_hrv = 28.0

        return {"status": "ok", "scenario": self.scenario}

    def update_telemetry(self) -> Dict[str, Any]:
        """
        Advances the simulation clock by 1 tick, smoothly interpolating current vitals towards target vitals
        and adding realistic physiological micro-variations.
        """
        self.step_count += 1
        now = time.time()

        # Smooth exponential moving average toward targets
        alpha = 0.22  # convergence speed
        self.current_hr += alpha * (self.target_hr - self.current_hr)
        self.current_spo2 += alpha * (self.target_spo2 - self.current_spo2)
        self.current_temp_c += (alpha * 0.5) * (self.target_temp_c - self.current_temp_c)
        self.current_aqi += alpha * (self.target_aqi - self.current_aqi)
        self.current_co2 += alpha * (self.target_co2 - self.current_co2)
        self.current_pm25 += alpha * (self.target_pm25 - self.current_pm25)
        self.current_pm10 += alpha * (self.target_pm10 - self.current_pm10)
        self.current_tvoc += alpha * (self.target_tvoc - self.current_tvoc)
        self.current_hrv += alpha * (self.target_hrv - self.current_hrv)

        # Add physiological jitter / respiratory sinus arrhythmia
        respiration_factor = math.sin(self.step_count * 0.35)
        hr_jitter = (respiration_factor * 1.8) + random.uniform(-0.6, 0.6)
        if self.scenario == "arrhythmia":
            # Sudden ectopic beats / erratic jumps
            if random.random() < 0.25:
                hr_jitter += random.choice([-18.0, 24.0, -12.0, 19.0])

        out_hr = round(max(35.0, min(210.0, self.current_hr + hr_jitter)), 1)
        out_spo2 = round(max(70.0, min(100.0, self.current_spo2 + random.uniform(-0.2, 0.2))), 1)
        out_temp_c = round(self.current_temp_c + random.uniform(-0.02, 0.02), 2)
        out_temp_f = round(out_temp_c * 9.0 / 5.0 + 32.0, 2)
        out_aqi = round(max(5.0, self.current_aqi + random.uniform(-1.5, 1.5)), 1)
        out_co2 = round(max(380.0, self.current_co2 + random.uniform(-8.0, 8.0)), 1)
        out_pm25 = round(max(1.0, self.current_pm25 + random.uniform(-0.4, 0.4)), 1)
        out_pm10 = round(max(2.0, self.current_pm10 + random.uniform(-0.8, 0.8)), 1)
        out_tvoc = round(max(5.0, self.current_tvoc + random.uniform(-2.0, 2.0)), 1)
        out_hrv = round(max(8.0, self.current_hrv + random.uniform(-2.0, 2.0)), 1)

        # Push to rolling histories
        self.history_timestamps.append(now)
        self.history_hr.append(out_hr)
        self.history_spo2.append(out_spo2)
        self.history_temp_c.append(out_temp_c)
        self.history_aqi.append(out_aqi)
        self.history_co2.append(out_co2)
        self.history_pm25.append(out_pm25)

        # Respiration rate estimation derived from HR and scenario
        respiration_rate = 14
        if self.scenario == "exercise":
            respiration_rate = 28 + int(random.uniform(-1, 2))
        elif self.scenario == "hypoxia":
            respiration_rate = 22 + int(random.uniform(-1, 2))
        elif self.scenario == "fever":
            respiration_rate = 19 + int(random.uniform(-1, 1))

        # Battery and sensor connectivity simulation
        battery_pct = round(max(10, 94.0 - ((now - self.start_time) / 360.0) % 85), 1)

        vitals = {
            "timestamp": now,
            "scenario": self.scenario,
            "heart_rate": out_hr,
            "spo2": out_spo2,
            "temperature_c": out_temp_c,
            "temperature_f": out_temp_f,
            "hrv_ms": out_hrv,
            "respiration_rate_bpm": respiration_rate,
            "aqi": out_aqi,
            "co2_ppm": out_co2,
            "pm25": out_pm25,
            "pm10": out_pm10,
            "tvoc_ppb": out_tvoc,
            "ambient_temp_c": self.ambient_temp_c,
            "ambient_humidity_pct": self.ambient_humidity_pct,
            "battery_pct": battery_pct,
            "ble_signal_dbm": -58 + int(random.uniform(-3, 3)),
            "device_status": "Online (Edge NPU Active)"
        }

        return vitals

    def generate_ecg_chunk(self, num_points: int = 50) -> List[float]:
        """
        Synthesizes a realistic mathematical P-Q-R-S-T cardiac waveform at ~100Hz.
        Adjusts shape and speed dynamically based on current heart rate and arrhythmia state.
        """
        hr = self.current_hr
        freq = hr / 60.0  # beats per second
        dt = 1.0 / 100.0  # 100 samples/sec
        points = []

        for _ in range(num_points):
            self.ecg_phase += freq * dt
            if self.ecg_phase >= 1.0:
                self.ecg_phase -= 1.0

            phase = self.ecg_phase

            # Synthetic ECG synthesis using Gaussian peaks for P, Q, R, S, T waves
            # Baseline is ~0.0
            val = 0.0

            # Baseline wander (low frequency breathing artifact)
            val += 0.04 * math.sin(2 * math.pi * phase * 0.2)

            # P wave (Atrial Depolarization): occurs at phase ~0.15, amplitude +0.18
            p_center, p_width, p_amp = 0.16, 0.035, 0.18
            val += p_amp * math.exp(-((phase - p_center) ** 2) / (2 * (p_width ** 2)))

            # Q wave (Septal Depolarization): occurs at phase ~0.26, amplitude -0.15
            q_center, q_width, q_amp = 0.26, 0.012, -0.15
            val += q_amp * math.exp(-((phase - q_center) ** 2) / (2 * (q_width ** 2)))

            # R peak (Ventricular Depolarization): occurs at phase ~0.30, amplitude +1.20 (tall sharp spike)
            r_center, r_width, r_amp = 0.30, 0.015, 1.25
            if self.scenario == "arrhythmia" and random.random() < 0.15:
                r_amp = 1.65  # Ectopic PVC spike
                r_width = 0.028  # Widened QRS complex
            val += r_amp * math.exp(-((phase - r_center) ** 2) / (2 * (r_width ** 2)))

            # S wave (Purkinje Depolarization): occurs at phase ~0.34, amplitude -0.32
            s_center, s_width, s_amp = 0.34, 0.014, -0.32
            val += s_amp * math.exp(-((phase - s_center) ** 2) / (2 * (s_width ** 2)))

            # T wave (Ventricular Repolarization): occurs at phase ~0.55, amplitude +0.28
            t_center, t_width, t_amp = 0.55, 0.065, 0.30
            val += t_amp * math.exp(-((phase - t_center) ** 2) / (2 * (t_width ** 2)))

            # Sensor thermal noise
            val += random.uniform(-0.02, 0.02)

            points.append(round(val, 3))

        return points

    def get_history(self) -> Dict[str, Any]:
        """Returns the rolling historical telemetry series for frontend chart rendering."""
        return {
            "timestamps": list(self.history_timestamps),
            "heart_rate": list(self.history_hr),
            "spo2": list(self.history_spo2),
            "temperature_c": list(self.history_temp_c),
            "aqi": list(self.history_aqi),
            "co2": list(self.history_co2),
            "pm25": list(self.history_pm25)
        }
