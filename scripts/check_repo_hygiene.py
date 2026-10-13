"""Verificación estática de higiene del repositorio.

Este script no accede a red ni imprime valores de variables de entorno. Su
objetivo es fallar CI cuando Git rastrea archivos que deben permanecer locales.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath


FORBIDDEN_EXACT = {
    ".env",
}
FORBIDDEN_PREFIXES = (
    "data/raw/",
    "data/private/",
    "exports/",
    "artifacts/",
    "checkpoints/",
    "models/checkpoints/",
    "wandb/",
    "mlruns/",
)
FORBIDDEN_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".pt",
    ".pth",
    ".ckpt",
    ".safetensors",
    ".sqlite",
    ".sqlite3",
)
FORBIDDEN_COMPONENTS = {
    "__pycache__",
    ".pytest_cache",
    ".ipynb_checkpoints",
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def violations(paths: list[str]) -> list[str]:
    problems: list[str] = []
    for raw in paths:
        path = raw.replace("\\", "/")
        pure = PurePosixPath(path)

        if path in FORBIDDEN_EXACT:
            problems.append(f"archivo sensible rastreado: {path}")
            continue

        if any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            problems.append(f"artefacto/dato privado rastreado: {path}")
            continue

        if any(path.lower().endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            problems.append(f"binario/artefacto rastreado: {path}")
            continue

        if any(component in FORBIDDEN_COMPONENTS for component in pure.parts):
            problems.append(f"directorio temporal rastreado: {path}")

    return sorted(problems)


def main() -> int:
    try:
        paths = tracked_files()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: no fue posible consultar git ls-files: {exc}", file=sys.stderr)
        return 2

    problems = violations(paths)
    if problems:
        print("Higiene del repositorio: FALLÓ", file=sys.stderr)
        for problem in problems:
            print(f" - {problem}", file=sys.stderr)
        return 1

    print(f"Higiene del repositorio: OK ({len(paths)} archivos rastreados).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
