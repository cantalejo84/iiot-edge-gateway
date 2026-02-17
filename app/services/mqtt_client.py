import os
import ssl
import threading
import paho.mqtt.client as mqtt


def test_connection(config, certs_dir):
    endpoint = config.get("endpoint", "")
    if not endpoint:
        return {"ok": False, "error": "MQTT endpoint is required"}

    # Parse endpoint: mqtts://host:port or mqtt://host:port
    use_tls = endpoint.startswith("mqtts://")
    clean = endpoint.replace("mqtts://", "").replace("mqtt://", "")
    parts = clean.split(":")
    host = parts[0]
    port = int(parts[1]) if len(parts) > 1 else (8883 if use_tls else 1883)

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

    try:
        client.connect(host, port, keepalive=10)
        client.loop_start()
        event.wait(timeout=5)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        result = {"ok": False, "error": str(e)}

    return result
