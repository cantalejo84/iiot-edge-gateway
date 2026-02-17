// OPC UA Node Browser - Lazy-load tree with node details

let currentNodeDetails = null;

document.addEventListener("DOMContentLoaded", () => {
    loadTree("ns=0;i=85");
    loadSelectedCount();

    document.getElementById("btn-refresh-root").addEventListener("click", () => {
        loadTree("ns=0;i=85");
    });

    document.getElementById("btn-add-to-selection").addEventListener("click", addToSelection);
});

async function loadTree(rootNodeId) {
    const container = document.getElementById("tree-container");
    container.innerHTML = '<div class="text-center text-secondary p-4"><span class="loading-spinner"></span> Loading nodes...</div>';

    try {
        const nodes = await fetchJSON(`/api/opcua/browse?node_id=${encodeURIComponent(rootNodeId)}`);
        if (nodes.error) {
            container.innerHTML = `<div class="text-center p-4"><span class="test-result error" style="display:block;">${nodes.error}</span><p class="mt-2" style="font-size:0.8rem;"><a href="/opcua/config">Configure OPC UA connection first</a></p></div>`;
            return;
        }
        container.innerHTML = "";
        const tree = buildTreeLevel(nodes);
        container.appendChild(tree);
    } catch (e) {
        container.innerHTML = `<div class="text-center p-4 text-danger"><i class="bi bi-exclamation-triangle"></i> Failed to connect. <a href="/opcua/config">Check configuration</a>.</div>`;
    }
}

function buildTreeLevel(nodes) {
    const ul = document.createElement("div");
    for (const node of nodes) {
        const item = document.createElement("div");

        const row = document.createElement("div");
        row.className = "tree-node";
        row.dataset.nodeId = node.node_id;

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

        row.addEventListener("click", (e) => {
            e.stopPropagation();
            // Select this node
            document.querySelectorAll(".tree-node.selected").forEach(n => n.classList.remove("selected"));
            row.classList.add("selected");
            loadNodeDetails(node.node_id);

            // Toggle children
            if (node.has_children) {
                const children = item.querySelector(".tree-children");
                if (children) {
                    children.classList.toggle("expanded");
                    toggle.textContent = children.classList.contains("expanded") ? "\u25BC" : "\u25B6";
                } else {
                    expandNode(item, node.node_id, toggle);
                }
            }
        });

        item.appendChild(row);
        ul.appendChild(item);
    }
    return ul;
}

async function expandNode(parentItem, nodeId, toggleEl) {
    toggleEl.innerHTML = '<span class="loading-spinner" style="width:0.7rem;height:0.7rem;border-width:1px;"></span>';
    try {
        const children = await fetchJSON(`/api/opcua/browse?node_id=${encodeURIComponent(nodeId)}`);
        const childContainer = document.createElement("div");
        childContainer.className = "tree-children expanded";
        const childTree = buildTreeLevel(children);
        childContainer.appendChild(childTree);
        parentItem.appendChild(childContainer);
        toggleEl.textContent = "\u25BC";
    } catch (e) {
        toggleEl.textContent = "\u25B6";
    }
}

async function loadNodeDetails(nodeId) {
    const content = document.getElementById("node-details-content");
    const empty = document.getElementById("node-details-empty");
    const addBtn = document.getElementById("btn-add-to-selection");

    empty.style.display = "none";
    content.style.display = "block";

    // Show loading state
    document.getElementById("detail-node-id").textContent = "Loading...";

    try {
        const details = await fetchJSON(`/api/opcua/node-details?node_id=${encodeURIComponent(nodeId)}`);
        currentNodeDetails = details;

        document.getElementById("detail-node-id").textContent = details.node_id || "-";
        document.getElementById("detail-display-name").textContent = details.display_name || "-";
        document.getElementById("detail-node-class").textContent = details.node_class || "-";
        document.getElementById("detail-data-type").textContent = details.data_type || "-";
        document.getElementById("detail-value").textContent = details.value !== undefined ? details.value : "-";
        document.getElementById("detail-namespace").textContent = details.namespace !== undefined ? details.namespace : "-";

        // Show add button only for variables
        addBtn.style.display = details.node_class === "Variable" ? "block" : "none";
    } catch (e) {
        document.getElementById("detail-node-id").textContent = "Error loading details";
    }
}

async function addToSelection() {
    if (!currentNodeDetails) return;

    // Get current nodes
    const existing = await fetchJSON("/api/opcua/nodes");
    const nodes = Array.isArray(existing) ? existing : [];

    // Check if already exists
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
    loadSelectedCount();
}

async function loadSelectedCount() {
    const nodes = await fetchJSON("/api/opcua/nodes");
    const count = Array.isArray(nodes) ? nodes.length : 0;
    document.getElementById("selected-count").textContent = count;
}
