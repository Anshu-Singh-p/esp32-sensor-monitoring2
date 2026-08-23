"""
ESP32 Sensor Processing Backend Server
Serves production REST API endpoints (/api/v1/...), real-time Server-Sent Events (/api/v1/stream),
background telemetry simulator, and static dashboard assets.
"""

import os
import sys
import json
import time
import urllib.parse
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "frontend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from api.sensor_routes import sensor_api_routes
from api.threshold_routes import threshold_routes
from api.calibration_routes import calibration_routes
from api.alert_routes import alert_routes
from services.simulator import esp32_simulator
from database.database import db

live_clients = set()
live_clients_lock = threading.Lock()
simulator_active = True


def broadcast_telemetry(payload: Dict[str, Any]):
    with live_clients_lock:
        if not live_clients:
            return
        data_str = f"data: {json.dumps(payload)}\n\n"
        dead_clients = []
        for client_wfile in live_clients:
            try:
                client_wfile.write(data_str.encode("utf-8"))
                client_wfile.flush()
            except Exception:
                dead_clients.append(client_wfile)
        for d in dead_clients:
            live_clients.discard(d)


def background_simulator_loop():
    global simulator_active
    while True:
        if simulator_active:
            try:
                latest = db.get_latest_reading()
                now = time.time()
                last_time = latest.get("epoch_time", 0) if latest else 0
                
                if now - last_time > 2.0:
                    sim_payload = esp32_simulator.generate_payload()
                    headers = {"x-api-key": "ESP32_SECURE_KEY_2026"}
                    status_code, resp = sensor_api_routes.handle_ingest_sensor_data(headers, sim_payload)
                    if status_code == 200:
                        _, latest_view = sensor_api_routes.handle_get_latest()
                        broadcast_telemetry(latest_view)
            except Exception as e:
                print(f"[Simulator Loop Exception]: {e}")
        time.sleep(1.0)


