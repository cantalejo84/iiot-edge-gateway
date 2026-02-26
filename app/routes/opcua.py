import asyncio
from flask import Blueprint, jsonify, request, render_template

from app.services import config_store

opcua_bp = Blueprint("opcua", __name__)


# --- Page routes ---

@opcua_bp.route("/opcua/config")
def opcua_config_page():
    config = config_store.get_section("opcua")
    is_dirty = config_store.is_dirty()
    return render_template("opcua_config.html", config=config, is_dirty=is_dirty)


@opcua_bp.route("/opcua/browser")
def opcua_browser_page():
    is_dirty = config_store.is_dirty()
    return render_template("opcua_browser.html", is_dirty=is_dirty)


@opcua_bp.route("/opcua/nodes")
def opcua_nodes_page():
    nodes = config_store.get_section("nodes")
    is_dirty = config_store.is_dirty()
    return render_template("node_selection.html", nodes=nodes, is_dirty=is_dirty)


# --- API routes ---

@opcua_bp.route("/api/opcua/config", methods=["GET"])
def get_opcua_config():
    return jsonify(config_store.get_section("opcua"))


@opcua_bp.route("/api/opcua/config", methods=["POST"])
def save_opcua_config():
    data = request.get_json()
    config_store.update_section("opcua", data)
    return jsonify({"ok": True})


@opcua_bp.route("/api/opcua/test-connection", methods=["POST"])
def test_opcua_connection():
    from app.services.opcua_client import test_connection
    from app.services import event_log
    config = config_store.get_section("opcua")
    data = request.get_json() or {}
    merged = {**config, **data}
    endpoint = merged.get("endpoint", "")
    result = asyncio.run(test_connection(merged))
    if result.get("ok"):
        event_log.log("info", "opcua", f"Connection OK → {endpoint}")
    else:
        event_log.log("error", "opcua", f"Connection failed → {endpoint}", detail=result.get("detail") or result.get("error"))
    return jsonify(result)


@opcua_bp.route("/api/opcua/browse", methods=["GET"])
def browse_opcua_nodes():
    from app.services.opcua_client import browse_children
    config = config_store.get_section("opcua")
    node_id = request.args.get("node_id", "ns=0;i=85")
    try:
        result = asyncio.run(browse_children(config, node_id))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@opcua_bp.route("/api/opcua/node-details", methods=["GET"])
def get_node_details():
    from app.services.opcua_client import read_node_details
    config = config_store.get_section("opcua")
    node_id = request.args.get("node_id")
    if not node_id:
        return jsonify({"error": "node_id is required"}), 400
    try:
        result = asyncio.run(read_node_details(config, node_id))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@opcua_bp.route("/api/opcua/nodes", methods=["GET"])
def get_selected_nodes():
    return jsonify(config_store.get_section("nodes"))


@opcua_bp.route("/api/opcua/nodes", methods=["POST"])
def save_selected_nodes():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({"error": "Expected a list of nodes"}), 400
    config_store.update_section("nodes", data)
    return jsonify({"ok": True})
