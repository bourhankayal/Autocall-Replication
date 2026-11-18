from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
TABLE_PATH = ROOT / "output" / "latest" / "tables" / "risk_summary.csv"
FIGURE_DIR = ROOT / "output" / "latest" / "figures"

FAMILY_ORDER = ("calls_puts", "full")
FAMILY_LABELS = {"calls_puts": "Calls + Puts", "full": "Full (avec binaires)"}
PENALTY_ORDER = ("l0", "l1", "l2", "elastic_net")
PROFILE_ORDER = ("performance", "compromise", "parsimony")
PENALTY_LABELS = {
    "l0": "L0 pénalisée",
    "l1": "L1",
    "l2": "L2 (Ridge)",
    "elastic_net": "Elastic Net",
}
PROFILE_LABELS = {
    "performance": "Performance",
    "compromise": "Compromis",
    "parsimony": "Parcimonie",
}
PROFILE_COLORS = {
    "performance": "#2C7FB8",
    "compromise": "#F28E2B",
    "parsimony": "#59A14F",
}


def main() -> None:
    table = pd.read_csv(TABLE_PATH)
    complete_index = pd.MultiIndex.from_product(
        [PENALTY_ORDER, PROFILE_ORDER], names=["penalty", "profile"]
    )
    metric_pairs = (
        ("gross_rmse", "residual_rmse", "RMSE"),
        ("gross_es_975", "residual_es_975", "Expected Shortfall 97,5 %"),
    )

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 10.0), sharey="row")
    for row_index, family in enumerate(FAMILY_ORDER):
        family_table = (
            table.loc[table["family"] == family]
            .set_index(["penalty", "profile"])
            .reindex(complete_index)
            .reset_index()
        )
        y = np.arange(len(family_table), dtype=float)
        labels = [
            f"{PENALTY_LABELS[penalty]} · {PROFILE_LABELS[profile]}"
            for penalty, profile in zip(
                family_table["penalty"], family_table["profile"]
            )
        ]
        colors = family_table["profile"].map(PROFILE_COLORS).to_numpy()

        for column_index, (gross_column, residual_column, metric_title) in enumerate(
            metric_pairs
        ):
            axis = axes[row_index, column_index]
            residual_values = family_table[residual_column].to_numpy(dtype=float)
            gross_reference = float(family_table[gross_column].dropna().iloc[0])
            axis.scatter(
                residual_values,
                y,
                s=58,
                c=colors,
                edgecolor="white",
                linewidth=0.6,
                zorder=3,
            )
            axis.axvline(
                gross_reference,
                color="0.35",
                linestyle="--",
                linewidth=1.5,
                label=f"Risque brut : {gross_reference:.2f}",
            )
            axis.set_title(metric_title)
            axis.set_xlabel("Montant pour un nominal de 100")
            axis.set_yticks(y)
            axis.set_yticklabels(labels)
            axis.grid(axis="x", alpha=0.25)
            axis.legend(loc="lower right", frameon=True)

        axes[row_index, 0].invert_yaxis()
        axes[row_index, 0].set_ylabel(FAMILY_LABELS[family])

    profile_handles = [
        axes[0, 0].scatter(
            [], [], s=58, color=PROFILE_COLORS[profile], label=PROFILE_LABELS[profile]
        )
        for profile in PROFILE_ORDER
    ]
    fig.legend(
        handles=profile_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.962),
        ncol=3,
        frameon=False,
    )
    fig.suptitle(
        "Contrôle en montants — risque brut et exposition résiduelle",
        y=0.995,
        fontsize=14,
    )
    fig.subplots_adjust(
        left=0.23,
        right=0.98,
        top=0.91,
        bottom=0.07,
        hspace=0.28,
        wspace=0.18,
    )

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        fig.savefig(
            FIGURE_DIR / f"risk_absolute_control.{extension}",
            dpi=220,
            bbox_inches="tight",
        )
    plt.close(fig)


if __name__ == "__main__":
    main()
