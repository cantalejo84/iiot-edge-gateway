import os
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader


def render_config(config):
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "telegraf")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("telegraf.conf.j2")
    return template.render(
        opcua=config.get("opcua", {}),
        nodes=config.get("nodes", []),
        mqtt=config.get("mqtt", {}),
        publishing=config.get(
            "publishing", {"mode": "individual", "group_interval": "10s"}
        ),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
