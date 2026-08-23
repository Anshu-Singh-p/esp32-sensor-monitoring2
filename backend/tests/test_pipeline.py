"""
End-to-End Automated Test Suite for ESP32 Sensor Processing Pipeline
Verifies all 8 pipeline stages from reception to thresholding, database, and APIs.
"""

import os
import sys
import time
import json

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(TESTS_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from processing.validation import sensor_validator
from processing.calibration import calibration_manager
from processing.filtering import sensor_filter_engine
from processing.feature_extraction import feature_extractor
from threshold.threshold_engine import research_threshold_engine
from api.sensor_routes import sensor_api_routes
from api.calibration_routes import calibration_routes
from api.threshold_routes import threshold_routes
from api.alert_routes import alert_routes
from database.database import db


def run_pipeline_tests():
    print("==================================================================")
    print("  RUNNING COMPLETE 8-STAGE ESP32 SENSOR PROCESSING PIPELINE TESTS")
    print("==================================================================")

    # -------------------------------------------------------------
    # STAGE 1 & 2: RECEPTION & VALIDATION
    # -------------------------------------------------------------
    print("\n[STAGE 1 & 2] Testing Reception & Sensor Data Validation...")
    raw_packet = {
        "device_id": "ESP32_01",
        "timestamp": time.time(),
        "api_key": "ESP32_SECURE_KEY_2026",
        "sensors": {
            "max30102": {"red": 120000, "ir": 130000, "heart_rate": 78.0, "spo2": 98.0},
            "mpu6050": {"accel": {"x": 0.05, "y": 0.02, "z": 0.98}, "gyro": {"x": 0.1, "y": 0.2, "z": 0.3}},
            "bme280": {"temperature": 25.5, "humidity": 55.0, "pressure": 1012.0}
        }
    }
    val_data, err = sensor_validator.validate_packet(raw_packet)
    assert err is None, f"Validation failed on valid payload: {err}"
    assert "max30102" in val_data and "mpu6050" in val_data and "environment" in val_data
    print("  ✓ Stage 2: Standard BME280 packet passed validation.")

    # BMP280 validation (no humidity)
    bmp_packet = {
        "device_id": "ESP32_01",
        "timestamp": time.time(),
        "sensors": {
            "bmp280": {"temperature": 24.2, "pressure": 1011.5}
        }
    }
    val_bmp, err_bmp = sensor_validator.validate_packet(bmp_packet)
    assert err_bmp is None
    assert val_bmp["environment"]["humidity"] is None
    assert val_bmp["environment"]["type"] == "BMP280"
    print("  ✓ Stage 2: BMP280 packet passed (humidity properly null).")

    # Invalid range check (e.g. NaN or impossible acceleration)
    nan_packet = {
        "device_id": "ESP32_01",
        "sensors": {"mpu6050": {"accel": {"x": 999.0, "y": 0.0, "z": 0.0}}}
    }
    _, nan_err = sensor_validator.validate_packet(nan_packet)
    assert nan_err is not None, "Failed to reject impossible acceleration!"
    print("  ✓ Stage 2: Out-of-bounds measurement properly rejected.")

    # -------------------------------------------------------------
    # STAGE 3: CALIBRATION
    # -------------------------------------------------------------
    print("\n[STAGE 3] Testing Configurable Offset & Scale Calibration...")
    calibration_manager.set_calibration("bme280_bmp280", {"temp_offset": 1.0, "temp_scale": 1.05})
    calibrated = calibration_manager.calibrate(val_data)
    expected_temp = round((25.5 - 1.0) * 1.05, 2)
    assert calibrated["environment"]["temperature"] == expected_temp
    print(f"  ✓ Stage 3: Temperature calibrated correctly to {expected_temp}°C.")

    # Reset calibration
    calibration_manager.set_calibration("bme280_bmp280", {"temp_offset": 0.0, "temp_scale": 1.0})

    # -------------------------------------------------------------
    # STAGE 4: SIGNAL FILTERING
    # -------------------------------------------------------------
    print("\n[STAGE 4] Testing Digital Filtering (DC Baseline & Low-Pass)...")
    filtered = sensor_filter_engine.filter_telemetry(calibrated)
    assert "dc_red" in filtered["max30102"] and "ac_red" in filtered["max30102"]
    assert "filtered_ax" in filtered["mpu6050"]
    print("  ✓ Stage 4: PPG DC baseline tracked and AC pulsatile component isolated.")
    print("  ✓ Stage 4: MPU6050 low-pass filter evaluated.")

    # -------------------------------------------------------------
    # STAGE 5: FEATURE EXTRACTION
    # -------------------------------------------------------------
    print("\n[STAGE 5] Testing Feature Extraction (BPM, SpO2, SQI, Magnitudes)...")
    extracted = feature_extractor.extract_features(filtered)
    feats = extracted["features"]
    assert feats["max30102"]["signal_quality_index"] > 50.0
    assert feats["mpu6050"]["accel_magnitude"] > 0.9
    assert feats["mpu6050"]["activity"] == "STATIONARY"
    print(f"  ✓ Stage 5: Features extracted: SQI={feats['max30102']['signal_quality_index']}%, Accel Mag={feats['mpu6050']['accel_magnitude']}g, Activity={feats['mpu6050']['activity']}.")

    # -------------------------------------------------------------
    # STAGE 6: THRESHOLD EVALUATION & DEBOUNCING
    # -------------------------------------------------------------
    print("\n[STAGE 6] Testing Research Threshold Engine (Debouncing & Hysteresis)...")
    th_evals = research_threshold_engine.evaluate_features(extracted)
    assert th_evals["heart_rate"]["status"] == "NORMAL"
    assert th_evals["heart_rate"]["confidence"] > 0.5
    print("  ✓ Stage 6: Resting Heart Rate evaluated as NORMAL.")

    # Test debouncing on high heart rate (115 BPM)
    high_hr_data = dict(extracted)
    high_hr_data["features"]["max30102"]["heart_rate"] = 118.0
    
    # 1 single sample should NOT immediately switch to HIGH
    res1 = research_threshold_engine.evaluate_features(high_hr_data)
    assert res1["heart_rate"]["status"] == "NORMAL", "Debouncing failed: single sample triggered alert!"

    # 4 consecutive samples SHOULD switch to HIGH
    for _ in range(4):
        res_high = research_threshold_engine.evaluate_features(high_hr_data)
    assert res_high["heart_rate"]["status"] in ["HIGH", "CRITICAL"]
    print("  ✓ Stage 6: Debouncer successfully promoted 4 consecutive high readings to HIGH.")

    # -------------------------------------------------------------
    # STAGE 7 & 8: REST API ENDPOINTS & DATABASE
    # -------------------------------------------------------------
    print("\n[STAGE 7 & 8] Testing REST API Ingestion & Queries (/api/v1/...)...")
    
    # Auth test
    bad_packet = dict(raw_packet)
    bad_packet["api_key"] = "INVALID_KEY"
    code, _ = sensor_api_routes.handle_ingest_sensor_data({"x-api-key": "INVALID_KEY"}, bad_packet)
    assert code == 401
    print("  ✓ API: Unauthorized request rejected with 401.")

    # Ingest test
    code, resp = sensor_api_routes.handle_ingest_sensor_data({"x-api-key": "ESP32_SECURE_KEY_2026"}, raw_packet)
    assert code == 200 and resp["status"] == "success"
    print("  ✓ API: POST /api/v1/sensor-data succeeded with 200.")

    # Latest readings test
    code, latest = sensor_api_routes.handle_get_latest()
    assert code == 200 and latest["is_online"] is True
    print("  ✓ API: GET /api/v1/readings/latest returned valid telemetry snapshot.")

    # History test
    code, hist = sensor_api_routes.handle_get_history("5m")
    assert code == 200 and hist["count"] > 0
    print(f"  ✓ API: GET /api/v1/readings/history returned {hist['count']} records.")

    # Calibration API test
    code, cal_resp = calibration_routes.handle_get_calibration()
    assert code == 200 and "max30102" in cal_resp["calibration"]
    print("  ✓ API: GET /api/v1/calibration returned active sensor profiles.")

    # Thresholds API test
    code, th_resp = threshold_routes.handle_get_thresholds()
    assert code == 200 and "heart_rate" in th_resp["thresholds"]
    print("  ✓ API: GET /api/v1/thresholds returned active thresholds & baselines.")

    # Alerts API test
    code, alerts_resp = alert_routes.handle_get_alerts()
    assert code == 200
    print(f"  ✓ API: GET /api/v1/alerts returned {alerts_resp['count']} alerts.")

    # System Status API test
    code, sys_status = sensor_api_routes.handle_get_system_status()
    assert code == 200 and sys_status["system_status"] == "OPERATIONAL"
    print("  ✓ API: GET /api/v1/system/status confirmed system is OPERATIONAL.")

    print("\n" + "=" * 66)
    print("  🎉 ALL 8 PIPELINE STAGES & API ENDPOINTS VALIDATED SUCCESSFULLY!")
    print("==================================================================\n")


if __name__ == "__main__":
    run_pipeline_tests()
