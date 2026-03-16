import os
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify

from app.services import config_store
from app.services.system_monitor import (
    clear_intentional_restart,
    mark_intentional_restart,
    reset_crash_detection,
)
from app.services.telegraf_config import render_config

telegraf_bp = Blueprint("telegraf", __name__)


@telegraf_bp.route("/api/telegraf/preview", methods=["GET"])
def preview_config():
    """Return the currently running telegraf.conf from disk."""
    output_path = os.path.join(
        current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf"
    )
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
    output_path = os.path.join(
        current_app.config["TELEGRAF_OUTPUT_DIR"], "telegraf.conf"
    )
    with open(output_path, "w") as f:
        f.write(rendered)
    config_store.mark_applied()

    deploy_time = time.time()
    reset_crash_detection()  # before restart — prevents false crash on counter reset
    mark_intentional_restart()  # suppress unplanned detection during restart window
    restart_result = _restart_telegraf()

    if restart_result.get("ok"):
        event_log.log("info", "telegraf", "Config applied and agent restarted")
        config_store.record_restart(datetime.now(timezone.utc).isoformat(), "deploy")
        # Wait briefly then check Telegraf logs for config parse errors
        time.sleep(3)
        # Update with precise Docker timestamp, then re-enable unplanned detection
        telegraf_start = _get_telegraf_started_at()
        if telegraf_start:
            config_store.record_restart(telegraf_start, "deploy")
        reset_crash_detection()  # clear stale baseline from old metrics.json before re-enabling
        clear_intentional_restart()
        error_line = _get_telegraf_config_error(since=deploy_time)
        if error_line:
            event_log.log(
                "error", "telegraf", "Telegraf config error detected", detail=error_line
            )
    else:
        reset_crash_detection()
        clear_intentional_restart()
        event_log.log(
            "error",
            "telegraf",
            "Config applied but restart failed",
            detail=restart_result.get("error"),
        )

    return jsonify({"ok": True, "path": output_path, "restart": restart_result})


# Keywords that indicate a genuine config parse/load error in Telegraf logs.
# Runtime errors (OPC UA session drops, MQTT timeouts, etc.) are excluded — they
# are transient and Telegraf recovers from them automatically without intervention.
_CONFIG_ERROR_KEYWORDS = (
    "config",
    "toml",
    "parse",
    "invalid",
    "unknown field",
    "failed to load",
    "cannot parse",
    "error loading",
)


def _get_telegraf_config_error(since):
    """Return the first config-related E! log line emitted after `since` (Unix timestamp).

    Filters out:
    - Lines logged before the deploy (via Docker SDK `since` param)
    - Runtime E! errors that are not config problems (OPC UA session drops, etc.)
    """
    try:
        import docker

        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        if not containers:
            return None
        logs = (
            containers[0]
            .logs(tail=50, stderr=True, stdout=True, since=int(since))
            .decode("utf-8", errors="replace")
        )
        for line in reversed(logs.splitlines()):
            if " E! " not in line:
                continue
            if any(kw in line.lower() for kw in _CONFIG_ERROR_KEYWORDS):
                return line.strip()
        return None
    except Exception:
        return None


@telegraf_bp.route("/api/telegraf/logs", methods=["GET"])
def telegraf_logs():
    """Return recent Telegraf container log lines."""
    try:
        import docker

        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        if not containers:
            return jsonify({"ok": True, "lines": []})
        raw = (
            containers[0]
            .logs(tail=200, stderr=True, stdout=True)
            .decode("utf-8", errors="replace")
        )
        lines = [line for line in raw.splitlines() if line.strip()]
        return jsonify({"ok": True, "lines": lines})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _get_telegraf_started_at():
    """Return the Telegraf container's current started_at ISO string, or None."""
    try:
        import docker

        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        if not containers:
            return None
        containers[0].reload()
        return containers[0].attrs["State"]["StartedAt"]
    except Exception:
        return None


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
        reset_crash_detection()  # before stop — prevents false crash on counter drop to 0
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
        reset_crash_detection()  # before start — prevents false crash on counter reset
        mark_intentional_restart()  # suppress unplanned detection during restart window
        for container in containers:
            container.start()
        config_store.record_restart(datetime.now(timezone.utc).isoformat(), "manual")
        # Brief wait for Docker to update StartedAt, then update with precise timestamp
        time.sleep(2)
        telegraf_start = _get_telegraf_started_at()
        if telegraf_start:
            config_store.record_restart(telegraf_start, "manual")
        reset_crash_detection()  # clear stale baseline from old metrics.json before re-enabling
        clear_intentional_restart()  # re-enable unplanned detection
        event_log.log("info", "telegraf", "Agent started manually")
        return jsonify({"ok": True})
    except Exception as e:
        event_log.log("error", "telegraf", "Failed to start agent", detail=str(e))
        return jsonify({"ok": False, "error": str(e)})
