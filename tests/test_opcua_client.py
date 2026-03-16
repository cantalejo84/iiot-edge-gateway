"""Unit tests for opcua_client helpers.

Tests use mocks — no real OPC UA server required.
Covers: access_level bitmask handling, value_rank labels, min_sampling_interval
display, status_code extraction, and graceful None on attribute errors.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── Helpers that mirror JS rendering logic (tested in Python for parity) ─────


def decode_access_level(al):
    """Mirror the JS bitmask decode from opcua_browser.js."""
    if al is None:
        return []
    flags = []
    if al & 0x01:
        flags.append("Read")
    if al & 0x02:
        flags.append("Write")
    if al & 0x04:
        flags.append("History")
    return flags


def format_value_rank(vr):
    """Mirror the JS value_rank label logic."""
    if vr is None:
        return None
    mapping = {-1: "Scalar", 0: "Scalar or Array", 1: "Array[1D]"}
    return mapping.get(vr, f"Array[{vr}D]")


def format_min_sampling(msi):
    """Mirror the JS min_sampling_interval display logic."""
    if msi is None:
        return "—"
    if msi < 0:
        return "Continuous"
    if msi == 0:
        return "Fastest"
    if msi < 1000:
        return f"{msi}ms"
    return f"{msi / 1000}s"


# ─── Access Level decode ──────────────────────────────────────────────────────


class TestAccessLevelDecode:
    def test_read_only(self):
        assert decode_access_level(1) == ["Read"]

    def test_read_write(self):
        assert decode_access_level(3) == ["Read", "Write"]

    def test_read_write_history(self):
        assert decode_access_level(7) == ["Read", "Write", "History"]

    def test_write_only(self):
        assert decode_access_level(2) == ["Write"]

    def test_history_only(self):
        assert decode_access_level(4) == ["History"]

    def test_zero(self):
        assert decode_access_level(0) == []

    def test_none(self):
        assert decode_access_level(None) == []


# ─── Value Rank labels ────────────────────────────────────────────────────────


class TestValueRankLabel:
    def test_scalar(self):
        assert format_value_rank(-1) == "Scalar"

    def test_scalar_or_array(self):
        assert format_value_rank(0) == "Scalar or Array"

    def test_one_dimension(self):
        assert format_value_rank(1) == "Array[1D]"

    def test_two_dimensions(self):
        assert format_value_rank(2) == "Array[2D]"

    def test_none(self):
        assert format_value_rank(None) is None


# ─── Min Sampling Interval display ───────────────────────────────────────────


class TestMinSamplingInterval:
    def test_continuous(self):
        assert format_min_sampling(-1) == "Continuous"

    def test_fastest(self):
        assert format_min_sampling(0) == "Fastest"

    def test_milliseconds(self):
        assert format_min_sampling(100) == "100ms"

    def test_boundary_999ms(self):
        assert format_min_sampling(999) == "999ms"

    def test_one_second(self):
        assert format_min_sampling(1000) == "1.0s"

    def test_two_seconds(self):
        assert format_min_sampling(2000) == "2.0s"

    def test_none(self):
        assert format_min_sampling(None) == "—"


# ─── opcua_client async functions (mocked) ────────────────────────────────────


def _make_data_value(value=42.0, status_name="Good", src_ts=None, srv_ts=None):
    """Build a mock asyncua DataValue."""
    dv = MagicMock()
    dv.Value.Value = value
    dv.StatusCode.name = status_name
    dv.SourceTimestamp = src_ts
    dv.ServerTimestamp = srv_ts
    return dv


def _make_attr_result(value):
    """Wrap a value in a mock get_attribute() result (DataValue-like)."""
    result = MagicMock()
    result.Value.Value = value
    return result


class TestReadNodeDetails:
    """Tests for read_node_details() extended attributes."""

    def _make_node(
        self,
        access_level=1,
        description="Test desc",
        value_rank=-1,
        min_sampling=100.0,
        historizing=False,
    ):
        node = AsyncMock()
        node.nodeid.to_string.return_value = "ns=2;s=Temperature"
        node.nodeid.NamespaceIndex = 2
        node.nodeid.NodeIdType = MagicMock()
        # read_browse_name
        bn = MagicMock()
        bn.Name = "Temperature"
        node.read_browse_name = AsyncMock(return_value=bn)
        # read_node_class — asyncua ua.NodeClass.Variable
        from asyncua import ua

        node.read_node_class = AsyncMock(return_value=ua.NodeClass.Variable)
        # read_value
        node.read_value = AsyncMock(return_value=23.5)
        # read_data_type
        dt_node_id = MagicMock()
        node.read_data_type = AsyncMock(return_value=dt_node_id)

        # get_attribute — called per AttributeId
        def get_attr_side_effect(attr_id):
            from asyncua import ua

            mapping = {
                ua.AttributeIds.AccessLevel: _make_attr_result(access_level),
                ua.AttributeIds.Description: _make_attr_result(
                    MagicMock(Text=description) if description else None
                ),
                ua.AttributeIds.ValueRank: _make_attr_result(value_rank),
                ua.AttributeIds.MinimumSamplingInterval: _make_attr_result(
                    min_sampling
                ),
                ua.AttributeIds.Historizing: _make_attr_result(historizing),
                ua.AttributeIds.Value: _make_data_value(23.5),
            }
            future = asyncio.Future()
            future.set_result(mapping.get(attr_id, _make_attr_result(None)))
            return future

        node.get_attribute = get_attr_side_effect
        # get_children — no EU properties
        node.get_children = AsyncMock(return_value=[])
        return node

    def _run(self, coro):
        return asyncio.run(coro)

    def test_access_level_read_only(self):
        """access_level=1 should be returned as int 1."""
        node = self._make_node(access_level=1)

        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get_node.return_value = node
            # data type browse
            dt_name = MagicMock()
            dt_name.Name = "Float"
            mock_client.get_node.return_value.read_browse_name = AsyncMock(
                return_value=dt_name
            )
            dt_node = AsyncMock()
            dt_bn = MagicMock()
            dt_bn.Name = "Float"
            dt_node.read_browse_name = AsyncMock(return_value=dt_bn)

            async def fake_get_node(nid):
                return dt_node

            mock_client.get_node = MagicMock(side_effect=lambda nid: node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_node_details

            result = self._run(
                read_node_details(
                    {"endpoint": "opc.tcp://test:4840"}, "ns=2;s=Temperature"
                )
            )

        assert result["access_level"] == 1

    def test_access_level_none_on_exception(self):
        """If get_attribute raises, access_level should be None."""
        from asyncua import ua

        node = self._make_node()

        original_side = node.get_attribute

        def raise_on_access_level(attr_id):
            if attr_id == ua.AttributeIds.AccessLevel:
                raise Exception("BadAttributeIdInvalid")
            return original_side(attr_id)

        node.get_attribute = raise_on_access_level

        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get_node = MagicMock(return_value=node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_node_details

            result = self._run(
                read_node_details(
                    {"endpoint": "opc.tcp://test:4840"}, "ns=2;s=Temperature"
                )
            )

        assert result["access_level"] is None

    def test_description_none_when_empty(self):
        """description=None when server returns no text."""
        node = self._make_node(description=None)

        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get_node = MagicMock(return_value=node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_node_details

            result = self._run(
                read_node_details(
                    {"endpoint": "opc.tcp://test:4840"}, "ns=2;s=Temperature"
                )
            )

        assert result["description"] is None

    def test_historizing_false(self):
        node = self._make_node(historizing=False)

        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get_node = MagicMock(return_value=node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_node_details

            result = self._run(
                read_node_details(
                    {"endpoint": "opc.tcp://test:4840"}, "ns=2;s=Temperature"
                )
            )

        assert result["historizing"] is False

    def test_engineering_units_none_when_no_property(self):
        """No EU property children → engineering_units is None."""
        node = self._make_node()
        node.get_children = AsyncMock(return_value=[])

        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get_node = MagicMock(return_value=node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_node_details

            result = self._run(
                read_node_details(
                    {"endpoint": "opc.tcp://test:4840"}, "ns=2;s=Temperature"
                )
            )

        assert result["engineering_units"] is None


class TestReadNamespaceArray:
    def test_returns_indexed_list(self):
        ns_uris = ["http://opcfoundation.org/UA/", "urn:vendor:server"]

        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            ns_node = AsyncMock()
            ns_node.read_value = AsyncMock(return_value=ns_uris)
            mock_client.get_node = MagicMock(return_value=ns_node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_namespace_array

            result = asyncio.run(
                read_namespace_array({"endpoint": "opc.tcp://test:4840"})
            )

        assert result == [
            {"index": 0, "uri": "http://opcfoundation.org/UA/"},
            {"index": 1, "uri": "urn:vendor:server"},
        ]


class TestReadNodeValue:
    def test_returns_value_and_status(self):
        from datetime import datetime, timezone

        src_ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        srv_ts = datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc)

        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            node = AsyncMock()
            dv = _make_data_value(42.5, "Good", src_ts, srv_ts)
            node.get_attribute = AsyncMock(return_value=dv)
            mock_client.get_node = MagicMock(return_value=node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_node_value

            result = asyncio.run(
                read_node_value(
                    {"endpoint": "opc.tcp://test:4840"}, "ns=2;s=Temperature"
                )
            )

        assert result["value"] == "42.5"
        assert result["status_code"] == "Good"
        assert "2024-01-15" in result["source_timestamp"]
        assert "2024-01-15" in result["server_timestamp"]

    def test_none_timestamps_when_not_set(self):
        with patch("app.services.opcua_client._build_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            node = AsyncMock()
            dv = _make_data_value(0, "Good", None, None)
            node.get_attribute = AsyncMock(return_value=dv)
            mock_client.get_node = MagicMock(return_value=node)
            mock_build.return_value = mock_client

            from app.services.opcua_client import read_node_value

            result = asyncio.run(
                read_node_value(
                    {"endpoint": "opc.tcp://test:4840"}, "ns=2;s=Temperature"
                )
            )

        assert result["source_timestamp"] is None
        assert result["server_timestamp"] is None
