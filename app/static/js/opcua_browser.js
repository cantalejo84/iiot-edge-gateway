// OPC UA Node Browser - Lazy-load tree with node details

let currentNodeDetails = null;
let selectedNodeIds = new Set();
let breadcrumbPath = [{ name: "Objects", node_id: "ns=0;i=85" }];
let autoRefreshTimer = null;
let autoRefreshNodeId = null;

document.addEventListener("DOMContentLoaded", () => {
    loadTree("ns=0;i=85");
    loadSelectedNodeIds();
    loadSelectedCount();
    loadNamespaceTable();

    document.getElementById("btn-refresh-root").addEventListener("click", () => {
        breadcrumbPath = [{ name: "Objects", node_id: "ns=0;i=85" }];
        loadTree("ns=0;i=85");
    });

    document.getElementById("btn-add-to-selection").addEventListener("click", addToSelection);

    document.getElementById("tree-search").addEventListener("input", e => filterTree(e.target.value));

    document.getElementById("toggle-auto-refresh").addEventListener("change", e => {
        if (e.target.checked && currentNodeDetails?.node_class === "Variable") {
            startAutoRefresh(currentNodeDetails.node_id);
        } else {
            stopAutoRefresh();
        }
    });

    document.getElementById("btn-add-bulk").addEventListener("click", addBulkToSelection);
    document.getElementById("btn-deselect-all").addEventListener("click", deselectAll);

    // Rotate chevron on namespace card expand/collapse
    document.getElementById("ns-table-collapse").addEventListener("show.bs.collapse", () => {
        document.getElementById("ns-chevron").style.transform = "rotate(180deg)";
    });
    document.getElementById("ns-table-collapse").addEventListener("hide.bs.collapse", () => {
        document.getElementById("ns-chevron").style.transform = "";
    });

    window.addEventListener("beforeunload", stopAutoRefresh);
});

// ─── Tree ────────────────────────────────────────────────────────────────────

async function loadTree(rootNodeId) {
    const container = document.getElementById("tree-container");
    container.innerHTML = '<div class="text-center text-secondary p-4"><span class="loading-spinner"></span> Loading nodes...</div>';

    // Reset search filter
    const searchInput = document.getElementById("tree-search");
    if (searchInput) searchInput.value = "";

    try {
        const nodes = await fetchJSON(`/api/opcua/browse?node_id=${encodeURIComponent(rootNodeId)}`);
        if (nodes.error) {
            container.innerHTML = `<div class="text-center p-4"><span class="test-result error" style="display:block;">${nodes.error}</span><p class="mt-2" style="font-size:0.8rem;"><a href="/opcua/config">Configure OPC UA connection first</a></p></div>`;
            return;
        }
        container.innerHTML = "";
        const tree = buildTreeLevel(nodes, 1);
        container.appendChild(tree);
        renderBreadcrumb();
    } catch (e) {
        container.innerHTML = `<div class="text-center p-4 text-danger"><i class="bi bi-exclamation-triangle"></i> Failed to connect. <a href="/opcua/config">Check configuration</a>.</div>`;
    }
}

