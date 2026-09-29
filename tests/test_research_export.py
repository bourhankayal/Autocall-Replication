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
        timestamp=datetime(2026, 9, 24, 15, 30, tzinfo=timezone.utc),
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


def test_main_notebook_ends_with_structured_export():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    final_source = "".join(notebook["cells"][-1]["source"])

    assert "export_research_run(" in final_source
    assert 'output_root=_project_root / "output"' in final_source
    assert "RUN_FIGURES" in final_source
    assert "retained_policy_weights" in final_source
