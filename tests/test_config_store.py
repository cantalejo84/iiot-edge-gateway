"""Tests for config_store: dirty tracking, mark_applied, and resilience.

is_dirty() controls the "Unapplied changes" badge. mark_applied() is called
after every successful deploy. Bugs here produce confusing UX or data loss.
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.config import DEFAULT_CONFIG
from app.services import config_store


def _write_config(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def _make_config(**meta_overrides):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["_meta"].update(meta_overrides)
    return cfg


# ---------------------------------------------------------------------------
# is_dirty()
# ---------------------------------------------------------------------------


class TestIsDirty:
    def test_no_file_returns_false(self, app_ctx):
        assert config_store.is_dirty() is False

    def test_last_modified_none_returns_false(self, app_ctx):
        cfg = _make_config(last_modified=None, last_applied=None)
        _write_config(app_ctx / "config.json", cfg)
        assert config_store.is_dirty() is False

    def test_last_applied_none_with_modified_returns_true(self, app_ctx):
        cfg = _make_config(last_modified="2024-01-01T00:00:01Z", last_applied=None)
        _write_config(app_ctx / "config.json", cfg)
        assert config_store.is_dirty() is True

    def test_modified_after_applied_returns_true(self, app_ctx):
        cfg = _make_config(
            last_applied="2024-01-01T00:00:00Z",
            last_modified="2024-01-01T00:00:01Z",
        )
        _write_config(app_ctx / "config.json", cfg)
        assert config_store.is_dirty() is True

    def test_modified_equals_applied_returns_false(self, app_ctx):
        ts = "2024-01-01T12:00:00Z"
        cfg = _make_config(last_applied=ts, last_modified=ts)
        _write_config(app_ctx / "config.json", cfg)
        assert config_store.is_dirty() is False

    def test_modified_before_applied_returns_false(self, app_ctx):
        cfg = _make_config(
            last_applied="2024-01-01T00:00:02Z",
            last_modified="2024-01-01T00:00:01Z",
        )
        _write_config(app_ctx / "config.json", cfg)
        assert config_store.is_dirty() is False


# ---------------------------------------------------------------------------
# mark_applied()
# ---------------------------------------------------------------------------


class TestMarkApplied:
    def test_mark_applied_clears_dirty(self, app_ctx):
        cfg = _make_config(last_modified="2024-01-01T00:00:01Z", last_applied=None)
        _write_config(app_ctx / "config.json", cfg)
        assert config_store.is_dirty() is True

        config_store.mark_applied()

        assert config_store.is_dirty() is False

    def test_mark_applied_sets_equal_timestamps(self, app_ctx):
        cfg = _make_config(last_modified="2024-01-01T00:00:01Z", last_applied=None)
        _write_config(app_ctx / "config.json", cfg)

        config_store.mark_applied()

        meta = config_store.load()["_meta"]
        assert meta["last_applied"] == meta["last_modified"]

    def test_mark_applied_snapshots_mqtt_config(self, app_ctx):
        cfg = _make_config(last_modified="2024-01-01T00:00:01Z")
        cfg["mqtt"]["endpoint"] = "mqtts://broker.example.com:8883"
        cfg["mqtt"]["topic_pattern"] = "iiot/{{ .Hostname }}/{{ .PluginName }}"
        _write_config(app_ctx / "config.json", cfg)

        config_store.mark_applied()

        meta = config_store.load()["_meta"]
        assert "applied_mqtt" in meta
        assert meta["applied_mqtt"]["endpoint"] == "mqtts://broker.example.com:8883"
        assert (
            meta["applied_mqtt"]["topic_pattern"]
            == "iiot/{{ .Hostname }}/{{ .PluginName }}"
        )

    def test_mark_applied_does_not_rebump_last_modified(self, app_ctx):
        """Calling mark_applied must NOT change last_modified — that would re-trigger dirty."""
        cfg = _make_config(
            last_modified="2024-01-01T00:00:01Z",
            last_applied="2024-01-01T00:00:01Z",
        )
        _write_config(app_ctx / "config.json", cfg)

        config_store.mark_applied()

        # Still not dirty after a second mark_applied
        assert config_store.is_dirty() is False

    def test_mark_applied_idempotent(self, app_ctx):
        """Calling mark_applied twice doesn't make config dirty."""
        cfg = _make_config(last_modified="2024-01-01T00:00:01Z", last_applied=None)
        _write_config(app_ctx / "config.json", cfg)

        config_store.mark_applied()
        config_store.mark_applied()

        assert config_store.is_dirty() is False

    def test_no_file_does_not_crash(self, app_ctx):
        """mark_applied is a no-op when config.json doesn't exist yet."""
        config_store.mark_applied()  # should not raise


