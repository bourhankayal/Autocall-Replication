"""Rebuild the dated-payment comparison from the saved evaluation table."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "output" / "latest" / "tables" / "method_comparison_by_date.csv"
OUTPUT = ROOT / "output" / "latest" / "figures"


def main() -> None:
    data = pd.read_csv(TABLE)
    families = ("calls_puts", "full")
    family_labels = {"calls_puts": "Calls + Puts", "full": "Full (avec binaires)"}
    objectives = (
        ("par_echeance", "A — ajustement par échéance"),
        ("total_pathwise", "B — ajustement du total"),
    )
    colors = {
        "l0": "#8b54b5",
        "l1": "#1876b9",
        "l2": "#e58b2a",
        "elastic_net": "#258b56",
    }

    figure, axes = plt.subplots(2, len(families), figsize=(14, 7.5), squeeze=False)
    for column, family in enumerate(families):
        panel = data.loc[data["family"].eq(family)].copy()
        for row, (method, objective_label) in enumerate(objectives):
            axis = axes[row, column]
            for penalty in ("l0", "l1", "l2", "elastic_net"):
                subset = panel.loc[
                    panel["penalty"].eq(penalty) & panel["method"].eq(method)
                ].copy()
                if subset.empty:
                    continue
                subset["payment_date"] = pd.to_datetime(subset["payment_date"])
                subset = subset.sort_values("payment_date")
                axis.plot(
                    subset["payment_date"],
                    subset["rmse_pct_notional"],
                    marker="o",
                    linewidth=1.8,
                    color=colors[penalty],
                    label=penalty.upper().replace("ELASTIC_NET", "Elastic Net"),
                )
            axis.set_title(f"{family_labels[family]} — {objective_label}")
            axis.set_xlabel("Date de paiement")
            axis.set_ylabel("RMSE du paiement (% du nominal)")
            axis.set_ylim(bottom=0)
            axis.tick_params(axis="x", rotation=25)
            axis.grid(alpha=0.25)

    legend_items = {}
    for axis in axes.flat:
        handles, labels = axis.get_legend_handles_labels()
        legend_items.update({label: handle for handle, label in zip(handles, labels)})
    figure.legend(
        legend_items.values(),
        legend_items.keys(),
        loc="upper center",
        ncol=len(legend_items),
        frameon=False,
        bbox_to_anchor=(0.5, 0.95),
    )
    figure.suptitle(
        "RMSE des paiements par date : objectifs A et B présentés séparément",
        fontsize=14,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.90))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT / "conditional_method_payment_comparison.pdf", bbox_inches="tight")
    figure.savefig(
        OUTPUT / "conditional_method_payment_comparison.png",
        dpi=180,
        bbox_inches="tight",
    )
    plt.close(figure)
    print("Conditional payment comparison regenerated from the saved table.")


if __name__ == "__main__":
    main()
