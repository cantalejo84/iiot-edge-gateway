// Navigation and main-content locking during long async operations

let _navLockTimer = null;

function lockNav() {
    document.querySelectorAll(".sidebar .nav-link, .sidebar a").forEach(el => {
        el.dataset.hrefBackup = el.getAttribute("href") || "";
        el.setAttribute("href", "#");
        el.classList.add("nav-locked");
    });
    document.querySelectorAll(".state-status").forEach(el => el.classList.add("nav-locked"));
    document.querySelectorAll("#btn-agent-play, #btn-agent-stop").forEach(btn => {
        btn.disabled = true;
    });
}

function unlockNav() {
    document.querySelectorAll(".sidebar .nav-link, .sidebar a").forEach(el => {
        if (el.dataset.hrefBackup !== undefined) {
            el.setAttribute("href", el.dataset.hrefBackup);
            delete el.dataset.hrefBackup;
        }
        el.classList.remove("nav-locked");
    });
    document.querySelectorAll(".state-status").forEach(el => el.classList.remove("nav-locked"));
    document.querySelectorAll("#btn-agent-play, #btn-agent-stop").forEach(btn => {
        btn.disabled = false;
    });
}

function lockMain(msg) {
    if (_navLockTimer) clearTimeout(_navLockTimer);
    const overlay = document.getElementById("main-overlay");
    if (!overlay) return;
    const msgEl = document.getElementById("main-overlay-msg");
    if (msgEl && msg) msgEl.textContent = msg;
    overlay.classList.remove("d-none");
    // Safety timeout: auto-unlock after 30s in case the API hangs
    _navLockTimer = setTimeout(() => {
        unlockMain();
        unlockNav();
        showAlert("Operation timed out. Please retry.", "warning");
    }, 30000);
}

function unlockMain() {
    if (_navLockTimer) { clearTimeout(_navLockTimer); _navLockTimer = null; }
    const overlay = document.getElementById("main-overlay");
    if (!overlay) return;
    overlay.classList.add("d-none");
}
