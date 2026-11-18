"""Rebuild the objective-comparison figure from the saved notebook export."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "output" / "latest" / "tables" / "method_objective_tradeoff_table.csv"


def build_figure(data: pd.DataFrame, *, language: str) -> plt.Figure:
    french = language == "fr"
    families = ("calls_puts", "full")
    family_labels = {
        "calls_puts": "Calls + Puts",
        "full": "Full (avec binaires)" if french else "Full (with digitals)",
    }
    penalties = {
        family: [
            penalty
            for penalty in ("l0", "l1", "l2", "elastic_net")
            if penalty in set(data.loc[data["family"].eq(family), "penalty"])
        ]
        for family in families
    }
    metrics = (
        (
            "rmse_paiements_A_pct",
            "rmse_paiements_B_pct",
            "RMSE des paiements" if french else "Dated-payment RMSE",
        ),
        (
            "rmse_total_A_pct",
            "rmse_total_B_pct",
            "RMSE du total actualisé" if french else "Discounted-total RMSE",
        ),
    )
    objective_labels = (
        "A — par échéance" if french else "A — payment dates",
        "B — total" if french else "B — pathwise total",
    )
    colors = ("#2778b4", "#df842c")

    figure, axes = plt.subplots(2, 2, figsize=(12, 7.2), squeeze=False)
    for column, family in enumerate(families):
        panel = data.loc[data["family"].eq(family)].set_index("penalty")
        positions = np.arange(len(penalties[family]))
        for row, (column_a, column_b, metric_title) in enumerate(metrics):
            axis = axes[row, column]
            width = 0.36
            for offset, value_column, label, color in zip(
                (-width / 2, width / 2),
                (column_a, column_b),
                objective_labels,
                colors,
            ):
                values = panel.loc[penalties[family], value_column].astype(float).to_numpy()
                bars = axis.bar(
                    positions + offset,
                    values,
                    width=width,
                    color=color,
                    label=label,
                )
                axis.bar_label(bars, fmt="%.2f", padding=2, fontsize=8)
            axis.set_title(f"{family_labels[family]} — {metric_title}")
            axis.set_xticks(
                positions,
                [
                    penalty.upper().replace("ELASTIC_NET", "Elastic Net")
                    for penalty in penalties[family]
                ],
            )
            axis.set_ylabel("% du nominal" if french else "% of notional")
            axis.set_ylim(bottom=0)
            axis.grid(axis="y", alpha=0.2)

    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        ncol=2,
        frameon=False,
        bbox_to_anchor=(0.5, 0.94),
    )
    figure.suptitle(
        "Effet du choix de l’objectif sur les paiements et le total actualisé"
        if french
        else "Effect of the fitting objective on dated payments and discounted totals",
        fontsize=14,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.89))
    return figure


def main() -> None:
    data = pd.read_csv(TABLE)
    for language in ("fr", "en"):
        figure = build_figure(data, language=language)
        destination = ROOT / "overleaf" / "figures" / language
        destination.mkdir(parents=True, exist_ok=True)
        figure.savefig(destination / "method_objective_tradeoff.pdf", bbox_inches="tight")
        figure.savefig(
            destination / "method_objective_tradeoff.png",
            dpi=180,
            bbox_inches="tight",
        )
        plt.close(figure)
    print("Objective-comparison figures regenerated from the saved table.")


if __name__ == "__main__":
    main()
