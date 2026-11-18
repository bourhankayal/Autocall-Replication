"""Rebuild the promoted REPORT figures with English labels only.

The script reads the frozen CSV exports from the promoted hyperparameter run.
It does not refit a policy, resimulate paths, or open the reserved test sample.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.text import Text


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "output" / "hyperparameters" / "latest"
TABLES = RUN / "tables"
OUTPUT = ROOT / "overleaf" / "figures" / "en"
sys.path.insert(0, str(ROOT / "src"))

from autocall_replication.replication.hyperparameter_study import (  # noqa: E402
    plot_alpha_tail_frontier,
    plot_regularization_grid,
    plot_rho_grid,
    plot_seed_robustness,
    plot_tail_frontiers,
)


FAMILY_NAMES = {"calls_puts": "Calls + Puts", "full": "Full (with digitals)"}
PENALTY_NAMES = {"l0": "L0", "l1": "L1", "l2": "L2", "elastic_net": "Elastic Net"}


TRANSLATIONS = {
    "Calls + Puts (sans binaires)": "Calls + Puts (without digitals)",
    "Full (Calls + Puts + binaires)": "Full (Calls + Puts + digitals)",
    "Full (avec binaires)": "Full (with digitals)",
    "Erreur de validation (RMSE)": "Validation error (RMSE)",
    "Nombre d'options actives": "Number of active options",
    "Ratio L1 ρ": "L1 ratio ρ",
    "Alpha relatif (fort en haut → faible en bas)": "Relative alpha (strong at top → weak at bottom)",
    "Alpha relatif (régularisation forte → faible)":
        "Relative alpha (strong → weak regularisation)",
    "RMSE (% du nominal)": "RMSE (% of notional)",
    "Options actives": "Active options",
    "Elastic Net — grille conjointe (ρ, alpha) : trois profils retenus par famille":
        "Elastic Net — joint (ρ, alpha) grid: three retained profiles per family",
    "P : performance · C : compromis · S : parcimonie · Gris : non convergé ou absent.":
        "P: performance · C: compromise · S: parsimony · Grey: non-converged or missing.",
    "Non convergé : état à l'arrêt du solveur": "Non-converged: solver stopping state",
    "Croix grises : métriques du portefeuille à l'arrêt du solveur":
        "Grey crosses: portfolio metrics at solver termination",
    "jusqu'à": "up to",
    "itérations": "iterations",
    "; valeurs provisoires, exclues de la sélection.":
        "; provisional values excluded from selection.",
    "Compromis": "Compromise",
    "Parcimonie": "Parsimony",
    "convergés": "converged",
    "RMSE de validation (% du nominal)": "Validation RMSE (% of notional)",
    "erreur de validation": "validation error",
    "taille du portefeuille": "portfolio size",
    "Boîte : 25e–75e percentile": "Box: 25th–75th percentile",
    "Moustaches : limite à 1,5 × IQR": "Whiskers: 1.5 × IQR limit",
    "Trait orange : médiane": "Orange line: median",
    "Triangle vert : moyenne": "Green triangle: mean",
    "Point bleu : recalibration": "Blue point: recalibration",
    "Croix grise : non convergé, résultat provisoire":
        "Grey cross: non-converged, provisional result",
    "Stabilité sur": "Stability across",
    "graines — distribution de chaque profil": "seeds — distribution of each profile",
    "Alphas conditionnels : RMSE, ES et nombre d'options":
        "Conditional alphas: RMSE, ES and number of options",
    "Non-dominance sur RMSE, ES et taille, par pénalité · taille des cercles ∝ options actives":
        "Non-dominance in RMSE, ES and size by penalty · circle size ∝ active options",
    "RMSE sur validation ES indépendante (% du nominal ; plus bas = mieux)":
        "RMSE on independent ES validation (% of notional; lower is better)",
    "ES 97,5 % résiduel (% du nominal ; plus bas = mieux)":
        "Residual ES 97.5% (% of notional; lower is better)",
    "non dominé": "non-dominated",
    "Dominé · arrière-plan": "Dominated · background",
    "Étoile · profil déjà retenu": "Star · previously retained profile",
    "ES pénalisé — grille lambda": "Penalised ES — lambda grid",
    "ES contraint — grille de budgets": "Constrained ES — budget grid",
    "Tous les candidats convergés": "All converged candidates",
    "Admissibles non dominés": "Admissible non-dominated candidates",
    "Priorité RMSE": "RMSE priority",
    "Priorité ES": "ES priority",
    "Plafond strict": "Strict cap",
    "Plafond intermédiaire": "Intermediate cap",
    "Plafond souple": "Loose cap",
    "RMSE en validation indépendante (% du nominal)":
        "RMSE on independent validation (% of notional)",
    "ES 97,5 % en validation indépendante (% du nominal)":
        "ES 97.5% on independent validation (% of notional)",
    "Lambda ES": "ES lambda",
    "Budget ES absolu": "Absolute ES budget",
    "Contrôle du risque de queue — tous les candidats, frontière et profils retenus":
        "Tail-risk control — all candidates, frontier and retained profiles",
    "λ ≥ 1 exclu de la sélection": "λ ≥ 1 excluded from selection",
    "points diagnostiques": "diagnostic points",
    "certains hors cadre": "some outside the frame",
}


def table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / name)


def translate_figure(figure: plt.Figure) -> plt.Figure:
    # Force Matplotlib to materialise tick labels before translating them.
    figure.canvas.draw()
    replacements = sorted(TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True)
    for artist in figure.findobj(match=Text):
        value = artist.get_text()
        for source, target in replacements:
            value = value.replace(source, target)
        artist.set_text(value)
    return figure


def save(figure: plt.Figure, name: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT / f"{name}.pdf", bbox_inches="tight")
    figure.savefig(OUTPUT / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


def build_alpha_grid() -> None:
    data = table("alpha_grid.csv")
    profiles = table("alpha_profiles.csv")
    figure = plot_regularization_grid(
        data.loc[data["penalty"].ne("elastic_net")], profiles, nominal=100.0,
        title="Method B — L0, L1 and L2 alpha paths (Elastic Net: joint map above)",
    )
    save(translate_figure(figure), "alpha_grid")


def build_rho_grid() -> None:
    figure = plot_rho_grid(
        table("elastic_net_rho_grid.csv"),
        selected=table("elastic_net_rho_profiles.csv"), nominal=100.0,
    )
    save(translate_figure(figure), "elastic_net_rho_grid")


def build_l0_audit() -> None:
    data = table("l0_initialization_audit.csv")
    figure, axes = plt.subplots(1, 2, figsize=(14, 4.8))
    for family, group in data.groupby("family", sort=False):
        ordered = group.sort_values("alpha_relative", ascending=False)
        axes[0].plot(ordered["alpha_relative"], ordered["warm_cold_support_jaccard"],
                     marker="o", label=FAMILY_NAMES[family])
        axes[1].plot(ordered["alpha_relative"], ordered["n_distinct_supports"],
                     marker="o", label=FAMILY_NAMES[family])
    for axis in axes:
        axis.set_xscale("log")
        axis.invert_xaxis()
        axis.set_xlabel("Relative L0 alpha (strong → weak)")
        axis.grid(alpha=0.25)
        axis.legend()
    axes[0].set_title("Warm-start / cold-start agreement")
    axes[0].set_ylabel("Support Jaccard similarity")
    axes[1].set_title("Multiplicity of observed local solutions")
    axes[1].set_ylabel("Number of distinct supports")
    figure.suptitle("L0 — initialisation-dependence audit")
    figure.tight_layout()
    save(figure, "l0_initialization_audit")


def build_stability() -> None:
    figure = plot_seed_robustness(table("selected_stability_details.csv"), nominal=100.0)
    figure = translate_figure(figure)
    # The plotting helper installs a formatter that recreates the y tick labels
    # during the final draw, so freeze their translated form explicitly.
    for axis in figure.axes[:2]:
        translated = []
        for label in axis.get_yticklabels():
            value = label.get_text()
            value = value.replace("Compromis", "Compromise")
            value = value.replace("Parcimonie", "Parsimony")
            value = value.replace("convergés", "converged")
            translated.append(value)
        axis.set_yticks(axis.get_yticks())
        axis.set_yticklabels(translated)
    save(figure, "multi_seed_stability")


def build_filter_map() -> None:
    data = table("regularization_filter_flow.csv")
    stage_order = list(dict.fromkeys(data["stage"]))
    row_order = list(dict.fromkeys(zip(data["family"], data["penalty"])))
    pivot = data.pivot(index=["family", "penalty"], columns="stage", values="remaining")
    pivot = pivot.reindex(index=pd.MultiIndex.from_tuples(row_order), columns=stage_order)
    values = pivot.to_numpy(dtype=float)
    figure, axis = plt.subplots(figsize=(13, 5.8))
    image = axis.imshow(values, aspect="auto", cmap="YlGn", vmin=0,
                        vmax=max(1.0, float(np.nanmax(values))))
    labels = {
        "Grille initiale": "Initial grid", "Convergés": "Converged",
        "≥ 2 options": "≥ 2 options", "Robustes sur 10 graines": "Robust across 10 seeds",
        "Non dominés": "Non-dominated", "Performance statique": "Static performance",
        "Sans doublons stricts": "No strict duplicates",
        "Sans quasi-doublons": "No near-duplicates", "Profils distincts": "Distinct profiles",
    }
    axis.set_xticks(range(len(stage_order)), [labels.get(value, value) for value in stage_order],
                    rotation=35, ha="right")
    axis.set_yticks(range(len(row_order)),
                    [f"{family} / {PENALTY_NAMES[penalty]}" for family, penalty in row_order])
    threshold = np.nanmax(values) * 0.55
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            if np.isfinite(values[row, column]):
                axis.text(column, row, f"{int(values[row, column])}", ha="center", va="center",
                          color="white" if values[row, column] > threshold else "black", fontsize=9)
    axis.set_title("Number of solutions remaining after each filter")
    figure.colorbar(image, ax=axis, label="Remaining solutions")
    figure.tight_layout()
    save(figure, "regularization_filter_map")


def build_alpha_tail_frontiers() -> None:
    data = table("alpha_tail_frontier.csv")
    for family in ("calls_puts", "full"):
        for panel in ("overview", "zoom"):
            figure = plot_alpha_tail_frontier(
                data.loc[data["family"].eq(family)], nominal=100.0,
                title=f"{FAMILY_NAMES[family]} — conditional B policies · independent tail validation",
                language="en", panel=panel,
            )
            save(translate_figure(figure), f"alpha_tail_frontier_{family}_{panel}")


def build_tail_frontiers() -> None:
    grid = table("tail_grid.csv")
    lambda_profiles = table("lambda_es_profiles.csv")
    budget_profiles = table("es_budget_profiles.csv")
    for family in ("calls_puts", "full"):
        penalty = "elastic_net"
        subset = grid.loc[grid["family"].eq(family) & grid["penalty"].eq(penalty)].copy()
        result = {
            "lambda_table": subset.loc[subset["objective"].eq("penalized_es")],
            "budget_table": subset.loc[subset["objective"].eq("constrained_es")],
            "lambda_profiles": lambda_profiles.loc[
                lambda_profiles["family"].eq(family) & lambda_profiles["penalty"].eq(penalty)
            ],
            "budget_profiles": budget_profiles.loc[
                budget_profiles["family"].eq(family) & budget_profiles["penalty"].eq(penalty)
            ],
        }
        figure = plot_tail_frontiers(result, nominal=100.0)
        figure.suptitle(
            f"{FAMILY_NAMES[family]} — Elastic Net — RMSE and ES on independent validation",
            fontsize=13,
        )
        save(translate_figure(figure), f"tail_frontiers_{family}_elastic_net")


def mixture_label(value: str) -> str:
    return str(value).replace(" — ", "\n").replace(" ; ", "\n")


def build_importance_sampling() -> None:
    summary = table("importance_sampling_grid.csv").sort_values(["candidate_index", "family"])
    positions = {value: index for index, value in enumerate(sorted(summary["candidate_index"].unique()))}
    labels = {
        row.candidate_index: mixture_label(row.mixture_description)
        for row in summary.drop_duplicates("candidate_index").itertuples()
    }
    figure, axes = plt.subplots(1, 2, figsize=(16, 6.0))
    for family, group in summary.groupby("family", sort=False):
        offset = -0.09 if family == "calls_puts" else 0.09
        xs = group["candidate_index"].map(positions) + offset
        color = "tab:blue" if family == "calls_puts" else "tab:orange"
        axes[0].scatter(xs, group["worst_precision_ratio_to_mc"], s=70, color=color,
                        label=FAMILY_NAMES[family])
        axes[1].scatter(xs, group["effective_sample_ratio_min"], s=70, color=color,
                        label=FAMILY_NAMES[family])
        selected = group.loc[group["recommended"].astype(bool)]
        selected_x = selected["candidate_index"].map(positions) + offset
        for axis, metric in zip(axes, ("worst_precision_ratio_to_mc", "effective_sample_ratio_min")):
            axis.scatter(selected_x, selected[metric], marker="*", s=210, color=color,
                         edgecolor="black", zorder=5)
    axes[0].axhline(1.0, color="black", linestyle=":", label="Same precision as standard MC")
    axes[1].axhline(0.20, color="black", linestyle=":", label="20% ESS threshold")
    axes[0].set_title("Worst IS/MC precision ratio across policies")
    axes[0].set_ylabel("IS standard deviation / MC standard deviation; lower is better")
    axes[1].set_title("Weight quality: minimum ESS")
    axes[1].set_ylabel("ESS / number of paths")
    ordered_candidates = sorted(positions, key=positions.get)
    for axis in axes:
        axis.set_xticks(range(len(ordered_candidates)), [labels[value] for value in ordered_candidates], fontsize=8)
        axis.set_xlim(-0.35, len(ordered_candidates) - 0.65)
        axis.set_xlabel("Tested method · shift: simulated share")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle("Selecting a robust IS mixture for all retained ES policies — star = recommendation")
    figure.tight_layout(rect=(0, 0, 1, 0.94))
    save(figure, "importance_sampling_grid")

    policy = table("importance_sampling_policy_summary.csv")
    for family, group in policy.loc[policy["candidate_index"].ge(0)].groupby("family", sort=False):
        heat = group.pivot(index="policy_key", columns="candidate_index", values="precision_ratio_to_mc").sort_index()
        figure, axis = plt.subplots(figsize=(11, max(6.0, 0.35 * len(heat) + 2.5)))
        values = heat.to_numpy(dtype=float)
        image = axis.imshow(values, aspect="auto", cmap="RdYlGn_r", vmin=0,
                            vmax=max(2.0, float(np.nanmax(values))))
        axis.set_yticks(np.arange(len(heat)), heat.index, fontsize=8)
        recommended = summary.loc[summary["family"].eq(family) & summary["recommended"].astype(bool),
                                  "candidate_index"]
        chosen = int(recommended.iloc[0]) if len(recommended) else -999
        axis.set_xticks(np.arange(len(heat.columns)), [
            labels[int(value)] + ("\n★ retained" if int(value) == chosen else "")
            for value in heat.columns
        ], fontsize=8)
        axis.set_title(f"{FAMILY_NAMES[family]} — IS/MC precision by frozen ES portfolio")
        axis.set_xlabel("Tested IS mixture · shift: simulated share")
        figure.colorbar(image, ax=axis, label="IS standard deviation / MC standard deviation (lower is better)")
        figure.tight_layout()
        save(figure, f"importance_policy_precision_{family}")


def build_decision_dashboard() -> None:
    stability = table("stability_size_diagnostic.csv")
    idx = stability.groupby(["family", "penalty"])["size_multiplier"].idxmax()
    size_plot = stability.loc[idx].sort_values(["family", "penalty"]).copy()
    importance = table("importance_sampling_grid.csv")
    admissible = importance.loc[importance["passes_weight_diagnostics"].astype(bool)]
    best_is = admissible.loc[admissible.groupby("family")["worst_precision_ratio_to_mc"].idxmin()]
    budgets = table("es_budget_level_status.csv")

    figure = plt.figure(figsize=(14, 7.2))
    grid = figure.add_gridspec(2, 2, width_ratios=(1.55, 1.0), height_ratios=(1.0, 1.0))
    stability_axis = figure.add_subplot(grid[:, 0])
    is_axis = figure.add_subplot(grid[0, 1])
    budget_axis = figure.add_subplot(grid[1, 1])

    values = size_plot["size_multiplier"].to_numpy(dtype=float)
    stability_axis.barh(np.arange(len(size_plot)), values,
                        color=["#c0392b" if value >= 2.0 else "#4c8f7b" for value in values])
    stability_axis.set_yticks(np.arange(len(size_plot)), [
        f"{FAMILY_NAMES[row.family]} / {PENALTY_NAMES[row.penalty]}" for row in size_plot.itertuples()
    ], fontsize=8)
    stability_axis.invert_yaxis()
    stability_axis.axvline(2.0, color="#9b2c2c", linestyle=":", label="Descriptive alert: ×2")
    stability_axis.legend(fontsize=8, loc="lower right")
    stability_axis.set_title("Mean recalibrated size / initial size")
    stability_axis.set_xlabel("Size ratio; closer to 1 means more stable")
    stability_axis.grid(axis="x", alpha=0.2)

    is_axis.axvline(1.0, color="black", linestyle=":")
    is_values = best_is["worst_precision_ratio_to_mc"].to_numpy(dtype=float)
    is_axis.scatter(is_values, np.arange(len(best_is)), s=95,
                    color=["#4c8f7b" if value < 1.0 else "#c0392b" for value in is_values])
    is_axis.set_yticks(np.arange(len(best_is)), [FAMILY_NAMES[value] for value in best_is["family"]])
    is_axis.set_xlim(0, max(1.25, float(np.max(is_values)) * 1.25))
    for row_index, value in enumerate(is_values):
        is_axis.annotate(f"{value:.2f}", (value, row_index), xytext=(7, 0),
                         textcoords="offset points", va="center", fontsize=9)
    is_axis.set_title("Best admissible IS: worst precision ratio")
    is_axis.set_xlabel("IS / MC standard deviation; below 1 is better")
    is_axis.grid(axis="x", alpha=0.2)

    levels = [("strict", "5%"), ("intermédiaire", "10%"), ("souple", "15%")]
    counts = [int(budgets.loc[budgets["level"].eq(level), "status"].eq("retenu").sum())
              for level, _ in levels]
    total_pairs = budgets[["family", "penalty"]].drop_duplicates().shape[0]
    budget_axis.barh(range(3), counts, color="#3b8d6e")
    budget_axis.set_yticks(range(3), [f"{label} cap" for _, label in levels])
    budget_axis.invert_yaxis()
    budget_axis.set_xlim(0, total_pairs * 1.18)
    for index, count in enumerate(counts):
        budget_axis.text(count + 0.1, index, f"{count}/{total_pairs}", va="center", fontsize=9)
    budget_axis.set_title("Family / penalty pairs with admissible ES")
    budget_axis.set_xlabel("Number of admissible pairs in validation")
    budget_axis.grid(axis="x", alpha=0.2)
    figure.suptitle("REPORT run summary — validation and robustness, not final test", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    save(figure, "decision_dashboard")


def main() -> None:
    plt.rcParams.update({"figure.dpi": 120, "savefig.dpi": 180, "font.size": 10})
    build_alpha_grid()
    build_rho_grid()
    build_l0_audit()
    build_stability()
    build_filter_map()
    build_alpha_tail_frontiers()
    build_tail_frontiers()
    build_importance_sampling()
    build_decision_dashboard()
    print(f"English figures written to {OUTPUT}")


if __name__ == "__main__":
    main()
