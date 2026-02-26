// MQTT View Messages — live tail with UTC timestamps + clear

let tailInterval = null;
let tailAutoStopTimeout = null;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btn-tail-toggle").addEventListener("click", toggleTail);
    document.getElementById("btn-clear-messages").addEventListener("click", clearMessages);
    checkTailStatus();
});

// --- Init ---

async function checkTailStatus() {
    try {
        const data = await fetchJSON("/api/mqtt/tail");
        if (data.running) {
            setTailUI(true, data.topic);
            startPolling();
            renderMessages(data.messages);
        }
    } catch (e) {}
}

// --- Toggle ---

async function toggleTail() {
    const btn = document.getElementById("btn-tail-toggle");
    setLoading(btn, true);

    if (tailInterval) {
        await fetchJSON("/api/mqtt/tail/stop", { method: "POST" });
        setLoading(btn, false);
        stopTail();
    } else {
        const result = await fetchJSON("/api/mqtt/tail/start", { method: "POST" });
        if (result.ok) {
            const status = await fetchJSON("/api/mqtt/tail");
            setLoading(btn, false);
            setTailUI(true, status.topic);
            startPolling();
            // Auto-stop after 5 minutes
            tailAutoStopTimeout = setTimeout(async () => {
                await fetchJSON("/api/mqtt/tail/stop", { method: "POST" });
                stopTail();
            }, 300000);
        } else {
            setLoading(btn, false);
            showAlert("Failed to start: " + result.error, "danger");
        }
    }
}

function stopTail() {
    stopPolling();
    setTailUI(false);
    clearTimeout(tailAutoStopTimeout);
    tailAutoStopTimeout = null;
}

// --- UI ---

function setTailUI(running, topic) {
    const btn = document.getElementById("btn-tail-toggle");
    const statusEl = document.getElementById("tail-status");
    const topicEl = document.getElementById("tail-topic");
    const empty = document.getElementById("tail-empty");

    if (running) {
        btn.innerHTML = '<i class="bi bi-stop-fill"></i> Stop';
        statusEl.textContent = "Listening...";
        if (topic) {
            topicEl.textContent = topic;
            topicEl.style.display = "";
        }
    } else {
        btn.innerHTML = '<i class="bi bi-play-fill"></i> Start';
        statusEl.textContent = "";
        topicEl.style.display = "none";
        if (document.getElementById("tail-messages").children.length === 0) {
            empty.style.display = "";
        }
    }
}

// --- Polling ---

function startPolling() {
    if (tailInterval) return;
    tailInterval = setInterval(pollTail, 2000);
    pollTail();
}

function stopPolling() {
    clearInterval(tailInterval);
    tailInterval = null;
}

async function pollTail() {
    try {
        const data = await fetchJSON("/api/mqtt/tail");
        if (!data.running && tailInterval) { stopTail(); return; }
        renderMessages(data.messages);
    } catch (e) {}
}

// --- Render ---

function renderMessages(messages) {
    const container = document.getElementById("tail-messages");
    const empty = document.getElementById("tail-empty");
    if (!messages || messages.length === 0) return;
    empty.style.display = "none";
    container.innerHTML = "";
    messages.forEach((msg, i) => {
        // UTC timestamp like logs
        const utcTime = new Date(msg.timestamp).toISOString();
        let payload = msg.payload;
        try { payload = JSON.stringify(JSON.parse(msg.payload), null, 2); } catch (e) {}
        const div = document.createElement("div");
        div.className = "tail-message";
        div.innerHTML = `
            <div class="tail-message-header">
                <span class="tail-time">${utcTime}</span>
                <span class="tail-topic">${escapeHtml(msg.topic)}</span>
            </div>
            <pre class="tail-payload mb-0">${escapeHtml(payload)}</pre>
            <button class="btn-copy-payload" onclick="copyPayload(${i})" title="Copy payload">
                <i class="bi bi-clipboard"></i>
            </button>`;
        div.dataset.payload = msg.payload;
        container.appendChild(div);
    });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// --- Clear ---

async function clearMessages() {
    await fetchJSON("/api/mqtt/messages/clear", { method: "POST" });
    document.getElementById("tail-messages").innerHTML = "";
    document.getElementById("tail-empty").style.display = "";
}

// --- Copy payload ---

async function copyPayload(index) {
    const messages = document.querySelectorAll(".tail-message");
    if (!messages[index]) return;
    const payload = messages[index].dataset.payload;
    try {
        await navigator.clipboard.writeText(payload);
    } catch (e) {
        const ta = document.createElement("textarea");
        ta.value = payload;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
    }
    showAlert("Payload copied to clipboard.", "success");
}
