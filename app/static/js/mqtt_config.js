// MQTT Connection Configuration — auto-save + cert upload + test connection

let saveTimeout = null;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btn-test").addEventListener("click", testConnection);
    document.getElementById("btn-upload-certs").addEventListener("click", uploadCerts);
    document.getElementById("btn-use-demo").addEventListener("click", useDemo);
    document.getElementById("btn-aws-policy").addEventListener("click", generateAwsPolicy);
    document.getElementById("btn-azure-config").addEventListener("click", generateAzureConfig);
    document.getElementById("btn-clear-connection").addEventListener("click", () => {
        new bootstrap.Modal(document.getElementById("clearConfirmModal")).show();
    });
    document.getElementById("btn-confirm-clear").addEventListener("click", clearConnection);
    document.getElementById("btn-remove-certs").addEventListener("click", removeCerts);
    document.getElementById("btn-copy-policy").addEventListener("click", copyPolicy);
    document.getElementById("btn-apply-azure-username").addEventListener("click", applyAzureUsername);
    document.getElementById("btn-apply-azure-topic").addEventListener("click", applyAzureTopic);

    // Auto-save on field changes
    document.querySelectorAll("#endpoint, #topic_pattern, #qos, #data_format, #mqtt_username, #mqtt_password")
        .forEach(el => {
            el.addEventListener("change", scheduleAutoSave);
            el.addEventListener("input", scheduleAutoSave);
        });

    document.getElementById("endpoint").addEventListener("input", checkEndpointType);
    checkEndpointType();

    // Example hint chips
    document.querySelectorAll(".field-hint[data-field]").forEach(el => {
        el.addEventListener("click", () => {
            const input = document.getElementById(el.dataset.field);
            if (!input) return;
            input.value = el.dataset.value;
            input.dispatchEvent(new Event("input"));
            input.dispatchEvent(new Event("change"));
        });
    });
});

// --- Endpoint detection ---

function isAwsEndpoint(endpoint) {
    return /\.iot\.[a-z0-9-]+\.amazonaws\.com/i.test(endpoint);
}

function isAzureEndpoint(endpoint) {
    return /\.azure-devices\.net/i.test(endpoint);
}

function checkEndpointType() {
    const endpoint = document.getElementById("endpoint").value;
    document.getElementById("btn-aws-policy").disabled = !isAwsEndpoint(endpoint);
    document.getElementById("btn-azure-config").disabled = !isAzureEndpoint(endpoint);

    // Show azure hint chip only when Azure endpoint detected
    document.querySelectorAll(".azure-hint").forEach(el => {
        el.style.display = isAzureEndpoint(endpoint) ? "" : "none";
    });

    // Show auth section only for Azure (or when username already has a value)
    const authSection = document.getElementById("auth-section");
    const hasAuth = document.getElementById("mqtt_username").value.trim() !== "" ||
                    document.getElementById("mqtt_password").value.trim() !== "";
    authSection.style.display = (isAzureEndpoint(endpoint) || hasAuth) ? "" : "none";
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// --- Auto-save ---

function getFormData() {
    return {
        endpoint: document.getElementById("endpoint").value,
        topic_pattern: document.getElementById("topic_pattern").value,
        qos: parseInt(document.getElementById("qos").value),
        data_format: document.getElementById("data_format").value,
        username: document.getElementById("mqtt_username").value,
        password: document.getElementById("mqtt_password").value,
    };
}

function scheduleAutoSave() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(autoSave, 800);
}

async function autoSave() {
    const data = await fetchJSON("/api/mqtt/config", { method: "POST", body: getFormData() });
    if (data.ok) updateConfigStatus(true);
}

// --- Test Connection ---

async function testConnection() {
    const btn = document.getElementById("btn-test");
    const statusEl = document.getElementById("conn-status");
    setLoading(btn, true);
    statusEl.innerHTML = "";

    const result = await fetchJSON("/api/mqtt/test-connection", {
        method: "POST",
        body: { endpoint: document.getElementById("endpoint").value },
    });
    setLoading(btn, false);

    if (result.ok) {
        statusEl.innerHTML = '<i class="bi bi-check-circle-fill" style="color:var(--success);font-size:0.9rem;"></i>';
    } else {
        statusEl.innerHTML = `<span class="conn-error-badge" title="${escapeHtml(result.error)}"><i class="bi bi-x-circle-fill"></i> Failed</span>`;
    }
}

// --- Demo broker ---

function useDemo() {
    document.getElementById("endpoint").value = "mqtt://mosquitto:1883";
    document.getElementById("topic_pattern").value = 'iiot/gateway/{{ .Hostname }}/{{ .PluginName }}';
    document.getElementById("qos").value = "0";
    document.getElementById("data_format").value = "json";
    document.getElementById("mqtt_username").value = "";
    document.getElementById("mqtt_password").value = "";
    checkEndpointType();
    autoSave();
    showAlert("Demo broker settings applied.", "success");
}

