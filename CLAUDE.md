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

**7 Blueprints** in `app/routes/`:
- `opcua.py` -- OPC UA config + node browsing + node selection APIs
- `mqtt.py` -- MQTT config + TLS cert upload + live tail (subscribe to broker messages)
- `telegraf.py` -- Preview and generate `telegraf.conf` + restart Telegraf container via Docker SDK
- `dashboard.py` -- System health (psutil) + Telegraf pipeline metrics + container status + gateway info
- `modbus.py` -- Modbus TCP config + register management + test connection
- `help.py` -- Help page (single `/help` route)
- `configuration.py` -- Config export/import (JSON download/upload)

**6 Services** in `app/services/`:
- `config_store.py` -- Thread-safe JSON persistence (`data/config.json`) with atomic writes via tmp+rename
- `opcua_client.py` -- asyncua wrapper for connect/browse/read/namespace array/live value refresh
- `mqtt_client.py` -- paho-mqtt connection test with TLS support + `MqttTailSubscriber` singleton for live message tail
- `telegraf_config.py` -- Renders `app/telegraf/telegraf.conf.j2` with Jinja2
- `system_monitor.py` -- CPU/RAM/Disk/Network via psutil, Telegraf health via HTTP, pipeline metrics from shared JSON file, container status via Docker SDK
- `event_log.py` -- Thread-safe ring buffer (`deque(maxlen=150)`) for gateway events (OPC UA test, MQTT test, deploy, agent start/stop)

**Frontend:** Bootstrap 5 CDN + vanilla JS. Each page has a dedicated JS file in `app/static/js/`. Templates use Jinja2 server-side rendering. All config screens use **auto-save with debounce** (no Save buttons). Shared helpers split across 7 global modules loaded in `base.html`: `api.js` (fetchJSON with try/catch), `ui-helpers.js` (showAlert, setLoading, updateConfigStatus), `nav-lock.js` (lockNav/unlockNav/lockMain/unlockMain + 30s safety timeout), `agent.js` (setAgentUI, startAgent, stopAgent, applyConfig), `logs.js` (renderLogs, updateLogBadge, loadTelegrafLogs, pollLogBadge), `theme.js` (applyTheme), `app-init.js` (DOMContentLoaded wiring). All functions are global — no ES modules.

**Sidebar navigation:** Parent items: Dashboard, OPC UA, Modbus TCP, MQTT. Nav-children: OPC UA → Connection, Browse Nodes, **Acquisition** (icon `bi-sliders`, was "Node Selection"). Modbus TCP → Connection. MQTT → Connection, View Messages. All use `.nav-child` class (indented with left border). Sections: Dashboard | INPUT | OUTPUT | SYSTEM | STATE | (bottom) Deploy config button + status badge. Parent nav item active when `request.path.startswith('/opcua')` or `.startswith('/mqtt')` or `.startswith('/modbus')`. Branding shows "IIoT Gateway" (default theme) or "K-Gateway" (Keepler theme) with "powered by Telegraf" subtitle.

## Key Patterns

**Auto-save:** All config screens (OPC UA, Node Selection, MQTT) auto-save on field change with 800ms debounce. No Save buttons.

**Deploy config:** The sidebar "Deploy config" button (bottom of sidebar) generates `telegraf.conf` from config AND restarts the Telegraf container via Docker SDK (`docker` Python package). Requires Docker socket mount (`/var/run/docker.sock`). A status badge below the button shows "Config synced" or "Unapplied changes".

**Async-from-sync bridge:** asyncua is async-only but Flask is sync. Routes use `asyncio.run()` to call async OPC UA operations. Creates a new event loop per request -- acceptable for MVP low-concurrency.

**Dirty state tracking:** `config_store` tracks `_meta.last_modified` vs `_meta.last_applied`. `mark_applied()` writes both timestamps atomically (does NOT call `save()`, which would re-bump `last_modified`). The UI shows "Unapplied changes" when config has changed since last apply.

**Certificate path mapping:** Users upload certs to `data/certs/mqtt/` on host. Config stores container-side paths (`/etc/telegraf/certs/mqtt/*.pem`) because Telegraf reads them from its container volume mount.

**Config structure:** Single `data/config.json` with sections: `opcua` (includes `enabled` flag), `nodes` (array), `mqtt`, `modbus` (includes `enabled`, `registers` array), `publishing`, `acquisition`, `_meta`. Defaults defined in `app/config.py`.

