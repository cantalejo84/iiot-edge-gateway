# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Industrial IoT Edge Gateway: Flask web app that configures Telegraf to read OPC UA data and publish to MQTT (AWS IoT Core). The Flask app generates `telegraf.conf`, Telegraf does the actual data collection. Designed to run in Docker on edge servers.

## Development Commands

```bash
# Full stack (gateway + telegraf + demo OPC UA server + Mosquitto broker)
docker compose up --build -d

# Dev mode (hot-reload: mounts ./app as volume + Flask debug)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Rebuild only gateway after code changes
docker compose up --build -d gateway

# Stop all containers
docker compose down

# Stop and remove volumes (resets metrics data)
docker compose down -v

# View logs
docker compose logs -f gateway
docker compose logs -f telegraf

# Local dev without Docker (port 5000 may be taken by AirPlay on macOS)
source venv/bin/activate
FLASK_APP=app FLASK_DEBUG=1 flask run --port 8050
```

Gateway runs on port **8050** (`localhost:8050`).

## Architecture

**Request flow:** Browser -> Flask routes (blueprints) -> services -> JSON config / async OPC UA / MQTT test

**4 Blueprints** in `app/routes/`:
- `opcua.py` -- OPC UA config + node browsing + node selection APIs
- `mqtt.py` -- MQTT config + TLS cert upload + live tail (subscribe to broker messages)
- `telegraf.py` -- Preview and generate `telegraf.conf` + restart Telegraf container via Docker SDK
- `dashboard.py` -- System health (psutil) + Telegraf pipeline metrics + container status + gateway info

**6 Services** in `app/services/`:
- `config_store.py` -- Thread-safe JSON persistence (`data/config.json`) with atomic writes via tmp+rename
- `opcua_client.py` -- asyncua wrapper for connect/browse/read
- `mqtt_client.py` -- paho-mqtt connection test with TLS support + `MqttTailSubscriber` singleton for live message tail
- `telegraf_config.py` -- Renders `app/telegraf/telegraf.conf.j2` with Jinja2
- `system_monitor.py` -- CPU/RAM/Disk/Network via psutil, Telegraf health via HTTP, pipeline metrics from shared JSON file, container status via Docker SDK

**Frontend:** Bootstrap 5 CDN + vanilla JS. Each page has a dedicated JS file in `app/static/js/`. Templates use Jinja2 server-side rendering. All config screens use **auto-save with debounce** (no Save buttons). Shared helpers in `app/static/js/common.js` (`fetchJSON`, `setLoading`, `showAlert`, `updateConfigStatus`).

**Sidebar navigation:** Browse Nodes and Node Selection are visually nested under OPC UA Config using `.nav-child` class (indented with left border). Sections: Dashboard | INPUT | OUTPUT | SYSTEM | STATE | (bottom) Deploy config button + status badge. Branding shows "IIoT Gateway" (default theme) or "K-Gateway" (Keepler theme) with "powered by Telegraf" subtitle.

## Key Patterns

**Auto-save:** All config screens (OPC UA, Node Selection, MQTT) auto-save on field change with 800ms debounce. No Save buttons.

**Deploy config:** The sidebar "Deploy config" button (bottom of sidebar) generates `telegraf.conf` from config AND restarts the Telegraf container via Docker SDK (`docker` Python package). Requires Docker socket mount (`/var/run/docker.sock`). A status badge below the button shows "Config synced" or "Unapplied changes".

**Async-from-sync bridge:** asyncua is async-only but Flask is sync. Routes use `asyncio.run()` to call async OPC UA operations. Creates a new event loop per request -- acceptable for MVP low-concurrency.

**Dirty state tracking:** `config_store` tracks `_meta.last_modified` vs `_meta.last_applied`. `mark_applied()` writes both timestamps atomically (does NOT call `save()`, which would re-bump `last_modified`). The UI shows "Unapplied changes" when config has changed since last apply.

**Certificate path mapping:** Users upload certs to `data/certs/mqtt/` on host. Config stores container-side paths (`/etc/telegraf/certs/mqtt/*.pem`) because Telegraf reads them from its container volume mount.

**Config structure:** Single `data/config.json` with sections: `opcua`, `nodes` (array), `mqtt`, `_meta`. Defaults defined in `app/config.py`.

**Telegraf MQTT topic:** Uses Telegraf template syntax `{{ .Hostname }}/{{ .PluginName }}` (NOT Go template `{{ .Name }}`). Topic values with double quotes inside must use **single quotes** in TOML to avoid parse errors.

