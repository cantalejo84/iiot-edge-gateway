import json
import os
import time
import urllib.request

import psutil


def get_system_health():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": mem.percent,
        "memory_used_mb": round(mem.used / (1024 * 1024)),
        "memory_total_mb": round(mem.total / (1024 * 1024)),
        "disk_percent": disk.percent,
        "bytes_sent": net.bytes_sent,
        "bytes_recv": net.bytes_recv,
    }


def get_telegraf_status():
    from flask import current_app

    health_url = current_app.config.get("TELEGRAF_HEALTH_URL", "http://localhost:8080")
    try:
        req = urllib.request.urlopen(health_url, timeout=3)  # nosec B310
        return {"running": True, "status_code": req.getcode()}
    except Exception:
        return {"running": False, "status_code": None}


# Module-level state for detecting Telegraf process crashes.
# Cleared by reset_crash_detection() after any intentional restart (deploy / manual start).
_prev_gathered: dict = {}


def reset_crash_detection():
    """Clear the previous-gathered baseline. Call after any intentional Telegraf restart
    so the next metrics poll does not misread the counter reset as a crash."""
    global _prev_gathered
    _prev_gathered = {}


def get_telegraf_metrics():
    from flask import current_app

    metrics_file = current_app.config.get(
        "TELEGRAF_METRICS_FILE",
        "/tmp/telegraf-metrics/metrics.json",  # nosec B108
    )

    default = {
        # OPC UA
        "opcua_gathered": 0,
        "opcua_scan_time_ms": 0,
        "opcua_errors": 0,
        "opcua_read_success": 0,
        "opcua_read_error": 0,
        # Modbus
        "modbus_gathered": 0,
        "modbus_scan_time_ms": 0,
        "modbus_errors": 0,
        # MQTT output (shared)
        "mqtt_written": 0,
        "mqtt_dropped": 0,
        "mqtt_buffer_size": 0,
        "mqtt_buffer_limit": 10000,
        "mqtt_errors": 0,
        "last_updated": None,
    }

    if not os.path.exists(metrics_file):
        return default

    try:
        with open(metrics_file, "r") as f:
            content = f.read().strip()

        if not content:
            return default

        lines = content.strip().split("\n")
        metrics = default.copy()

        def _parse_opcua_gather(fields, data):
            metrics["opcua_gathered"] = fields.get("metrics_gathered", 0)
            metrics["opcua_errors"] = fields.get("errors", 0)
            metrics["opcua_scan_time_ms"] = round(
                fields.get("gather_time_ns", 0) / 1_000_000, 2
            )
            metrics["last_updated"] = data.get("timestamp")

        def _parse_modbus_gather(fields, data):
            metrics["modbus_gathered"] = fields.get("metrics_gathered", 0)
            metrics["modbus_errors"] = fields.get("errors", 0)
            metrics["modbus_scan_time_ms"] = round(
                fields.get("gather_time_ns", 0) / 1_000_000, 2
            )
            if not metrics.get("last_updated"):
                metrics["last_updated"] = data.get("timestamp")

        def _parse_mqtt_write(fields, data):
            metrics["mqtt_written"] = fields.get("metrics_written", 0)
            metrics["mqtt_dropped"] = fields.get("metrics_dropped", 0)
            metrics["mqtt_buffer_size"] = fields.get("buffer_size", 0)
            metrics["mqtt_buffer_limit"] = fields.get("buffer_limit", 10000)
            metrics["mqtt_errors"] = fields.get("errors", 0)

        def _parse_opcua_status(fields, data):
            metrics["opcua_read_success"] = fields.get("read_success", 0)
            metrics["opcua_read_error"] = fields.get("read_error", 0)

        # Key: (metric_name, tag_key, tag_value) — tag_key/value are None for untagged metrics
        parsers = {
            ("internal_gather", "input", "opcua"): _parse_opcua_gather,
            ("internal_gather", "input", "modbus"): _parse_modbus_gather,
            ("internal_write", "output", "mqtt"): _parse_mqtt_write,
            ("internal_opcua", None, None): _parse_opcua_status,
        }
        found = set()

        for line in reversed(lines):
            if len(found) == len(parsers):
                break
            try:
                data = json.loads(line)
                name = data.get("name", "")
                tags = data.get("tags", {})
                fields = data.get("fields", {})

                for key, parser_fn in parsers.items():
                    if key in found:
                        continue
                    metric_name, tag_key, tag_value = key
                    if name != metric_name:
                        continue
                    if tag_key and tags.get(tag_key) != tag_value:
                        continue
                    parser_fn(fields, data)
                    found.add(key)

            except (json.JSONDecodeError, KeyError):
                continue

        # Crash detection: a counter decreasing from a non-trivial value means
        # the Telegraf process restarted inside the container (entrypoint loop).
        global _prev_gathered
        crash_detected = False
        for key in ("opcua_gathered", "modbus_gathered"):
            current = metrics[key]
            prev = _prev_gathered.get(key)
            if prev is not None and prev > 5 and current < prev:
                crash_detected = True
            _prev_gathered[key] = current
        metrics["process_crash_detected"] = crash_detected

        return metrics
    except Exception:
        return default