**Input enabled flags:** Both OPC UA and Modbus have an `enabled` boolean in config.json. OPC UA defaults to `True` (backwards compatible via `opcua.get('enabled', true)` in Jinja2). Modbus defaults to `False`. Active toggle is a **Form Switch in the card header** — not a separate button. Template check: `{% if config.enabled is not sameas false %}checked{% endif %}` (OPC UA) or `{% if config.enabled %}checked{% endif %}` (Modbus). The toggle change fires `scheduleSave()`; `save()` reads `.checked` from the toggle.

**Config page layout (OPC UA and Modbus):** Two-column layout — col-lg-8 (Connection Settings, Active toggle in card header) | col-lg-4 (Actions: Demo Server, Test Connection, Clear configuration). No separate Disable/Enable button.

**Telegraf MQTT topic:** Uses Telegraf template syntax `{{ .Hostname }}/{{ .PluginName }}` (NOT Go template `{{ .Name }}`). Topic values with double quotes inside must use **single quotes** in TOML to avoid parse errors.

**Telegraf metrics filtering:**
- `[[outputs.mqtt]]` uses dynamic `namepass` built from enabled inputs: OPC UA adds `"opcua"`, Modbus adds `"modbus"`. Built with Jinja2 variables `opcua_on`/`modbus_on`.
- `[[outputs.file]]` uses `namepass = ["internal_*"]` to capture internal metrics for the dashboard.
- `[[inputs.internal]]` has `collect_memstats = true` to enable per-plugin metrics.

**Modbus TCP input (Telegraf 1.33):** Uses `[[inputs.modbus]]` with register-based format — NOT metric-based. Critical requirements for Telegraf 1.33:
- `controller` must use `tcp://` prefix: `"tcp://host:502"` — plain `"host:502"` gives "invalid controller" error
- `address` is `[]uint16` array with ALL registers for the type: 16-bit → `[0]`, 32-bit → `[0, 1]`, 64-bit → `[0,1,2,3]`
- `scale = 1.0` required on every register — defaults to 0.0 which is invalid
- `FLOAT32` is deprecated → use `FLOAT32-IEEE`; `FLOAT64` → `FLOAT64-IEEE`
- `transmission_mode = "TCP"` no longer needed (inferred from `tcp://` prefix)
- `skip_processors_after_aggregators = false` in `[agent]` suppresses v1.40 warning

In `telegraf.conf.j2`: macro `reg_addrs(addr, data_type)` computes the correct address array; macro `norm_dt(data_type)` maps deprecated type names; `tcp://` prefix is added automatically if missing. Registers grouped by type via `selectattr('register_type', 'equalto', 'holding') | list`. Coil/discrete registers use `data_type = "BOOL"`, omit `byte_order`.

**Telegraf internal metrics parsing:** Dashboard reads per-plugin metrics from a shared JSON file (`/tmp/telegraf-metrics/metrics.json`), parsing NDJSON lines in reverse order. Key fields:
- `internal_gather` (input=opcua): scan_time_ms, opcua_errors
- `internal_write` (output=mqtt): `metrics_added` → OPC UA Read (published to MQTT), `metrics_written` → MQTT Send (confirmed by broker), buffer_size, mqtt_dropped, mqtt_errors
- `internal_opcua`: read_success/read_error (true cumulative Telegraf counters, 1 per gather batch)

`metrics_gathered` and `metrics_written` are **cumulative counters** since Telegraf started (in-memory in Telegraf, reset to 0 on restart). Shown raw from NDJSON — no Flask accumulation. Low numbers after long uptime = slow scan rate, not a bug.

**Telegraf TLS config:** Only include TLS cert paths in `telegraf.conf.j2` when endpoint uses `mqtts://` or `ssl://`. Mixing TLS certs with plain `mqtt://` causes Telegraf to crash with EOF.

**Telegraf permissions:** Container runs as `user: "0:0"` (root) with an entrypoint that pre-creates the metrics file before starting Telegraf.

