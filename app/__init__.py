import os
from flask import Flask, redirect, url_for


def create_app():
    app = Flask(__name__)

    app.config["DATA_DIR"] = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
    app.config["TELEGRAF_OUTPUT_DIR"] = os.environ.get("TELEGRAF_OUTPUT_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "telegraf"))
    app.config["TELEGRAF_HEALTH_URL"] = os.environ.get("TELEGRAF_HEALTH_URL", "http://localhost:8080")
    app.config["TELEGRAF_METRICS_FILE"] = os.environ.get("TELEGRAF_METRICS_FILE", "/tmp/telegraf-metrics/metrics.json")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    # Ensure data directories exist
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    os.makedirs(os.path.join(app.config["DATA_DIR"], "certs", "mqtt"), exist_ok=True)
    os.makedirs(os.path.join(app.config["DATA_DIR"], "certs", "opcua"), exist_ok=True)
    os.makedirs(app.config["TELEGRAF_OUTPUT_DIR"], exist_ok=True)

    from app.routes.opcua import opcua_bp
    from app.routes.mqtt import mqtt_bp
    from app.routes.telegraf import telegraf_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(opcua_bp)
    app.register_blueprint(mqtt_bp)
    app.register_blueprint(telegraf_bp)
    app.register_blueprint(dashboard_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.dashboard_page"))

    return app
