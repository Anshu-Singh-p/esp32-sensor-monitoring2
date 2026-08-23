"""
ESP32 MAX30102 Signal Quality and Contact Verification Service
Evaluates photoplethysmography (PPG) optical reliability and flags invalid measurements.
"""

from typing import Dict, Any, Tuple


class SignalQualityService:
    def __init__(self):
        # Minimum DC raw IR threshold indicating valid skin contact
        self.contact_ir_threshold = 40000
        self.saturation_ir_threshold = 250000

    def evaluate_max30102(self, max_data: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Evaluates MAX30102 contact and signal quality.
        Returns:
            - is_valid (bool)
            - quality_score (0.0 - 100.0)
            - quality_status ('GOOD', 'ACCEPTABLE', 'POOR', 'NO_CONTACT', 'SATURATED')
        """
        if not max_data:
            return False, 0.0, "NO_DATA"

        finger = max_data.get("finger_detected", False)
        ir = max_data.get("ir")
        red = max_data.get("red")
        hr = max_data.get("heart_rate")
        spo2 = max_data.get("spo2")

        # 1. No contact or low optical signal
        if not finger or (ir is not None and ir < self.contact_ir_threshold):
            return False, 0.0, "NO_CONTACT"

        # 2. Optical saturation (ambient light interference or extreme pressure)
        if ir is not None and ir > self.saturation_ir_threshold:
            return False, 15.0, "SATURATED"

        # 3. Assess physiological feasibility
        quality_score = max_data.get("signal_quality", 90.0) or 90.0
        
        # If heart rate or SpO2 are completely erratic / zero, degrade quality
        if hr is None or hr < 35 or hr > 220:
            quality_score = min(quality_score, 45.0)
        
        if spo2 is None or spo2 < 50:
            quality_score = min(quality_score, 40.0)

        # 4. Determine status
        if quality_score >= 80.0:
            status = "GOOD"
            is_valid = True
        elif quality_score >= 60.0:
            status = "ACCEPTABLE"
            is_valid = True
        else:
            status = "POOR"
            is_valid = False

        return is_valid, round(quality_score, 1), status


signal_quality_service = SignalQualityService()
