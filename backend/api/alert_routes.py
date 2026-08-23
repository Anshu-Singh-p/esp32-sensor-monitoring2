"""
API Alert Endpoints (/api/v1/alerts)
Allows listing, acknowledging, and resolving alerts.
"""

from typing import Dict, Any, Tuple, Optional
from database.database import db


class AlertRoutes:
    def handle_get_alerts(self, status: Optional[str] = None) -> Tuple[int, Dict[str, Any]]:
        """GET /api/v1/alerts"""
        alerts = db.get_alerts(status)
        return 200, {
            "status": "success",
            "count": len(alerts),
            "alerts": alerts
        }

    def handle_acknowledge_alert(self, alert_id: str) -> Tuple[int, Dict[str, Any]]:
        """POST /api/v1/alerts/{id}/acknowledge"""
        success = db.update_alert_status(alert_id, "ACKNOWLEDGED")
        if success:
            return 200, {"status": "acknowledged", "alert_id": alert_id}
        return 404, {"error": f"Alert '{alert_id}' not found."}

    def handle_resolve_alert(self, alert_id: str) -> Tuple[int, Dict[str, Any]]:
        """POST /api/v1/alerts/{id}/resolve"""
        success = db.update_alert_status(alert_id, "RESOLVED")
        if success:
            return 200, {"status": "resolved", "alert_id": alert_id}
        return 404, {"error": f"Alert '{alert_id}' not found."}


alert_routes = AlertRoutes()
