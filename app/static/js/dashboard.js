// Dashboard - auto-refresh pipeline, system health, quality metrics

let lastOpcuaCount = null;
let telegrafRunning = null;

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });
    refreshAll();
    setInterval(refreshAll, 5000);
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
        setPipelineActive(telegrafRunning === true);
    } catch (e) {}
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

        const opcuaCount = d.opcua_gathered;
        lastOpcuaCount = opcuaCount;

        // OPC UA node
        document.getElementById("p-opcua-read").textContent = formatNum(d.opcua_gathered);
        document.getElementById("p-mqtt-written").textContent = formatNum(d.mqtt_written);

        // Buffer
        const bufPct = d.mqtt_buffer_limit > 0 ? (d.mqtt_buffer_size / d.mqtt_buffer_limit) * 100 : 0;
        const bufFill = document.getElementById("p-buffer-fill");
        bufFill.style.width = `${bufPct}%`;
        bufFill.className = "pf-buffer-fill";
        if (bufPct > 80) bufFill.classList.add("danger");
        else if (bufPct > 50) bufFill.classList.add("warning");
        document.getElementById("p-buffer-text").textContent =
            `${formatNum(d.mqtt_buffer_size)} / ${formatNum(d.mqtt_buffer_limit)}`;

        // Stats
        document.getElementById("p-scan-time").textContent = `${d.scan_time_ms} ms`;

        const droppedEl = document.getElementById("p-dropped");
        droppedEl.textContent = formatNum(d.mqtt_dropped);
        droppedEl.style.color = d.mqtt_dropped > 0 ? "var(--warning)" : "";

        const errorsEl = document.getElementById("p-errors");
        const totalErrors = d.opcua_errors + d.mqtt_errors;
        errorsEl.textContent = `${d.opcua_errors} / ${d.mqtt_errors}`;
        errorsEl.style.color = totalErrors > 0 ? "var(--danger)" : "";

        const lossEl = document.getElementById("p-loss");
        if (d.opcua_gathered > 0) {
            const loss = Math.max(0, ((d.opcua_gathered - d.mqtt_written) / d.opcua_gathered) * 100);
            lossEl.textContent = `${loss.toFixed(1)}%`;
            lossEl.style.color = loss > 0 ? "var(--danger)" : "var(--success)";
        } else {
            lossEl.textContent = "--";
            lossEl.style.color = "";
        }

        // Read quality
        document.getElementById("q-read-success").textContent = formatNum(d.opcua_read_success);
        document.getElementById("q-read-error").textContent = formatNum(d.opcua_read_error);

        const total = d.opcua_read_success + d.opcua_read_error;
        const rate = total > 0 ? (d.opcua_read_success / total) * 100 : 0;
        document.getElementById("q-success-rate").textContent = total > 0 ? `${rate.toFixed(1)}%` : "--";
        document.getElementById("q-success-bar").style.width = `${rate}%`;
        document.getElementById("q-error-bar").style.width = `${total > 0 ? 100 - rate : 0}%`;

        if (d.last_updated) {
            document.getElementById("last-updated").textContent =
                new Date(d.last_updated * 1000).toLocaleTimeString();
        }
    } catch (e) {}
}

function setPipelineActive(active) {
    const flow = document.getElementById("pipeline-flow");
    const dot = document.getElementById("pipeline-status-dot");
    const label = document.getElementById("pipeline-status-label");
    const badge = document.getElementById("pipeline-status-badge");
    if (!flow) return;

    if (active) {
        flow.classList.add("pipeline-active");
        flow.classList.remove("pipeline-stopped");
        if (dot) dot.classList.add("dot-running");
        if (label) label.textContent = "Running";
        if (badge) { badge.classList.add("badge-running"); badge.classList.remove("badge-stopped"); }
    } else {
        flow.classList.remove("pipeline-active");
        flow.classList.add("pipeline-stopped");
        if (dot) dot.classList.remove("dot-running");
        if (label) label.textContent = "Stopped";
        if (badge) { badge.classList.remove("badge-running"); badge.classList.add("badge-stopped"); }
    }
}

// --- Gateway Info ---

async function refreshGatewayInfo() {
    try {
        const d = await fetchJSON("/api/dashboard/gateway-info");

        document.getElementById("g-uptime").textContent = formatDuration(d.uptime_seconds);
        document.getElementById("g-nodes").textContent = d.nodes_configured;

        const lastConfig = document.getElementById("g-last-config");
        if (d.last_config_applied) {
            lastConfig.textContent = new Date(d.last_config_applied).toLocaleString(undefined, {
                day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
            });
        } else {
            lastConfig.textContent = "Never";
        }

        const list = document.getElementById("g-containers");
        if (d.containers && d.containers.length > 0) {
            list.innerHTML = d.containers.map(c => {
                const isRunning = c.status === "running";
                const label = c.status.charAt(0).toUpperCase() + c.status.slice(1);
                return `<div class="container-status-item">
                    <span class="status-dot ${isRunning ? "online" : "offline"}"></span>
                    <span class="container-name">${c.name}</span>
                    <span class="container-state ${isRunning ? "" : "text-danger"}">${label}</span>
                </div>`;
            }).join("");
        } else {
            list.innerHTML = '<span class="text-muted" style="font-size:0.75rem;">No containers found</span>';
        }
    } catch (e) {}
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
