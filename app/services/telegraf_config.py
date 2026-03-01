import os
import re
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader


def _toml_dq(value):
    """Escape a value for safe use inside a TOML double-quoted string."""
    s = str(value) if value is not None else ""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = re.sub(r"[\r\n\t]", "", s)
    return s


def _toml_sq(value):
    """Strip characters unsafe in a TOML literal (single-quoted) string."""
    s = str(value) if value is not None else ""
    s = s.replace("'", "")
    s = re.sub(r"[\r\n\t]", "", s)
    return s


def render_config(config):
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "telegraf")
    env = Environment(loader=FileSystemLoader(template_dir))  # nosec B701
    env.filters["toml_dq"] = _toml_dq
    env.filters["toml_sq"] = _toml_sq
    template = env.get_template("telegraf.conf.j2")
    return template.render(
        opcua=config.get("opcua", {}),
        nodes=config.get("nodes", []),
        mqtt=config.get("mqtt", {}),
        publishing=config.get(
            "publishing", {"mode": "individual", "group_interval": "10s"}
        ),
        modbus=config.get("modbus", {"enabled": False, "registers": []}),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
