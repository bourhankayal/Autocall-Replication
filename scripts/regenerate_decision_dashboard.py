"""Regenerate the decision dashboard from an already completed hyperparameter run.

This script only reads exported CSV tables.  It does not recalibrate a policy,
simulate paths, or rerun the hyperparameter study.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "output" / "hyperparameters" / "latest" / "tables"
LATEST_FIGURES = ROOT / "output" / "hyperparameters" / "latest" / "figures"
OVERLEAF_FIGURES = ROOT / "overleaf" / "figures"

FAMILY_COLORS = {"calls_puts": "#2563a6", "full": "#d97706"}
PENALTY_MARKERS = {"l0": "s", "l1": "o", "l2": "^", "elastic_net": "D"}
PENALTY_LABELS = {"l0": "L0", "l1": "L1", "l2": "L2", "elastic_net": "Elastic Net"}
ANNOTATION_OFFSETS = {"l0": (6, 5), "l1": (6, -12), "l2": (6, 5), "elastic_net": (6, 7)}


TEXT = {
    "fr": {
        "families": {"calls_puts": "Calls + Puts", "full": "Full (avec binaires)"},
        "title": "Profils compromis : RMSE et nombre d’options",
        "tradeoff_x": "Options actives dans toute la politique (axe logarithmique)",
        "tradeoff_y": "RMSE de validation (% du nominal)",
        "family_legend": "Famille",
    },
    "en": {
        "families": {"calls_puts": "Calls + Puts", "full": "Full (with digitals)"},
        "title": "Compromise profiles: RMSE and option count",
        "tradeoff_x": "Active options in the whole policy (log scale)",
        "tradeoff_y": "Validation RMSE (% of notional)",
        "family_legend": "Family",
    },
}


def _load_profiles() -> pd.DataFrame:
    profiles = pd.read_csv(TABLES / "selected_regularisation_profiles.csv")
    profiles = profiles.loc[profiles["profile"].eq("compromise")].drop_duplicates(
        ["family", "penalty", "solution_index"]
    )
    return profiles


def build_dashboard(language: str) -> plt.Figure:
    labels = TEXT[language]
    profiles = _load_profiles()

    figure, tradeoff_axis = plt.subplots(figsize=(10.5, 5.6), constrained_layout=True)

    for row in profiles.itertuples():
        tradeoff_axis.scatter(
            row.n_options_active,
            row.validation_rmse,
            s=95,
            marker=PENALTY_MARKERS[row.penalty],
            color=FAMILY_COLORS[row.family],
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
        tradeoff_axis.annotate(
            PENALTY_LABELS[row.penalty],
            (row.n_options_active, row.validation_rmse),
            xytext=ANNOTATION_OFFSETS[row.penalty],
            textcoords="offset points",
            fontsize=8,
        )
    tradeoff_axis.set_xscale("log")
    tradeoff_axis.set_xlabel(labels["tradeoff_x"])
    tradeoff_axis.set_ylabel(labels["tradeoff_y"])
    tradeoff_axis.grid(alpha=0.22)

    family_handles = [
        Line2D(
            [],
            [],
            linestyle="None",
            marker="o",
            color=color,
            label=labels["families"][family],
        )
        for family, color in FAMILY_COLORS.items()
    ]
    tradeoff_axis.legend(
        handles=family_handles,
        title=labels["family_legend"],
        loc="upper right",
        ncol=2,
        fontsize=8,
        title_fontsize=8,
    )
    figure.suptitle(labels["title"], fontsize=14)
    return figure


def save_dashboard(language: str) -> None:
    figure = build_dashboard(language)
    targets = [OVERLEAF_FIGURES / language]
    if language == "fr":
        targets.append(LATEST_FIGURES)
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        figure.savefig(target / "decision_dashboard.pdf", bbox_inches="tight")
        figure.savefig(target / "decision_dashboard.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    save_dashboard("fr")
    save_dashboard("en")
    print("Decision dashboards regenerated from completed-run CSV exports.")
