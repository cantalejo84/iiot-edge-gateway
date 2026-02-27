import json
import os
import re

from flask import Blueprint, current_app, jsonify, render_template, request

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
    return render_template(
        "mqtt_config.html", config=config, certs_status=certs_status, is_dirty=is_dirty
    )


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

    for field, filename in [
        ("tls_ca", "ca.pem"),
        ("tls_cert", "cert.pem"),
        ("tls_key", "key.pem"),
    ]:
        if field in request.files:
            f = request.files[field]
            if f.filename:
                f.save(os.path.join(certs_dir, filename))
                uploaded.append(field)

    if uploaded:
        # Update config with container-side cert paths
        config_store.update_section(
            "mqtt",
            {
                "tls_ca": "/etc/telegraf/certs/mqtt/ca.pem",
                "tls_cert": "/etc/telegraf/certs/mqtt/cert.pem",
                "tls_key": "/etc/telegraf/certs/mqtt/key.pem",
            },
        )

    return jsonify({"ok": True, "uploaded": uploaded})


@mqtt_bp.route("/api/mqtt/test-connection", methods=["POST"])
def test_mqtt_connection():
    from app.services import event_log
    from app.services.mqtt_client import test_connection

    config = config_store.get_section("mqtt")
    data = request.get_json() or {}
    merged = {**config, **data}
    endpoint = merged.get("endpoint", "")
    certs_dir = os.path.join(current_app.config["DATA_DIR"], "certs", "mqtt")
    result = test_connection(merged, certs_dir)
    if result.get("ok"):
        event_log.log("info", "mqtt", f"Connection OK → {endpoint}")
    else:
        event_log.log(
            "error",
            "mqtt",
            f"Connection failed → {endpoint}",
            detail=result.get("error"),
        )
    return jsonify(result)


@mqtt_bp.route("/api/mqtt/azure-iot-config", methods=["GET"])
def get_azure_iot_config():
    config = config_store.get_section("mqtt")
    endpoint = config.get("endpoint", "")

    hub_name = "your-iothub"
    match = re.search(r"([a-zA-Z0-9-]+)\.azure-devices\.net", endpoint)
    if match:
        hub_name = match.group(1)

    device_id = "{{ .Hostname }}"
    username = f"{hub_name}.azure-devices.net/{device_id}/?api-version=2021-04-12"
    topic = f"devices/{device_id}/messages/events/"

    return jsonify(
        {
            "ok": True,
            "hub_name": hub_name,
            "username": username,
            "topic": topic,
        }
    )


@mqtt_bp.route("/api/mqtt/clear", methods=["POST"])
def clear_mqtt_config():
    config_store.update_section(
        "mqtt",
        {
            "endpoint": "",
            "topic_pattern": "",
            "qos": 0,
            "data_format": "json",
            "tls_ca": "",
            "tls_cert": "",
            "tls_key": "",
            "username": "",
            "password": "",
        },
    )
    certs_dir = os.path.join(current_app.config["DATA_DIR"], "certs", "mqtt")
    for fname in ["ca.pem", "cert.pem", "key.pem"]:
        fpath = os.path.join(certs_dir, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
    return jsonify({"ok": True})


@mqtt_bp.route("/api/mqtt/delete-certs", methods=["POST"])
def delete_certs():
    certs_dir = os.path.join(current_app.config["DATA_DIR"], "certs", "mqtt")
    deleted = []
    for fname, field in [
        ("ca.pem", "tls_ca"),
        ("cert.pem", "tls_cert"),
        ("key.pem", "tls_key"),
    ]:
        fpath = os.path.join(certs_dir, fname)
        if os.path.exists(fpath):
            os.remove(fpath)
            deleted.append(field)
    config_store.update_section("mqtt", {"tls_ca": "", "tls_cert": "", "tls_key": ""})
    return jsonify({"ok": True, "deleted": deleted})


@mqtt_bp.route("/api/mqtt/aws-iot-policy", methods=["GET"])
def get_aws_iot_policy():
    config = config_store.get_section("mqtt")
    endpoint = config.get("endpoint", "")
    topic_pattern = config.get("topic_pattern", "")

    region = "us-east-1"
    match = re.search(r"\.iot\.([a-z0-9-]+)\.amazonaws\.com", endpoint)
    if match:
        region = match.group(1)

    topic_base = re.sub(r"\{\{[^}]+\}\}", "*", topic_pattern).strip("/")
    if not topic_base:
        topic_base = "iiot/gateway/*"

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "iot:Connect",
                "Resource": f"arn:aws:iot:{region}:*:client/*",
            },
            {
                "Effect": "Allow",
                "Action": ["iot:Publish", "iot:Receive"],
                "Resource": f"arn:aws:iot:{region}:*:topic/{topic_base}",
            },
            {
                "Effect": "Allow",
                "Action": "iot:Subscribe",
                "Resource": f"arn:aws:iot:{region}:*:topicfilter/{topic_base}",
            },
        ],
    }
    return jsonify(
        {"ok": True, "policy": json.dumps(policy, indent=2), "region": region}
    )


@mqtt_bp.route("/mqtt/messages")
def mqtt_messages_page():
    config = config_store.get_section("mqtt")
    is_dirty = config_store.is_dirty()
    return render_template("mqtt_messages.html", config=config, is_dirty=is_dirty)


@mqtt_bp.route("/api/mqtt/messages/clear", methods=["POST"])
def clear_messages():
    from app.services.mqtt_client import tail_subscriber

    tail_subscriber.clear_messages()
    return jsonify({"ok": True})


@mqtt_bp.route("/api/mqtt/tail/start", methods=["POST"])
def start_tail():
    from app.services.mqtt_client import tail_subscriber

    # Use the last-deployed MQTT config so the tail matches what Telegraf is actually using
    config = config_store.get_applied_section("mqtt")
    certs_dir = os.path.join(current_app.config["DATA_DIR"], "certs", "mqtt")
    result = tail_subscriber.start(config, certs_dir)
    return jsonify(result)


@mqtt_bp.route("/api/mqtt/tail/stop", methods=["POST"])
def stop_tail():
    from app.services.mqtt_client import tail_subscriber

    tail_subscriber.stop()
    return jsonify({"ok": True})


@mqtt_bp.route("/api/mqtt/tail", methods=["GET"])
def get_tail():
    from app.services.mqtt_client import tail_subscriber

    return jsonify(
        {
            "running": tail_subscriber.is_running(),
            "topic": tail_subscriber.get_subscribe_topic(),
            "messages": tail_subscriber.get_messages(),
        }
    )
