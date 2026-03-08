"""Unit tests for mqtt_client helpers.

_parse_endpoint is called before TLS setup — a wrong result means Telegraf
either connects without encryption or uses the wrong port silently.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.mqtt_client import _parse_endpoint


class TestParseEndpoint:
    # --- Plain MQTT ---

    def test_mqtt_with_explicit_port(self):
        host, port, use_tls = _parse_endpoint("mqtt://broker:1883")
        assert host == "broker"
        assert port == 1883
        assert use_tls is False

    def test_mqtt_default_port(self):
        """No port specified → defaults to 1883."""
        host, port, use_tls = _parse_endpoint("mqtt://broker")
        assert host == "broker"
        assert port == 1883
        assert use_tls is False

    def test_mqtt_custom_port(self):
        host, port, use_tls = _parse_endpoint("mqtt://broker:5000")
        assert port == 5000
        assert use_tls is False

    # --- TLS (mqtts://) ---

    def test_mqtts_with_explicit_port(self):
        host, port, use_tls = _parse_endpoint("mqtts://broker:8883")
        assert host == "broker"
        assert port == 8883
        assert use_tls is True

    def test_mqtts_default_port(self):
        """No port → defaults to 8883 for mqtts."""
        host, port, use_tls = _parse_endpoint("mqtts://broker")
        assert host == "broker"
        assert port == 8883
        assert use_tls is True

    def test_mqtts_custom_port(self):
        host, port, use_tls = _parse_endpoint("mqtts://broker:5001")
        assert port == 5001
        assert use_tls is True

    # --- TLS flag is mutually exclusive with scheme ---

    def test_mqtt_scheme_never_sets_tls(self):
        _, _, use_tls = _parse_endpoint("mqtt://broker:8883")
        assert use_tls is False

    def test_mqtts_scheme_always_sets_tls(self):
        _, _, use_tls = _parse_endpoint("mqtts://broker:1883")
        assert use_tls is True

    # --- Host extraction ---

    def test_ip_address_host(self):
        host, port, _ = _parse_endpoint("mqtt://192.168.1.100:1883")
        assert host == "192.168.1.100"
        assert port == 1883

    def test_fqdn_host(self):
        host, port, use_tls = _parse_endpoint(
            "mqtts://abc.iot.eu-west-1.amazonaws.com:8883"
        )
        assert host == "abc.iot.eu-west-1.amazonaws.com"
        assert port == 8883
        assert use_tls is True

    def test_localhost(self):
        host, port, _ = _parse_endpoint("mqtt://localhost:1883")
        assert host == "localhost"

    # --- Demo / Mosquitto broker (common dev setup) ---

    def test_mosquitto_demo(self):
        host, port, use_tls = _parse_endpoint("mqtt://mosquitto:1883")
        assert host == "mosquitto"
        assert port == 1883
        assert use_tls is False
