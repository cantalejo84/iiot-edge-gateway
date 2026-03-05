import io
import json
import os
import time

from flask import Blueprint, current_app, jsonify, render_template, request, send_file

from app.services import config_store, event_log
from app.services.system_monitor import get_telegraf_version
from app.services.telegraf_config import render_config

configuration_bp = Blueprint("configuration", __name__)


@configuration_bp.route("/configuration")
def configuration_page():
    return render_template("configuration.html", telegraf_version=get_telegraf_version())


# ── Gateway config export ──────────────────────────────────────────────────────

@configuration_bp.route("/api/configuration/export", methods=["GET"])
def export_config():
    """Download config.json as a file."""
    config = config_store.load()
    data = json.dumps(config, indent=2).encode("utf-8")
    return send_file(
        io.BytesIO(data),
        mimetype="application/json",
        as_attachment=True,
        download_name="gateway-config.json",
    )


# ── Gateway config import ──────────────────────────────────────────────────────

@configuration_bp.route("/api/configuration/import", methods=["POST"])
def import_config():
    """Receive a config.json file, validate and apply it."""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400

    f = request.files["file"]
    try:
        data = json.loads(f.read().decode("utf-8"))
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON file"}), 400

    # Basic structure validation
    expected_keys = {"opcua", "nodes", "mqtt", "modbus", "publishing"}
    if not expected_keys.issubset(data.keys()):
        missing = expected_keys - data.keys()
        return jsonify({"ok": False, "error": f"Missing sections: {', '.join(missing)}"}), 400

    config_store.save(data)
    event_log.log("info", "system", "Gateway config imported from file")
    return jsonify({"ok": True})


# ── Telegraf config read/write ─────────────────────────────────────────────────

@configuration_bp.route("/api/configuration/telegraf", methods=["GET"])
def get_telegraf_config():
    """Return current telegraf.conf from disk."""
    path = os.path.join(current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf")
    if os.path.exists(path):
        with open(path, "r") as fh:
            content = fh.read()
    else:
        content = ""
    return jsonify({"ok": True, "content": content, "exists": os.path.exists(path)})


@configuration_bp.route("/api/configuration/telegraf", methods=["POST"])
def save_telegraf_config():
    """Save edited telegraf.conf and restart Telegraf (does not regenerate from UI config)."""
    body = request.get_json(silent=True)
    if not body or "content" not in body:
        return jsonify({"ok": False, "error": "Missing content"}), 400

    content = body["content"]
    path = os.path.join(current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf")
    with open(path, "w") as fh:
        fh.write(content)

    restart_result = _restart_telegraf()

    if restart_result.get("ok"):
        event_log.log("info", "telegraf", "Telegraf config edited manually and agent restarted")
        time.sleep(3)
        error_line = _get_telegraf_config_error()
        if error_line:
            event_log.log("error", "telegraf", "Telegraf failed to load config", detail=error_line)
            return jsonify({"ok": True, "restart": restart_result, "warning": error_line})
    else:
        event_log.log("error", "telegraf", "Manual config saved but restart failed",
                      detail=restart_result.get("error"))

    return jsonify({"ok": True, "restart": restart_result})


# ── Helpers (same as telegraf.py) ─────────────────────────────────────────────

def _restart_telegraf():
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(filters={"name": "telegraf"})
        for c in containers:
            c.restart(timeout=10)
        return {"ok": True, "message": f"Restarted {len(containers)} container(s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_telegraf_config_error():
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        if not containers:
            return None
        logs = containers[0].logs(tail=30, stderr=True, stdout=True).decode("utf-8", errors="replace")
        for line in reversed(logs.splitlines()):
            if " E! " in line:
                return line.strip()
        return None
    except Exception:
        return None
