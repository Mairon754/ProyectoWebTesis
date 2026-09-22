/*
 * FASE 9 — Guardado automático y recuperación temporal RIASEC.
 *
 * Principios:
 * - PostgreSQL/backend es la persistencia oficial;
 * - localStorage solo conserva una copia temporal de recuperación;
 * - una respuesta seleccionada se intenta persistir progresivamente;
 * - el estado de etapa/pregunta también se sincroniza con el backend;
 * - si se pierde conexión, se conserva una respuesta pendiente y se reintenta.
 */

(() => {
    "use strict";

    const root = document.querySelector("[data-assessment-experience]");
    const form = document.querySelector("[data-assessment-form]");

    if (!root || !form) {
        return;
    }

    const responseUrl = root.dataset.responseUrl;
    const autosaveUrl = root.dataset.autosaveUrl;
    const sessionId = root.dataset.sessionId;
    const stage = root.dataset.stage || "onet";
    const assessmentStatus = root.dataset.assessmentStatus || "in_progress";
    const currentIndex = Number(root.dataset.currentIndex || 1);
    const itemId = form.querySelector('input[name="item_id"]')?.value || "";
    const statusBox = root.querySelector("[data-autosave-status]");
    const statusMessage = root.querySelector("[data-autosave-message]");
    const progressElement = root.querySelector("progress");
    const answerInputs = Array.from(
        root.querySelectorAll("[data-answer-input]")
    );
    const ttsUsedInput = root.querySelector("[data-tts-used]");
    const responseTimeInput = root.querySelector("[data-response-time-ms]");

    if (!responseUrl || !autosaveUrl || !sessionId || !itemId) {
        return;
    }

    const storageKey = `riasec:assessment:${sessionId}`;
    const startedAt = performance.now();
    let debounceTimer = null;
    let retryTimer = null;
    let requestSequence = 0;
    let pendingController = null;

    function selectedValue() {
        const selected = answerInputs.find((input) => input.checked);
        return selected ? Number(selected.value) : null;
    }

    function ttsWasUsed() {
        return ttsUsedInput?.value === "true";
    }

    function elapsedResponseTime() {
        const milliseconds = Math.max(0, Math.round(performance.now() - startedAt));
        if (responseTimeInput) {
            responseTimeInput.value = String(milliseconds);
        }
        return milliseconds;
    }

    function currentProgressSnapshot() {
        const answeredItems = Number(progressElement?.value || 0);
        const totalItems = Number(progressElement?.max || 60);
        const percentage = totalItems > 0
            ? Math.round((answeredItems / totalItems) * 10000) / 100
            : 0;

        return { answeredItems, totalItems, percentage };
    }

    function readLocalState() {
        try {
            const raw = window.localStorage.getItem(storageKey);
            if (!raw) {
                return null;
            }

            const parsed = JSON.parse(raw);
            if (parsed?.version !== 1 || parsed?.sessionId !== sessionId) {
                return null;
            }
            return parsed;
        } catch (error) {
            console.warn("No fue posible leer recuperación local RIASEC.", error);
            return null;
        }
    }

    function writeLocalState(overrides = {}) {
        const previous = readLocalState() || {};
        const progress = currentProgressSnapshot();
        const value = selectedValue();

        const state = {
            ...previous,
            version: 1,
            sessionId,
            stage,
            assessmentStatus,
            currentItemIndex: currentIndex,
            itemId,
            responseRaw: value,
            ttsUsed: ttsWasUsed(),
            answeredItems: progress.answeredItems,
            totalItems: progress.totalItems,
            percentage: progress.percentage,
            updatedAt: new Date().toISOString(),
            ...overrides,
        };

        try {
            window.localStorage.setItem(storageKey, JSON.stringify(state));
        } catch (error) {
            console.warn("No fue posible guardar recuperación local RIASEC.", error);
        }

        return state;
    }

    function setSaveStatus(state, message) {
        if (statusBox) {
            statusBox.dataset.saveState = state;
        }
        if (statusMessage) {
            statusMessage.textContent = message;
        }
    }

    async function postJson(url, payload, options = {}) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body: JSON.stringify(payload),
            credentials: "same-origin",
            keepalive: Boolean(options.keepalive),
            signal: options.signal,
        });

        let body = null;
        try {
            body = await response.json();
        } catch {
            throw new Error(`Respuesta HTTP ${response.status} no válida.`);
        }

        if (!response.ok || body?.success !== true) {
            throw new Error(body?.message || `Error HTTP ${response.status}.`);
        }

        return body;
    }

    function updateProgress(progress) {
        if (!progress || !progressElement) {
            return;
        }

        progressElement.value = Number(progress.answered_items || 0);
        progressElement.setAttribute(
            "aria-valuetext",
            `${progress.answered_items || 0} de 60 preguntas respondidas`
        );

        const count = root.querySelector(".assessment-topbar__count");
        if (count) {
            count.textContent = `${progress.answered_items || 0} respondidas`;
        }

        const meta = root.querySelectorAll(".progress-meta span");
        if (meta[0]) {
            meta[0].textContent = `${progress.percentage || 0}% completado`;
        }
        if (meta[1]) {
            meta[1].textContent = `${progress.missing_items || 0} pendientes`;
        }
    }

    async function syncAssessmentState(options = {}) {
        try {
            const response = await postJson(
                autosaveUrl,
                {
                    session_id: sessionId,
                    stage,
                    current_item_index: currentIndex,
                },
                options
            );
            writeLocalState({
                assessmentStatus: response.data?.status || assessmentStatus,
                backendStage: response.data?.stage || stage,
                backendCurrentItemIndex: (
                    response.data?.current_item_index || currentIndex
                ),
                stateSyncedAt: new Date().toISOString(),
            });
            return true;
        } catch (error) {
            console.warn("No se pudo sincronizar el estado de navegación.", error);
            return false;
        }
    }

    function scheduleRetry() {
        window.clearTimeout(retryTimer);
        retryTimer = window.setTimeout(() => {
            if (navigator.onLine) {
                syncPendingResponse("retry");
            }
        }, 1800);
    }

    async function syncPendingResponse(source = "selection") {
        const value = selectedValue();
        if (!Number.isInteger(value) || value < 1 || value > 5) {
            return false;
        }

        const sequence = ++requestSequence;
        pendingController?.abort();
        pendingController = new AbortController();

        writeLocalState({ pendingResponse: true });

        if (!navigator.onLine) {
            setSaveStatus(
                "offline",
                "Sin conexión. La respuesta queda guardada temporalmente en este dispositivo."
            );
            return false;
        }

        setSaveStatus(
            "saving",
            source === "recovery"
                ? "Recuperando y sincronizando una respuesta pendiente…"
                : "Guardando respuesta…"
        );

        try {
            const response = await postJson(
                responseUrl,
                {
                    session_id: sessionId,
                    item_id: itemId,
                    response_raw: value,
                    response_time_ms: elapsedResponseTime(),
                    tts_used: ttsWasUsed(),
                },
                { signal: pendingController.signal }
            );

            if (sequence !== requestSequence) {
                return false;
            }

            updateProgress(response.data?.progress);
            writeLocalState({
                pendingResponse: false,
                lastSyncedAt: new Date().toISOString(),
            });

            await syncAssessmentState();
            setSaveStatus("saved", "Respuesta guardada automáticamente.");
            return true;
        } catch (error) {
            if (error?.name === "AbortError") {
                return false;
            }

            writeLocalState({ pendingResponse: true });
            setSaveStatus(
                navigator.onLine ? "error" : "offline",
                navigator.onLine
                    ? "No pudimos sincronizar todavía. Conservamos una copia temporal y reintentaremos."
                    : "Sin conexión. Conservamos una copia temporal y reintentaremos al volver la conexión."
            );
            console.warn("Autosave de respuesta pendiente.", error);
            scheduleRetry();
            return false;
        }
    }

    function scheduleResponseSave() {
        window.clearTimeout(debounceTimer);
        elapsedResponseTime();
        writeLocalState({ pendingResponse: true });
        setSaveStatus("saving", "Preparando guardado automático…");

        debounceTimer = window.setTimeout(() => {
            syncPendingResponse("selection");
        }, 450);
    }

    function restorePendingLocalResponse() {
        const local = readLocalState();
        if (
            !local?.pendingResponse
            || local.itemId !== itemId
            || local.currentItemIndex !== currentIndex
            || !Number.isInteger(local.responseRaw)
            || local.responseRaw < 1
            || local.responseRaw > 5
        ) {
            return false;
        }

        const input = answerInputs.find(
            (candidate) => Number(candidate.value) === local.responseRaw
        );
        if (!input) {
            return false;
        }

        input.checked = true;
        if (ttsUsedInput && local.ttsUsed) {
            ttsUsedInput.value = "true";
        }
        input.dispatchEvent(new Event("change", { bubbles: true }));
        setSaveStatus(
            "saving",
            "Recuperamos una respuesta pendiente de este dispositivo. Sincronizando…"
        );
        window.setTimeout(() => syncPendingResponse("recovery"), 80);
        return true;
    }

    answerInputs.forEach((input) => {
        input.addEventListener("change", scheduleResponseSave);
    });

    form.addEventListener("submit", () => {
        window.clearTimeout(debounceTimer);
        elapsedResponseTime();
        writeLocalState({ pendingResponse: true });
    });

    window.addEventListener("online", () => {
        const local = readLocalState();
        if (local?.pendingResponse && local.itemId === itemId) {
            syncPendingResponse("retry");
        } else {
            syncAssessmentState();
            setSaveStatus("saved", "Conexión restablecida.");
        }
    });

    window.addEventListener("offline", () => {
        setSaveStatus(
            "offline",
            "Sin conexión. Los cambios pendientes se conservarán temporalmente en este dispositivo."
        );
    });

    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") {
            writeLocalState();
        }
    });

    window.addEventListener("pagehide", () => {
        writeLocalState();
    });

    if (!restorePendingLocalResponse()) {
        writeLocalState({ pendingResponse: false });
        syncAssessmentState().then((saved) => {
            setSaveStatus(
                saved ? "saved" : "error",
                saved
                    ? "Estado sincronizado con el servidor."
                    : "No pudimos sincronizar el estado todavía."
            );
        });
    }

    window.RiasecAutosave = {
        syncResponse: syncPendingResponse,
        syncState: syncAssessmentState,
        readLocalState,
    };
})();
