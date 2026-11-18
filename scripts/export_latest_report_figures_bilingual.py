"""Export the latest REPORT result figures in French and English.

The script reads frozen CSV outputs only. It does not recalibrate a policy,
resimulate paths, or open the reserved final-test sample.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "output" / "latest" / "tables"
FIGURES = ROOT / "overleaf" / "figures"

FAMILY = {
    "fr": {"calls_puts": "Calls + Puts", "full": "Full (avec binaires)"},
    "en": {"calls_puts": "Calls + Puts", "full": "Full (with digitals)"},
}
PROFILE = {
    "fr": {"performance": "Performance", "compromise": "Compromis", "parsimony": "Parcimonie"},
    "en": {"performance": "Performance", "compromise": "Compromise", "parsimony": "Parsimony"},
}
PENALTY = {
    "fr": {"l0": "L0", "l1": "L1", "l2": "L2", "elastic_net": "Elastic Net"},
    "en": {"l0": "L0", "l1": "L1", "l2": "L2", "elastic_net": "Elastic Net"},
}


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


def save(fig: plt.Figure, language: str, name: str) -> None:
    destination = FIGURES / language
    destination.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(destination / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def compromise_comparison(language: str) -> None:
    data = read("report_profile_outcomes.csv")
    order = [
        ("calls_puts", "elastic_net"), ("calls_puts", "l0"),
        ("calls_puts", "l1"), ("calls_puts", "l2"),
        ("full", "elastic_net"), ("full", "l0"), ("full", "l1"), ("full", "l2"),
    ]
    rows = []
    for family, penalty in order:
        row = data.loc[data["family"].eq(family) & data["penalty"].eq(penalty)].iloc[0]
        rows.append(row)
    labels = [f"{FAMILY[language][r.family]} / {PENALTY[language][r.penalty]}" for r in rows]
    colors = ["#2b9c6b" if r.family == "calls_puts" else "#e38d22" for r in rows]
    y = np.arange(len(rows))
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 6.1), sharey=True)
    axes[0].barh(y, [r.residual_rmse_pct_notional for r in rows], color=colors)
    axes[1].barh(y, [r.residual_es_975_pct_notional for r in rows], color=colors)
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    for axis in axes:
        axis.grid(axis="x", alpha=0.25)
        axis.set_axisbelow(True)
    if language == "fr":
        fig.suptitle("Profils compromis — évaluation indépendante commune", fontsize=15)
        axes[0].set_title("Erreur globale — RMSE")
        axes[1].set_title("Risque de queue — ES 97,5 %")
        xlabel = "% du nominal"
        threshold = "Plafond indicatif d’ES : 10 %"
    else:
        fig.suptitle("Compromise profiles — common independent evaluation", fontsize=15)
        axes[0].set_title("Overall error — RMSE")
        axes[1].set_title("Tail risk — ES 97.5%")
        xlabel = "% of notional"
        threshold = "Indicative ES ceiling: 10%"
    axes[0].set_xlabel(xlabel)
    axes[1].set_xlabel(xlabel)
    axes[1].axvline(10.0, color="#b33a3a", linestyle="--", linewidth=1.5, label=threshold)
    axes[1].legend(loc="lower right")
    fig.tight_layout()
    save(fig, language, "report_compromise_comparison")


def importance_sampling(language: str) -> None:
    data = read("report_importance_ci_table.csv")
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 7.4), sharex=True)
    for axis, family in zip(axes, ("calls_puts", "full")):
        subset = data.loc[data["Famille"].eq(family)].copy()
        subset["rank"] = subset["Pénalité"].map({"l0": 0, "l1": 1, "l2": 2, "elastic_net": 3}) * 3 + subset["Profil"].map({"performance": 0, "compromise": 1, "parsimony": 2})
        subset = subset.sort_values("rank")
        y = np.arange(len(subset))
        labels = [f"{p.upper()} · {PROFILE[language][q]}" for p, q in zip(subset["Pénalité"], subset["Profil"])]
        mc = subset["standard_es_975_pct_notional"].to_numpy()
        is_ = subset["importance_es_975_pct_notional"].to_numpy()
        axis.errorbar(mc, y - 0.10, xerr=[mc - subset["standard_ci_low"], subset["standard_ci_high"] - mc], fmt="o", color="#666666", capsize=3, label="Monte Carlo")
        axis.errorbar(is_, y + 0.10, xerr=[is_ - subset["importance_ci_low"], subset["importance_ci_high"] - is_], fmt="o", color="#2ca02c", capsize=3, label="Importance sampling")
        axis.set_yticks(y, labels)
        axis.invert_yaxis()
        axis.set_title(FAMILY[language][family])
        axis.grid(axis="x", alpha=0.25)
        axis.legend()
    title = "Même ES 97,5 % estimée par deux méthodes — portefeuilles figés" if language == "fr" else "Same 97.5% ES estimated by two methods — frozen portfolios"
    xlabel = "ES résiduelle (% du nominal)" if language == "fr" else "Residual ES (% of notional)"
    fig.suptitle(title, fontsize=15)
    for axis in axes:
        axis.set_xlabel(xlabel)
    fig.tight_layout()
    save(fig, language, "importance_sampling_es")


def tail_concentration(language: str) -> None:
    data = read("tail_concentration_curve.csv")
    data = data.loc[data["penalty"].eq("elastic_net") & data["profile"].eq("compromise") & data["level"].eq(0.975)]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.0), sharex=True, sharey=True)
    for axis, family in zip(axes, ("calls_puts", "full")):
        subset = data.loc[data["family"].eq(family)]
        for method, color, style, label_fr, label_en in [
            ("Monte-Carlo standard", "#2b7bba", "-", "Monte Carlo", "Monte Carlo"),
            ("Importance sampling", "#2ca02c", "--", "Importance sampling", "Importance sampling"),
        ]:
            part = subset.loc[subset["estimator"].eq(method)]
            axis.plot(100 * part["tail_mass_fraction"], 100 * part["positive_tail_loss_share"], marker="o", color=color, linestyle=style, label=label_fr if language == "fr" else label_en)
        uniform = "Risque uniformément réparti" if language == "fr" else "Uniformly distributed risk"
        axis.plot([0, 100], [0, 100], color="#aaaaaa", linestyle=":", label=uniform)
        axis.set_title(FAMILY[language][family])
        axis.grid(alpha=0.25)
        axis.set_xlabel("Part cumulée de la masse de queue (%)" if language == "fr" else "Cumulative share of tail mass (%)")
    axes[0].set_ylabel("Part cumulée de la perte positive de queue (%)" if language == "fr" else "Cumulative share of positive tail loss (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3)
    title = "Concentration de l’ES 97,5 % — Elastic Net, profil compromis" if language == "fr" else "Concentration of 97.5% ES — Elastic Net, compromise profile"
    fig.suptitle(title, fontsize=15)
    fig.tight_layout(rect=(0, 0.10, 1, 0.95))
    save(fig, language, "tail_risk_concentration")


def tail_four_experiments(language: str) -> None:
    data = read("report_tail_risk_experiment_table.csv")
    second = data.loc[data["calibration_sampling"].ne("standard_mc"), "calibration_sampling"].unique()
    if len(second) != 1:
        raise ValueError("Expected exactly one second calibration design.")
    second_plan = second.item()
    plan_label = "IS" if second_plan == "importance_sampling" else "MC bis" if language == "fr" else "MC repeat"
    controls = ("rmse_only", "es_constraint")
    order = [(plan, control) for plan in ("standard_mc", second_plan) for control in controls]
    constraint = "contrainte ES" if language == "fr" else "ES constraint"
    labels = [f"{plan} / {metric}" for plan in ("MC", plan_label) for metric in ("RMSE", constraint)]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.0))
    x = np.arange(4)
    width = 0.36
    for offset, family, color in [(-width / 2, "calls_puts", "#2b7bba"), (width / 2, "full", "#2ca02c")]:
        subset = data.loc[data["Famille"].eq(family)]
        rows = [subset.loc[subset["calibration_sampling"].eq(s) & subset["risk_control"].eq(c)].iloc[0] for s, c in order]
        axes[0].bar(x + offset, [r.evaluation_rmse_pct_notional for r in rows], width, color=color, label=FAMILY[language][family])
        axes[1].bar(x + offset, [r.evaluation_es_pct_notional for r in rows], width, color=color, label=FAMILY[language][family])
    for axis in axes:
        axis.set_xticks(x, labels, rotation=16)
        axis.grid(axis="y", alpha=0.25)
        axis.legend()
    if language == "fr":
        fig.suptitle("Effet de la contrainte d’ES selon le plan de calibration", fontsize=15)
        axes[0].set_title("Erreur globale hors calibration")
        axes[1].set_title("Risque extrême hors calibration")
        axes[0].set_ylabel("RMSE (% du nominal)")
        axes[1].set_ylabel("ES 97,5 % (% du nominal)")
    else:
        fig.suptitle("Effect of the ES constraint by calibration design", fontsize=15)
        axes[0].set_title("Out-of-calibration overall error")
        axes[1].set_title("Out-of-calibration tail risk")
        axes[0].set_ylabel("RMSE (% of notional)")
        axes[1].set_ylabel("ES 97.5% (% of notional)")
    fig.tight_layout()
    save(fig, language, "tail_risk_four_experiments")


def method_objective_tradeoff(language: str) -> None:
    data = read("method_objective_tradeoff_table.csv")
    penalties = ["l0", "l1", "l2", "elastic_net"]
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.0))
    for column, family in enumerate(("calls_puts", "full")):
        subset = data.loc[data["family"].eq(family)]
        available = [p for p in penalties if p in set(subset["penalty"])]
        x = np.arange(len(available))
        for row, (metric, title_fr, title_en) in enumerate([
            ("rmse_paiements", "RMSE des paiements", "Payment RMSE"),
            ("rmse_total", "RMSE du total actualisé", "Discounted-total RMSE"),
        ]):
            axis = axes[row, column]
            ordered = subset.set_index("penalty").loc[available]
            axis.bar(x - 0.18, ordered[f"{metric}_A_pct"], 0.36, color="#2b7bba", label="A / par échéance" if language == "fr" else "A / by payment date")
            axis.bar(x + 0.18, ordered[f"{metric}_B_pct"], 0.36, color="#e38d22", label="B / total")
            axis.set_xticks(x, ["Elastic Net" if p == "elastic_net" else p.upper() for p in available])
            axis.set_title(f"{FAMILY[language][family]} — {title_fr if language == 'fr' else title_en}")
            axis.set_ylabel("% du nominal" if language == "fr" else "% of notional")
            axis.grid(axis="y", alpha=0.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.995))
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, language, "method_objective_tradeoff")


def main() -> None:
    for language in ("fr", "en"):
        compromise_comparison(language)
        if (TABLES / "report_importance_ci_table.csv").is_file():
            importance_sampling(language)
        if (TABLES / "tail_concentration_curve.csv").is_file():
            tail_concentration(language)
        tail_four_experiments(language)
        method_objective_tradeoff(language)


if __name__ == "__main__":
    main()
