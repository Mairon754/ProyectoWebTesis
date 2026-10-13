"""Pruebas de consolidación de experiencia, accesibilidad y alcance científico."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_public_copy_uses_pseudonymous_and_non_diagnostic_language():
    base = _read("app/templates/base.html")
    welcome = _read("app/templates/welcome.html")
    results = _read("app/templates/results.html")

    assert "Apoyo a la reflexión, no diagnóstico" in base
    assert "código seudónimo" in welcome
    assert "Tu perfil de intereses RIASEC" in results
    assert "no es un diagnóstico psicológico" in results
    assert "no es percentil ni probabilidad" in results


def test_assessment_keeps_accessible_progress_and_progressive_enhancement():
    assessment = _read("app/templates/assessment.html")

    assert "<progress" in assessment
    assert 'aria-live="polite"' in assessment
    assert "Escuchar pregunta" in assessment
    assert "La evaluación funciona sin JavaScript" in assessment
    assert "los botones del formulario" in assessment


def test_css_preserves_focus_reduced_motion_and_forced_colors_support():
    main_css = _read("app/static/css/main.css")
    assessment_css = _read("app/static/css/assessment.css")

    assert ":focus-visible" in main_css
    assert "prefers-reduced-motion: reduce" in main_css
    assert "forced-colors: active" in main_css
    assert "prefers-reduced-motion: reduce" in assessment_css
    assert "forced-colors: active" in assessment_css


def test_temporary_recovery_is_tab_scoped_and_speech_is_optional():
    autosave = _read("app/static/js/autosave.js")
    speech = _read("app/static/js/speech.js")

    assert "sessionStorage" in autosave
    assert "localStorage" not in autosave
    assert "SpeechSynthesisUtterance" in speech
    assert '"es-CO"' in speech
    assert "mediaDevices" not in speech
    assert "getUserMedia" not in speech
