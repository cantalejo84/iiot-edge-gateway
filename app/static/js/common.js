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

async function applyConfig(btn) {
    setLoading(btn, true);
    const data = await fetchJSON("/api/telegraf/generate", { method: "POST" });
    setLoading(btn, false);

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

// Config preview and apply actions
document.addEventListener("DOMContentLoaded", () => {
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
