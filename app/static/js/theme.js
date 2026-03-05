// Theme system: default (dark) and keepler (light)

function applyTheme(theme) {
    const root = document.getElementById("app-root");
    if (!root) return;
    if (theme === "keepler") {
        root.setAttribute("data-theme", "keepler");
        root.setAttribute("data-bs-theme", "light");
    } else {
        root.removeAttribute("data-theme");
        root.setAttribute("data-bs-theme", "dark");
    }
}

(function initTheme() {
    const saved = localStorage.getItem("iiot-theme") || "default";
    applyTheme(saved);
})();
