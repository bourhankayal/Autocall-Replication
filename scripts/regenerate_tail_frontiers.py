"""Regenerate the promoted tail-frontier figures without refitting policies."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output" / "hyperparameters" / "latest"
TABLES = RUN / "tables"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from autocall_replication.replication.hyperparameter_study import plot_tail_frontiers
from export_report_figures_en import translate_figure


def read_table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


def save(figure: plt.Figure, language: str, name: str) -> None:
    destination = ROOT / "overleaf" / "figures" / language
    destination.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination / f"{name}.pdf", bbox_inches="tight")
    figure.savefig(destination / f"{name}.png", dpi=180, bbox_inches="tight")


def main() -> None:
    grid = read_table("tail_grid.csv")
    lambda_profiles = read_table("lambda_es_profiles.csv")
    budget_profiles = read_table("es_budget_profiles.csv")
    family_names = {
        "calls_puts": ("Calls + Puts", "Calls + Puts"),
        "full": ("Full (avec binaires)", "Full (with digitals)"),
    }

    for family, (name_fr, name_en) in family_names.items():
        penalty = "elastic_net"
        subset = grid.loc[grid["family"].eq(family) & grid["penalty"].eq(penalty)].copy()
        result = {
            "lambda_table": subset.loc[subset["objective"].eq("penalized_es")],
            "budget_table": subset.loc[subset["objective"].eq("constrained_es")],
            "lambda_profiles": lambda_profiles.loc[
                lambda_profiles["family"].eq(family)
                & lambda_profiles["penalty"].eq(penalty)
            ],
            "budget_profiles": budget_profiles.loc[
                budget_profiles["family"].eq(family)
                & budget_profiles["penalty"].eq(penalty)
            ],
        }
        output_name = f"tail_frontiers_{family}_elastic_net"

        figure_fr = plot_tail_frontiers(result, nominal=100.0)
        figure_fr.suptitle(
            f"{name_fr} — ELASTIC_NET — RMSE et ES sur validation indépendante",
            fontsize=13,
        )
        save(figure_fr, "fr", output_name)
        plt.close(figure_fr)

        figure_en = plot_tail_frontiers(result, nominal=100.0)
        figure_en.suptitle(
            f"{name_en} — Elastic Net — RMSE and ES on independent validation",
            fontsize=13,
        )
        translate_figure(figure_en)
        save(figure_en, "en", output_name)
        plt.close(figure_en)

    print("Tail-frontier figures regenerated from the frozen report tables.")


if __name__ == "__main__":
    main()
