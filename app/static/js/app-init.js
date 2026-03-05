// Base layout event wiring — runs on every page

document.addEventListener("DOMContentLoaded", () => {
    // --- Theme switcher ---
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

    // --- Agent play/stop buttons ---
    const playBtn = document.getElementById("btn-agent-play");
    const stopBtn = document.getElementById("btn-agent-stop");
    if (playBtn && stopBtn) {
        playBtn.addEventListener("click", startAgent);
        stopBtn.addEventListener("click", stopAgent);
        fetchJSON("/api/telegraf/status").then(data => {
            if (data.ok) setAgentUI(data.running);
        });
    }

    // --- Logs modal ---
    let activeLogsTab = "gateway";

    function switchLogsTab(tab) {
        activeLogsTab = tab;
        document.querySelectorAll("[data-logs-tab]").forEach(b => b.classList.toggle("active", b.dataset.logsTab === tab));
        document.getElementById("logs-panel-gateway").style.display = tab === "gateway" ? "" : "none";
        document.getElementById("logs-panel-telegraf").style.display = tab === "telegraf" ? "" : "none";
        if (tab === "telegraf") loadTelegrafLogs();
    }

    const logsBtn = document.getElementById("btn-open-logs");
    if (logsBtn) {
        logsBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            sessionStorage.setItem("logsLastSeen", new Date().toISOString());
            const badge = document.getElementById("logs-error-badge");
            if (badge) badge.classList.add("d-none");
            const events = await fetchJSON("/api/logs");
            renderLogs(Array.isArray(events) ? events : []);
            switchLogsTab("gateway");
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

    document.querySelectorAll("[data-logs-tab]").forEach(btn => {
        btn.addEventListener("click", () => switchLogsTab(btn.dataset.logsTab));
    });

    // --- Error badge polling (every 30s) ---
    pollLogBadge();
    setInterval(pollLogBadge, 30000);

    // --- Preview config ---
    document.querySelectorAll('[data-action="preview-config"]').forEach(el => {
        el.addEventListener("click", async (e) => {
            e.preventDefault();
            const data = await fetchJSON("/api/telegraf/preview");
            document.getElementById("config-preview-content").textContent = data.config || "";
            new bootstrap.Modal(document.getElementById("configPreviewModal")).show();
        });
    });

    // --- Deploy config (sidebar button) ---
    document.querySelectorAll('[data-action="generate-config"]').forEach(el => {
        el.addEventListener("click", async (e) => {
            e.preventDefault();
            await applyConfig(el);
        });
    });

    // --- Apply from preview modal ---
    const applyBtn = document.getElementById("btn-apply-from-preview");
    if (applyBtn) {
        applyBtn.addEventListener("click", async () => {
            await applyConfig(applyBtn);
            bootstrap.Modal.getInstance(document.getElementById("configPreviewModal")).hide();
        });
    }
});