function buildTreeLevel(nodes, depth) {
    const ul = document.createElement("div");
    for (const node of nodes) {
        const item = document.createElement("div");

        const row = document.createElement("div");
        row.className = "tree-node";
        row.dataset.nodeId = node.node_id;
        row.dataset.depth = depth;
        row.dataset.name = node.display_name;

        // Bulk checkbox for Variables
        if (node.node_class === "Variable") {
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.className = "bulk-cb me-1";
            cb.dataset.nodeId = node.node_id;
            cb.dataset.name = node.display_name;
            cb.addEventListener("change", updateBulkToolbar);
            cb.addEventListener("click", e => e.stopPropagation());
            row.appendChild(cb);
        }

        const toggle = document.createElement("span");
        toggle.className = "toggle";
        toggle.textContent = node.has_children ? "\u25B6" : "";
        row.appendChild(toggle);

        const icon = document.createElement("i");
        icon.className = `bi node-icon ${node.node_class === "Variable" ? "bi-tag variable" : "bi-folder2 object"}`;
        row.appendChild(icon);

        const label = document.createElement("span");
        label.textContent = node.display_name;
        row.appendChild(label);

        // Already-selected indicator
        if (node.node_class === "Variable" && selectedNodeIds.has(node.node_id)) {
            const check = document.createElement("i");
            check.className = "bi bi-check-circle-fill ms-auto text-success";
            check.title = "Already in selection";
            check.style.fontSize = "0.75rem";
            check.style.flexShrink = "0";
            row.appendChild(check);
        }

        row.addEventListener("click", (e) => {
            e.stopPropagation();
            document.querySelectorAll(".tree-node.selected").forEach(n => n.classList.remove("selected"));
            row.classList.add("selected");
            loadNodeDetails(node.node_id);

            // Update breadcrumb
            const d = parseInt(row.dataset.depth, 10);
            breadcrumbPath = breadcrumbPath.slice(0, d);
            breadcrumbPath.push({ name: node.display_name, node_id: node.node_id });
            renderBreadcrumb();

            // Toggle children
            if (node.has_children) {
                const children = item.querySelector(".tree-children");
                if (children) {
                    children.classList.toggle("expanded");
                    toggle.textContent = children.classList.contains("expanded") ? "\u25BC" : "\u25B6";
                } else {
                    expandNode(item, node.node_id, toggle, depth + 1);
                }
            }
        });

        item.appendChild(row);
        ul.appendChild(item);
    }
    return ul;
}

async function expandNode(parentItem, nodeId, toggleEl, depth) {
    toggleEl.innerHTML = '<span class="loading-spinner" style="width:0.7rem;height:0.7rem;border-width:1px;"></span>';
    try {
        const children = await fetchJSON(`/api/opcua/browse?node_id=${encodeURIComponent(nodeId)}`);
        const childContainer = document.createElement("div");
        childContainer.className = "tree-children expanded";
        const childTree = buildTreeLevel(children, depth);
        childContainer.appendChild(childTree);
        parentItem.appendChild(childContainer);
        toggleEl.textContent = "\u25BC";

        // Re-apply active filter if any
        const term = document.getElementById("tree-search")?.value;
        if (term) filterTree(term);
    } catch (e) {
        toggleEl.textContent = "\u25B6";
    }
}

// ─── Search / Filter ─────────────────────────────────────────────────────────

function filterTree(term) {
    const lower = term.toLowerCase();
    document.querySelectorAll(".tree-node").forEach(row => {
        const labelEl = row.querySelector("span:not(.toggle)");
        const label = labelEl?.textContent || "";
        const match = !term || label.toLowerCase().includes(lower);
        row.style.display = match ? "" : "none";
    });
}

// ─── Breadcrumb ───────────────────────────────────────────────────────────────

function renderBreadcrumb() {
    const nav = document.getElementById("tree-breadcrumb");
    const ol = nav.querySelector("ol");
    nav.style.display = breadcrumbPath.length > 1 ? "" : "none";
    ol.innerHTML = breadcrumbPath.map((item, i) => {
        const isLast = i === breadcrumbPath.length - 1;
        if (isLast) return `<li class="breadcrumb-item active">${escHtml(item.name)}</li>`;
        return `<li class="breadcrumb-item"><a href="#" data-jump-node="${escAttr(item.node_id)}">${escHtml(item.name)}</a></li>`;
    }).join("");
    ol.querySelectorAll("[data-jump-node]").forEach(a => {
        a.addEventListener("click", e => {
            e.preventDefault();
            const idx = breadcrumbPath.findIndex(x => x.node_id === a.dataset.jumpNode);
            if (idx >= 0) {
                breadcrumbPath = breadcrumbPath.slice(0, idx + 1);
                loadTree(a.dataset.jumpNode);
            }
        });
    });
}

