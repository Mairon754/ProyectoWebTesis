"""Pruebas del control de higiene del repositorio."""

from scripts.check_repo_hygiene import violations


def test_repo_hygiene_rejects_sensitive_and_generated_paths():
    problems = violations(
        [
            ".env",
            "app/__pycache__/service.cpython-314.pyc",
            "data/private/respuestas.csv",
            "artifacts/run/model.pt",
        ]
    )

    assert len(problems) == 4
    assert any(".env" in problem for problem in problems)
    assert any("data/private" in problem for problem in problems)
    assert any("model.pt" in problem for problem in problems)


def test_repo_hygiene_allows_documentation_and_env_example():
    assert violations(
        [
            ".env.example",
            "README.md",
            "docs/TECHNICAL_MANUAL.md",
            "app/services/dataset_service.py",
        ]
    ) == []
