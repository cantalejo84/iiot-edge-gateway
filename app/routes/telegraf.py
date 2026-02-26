import os
from flask import Blueprint, jsonify, current_app

from app.services import config_store
from app.services.telegraf_config import render_config

telegraf_bp = Blueprint("telegraf", __name__)


@telegraf_bp.route("/api/telegraf/preview", methods=["GET"])
def preview_config():
    """Return the currently running telegraf.conf from disk."""
    output_path = os.path.join(current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf")
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            content = f.read()
    else:
        content = "# No config deployed yet.\n# Use 'Deploy config' to generate and apply telegraf.conf."
    return jsonify({"config": content})


@telegraf_bp.route("/api/telegraf/generate", methods=["POST"])
def generate_config():
    from app.services import event_log
    config = config_store.load()
    rendered = render_config(config)
    output_path = os.path.join(current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf")
    with open(output_path, "w") as f:
        f.write(rendered)
    config_store.mark_applied()

    restart_result = _restart_telegraf()

    if restart_result.get("ok"):
        event_log.log("info", "telegraf", "Config applied and agent restarted")
    else:
        event_log.log("error", "telegraf", "Config applied but restart failed", detail=restart_result.get("error"))

    return jsonify({"ok": True, "path": output_path, "restart": restart_result})


def _restart_telegraf():
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(filters={"name": "telegraf"})
        for container in containers:
            container.restart(timeout=10)
        return {"ok": True, "message": f"Restarted {len(containers)} container(s)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@telegraf_bp.route("/api/telegraf/status", methods=["GET"])
def telegraf_status():
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        if not containers:
            return jsonify({"ok": True, "running": False})
        running = containers[0].status == "running"
        return jsonify({"ok": True, "running": running})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@telegraf_bp.route("/api/telegraf/stop", methods=["POST"])
def stop_telegraf():
    from app.services import event_log
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(filters={"name": "telegraf"})
        for container in containers:
            container.stop(timeout=10)
        event_log.log("warning", "telegraf", "Agent stopped manually")
        return jsonify({"ok": True})
    except Exception as e:
        event_log.log("error", "telegraf", "Failed to stop agent", detail=str(e))
        return jsonify({"ok": False, "error": str(e)})


@telegraf_bp.route("/api/telegraf/start", methods=["POST"])
def start_telegraf():
    from app.services import event_log
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        for container in containers:
            container.start()
        event_log.log("info", "telegraf", "Agent started manually")
        return jsonify({"ok": True})
    except Exception as e:
        event_log.log("error", "telegraf", "Failed to start agent", detail=str(e))
        return jsonify({"ok": False, "error": str(e)})
