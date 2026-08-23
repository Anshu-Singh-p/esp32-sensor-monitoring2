"""
ESP32 Sensor Processing Automated Test Suite (Root Launcher)
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_TESTS_DIR = os.path.join(BASE_DIR, "..", "backend", "tests")
if BACKEND_TESTS_DIR not in sys.path:
    sys.path.insert(0, BACKEND_TESTS_DIR)

from test_pipeline import run_pipeline_tests

if __name__ == "__main__":
    run_pipeline_tests()
