from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib
import pandas as pd

from autocall_replication.research_export import export_research_run

matplotlib.use("Agg")
import matplotlib.pyplot as plt

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "autocall_research.ipynb"


def test_export_research_run_writes_dated_and_latest_artifacts(tmp_path):
    figure, axis = plt.subplots()
    axis.plot([0, 1], [1, 0])

    result = export_research_run(
        output_root=tmp_path,
        run_mode="fast",
        configuration={"risk_paths": 2000, "seed": 42},
        tables={"decision table": pd.DataFrame({"alpha": [0.1], "rmse": [2.5]})},
        figures={"risk overview": figure},
        metadata={"test_status": "reserved"},
        run_started_at=datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc),
    )
    plt.close(figure)

    run_dir = result["run_dir"]
    assert run_dir.name == "2026-09-24_153000_fast"
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "configuration.json").exists()
    assert (run_dir / "tables" / "decision_table.csv").exists()
    assert (run_dir / "figures" / "risk_overview.pdf").exists()
    assert (run_dir / "figures" / "risk_overview.png").exists()
    assert (tmp_path / "latest" / "manifest.json").exists()
    assert not (tmp_path / "runs" / ".2026-09-24_153000_fast.tmp").exists()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["started_at"] == "2026-09-24T15:30:00+00:00"
    assert datetime.fromisoformat(manifest["exported_at"]) >= datetime.fromisoformat(
        manifest["started_at"]
    )


def test_export_copies_promoted_vector_and_raster_figure_without_replotting(tmp_path):
    source_dir = tmp_path / "promoted"
    source_dir.mkdir()
    figure, axis = plt.subplots()
    axis.plot([0, 1], [0, 1])
    figure.savefig(source_dir / "selection.pdf")
    figure.savefig(source_dir / "selection.png")
    plt.close(figure)

    result = export_research_run(
        output_root=tmp_path / "results", run_mode="fast",
        configuration={}, tables={},
        figures={"hyperparameter_selection": source_dir / "selection.png"},
        update_latest=False,
    )
    for extension in ("pdf", "png"):
        assert (result["run_dir"] / "figures" / f"hyperparameter_selection.{extension}").read_bytes() == (
            source_dir / f"selection.{extension}"
        ).read_bytes()


def test_export_rejects_two_start_time_arguments(tmp_path):
    started_at = datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc)

    try:
        export_research_run(
            output_root=tmp_path,
            run_mode="fast",
            configuration={},
            tables={},
            timestamp=started_at,
            run_started_at=started_at,
        )
    except ValueError as error:
        assert "pas les deux" in str(error)
    else:
        raise AssertionError("Deux heures de démarrage concurrentes doivent être refusées.")


def test_repeated_export_from_same_notebook_start_keeps_both_runs(tmp_path):
    started_at = datetime(2026, 10, 4, 9, 12, 34, tzinfo=timezone.utc)
    arguments = {
        "output_root": tmp_path,
        "run_mode": "report",
        "configuration": {"risk_paths": 20_000},
        "tables": {"summary": pd.DataFrame({"rmse": [2.5]})},
        "run_started_at": started_at,
    }

    first = export_research_run(**arguments)
    second = export_research_run(**arguments)

    assert first["run_dir"].name == "2026-10-04_091234_report"
    assert second["run_dir"].name == "2026-10-04_091234_report_2"
    assert first["run_dir"].exists()
    assert second["run_dir"].exists()
    assert json.loads((tmp_path / "latest" / "manifest.json").read_text(encoding="utf-8"))[
        "run_id"
    ] == second["run_id"]


def test_main_notebook_ends_with_structured_export():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    final_source = "".join(notebook["cells"][-1]["source"])

    assert "export_research_run(" in final_source
    assert 'output_root=_project_root / "output"' in final_source
    assert "RUN_FIGURES" in final_source
    assert "retained_policy_weights" in final_source
    assert "run_started_at=NOTEBOOK_RUN_STARTED_AT" in final_source

    first_code_cell = next(cell for cell in notebook["cells"] if cell["cell_type"] == "code")
    first_code_source = "".join(first_code_cell["source"])
    assert "NOTEBOOK_RUN_STARTED_AT = datetime.now().astimezone()" in first_code_source
