// HTTP helpers

async function fetchJSON(url, options = {}) {
    try {
        const defaults = { headers: { "Content-Type": "application/json" } };
        if (options.body && typeof options.body === "object" && !(options.body instanceof FormData)) {
            options.body = JSON.stringify(options.body);
        }
        if (options.body instanceof FormData) {
            delete defaults.headers["Content-Type"];
        }
        const resp = await fetch(url, { ...defaults, ...options });
        if (!resp.ok) return { ok: false, error: `HTTP ${resp.status}` };
        return await resp.json();
    } catch (e) {
        return { ok: false, error: e.message };
    }
}