**Telegraf metrics filtering:**
- `[[outputs.mqtt]]` uses `namepass = ["opcua"]` to only send OPC UA data to the broker (NOT `tagpass`, because OPC UA metrics don't have an `input` tag).
- `[[outputs.file]]` uses `namepass = ["internal_*"]` to capture internal metrics for the dashboard.
- `[[inputs.internal]]` has `collect_memstats = true` to enable per-plugin metrics.

**Telegraf internal metrics parsing:** Dashboard reads per-plugin metrics from a shared JSON file (`/tmp/telegraf-metrics/metrics.json`), parsing NDJSON lines in reverse order. Key fields:
- `internal_gather` (input=opcua): scan_time_ms, opcua_errors
- `internal_write` (output=mqtt): `metrics_added` → OPC UA Read (published to MQTT), `metrics_written` → MQTT Send (confirmed by broker), buffer_size, mqtt_dropped, mqtt_errors
- `internal_opcua`: read_success/read_error (true cumulative Telegraf counters, 1 per gather batch)

`metrics_added` and `metrics_written` are per-cycle counts, accumulated in memory via module-level `_acc` dict in `system_monitor.py` (resets on Flask restart). New timestamp in the file triggers accumulation.

**Telegraf TLS config:** Only include TLS cert paths in `telegraf.conf.j2` when endpoint uses `mqtts://` or `ssl://`. Mixing TLS certs with plain `mqtt://` causes Telegraf to crash with EOF.

**Telegraf permissions:** Container runs as `user: "0:0"` (root) with an entrypoint that pre-creates the metrics file before starting Telegraf.

**MQTT Live Tail:** `MqttTailSubscriber` is a module-level singleton in `mqtt_client.py` with a background paho-mqtt thread and `deque(maxlen=5)`. Converts Telegraf topic templates to MQTT wildcards via regex (`{{ .Hostname }}` -> `+`). Auto-stops after 10 seconds in the frontend.

**Container status:** `system_monitor.get_container_status()` uses Docker SDK to list project containers and maps service names to user-friendly display names (e.g. `gateway` -> `Edge UI`, `telegraf` -> `Telegraf Data Agent`).

**CSS inline style vs class specificity:** When toggling element visibility, set `el.style.display = ""` (not `"none"`) to let CSS classes control display. Inline styles override class-based rules.

**Theme system:** Two themes — default (dark) and keepler (light). Stored in `localStorage("iiot-theme")`, applied via `data-theme="keepler"` + `data-bs-theme="light"` on `<html>`. Inline `<script>` in `<head>` prevents flash on navigation. Keepler uses Montserrat font (UI only; JetBrains Mono kept for code content like config preview and MQTT payload). Corporate colors: INPUT=#b8860b, OUTPUT=#c82b4a, SYSTEM=#6b2cf5, STATE=#0891b2. Keepler sidebar is white (not dark).

**Agent state control:** STATE section in sidebar has two separate buttons: `btn-agent-play` and `btn-agent-stop`. `setAgentUI(running)` in `common.js` updates their active classes and the status dot. Each button calls its own async function (`startAgent`, `stopAgent`) with `lockNav()`/`unlockNav()`.

**Event log:** `app/services/event_log.py` — thread-safe ring buffer `deque(maxlen=150)`. Logs OPC UA test, MQTT test, deploy config, agent start/stop events. Badge in sidebar uses `sessionStorage("logsLastSeen")` to avoid reappearing after viewing.

## Dashboard Layout

3-section dashboard with 5-second auto-refresh:
1. **Pipeline Health** -- OPC UA Read -> Buffer -> MQTT Send flow visualization + stats (Scan Time, Dropped, Errors, Loss Rate)
2. **System Health** -- CPU, Memory, Disk, Network I/O in 4-column grid with progress bars
3. **Data Quality + Gateway Info** -- OPC UA read success/error rates + uptime, nodes configured, last config applied, component status (all containers with running/stopped indicators)

All metrics have Bootstrap tooltip hints explaining what they mean.

## MQTT Config Page Layout

Single-card **Broker Connection** with:
- Endpoint, Topic Pattern, QoS, Data Format fields
- **Demo** button (quick-fill with built-in Mosquitto) and **Test** button (green check on success) in the header
- **TLS Certificates** collapsible section (collapsed by default)

**Live Messages** card with Start/Stop, auto-stop after 10s, subscribed topic badge, and copy-to-clipboard per message.

## Demo Infrastructure

Built-in demo servers in `docker-compose.yml`:
- `opcua-demo-server` -- asyncua server with simulated Plant/Line1/Line2 hierarchy (Temperature, Pressure, Speed, Status variables that update every 2s). Source: `test_infra/opcua_server/server.py`
- `mosquitto` -- Anonymous MQTT broker on ports 1883 + 9001 (websocket). Config: `test_infra/mosquitto/mosquitto.conf`

The UI has "Use Demo Server" / "Demo" quick-fill buttons.

## Files NOT in git (runtime-generated)

- `data/config.json` -- user configuration (runtime state)
- `data/certs/` -- TLS certificates
- `telegraf/telegraf.conf` -- generated by the app
