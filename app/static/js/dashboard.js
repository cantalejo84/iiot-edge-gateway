// Dashboard - auto-refresh system health and telegraf metrics

document.addEventListener("DOMContentLoaded", () => {
    refreshAll();
    setInterval(refreshAll, 5000);
});

async function refreshAll() {
    await Promise.all([
        refreshHealth(),
        refreshTelegrafStatus(),
        refreshTelegrafMetrics(),
    ]);
}

async function refreshHealth() {
    try {
        const data = await fetchJSON("/api/dashboard/health");
        updateMetric("cpu", data.cpu_percent);
        updateMetric("ram", data.memory_percent);
        updateMetric("disk", data.disk_percent);
    } catch (e) {
        // Silently fail on dashboard refresh
    }
}

function updateMetric(id, value) {
    const valueEl = document.getElementById(`${id}-value`);
    const barEl = document.getElementById(`${id}-bar`);
    if (!valueEl || !barEl) return;

    valueEl.textContent = `${Math.round(value)}%`;
    barEl.style.width = `${value}%`;

    // Color coding
    barEl.className = "progress-bar";
    if (value > 90) barEl.classList.add("bg-danger");
    else if (value > 70) barEl.classList.add("bg-warning");
    else barEl.classList.add("bg-success");
}

async function refreshTelegrafStatus() {
    try {
        const data = await fetchJSON("/api/dashboard/telegraf-status");
        const dot = document.getElementById("telegraf-dot");
        const badge = document.getElementById("telegraf-badge");

        if (data.running) {
            dot.className = "status-dot online";
            badge.className = "badge text-bg-success";
            badge.textContent = "Running";
        } else {
            dot.className = "status-dot offline";
            badge.className = "badge text-bg-danger";
            badge.textContent = "Stopped";
        }
    } catch (e) {
        // Silently fail
    }
}

async function refreshTelegrafMetrics() {
    try {
        const data = await fetchJSON("/api/dashboard/telegraf-metrics");
        document.getElementById("opcua-gathered").textContent = formatNumber(data.opcua_gathered);
        document.getElementById("mqtt-written").textContent = formatNumber(data.mqtt_written);
        document.getElementById("mqtt-dropped").textContent = formatNumber(data.mqtt_dropped);
        document.getElementById("opcua-errors").textContent = formatNumber(data.opcua_errors);

        const lastUpdated = document.getElementById("last-updated");
        if (data.last_updated) {
            const d = new Date(data.last_updated * 1000 || data.last_updated);
            lastUpdated.textContent = d.toLocaleTimeString();
        } else {
            lastUpdated.textContent = "No data";
        }
    } catch (e) {
        // Silently fail
    }
}

function formatNumber(n) {
    if (n === null || n === undefined) return "--";
    if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(1) + "K";
    return String(n);
}
