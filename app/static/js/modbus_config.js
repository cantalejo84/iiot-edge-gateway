// Modbus TCP Config — auto-save with debounce + register table

const REGISTER_TYPES = ["holding", "input", "coil", "discrete"];
const DATA_TYPES = ["UINT16", "INT16", "UINT32", "INT32", "FLOAT32", "FLOAT64", "BOOL"];
const BYTE_ORDERS = ["ABCD", "DCBA", "BADC", "CDAB"];

let saveTimer = null;
let registers = [];

// ── Init ──────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });

    const cfg = await fetchJSON("/api/modbus/config");
    registers = cfg.registers || [];
    renderTable();

    // Wire auto-save on connection fields
    ["modbus-controller", "modbus-slave-id", "modbus-timeout"].forEach(id => {
        document.getElementById(id).addEventListener("input", scheduleSave);
    });
    document.getElementById("modbus-enabled").addEventListener("change", scheduleSave);

    document.getElementById("btn-add-register").addEventListener("click", addRegister);
    document.getElementById("btn-test-connection").addEventListener("click", testConnection);
    document.getElementById("btn-demo-fill").addEventListener("click", fillDemo);
});

// ── Register table ────────────────────────────────────────────────────────────

function renderTable() {
    const tbody = document.getElementById("register-tbody");
    const empty = document.getElementById("register-empty");

    if (registers.length === 0) {
        tbody.innerHTML = "";
        empty.style.display = "";
        return;
    }
    empty.style.display = "none";

    tbody.innerHTML = registers.map((reg, i) => `
        <tr data-index="${i}">
            <td>
                <input type="text" class="form-control form-control-sm reg-name"
                    value="${esc(reg.name)}" placeholder="temperature">
            </td>
            <td>
                <select class="form-select form-select-sm reg-type">
                    ${REGISTER_TYPES.map(t =>
                        `<option value="${t}" ${t === reg.register_type ? "selected" : ""}>${t}</option>`
                    ).join("")}
                </select>
            </td>
            <td>
                <input type="number" class="form-control form-control-sm reg-address"
                    value="${reg.address}" min="0">
            </td>
            <td>
                <select class="form-select form-select-sm reg-data-type">
                    ${DATA_TYPES.map(t =>
                        `<option value="${t}" ${t === reg.data_type ? "selected" : ""}>${t}</option>`
                    ).join("")}
                </select>
            </td>
            <td>
                <select class="form-select form-select-sm reg-byte-order">
                    ${BYTE_ORDERS.map(o =>
                        `<option value="${o}" ${o === reg.byte_order ? "selected" : ""}>${o}</option>`
                    ).join("")}
                </select>
            </td>
            <td>
                <button class="btn btn-xs btn-outline-danger reg-delete" data-index="${i}" title="Remove">
                    <i class="bi bi-trash"></i>
                </button>
            </td>
        </tr>
    `).join("");

    // Wire row events
    tbody.querySelectorAll("input, select").forEach(el => {
        el.addEventListener("change", onRowChange);
        el.addEventListener("input", onRowChange);
    });
    tbody.querySelectorAll(".reg-delete").forEach(btn => {
        btn.addEventListener("click", e => {
            const idx = parseInt(e.currentTarget.dataset.index);
            registers.splice(idx, 1);
            renderTable();
            scheduleSave();
        });
    });
}

function onRowChange(e) {
    const tr = e.target.closest("tr");
    const i = parseInt(tr.dataset.index);
    registers[i] = {
        name: tr.querySelector(".reg-name").value.trim(),
        register_type: tr.querySelector(".reg-type").value,
        address: parseInt(tr.querySelector(".reg-address").value) || 0,
        data_type: tr.querySelector(".reg-data-type").value,
        byte_order: tr.querySelector(".reg-byte-order").value,
    };
    scheduleSave();
}

function addRegister() {
    registers.push({
        name: "",
        register_type: "holding",
        address: registers.length > 0 ? registers[registers.length - 1].address + 1 : 0,
        data_type: "FLOAT32",
        byte_order: "ABCD",
    });
    renderTable();
    // Focus the name field of the new row
    const rows = document.querySelectorAll("#register-tbody tr");
    if (rows.length > 0) {
        rows[rows.length - 1].querySelector(".reg-name").focus();
    }
    scheduleSave();
}

// ── Save ──────────────────────────────────────────────────────────────────────

function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 800);
}

async function save() {
    const payload = {
        enabled: document.getElementById("modbus-enabled").checked,
        controller: document.getElementById("modbus-controller").value.trim(),
        slave_id: parseInt(document.getElementById("modbus-slave-id").value) || 1,
        timeout: document.getElementById("modbus-timeout").value.trim() || "5s",
        registers,
    };
    await fetchJSON("/api/modbus/config", { method: "POST", body: JSON.stringify(payload) });
    updateConfigStatus();
}

// ── Test connection ───────────────────────────────────────────────────────────

async function testConnection() {
    const btn = document.getElementById("btn-test-connection");
    const resultEl = document.getElementById("test-result");
    setLoading(btn, true);
    resultEl.style.display = "none";

    const payload = {
        controller: document.getElementById("modbus-controller").value.trim(),
        slave_id: parseInt(document.getElementById("modbus-slave-id").value) || 1,
    };

    const res = await fetchJSON("/api/modbus/test-connection", {
        method: "POST",
        body: JSON.stringify(payload),
    });

    setLoading(btn, false);
    resultEl.style.display = "";

    if (res.ok) {
        resultEl.innerHTML = `<div class="alert alert-success py-2 mb-0">
            <i class="bi bi-check-circle"></i> ${res.detail}
        </div>`;
    } else {
        resultEl.innerHTML = `<div class="alert alert-danger py-2 mb-0">
            <i class="bi bi-x-circle"></i> ${res.error}
        </div>`;
    }
}

// ── Demo fill ─────────────────────────────────────────────────────────────────

async function fillDemo() {
    document.getElementById("modbus-controller").value = "modbus-demo-server:502";
    document.getElementById("modbus-slave-id").value = "1";
    document.getElementById("modbus-timeout").value = "5s";
    document.getElementById("modbus-enabled").checked = true;

    // Add demo registers if table is empty
    if (registers.length === 0) {
        registers = [
            { name: "temperature", register_type: "holding", address: 0, data_type: "FLOAT32", byte_order: "ABCD" },
            { name: "pressure",    register_type: "holding", address: 2, data_type: "FLOAT32", byte_order: "ABCD" },
            { name: "motor_speed", register_type: "holding", address: 4, data_type: "FLOAT32", byte_order: "ABCD" },
            { name: "voltage",     register_type: "holding", address: 6, data_type: "FLOAT32", byte_order: "ABCD" },
            { name: "current",     register_type: "holding", address: 8, data_type: "FLOAT32", byte_order: "ABCD" },
        ];
        renderTable();
    }
    await save();
    showAlert("Demo settings applied", "success");
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;");
}
