# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Industrial IoT Edge Gateway: Flask web app that configures Telegraf to read OPC UA data and publish to MQTT (AWS IoT Core). The Flask app generates `telegraf.conf`, Telegraf does the actual data collection. Designed to run in Docker on edge servers.

## Development Commands

```bash
# Local dev (port 5000 may be taken by AirPlay on macOS, use 8050)
source venv/bin/activate
FLASK_APP=app FLASK_DEBUG=1 flask run --port 8050

# Docker dev (includes test OPC UA server + Mosquitto MQTT broker)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Production
docker compose up --build -d

# After generating new telegraf.conf via UI
docker compose restart telegraf
```

## Architecture

**Request flow:** Browser → Flask routes (blueprints) → services → JSON config / async OPC UA / MQTT test

**4 Blueprints** in `app/routes/`:
- `opcua.py` — OPC UA config + node browsing + node selection APIs
- `mqtt.py` — MQTT config + TLS cert upload
- `telegraf.py` — Preview and generate `telegraf.conf`
- `dashboard.py` — System health (psutil) + Telegraf metrics

**5 Services** in `app/services/`:
- `config_store.py` — Thread-safe JSON persistence (`data/config.json`) with atomic writes via tmp+rename
- `opcua_client.py` — asyncua wrapper for connect/browse/read
- `mqtt_client.py` — paho-mqtt connection test with TLS support
- `telegraf_config.py` — Renders `app/telegraf/telegraf.conf.j2` with Jinja2
- `system_monitor.py` — CPU/RAM via psutil, Telegraf health via HTTP, metrics from shared JSON file

**Frontend:** Bootstrap 5 CDN + vanilla JS. Each page has a dedicated JS file in `app/static/js/`. Templates use Jinja2 server-side rendering.

## Key Patterns

**Async-from-sync bridge:** asyncua is async-only but Flask is sync. Routes use `asyncio.run()` to call async OPC UA operations. Creates a new event loop per request — acceptable for MVP low-concurrency.

**Dirty state tracking:** `config_store` tracks `_meta.last_modified` vs `_meta.last_applied`. The UI shows an "Unapplied changes" warning when config has been saved but `telegraf.conf` hasn't been regenerated.

**Certificate path mapping:** Users upload certs to `data/certs/mqtt/` on host. Config stores container-side paths (`/etc/telegraf/certs/mqtt/*.pem`) because Telegraf reads them from its container volume mount.

**Config structure:** Single `data/config.json` with sections: `opcua`, `nodes` (array), `mqtt`, `_meta`. Defaults defined in `app/config.py`.

## Testing Infrastructure

`test_infra/opcua_server/server.py` — asyncua server with simulated Plant/Line1/Line2 hierarchy (Temperature, Pressure, Speed, Status variables that update every 2s).

`test_infra/mosquitto/mosquitto.conf` — Anonymous MQTT broker on ports 1883 + 9001 (websocket).

Both start automatically with `docker-compose.dev.yml`.
