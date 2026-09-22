/*
 * FASE 10 — Selector global de modo claro/oscuro.
 *
 * La preferencia visual se guarda únicamente en localStorage. No contiene
 * datos de la evaluación ni modifica la persistencia oficial del backend.
 */

(function () {
    "use strict";

    const STORAGE_KEY = "riasec-theme";
    const root = document.documentElement;
    const button = document.querySelector("[data-theme-toggle]");
    const label = document.querySelector("[data-theme-label]");
    const themeColor = document.querySelector('meta[name="theme-color"]');
    const mediaQuery = window.matchMedia
        ? window.matchMedia("(prefers-color-scheme: dark)")
        : null;

    function getStoredTheme() {
        try {
            const value = window.localStorage.getItem(STORAGE_KEY);
            return value === "light" || value === "dark" ? value : null;
        } catch (error) {
            return null;
        }
    }

    function saveTheme(theme) {
        try {
            window.localStorage.setItem(STORAGE_KEY, theme);
        } catch (error) {
            // El modo sigue funcionando durante la sesión aunque storage falle.
        }
    }

    function preferredTheme() {
        const stored = getStoredTheme();
        if (stored) {
            return stored;
        }
        return mediaQuery && mediaQuery.matches ? "dark" : "light";
    }

    function updateControls(theme) {
        if (!button) {
            return;
        }

        const isDark = theme === "dark";
        const nextModeLabel = isDark ? "claro" : "oscuro";

        button.setAttribute(
            "aria-label",
            `Cambiar a modo ${nextModeLabel}`,
        );
        button.setAttribute("aria-pressed", String(isDark));
        button.title = `Cambiar a modo ${nextModeLabel}`;

        if (label) {
            label.textContent = isDark ? "Modo claro" : "Modo oscuro";
        }

        if (themeColor) {
            themeColor.setAttribute(
                "content",
                isDark ? "#171d2c" : "#5b4bdb",
            );
        }
    }

    function applyTheme(theme, persist) {
        const normalized = theme === "dark" ? "dark" : "light";
        root.dataset.theme = normalized;
        updateControls(normalized);

        if (persist) {
            saveTheme(normalized);
        }
    }

    applyTheme(root.dataset.theme || preferredTheme(), false);

    if (button) {
        button.addEventListener("click", function () {
            const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
            applyTheme(nextTheme, true);
        });
    }

    if (mediaQuery) {
        const handleSystemThemeChange = function (event) {
            if (!getStoredTheme()) {
                applyTheme(event.matches ? "dark" : "light", false);
            }
        };

        if (typeof mediaQuery.addEventListener === "function") {
            mediaQuery.addEventListener("change", handleSystemThemeChange);
        } else if (typeof mediaQuery.addListener === "function") {
            mediaQuery.addListener(handleSystemThemeChange);
        }
    }
}());
