from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Sonde du Load Balancer. N'accède jamais au stockage."""
    return jsonify(status="ok"), 200
