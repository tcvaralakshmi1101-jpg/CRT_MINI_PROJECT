from flask import Blueprint, jsonify
from backend.services.gemini_service  import health_check
from backend.services.patient_service import get_stats

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def api_health():
    stats = get_stats()
    return jsonify({
        "status"          : "ok",
        "queue_size"      : stats["queue_size"],
        "treated_today"   : stats["treated_today"],
        "gemini_available": health_check()
    }), 200
