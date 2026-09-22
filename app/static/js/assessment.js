/*
 * FASE 7 — Control de estado de la pregunta RIASEC.
 *
 * Responsabilidades:
 * - mantener feedback accesible de selección;
 * - bloquear avance sin respuesta;
 * - coordinar navegación anterior/siguiente con el formulario tradicional;
 * - aplicar transiciones visuales sin alterar el cálculo RIASEC;
 * - ofrecer atajos de teclado que no interfieren con controles nativos.
 */

(() => {
    "use strict";

    const experience = document.querySelector("[data-assessment-experience]");
    const form = document.querySelector("[data-assessment-form]");

    if (!experience || !form) {
        return;
    }

    class AssessmentController {
        constructor(root, assessmentForm) {
            this.root = root;
            this.form = assessmentForm;
            this.card = root.querySelector("[data-swipe-surface]");
            this.feedback = root.querySelector("[data-assessment-feedback]");
            this.answerInputs = Array.from(
                root.querySelectorAll("[data-answer-input]")
            );
            this.answerOptions = Array.from(
                root.querySelectorAll("[data-answer-option]")
            );
            this.nextButton = root.querySelector("[data-action-next]");
            this.previousLink = root.querySelector("[data-action-previous]");
            this.directionInput = root.querySelector(
                "[data-navigation-direction]"
            );
            this.isTransitioning = false;
            this.prefersReducedMotion = window.matchMedia(
                "(prefers-reduced-motion: reduce)"
            ).matches;
            this.transitionDelay = this.prefersReducedMotion ? 0 : 215;

            this.handleFormSubmit = this.handleFormSubmit.bind(this);
            this.handleKeyDown = this.handleKeyDown.bind(this);
        }

        init() {
            document.documentElement.classList.add("js-enabled");
            document.body.classList.add("assessment-mode");

            this.answerInputs.forEach((input) => {
                input.addEventListener("change", () => {
                    this.syncAnswerState(true);
                });
            });

            if (this.nextButton) {
                this.nextButton.addEventListener("click", () => {
                    this.setDirection("next");
                });
            }

            if (this.previousLink) {
                this.previousLink.addEventListener("click", (event) => {
                    event.preventDefault();
                    this.goPrevious("button");
                });
            }

            this.form.addEventListener("submit", this.handleFormSubmit);
            document.addEventListener("keydown", this.handleKeyDown);

            this.syncAnswerState(false);
            this.applyEntranceAnimation();
        }

        getSelectedInput() {
            return this.answerInputs.find((input) => input.checked) || null;
        }

        hasAnswer() {
            return Boolean(this.getSelectedInput());
        }

        setDirection(direction) {
            if (!this.directionInput) {
                return;
            }

            this.directionInput.value = direction === "previous"
                ? "previous"
                : "next";
        }

        getDirection() {
            return this.directionInput?.value === "previous"
                ? "previous"
                : "next";
        }

        syncAnswerState(announceSelection) {
            const selected = this.getSelectedInput();

            this.answerOptions.forEach((option) => {
                const input = option.querySelector("[data-answer-input]");
                option.classList.toggle("is-selected", Boolean(input?.checked));
            });

            if (this.nextButton) {
                this.nextButton.disabled = !selected || this.isTransitioning;
                this.nextButton.dataset.ready = selected ? "true" : "false";
            }

            if (!selected || !announceSelection) {
                return;
            }

            const option = selected.closest("[data-answer-option]");
            const label = option?.querySelector(".answer-option__label")
                ?.textContent?.trim();

            this.announce(
                label
                    ? `Respuesta seleccionada: ${label}. Puedes continuar.`
                    : "Respuesta seleccionada. Puedes continuar.",
                "success"
            );
        }

        announce(message, tone = "neutral") {
            if (!this.feedback) {
                return;
            }

            this.feedback.textContent = message;
            this.feedback.dataset.tone = tone;
        }

        showNeedsAnswerFeedback() {
            this.announce(
                "Selecciona una respuesta antes de avanzar a la siguiente pregunta.",
                "warning"
            );

            if (!this.card) {
                return;
            }

            this.card.classList.remove("is-nudging");
            void this.card.offsetWidth;
            this.card.classList.add("is-nudging");

            window.setTimeout(() => {
                this.card?.classList.remove("is-nudging");
            }, 280);
        }

        setDragOffset(offset, progress) {
            if (this.isTransitioning) {
                return;
            }

            this.root.classList.add("is-dragging");
            this.root.style.setProperty("--swipe-offset", `${offset}px`);
            this.root.style.setProperty(
                "--swipe-progress",
                String(Math.min(Math.max(progress, 0), 1))
            );
        }

        clearDragOffset() {
            this.root.classList.remove("is-dragging");
            this.root.style.setProperty("--swipe-offset", "0px");
            this.root.style.setProperty("--swipe-progress", "0");
        }

        transition(direction, callback) {
            if (this.isTransitioning) {
                return;
            }

            this.isTransitioning = true;
            this.clearDragOffset();
            this.root.classList.add(
                direction === "previous" ? "is-exiting-down" : "is-exiting-up"
            );

            if (this.nextButton) {
                this.nextButton.disabled = true;
            }

            window.sessionStorage.setItem(
                "riasec-assessment-motion",
                direction === "previous" ? "previous" : "next"
            );

            window.setTimeout(callback, this.transitionDelay);
        }

        applyEntranceAnimation() {
            const direction = window.sessionStorage.getItem(
                "riasec-assessment-motion"
            );
            window.sessionStorage.removeItem("riasec-assessment-motion");

            if (this.prefersReducedMotion || !direction) {
                return;
            }

            const className = direction === "previous"
                ? "is-entering-from-top"
                : "is-entering-from-bottom";

            this.root.classList.add(className);
            window.setTimeout(() => {
                this.root.classList.remove(className);
            }, 280);
        }

        goNext(source = "button") {
            if (this.isTransitioning) {
                return;
            }

            if (!this.hasAnswer()) {
                this.showNeedsAnswerFeedback();
                return;
            }

            this.setDirection("next");
            this.announce(
                source === "swipe"
                    ? "Deslizamiento reconocido. Guardando respuesta y avanzando."
                    : "Guardando respuesta y avanzando.",
                "success"
            );
            this.form.requestSubmit(this.nextButton || undefined);
        }

        goPrevious(source = "button") {
            if (this.isTransitioning) {
                return;
            }

            if (!this.previousLink) {
                this.announce(
                    "Estás en la primera pregunta; no hay una pregunta anterior.",
                    "warning"
                );
                return;
            }

            if (this.hasAnswer()) {
                this.setDirection("previous");
                this.announce(
                    source === "swipe"
                        ? "Deslizamiento reconocido. Guardando y regresando."
                        : "Guardando y regresando a la pregunta anterior.",
                    "success"
                );
                this.form.requestSubmit(this.nextButton || undefined);
                return;
            }

            this.transition("previous", () => {
                window.location.assign(this.previousLink.href);
            });
        }

        handleFormSubmit(event) {
            if (this.isTransitioning) {
                event.preventDefault();
                return;
            }

            if (!this.hasAnswer()) {
                event.preventDefault();
                this.showNeedsAnswerFeedback();
                return;
            }

            event.preventDefault();
            const direction = this.getDirection();

            this.transition(direction, () => {
                HTMLFormElement.prototype.submit.call(this.form);
            });
        }

        handleKeyDown(event) {
            if (event.defaultPrevented || this.isTransitioning) {
                return;
            }

            const target = event.target;
            const isInteractive = target instanceof HTMLElement
                && Boolean(
                    target.closest("input, button, a, select, textarea, label")
                );

            if (!isInteractive && /^[1-5]$/.test(event.key)) {
                const input = this.answerInputs.find(
                    (candidate) => candidate.value === event.key
                );
                if (input) {
                    event.preventDefault();
                    input.checked = true;
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                    input.focus();
                }
                return;
            }

            if (isInteractive) {
                return;
            }

            if (event.key === "PageDown") {
                event.preventDefault();
                this.goNext("keyboard");
            } else if (event.key === "PageUp") {
                event.preventDefault();
                this.goPrevious("keyboard");
            }
        }
    }

    const controller = new AssessmentController(experience, form);
    controller.init();

    window.RiasecAssessment = {
        controller,
    };

    document.dispatchEvent(
        new CustomEvent("riasec:assessment-ready", {
            detail: { controller },
        })
    );
})();
