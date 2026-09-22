/*
 * Lector de preguntas RIASEC — reparación posterior a Fase 11.
 * Lee únicamente el enunciado actual y mantiene el backend como fuente
 * oficial de las respuestas y metadatos.
 */
(() => {
    "use strict";

    const root = document.querySelector("[data-assessment-experience]");
    const controls = document.querySelector("[data-speech-controls]");

    if (!root || !controls) {
        return;
    }

    const question = root.querySelector("[data-question-text]");
    const readButton = controls.querySelector("[data-speech-read]");
    const pauseButton = controls.querySelector("[data-speech-pause]");
    const resumeButton = controls.querySelector("[data-speech-resume]");
    const stopButton = controls.querySelector("[data-speech-stop]");
    const status = controls.querySelector("[data-speech-status]");
    const ttsUsedInput = root.querySelector("[data-tts-used]");

    const supported = Boolean(
        window.speechSynthesis
        && window.SpeechSynthesisUtterance
    );

    let utterance = null;
    let selectedVoice = null;

    function announce(message) {
        if (status) {
            status.textContent = message;
        }
    }

    function setState(state) {
        controls.dataset.speechState = state;
        const speaking = state === "speaking";
        const paused = state === "paused";
        const active = speaking || paused;

        if (readButton) readButton.disabled = !supported;
        if (pauseButton) pauseButton.disabled = !speaking;
        if (resumeButton) resumeButton.disabled = !paused;
        if (stopButton) stopButton.disabled = !active;
    }

    function chooseSpanishVoice() {
        if (!supported) return null;

        const voices = window.speechSynthesis.getVoices() || [];
        const spanish = voices.filter((voice) =>
            String(voice.lang || "").toLowerCase().startsWith("es")
        );

        return (
            spanish.find((voice) =>
                String(voice.lang || "").toLowerCase() === "es-co"
            )
            || spanish.find((voice) => voice.default)
            || spanish[0]
            || null
        );
    }

    function refreshVoice() {
        selectedVoice = chooseSpanishVoice();
    }

    function markTtsUsed() {
        if (ttsUsedInput) {
            ttsUsedInput.value = "true";
        }
    }

    function reset(message = "Lectura finalizada.") {
        utterance = null;
        setState("idle");
        announce(message);
    }

    function readQuestion() {
        if (!supported) {
            announce(
                "Este navegador no dispone de lectura en voz alta. "
                + "Puedes continuar la evaluación normalmente."
            );
            return;
        }

        const text = String(question?.textContent || "")
            .replace(/\\s+/g, " ")
            .trim();

        if (!text) {
            announce("No se encontró el texto de la pregunta actual.");
            return;
        }

        window.speechSynthesis.cancel();
        refreshVoice();
        markTtsUsed();

        utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = selectedVoice?.lang || "es-CO";
        utterance.rate = 0.95;
        utterance.pitch = 1;
        utterance.volume = 1;
        if (selectedVoice) utterance.voice = selectedVoice;

        utterance.onstart = () => {
            setState("speaking");
            announce("Leyendo la pregunta en voz alta.");
        };
        utterance.onend = () => reset();
        utterance.onerror = (event) => {
            if (["canceled", "interrupted"].includes(event.error)) {
                reset("Lectura detenida.");
                return;
            }
            reset(
                "No fue posible reproducir la lectura. "
                + "Puedes responder la pregunta normalmente."
            );
        };

        window.speechSynthesis.speak(utterance);
    }

    function pauseSpeech() {
        if (!supported || !window.speechSynthesis.speaking) return;
        window.speechSynthesis.pause();
        setState("paused");
        announce("Lectura pausada.");
    }

    function resumeSpeech() {
        if (!supported || !window.speechSynthesis.paused) return;
        window.speechSynthesis.resume();
        setState("speaking");
        announce("Lectura reanudada.");
    }

    function stopSpeech() {
        if (!supported) return;
        window.speechSynthesis.cancel();
        reset("Lectura detenida.");
    }

    if (!supported) {
        setState("unsupported");
        announce(
            "El lector de voz no está disponible en este navegador. "
            + "La evaluación sigue funcionando normalmente."
        );
        return;
    }

    refreshVoice();
    if (typeof window.speechSynthesis.addEventListener === "function") {
        window.speechSynthesis.addEventListener("voiceschanged", refreshVoice);
    }

    readButton?.addEventListener("click", readQuestion);
    pauseButton?.addEventListener("click", pauseSpeech);
    resumeButton?.addEventListener("click", resumeSpeech);
    stopButton?.addEventListener("click", stopSpeech);

    window.addEventListener("pagehide", () => {
        window.speechSynthesis.cancel();
    });

    setState("idle");

    window.RiasecSpeech = {
        read: readQuestion,
        pause: pauseSpeech,
        resume: resumeSpeech,
        stop: stopSpeech,
        isSupported: supported,
    };
})();