class ProductionDashboardHandler(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Readings
        if path in ["/api/v1/readings/latest", "/api/sensor-data/latest"]:
            code, resp = sensor_api_routes.handle_get_latest()
            self.send_json(code, resp)
        elif path in ["/api/v1/readings/history", "/api/sensor-data/history"]:
            range_val = query.get("range", ["5m"])[0]
            code, resp = sensor_api_routes.handle_get_history(range_val)
            self.send_json(code, resp)

        # 2. Devices
        elif path == "/api/v1/devices":
            code, resp = sensor_api_routes.handle_get_devices()
            self.send_json(code, resp)
        elif path.startswith("/api/v1/devices/"):
            device_id = path.split("/")[-1]
            code, resp = sensor_api_routes.handle_get_device_detail(device_id)
            self.send_json(code, resp)

        # 3. Alerts
        elif path in ["/api/v1/alerts", "/api/alerts"]:
            status_val = query.get("status", [None])[0]
            code, resp = alert_routes.handle_get_alerts(status_val)
            self.send_json(code, resp)

        # 4. Thresholds
        elif path in ["/api/v1/thresholds", "/api/thresholds"]:
            code, resp = threshold_routes.handle_get_thresholds()
            self.send_json(code, resp)

        # 5. Calibration
        elif path == "/api/v1/calibration":
            code, resp = calibration_routes.handle_get_calibration()
            self.send_json(code, resp)

        # 6. System Status
        elif path in ["/api/v1/system/status", "/api/device/status"]:
            code, resp = sensor_api_routes.handle_get_system_status()
            self.send_json(code, resp)

        # 7. Real-Time Stream
        elif path in ["/api/v1/stream", "/api/stream", "/ws"]:
            self.handle_live_stream()

        # 8. Static Assets
        else:
            self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        if path in ["/api/v1/sensor-data", "/api/sensor-data"]:
            headers_dict = {k.lower(): v for k, v in self.headers.items()}
            code, resp = sensor_api_routes.handle_ingest_sensor_data(headers_dict, body)
            if code == 200:
                _, latest_view = sensor_api_routes.handle_get_latest()
                broadcast_telemetry(latest_view)
            self.send_json(code, resp)

        elif path.startswith("/api/v1/alerts/") and path.endswith("/acknowledge"):
            alert_id = path.split("/")[-2]
            code, resp = alert_routes.handle_acknowledge_alert(alert_id)
            self.send_json(code, resp)

        elif path.startswith("/api/v1/alerts/") and path.endswith("/resolve"):
            alert_id = path.split("/")[-2]
            code, resp = alert_routes.handle_resolve_alert(alert_id)
            self.send_json(code, resp)

        elif path in ["/api/v1/simulator/scenario", "/api/simulator/scenario"]:
            code, resp = sensor_api_routes.handle_simulator_scenario(body)
            self.send_json(code, resp)
        else:
            self.send_json(404, {"error": f"Endpoint '{path}' not found."})

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        if path.startswith("/api/v1/thresholds/"):
            param = path.split("/")[-1]
            code, resp = threshold_routes.handle_update_threshold(param, body)
            self.send_json(code, resp)

        elif path in ["/api/thresholds", "/api/v1/thresholds"]:
            for p, cfg in body.items():
                if isinstance(cfg, dict):
                    threshold_routes.handle_update_threshold(p, cfg)
            code, resp = threshold_routes.handle_get_thresholds()
            self.send_json(code, resp)

        elif path.startswith("/api/v1/calibration/"):
            sensor = path.split("/")[-1]
            code, resp = calibration_routes.handle_update_calibration(sensor, body)
            self.send_json(code, resp)

        elif path.startswith("/api/alerts/") and path.endswith("/status"):
            alert_id = path.split("/")[3]
            new_status = body.get("status", "RESOLVED")
            if new_status == "ACKNOWLEDGED":
                code, resp = alert_routes.handle_acknowledge_alert(alert_id)
            else:
                code, resp = alert_routes.handle_resolve_alert(alert_id)
            self.send_json(code, resp)
        else:
            self.send_json(404, {"error": f"Endpoint '{path}' not found."})

    def handle_live_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_cors_headers()
        self.end_headers()

        with live_clients_lock:
            live_clients.add(self.wfile)

        _, latest = sensor_api_routes.handle_get_latest()
        init_data = f"data: {json.dumps(latest)}\n\n"
        try:
            self.wfile.write(init_data.encode("utf-8"))
            self.wfile.flush()
        except Exception:
            return

        try:
            while True:
                time.sleep(10.0)
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with live_clients_lock:
                live_clients.discard(self.wfile)

    def read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length).decode("utf-8")
            try:
                return json.loads(raw)
            except Exception:
                return {}
        return {}

    def send_json(self, status_code: int, data: Any):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def serve_static(self, path: str):
        if path in ["", "/"]:
            path = "/index.html"

        clean_path = os.path.normpath(path.lstrip("/"))
        file_path = os.path.join(FRONTEND_DIR, clean_path)

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            file_path = os.path.join(FRONTEND_DIR, "index.html")

        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon"
        }
        content_type = mime_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_json(500, {"error": f"Asset read error: {e}"})

    def log_message(self, format, *args):
        try:
            msg = format % args
            if "GET /api/v1/stream" in msg or "GET /api/v1/readings/latest" in msg or "/api/stream" in msg:
                return
            sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), msg))
        except Exception:
            pass


def run_app(port: int = 8080):
    sim_thread = threading.Thread(target=background_simulator_loop, daemon=True)
    sim_thread.start()

    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, ProductionDashboardHandler)
    print("=" * 65)
    print("  ESP32 SENSOR DATA PROCESSING & REAL-TIME HEALTH DASHBOARD")
    print(f"  Web Dashboard:       http://localhost:{port}")
    print(f"  API Ingestion:       http://localhost:{port}/api/v1/sensor-data")
    print(f"  Live Stream (SSE):   http://localhost:{port}/api/v1/stream")
    print(f"  Thresholds API:      http://localhost:{port}/api/v1/thresholds")
    print(f"  Calibration API:     http://localhost:{port}/api/v1/calibration")
    print("=" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    env_port = os.environ.get("PORT")
    port = int(env_port) if env_port else 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_app(port)
