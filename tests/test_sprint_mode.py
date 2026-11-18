"""The visual-preview mode must stay separate from research selections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autocall_replication.replication.hyperparameter_study import (
    promote_hyperparameter_selection,
)


ROOT = Path(__file__).resolve().parents[1]


def _notebook(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_sprint_configuration_exists_in_both_notebooks() -> None:
    main = _notebook("notebooks/autocall_research.ipynb")
    hyper = _notebook("notebooks/hyperparameter_research.ipynb")
    main_code = "\n".join("".join(cell["source"]) for cell in main["cells"] if cell["cell_type"] == "code")
    hyper_code = "\n".join("".join(cell["source"]) for cell in hyper["cells"] if cell["cell_type"] == "code")

    for code in (main_code, hyper_code):
        assert '"sprint": {' in code
        assert 'RUN_MODE = "fast"' in code  # Default research workflow is unchanged.
    assert '"risk_paths": 250' in main_code
    assert 'n_alphas=5' in hyper_code
    assert 'selected_hyperparameters.json' in main_code
    assert 'PROMOTE_THIS_RUN and RUN_MODE == "sprint"' in hyper_code


def test_sprint_selection_cannot_be_promoted(tmp_path: Path) -> None:
    run_dir = tmp_path / "sprint_run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text('{"completed": true}', encoding="utf-8")
    (run_dir / "selected_hyperparameters.json").write_text(
        '{"run_mode": "sprint"}', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="SPRINT"):
        promote_hyperparameter_selection(
            source_run_dir=run_dir,
            destination=tmp_path / "selected_hyperparameters_sprint.json",
            current_configuration={},
        )
