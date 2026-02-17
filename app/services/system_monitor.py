import json
import os

import psutil
import urllib.request


def get_system_health():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory_percent": mem.percent,
        "memory_used_mb": round(mem.used / (1024 * 1024)),
        "memory_total_mb": round(mem.total / (1024 * 1024)),
        "disk_percent": disk.percent,
    }


def get_telegraf_status():
    from flask import current_app
    health_url = current_app.config.get("TELEGRAF_HEALTH_URL", "http://localhost:8080")
    try:
        req = urllib.request.urlopen(health_url, timeout=3)
        return {"running": True, "status_code": req.getcode()}
    except Exception:
        return {"running": False, "status_code": None}


def get_telegraf_metrics():
    from flask import current_app
    metrics_file = current_app.config.get("TELEGRAF_METRICS_FILE", "/tmp/telegraf-metrics/metrics.json")

    default = {
        "opcua_gathered": 0,
        "mqtt_written": 0,
        "mqtt_dropped": 0,
        "opcua_errors": 0,
        "opcua_read_success": 0,
        "opcua_read_error": 0,
        "last_updated": None,
    }

    if not os.path.exists(metrics_file):
        return default

    try:
        with open(metrics_file, "r") as f:
            content = f.read().strip()

        if not content:
            return default

        # Telegraf file output writes one JSON per line; get the last relevant entries
        lines = content.strip().split("\n")
        metrics = default.copy()

        found = {"opcua_gather": False, "mqtt_write": False, "opcua_status": False}

        for line in reversed(lines):
            if all(found.values()):
                break
            try:
                data = json.loads(line)
                name = data.get("name", "")
                tags = data.get("tags", {})
                fields = data.get("fields", {})

                # OPC UA metrics gathered
                if name == "internal_gather" and tags.get("input") == "opcua" and not found["opcua_gather"]:
                    metrics["opcua_gathered"] = fields.get("metrics_gathered", 0)
                    metrics["opcua_errors"] = fields.get("errors", 0)
                    metrics["last_updated"] = data.get("timestamp")
                    found["opcua_gather"] = True

                # MQTT metrics written
                elif name == "internal_write" and tags.get("output") == "mqtt" and not found["mqtt_write"]:
                    metrics["mqtt_written"] = fields.get("metrics_written", 0)
                    metrics["mqtt_dropped"] = fields.get("metrics_dropped", 0)
                    found["mqtt_write"] = True

                # OPC UA read success/error
                elif name == "internal_opcua" and not found["opcua_status"]:
                    metrics["opcua_read_success"] = fields.get("read_success", 0)
                    metrics["opcua_read_error"] = fields.get("read_error", 0)
                    found["opcua_status"] = True

            except (json.JSONDecodeError, KeyError):
                continue

        return metrics
    except Exception:
        return default
