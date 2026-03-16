// Telegraf agent state control and config deploy

function setAgentUI(running, crashed = false) {
    const playBtn = document.getElementById("btn-agent-play");
    const stopBtn = document.getElementById("btn-agent-stop");
    const dot = document.getElementById("agent-status-dot");
    const text = document.getElementById("agent-status-text");
    if (!playBtn || !stopBtn) return;
    if (running) {
        playBtn.classList.add("btn-state-active");
        stopBtn.classList.remove("btn-state-active");
    } else {
        playBtn.classList.remove("btn-state-active");
        stopBtn.classList.add("btn-state-active");
    }
    if (dot) {
        dot.classList.remove("agent-dot-running", "agent-dot-stopped", "agent-dot-crashed");
        if (crashed)      dot.classList.add("agent-dot-crashed");
        else if (running) dot.classList.add("agent-dot-running");
        else              dot.classList.add("agent-dot-stopped");
    }
    if (text) text.textContent = crashed ? "Crashed" : (running ? "Running" : "Stopped");
}

async function startAgent() {
    const btn = document.getElementById("btn-agent-play");
    setLoading(btn, true);
    lockNav();
    lockMain("Starting Telegraf\u2026");
    const result = await fetchJSON("/api/telegraf/start", { method: "POST" });
    setLoading(btn, false);
    unlockNav();
    unlockMain();
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
    lockMain("Stopping Telegraf\u2026");
    const result = await fetchJSON("/api/telegraf/stop", { method: "POST" });
    setLoading(btn, false);
    unlockNav();
    unlockMain();
    if (result.ok) {
        setAgentUI(false);
    } else {
        showAlert("Failed to stop agent: " + (result.error || "unknown error"), "danger");
    }
}

async function applyConfig(btn) {
    setLoading(btn, true);
    lockNav();
    lockMain("Deploying config\u2026");

    const data = await fetchJSON("/api/telegraf/generate", { method: "POST" });

    setLoading(btn, false);
    unlockNav();
    unlockMain();

    if (data.ok) {
        const restartOk = data.restart && data.restart.ok;
        if (restartOk) {
            showAlert("Config applied and Telegraf restarted successfully.", "success");
            setAgentUI(true);
        } else {
            const err = data.restart ? data.restart.error : "unknown";
            showAlert(`Config generated but Telegraf restart failed: ${err}`, "warning");
        }
        updateConfigStatus(false);
    } else {
        showAlert("Failed to generate config.", "danger");
    }
}
