"""
ESP32 Sensor Monitoring Automated Test Suite
Verifies data models, filtering, threshold debounce/hysteresis, fall detection, database, and API handlers.
"""

import sys
import os
import time
import json

# Setup sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(TESTS_DIR, "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from models.sensor_models import validate_sensor_payload, SensorValidationError
from services.signal_quality import signal_quality_service
from services.sensor_processor import sensor_processor
from services.threshold_engine import threshold_engine
from services.alert_manager import alert_manager
from database.database import db
from api.sensor_routes import sensor_api_routes
from services.simulator import esp32_simulator


def run_tests():
    print("================================================================")
    print("  RUNNING ESP32 SENSOR MONITORING AUTOMATED VALIDATION SUITE")
    print("================================================================")

    # -------------------------------------------------------------
    # TEST 1: Payload Validation & Range Rejections
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Payload Validation & Operating Limits...")
    valid_bme_payload = {
        "device_id": "ESP32_01",
        "timestamp": time.time(),
        "api_key": "ESP32_SECURE_KEY_2026",
        "max30102": {
            "heart_rate": 78.0,
            "spo2": 98.5,
            "ir": 120000,
            "red": 110000,
            "signal_quality": 95.0,
            "finger_detected": True
        },
        "mpu6050": {
            "accel_x": 0.02,
            "accel_y": 0.01,
            "accel_z": 0.99,
            "gyro_x": 0.4,
            "gyro_y": 0.2,
            "gyro_z": 0.1,
            "activity": "STATIONARY"
        },
        "bme280": {
            "temperature": 25.4,
            "humidity": 55.0,
            "pressure": 1012.5
        }
    }
    cleaned, err = validate_sensor_payload(valid_bme_payload)
    assert err is None, f"Valid BME280 payload rejected: {err}"
    assert cleaned["env_sensor_type"] == "BME280"
    print("  ✓ Valid BME280 payload passed validation.")

    # Valid BMP280 payload (No humidity)
    valid_bmp_payload = {
        "device_id": "ESP32_01",
        "timestamp": time.time(),
        "api_key": "ESP32_SECURE_KEY_2026",
        "bmp280": {
            "temperature": 24.0,
            "pressure": 1010.0
        }
    }
    cleaned_bmp, err = validate_sensor_payload(valid_bmp_payload)
    assert err is None, f"Valid BMP280 payload rejected: {err}"
    assert cleaned_bmp["env_sensor_type"] == "BMP280"
    assert cleaned_bmp["environment"]["humidity"] is None
    print("  ✓ Valid BMP280 payload passed (humidity properly omitted).")

    # Invalid range payload (e.g. Impossible HR = 400 BPM)
    invalid_hr_payload = {
        "device_id": "ESP32_01",
        "max30102": {"heart_rate": 400.0}
    }
    _, err = validate_sensor_payload(invalid_hr_payload)
    assert err is not None, "Failed to reject out-of-bounds heart rate (400 BPM)"
    print("  ✓ Out-of-bounds heart rate properly rejected.")

    # -------------------------------------------------------------
    # TEST 2: Optical Contact & Signal Quality
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing MAX30102 Signal Quality & Contact Checks...")
    valid_sig, score, status = signal_quality_service.evaluate_max30102({
        "finger_detected": True,
        "ir": 130000,
        "red": 115000,
        "heart_rate": 75,
        "spo2": 98
    })
    assert valid_sig is True and status == "GOOD"
    print(f"  ✓ High quality finger contact passed (Score: {score}%, Status: {status}).")

    # Low optical IR test (no finger contact)
    invalid_sig, score, status = signal_quality_service.evaluate_max30102({
        "finger_detected": False,
        "ir": 12000,
        "heart_rate": None,
        "spo2": None
    })
    assert invalid_sig is False and status == "NO_CONTACT"
    print(f"  ✓ No contact correctly flagged (Score: {score}%, Status: {status}).")

    # -------------------------------------------------------------
    # TEST 3: Multi-Stage Fall Detection Algorithm
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing Multi-Stage Fall Detection State Machine...")
    t0 = time.time()
    # Normal motion should not trigger fall
    is_fall, desc = sensor_processor.detect_fall_event(1.02, 5.0, t0)
    assert is_fall is False
    print("  ✓ Normal baseline does not trigger false fall event.")

    # Stage 1: Impact
    sensor_processor.detect_fall_event(3.2, 80.0, t0 + 0.1)
    assert sensor_processor.fall_state == "STAGE1_IMPACT"
    
    # Stage 2: Large rotation
    sensor_processor.detect_fall_event(1.4, 180.0, t0 + 0.3)
    assert sensor_processor.fall_state == "STAGE2_ROTATION"

    # Stage 3: Post-impact rest (> 1.5s)
    # Feed resting samples
    for i in range(15):
        t_sample = t0 + 0.5 + i * 0.15
        is_fall, desc = sensor_processor.detect_fall_event(1.01, 3.0, t_sample)
        if is_fall:
            break

    assert is_fall is True, "Multi-stage fall event was not confirmed after impact + rotation + rest!"
    print(f"  ✓ Multi-stage fall event confirmed successfully: '{desc}'.")

    # -------------------------------------------------------------
    # TEST 4: Threshold Debounce & Hysteresis
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Threshold Debouncing & False Alert Prevention...")
    th_cfg = threshold_engine.get_thresholds()

    # Isolated high HR reading (1 sample) should NOT trigger alert
    eval1 = threshold_engine.evaluate_heart_rate(115.0, True, True, th_cfg["heart_rate"])
    assert eval1["alert_triggered"] is False, "Single isolated spike triggered false alarm!"
    assert eval1["status"] == "NORMAL"
    print("  ✓ Single isolated high HR spike suppressed by debouncer.")

    # 4 consecutive high HR readings SHOULD trigger alert
    for _ in range(4):
        eval_high = threshold_engine.evaluate_heart_rate(115.0, True, True, th_cfg["heart_rate"])
    assert eval_high["alert_triggered"] is True and eval_high["status"] == "HIGH"
    print("  ✓ Consecutive high HR readings successfully promoted to HIGH status.")

    # Hysteresis recovery: HR dropping to 99 BPM (when high_th=100, hyst=2.0) should NOT clear yet
    eval_hyst = threshold_engine.evaluate_heart_rate(99.0, True, True, th_cfg["heart_rate"])
    assert eval_hyst["status"] == "HIGH", "Hysteresis failed: cleared before dropping below (100 - 2 = 98 BPM)"
    
    # HR dropping to 97 BPM clears back to NORMAL
    eval_cleared = threshold_engine.evaluate_heart_rate(97.0, True, True, th_cfg["heart_rate"])
    assert eval_cleared["status"] == "NORMAL"
    print("  ✓ Hysteresis boundary verified (cleared at 97 BPM).")

    # SpO2 No-Contact rejection
    eval_nocontact = threshold_engine.evaluate_spo2(85.0, False, False, th_cfg["spo2"])
    assert eval_nocontact["alert_triggered"] is False
    assert eval_nocontact["status"] == "INVALID / NO CONTACT"
    print("  ✓ SpO2 no-contact suppressed false hypoxia alarm.")

    # -------------------------------------------------------------
    # TEST 5: Alert Lifecycle & Database Persistence
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing Alert Generation & SQLite Persistence...")
    test_alert = {
        "id": "ALT-TEST001",
        "device_id": "ESP32_01",
        "sensor": "MAX30102",
        "parameter": "heart_rate",
        "value": 118.0,
        "threshold_info": {"high_threshold": 100.0},
        "severity": "WARNING",
        "timestamp": time.time(),
        "status": "ACTIVE",
        "message": "Heart Rate above configured threshold."
    }
    db.insert_alert(test_alert)
    alerts = db.get_alerts("ACTIVE")
    found = any(a["id"] == "ALT-TEST001" for a in alerts)
    assert found is True
    print("  ✓ Alert inserted into SQLite database.")

    # Update alert status to RESOLVED
    db.update_alert_status("ALT-TEST001", "RESOLVED")
    resolved_alerts = db.get_alerts("RESOLVED")
    found_resolved = any(a["id"] == "ALT-TEST001" for a in resolved_alerts)
    assert found_resolved is True
    print("  ✓ Alert lifecycle state transitioned to RESOLVED.")

    # -------------------------------------------------------------
    # TEST 6: REST API Ingestion and Endpoints
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing REST API Handlers...")
    # Auth rejection
    bad_payload = dict(valid_bme_payload)
    bad_payload["api_key"] = "WRONG_KEY"
    code, resp = sensor_api_routes.handle_ingest_sensor_data({"x-api-key": "WRONG_KEY"}, bad_payload)
    assert code == 401
    print("  ✓ Unauthorized API key properly rejected (HTTP 401).")

    # Valid ingestion
    code, resp = sensor_api_routes.handle_ingest_sensor_data({"x-api-key": "ESP32_SECURE_KEY_2026"}, valid_bme_payload)
    assert code == 200 and resp["status"] == "success"
    print("  ✓ Ingestion endpoint accepted valid payload (HTTP 200).")

    # Latest reading API
    code, latest = sensor_api_routes.handle_get_latest()
    assert code == 200
    assert latest["device_id"] == "ESP32_01"
    assert "max30102" in latest and "mpu6050" in latest and "environment" in latest
    print("  ✓ GET /api/sensor-data/latest returned valid structured state.")

    # History API
    code, history = sensor_api_routes.handle_get_history("5m")
    assert code == 200 and history["count"] > 0
    print(f"  ✓ GET /api/sensor-data/history returned {history['count']} data points.")

    # Device Status API
    code, dev_status = sensor_api_routes.handle_get_device_status()
    assert code == 200 and dev_status["status"] == "ONLINE"
    print("  ✓ GET /api/device/status verified device ONLINE.")

    # Simulator Scenario test
    code, sim_res = sensor_api_routes.handle_simulator_scenario({"scenario": "CRITICAL_SPO2"})
    assert code == 200 and sim_res["scenario"] == "CRITICAL_SPO2"
    print("  ✓ POST /api/simulator/scenario switched simulator preset.")

    print("\n" + "=" * 64)
    print("  🎉 ALL AUTOMATED TEST SUITE CHECKS PASSED PERFECTLY!")
    print("================================================================\n")


if __name__ == "__main__":
    run_tests()
