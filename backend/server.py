"""
Edge AI Health Companion - Backend Server
Provides REST endpoints, Server-Sent Events (SSE) live telemetry streaming,
and static frontend file serving with zero external dependencies.
"""

import os
import sys
import json
import time
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

# Ensure backend directory is in python sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from edge_ai_engine import EdgeAIEngine
from telemetry_simulator import TelemetrySimulator

# Singleton engine & simulator instances
engine = EdgeAIEngine()
simulator = TelemetrySimulator()
dismissed_alerts = set()


class HealthCompanionHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler serving REST APIs, SSE telemetry streams,
    and static frontend assets.
    """

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self.handle_api_status()
        elif path == "/api/vitals":
            self.handle_api_vitals()
        elif path == "/api/history":
            self.handle_api_history()
        elif path == "/api/alerts":
            self.handle_api_alerts()
        elif path == "/api/stream":
            self.handle_api_stream()
        else:
            self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/simulate":
            scenario = data.get("scenario", "normal")
            res = simulator.set_scenario(scenario)
            dismissed_alerts.clear()
            self.send_json(200, res)
        elif path == "/api/alerts/dismiss":
            alert_id = data.get("id")
            if alert_id:
                dismissed_alerts.add(alert_id)
            self.send_json(200, {"status": "dismissed", "id": alert_id})
        elif path == "/api/edge-ai/recalibrate":
            res = engine.recalibrate()
            self.send_json(200, res)
        else:
            self.send_json(404, {"error": "Endpoint not found"})

    def handle_api_status(self):
        status_data = {
            "system": "Edge AI Health Companion",
            "version": "3.2.0-Production",
            "status": "Operational",
            "edge_engine": engine.model_name,
            "hardware": engine.hardware_target,
            "quantization": engine.quantization,
            "inferences_performed": engine.inference_count,
            "uptime_seconds": round(time.time() - simulator.start_time, 1),
            "simulated_scenario": simulator.scenario
        }
        self.send_json(200, status_data)

    def handle_api_vitals(self):
        vitals = simulator.update_telemetry()
        ai_meta, raw_alerts = engine.run_inference(vitals, simulator.scenario)
        active_alerts = [a for a in raw_alerts if a["id"] not in dismissed_alerts]
        ecg_chunk = simulator.generate_ecg_chunk(40)

        response = {
            "vitals": vitals,
            "edge_ai": ai_meta,
            "alerts": active_alerts,
            "ecg_waveform": ecg_chunk
        }
        self.send_json(200, response)

    def handle_api_history(self):
        history = simulator.get_history()
        self.send_json(200, history)

    def handle_api_alerts(self):
        vitals = simulator.update_telemetry()
        _, raw_alerts = engine.run_inference(vitals, simulator.scenario)
        active_alerts = [a for a in raw_alerts if a["id"] not in dismissed_alerts]
        self.send_json(200, {"alerts": active_alerts, "dismissed_count": len(dismissed_alerts)})

    def handle_api_stream(self):
        """
        Server-Sent Events (SSE) handler streaming real-time vitals, AI inference, and ECG samples.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_cors_headers()
        self.end_headers()

        try:
            while True:
                vitals = simulator.update_telemetry()
                ai_meta, raw_alerts = engine.run_inference(vitals, simulator.scenario)
                active_alerts = [a for a in raw_alerts if a["id"] not in dismissed_alerts]
                ecg_chunk = simulator.generate_ecg_chunk(35)

                payload = {
                    "vitals": vitals,
                    "edge_ai": ai_meta,
                    "alerts": active_alerts,
                    "ecg_waveform": ecg_chunk,
                    "timestamp": time.time()
                }

                data_str = f"data: {json.dumps(payload)}\n\n"
                self.wfile.write(data_str.encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.75)  # Stream frequency: ~1.3 Hz updates
        except (BrokenPipeError, ConnectionResetError):
            pass

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

        # Sanitize path to prevent directory traversal
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
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2"
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
            self.send_json(500, {"error": f"Failed to read asset: {str(e)}"})

    def log_message(self, format, *args):
        # Suppress routine GET logging for cleaner terminal output
        if "GET /api/stream" in args[0] or "GET /api/vitals" in args[0]:
            return
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))


def run_server(port: int = 8080):
    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, HealthCompanionHandler)
    print(f"==================================================")
    print(f"  Edge AI Health Companion Server Active")
    print(f"  Serving dashboard at: http://localhost:{port}")
    print(f"  Live Stream Endpoint:  http://localhost:{port}/api/stream")
    print(f"  Press Ctrl+C to terminate.")
    print(f"==================================================")
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
    run_server(port)
