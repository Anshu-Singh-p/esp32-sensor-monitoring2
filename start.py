#!/usr/bin/env python3
"""
ESP32 Sensor Monitoring & Threshold-Alert Dashboard
Quickstart launcher: Starts backend server and binds to environment PORT.
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
    time.sleep(1.2)
    url = f"http://localhost:{port}"
    print(f"Opening local browser at {url} ...")
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    # Read port from environment (Render, Railway, Heroku, Cloud Run, etc.) or default to 8080
    env_port = os.environ.get("PORT")
    port = int(env_port) if env_port else 8080

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    # Only open desktop browser in local interactive development (not in headless cloud environment)
    is_cloud = bool(os.environ.get("PORT") or os.environ.get("RENDER") or os.environ.get("DYNO") or os.environ.get("RAILWAY_ENVIRONMENT"))
    if not is_cloud:
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    run_app(port)


if __name__ == "__main__":
    main()
