import os
from flask import Blueprint, jsonify, current_app

from app.services import config_store
from app.services.telegraf_config import render_config

telegraf_bp = Blueprint("telegraf", __name__)


@telegraf_bp.route("/api/telegraf/preview", methods=["GET"])
def preview_config():
    config = config_store.load()
    rendered = render_config(config)
    return jsonify({"config": rendered})


@telegraf_bp.route("/api/telegraf/generate", methods=["POST"])
def generate_config():
    config = config_store.load()
    rendered = render_config(config)
    output_path = os.path.join(current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf")
    with open(output_path, "w") as f:
        f.write(rendered)
    config_store.mark_applied()

    # Restart Telegraf container
    restart_result = _restart_telegraf()

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
