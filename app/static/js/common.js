// Shared utilities for IIoT Edge Gateway

async function fetchJSON(url, options = {}) {
    const defaults = {
        headers: { "Content-Type": "application/json" },
    };
    if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
        options.body = JSON.stringify(options.body);
    }
    if (options.body instanceof FormData) {
        delete defaults.headers["Content-Type"];
    }
    const resp = await fetch(url, { ...defaults, ...options });
    return resp.json();
}

function showAlert(message, type = "success") {
    const container = document.getElementById("alert-container");
    if (!container) return;
    const alert = document.createElement("div");
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    container.prepend(alert);
    setTimeout(() => alert.remove(), 5000);
}

function updateConfigStatus(isDirty) {
    const el = document.getElementById("config-status");
    if (!el) return;
    if (isDirty) {
        el.innerHTML = '<span class="badge-status badge-dirty"><i class="bi bi-exclamation-circle"></i> Unapplied changes</span>';
    } else {
        el.innerHTML = '<span class="badge-status badge-clean"><i class="bi bi-check-circle"></i> Config synced</span>';
    }
}

function setLoading(btn, loading) {
    if (loading) {
        btn.dataset.originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span>';
    } else {
        btn.disabled = false;
        btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
    }
}

function lockNav() {
    document.querySelectorAll(".sidebar .nav-link, .sidebar a").forEach(el => {
        el.dataset.hrefBackup = el.getAttribute("href") || "";
        el.setAttribute("href", "#");
        el.classList.add("nav-locked");
    });
}

function unlockNav() {
    document.querySelectorAll(".sidebar .nav-link, .sidebar a").forEach(el => {
        if (el.dataset.hrefBackup !== undefined) {
            el.setAttribute("href", el.dataset.hrefBackup);
            delete el.dataset.hrefBackup;
        }
        el.classList.remove("nav-locked");
    });
}

async function applyConfig(btn) {
    setLoading(btn, true);
    lockNav();

    const data = await fetchJSON("/api/telegraf/generate", { method: "POST" });

    setLoading(btn, false);
    unlockNav();

    if (data.ok) {
        const restartOk = data.restart && data.restart.ok;
        if (restartOk) {
            showAlert("Config applied and Telegraf restarted successfully.", "success");
        } else {
            const err = data.restart ? data.restart.error : "unknown";
            showAlert(`Config generated but Telegraf restart failed: ${err}`, "warning");
        }
        updateConfigStatus(false);
    } else {
        showAlert("Failed to generate config.", "danger");
    }
}

// --- Telegraf Agent State ---

function setAgentUI(running) {
    const playBtn = document.getElementById("btn-agent-play");
    const stopBtn = document.getElementById("btn-agent-stop");
    const dot = document.getElementById("agent-status-dot");
    const text = document.getElementById("agent-status-text");
    if (!playBtn || !stopBtn) return;
    if (running) {
        playBtn.classList.add("btn-state-active");
        stopBtn.classList.remove("btn-state-active");
        if (dot) { dot.classList.add("agent-dot-running"); dot.classList.remove("agent-dot-stopped"); }
        if (text) text.textContent = "Running";
    } else {
        playBtn.classList.remove("btn-state-active");
        stopBtn.classList.add("btn-state-active");
        if (dot) { dot.classList.add("agent-dot-stopped"); dot.classList.remove("agent-dot-running"); }
        if (text) text.textContent = "Stopped";
    }
}

async function startAgent() {
    const btn = document.getElementById("btn-agent-play");
    setLoading(btn, true);
    lockNav();
    const result = await fetchJSON("/api/telegraf/start", { method: "POST" });
    setLoading(btn, false);
    unlockNav();
    if (result.ok) {
        setAgentUI(true);
    } else {
        showAlert("Failed to start agent: " + (result.error || "unknown error"), "danger");
    }
}

async function stopAgent() {
    const btn = document.getElementById("btn-agent-stop");
    setLoading(btn, true);
    lockNav();
    const result = await fetchJSON("/api/telegraf/stop", { method: "POST" });
    setLoading(btn, false);
    unlockNav();
    if (result.ok) {
        setAgentUI(false);
    } else {
        showAlert("Failed to stop agent: " + (result.error || "unknown error"), "danger");
    }
}

// --- Logs Modal ---

