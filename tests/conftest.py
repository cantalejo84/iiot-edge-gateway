"""Shared pytest fixtures."""
import pytest
from flask import Flask


@pytest.fixture
def app_ctx(tmp_path):
    """Minimal Flask app context with isolated temp DATA_DIR and metrics file."""
    app = Flask(__name__)
    app.config["DATA_DIR"] = str(tmp_path)
    app.config["TELEGRAF_METRICS_FILE"] = str(tmp_path / "metrics.json")
    with app.app_context():
        yield tmp_path
