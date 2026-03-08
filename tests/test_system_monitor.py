"""Tests for system_monitor.get_telegraf_metrics().

The NDJSON parser powers the Pipeline Health section of the dashboard.
Bugs produce wrong metric values or None-related errors in the frontend.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.system_monitor import (
    _compute_unexpected_restart,
    get_telegraf_metrics,
    reset_crash_detection,
)

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


# ---------------------------------------------------------------------------
# _compute_unexpected_restart()
# ---------------------------------------------------------------------------


class TestComputeUnexpectedRestart:

    def test_same_timestamp_returns_none(self):
        ts = "2026-03-07T10:30:00.123456789Z"
        assert _compute_unexpected_restart(ts, ts) is None

    def test_different_time_returns_current(self):
        current = "2026-03-07T12:00:00.000000000Z"
        deploy  = "2026-03-07T10:30:00.123456789Z"
        assert _compute_unexpected_restart(current, deploy) == current

    def test_none_current_returns_none(self):
        assert _compute_unexpected_restart(None, "2026-03-07T10:30:00Z") is None

    def test_none_deploy_returns_none(self):
        # No baseline → cannot determine unexpected restart
        assert _compute_unexpected_restart("2026-03-07T10:30:00Z", None) is None

    def test_both_none_returns_none(self):
        assert _compute_unexpected_restart(None, None) is None

    def test_same_second_different_subseconds_treated_as_same(self):
        # Sub-second differences are ignored; same container start
        ts1 = "2026-03-07T10:30:00.100000000Z"
        ts2 = "2026-03-07T10:30:00.999999999Z"
        assert _compute_unexpected_restart(ts1, ts2) is None

    def test_one_second_apart_detected_as_restart(self):
        current = "2026-03-07T10:30:01.000000000Z"
        deploy  = "2026-03-07T10:30:00.999999999Z"
        assert _compute_unexpected_restart(current, deploy) == current


# ---------------------------------------------------------------------------
# Crash detection (_prev_gathered logic)
# ---------------------------------------------------------------------------


class TestCrashDetection:
    """Verify process_crash_detected flag in get_telegraf_metrics()."""

    def setup_method(self):
        # Isolate each test from module-level state
        reset_crash_detection()

    def test_no_previous_state_no_crash(self, app_ctx):
        """First call: no baseline, never a crash."""
        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=10))
        d = get_telegraf_metrics()
        assert d["process_crash_detected"] is False

    def test_counter_increasing_no_crash(self, app_ctx):
        """Two calls with increasing counter: normal operation."""
        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=10))
        get_telegraf_metrics()  # seed baseline

        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=20))
        d = get_telegraf_metrics()
        assert d["process_crash_detected"] is False

    def test_counter_reset_triggers_crash(self, app_ctx):
        """Counter drops from high value to near-zero: crash detected."""
        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=50))
        get_telegraf_metrics()  # seed baseline with prev=50

        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=2))
        d = get_telegraf_metrics()
        assert d["process_crash_detected"] is True

    def test_counter_reset_below_threshold_no_crash(self, app_ctx):
        """Previous value <= 5: too small to distinguish restart from noise."""
        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=5))
        get_telegraf_metrics()  # seed baseline with prev=5

        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=0))
        d = get_telegraf_metrics()
        assert d["process_crash_detected"] is False

    def test_reset_crash_detection_prevents_false_positive(self, app_ctx):
        """After reset_crash_detection(), next poll with low counter is not a crash."""
        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=50))
        get_telegraf_metrics()  # seed baseline

        reset_crash_detection()  # simulates intentional restart (deploy / manual start)

        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=1))
        d = get_telegraf_metrics()
        assert d["process_crash_detected"] is False

    def test_modbus_crash_detected(self, app_ctx):
        """Crash detected via modbus counter reset, not opcua."""
        _write_metrics(app_ctx, _gather("modbus", metrics_gathered=30))
        get_telegraf_metrics()  # seed baseline

        _write_metrics(app_ctx, _gather("modbus", metrics_gathered=1))
        d = get_telegraf_metrics()
        assert d["process_crash_detected"] is True

    def test_crash_flag_clears_on_next_poll(self, app_ctx):
        """After crash detected, subsequent normal poll reports no crash."""
        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=50))
        get_telegraf_metrics()

        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=1))
        get_telegraf_metrics()  # crash detected here — baseline now set to 1

        _write_metrics(app_ctx, _gather("opcua", metrics_gathered=2))
        d = get_telegraf_metrics()
        assert d["process_crash_detected"] is False
