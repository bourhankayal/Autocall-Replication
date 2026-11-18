"""Smoke tests for the report-facing synthesis cell without a full Monte Carlo run."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from IPython.display import Markdown


NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "hyperparameter_research.ipynb"


def _synthesis_code() -> str:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "markdown" and "## 7. Fiche de décision" in "".join(cell["source"]):
            return "".join(notebook["cells"][index + 1]["source"])
    raise AssertionError("Synthesis section missing from hyperparameter notebook")


@pytest.mark.parametrize("with_is", [True, False])
def test_decision_dashboard_renders_with_or_without_admissible_is(with_is, monkeypatch, tmp_path):
    monkeypatch.setattr(plt, "show", lambda: None)
    families = ("calls_puts", "full")
    penalties = ("l0", "l1", "l2", "elastic_net")
    levels = (("strict", 5.0), ("intermédiaire", 10.0), ("souple", 15.0))
    budget_rows = [
        {
            "family": family,
            "penalty": penalty,
            "level": level,
            "status": "aucun candidat" if (family, penalty, level) == ("full", "l2", "strict") else "retenu",
            "selected_optimisation_budget_pct_notional": cap,
            "selected_validation_rmse_pct_notional": 2.3 + 0.05 * penalties.index(penalty),
            "selected_validation_es_pct_notional": 6.0 + 0.2 * penalties.index(penalty),
            "selected_n_options_active": 5 + penalties.index(penalty),
        }
        for family in families for penalty in penalties for level, cap in levels
    ]
    stability_rows = [
        {"family": "calls_puts", "penalty": "l1", "size_multiplier": 1.1,
         "base_n_options_active": 5, "n_options_active_mean": 5.5},
        {"family": "full", "penalty": "l0", "size_multiplier": 3.0,
         "base_n_options_active": 5, "n_options_active_mean": 15.0},
    ]
    importance_rows = [
        {"family": "calls_puts", "candidate_index": -1, "mixture_description": "MC standard",
         "worst_precision_ratio_to_mc": 1.0, "median_precision_ratio_to_mc": 1.0,
         "effective_sample_ratio_min": 1.0, "passes_weight_diagnostics": True,
         "recommended": True},
        {"family": "calls_puts", "candidate_index": 0, "mixture_description": "IS — 0 : 70 % ; -1 : 30 %",
         "worst_precision_ratio_to_mc": 1.3, "median_precision_ratio_to_mc": 1.2,
         "effective_sample_ratio_min": 0.7, "passes_weight_diagnostics": True,
         "recommended": False},
    ] if with_is else []
    seen = []
    context = {
        "np": np, "pd": pd, "plt": plt, "display": seen.append, "Markdown": Markdown,
        "SHOW_TECHNICAL_DETAILS": False, "RUN_MODE": "fast",
        "MAIN_FAMILIES": families, "FAMILY_LABELS": {"calls_puts": "Calls + Puts", "full": "Full"},
        "GRID": SimpleNamespace(penalties=penalties, es_budget_pct_notional=(5.0, 10.0, 15.0),
                                tail_alpha_ratios=(1.0, 0.001, 1e-4, 1e-5)),
        "prod": SimpleNamespace(notional=100.0),
        "HYPERPARAMETER_FIGURES": {},
        "final_profile_table": pd.DataFrame([{
            "family": "calls_puts", "penalty": "l1", "profile": "compromise",
            "alpha_relative": 0.1, "l1_ratio": np.nan,
            "validation_rmse": 3.0, "n_options_active": 5, "solution_index": 0,
        }]),
        "alpha_tail_table": pd.DataFrame(columns=[
            "family", "penalty", "solution_index", "validation_mae", "validation_var", "validation_es",
        ]),
        "selected_profile_stability": pd.DataFrame([
            {"family": "calls_puts", "penalty": "l1", "profile": "compromise",
             "solution_index": 0, "n_options_active_mean": 5.5,
             "support_pairwise_jaccard_median": 0.8,
             "common_evaluation_rmse_mean": 2.3,
             "common_evaluation_rmse_std": 0.05},
            {"family": "full", "penalty": "l0", "profile": "compromise",
             "solution_index": 1, "n_options_active_mean": 15.0,
             "support_pairwise_jaccard_median": 0.4,
             "common_evaluation_rmse_mean": 2.5,
             "common_evaluation_rmse_std": 0.15},
        ]),
        "lambda_profile_table": pd.DataFrame(columns=[
            "family", "penalty", "profile", "alpha_relative_tail", "l1_ratio",
            "lambda_es", "validation_rmse", "validation_es", "n_options_active",
        ]),
        "budget_profile_table": pd.DataFrame(columns=[
            "family", "penalty", "profile", "alpha_relative_tail", "l1_ratio",
            "risk_limit_es", "es_budget", "validation_rmse", "validation_es", "n_options_active",
        ]),
        "budget_level_status_table": pd.DataFrame(budget_rows),
            "budget_report_table": pd.DataFrame(budget_rows).loc[
                lambda frame: frame["level"].eq("intermédiaire")
            ].copy(),
        "stability_report_table": pd.DataFrame(stability_rows),
        "stability_size_diagnostic": pd.DataFrame(stability_rows),
        "importance_summary": pd.DataFrame(importance_rows),
        "tail_grid_table": pd.DataFrame([{
            "objective": "penalized_es", "lambda_selection_allowed": False,
        }]),
    }
    try:
        exec(compile(_synthesis_code(), str(NOTEBOOK), "exec"), context)
        assert len(context["decision_report_table"]) > 0
        assert len(context["synthesis_alert_table"]) == len(families)
        assert "decision_dashboard" in context["HYPERPARAMETER_FIGURES"]
        preview = tmp_path / "decision_dashboard.png"
        context["HYPERPARAMETER_FIGURES"]["decision_dashboard"].savefig(preview, dpi=130)
        assert preview.exists() and preview.stat().st_size > 10_000
        assert context["synthesis_alert_table"].loc[
            context["synthesis_alert_table"]["family"].eq("full"),
            "worst_size_multiplier",
        ].iloc[0] == 3.0
        assert any("Plafonds ES" in str(getattr(item, "data", "")) for item in seen)
    finally:
        plt.close("all")
