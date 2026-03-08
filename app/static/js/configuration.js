// Configuration page — Gateway Config export/import + Telegraf Config editor

document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    setupImport();
    setupTelegrafEditor();
});

// ── Tabs ──────────────────────────────────────────────────────────────────────

function setupTabs() {
    document.querySelectorAll("[data-tab]").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-tab]").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".config-tab").forEach(p => p.style.display = "none");
            btn.classList.add("active");
            document.getElementById("tab-" + btn.dataset.tab).style.display = "";
        });
    });
}

// ── Import ────────────────────────────────────────────────────────────────────

function setupImport() {
    document.getElementById("btn-import").addEventListener("click", async () => {
        const fileInput = document.getElementById("import-file");
        const resultEl = document.getElementById("import-result");

        if (!fileInput.files.length) {
            resultEl.innerHTML = '<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> Select a file first</span>';
            return;
        }

        if (!confirm("This will overwrite the current gateway configuration.\n\nProceed?")) return;

        const btn = document.getElementById("btn-import");
        setLoading(btn, true);
        resultEl.innerHTML = "";

        const form = new FormData();
        form.append("file", fileInput.files[0]);

        const res = await fetchJSON("/api/configuration/import", { method: "POST", body: form });
        setLoading(btn, false);

        if (res.ok) {
            resultEl.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> Imported. Click <strong>Deploy config</strong> to apply.</span>';
            updateConfigStatus(true);
            fileInput.value = "";
        } else {
            resultEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle"></i> ${res.error}</span>`;
        }
    });
}

// ── Telegraf editor ───────────────────────────────────────────────────────────

async function setupTelegrafEditor() {
    const editor = document.getElementById("telegraf-editor");
    const noConfig = document.getElementById("telegraf-no-config");

    const res = await fetchJSON("/api/configuration/telegraf");
    if (!res.exists || !res.content) {
        editor.style.display = "none";
        noConfig.style.display = "";
        return;
    }
    editor.value = res.content;

    document.getElementById("btn-apply-telegraf").addEventListener("click", applyTelegrafConfig);
}

async function applyTelegrafConfig() {
    const btn = document.getElementById("btn-apply-telegraf");
    const indicator = document.getElementById("telegraf-save-indicator");
    const content = document.getElementById("telegraf-editor").value;

    setLoading(btn, true);
    indicator.textContent = "Applying...";

    const res = await fetchJSON("/api/configuration/telegraf", {
        method: "POST",
        body: JSON.stringify({ content }),
    });

    setLoading(btn, false);

    if (res.ok) {
        if (res.warning) {
            indicator.textContent = "";
            showAlert(`Config applied but Telegraf reported an error: ${res.warning}`, "warning");
        } else {
            indicator.textContent = "Applied";
            setTimeout(() => { indicator.textContent = ""; }, 3000);
            showAlert("Telegraf config applied and agent restarted.", "success");
        }
    } else {
        indicator.textContent = "";
        showAlert("Failed to apply config. Check logs.", "danger");
    }
}
