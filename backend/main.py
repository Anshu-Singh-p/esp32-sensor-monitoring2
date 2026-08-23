"""
ESP32 Sensor Monitoring & Threshold-Alert Dashboard
Main Backend Server (HTTP, REST, Real-time Stream & Static Asset Serving)
"""

import os
import sys
import json
import time
import urllib.parse
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

# Ensure backend root is in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "frontend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from api.sensor_routes import sensor_api_routes
from services.simulator import esp32_simulator
from database.database import db

# Active streaming client queues for live telemetry broadcast
live_clients = set()
live_clients_lock = threading.Lock()
simulator_active = True


def broadcast_telemetry(payload: Dict[str, Any]):
    """Broadcasts live processed telemetry to all active connected streaming clients."""
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
    """Continuously runs the test simulator to feed data if physical ESP32 is not currently sending packets."""
    global simulator_active
    while True:
        if simulator_active:
            try:
                # Check if physical ESP32 has sent data within last 4 seconds
                latest = db.get_latest_reading()
                now = time.time()
                last_time = latest.get("epoch_time", 0) if latest else 0
                
                # If no real packet in last 3 seconds, generate simulated telemetry
                if now - last_time > 2.5:
                    sim_payload = esp32_simulator.generate_payload()
                    headers = {"x-api-key": "ESP32_SECURE_KEY_2026"}
                    status_code, resp = sensor_api_routes.handle_ingest_sensor_data(headers, sim_payload)
                    if status_code == 200:
                        # Broadcast to dashboard
                        _, latest_view = sensor_api_routes.handle_get_latest()
                        broadcast_telemetry(latest_view)
            except Exception as e:
                print(f"[Simulator Loop Error]: {e}")
        time.sleep(1.0)


class ESP32DashboardHandler(BaseHTTPRequestHandler):
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

        if path == "/api/sensor-data/latest":
            code, resp = sensor_api_routes.handle_get_latest()
            self.send_json(code, resp)
        elif path == "/api/sensor-data/history":
            range_val = query.get("range", ["5m"])[0]
            code, resp = sensor_api_routes.handle_get_history(range_val)
            self.send_json(code, resp)
        elif path == "/api/alerts":
            status_val = query.get("status", [None])[0]
            code, resp = sensor_api_routes.handle_get_alerts(status_val)
            self.send_json(code, resp)
        elif path == "/api/thresholds":
            code, resp = sensor_api_routes.handle_get_thresholds()
            self.send_json(code, resp)
        elif path == "/api/device/status":
            code, resp = sensor_api_routes.handle_get_device_status()
            self.send_json(code, resp)
        elif path in ["/api/stream", "/ws"]:
            self.handle_live_stream()
        else:
            self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        if path == "/api/sensor-data":
            headers_dict = {k.lower(): v for k, v in self.headers.items()}
            code, resp = sensor_api_routes.handle_ingest_sensor_data(headers_dict, body)
            if code == 200:
                # Broadcast new reading to dashboard
                _, latest_view = sensor_api_routes.handle_get_latest()
                broadcast_telemetry(latest_view)
            self.send_json(code, resp)
        elif path == "/api/simulator/scenario":
            code, resp = sensor_api_routes.handle_simulator_scenario(body)
            self.send_json(code, resp)
        else:
            self.send_json(404, {"error": "Endpoint not found."})

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        if path == "/api/thresholds":
            code, resp = sensor_api_routes.handle_update_thresholds(body)
            self.send_json(code, resp)
        elif path.startswith("/api/alerts/") and path.endswith("/status"):
            # Path: /api/alerts/<id>/status
            parts = path.strip("/").split("/")
            if len(parts) == 4:
                alert_id = parts[2]
                new_status = body.get("status", "RESOLVED")
                code, resp = sensor_api_routes.handle_update_alert_status(alert_id, new_status)
                self.send_json(code, resp)
            else:
                self.send_json(400, {"error": "Invalid alert path format."})
        else:
            self.send_json(404, {"error": "Endpoint not found."})

    def handle_live_stream(self):
        """Server-Sent Events / streaming handler for live dashboard socket."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_cors_headers()
        self.end_headers()

        with live_clients_lock:
            live_clients.add(self.wfile)

        # Send initial latest snapshot immediately
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
                # Keep-alive heartbeat ping
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
        if "GET /api/stream" in args[0] or "GET /api/sensor-data/latest" in args[0]:
            return
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


def run_app(port: int = 8080):
    # Start background simulator thread
    sim_thread = threading.Thread(target=background_simulator_loop, daemon=True)
    sim_thread.start()

    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, ESP32DashboardHandler)
    print("=" * 65)
    print("  ESP32 SENSOR MONITORING & THRESHOLD-ALERT SYSTEM")
    print(f"  Web Dashboard:      http://localhost:{port}")
    print(f"  Ingestion Endpoint: http://localhost:{port}/api/sensor-data")
    print(f"  Live Telemetry WS:  http://localhost:{port}/api/stream")
    print("=" * 65)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_app(port)