**Message Format (publishing):** The Acquisition page has an Individual / Grouped toggle stored in `config.json` under `publishing` (`mode`, `group_interval`). Default: `mode="grouped"`, `group_interval="30s"`. API: `GET/POST /api/opcua/publishing`. Grouped mode uses `[[inputs.opcua.group]]` + `tagexclude = ["id"]` + `[[aggregators.merge]]` with `drop_original = true`. **Critical:** use `aggregators.merge`, NOT `processors.merge` (doesn't exist). `drop_original = true` is required — without it both individual and grouped messages are published. `[[inputs.opcua.group]]` does NOT support `metric_name` in Telegraf 1.33.

**OPC UA Acquisition Mode:** Stored in `acquisition` section of `config.json`. API: `GET/POST /api/opcua/acquisition`. Defaults: `mode="polling"`, `scan_rate="30s"`, `sampling_interval="1s"`, `deadband_type="None"`, `deadband_value=0.0`. Two modes:
- **Polling**: adds plugin-level `interval = scan_rate` to `[[inputs.opcua]]`. No `monitoring_params`.
- **Subscription**: no plugin-level interval. Each node gets `[inputs.opcua.nodes.monitoring_params]` + nested `[inputs.opcua.nodes.monitoring_params.data_change_filter]`. **Critical:** deadband must be inside `data_change_filter`, NOT at `monitoring_params` level.
In `telegraf.conf.j2`: variables `acq`, `opcua_scan`, `opcua_sample`, `is_subscription`. `aggregators.merge period` = `opcua_sample if is_subscription else opcua_scan`. Route merges saved config with `DEFAULT_CONFIG` defaults to handle existing configs without the `acquisition` key.

**OPC UA Browse Nodes:** Rich node browser at `/opcua/browser`. Two-column layout: tree (left) + details (right).

*Extended attributes read by `read_node_details()` for Variable nodes (each in its own `try/except → None` — graceful on `BadAttributeIdInvalid`):*
- `access_level` (int|null) — bitmask: bit0=Read(0x01), bit1=Write(0x02), bit2=HistoryRead(0x04)
- `description` (str|null) — `ua.AttributeIds.Description` → `LocalizedText.Text`
- `value_rank` (int|null) — -1=Scalar, 0=ScalarOrOneDimension, 1+=Array
- `min_sampling_interval` (float|null, ms) — -1=Continuous, 0=Fastest
- `historizing` (bool|null)
- `status_code` (str|null) — "Good" / "Uncertain_*" / "Bad_*" (from `DataValue.StatusCode.name`)
- `source_timestamp`, `server_timestamp` (ISO str|null) — from `ua.AttributeIds.Value` DataValue (NOT from `read_value()` which unwraps it)
- `engineering_units` (str|null) — browse `HasProperty` children for "EngineeringUnits" node, read `EUInformation.DisplayName.Text`

*New functions in `opcua_client.py`:*
- `read_namespace_array(config)` — reads `ns=0;i=2255` (standard Server.NamespaceArray node)
- `read_node_value(config, node_id_str)` — lightweight read of only `ua.AttributeIds.Value` DataValue (value + status_code + timestamps), used for auto-refresh

*New API endpoints in `opcua.py`:*
- `GET /api/opcua/namespaces` → `[{index, uri}]`
- `GET /api/opcua/node-value?node_id=` → `{value, status_code, source_timestamp, server_timestamp}`

*Browser UX features in `opcua_browser.js`:*
- **Search/filter** — `<input type="search" id="tree-search">` in card-header; `filterTree(term)` hides non-matching `.tree-node` rows; re-applied after each `expandNode()` call
- **Breadcrumb** — `breadcrumbPath` array updated on each row click (`dataset.depth`); `renderBreadcrumb()` generates Bootstrap `<ol class="breadcrumb">`; clicking an ancestor calls `loadTree(node_id)`
- **Already-selected indicator** — `selectedNodeIds` Set (module scope) populated from `/api/opcua/nodes` on load; `bi-check-circle-fill text-success` appended to rows in `buildTreeLevel()`; updated locally after add without refetch
- **Bulk select** — checkboxes (`.bulk-cb`) prepended to Variable rows; `#bulk-toolbar` shown when any checked; `addBulkToSelection()` fetches current nodes, skips duplicates, POSTs full array; `parseNodeIdToEntry()` parses canonical `ns=X;Y=Z` via regex `/ns=(\d+);([isgb])=(.+)/`; `reconstructNodeId(n)` rebuilds from stored entry
- **Auto-refresh** — toggle switch in details card-header (only visible for Variables); `startAutoRefresh(nodeId)` / `stopAutoRefresh()` with `setInterval(3000)`; calls `GET /api/opcua/node-value`; stops and unchecks on node change
- **Server Namespaces** — collapsible card below selected-count; `loadNamespaceTable()` fetches `/api/opcua/namespaces`; NS index 0 shown muted; URI column with `word-break:break-all`

**Autofill prevention pattern:** Browser autofill fires `input`/`change` events on hidden fields (password) at page load → spurious auto-save. Fix: `let userInteracted = false` + listeners on `pointerdown`/`keydown` with `{ once: true }`. `scheduleAutoSave()` returns early if `!userInteracted`. Applied in `opcua_config.html`.

**Dashboard aggregator race condition:** `refreshTelegrafMetrics()` runs before `refreshGatewayInfo()` sets `nodesConfigured`. Fix: `/api/dashboard/telegraf-metrics` response includes `nodes_configured` read from config.json. Loss rate false positive after Telegraf restart: only compute when `d.mqtt_written > 0`.

**Dashboard telegraf_metrics field naming:** `system_monitor.get_telegraf_metrics()` returns `process_crash_detected` (internal key). `dashboard.telegraf_metrics()` extracts it with `.pop()`, logs it to event log if true, and re-exposes it as `process_crashed` in the final JSON response (the frontend key). The `process_crashed` flag triggers `agent-dot-crashed` styling on the STATE dot.

**First-deploy detection:** `dashboard.py` checks `os.path.isfile(conf_path)` and passes `never_deployed` to the template. A welcome banner is shown when no config has been deployed yet.

**Telegraf entrypoint (docker-compose.yml):** Container waits for `telegraf.conf` to exist before starting (loop with `sleep 3`), then runs a retry loop with `sleep 10` on crash. Telegraf volume is mounted as a directory (`./telegraf:/etc/telegraf-conf:ro`) — NOT as a file — to avoid Docker creating it as a directory on fresh installs.

**Telegraf logs endpoint:** `GET /api/telegraf/logs` reads Docker container logs via SDK (`container.logs(tail=50)`). Exposed in a Telegraf tab inside the Logs modal (`logs.js`: `loadTelegrafLogs()`). After deploy, `telegraf.py` sleeps 3s then calls `_get_telegraf_config_error(since=deploy_time)` which filters logs by: (1) Docker SDK `since=` param to exclude pre-deploy lines, (2) keyword filter (`config`, `toml`, `parse`, `invalid`, etc.) to ignore runtime E! errors like OPC UA session drops. Event log message: "Telegraf config error detected".

**MQTT Live Tail:** `MqttTailSubscriber` is a module-level singleton in `mqtt_client.py` with a background paho-mqtt thread and `deque(maxlen=50)`. Converts Telegraf topic templates to MQTT wildcards via regex (`{{ .Hostname }}` -> `+`). Auto-stops after 10 seconds in the frontend.

**Container status:** `system_monitor.get_container_status()` uses Docker SDK to list project containers and maps service names to user-friendly display names (e.g. `gateway` -> `Edge UI`, `telegraf` -> `Telegraf Data Agent`).

**CSS inline style vs class specificity:** When toggling element visibility, set `el.style.display = ""` (not `"none"`) to let CSS classes control display. Inline styles override class-based rules.

**Theme system:** Two themes — default (dark) and keepler (light). Stored in `localStorage("iiot-theme")`, applied via `data-theme="keepler"` + `data-bs-theme="light"` on `<html>`. Inline `<script>` in `<head>` prevents flash on navigation. Keepler uses Montserrat font (UI only; JetBrains Mono kept for code content like config preview and MQTT payload). Corporate colors: INPUT=#b8860b, OUTPUT=#c82b4a, SYSTEM=#6b2cf5, STATE=#0891b2. Keepler sidebar is white (not dark).

**Branding / logos:** Logo images in `app/static/img/`: `logo-default.png` (dark background), `logo-light.png` (light background), `logo-white.png` (white version). Sidebar uses `logo-white.png` for the default theme via `.brand-default` block. Keepler theme uses its own brand block (`.brand-keepler`). CSS: `.brand-logo { width: 100%; height: auto; display: block; }`. README header also uses `logo-white.png` as inline `<img>` before the title.

**Agent state control:** STATE section in sidebar has two separate buttons: `btn-agent-play` and `btn-agent-stop`. `setAgentUI(running, crashed=false)` in `agent.js` updates their active classes and the status dot. Three dot states: green (running), orange (stopped), red pulsing `agent-dot-crashed` (crashed). Each button calls its own async function (`startAgent`, `stopAgent`) with `lockNav()`/`unlockNav()`. `lockNav()`/`unlockNav()` also disable/enable these STATE buttons to prevent double-clicks during long ops. `applyConfig()` llama `setAgentUI(true)` tras restart exitoso. `.btn-state:disabled { opacity: 1 }` — NO reducir opacity al deshabilitar, para que la sección STATE se vea igual durante el lock del Deploy.

**Event log:** `app/services/event_log.py` — thread-safe ring buffer `deque(maxlen=150)`. Logs OPC UA test, MQTT test, deploy config, agent start/stop events. Badge in sidebar uses `sessionStorage("logsLastSeen")` to avoid reappearing after viewing. Logs modal has two tabs: Gateway events + Telegraf raw logs (loaded via `GET /api/telegraf/logs`). Each log entry has a **copy-to-clipboard button** (`.log-copy-btn`, visible on hover): copies `COMPONENT | timestamp | message | detail`, icon briefly changes to `bi-clipboard-check`.

**Sidebar SYSTEM section order:** Preview Config → Logs → Help.

## Help Page

6 tabs: Getting Started | Dashboard | OPC UA | MQTT & Cloud | Telegraf | IIoT Concepts.

- `app/routes/help.py` — simple Blueprint with a single `/help` route
- `app/templates/help.html` — all content inline
- CSS classes: `help-section`, `help-h2`, `help-p`, `help-steps`, `help-step`, `help-diagram`, `help-callout-{info/tip/warning}`, `help-card`, `help-table`, `help-list`, `help-code-block`, `help-conf-block`
- `help-diagram pre` and `help-code-block` use hardcoded `'JetBrains Mono','Consolas','Courier New',monospace` — NOT `var(--font-mono)`. Keepler theme overrides `--font-mono` with Montserrat (proportional), which breaks ASCII art.
- Screenshots served from `app/static/screenshots/` via `url_for('static', filename='screenshots/...')`. Do NOT use paths outside the static directory.
- Telegraf tab includes an "Updating the gateway" section with `git pull` + `docker compose up --build -d gateway`.

## Configuration Page

- `app/routes/configuration.py` — Blueprint with export and import routes
- `app/templates/configuration.html` — page template
- `app/static/js/configuration.js` — frontend logic
- `GET /api/configuration/export` — downloads `data/config.json` as a JSON file attachment
- `POST /api/configuration/import` — accepts uploaded JSON, validates structure, overwrites config

## Dashboard Layout

3-section dashboard with 5-second auto-refresh:
1. **Pipeline Health** -- Side-by-side layout (`.pipeline-health-body`): left column (`.pipeline-anim-col`, `border-right`) contains the flow animation; right column (`.pipeline-metrics-col`) contains vertical metric blocks. Flow animation: dual-input mode (`.pipeline-dual`) uses Y-fork — `pf-y-section` with two `pf-y-row` divs, each with a `pf-y-arm`, and a JS-positioned `pf-y-vbar`. `positionForkBar()` in `dashboard.js` sets the vertical bar height via `getBoundingClientRect()`. No pulse ring animation. Metric blocks (`.pm-block`): one per source, each with a `.pm-block-header` (colored bottom border via `currentColor`) and a `dash-grid dash-grid-metrics` grid. Sources: OPC UA (accent), Modbus (#b8860b), Output (#34d399). Status dots (`.stat-dot`) on error metrics: green if 0, red pulsing if >0, updated via `setDot(id, isOk)` in `dashboard.js`. When both inputs are disabled, a placeholder node `.pf-node-none` is shown with `bi-slash-circle` icon and "No input active" text.
2. **System Health** -- CPU, Memory, Disk, Network I/O in 4-column grid with progress bars.
3. **Gateway Info** -- Component status (all containers) + 3 metrics: **Telegraf running** (container uptime via Docker `State.StartedAt`), **Last Deploy Config** (`_meta.last_applied`), **Last restart** (`_meta.last_restart = {started_at, reason}` with badge Deploy/Manual/⚠ Unplanned/⚠ Crash). Unplanned restarts auto-detected in `get_gateway_info()` by comparing Docker `started_at` vs stored baseline; persisted immediately via `config_store.record_restart()`. Crash detection via `_prev_gathered` dict in system_monitor.py — if a cumulative counter drops from >5, `process_crash_detected=True` is returned; `dashboard.py` logs the event and records reason="crash". `_compute_unexpected_restart(current, last)` is a pure function for testability. CSS: `.restart-badge` + `.restart-deploy/.restart-manual/.restart-unplanned/.restart-crash`.

**Restart race condition fix:** Two-layer guard in `telegraf.py`:
1. `reset_crash_detection()` called BEFORE `container.start()` clears `_prev_gathered` so counter-drop detection doesn't fire on the new metrics.
2. `mark_intentional_restart()` called BEFORE `container.start()` sets `_intentional_restart_pending=True` to suppress "unplanned" detection in `get_gateway_info()` while the precise `started_at` is not yet recorded.
3. `record_restart(datetime.now(), reason)` written IMMEDIATELY after `container.start()` (before sleep) as a preliminary timestamp.
4. After `sleep(2/3)`, `record_restart(docker_started_at, reason)` updates with the precise Docker timestamp.
5. `reset_crash_detection()` + `clear_intentional_restart()` called after recording — `clear_intentional_restart()` also starts a 15-second grace period (`_POST_RESTART_GRACE_SECS=15`) during which `_prev_gathered` is not updated and crash detection is suppressed to absorb stale `metrics.json` data from before the restart.

Process crash INSIDE the container (entrypoint retry loop) does NOT call `record_restart` — it's not a container-level restart event. Docker `StartedAt` is unchanged. Applies to both `start_telegraf()` and `generate_config()` in `telegraf.py`.

Dashboard container start/stop: `POST /api/dashboard/container/<service>/start` and `/stop`. Only `DEMO_SERVICES = {"opcua-demo-server", "mosquitto"}` are allowed (returns 403 otherwise). Button click → disable button → call API → `refreshGatewayInfo()`.

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
- `modbus-demo-server` -- pymodbus TCP server on port 502 with 5 FLOAT32-IEEE holding registers (temperature 0-1, pressure 2-3, motor_speed 4-5, voltage 6-7, current 8-9). Source: `test_infra/modbus_server/server.py`
- `mosquitto` -- Anonymous MQTT broker on ports 1883 + 9001 (websocket). Config: `test_infra/mosquitto/mosquitto.conf`

The UI has "Use Demo Server" / "Demo" quick-fill buttons.

## Files NOT in git (runtime-generated)

- `data/config.json` -- user configuration (runtime state)
- `data/certs/` -- TLS certificates
- `telegraf/telegraf.conf` -- generated by the app

## CI / GitHub Actions

- `.github/workflows/tests.yml` -- tests on PR to main + `workflow_dispatch`
- `.github/workflows/code-quality.yml` -- ruff lint/format + `workflow_dispatch`
- `.github/workflows/security.yml` -- bandit + pip-audit + trivy + `workflow_dispatch`
- `.github/workflows/codeql.yml` -- CodeQL Python + `workflow_dispatch`
- All have `workflow_dispatch` for manual runs from GitHub Actions UI

**Trivy setup:** `continue-on-error: true` on the scan step so install/network failures don't break the job. Fallback step creates a minimal valid SARIF if the file is missing — must include `runs[0].tool.driver` (GitHub Code Scanning API rejects `"runs":[]`). Uses `github/codeql-action/upload-sarif@v4` (v3 deprecated Dec 2026).

**pip-audit** is the real gate (blocks PRs on CVEs). Trivy is reporting only (uploads SARIF to GitHub Security tab).

## Dependencies

- `Flask==3.1.3`, `Werkzeug==3.1.6` -- pinned to CVE-patched versions
- Run `pip-audit -r requirements.txt` locally to check for new CVEs before release

## Tests

- 150 tests, all green -- run with `source venv/bin/activate && python -m pytest tests/ -v`
- Test files:
  - `test_telegraf_config.py` (27) -- rendering del .j2 (polling, subscription, Modbus, dual, grouped, disabled, injection)
  - `test_toml_filters.py` (31) -- `_toml_dq` and `_toml_sq` (security, edge cases, unicode)
  - `test_mqtt_client.py` (12) -- `_parse_endpoint` (schemes, ports, TLS flag)
  - `test_config_store.py` (25) -- `is_dirty`, `mark_applied`, `load` resilience, save round-trip, `record_restart`
  - `test_system_monitor.py` (28) -- NDJSON parser + `_compute_unexpected_restart` + `TestCrashDetection`
  - `test_opcua_client.py` (27) -- mock-based: access_level bitmask, value_rank labels, min_sampling formatting, namespace array, read_node_value timestamps
