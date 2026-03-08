import socket

from flask import Blueprint, jsonify, render_template, request

from app.services import config_store, event_log

modbus_bp = Blueprint("modbus", __name__)


# --- Page routes ---


@modbus_bp.route("/modbus/config")
def modbus_config_page():
    config = config_store.get_section("modbus")
    is_dirty = config_store.is_dirty()
    return render_template("modbus_config.html", config=config, is_dirty=is_dirty)


# --- API routes ---


@modbus_bp.route("/api/modbus/config", methods=["GET"])
def get_modbus_config():
    return jsonify(config_store.get_section("modbus"))


@modbus_bp.route("/api/modbus/config", methods=["POST"])
def save_modbus_config():
    data = request.get_json()
    config_store.update_section("modbus", data)
    return jsonify({"ok": True})


@modbus_bp.route("/api/modbus/test-connection", methods=["POST"])
def test_modbus_connection():
    data = request.get_json() or {}
    config = config_store.get_section("modbus")
    merged = {**config, **data}

    controller = merged.get("controller", "")
    slave_id = int(merged.get("slave_id", 1))

    if not controller:
        return jsonify({"ok": False, "error": "Controller address is required"})

    # Parse host:port
    if ":" in controller:
        host, port_str = controller.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return jsonify({"ok": False, "error": f"Invalid port: {port_str}"})
    else:
        host = controller
        port = 502

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        # Modbus TCP read holding registers (function 0x03), address 0, count 1
        request_pdu = bytes(
            [0x00, 0x01, 0x00, 0x00, 0x00, 0x06, slave_id, 0x03, 0x00, 0x00, 0x00, 0x01]
        )
        sock.send(request_pdu)
        response = sock.recv(256)
        sock.close()
        detail = f"Connected to {host}:{port} — slave {slave_id} responded ({len(response)} bytes)"
        event_log.log(
            "info", "modbus", f"Connection OK → {host}:{port} slave {slave_id}"
        )
        return jsonify({"ok": True, "detail": detail})
    except socket.timeout:
        msg = f"Timeout connecting to {host}:{port}"
        event_log.log("error", "modbus", f"Connection failed → {msg}")
        return jsonify({"ok": False, "error": msg})
    except Exception as e:
        event_log.log(
            "error", "modbus", f"Connection failed → {host}:{port}", detail=str(e)
        )
        return jsonify({"ok": False, "error": str(e)})
