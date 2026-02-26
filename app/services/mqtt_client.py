import os
import re
import ssl
import threading
import time
from collections import deque
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


def _parse_endpoint(endpoint):
    use_tls = endpoint.startswith("mqtts://")
    clean = endpoint.replace("mqtts://", "").replace("mqtt://", "")
    parts = clean.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else (8883 if use_tls else 1883)
    return host, port, use_tls


def _configure_tls(client, certs_dir):
    ca_path = os.path.join(certs_dir, "ca.pem")
    cert_path = os.path.join(certs_dir, "cert.pem")
    key_path = os.path.join(certs_dir, "key.pem")

    if os.path.exists(ca_path) and os.path.exists(cert_path) and os.path.exists(key_path):
        client.tls_set(
            ca_certs=ca_path,
            certfile=cert_path,
            keyfile=key_path,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )
    elif os.path.exists(ca_path):
        client.tls_set(ca_certs=ca_path, tls_version=ssl.PROTOCOL_TLSv1_2)
    else:
        client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
        client.tls_insecure_set(True)


def test_connection(config, certs_dir):
    endpoint = config.get("endpoint", "")
    if not endpoint:
        return {"ok": False, "error": "MQTT endpoint is required"}

    host, port, use_tls = _parse_endpoint(endpoint)

    result = {"ok": False, "error": "Connection timeout"}
    event = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        nonlocal result
        if reason_code == 0:
            result = {"ok": True, "message": f"Connected to {host}:{port}"}
        else:
            result = {"ok": False, "error": f"Connection refused: {reason_code}"}
        event.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="iiot-gateway-test")
    client.on_connect = on_connect

    if use_tls:
        _configure_tls(client, certs_dir)

    try:
        client.connect(host, port, keepalive=10)
        client.loop_start()
        event.wait(timeout=5)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        result = {"ok": False, "error": str(e)}

    return result


class MqttTailSubscriber:
    """Background MQTT subscriber that keeps the last N messages."""

    def __init__(self, maxlen=50):
        self._messages = deque(maxlen=maxlen)
        self._client = None
        self._thread_running = False
        self._lock = threading.Lock()
        self._endpoint = None
        self._subscribe_topic = None

    def start(self, config, certs_dir):
        endpoint = config.get("endpoint", "")
        if not endpoint:
            return {"ok": False, "error": "MQTT endpoint is required"}

        # If already running on same endpoint, keep going
        if self._thread_running and self._endpoint == endpoint:
            return {"ok": True, "message": "Already running"}

        # Stop existing connection if endpoint changed
        if self._thread_running:
            self.stop()

        host, port, use_tls = _parse_endpoint(endpoint)
        self._endpoint = endpoint

        # Convert Telegraf topic template to MQTT wildcard
        # e.g. "iiot/gateway/{{ .Hostname }}/{{ .PluginName }}" -> "iiot/gateway/+/+"
        topic_pattern = config.get("topic_pattern", "#")
        subscribe_topic = re.sub(r"\{\{[^}]+\}\}", "+", topic_pattern) if topic_pattern else "#"
        self._subscribe_topic = subscribe_topic

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="iiot-gateway-tail")

        def on_connect(c, userdata, flags, reason_code, properties=None):
            if reason_code == 0:
                c.subscribe(subscribe_topic, qos=0)

        def on_message(c, userdata, msg):
            payload = msg.payload.decode("utf-8", errors="replace")[:2048]
            with self._lock:
                self._messages.appendleft({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "topic": msg.topic,
                    "payload": payload,
                })

        client.on_connect = on_connect
        client.on_message = on_message

        if use_tls:
            _configure_tls(client, certs_dir)

        try:
            client.connect(host, port, keepalive=60)
            client.loop_start()
            self._client = client
            self._thread_running = True
            return {"ok": True, "message": f"Subscribed to {host}:{port}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stop(self):
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        self._thread_running = False
        self._endpoint = None
        self._subscribe_topic = None

    def is_running(self):
        return self._thread_running

    def get_subscribe_topic(self):
        return self._subscribe_topic

    def get_messages(self):
        with self._lock:
            return list(self._messages)

    def clear_messages(self):
        with self._lock:
            self._messages.clear()


# Module-level singleton
tail_subscriber = MqttTailSubscriber()
