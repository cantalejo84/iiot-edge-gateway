"""Tests for telegraf.conf.j2 rendering.

Uses tomllib (stdlib Python 3.11+) to validate generated TOML.
Renders the template directly via Jinja2 — no Flask app context required.
"""
import sys
import tomllib
from pathlib import Path

import pytest

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.telegraf_config import render_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_OPCUA = {
    "enabled": True,
    "endpoint": "opc.tcp://localhost:4840",
    "auth_method": "Anonymous",
    "username": "",
    "password": "",
    "security_policy": "None",
    "security_mode": "None",
    "connect_timeout": "10s",
    "request_timeout": "5s",
    "certificate": "",
    "private_key": "",
}

_BASE_NODE = {
    "name": "Temperature",
    "namespace": "2",
    "identifier_type": "i",
    "identifier": "1001",
}

_BASE_MQTT = {
    "endpoint": "mqtt://broker:1883",
    "topic_pattern": "iiot/{{ .Hostname }}/{{ .PluginName }}",
    "qos": 1,
    "data_format": "json",
    "tls_ca": "",
    "tls_cert": "",
    "tls_key": "",
    "username": "",
    "password": "",
}

_BASE_MODBUS = {
    "enabled": False,
    "controller": "modbus-server:502",
    "slave_id": 1,
    "timeout": "5s",
    "poll_interval": "10s",
    "registers": [],
}

_BASE_ACQ = {
    "mode": "polling",
    "scan_rate": "30s",
    "sampling_interval": "1s",
    "queue_size": 10,
    "trigger": "StatusValue",
    "deadband_type": "None",
    "deadband_value": 0.0,
}

_BASE_PUB = {"mode": "individual", "group_interval": "30s"}


def _cfg(**overrides):
    """Build a minimal valid config dict, with optional overrides."""
    return {
        "opcua": _BASE_OPCUA.copy(),
        "nodes": [_BASE_NODE.copy()],
        "mqtt": _BASE_MQTT.copy(),
        "modbus": _BASE_MODBUS.copy(),
        "acquisition": _BASE_ACQ.copy(),
        "publishing": _BASE_PUB.copy(),
        **overrides,
    }


def _render_and_parse(config):
    """Render the template and parse the result as TOML. Returns (toml_str, toml_dict)."""
    rendered = render_config(config)
    try:
        parsed = tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as exc:
        pytest.fail(f"Generated config is not valid TOML:\n{exc}\n\n--- config ---\n{rendered}")
    return rendered, parsed


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOpcuaPolling:
    def test_valid_toml(self):
        _, _ = _render_and_parse(_cfg())

    def test_opcua_section_present(self):
        rendered, parsed = _render_and_parse(_cfg())
        assert "inputs" in parsed
        assert "opcua" in parsed["inputs"]

    def test_polling_has_interval(self):
        rendered, _ = _render_and_parse(_cfg())
        # plugin-level interval appears right after [[inputs.opcua]]
        assert 'interval = "30s"' in rendered

    def test_node_name_present(self):
        rendered, _ = _render_and_parse(_cfg())
        assert "Temperature" in rendered


class TestOpcuaSubscription:
    def _sub_cfg(self):
        acq = {**_BASE_ACQ, "mode": "subscription", "sampling_interval": "500ms"}
        return _cfg(acquisition=acq)

    def test_valid_toml(self):
        _render_and_parse(self._sub_cfg())

    def test_no_plugin_level_interval(self):
        rendered, _ = _render_and_parse(self._sub_cfg())
        # The plugin-level interval line must NOT appear before the endpoint line
        lines = rendered.splitlines()
        opcua_idx = next(i for i, l in enumerate(lines) if "[[inputs.opcua]]" in l)
        endpoint_idx = next(i for i, l in enumerate(lines) if "endpoint" in l and i > opcua_idx)
        plugin_block = "\n".join(lines[opcua_idx:endpoint_idx])
        assert 'interval = ' not in plugin_block

    def test_monitoring_params_present(self):
        rendered, _ = _render_and_parse(self._sub_cfg())
        assert "monitoring_params" in rendered

    def test_deadband_inside_data_change_filter(self):
        acq = {**_BASE_ACQ, "mode": "subscription", "deadband_type": "Absolute", "deadband_value": 0.5}
        rendered, _ = _render_and_parse(_cfg(acquisition=acq))
        assert "data_change_filter" in rendered
        assert "deadband_type" in rendered
        # deadband must NOT appear at monitoring_params level (outside data_change_filter)
        lines = rendered.splitlines()
        mp_idx = next((i for i, l in enumerate(lines) if "monitoring_params]" in l and "data_change" not in l), None)
        dcf_idx = next((i for i, l in enumerate(lines) if "data_change_filter" in l), None)
        assert mp_idx is not None and dcf_idx is not None
        # deadband_type line must be after data_change_filter header
        db_idx = next(i for i, l in enumerate(lines) if "deadband_type" in l)
        assert db_idx > dcf_idx


