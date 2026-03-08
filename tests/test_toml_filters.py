"""Unit tests for _toml_dq and _toml_sq filter functions.

These are the security boundary between user-controlled input and the
generated telegraf.conf. Bugs here can produce invalid TOML or allow
injection of arbitrary config keys.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.services.telegraf_config import _toml_dq, _toml_sq


class TestTomlDq:
    """Tests for _toml_dq — escaping for TOML double-quoted strings."""

    # --- Basic cases ---

    def test_none_returns_empty(self):
        assert _toml_dq(None) == ""

    def test_empty_string(self):
        assert _toml_dq("") == ""

    def test_plain_string_unchanged(self):
        assert _toml_dq("hello") == "hello"

    # --- Quote escaping ---

    def test_double_quote_escaped(self):
        assert _toml_dq('"') == '\\"'

    def test_double_quote_in_middle(self):
        assert _toml_dq('say "hello"') == 'say \\"hello\\"'

    # --- Backslash escaping ---

    def test_backslash_doubled(self):
        assert _toml_dq("\\") == "\\\\"

    def test_windows_path(self):
        assert _toml_dq("C:\\Users\\data") == "C:\\\\Users\\\\data"

    def test_backslash_then_quote(self):
        # Input: a\"b  →  a\\"b (backslash doubled first, then quote escaped)
        result = _toml_dq('a\\"b')
        assert result == 'a\\\\\\"b'

    # --- Control character stripping ---

    def test_newline_stripped(self):
        assert _toml_dq("line\nbreak") == "linebreak"

    def test_carriage_return_stripped(self):
        assert _toml_dq("line\rbreak") == "linebreak"

    def test_tab_stripped(self):
        assert _toml_dq("col\there") == "colhere"

    def test_crlf_stripped(self):
        assert _toml_dq("line\r\nend") == "lineend"

    def test_only_newlines_returns_empty(self):
        assert _toml_dq("\n\r\t") == ""

    # --- Injection attempts ---

    def test_injection_close_quote_and_key(self):
        # Attacker tries to break out: `" \n[evil]` → backslash + quote escaped, newline stripped
        result = _toml_dq('"\n[evil]')
        assert "\n" not in result
        assert result == '\\"[evil]'

    def test_injection_double_close(self):
        result = _toml_dq('normal" extra="injected')
        assert result == 'normal\\" extra=\\"injected'

    # --- Unicode and non-ASCII ---

    def test_unicode_passthrough(self):
        assert _toml_dq("café") == "café"

    def test_unicode_special_chars(self):
        assert _toml_dq("温度") == "温度"

    def test_emoji_passthrough(self):
        assert _toml_dq("temp🌡️") == "temp🌡️"

    # --- Result is safe inside a TOML double-quoted string ---

    def test_result_produces_valid_toml(self):
        import tomllib

        for value in ["hello", '"quoted"', "back\\slash", "line\nbreak", 'a"b\\c']:
            escaped = _toml_dq(value)
            toml_str = f'key = "{escaped}"\n'
            parsed = tomllib.loads(toml_str)
            assert "key" in parsed


class TestTomlSq:
    """Tests for _toml_sq — sanitizing for TOML literal (single-quoted) strings."""

    # --- Basic cases ---

    def test_none_returns_empty(self):
        assert _toml_sq(None) == ""

    def test_empty_string(self):
        assert _toml_sq("") == ""

    def test_plain_string_unchanged(self):
        assert _toml_sq("hello") == "hello"

    # --- Single quote removal ---

    def test_single_quote_removed(self):
        assert _toml_sq("it's") == "its"

    def test_multiple_single_quotes_removed(self):
        assert _toml_sq("a'b'c'd") == "abcd"

    def test_only_single_quotes_returns_empty(self):
        assert _toml_sq("'''") == ""

    # --- Control character stripping ---

    def test_newline_stripped(self):
        assert _toml_sq("line\nbreak") == "linebreak"

    def test_tab_stripped(self):
        assert _toml_sq("col\there") == "colhere"

    def test_cr_stripped(self):
        assert _toml_sq("line\rend") == "lineend"

    # --- Telegraf topic template (primary use case) ---

    def test_telegraf_topic_template_unchanged(self):
        topic = "iiot/gateway/{{ .Hostname }}/{{ .PluginName }}"
        assert _toml_sq(topic) == topic

    def test_topic_with_single_quote_sanitized(self):
        # If a user types a single quote in the topic, it gets removed
        result = _toml_sq("iiot/gw'test/{{ .PluginName }}")
        assert "'" not in result
        assert "iiot/gwtest/{{ .PluginName }}" == result

    # --- Result is safe inside a TOML literal string ---

    def test_result_produces_valid_toml(self):
        import tomllib

        for value in [
            "hello",
            "it's ok",
            "line\nbreak",
            "{{ .Hostname }}/{{ .PluginName }}",
        ]:
            sanitized = _toml_sq(value)
            toml_str = f"key = '{sanitized}'\n"
            parsed = tomllib.loads(toml_str)
            assert "key" in parsed