function renderLogs(events) {
    const list = document.getElementById("logs-list");
    const empty = document.getElementById("logs-empty");
    if (!list) return;

    if (!events || events.length === 0) {
        list.innerHTML = "";
        if (empty) empty.style.display = "";
        return;
    }

    if (empty) empty.style.display = "none";

    const levelIcon = { error: "bi-x-circle-fill", warning: "bi-exclamation-triangle-fill", info: "bi-info-circle-fill" };
    const levelColor = { error: "var(--danger)", warning: "var(--warning)", info: "var(--accent)" };
    const compColor = { opcua: "#a78bfa", mqtt: "#34d399", telegraf: "#fb923c", system: "#94a3b8" };

    list.innerHTML = events.map(e => {
        const timestamp = new Date(e.ts).toISOString();
        const icon = levelIcon[e.level] || "bi-circle";
        const color = levelColor[e.level] || "var(--text-secondary)";
        const compClr = compColor[e.component] || "#94a3b8";
        const detail = e.detail
            ? `<div class="log-detail">${escapeLogHtml(e.detail)}</div>`
            : "";
        return `
        <div class="log-entry log-${e.level}">
            <div class="log-entry-header">
                <i class="bi ${icon}" style="color:${color};flex-shrink:0;"></i>
                <span class="log-comp-badge" style="background:${compClr}22;color:${compClr};border-color:${compClr}44;">${e.component.toUpperCase()}</span>
                <span class="log-message">${escapeLogHtml(e.message)}</span>
                <span class="log-time">${timestamp}</span>
            </div>
            ${detail}
        </div>`;
    }).join("");

}

function updateLogBadge(events) {
    const modal = document.getElementById("logsModal");
    const isOpen = modal && modal.classList.contains("show");
    if (isOpen) return;

    const lastSeen = sessionStorage.getItem("logsLastSeen");
    const unseen = (events || []).filter(e =>
        e.level === "error" && (!lastSeen || e.ts > lastSeen)
    );
    const badge = document.getElementById("logs-error-badge");
    if (!badge) return;
    if (unseen.length > 0) {
        badge.textContent = unseen.length;
        badge.classList.remove("d-none");
    } else {
        badge.classList.add("d-none");
    }
}

function escapeLogHtml(str) {
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
}

// --- Theme switcher ---

function applyTheme(theme) {
    const root = document.getElementById("app-root");
    if (!root) return;
    if (theme === "keepler") {
        root.setAttribute("data-theme", "keepler");
        root.setAttribute("data-bs-theme", "light");
    } else {
        root.removeAttribute("data-theme");
        root.setAttribute("data-bs-theme", "dark");
    }
}

(function initTheme() {
    const saved = localStorage.getItem("iiot-theme") || "default";
    applyTheme(saved);
})();

// Config preview and apply actions
document.addEventListener("DOMContentLoaded", () => {
    // Theme switcher
    function updateThemeButtons(theme) {
        document.querySelectorAll(".theme-option").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.themeValue === theme);
        });
    }
    document.querySelectorAll(".theme-option").forEach(btn => {
        btn.addEventListener("click", () => {
            const theme = btn.dataset.themeValue;
            applyTheme(theme);
            localStorage.setItem("iiot-theme", theme);
            updateThemeButtons(theme);
        });
    });
    const savedTheme = localStorage.getItem("iiot-theme") || "default";
    updateThemeButtons(savedTheme);
    // Agent play/stop buttons
    const playBtn = document.getElementById("btn-agent-play");
    const stopBtn = document.getElementById("btn-agent-stop");
    if (playBtn && stopBtn) {
        playBtn.addEventListener("click", startAgent);
        stopBtn.addEventListener("click", stopAgent);
        fetchJSON("/api/telegraf/status").then(data => {
            if (data.ok) setAgentUI(data.running);
        }).catch(() => {});
    }
    // Logs modal
    const logsBtn = document.getElementById("btn-open-logs");
    if (logsBtn) {
        logsBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            // Mark all current logs as seen
            sessionStorage.setItem("logsLastSeen", new Date().toISOString());
            const badge = document.getElementById("logs-error-badge");
            if (badge) badge.classList.add("d-none");
            const events = await fetchJSON("/api/logs");
            renderLogs(events);
            new bootstrap.Modal(document.getElementById("logsModal")).show();
        });
    }
    const clearLogsBtn = document.getElementById("btn-clear-logs");
    if (clearLogsBtn) {
        clearLogsBtn.addEventListener("click", async () => {
            await fetchJSON("/api/logs/clear", { method: "POST" });
            renderLogs([]);
        });
    }

    // Poll error badge every 30s (lightweight: just a count check)
    async function pollLogBadge() {
        try {
            const events = await fetchJSON("/api/logs");
            updateLogBadge(events);
        } catch (e) {}
    }
    pollLogBadge();
    setInterval(pollLogBadge, 30000);

    // Preview config
    document.querySelectorAll('[data-action="preview-config"]').forEach(el => {
        el.addEventListener("click", async (e) => {
            e.preventDefault();
            const data = await fetchJSON("/api/telegraf/preview");
            document.getElementById("config-preview-content").textContent = data.config;
            new bootstrap.Modal(document.getElementById("configPreviewModal")).show();
        });
    });

    // Apply config (sidebar button)
    document.querySelectorAll('[data-action="generate-config"]').forEach(el => {
        el.addEventListener("click", async (e) => {
            e.preventDefault();
            await applyConfig(el);
        });
    });

    // Apply from preview modal
    const applyBtn = document.getElementById("btn-apply-from-preview");
    if (applyBtn) {
        applyBtn.addEventListener("click", async () => {
            await applyConfig(applyBtn);
            bootstrap.Modal.getInstance(document.getElementById("configPreviewModal")).hide();
        });
    }
});
