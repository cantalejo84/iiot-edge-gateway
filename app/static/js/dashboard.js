// Dashboard - auto-refresh pipeline, system health, quality metrics

let lastOpcuaCount = null;
let telegrafRunning = null;
let nodesConfigured = 0;
let anyInputActive = true;

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });
    positionForkBar();
    window.addEventListener("resize", positionForkBar);
    refreshAll();
    setInterval(refreshAll, 5000);

    document.getElementById("g-containers").addEventListener("click", async (e) => {
        const btn = e.target.closest(".demo-toggle-btn");
        if (!btn) return;
        const { service, action } = btn.dataset;
        btn.disabled = true;
        await fetchJSON(`/api/dashboard/container/${service}/${action}`, { method: "POST" });
        await refreshGatewayInfo();
    });
});

async function refreshAll() {
    await Promise.all([
        refreshHealth(),
        refreshTelegrafMetrics(),
        refreshGatewayInfo(),
        refreshTelegrafRunning(),
    ]);
}

async function refreshTelegrafRunning() {
    try {
        const d = await fetchJSON("/api/telegraf/status");
        telegrafRunning = d.ok ? d.running : null;
        updatePipelineStatus();
    } catch (e) {}
}

function updatePipelineStatus() {
    if (telegrafRunning === true && anyInputActive) {
        setPipelineState("running");
    } else if (telegrafRunning === true && !anyInputActive) {
        setPipelineState("idle");
    } else {
        setPipelineState("stopped");
    }
}

// --- System Health ---

async function refreshHealth() {
    try {
        const d = await fetchJSON("/api/dashboard/health");
        updateGauge("cpu", d.cpu_percent);
        updateGauge("ram", d.memory_percent);
        updateGauge("disk", d.disk_percent);

        const ramDetail = document.getElementById("ram-detail");
        if (ramDetail) {
            ramDetail.textContent = `${formatBytes(d.memory_used_mb * 1024 * 1024)} / ${formatBytes(d.memory_total_mb * 1024 * 1024)}`;
        }

        document.getElementById("net-sent").textContent = formatBytes(d.bytes_sent);
        document.getElementById("net-recv").textContent = formatBytes(d.bytes_recv);
    } catch (e) {}
}

function updateGauge(id, value) {
    const valueEl = document.getElementById(`${id}-value`);
    const barEl = document.getElementById(`${id}-bar`);
    if (!valueEl || !barEl) return;
    valueEl.textContent = `${Math.round(value)}%`;
    barEl.style.width = `${value}%`;
    barEl.className = "progress-bar";
    if (value > 90) barEl.classList.add("bg-danger");
    else if (value > 70) barEl.classList.add("bg-warning");
    else barEl.classList.add("bg-success");
}

// --- Pipeline Metrics ---

