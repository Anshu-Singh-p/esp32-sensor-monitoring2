#!/usr/bin/env python3
"""
ESP32 Sensor Monitoring & Threshold-Alert Dashboard
Quickstart launcher: Starts backend server and opens web dashboard in default browser.
"""

import sys
import os
import time
import webbrowser
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from main import run_app


def open_browser(port):
    time.sleep(1.0)
    url = f"http://localhost:{port}"
    print(f"Opening browser at {url} ...")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Please open {url} manually in your browser.")


def main():
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    run_app(port)


if __name__ == "__main__":
    main()
