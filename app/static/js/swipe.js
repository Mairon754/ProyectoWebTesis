/*
 * FASE 7 — Navegación vertical mediante swipe / drag.
 *
 * Implementa Pointer Events cuando están disponibles y Touch Events como
 * respaldo. Los gestos que empiezan sobre controles interactivos se ignoran
 * para impedir cambios accidentales mientras se selecciona una respuesta.
 */

(() => {
    "use strict";

    const MIN_DISTANCE = 88;
    const MAX_DURATION = 1000;
    const DIRECTION_RATIO = 1.25;
    const PREVENT_SCROLL_DISTANCE = 12;
    const MAX_VISUAL_OFFSET = 96;

    const interactiveSelector = [
        "input",
        "button",
        "a",
        "label",
        "select",
        "textarea",
        "[role='button']",
    ].join(",");

    class VerticalSwipeNavigator {
        constructor(controller) {
            this.controller = controller;
            this.surface = controller.card;
            this.active = false;
            this.pointerId = null;
            this.startX = 0;
            this.startY = 0;
            this.lastX = 0;
            this.lastY = 0;
            this.startedAt = 0;

            this.onPointerDown = this.onPointerDown.bind(this);
            this.onPointerMove = this.onPointerMove.bind(this);
            this.onPointerUp = this.onPointerUp.bind(this);
            this.onPointerCancel = this.onPointerCancel.bind(this);
            this.onTouchStart = this.onTouchStart.bind(this);
            this.onTouchMove = this.onTouchMove.bind(this);
            this.onTouchEnd = this.onTouchEnd.bind(this);
            this.onTouchCancel = this.onTouchCancel.bind(this);
        }

        init() {
            if (!this.surface) {
                return;
            }

            if ("PointerEvent" in window) {
                this.surface.addEventListener("pointerdown", this.onPointerDown);
                this.surface.addEventListener("pointermove", this.onPointerMove);
                this.surface.addEventListener("pointerup", this.onPointerUp);
                this.surface.addEventListener(
                    "pointercancel",
                    this.onPointerCancel
                );
            }

            this.surface.addEventListener(
                "touchstart",
                this.onTouchStart,
                { passive: true }
            );
            this.surface.addEventListener(
                "touchmove",
                this.onTouchMove,
                { passive: false }
            );
            this.surface.addEventListener("touchend", this.onTouchEnd);
            this.surface.addEventListener("touchcancel", this.onTouchCancel);
        }

        shouldIgnoreStart(target) {
            return this.controller.isTransitioning
                || !(target instanceof Element)
                || Boolean(target.closest(interactiveSelector));
        }

        beginGesture(x, y, pointerId = null) {
            this.active = true;
            this.pointerId = pointerId;
            this.startX = x;
            this.startY = y;
            this.lastX = x;
            this.lastY = y;
            this.startedAt = performance.now();
        }

        updateGesture(x, y) {
            if (!this.active) {
                return;
            }

            this.lastX = x;
            this.lastY = y;

            const deltaX = x - this.startX;
            const deltaY = y - this.startY;
            const verticalDistance = Math.abs(deltaY);
            const horizontalDistance = Math.abs(deltaX);

            if (
                verticalDistance < PREVENT_SCROLL_DISTANCE
                || verticalDistance <= horizontalDistance
            ) {
                return;
            }

            const visualOffset = Math.max(
                -MAX_VISUAL_OFFSET,
                Math.min(MAX_VISUAL_OFFSET, deltaY)
            );
            const progress = Math.min(verticalDistance / MIN_DISTANCE, 1);

            this.controller.setDragOffset(visualOffset, progress);
        }

        finishGesture() {
            if (!this.active) {
                return;
            }

            const deltaX = this.lastX - this.startX;
            const deltaY = this.lastY - this.startY;
            const verticalDistance = Math.abs(deltaY);
            const horizontalDistance = Math.abs(deltaX);
            const duration = performance.now() - this.startedAt;
            const hasDistance = verticalDistance >= MIN_DISTANCE;
            const isVertical = verticalDistance
                >= horizontalDistance * DIRECTION_RATIO;
            const hasValidDuration = duration <= MAX_DURATION;

            this.resetGesture();

            if (!hasDistance || !isVertical || !hasValidDuration) {
                this.controller.clearDragOffset();
                return;
            }

            if (deltaY < 0) {
                this.controller.goNext("swipe");
            } else {
                this.controller.goPrevious("swipe");
            }
        }

        resetGesture() {
            this.active = false;
            this.pointerId = null;
        }

        cancelGesture() {
            this.resetGesture();
            this.controller.clearDragOffset();
        }

        onPointerDown(event) {
            if (!event.isPrimary || this.shouldIgnoreStart(event.target)) {
                return;
            }

            if (event.pointerType === "touch") {
                return;
            }

            if (event.pointerType === "mouse" && event.button !== 0) {
                return;
            }

            this.beginGesture(event.clientX, event.clientY, event.pointerId);
            this.surface.setPointerCapture?.(event.pointerId);
        }

        onPointerMove(event) {
            if (!this.active || event.pointerId !== this.pointerId) {
                return;
            }

            this.updateGesture(event.clientX, event.clientY);
        }

        onPointerUp(event) {
            if (!this.active || event.pointerId !== this.pointerId) {
                return;
            }

            this.lastX = event.clientX;
            this.lastY = event.clientY;
            this.surface.releasePointerCapture?.(event.pointerId);
            this.finishGesture();
        }

        onPointerCancel(event) {
            if (this.pointerId === event.pointerId) {
                this.cancelGesture();
            }
        }

        onTouchStart(event) {
            if (
                event.touches.length !== 1
                || this.shouldIgnoreStart(event.target)
            ) {
                return;
            }

            const touch = event.touches[0];
            this.beginGesture(touch.clientX, touch.clientY);
        }

        onTouchMove(event) {
            if (!this.active || event.touches.length !== 1) {
                return;
            }

            const touch = event.touches[0];
            const deltaX = touch.clientX - this.startX;
            const deltaY = touch.clientY - this.startY;

            if (
                Math.abs(deltaY) > PREVENT_SCROLL_DISTANCE
                && Math.abs(deltaY) > Math.abs(deltaX)
            ) {
                event.preventDefault();
            }

            this.updateGesture(touch.clientX, touch.clientY);
        }

        onTouchEnd() {
            this.finishGesture();
        }

        onTouchCancel() {
            this.cancelGesture();
        }
    }

    const initialize = (controller) => {
        if (!controller || controller.swipeNavigator) {
            return;
        }

        const navigator = new VerticalSwipeNavigator(controller);
        navigator.init();
        controller.swipeNavigator = navigator;
    };

    if (window.RiasecAssessment?.controller) {
        initialize(window.RiasecAssessment.controller);
    } else {
        document.addEventListener(
            "riasec:assessment-ready",
            (event) => initialize(event.detail?.controller),
            { once: true }
        );
    }
})();
