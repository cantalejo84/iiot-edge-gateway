// Node Selection - Table management with per-node config + auto-save

let nodes = [];
let saveTimeout = null;

document.addEventListener("DOMContentLoaded", () => {
    loadNodes();

    document.getElementById("btn-clear-all").addEventListener("click", () => {
        if (confirm("Remove all selected nodes?")) {
            nodes = [];
            renderTable();
            saveNodes();
        }
    });
});

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
                <select class="form-select form-select-sm" data-idx="${idx}" data-field="sampling_mode">
                    <option value="polling" ${node.sampling_mode === "polling" ? "selected" : ""}>Polling</option>
                    <option value="subscription" ${node.sampling_mode === "subscription" ? "selected" : ""}>Subscription</option>
                </select>
            </td>
            <td><input type="text" class="form-control form-control-sm" value="${esc(node.interval || '1s')}" data-idx="${idx}" data-field="interval" style="width:5rem;"></td>
            <td>
                <div class="d-flex gap-1">
                    <select class="form-select form-select-sm" data-idx="${idx}" data-field="deadband_type" style="width:6rem;">
                        <option value="None" ${node.deadband_type === "None" ? "selected" : ""}>None</option>
                        <option value="Absolute" ${node.deadband_type === "Absolute" ? "selected" : ""}>Absolute</option>
                        <option value="Percent" ${node.deadband_type === "Percent" ? "selected" : ""}>Percent</option>
                    </select>
                    <input type="number" class="form-control form-control-sm" value="${node.deadband_value || 0}" data-idx="${idx}" data-field="deadband_value" style="width:4rem;" step="0.1">
                </div>
            </td>
            <td>
                <button class="btn btn-sm btn-outline-danger" data-remove="${idx}" title="Remove">
                    <i class="bi bi-x"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Bind change events with auto-save
    tbody.querySelectorAll("[data-field]").forEach(el => {
        el.addEventListener("change", () => {
            const idx = parseInt(el.dataset.idx);
            const field = el.dataset.field;
            let value = el.value;
            if (field === "deadband_value") value = parseFloat(value) || 0;
            nodes[idx][field] = value;
            scheduleAutoSave();
        });
    });

    // Bind remove buttons
    tbody.querySelectorAll("[data-remove]").forEach(btn => {
        btn.addEventListener("click", () => {
            const idx = parseInt(btn.dataset.remove);
            nodes.splice(idx, 1);
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
    if (data.ok) {
        updateConfigStatus(true);
    }
}

function esc(str) {
    const div = document.createElement("div");
    div.textContent = str || "";
    return div.innerHTML;
}
