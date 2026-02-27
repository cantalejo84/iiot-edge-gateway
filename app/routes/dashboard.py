import os

from flask import Blueprint, current_app, jsonify, render_template

from app.services import config_store, event_log
from app.services.system_monitor import (
    get_gateway_info,
    get_system_health,
    get_telegraf_metrics,
    get_telegraf_status,
)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
def dashboard_page():
    is_dirty = config_store.is_dirty()
    conf_path = os.path.join(current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf")
    never_deployed = not os.path.isfile(conf_path)
    return render_template(
        "dashboard.html", is_dirty=is_dirty, never_deployed=never_deployed
    )


@dashboard_bp.route("/api/dashboard/health", methods=["GET"])
def health():
    return jsonify(get_system_health())


@dashboard_bp.route("/api/dashboard/telegraf-status", methods=["GET"])
def telegraf_status():
    return jsonify(get_telegraf_status())


@dashboard_bp.route("/api/dashboard/telegraf-metrics", methods=["GET"])
def telegraf_metrics():
    return jsonify(get_telegraf_metrics())


@dashboard_bp.route("/api/dashboard/gateway-info", methods=["GET"])
def gateway_info():
    return jsonify(get_gateway_info())


@dashboard_bp.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify(event_log.get_events())


@dashboard_bp.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    event_log.clear()
    return jsonify({"ok": True})