async function refreshTelegrafMetrics() {
    try {
        const d = await fetchJSON("/api/dashboard/telegraf-metrics");

        lastOpcuaCount = d.opcua_gathered;
        if (d.nodes_configured !== undefined) nodesConfigured = d.nodes_configured;
        if (d.any_input_active !== undefined) {
            anyInputActive = d.any_input_active;
            updatePipelineStatus();
        }

        // OPC UA input node
        setText("p-opcua-read", formatNum(d.opcua_gathered));

        // Aggregator node (only rendered in grouped mode)
        const aggEl = document.getElementById("p-agg-grouped");
        if (aggEl) {
            aggEl.textContent = (nodesConfigured > 0 && d.opcua_gathered > 0)
                ? formatNum(Math.round(d.opcua_gathered / nodesConfigured))
                : "--";
        }

        // Modbus input node
        setText("p-modbus-read", formatNum(d.modbus_gathered));
        setText("p-modbus-errors", formatNum(d.modbus_errors));
        setText("p-modbus-scan", `${d.modbus_scan_time_ms} ms`);
        setText("p-modbus-scan-stat", `${d.modbus_scan_time_ms} ms`);

        // MQTT output
        setText("p-mqtt-written", formatNum(d.mqtt_written));

        // Buffer
        const bufPct = d.mqtt_buffer_limit > 0 ? (d.mqtt_buffer_size / d.mqtt_buffer_limit) * 100 : 0;
        const bufFill = document.getElementById("p-buffer-fill");
        if (bufFill) {
            bufFill.style.width = `${bufPct}%`;
            bufFill.className = "pf-buffer-fill";
            if (bufPct > 80) bufFill.classList.add("danger");
            else if (bufPct > 50) bufFill.classList.add("warning");
        }
        setText("p-buffer-text", `${formatNum(d.mqtt_buffer_size)} / ${formatNum(d.mqtt_buffer_limit)}`);

        // OPC UA scan stat
        setText("p-scan-time", `${d.opcua_scan_time_ms} ms`);

        // OPC UA read quality (pipeline node chips)
        setText("q-read-success", formatNum(d.opcua_read_success));
        setText("q-read-error", formatNum(d.opcua_read_error));
        const total = d.opcua_read_success + d.opcua_read_error;
        const rate = total > 0 ? (d.opcua_read_success / total) * 100 : 0;
        setText("q-success-rate", total > 0 ? `${rate.toFixed(1)}%` : "--");

        // OPC UA metrics row
        setText("q2-read-success", formatNum(d.opcua_read_success));
        setText("q2-read-error", formatNum(d.opcua_read_error));
        setText("q2-success-rate", total > 0 ? `${rate.toFixed(1)}%` : "--");
        setDot("dot-read-error", d.opcua_read_error === 0);

        // Modbus metrics row
        setText("p-modbus-errors-stat", formatNum(d.modbus_errors));
        setDot("dot-modbus-errors", d.modbus_errors === 0);

        // Output metrics row
        const droppedEl = document.getElementById("p-dropped");
        if (droppedEl) {
            droppedEl.textContent = formatNum(d.mqtt_dropped);
            droppedEl.style.color = d.mqtt_dropped > 0 ? "var(--warning)" : "";
        }
        setDot("dot-dropped", d.mqtt_dropped === 0);

        const errorsEl = document.getElementById("p-errors");
        if (errorsEl) {
            errorsEl.textContent = formatNum(d.mqtt_errors);
            errorsEl.style.color = d.mqtt_errors > 0 ? "var(--danger)" : "";
        }
        setDot("dot-errors", d.mqtt_errors === 0);

        const lossEl = document.getElementById("p-loss");
        if (lossEl) {
            // In grouped mode OPC UA metrics are merged N→1, so use aggregator count
            const isGrouped = document.getElementById("p-agg-grouped") !== null;
            let opcuaIn = (isGrouped && nodesConfigured > 0)
                ? Math.round(d.opcua_gathered / nodesConfigured)
                : d.opcua_gathered;
            // The aggregator always keeps 1 batch buffered — subtract it to avoid false positives at startup
            if (isGrouped) opcuaIn = Math.max(0, opcuaIn - 1);
            const totalIn = opcuaIn + d.modbus_gathered;
            if (totalIn > 0 && d.mqtt_written > 0) {
                const loss = Math.max(0, ((totalIn - d.mqtt_written) / totalIn) * 100);
                lossEl.textContent = `${loss.toFixed(1)}%`;
                lossEl.style.color = loss > 0 ? "var(--danger)" : "var(--success)";
            } else {
                lossEl.textContent = "--";
                lossEl.style.color = "";
            }
        }

        if (d.last_updated) {
            setText("last-updated", new Date(d.last_updated * 1000).toISOString().replace("T", " ").slice(0, 19) + " UTC");
        }
    } catch (e) {}
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setDot(id, isOk) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = "stat-dot " + (isOk ? "dot-ok" : "dot-err");
}

function setWidth(id, val) {
    const el = document.getElementById(id);
    if (el) el.style.width = val;
}

function setPipelineState(state) {
    // state: "running" | "idle" | "stopped"
    const flow = document.getElementById("pipeline-flow");
    const dot = document.getElementById("pipeline-status-dot");
    const label = document.getElementById("pipeline-status-label");
    const badge = document.getElementById("pipeline-status-badge");
    if (!flow) return;

    flow.classList.remove("pipeline-active", "pipeline-stopped", "pipeline-idle");
    if (dot) dot.classList.remove("dot-running", "dot-idle");
    if (badge) badge.classList.remove("badge-running", "badge-stopped", "badge-idle");

    if (state === "running") {
        flow.classList.add("pipeline-active");
        if (dot) dot.classList.add("dot-running");
        if (label) label.textContent = "Running";
        if (badge) badge.classList.add("badge-running");
    } else if (state === "idle") {
        flow.classList.add("pipeline-idle");
        if (dot) dot.classList.add("dot-idle");
        if (label) label.textContent = "Idle";
        if (badge) badge.classList.add("badge-idle");
    } else {
        flow.classList.add("pipeline-stopped");
        if (label) label.textContent = "Stopped";
        if (badge) badge.classList.add("badge-stopped");
    }
}