function escHtml(str) {
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function escAttr(str) {
    return String(str).replace(/"/g, "&quot;");
}

// ─── Node Details ─────────────────────────────────────────────────────────────

async function loadNodeDetails(nodeId) {
    const content = document.getElementById("node-details-content");
    const empty = document.getElementById("node-details-empty");

    stopAutoRefresh();
    document.getElementById("toggle-auto-refresh").checked = false;

    empty.style.display = "none";
    content.style.display = "block";
    document.getElementById("detail-node-id").textContent = "Loading...";

    try {
        const details = await fetchJSON(`/api/opcua/node-details?node_id=${encodeURIComponent(nodeId)}`);
        currentNodeDetails = details;
        renderNodeDetails(details);
    } catch (e) {
        document.getElementById("detail-node-id").textContent = "Error loading details";
    }
}

function renderNodeDetails(details) {
    // Identity
    document.getElementById("detail-node-id").textContent = details.node_id || "-";
    document.getElementById("detail-display-name").textContent = details.display_name || "-";
    document.getElementById("detail-namespace").textContent = details.namespace ?? "-";

    const nc = details.node_class || "-";
    const ncIcon = nc === "Variable" ? "bi-tag" : "bi-folder2";
    document.getElementById("detail-node-class").innerHTML =
        `<i class="bi ${ncIcon} me-1"></i>${escHtml(nc)}`;

    // Description
    const descRow = document.getElementById("detail-description-row");
    if (details.description) {
        document.getElementById("detail-description").textContent = details.description;
        descRow.style.removeProperty("display");
    } else {
        descRow.style.setProperty("display", "none", "important");
    }

    // Variable section
    const varAttrs = document.getElementById("detail-variable-attrs");
    const addBtn = document.getElementById("btn-add-to-selection");
    const refreshToggle = document.getElementById("details-refresh-toggle");

    if (nc !== "Variable") {
        varAttrs.style.display = "none";
        addBtn.style.display = "none";
        refreshToggle.classList.add("d-none");
        refreshToggle.classList.remove("d-flex");
        return;
    }

    varAttrs.style.display = "";
    addBtn.style.display = "block";
    refreshToggle.classList.remove("d-none");
    refreshToggle.classList.add("d-flex");

    // Value + engineering units
    document.getElementById("detail-value").textContent = details.value ?? "-";
    const euEl = document.getElementById("detail-engineering-units");
    euEl.textContent = details.engineering_units ? `[${details.engineering_units}]` : "";

    // Status badge
    const badge = document.getElementById("detail-status-badge");
    if (details.status_code) {
        const sc = details.status_code;
        let cls = "bg-secondary";
        if (sc === "Good") cls = "bg-success";
        else if (sc.startsWith("Uncertain")) cls = "bg-warning text-dark";
        else if (sc.startsWith("Bad")) cls = "bg-danger";
        badge.className = `badge ${cls}`;
        badge.textContent = sc;
    } else {
        badge.className = "";
        badge.textContent = "";
    }

    // Data type + value rank
    document.getElementById("detail-data-type").textContent = details.data_type || "-";
    const vrBadge = document.getElementById("detail-value-rank-badge");
    if (details.value_rank !== null && details.value_rank !== undefined) {
        const vrMap = { "-1": "Scalar", "0": "Scalar or Array", "1": "Array[1D]" };
        vrBadge.textContent = vrMap[String(details.value_rank)] || `Array[${details.value_rank}D]`;
        vrBadge.style.display = "";
    } else {
        vrBadge.style.display = "none";
    }

    // Access level bitmask
    const alEl = document.getElementById("detail-access-level");
    if (details.access_level !== null && details.access_level !== undefined) {
        const al = details.access_level;
        let html = "";
        if (al & 0x01) html += '<span class="badge bg-primary me-1">Read</span>';
        if (al & 0x02) html += '<span class="badge bg-warning text-dark me-1">Write</span>';
        if (al & 0x04) html += '<span class="badge bg-secondary me-1">History</span>';
        alEl.innerHTML = html || '<span class="text-muted">—</span>';
    } else {
        alEl.innerHTML = '<span class="text-muted">—</span>';
    }

    // Timestamps
    function fmtTs(iso) {
        if (!iso) return "—";
        try { return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC"; }
        catch (e) { return iso; }
    }
    document.getElementById("detail-source-ts").textContent = fmtTs(details.source_timestamp);
    document.getElementById("detail-server-ts").textContent = fmtTs(details.server_timestamp);

    // Min sampling interval
    const msiEl = document.getElementById("detail-min-sampling");
    if (details.min_sampling_interval !== null && details.min_sampling_interval !== undefined) {
        const msi = details.min_sampling_interval;
        if (msi < 0) msiEl.textContent = "Continuous";
        else if (msi === 0) msiEl.textContent = "Fastest";
        else if (msi < 1000) msiEl.textContent = `${msi}ms`;
        else msiEl.textContent = `${msi / 1000}s`;
    } else {
        msiEl.textContent = "—";
    }

    // Historizing
    const histIcon = document.getElementById("detail-historizing-icon");
    const histLabel = document.getElementById("detail-historizing-label");
    const showHist = !!details.historizing;
    histIcon.style.display = showHist ? "" : "none";
    histLabel.style.display = showHist ? "" : "none";
}

// ─── Add to selection ─────────────────────────────────────────────────────────

async function addToSelection() {
    if (!currentNodeDetails) return;

    const existing = await fetchJSON("/api/opcua/nodes");
    const nodes = Array.isArray(existing) ? existing : [];

    if (nodes.some(n => n.identifier === (currentNodeDetails.identifier || "") && n.namespace === String(currentNodeDetails.namespace))) {
        showAlert("Node already in selection", "warning");
        return;
    }

    nodes.push({
        name: currentNodeDetails.display_name,
        namespace: String(currentNodeDetails.namespace),
        identifier_type: currentNodeDetails.identifier_type || "s",
        identifier: String(currentNodeDetails.identifier || ""),
        sampling_mode: "polling",
        interval: "1s",
        deadband_type: "None",
        deadband_value: 0,
    });

    await fetchJSON("/api/opcua/nodes", { method: "POST", body: nodes });
    showAlert(`Added "${currentNodeDetails.display_name}" to selection`, "success");
    updateConfigStatus(true);
    selectedNodeIds.add(currentNodeDetails.node_id);
    loadSelectedCount();

    // Add checkmark to the currently selected tree row
    const row = document.querySelector(`.tree-node.selected`);
    if (row && !row.querySelector(".bi-check-circle-fill")) {
        const check = document.createElement("i");
        check.className = "bi bi-check-circle-fill ms-auto text-success";
        check.title = "Already in selection";
        check.style.fontSize = "0.75rem";
        check.style.flexShrink = "0";
        row.appendChild(check);
    }
}

// ─── Bulk select ──────────────────────────────────────────────────────────────

function updateBulkToolbar() {
    const checked = document.querySelectorAll(".bulk-cb:checked");
    const toolbar = document.getElementById("bulk-toolbar");
    if (checked.length > 0) {
        toolbar.classList.remove("d-none");
        document.getElementById("bulk-count").textContent = `${checked.length} selected`;
    } else {
        toolbar.classList.add("d-none");
    }
}

function deselectAll() {
    document.querySelectorAll(".bulk-cb:checked").forEach(cb => { cb.checked = false; });
    updateBulkToolbar();
}

function parseNodeIdToEntry(nodeId, name) {
    const m = nodeId.match(/^ns=(\d+);([isgb])=(.+)$/);
    if (!m) return null;
    return {
        name: name,
        namespace: m[1],
        identifier_type: m[2],
        identifier: m[3],
        sampling_mode: "polling",
        interval: "1s",
        deadband_type: "None",
        deadband_value: 0,
    };
}

function reconstructNodeId(n) {
    return `ns=${n.namespace};${n.identifier_type}=${n.identifier}`;
}

async function addBulkToSelection() {
    const checked = document.querySelectorAll(".bulk-cb:checked");
    if (!checked.length) return;

    const existing = await fetchJSON("/api/opcua/nodes");
    const nodes = Array.isArray(existing) ? existing : [];
    let added = 0;

    checked.forEach(cb => {
        const nodeId = cb.dataset.nodeId;
        const entry = parseNodeIdToEntry(nodeId, cb.dataset.name);
        if (entry && !nodes.some(n => reconstructNodeId(n) === nodeId)) {
            nodes.push(entry);
            selectedNodeIds.add(nodeId);
            added++;
            // Add checkmark to tree row
            const row = document.querySelector(`.tree-node[data-node-id="${CSS.escape(nodeId)}"]`);
            if (row && !row.querySelector(".bi-check-circle-fill")) {
                const check = document.createElement("i");
                check.className = "bi bi-check-circle-fill ms-auto text-success";
                check.title = "Already in selection";
                check.style.fontSize = "0.75rem";
                check.style.flexShrink = "0";
                row.appendChild(check);
            }
        }
    });

    if (added > 0) {
        await fetchJSON("/api/opcua/nodes", { method: "POST", body: nodes });
        showAlert(`Added ${added} node${added > 1 ? "s" : ""} to selection`, "success");
        updateConfigStatus(true);
        loadSelectedCount();
    } else {
        showAlert("All selected nodes already in selection", "warning");
    }

    checked.forEach(cb => { cb.checked = false; });
    updateBulkToolbar();
}

// ─── Selected count ───────────────────────────────────────────────────────────

async function loadSelectedCount() {
    const nodes = await fetchJSON("/api/opcua/nodes");
    const count = Array.isArray(nodes) ? nodes.length : 0;
    document.getElementById("selected-count").textContent = count;
}

async function loadSelectedNodeIds() {
    const nodes = await fetchJSON("/api/opcua/nodes");
    if (Array.isArray(nodes)) {
        selectedNodeIds = new Set(nodes.map(n => reconstructNodeId(n)));
    }
}

// ─── Auto-refresh ─────────────────────────────────────────────────────────────

function startAutoRefresh(nodeId) {
    stopAutoRefresh();
    autoRefreshNodeId = nodeId;
    autoRefreshTimer = setInterval(() => refreshNodeValue(autoRefreshNodeId), 3000);
}

function stopAutoRefresh() {
    if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; }
    autoRefreshNodeId = null;
}

async function refreshNodeValue(nodeId) {
    if (!nodeId) return;
    const dv = await fetchJSON(`/api/opcua/node-value?node_id=${encodeURIComponent(nodeId)}`);
    if (!dv || dv.error) return;

    document.getElementById("detail-value").textContent = dv.value ?? "-";

    const badge = document.getElementById("detail-status-badge");
    if (dv.status_code) {
        const sc = dv.status_code;
        let cls = "bg-secondary";
        if (sc === "Good") cls = "bg-success";
        else if (sc.startsWith("Uncertain")) cls = "bg-warning text-dark";
        else if (sc.startsWith("Bad")) cls = "bg-danger";
        badge.className = `badge ${cls}`;
        badge.textContent = sc;
    }

    function fmtTs(iso) {
        if (!iso) return "—";
        try { return new Date(iso).toISOString().replace("T", " ").slice(0, 19) + " UTC"; }
        catch (e) { return iso; }
    }
    document.getElementById("detail-source-ts").textContent = fmtTs(dv.source_timestamp);
    document.getElementById("detail-server-ts").textContent = fmtTs(dv.server_timestamp);
}

// ─── Namespace table ──────────────────────────────────────────────────────────

async function loadNamespaceTable() {
    const body = document.getElementById("ns-table-body");
    try {
        const namespaces = await fetchJSON("/api/opcua/namespaces");
        if (!Array.isArray(namespaces) || namespaces.error) {
            body.innerHTML = `<p class="text-muted text-center p-2 mb-0" style="font-size:0.8rem;">Could not load namespaces — connect to a server first</p>`;
            return;
        }
        const table = document.createElement("table");
        table.className = "table table-sm mb-0";
        table.style.fontSize = "0.78rem";
        table.innerHTML = `<thead><tr><th style="width:3.5rem;">Index</th><th>URI</th></tr></thead>`;
        const tbody = document.createElement("tbody");
        namespaces.forEach(ns => {
            const tr = document.createElement("tr");
            if (ns.index === 0) tr.classList.add("text-muted");
            tr.innerHTML = `<td class="text-center">${ns.index}</td><td class="font-mono" style="word-break:break-all;">${escHtml(ns.uri)}</td>`;
            tbody.appendChild(tr);
        });
        table.appendChild(tbody);
        body.innerHTML = "";
        body.appendChild(table);
    } catch (e) {
        body.innerHTML = `<p class="text-muted text-center p-2 mb-0" style="font-size:0.8rem;">Could not load namespaces</p>`;
    }
}