// --- AWS IoT Policy ---

async function generateAwsPolicy() {
    const btn = document.getElementById("btn-aws-policy");
    setLoading(btn, true);
    const result = await fetchJSON("/api/mqtt/aws-iot-policy");
    setLoading(btn, false);

    if (result.ok) {
        document.getElementById("aws-policy-content").textContent = result.policy;
        new bootstrap.Modal(document.getElementById("awsPolicyModal")).show();
    } else {
        showAlert("Failed to generate policy.", "danger");
    }
}

async function copyPolicy() {
    const text = document.getElementById("aws-policy-content").textContent;
    try {
        await navigator.clipboard.writeText(text);
    } catch (e) {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
    }
    showAlert("Policy copied to clipboard.", "success");
}

// --- Azure IoT Hub Config ---

let _azureConfig = null;

async function generateAzureConfig() {
    const btn = document.getElementById("btn-azure-config");
    setLoading(btn, true);
    const result = await fetchJSON("/api/mqtt/azure-iot-config");
    setLoading(btn, false);

    if (result.ok) {
        _azureConfig = result;
        document.getElementById("azure-hub-name").textContent = result.hub_name;
        document.getElementById("azure-username").textContent = result.username;
        document.getElementById("azure-topic").textContent = result.topic;
        new bootstrap.Modal(document.getElementById("azureConfigModal")).show();
    } else {
        showAlert("Failed to generate Azure config.", "danger");
    }
}

function applyAzureUsername() {
    if (!_azureConfig) return;
    document.getElementById("mqtt_username").value = _azureConfig.username;
    document.getElementById("mqtt_username").dispatchEvent(new Event("input"));
    scheduleAutoSave();
    showAlert("Username applied.", "success");
}

function applyAzureTopic() {
    if (!_azureConfig) return;
    document.getElementById("topic_pattern").value = _azureConfig.topic;
    document.getElementById("topic_pattern").dispatchEvent(new Event("input"));
    scheduleAutoSave();
    showAlert("Topic pattern applied.", "success");
}

// --- Clear Connection & Certs ---

async function clearConnection() {
    bootstrap.Modal.getInstance(document.getElementById("clearConfirmModal")).hide();
    const result = await fetchJSON("/api/mqtt/clear", { method: "POST" });
    if (result.ok) {
        showAlert("Connection and certificates cleared.", "success");
        setTimeout(() => location.reload(), 800);
    } else {
        showAlert("Failed to clear connection.", "danger");
    }
}

// --- Remove Certificates ---

async function removeCerts() {
    const btn = document.getElementById("btn-remove-certs");
    setLoading(btn, true);
    const result = await fetchJSON("/api/mqtt/delete-certs", { method: "POST" });
    setLoading(btn, false);

    if (result.ok) {
        ["tls_ca", "tls_cert", "tls_key"].forEach(f => updateCertStatus(f, false));
        btn.disabled = true;
        showAlert("Certificates removed.", "success");
    } else {
        showAlert("Failed to remove certificates.", "danger");
    }
}

function updateCertStatus(fieldId, uploaded) {
    const el = document.getElementById(`status-${fieldId}`);
    if (!el) return;
    const labels = { tls_ca: "ca.pem", tls_cert: "cert.pem", tls_key: "key.pem" };
    if (uploaded) {
        el.className = "cert-status mt-1 uploaded";
        el.innerHTML = `<i class="bi bi-check-circle-fill"></i> ${labels[fieldId]} uploaded`;
    } else {
        el.className = "cert-status mt-1 missing";
        el.innerHTML = `<i class="bi bi-circle"></i> Not uploaded`;
    }
}

// --- Certificate Upload ---

async function uploadCerts() {
    const btn = document.getElementById("btn-upload-certs");
    const formData = new FormData();

    const caFile = document.getElementById("tls_ca").files[0];
    const certFile = document.getElementById("tls_cert").files[0];
    const keyFile = document.getElementById("tls_key").files[0];

    if (!caFile && !certFile && !keyFile) {
        showAlert("Select at least one certificate file to upload.", "warning");
        return;
    }

    if (caFile) formData.append("tls_ca", caFile);
    if (certFile) formData.append("tls_cert", certFile);
    if (keyFile) formData.append("tls_key", keyFile);

    setLoading(btn, true);
    const resp = await fetch("/api/mqtt/upload-certs", { method: "POST", body: formData });
    const result = await resp.json();
    setLoading(btn, false);

    if (result.ok) {
        result.uploaded.forEach(f => updateCertStatus(f, true));
        document.getElementById("btn-remove-certs").disabled = false;
        showAlert(`Uploaded: ${result.uploaded.join(", ")}`, "success");
    } else {
        showAlert("Failed to upload certificates.", "danger");
    }
}