# ---------------------------------------------------------------------------
# load() resilience
# ---------------------------------------------------------------------------


class TestLoad:
    def test_no_file_returns_defaults(self, app_ctx):
        result = config_store.load()
        assert result["opcua"] == DEFAULT_CONFIG["opcua"]
        assert result["nodes"] == []
        assert result["mqtt"] == DEFAULT_CONFIG["mqtt"]

    def test_corrupted_json_returns_defaults(self, app_ctx):
        (app_ctx / "config.json").write_text("{ not valid json !!!")
        result = config_store.load()
        assert result["opcua"] == DEFAULT_CONFIG["opcua"]

    def test_partial_json_returns_defaults(self, app_ctx):
        # Truncated write — simulates a crash during save
        (app_ctx / "config.json").write_text('{"opcua": {"endpoint": "opc.tcp://host"')
        result = config_store.load()
        assert result["opcua"] == DEFAULT_CONFIG["opcua"]

    def test_valid_file_returns_content(self, app_ctx):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["opcua"]["endpoint"] = "opc.tcp://custom:4840"
        _write_config(app_ctx / "config.json", cfg)

        result = config_store.load()
        assert result["opcua"]["endpoint"] == "opc.tcp://custom:4840"


# ---------------------------------------------------------------------------
# save() + load() round-trip
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_roundtrip_preserves_data(self, app_ctx):
        cfg = config_store.load()
        cfg["opcua"]["endpoint"] = "opc.tcp://roundtrip:4840"
        config_store.save(cfg)

        loaded = config_store.load()
        assert loaded["opcua"]["endpoint"] == "opc.tcp://roundtrip:4840"

    def test_save_bumps_last_modified(self, app_ctx):
        cfg = _make_config(last_modified=None)
        _write_config(app_ctx / "config.json", cfg)

        cfg2 = config_store.load()
        config_store.save(cfg2)

        loaded = config_store.load()
        assert loaded["_meta"]["last_modified"] is not None

    def test_save_uses_atomic_write(self, app_ctx):
        """tmp file must not remain after a successful save."""
        cfg = config_store.load()
        config_store.save(cfg)
        assert not (app_ctx / "config.json.tmp").exists()


# ---------------------------------------------------------------------------
# record_telegraf_start()
# ---------------------------------------------------------------------------


class TestRecordRestart:
    def test_stores_started_at_and_reason(self, app_ctx):
        cfg = _make_config()
        _write_config(app_ctx / "config.json", cfg)

        config_store.record_restart("2026-03-07T10:30:00.123456789Z", "deploy")

        meta = config_store.load()["_meta"]
        assert meta["last_restart"]["started_at"] == "2026-03-07T10:30:00.123456789Z"
        assert meta["last_restart"]["reason"] == "deploy"

    def test_all_reasons_accepted(self, app_ctx):
        cfg = _make_config()
        _write_config(app_ctx / "config.json", cfg)

        for reason in ("deploy", "manual", "unplanned"):
            config_store.record_restart("2026-03-07T10:30:00Z", reason)
            assert config_store.load()["_meta"]["last_restart"]["reason"] == reason

    def test_overwrites_previous_value(self, app_ctx):
        cfg = _make_config()
        cfg["_meta"]["last_restart"] = {
            "started_at": "2026-01-01T00:00:00Z",
            "reason": "deploy",
        }
        _write_config(app_ctx / "config.json", cfg)

        config_store.record_restart("2026-03-07T10:30:00Z", "unplanned")

        last = config_store.load()["_meta"]["last_restart"]
        assert last["started_at"] == "2026-03-07T10:30:00Z"
        assert last["reason"] == "unplanned"

    def test_does_not_bump_last_modified(self, app_ctx):
        """Recording a restart must NOT make config dirty."""
        ts = "2024-01-01T12:00:00Z"
        cfg = _make_config(last_modified=ts, last_applied=ts)
        _write_config(app_ctx / "config.json", cfg)

        config_store.record_restart("2026-03-07T10:30:00Z", "manual")

        assert config_store.is_dirty() is False
        assert config_store.load()["_meta"]["last_modified"] == ts

    def test_does_not_affect_other_meta_fields(self, app_ctx):
        ts = "2024-01-01T12:00:00Z"
        cfg = _make_config(last_modified=ts, last_applied=ts)
        _write_config(app_ctx / "config.json", cfg)

        config_store.record_restart("2026-03-07T10:30:00Z", "deploy")

        meta = config_store.load()["_meta"]
        assert meta["last_applied"] == ts
        assert meta["last_modified"] == ts

    def test_no_file_does_not_crash(self, app_ctx):
        config_store.record_restart(
            "2026-03-07T10:30:00Z", "manual"
        )  # should not raise