// --- Gateway Info ---

async function refreshGatewayInfo() {
    try {
        const d = await fetchJSON("/api/dashboard/gateway-info");

        nodesConfigured = d.nodes_configured || 0;

        setText("g-telegraf-uptime",
            d.telegraf_uptime_seconds != null ? formatDuration(d.telegraf_uptime_seconds) : "--"
        );

        const lastConfig = document.getElementById("g-last-config");
        if (lastConfig) {
            lastConfig.textContent = d.last_config_applied
                ? new Date(d.last_config_applied).toISOString().replace("T", " ").slice(0, 19) + " UTC"
                : "Never";
        }

        const lastRestart = document.getElementById("g-last-restart");
        if (lastRestart) {
            const r = d.last_restart;
            if (r && r.started_at) {
                const ts = new Date(r.started_at).toISOString().replace("T", " ").slice(0, 19) + " UTC";
                const badges = {
                    deploy:    { label: "Deploy",      cls: "restart-deploy" },
                    manual:    { label: "Manual",      cls: "restart-manual" },
                    unplanned: { label: "⚠ Unplanned", cls: "restart-unplanned" },
                    crash:     { label: "⚠ Crash",     cls: "restart-crash" },
                };
                const b = badges[r.reason] || { label: r.reason, cls: "restart-manual" };
                lastRestart.innerHTML = `${ts} <span class="restart-badge ${b.cls}">${b.label}</span>`;
            } else {
                lastRestart.textContent = "--";
            }
        }

        const list = document.getElementById("g-containers");
        if (d.containers && d.containers.length > 0) {
            list.innerHTML = d.containers.map(c => {
                const isRunning = c.status === "running";
                const label = c.status.charAt(0).toUpperCase() + c.status.slice(1);
                const btn = c.is_demo
                    ? `<button class="btn btn-xs demo-toggle-btn ms-auto"
                           data-service="${c.service}"
                           data-action="${isRunning ? "stop" : "start"}"
                           title="${isRunning ? "Stop" : "Start"} demo">
                           ${isRunning ? "⏹" : "▶"}
                       </button>`
                    : "";
                return `<div class="container-status-item d-flex align-items-center">
                    <span class="status-dot ${isRunning ? "online" : "offline"}"></span>
                    <span class="container-name">${c.name}</span>
                    <span class="container-state ${isRunning ? "" : "text-danger"} me-auto">${label}</span>
                    ${btn}
                </div>`;
            }).join("");
        } else {
            list.innerHTML = '<span class="text-muted" style="font-size:0.75rem;">No containers found</span>';
        }
    } catch (e) {}
}

// --- Y-fork merge bar positioning ---

function positionForkBar() {
    const opcuaNode = document.getElementById("pf-opcua");
    const modbusNode = document.getElementById("pf-modbus");
    const vbarWrap = document.getElementById("pf-y-vbar-wrap");
    const vbar = document.getElementById("pf-y-vbar");
    if (!opcuaNode || !modbusNode || !vbarWrap || !vbar) return;

    const wrapRect = vbarWrap.getBoundingClientRect();
    const opcuaRect = opcuaNode.getBoundingClientRect();
    const modbusRect = modbusNode.getBoundingClientRect();

    const topY = opcuaRect.top + opcuaRect.height / 2 - wrapRect.top;
    const botY = modbusRect.top + modbusRect.height / 2 - wrapRect.top;

    vbar.style.top = topY + "px";
    vbar.style.height = (botY - topY) + "px";
}

// --- Helpers ---

function formatNum(n) {
    if (n === null || n === undefined) return "--";
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "K";
    return n.toLocaleString();
}

function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + " " + units[i];
}

function formatDuration(seconds) {
    if (!seconds || seconds < 0) return "--";
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}
