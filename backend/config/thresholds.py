"""
ESP32 Sensor Monitoring & Threshold-Alert Dashboard
Threshold Configuration and Physiological/Physical Reference Bounds
"""

# Default API Configuration
DEFAULT_API_KEY = "ESP32_SECURE_KEY_2026"
DEFAULT_DEVICE_ID = "ESP32_01"

# 1. PHYSICAL SENSOR OPERATING LIMITS (From Official Datasheets)
# Used for input validation to reject impossible / damaged sensor readings
SENSOR_OPERATING_LIMITS = {
    "max30102": {
        "heart_rate_min_bpm": 30.0,
        "heart_rate_max_bpm": 240.0,
        "spo2_min_pct": 0.0,
        "spo2_max_pct": 100.0,
        "raw_ir_min": 0,
        "raw_ir_max": 262143,  # 18-bit ADC limit
        "raw_red_min": 0,
        "raw_red_max": 262143,
        "min_valid_contact_ir": 40000,  # DC threshold for finger contact
    },
    "mpu6050": {
        "accel_range_g": 16.0,   # Max configurable range (+/- 16g)
        "gyro_range_dps": 2000.0 # Max configurable range (+/- 2000 deg/s)
    },
    "bme280_bmp280": {
        "temp_min_c": -40.0,
        "temp_max_c": 85.0,
        "pressure_min_hpa": 300.0,
        "pressure_max_hpa": 1100.0,
        "humidity_min_pct": 0.0,
        "humidity_max_pct": 100.0
    }
}

# 2. ADULT RESTING PHYSIOLOGICAL & ENVIRONMENTAL REFERENCE BOUNDS
# Evidence-based baseline reference guides (NOT individual medical diagnoses)
REFERENCE_BASELINES = {
    "heart_rate": {
        "low_reference": 60.0,     # Adult resting bradycardia reference boundary
        "high_reference": 100.0,   # Adult resting tachycardia reference boundary
        "unit": "BPM",
        "description": "Standard adult resting heart rate reference zone (60-100 BPM)."
    },
    "spo2": {
        "normal_min_reference": 95.0,  # Optimal blood oxygenation reference
        "caution_min_reference": 90.0, # Sub-optimal / mild hypoxemia boundary
        "unit": "%",
        "description": "Resting pulse oximetry reference (>=95% Normal, 90-94% Caution, <90% Critical)."
    },
    "temperature": {
        "low_reference": 18.0,
        "high_reference": 30.0,
        "unit": "°C",
        "description": "Ambient room comfort reference range (18-30°C)."
    },
    "humidity": {
        "low_reference": 30.0,
        "high_reference": 60.0,
        "unit": "%",
        "description": "Ambient indoor relative humidity comfort zone (30-60%)."
    },
    "pressure": {
        "low_reference": 950.0,
        "high_reference": 1050.0,
        "unit": "hPa",
        "description": "Standard sea-level barometric pressure range (950-1050 hPa)."
    }
}

# 3. INITIAL CONFIGURABLE PROJECT ALERT THRESHOLDS
# Stored in database and customizable via PUT /api/thresholds
DEFAULT_THRESHOLDS = {
    "heart_rate": {
        "parameter": "heart_rate",
        "low_threshold": 60.0,
        "high_threshold": 100.0,
        "hysteresis": 2.0,            # Require crossing threshold by +/- 2 BPM to clear
        "debounce_samples": 4,        # Require 4 consecutive abnormal readings
        "unit": "BPM",
        "type": "physiological"
    },
    "spo2": {
        "parameter": "spo2",
        "normal_min": 95.0,
        "caution_min": 90.0,
        "hysteresis": 1.0,            # Require +1% recovery to change state
        "debounce_samples": 3,        # Require 3 consecutive abnormal readings
        "unit": "%",
        "type": "physiological"
    },
    "temperature": {
        "parameter": "temperature",
        "low_threshold": 18.0,
        "high_threshold": 32.0,
        "hysteresis": 0.5,
        "debounce_samples": 3,
        "unit": "°C",
        "type": "environmental"
    },
    "humidity": {
        "parameter": "humidity",
        "low_threshold": 30.0,
        "high_threshold": 65.0,
        "hysteresis": 2.0,
        "debounce_samples": 3,
        "unit": "%",
        "type": "environmental"
    },
    "pressure": {
        "parameter": "pressure",
        "low_threshold": 950.0,
        "high_threshold": 1050.0,
        "hysteresis": 5.0,
        "debounce_samples": 3,
        "unit": "hPa",
        "type": "environmental"
    },
    "motion": {
        "parameter": "motion",
        "impact_accel_g": 2.6,        # Stage 1: Freefall/Impact threshold
        "rotational_gyro_dps": 160.0, # Stage 2: Angular velocity perturbation threshold
        "inactivity_accel_tol_g": 0.2,# Stage 3: Inactivity tolerance around 1.0g
        "inactivity_gyro_max_dps": 15.0,# Stage 3: Minimal motion threshold
        "inactivity_duration_sec": 2.0, # Stage 3: Required post-fall resting duration
        "debounce_samples": 1,
        "type": "motion"
    }
}
