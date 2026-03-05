"""Tests for system_monitor.get_telegraf_metrics().

The NDJSON parser powers the Pipeline Health section of the dashboard.
Bugs produce wrong metric values or None-related errors in the frontend.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.system_monitor import get_telegraf_metrics

# ---------------------------------------------------------------------------
# NDJSON fixture helpers
# ---------------------------------------------------------------------------

_TS = 1700000010  # arbitrary fixed timestamp


def _gather(input_name, metrics_gathered=5, gather_time_ns=12_500_000, errors=0, ts=_TS):
    return json.dumps({
        "name": "internal_gather",
        "tags": {"input": input_name},
        "fields": {
            "metrics_gathered": metrics_gathered,
            "gather_time_ns": gather_time_ns,
            "errors": errors,
        },
        "timestamp": ts,
    })


def _write_mqtt(metrics_written=8, metrics_dropped=2, buffer_size=4,
                buffer_limit=10000, errors=0, ts=_TS):
    return json.dumps({
        "name": "internal_write",
        "tags": {"output": "mqtt"},
        "fields": {
            "metrics_written": metrics_written,
            "metrics_dropped": metrics_dropped,
            "buffer_size": buffer_size,
            "buffer_limit": buffer_limit,
            "errors": errors,
        },
        "timestamp": ts,
    })


def _opcua_status(read_success=25, read_error=2, ts=_TS):
    return json.dumps({
        "name": "internal_opcua",
        "tags": {},
        "fields": {"read_success": read_success, "read_error": read_error},
        "timestamp": ts,
    })


def _write_metrics(app_ctx, *lines):
    (app_ctx / "metrics.json").write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetTelegrafMetricsNoFile:

    def test_returns_defaults_when_file_missing(self, app_ctx):
        result = get_telegraf_metrics()
        assert result["opcua_gathered"] == 0
        assert result["modbus_gathered"] == 0
        assert result["mqtt_written"] == 0
        assert result["last_updated"] is None

    def test_returns_defaults_when_file_empty(self, app_ctx):
        (app_ctx / "metrics.json").write_text("")
        result = get_telegraf_metrics()
        assert result["opcua_gathered"] == 0


class TestGetTelegrafMetricsFull:

    def test_all_fields_parsed(self, app_ctx):
        _write_metrics(
            app_ctx,
            _gather("opcua", metrics_gathered=5, gather_time_ns=12_500_000, errors=0),
            _gather("modbus", metrics_gathered=3, gather_time_ns=8_000_000, errors=1),
            _write_mqtt(metrics_written=8, metrics_dropped=2, buffer_size=4, buffer_limit=10000, errors=0),
            _opcua_status(read_success=25, read_error=2),
        )
        d = get_telegraf_metrics()

        assert d["opcua_gathered"] == 5
        assert d["opcua_scan_time_ms"] == round(12_500_000 / 1_000_000, 2)
        assert d["opcua_errors"] == 0

        assert d["modbus_gathered"] == 3
        assert d["modbus_scan_time_ms"] == round(8_000_000 / 1_000_000, 2)
        assert d["modbus_errors"] == 1

        assert d["mqtt_written"] == 8
        assert d["mqtt_dropped"] == 2
        assert d["mqtt_buffer_size"] == 4
        assert d["mqtt_buffer_limit"] == 10000
        assert d["mqtt_errors"] == 0

        assert d["opcua_read_success"] == 25
        assert d["opcua_read_error"] == 2

    def test_last_updated_set_from_opcua_gather(self, app_ctx):
        _write_metrics(app_ctx, _gather("opcua", ts=_TS))
        d = get_telegraf_metrics()
        assert d["last_updated"] == _TS

    def test_last_updated_falls_back_to_modbus(self, app_ctx):
        """When only Modbus data is present, last_updated comes from it."""
        _write_metrics(app_ctx, _gather("modbus", ts=_TS))
        d = get_telegraf_metrics()
        assert d["last_updated"] == _TS


class TestGetTelegrafMetricsLatestWins:
    """Parser iterates lines in reverse — the most recent entry must win."""

    def test_most_recent_opcua_gather_wins(self, app_ctx):
        old = _gather("opcua", metrics_gathered=1, ts=_TS - 60)
        new = _gather("opcua", metrics_gathered=99, ts=_TS)
        _write_metrics(app_ctx, old, new)  # new is last → first in reversed()
        d = get_telegraf_metrics()
        assert d["opcua_gathered"] == 99

    def test_most_recent_mqtt_write_wins(self, app_ctx):
        old = _write_mqtt(metrics_written=10, ts=_TS - 60)
        new = _write_mqtt(metrics_written=200, ts=_TS)
        _write_metrics(app_ctx, old, new)
        d = get_telegraf_metrics()
        assert d["mqtt_written"] == 200


class TestGetTelegrafMetricsPartial:

    def test_only_opcua_modbus_fields_default(self, app_ctx):
        _write_metrics(
            app_ctx,
            _gather("opcua", metrics_gathered=7),
            _write_mqtt(metrics_written=5),
        )
        d = get_telegraf_metrics()
        assert d["opcua_gathered"] == 7
        assert d["mqtt_written"] == 5
        assert d["modbus_gathered"] == 0   # not present → default
        assert d["modbus_errors"] == 0

    def test_only_modbus_opcua_fields_default(self, app_ctx):
        _write_metrics(app_ctx, _gather("modbus", metrics_gathered=4))
        d = get_telegraf_metrics()
        assert d["modbus_gathered"] == 4
        assert d["opcua_gathered"] == 0

    def test_missing_opcua_status_stays_zero(self, app_ctx):
        _write_metrics(app_ctx, _gather("opcua"))
        d = get_telegraf_metrics()
        assert d["opcua_read_success"] == 0
        assert d["opcua_read_error"] == 0


class TestGetTelegrafMetricsMalformed:

    def test_malformed_lines_skipped(self, app_ctx):
        _write_metrics(
            app_ctx,
            "not json at all",
            _gather("opcua", metrics_gathered=5),
            "{broken",
            _write_mqtt(metrics_written=3),
        )
        d = get_telegraf_metrics()
        assert d["opcua_gathered"] == 5
        assert d["mqtt_written"] == 3

    def test_wrong_tag_values_not_matched(self, app_ctx):
        """internal_gather with input=unknown should not fill opcua or modbus fields."""
        line = json.dumps({
            "name": "internal_gather",
            "tags": {"input": "unknown_plugin"},
            "fields": {"metrics_gathered": 999, "gather_time_ns": 0, "errors": 0},
            "timestamp": _TS,
        })
        _write_metrics(app_ctx, line)
        d = get_telegraf_metrics()
        assert d["opcua_gathered"] == 0
        assert d["modbus_gathered"] == 0

    def test_missing_fields_key_handled(self, app_ctx):
        line = json.dumps({
            "name": "internal_gather",
            "tags": {"input": "opcua"},
            # no "fields" key
            "timestamp": _TS,
        })
        _write_metrics(app_ctx, line)
        # Should not raise; fields default to 0
        d = get_telegraf_metrics()
        assert d["opcua_gathered"] == 0

    def test_entirely_bad_file_returns_defaults(self, app_ctx):
        (app_ctx / "metrics.json").write_text("garbage\nmore garbage\n!!!")
        d = get_telegraf_metrics()
        assert d["opcua_gathered"] == 0
        assert d["mqtt_written"] == 0
