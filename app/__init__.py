import os

from flask import Flask, redirect, url_for


def create_app():
    app = Flask(__name__)

    app.config["DATA_DIR"] = os.environ.get(
        "DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    )
    app.config["TELEGRAF_OUTPUT_DIR"] = os.environ.get(
        "TELEGRAF_OUTPUT_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "telegraf"),
    )
    app.config["TELEGRAF_HEALTH_URL"] = os.environ.get(
        "TELEGRAF_HEALTH_URL", "http://localhost:8080"
    )
    app.config["TELEGRAF_METRICS_FILE"] = os.environ.get(
        "TELEGRAF_METRICS_FILE",
        "/tmp/telegraf-metrics/metrics.json",  # nosec B108
    )
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    # Ensure data directories exist
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    os.makedirs(os.path.join(app.config["DATA_DIR"], "certs", "mqtt"), exist_ok=True)
    os.makedirs(os.path.join(app.config["DATA_DIR"], "certs", "opcua"), exist_ok=True)
    os.makedirs(app.config["TELEGRAF_OUTPUT_DIR"], exist_ok=True)

    from app.routes.dashboard import dashboard_bp
    from app.routes.help import help_bp
    from app.routes.modbus import modbus_bp
    from app.routes.mqtt import mqtt_bp
    from app.routes.opcua import opcua_bp
    from app.routes.telegraf import telegraf_bp

    app.register_blueprint(opcua_bp)
    app.register_blueprint(modbus_bp)
    app.register_blueprint(mqtt_bp)
    app.register_blueprint(telegraf_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(help_bp)

    @app.context_processor
    def inject_input_status():
        from app.services import config_store as cs

        cfg = cs.load()
        return {
            "opcua_ready": len(cfg.get("nodes", [])) > 0,
            "modbus_ready": cfg.get("modbus", {}).get("enabled", False)
            and len(cfg.get("modbus", {}).get("registers", [])) > 0,
        }

    @app.route("/")
    def index():
        return redirect(url_for("dashboard.dashboard_page"))

    return app
