// UI helper utilities: alerts, loading state, config status badge

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
