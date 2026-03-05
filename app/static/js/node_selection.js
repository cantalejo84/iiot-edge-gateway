// Node Selection - Acquisition mode config + node table + message format

let nodes = [];
let saveTimeout = null;
let acqTimeout = null;
let publishingTimeout = null;

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));

    loadNodes();
    loadAcquisition();
    loadPublishing();

    document.getElementById("btn-clear-all").addEventListener("click", () => {
        if (confirm("Remove all selected nodes?")) {
            nodes = [];
            renderTable();
            saveNodes();
        }
    });

    // Acquisition mode toggle
    document.querySelectorAll(".acq-mode-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            setAcqMode(btn.dataset.mode);
            scheduleAcqSave();
        });
    });

    // Acquisition fields — auto-save on change
    ["acq-scan-rate", "acq-sampling-interval", "acq-queue-size", "acq-trigger", "acq-deadband-type", "acq-deadband-value"]
        .forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener("input", scheduleAcqSave);
                el.addEventListener("change", scheduleAcqSave);
            }
        });

    // Deadband type controls value field visibility
    document.getElementById("acq-deadband-type").addEventListener("change", updateDeadbandValueVisibility);

    // Publishing mode radios
    document.querySelectorAll("input[name='publishing_mode']").forEach(radio => {
        radio.addEventListener("change", schedulePublishingSave);
    });
});

// ── Acquisition Mode ─────────────────────────────────────────────

function setAcqMode(mode) {
    document.querySelectorAll(".acq-mode-btn").forEach(btn => {
        btn.classList.toggle("btn-primary", btn.dataset.mode === mode);
        btn.classList.toggle("btn-outline-secondary", btn.dataset.mode !== mode);
    });
    document.getElementById("acq-polling-section").style.display = mode === "polling" ? "" : "none";
    document.getElementById("acq-subscription-section").style.display = mode === "subscription" ? "" : "none";
}

function updateDeadbandValueVisibility() {
    const type = document.getElementById("acq-deadband-type").value;
    document.getElementById("acq-deadband-value-col").style.display = type === "None" ? "none" : "";
}

async function loadAcquisition() {
    const d = await fetchJSON("/api/opcua/acquisition");
    const mode = d.mode || "polling";

    setAcqMode(mode);

    const scanRate = document.getElementById("acq-scan-rate");
    if (scanRate) scanRate.value = d.scan_rate || "10s";

    const samplingInterval = document.getElementById("acq-sampling-interval");
    if (samplingInterval) samplingInterval.value = d.sampling_interval || "1s";

    const queueSize = document.getElementById("acq-queue-size");
    if (queueSize) queueSize.value = d.queue_size ?? 10;

    const trigger = document.getElementById("acq-trigger");
    if (trigger) trigger.value = d.trigger || "StatusValue";

    const deadbandType = document.getElementById("acq-deadband-type");
    if (deadbandType) deadbandType.value = d.deadband_type || "None";

    const deadbandValue = document.getElementById("acq-deadband-value");
    if (deadbandValue) deadbandValue.value = d.deadband_value ?? 0;

    updateDeadbandValueVisibility();
}

function getAcqData() {
    const mode = document.querySelector(".acq-mode-btn.btn-primary")?.dataset.mode || "polling";
    return {
        mode,
        scan_rate: document.getElementById("acq-scan-rate")?.value.trim() || "10s",
        sampling_interval: document.getElementById("acq-sampling-interval")?.value.trim() || "1s",
        queue_size: parseInt(document.getElementById("acq-queue-size")?.value) || 10,
        trigger: document.getElementById("acq-trigger")?.value || "StatusValue",
        deadband_type: document.getElementById("acq-deadband-type")?.value || "None",
        deadband_value: parseFloat(document.getElementById("acq-deadband-value")?.value) || 0,
    };
}

function scheduleAcqSave() {
    const indicator = document.getElementById("acq-save-indicator");
    if (indicator) indicator.textContent = "Unsaved changes...";
    clearTimeout(acqTimeout);
    acqTimeout = setTimeout(saveAcquisition, 800);
}

async function saveAcquisition() {
    const indicator = document.getElementById("acq-save-indicator");
    if (indicator) indicator.textContent = "Saving...";
    const data = await fetchJSON("/api/opcua/acquisition", { method: "POST", body: getAcqData() });
    if (data.ok) {
        updateConfigStatus(true);
        if (indicator) {
            indicator.textContent = "Saved";
            setTimeout(() => { indicator.textContent = ""; }, 2000);
        }
    }
}

// ── Nodes ────────────────────────────────────────────────────────

async function loadNodes() {
    const data = await fetchJSON("/api/opcua/nodes");
    nodes = Array.isArray(data) ? data : [];
    renderTable();
}

function renderTable() {
    const tbody = document.getElementById("nodes-tbody");
    const table = document.getElementById("nodes-table");
    const empty = document.getElementById("nodes-empty");
    const count = document.getElementById("node-count");

    count.textContent = nodes.length;

    if (nodes.length === 0) {
        table.style.display = "none";
        empty.style.display = "block";
        return;
    }

    table.style.display = "table";
    empty.style.display = "none";
    tbody.innerHTML = "";

    nodes.forEach((node, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><input type="text" class="form-control form-control-sm" value="${esc(node.name)}" data-idx="${idx}" data-field="name"></td>
            <td>${esc(node.namespace)}</td>
            <td><code>${esc(node.identifier)}</code></td>
            <td>${esc(node.identifier_type)}</td>
            <td>
                <button class="btn btn-sm btn-outline-secondary" data-remove="${idx}" title="Remove">
                    <i class="bi bi-x"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Name edit auto-save
    tbody.querySelectorAll("[data-field='name']").forEach(el => {
        el.addEventListener("change", () => {
            nodes[parseInt(el.dataset.idx)].name = el.value;
            scheduleAutoSave();
        });
    });

    // Remove buttons
    tbody.querySelectorAll("[data-remove]").forEach(btn => {
        btn.addEventListener("click", () => {
            nodes.splice(parseInt(btn.dataset.remove), 1);
            renderTable();
            saveNodes();
        });
    });
}

function scheduleAutoSave() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveNodes, 800);
}

async function saveNodes() {
    const data = await fetchJSON("/api/opcua/nodes", { method: "POST", body: nodes });
    if (data.ok) updateConfigStatus(true);
}

// ── Publishing ───────────────────────────────────────────────────

async function loadPublishing() {
    const data = await fetchJSON("/api/opcua/publishing");
    const mode = data.mode || "individual";
    const radio = document.querySelector(`input[name='publishing_mode'][value='${mode}']`);
    if (radio) radio.checked = true;
}

function schedulePublishingSave() {
    clearTimeout(publishingTimeout);
    publishingTimeout = setTimeout(savePublishing, 800);
}

async function savePublishing() {
    const mode = document.querySelector("input[name='publishing_mode']:checked")?.value || "individual";
    const data = await fetchJSON("/api/opcua/publishing", { method: "POST", body: { mode } });
    if (data.ok) updateConfigStatus(true);
}

// ── Helpers ──────────────────────────────────────────────────────

function esc(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
}