def _get_telegraf_container_info():
    """Return (started_at_iso, uptime_seconds) for the Telegraf container.

    started_at_iso is the raw Docker timestamp string (e.g. "2026-03-07T10:30:00.123Z").
    uptime_seconds is None if the container is not running or Docker is unavailable.
    Returns (None, None) on any error.
    """
    try:
        import docker
        from datetime import datetime, timezone

        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        if not containers:
            return None, None
        c = containers[0]
        c.reload()
        started_at = c.attrs["State"]["StartedAt"]  # e.g. "2026-03-07T10:30:00.123456789Z"
        if c.status != "running":
            return started_at, None
        # Parse to second precision — strip sub-second portion
        dt_str = started_at[:19]  # "2026-03-07T10:30:00"
        start_dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        uptime = int(time.time() - start_dt.timestamp())
        return started_at, uptime
    except Exception:
        return None, None


def _compute_unexpected_restart(current_started_at, last_deploy_start):
    """Return current_started_at if Telegraf restarted after the last deploy, else None.

    Compares to second precision to tolerate sub-second differences in Docker timestamps.
    Returns None when either argument is missing (no baseline to compare against).
    """
    if not current_started_at or not last_deploy_start:
        return None
    if current_started_at[:19] != last_deploy_start[:19]:
        return current_started_at
    return None


def get_container_status():
    try:
        import docker

        client = docker.from_env()
        project_containers = client.containers.list(
            all=True, filters={"label": "com.docker.compose.project"}
        )

        # Detect our project name from any container we're running inside
        my_project = None
        hostname = os.environ.get("HOSTNAME", "")
        for c in project_containers:
            if c.short_id in hostname or c.name in hostname:
                my_project = c.labels.get("com.docker.compose.project")
                break

        # Fallback: use the most common project label
        if not my_project and project_containers:
            projects = {}
            for c in project_containers:
                p = c.labels.get("com.docker.compose.project", "")
                projects[p] = projects.get(p, 0) + 1
            my_project = max(projects, key=projects.get)

        display_names = {
            "gateway": "Edge UI",
            "telegraf": "Telegraf Data Agent",
            "mosquitto": "MQTT Broker Demo",
            "opcua-demo-server": "OPC-UA Server Demo",
            "modbus-demo-server": "Modbus Server Demo",
        }

        demo_services = {"opcua-demo-server", "mosquitto", "modbus-demo-server"}

        result = []
        for c in project_containers:
            if c.labels.get("com.docker.compose.project") != my_project:
                continue
            service = c.labels.get("com.docker.compose.service", c.name)
            status = c.status
            if status == "exited":
                status = "stopped"
            result.append(
                {
                    "name": display_names.get(service, service),
                    "service": service,
                    "is_demo": service in demo_services,
                    "status": status,
                }
            )

        order = ["Edge UI", "Telegraf Data Agent"]
        result.sort(
            key=lambda x: (
                order.index(x["name"]) if x["name"] in order else len(order),
                x["name"],
            )
        )
        return result
    except Exception:
        return []


def get_gateway_info():
    from app.services import config_store

    config = config_store.load()
    meta = config.get("_meta", {})
    nodes = config.get("nodes", [])

    telegraf_started_at, telegraf_uptime_seconds = _get_telegraf_container_info()

    last_restart = meta.get("last_restart", {})
    # Auto-detect unplanned restart: Telegraf started at a different time than recorded
    if _compute_unexpected_restart(telegraf_started_at, last_restart.get("started_at")):
        config_store.record_restart(telegraf_started_at, "unplanned")
        last_restart = {"started_at": telegraf_started_at, "reason": "unplanned"}

    return {
        "telegraf_uptime_seconds": telegraf_uptime_seconds,
        "last_config_applied": meta.get("last_applied"),
        "last_restart": last_restart,
        "nodes_configured": len(nodes),
        "containers": get_container_status(),
    }


def get_telegraf_version():
    try:
        import docker

        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "telegraf"})
        for c in containers:
            for tag in c.image.tags or []:
                if ":" in tag:
                    ver = tag.split(":")[-1]
                    if ver and ver != "latest":
                        return ver
    except Exception:
        pass
    return None
