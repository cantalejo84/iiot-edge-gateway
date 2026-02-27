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


# Accumulators for per-cycle Telegraf counters (reset on process restart)
_acc_lock = __import__("threading").Lock()
_acc = {"opcua_total": 0, "modbus_total": 0, "mqtt_total": 0, "last_ts": None}


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

        found = {
            "opcua_gather": False,
            "modbus_gather": False,
            "mqtt_write": False,
            "opcua_status": False,
        }

        for line in reversed(lines):
            if all(found.values()):
                break
            try:
                data = json.loads(line)
                name = data.get("name", "")
                tags = data.get("tags", {})
                fields = data.get("fields", {})

                if (
                    name == "internal_gather"
                    and tags.get("input") == "opcua"
                    and not found["opcua_gather"]
                ):
                    metrics["opcua_errors"] = fields.get("errors", 0)
                    metrics["opcua_scan_time_ms"] = round(
                        fields.get("gather_time_ns", 0) / 1_000_000, 2
                    )
                    metrics["last_updated"] = data.get("timestamp")
                    found["opcua_gather"] = True

                elif (
                    name == "internal_gather"
                    and tags.get("input") == "modbus"
                    and not found["modbus_gather"]
                ):
                    metrics["modbus_errors"] = fields.get("errors", 0)
                    metrics["modbus_scan_time_ms"] = round(
                        fields.get("gather_time_ns", 0) / 1_000_000, 2
                    )
                    metrics["_cycle_modbus"] = fields.get("metrics_gathered", 0)
                    if not metrics.get("last_updated"):
                        metrics["last_updated"] = data.get("timestamp")
                    found["modbus_gather"] = True

                elif (
                    name == "internal_write"
                    and tags.get("output") == "mqtt"
                    and not found["mqtt_write"]
                ):
                    metrics["_cycle_mqtt_added"] = fields.get("metrics_added", 0)
                    metrics["_cycle_mqtt"] = fields.get("metrics_written", 0)
                    metrics["mqtt_dropped"] = fields.get("metrics_dropped", 0)
                    metrics["mqtt_buffer_size"] = fields.get("buffer_size", 0)
                    metrics["mqtt_buffer_limit"] = fields.get("buffer_limit", 10000)
                    metrics["mqtt_errors"] = fields.get("errors", 0)
                    found["mqtt_write"] = True

                elif name == "internal_opcua" and not found["opcua_status"]:
                    metrics["opcua_read_success"] = fields.get("read_success", 0)
                    metrics["opcua_read_error"] = fields.get("read_error", 0)
                    found["opcua_status"] = True

            except (json.JSONDecodeError, KeyError):
                continue

        # Accumulate per-cycle counts into running totals
        with _acc_lock:
            ts = metrics.get("last_updated")
            if ts and ts != _acc["last_ts"]:
                _acc["opcua_total"] += metrics.get("_cycle_mqtt_added", 0)
                _acc["modbus_total"] += metrics.get("_cycle_modbus", 0)
                _acc["mqtt_total"] += metrics.get("_cycle_mqtt", 0)
                _acc["last_ts"] = ts
            metrics["opcua_gathered"] = _acc["opcua_total"]
            metrics["modbus_gathered"] = _acc["modbus_total"]
            metrics["mqtt_written"] = _acc["mqtt_total"]

        metrics.pop("_cycle_mqtt_added", None)
        metrics.pop("_cycle_modbus", None)
        metrics.pop("_cycle_mqtt", None)
        return metrics
    except Exception:
        return default


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

    # Uptime: time since process start (inside container = container uptime)
    uptime_seconds = int(time.time() - psutil.boot_time())

    # Config info
    config = config_store.load()
    meta = config.get("_meta", {})
    nodes = config.get("nodes", [])

    return {
        "uptime_seconds": uptime_seconds,
        "last_config_applied": meta.get("last_applied"),
        "nodes_configured": len(nodes),
        "containers": get_container_status(),
    }