class TestModbusOnly:
    def _modbus_cfg(self):
        modbus = {
            **_BASE_MODBUS,
            "enabled": True,
            "controller": "modbus-server:502",
            "registers": [
                {
                    "name": "temperature",
                    "register_type": "holding",
                    "address": 0,
                    "data_type": "FLOAT32",
                    "byte_order": "ABCD",
                },
            ],
        }
        opcua = {**_BASE_OPCUA, "enabled": False}
        return _cfg(opcua=opcua, nodes=[], modbus=modbus)

    def test_valid_toml(self):
        _render_and_parse(self._modbus_cfg())

    def test_modbus_section_present(self):
        rendered, parsed = _render_and_parse(self._modbus_cfg())
        assert "modbus" in parsed["inputs"]

    def test_tcp_prefix_added(self):
        rendered, _ = _render_and_parse(self._modbus_cfg())
        assert 'controller = "tcp://modbus-server:502"' in rendered

    def test_scale_present(self):
        rendered, _ = _render_and_parse(self._modbus_cfg())
        assert "scale = 1.0" in rendered

    def test_float32_normalized(self):
        rendered, _ = _render_and_parse(self._modbus_cfg())
        assert "FLOAT32-IEEE" in rendered
        assert '"FLOAT32"' not in rendered

    def test_no_opcua_section(self):
        rendered, parsed = _render_and_parse(self._modbus_cfg())
        assert "opcua" not in parsed.get("inputs", {})


class TestDualInput:
    def _dual_cfg(self):
        modbus = {
            **_BASE_MODBUS,
            "enabled": True,
            "controller": "tcp://modbus-server:502",
            "registers": [
                {
                    "name": "pressure",
                    "register_type": "holding",
                    "address": 2,
                    "data_type": "FLOAT32-IEEE",
                    "byte_order": "ABCD",
                },
            ],
        }
        return _cfg(modbus=modbus)

    def test_valid_toml(self):
        _render_and_parse(self._dual_cfg())

    def test_namepass_contains_both(self):
        rendered, _ = _render_and_parse(self._dual_cfg())
        assert '"opcua"' in rendered and '"modbus"' in rendered
        # They must appear on the same namepass line
        namepass_line = next(l for l in rendered.splitlines() if "namepass" in l and "opcua" in l)
        assert "modbus" in namepass_line


class TestGroupedMode:
    def _grouped_cfg(self):
        pub = {"mode": "grouped", "group_interval": "30s"}
        return _cfg(publishing=pub)

    def test_valid_toml(self):
        _render_and_parse(self._grouped_cfg())

    def test_aggregators_merge_present(self):
        rendered, parsed = _render_and_parse(self._grouped_cfg())
        assert "aggregators" in parsed
        assert "merge" in parsed["aggregators"]

    def test_drop_original_true(self):
        _, parsed = _render_and_parse(self._grouped_cfg())
        # [[aggregators.merge]] is an array-of-tables in TOML → list
        merge = parsed["aggregators"]["merge"]
        merge_item = merge[0] if isinstance(merge, list) else merge
        assert merge_item["drop_original"] is True

    def test_no_processors_merge(self):
        rendered, parsed = _render_and_parse(self._grouped_cfg())
        assert "processors" not in parsed or "merge" not in parsed.get("processors", {})

    def test_tagexclude_id(self):
        rendered, parsed = _render_and_parse(self._grouped_cfg())
        # [[inputs.opcua]] is an array-of-tables → list
        opcua = parsed["inputs"]["opcua"]
        opcua_cfg = opcua[0] if isinstance(opcua, list) else opcua
        assert opcua_cfg.get("tagexclude") == ["id"]


class TestOpcuaDisabled:
    def test_valid_toml(self):
        cfg = _cfg(opcua={**_BASE_OPCUA, "enabled": False}, nodes=[])
        _render_and_parse(cfg)

    def test_no_opcua_section(self):
        cfg = _cfg(opcua={**_BASE_OPCUA, "enabled": False}, nodes=[])
        _, parsed = _render_and_parse(cfg)
        assert "opcua" not in parsed.get("inputs", {})

    def test_no_aggregators_merge(self):
        cfg = _cfg(
            opcua={**_BASE_OPCUA, "enabled": False},
            nodes=[],
            publishing={"mode": "grouped", "group_interval": "30s"},
        )
        _, parsed = _render_and_parse(cfg)
        assert "aggregators" not in parsed or "merge" not in parsed.get("aggregators", {})


class TestTomlInjection:
    """Malicious input in node names must not break TOML parse."""

    def test_double_quote_in_name(self):
        node = {**_BASE_NODE, "name": 'Temp"Sensor'}
        cfg = _cfg(nodes=[node])
        rendered, _ = _render_and_parse(cfg)
        # The injected quote must be escaped
        assert '\\"' in rendered

    def test_newline_in_name(self):
        node = {**_BASE_NODE, "name": "Temp\nSensor"}
        cfg = _cfg(nodes=[node])
        _render_and_parse(cfg)

    def test_toml_injection_attempt(self):
        # Classic TOML injection: attempt to close the string and inject a new table
        node = {**_BASE_NODE, "name": 'x"] \n[[inputs.evil]]'}
        cfg = _cfg(nodes=[node])
        _, parsed = _render_and_parse(cfg)
        # The injected table must NOT appear as a parsed TOML section
        assert "evil" not in parsed.get("inputs", {})
