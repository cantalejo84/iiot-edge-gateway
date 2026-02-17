import os
from flask import Blueprint, jsonify, request, render_template, current_app

from app.services import config_store

mqtt_bp = Blueprint("mqtt", __name__)


@mqtt_bp.route("/mqtt/config")
def mqtt_config_page():
    config = config_store.get_section("mqtt")
    is_dirty = config_store.is_dirty()
    # Check which cert files exist
    certs_dir = os.path.join(current_app.config["DATA_DIR"], "certs", "mqtt")
    certs_status = {
        "tls_ca": os.path.exists(os.path.join(certs_dir, "ca.pem")),
        "tls_cert": os.path.exists(os.path.join(certs_dir, "cert.pem")),
        "tls_key": os.path.exists(os.path.join(certs_dir, "key.pem")),
    }
    return render_template("mqtt_config.html", config=config, certs_status=certs_status, is_dirty=is_dirty)


@mqtt_bp.route("/api/mqtt/config", methods=["GET"])
def get_mqtt_config():
    return jsonify(config_store.get_section("mqtt"))


@mqtt_bp.route("/api/mqtt/config", methods=["POST"])
def save_mqtt_config():
    data = request.get_json()
    config_store.update_section("mqtt", data)
    return jsonify({"ok": True})


@mqtt_bp.route("/api/mqtt/upload-certs", methods=["POST"])
def upload_certs():
    certs_dir = os.path.join(current_app.config["DATA_DIR"], "certs", "mqtt")
    uploaded = []

    for field, filename in [("tls_ca", "ca.pem"), ("tls_cert", "cert.pem"), ("tls_key", "key.pem")]:
        if field in request.files:
            f = request.files[field]
            if f.filename:
                f.save(os.path.join(certs_dir, filename))
                uploaded.append(field)

    if uploaded:
        # Update config with container-side cert paths
        config_store.update_section("mqtt", {
            "tls_ca": "/etc/telegraf/certs/mqtt/ca.pem",
            "tls_cert": "/etc/telegraf/certs/mqtt/cert.pem",
            "tls_key": "/etc/telegraf/certs/mqtt/key.pem",
        })

    return jsonify({"ok": True, "uploaded": uploaded})


@mqtt_bp.route("/api/mqtt/test-connection", methods=["POST"])
def test_mqtt_connection():
    from app.services.mqtt_client import test_connection
    config = config_store.get_section("mqtt")
    data = request.get_json() or {}
    merged = {**config, **data}
    certs_dir = os.path.join(current_app.config["DATA_DIR"], "certs", "mqtt")
    result = test_connection(merged, certs_dir)
    return jsonify(result)
