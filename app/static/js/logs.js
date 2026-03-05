// Logs rendering, badge management, and Telegraf log fetching

function escapeLogHtml(str) {
    const d = document.createElement("div");
    d.textContent = String(str);
    return d.innerHTML;
}

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

    list.innerHTML = [...events].reverse().map(e => {
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
                <button class="log-copy-btn" title="Copy to clipboard" data-copy="${escapeLogHtml(e.component.toUpperCase() + ' | ' + timestamp + ' | ' + e.message + (e.detail ? ' | ' + e.detail : ''))}">
                    <i class="bi bi-clipboard"></i>
                </button>
            </div>
            ${detail}
        </div>`;
    }).join("");

    const scrollable = list.closest(".modal-body") || list.parentElement;
    if (scrollable) scrollable.scrollTop = scrollable.scrollHeight;

    list.querySelectorAll(".log-copy-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            navigator.clipboard.writeText(btn.dataset.copy || "").catch(() => {});
            const icon = btn.querySelector("i");
            if (icon) { icon.className = "bi bi-clipboard-check"; }
            setTimeout(() => { if (icon) icon.className = "bi bi-clipboard"; }, 1500);
        });
    });
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

async function loadTelegrafLogs() {
    const container = document.getElementById("telegraf-logs-content");
    if (!container) return;
    const data = await fetchJSON("/api/telegraf/logs");
    if (!data.ok || !data.lines || data.lines.length === 0) {
        container.innerHTML = '<div class="logs-empty"><i class="bi bi-terminal" style="font-size:1.5rem;opacity:0.3;"></i><div>No Telegraf logs available</div></div>';
        return;
    }
    container.innerHTML = data.lines.map(line => {
        let cls = "tlog-info";
        if (line.includes(" E! ")) cls = "tlog-error";
        else if (line.includes(" W! ")) cls = "tlog-warn";
        return `<div class="tlog-line ${cls}">${escapeLogHtml(line)}</div>`;
    }).join("");
    container.scrollTop = container.scrollHeight;
}

async function pollLogBadge() {
    const events = await fetchJSON("/api/logs");
    if (events && !events.error) updateLogBadge(events);
}
