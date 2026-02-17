// MQTT Configuration - auto-save + cert upload + test connection

let saveTimeout = null;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btn-test").addEventListener("click", testConnection);
    document.getElementById("btn-upload-certs").addEventListener("click", uploadCerts);

    // Auto-save on field changes
    document.querySelectorAll("#endpoint, #topic_pattern, #qos, #data_format")
        .forEach(el => {
            el.addEventListener("change", scheduleAutoSave);
            el.addEventListener("input", scheduleAutoSave);
        });

    // Demo broker quick-fill + immediate save
    document.getElementById("btn-use-demo").addEventListener("click", () => {
        document.getElementById("endpoint").value = "mqtt://mosquitto:1883";
        document.getElementById("topic_pattern").value = 'iiot/gateway/{{ .Hostname }}/{{ .PluginName }}';
        document.getElementById("qos").value = "0";
        document.getElementById("data_format").value = "json";
        autoSave();
        showAlert("Demo broker settings applied and saved.", "success");
    });
});

function getFormData() {
    return {
        endpoint: document.getElementById("endpoint").value,
        topic_pattern: document.getElementById("topic_pattern").value,
        qos: parseInt(document.getElementById("qos").value),
        data_format: document.getElementById("data_format").value,
    };
}

function scheduleAutoSave() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(autoSave, 800);
}

async function autoSave() {
    const data = await fetchJSON("/api/mqtt/config", { method: "POST", body: getFormData() });
    if (data.ok) {
        updateConfigStatus(true);
    }
}

async function testConnection() {
    const btn = document.getElementById("btn-test");
    const resultEl = document.getElementById("test-result");
    setLoading(btn, true);
    resultEl.className = "test-result";
    resultEl.style.display = "";

    const data = {
        endpoint: document.getElementById("endpoint").value,
    };

    const result = await fetchJSON("/api/mqtt/test-connection", { method: "POST", body: data });
    setLoading(btn, false);

    if (result.ok) {
        resultEl.className = "test-result success";
        resultEl.textContent = result.message || "Connected successfully";
    } else {
        resultEl.className = "test-result error";
        resultEl.textContent = "Connection failed: " + result.error;
    }
}

async function uploadCerts() {
    const btn = document.getElementById("btn-upload-certs");
    const formData = new FormData();

    const caFile = document.getElementById("tls_ca").files[0];
    const certFile = document.getElementById("tls_cert").files[0];
    const keyFile = document.getElementById("tls_key").files[0];

    if (!caFile && !certFile && !keyFile) {
        showAlert("Select at least one certificate file to upload", "warning");
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
        showAlert(`Certificates uploaded: ${result.uploaded.join(", ")}`, "success");
        setTimeout(() => location.reload(), 1000);
    } else {
        showAlert("Failed to upload certificates", "danger");
    }
}
