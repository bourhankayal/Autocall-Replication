"""Commande unique de validation locale du dépôt."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_MODULES = [
    "src/autocall_replication/__init__.py",
    "src/autocall_replication/products.py",
    "src/autocall_replication/monte_carlo.py",
    "src/autocall_replication/replication/__init__.py",
    "src/autocall_replication/replication/common.py",
    "src/autocall_replication/replication/conditional_policy.py",
    "src/autocall_replication/replication/funding.py",
    "src/autocall_replication/replication/importance_sampling.py",
    "src/autocall_replication/replication/mean_payoff.py",
    "src/autocall_replication/replication/pathwise_payoff.py",
    "src/autocall_replication/replication/portfolio_diagnostics.py",
    "src/autocall_replication/replication/price_surface.py",
    "src/autocall_replication/replication/regularization_path.py",
    "src/autocall_replication/replication/optimization.py",
    "src/autocall_replication/replication/semi_static.py",
    "src/autocall_replication/replication/spectral.py",
    "src/autocall_replication/replication/stability.py",
    "src/autocall_replication/replication/static_cashflows.py",
    "src/autocall_replication/replication/risk.py",
    "src/autocall_replication/replication/transaction_costs.py",
    "scripts/reproduce_mc_report.py",
    "scripts/validate.py",
]


def run(command: list[str]) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(command, cwd=PROJECT_ROOT, check=True, env=environment)


def validate_python_sources() -> None:
    print(f"\nValidation syntaxique de {len(PYTHON_MODULES)} fichier(s) Python", flush=True)
    for relative_path in PYTHON_MODULES:
        source_path = PROJECT_ROOT / relative_path
        source = source_path.read_text(encoding="utf-8")
        compile(source, str(source_path), "exec")
        print(f"  OK  {relative_path}")


def validate_notebooks() -> None:
    notebooks = sorted((PROJECT_ROOT / "notebooks").glob("*.ipynb"))
    print(f"\nValidation JSON de {len(notebooks)} notebook(s)", flush=True)
    for notebook in notebooks:
        with notebook.open("r", encoding="utf-8") as stream:
            content = json.load(stream)
        if "cells" not in content or "nbformat" not in content:
            raise ValueError(f"Notebook incomplet : {notebook.name}")
        print(f"  OK  {notebook.name}")


def validate_pyproject() -> None:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    print("\nValidation de pyproject.toml", flush=True)
    with pyproject.open("rb") as stream:
        content = tomllib.load(stream)
    project = content.get("project", {})
    required_fields = {"name", "version", "requires-python", "dependencies"}
    missing = sorted(required_fields - project.keys())
    if missing:
        raise ValueError(f"Champs manquants dans pyproject.toml : {missing}")
    print("  OK  pyproject.toml")


def main() -> int:
    validate_pyproject()
    validate_python_sources()
    validate_notebooks()
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ]
    )
    print("\nValidation terminee avec succes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
