import copy
import json
import os
import threading
from datetime import datetime, timezone

from app.config import DEFAULT_CONFIG

_lock = threading.Lock()


def _config_path():
    from flask import current_app

    return os.path.join(current_app.config["DATA_DIR"], "config.json")


def load():
    with _lock:
        path = _config_path()
        if not os.path.exists(path):
            return copy.deepcopy(DEFAULT_CONFIG)
        with open(path, "r") as f:
            return json.load(f)


def save(config):
    with _lock:
        config["_meta"]["last_modified"] = datetime.now(timezone.utc).isoformat()
        path = _config_path()
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp_path, path)


def get_section(section):
    config = load()
    return config.get(section, {})


def update_section(section, data):
    config = load()
    if section == "nodes":
        config["nodes"] = data
    else:
        config.setdefault(section, {}).update(data)
    save(config)
    return config


def mark_applied():
    with _lock:
        path = _config_path()
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            config = json.load(f)
        now = datetime.now(timezone.utc).isoformat()
        config["_meta"]["last_applied"] = now
        config["_meta"]["last_modified"] = now
        # Snapshot the deployed mqtt config so the tail subscriber uses the right broker
        config["_meta"]["applied_mqtt"] = copy.deepcopy(config.get("mqtt", {}))
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(config, f, indent=2)
        os.replace(tmp_path, path)


def get_applied_section(section):
    """Return the last-deployed snapshot of a config section, or current if never deployed."""
    config = load()
    meta = config.get("_meta", {})
    key = f"applied_{section}"
    if key in meta:
        return meta[key]
    return config.get(section, {})


def is_dirty():
    config = load()
    meta = config.get("_meta", {})
    last_modified = meta.get("last_modified")
    last_applied = meta.get("last_applied")
    if not last_modified:
        return False
    if not last_applied:
        return True
    return last_modified > last_applied
