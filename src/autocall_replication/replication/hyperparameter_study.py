"""External hyperparameter research for the conditional autocall replication.

This module deliberately contains no final-test evaluation.  It builds and
summarises calibration/validation grids that are run from the dedicated
``hyperparameter_research.ipynb`` notebook.  The main research notebook only
loads a manually promoted, product-compatible selection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import pickle
import shutil
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle
import numpy as np
import pandas as pd

from .risk import empirical_var_es
from .tail_risk_optimization import (
    TailRiskOptimizationConfig,
    solve_tail_risk_replication,
)
from ..research_export import export_research_run


EXPLORATORY_ALPHA_GRID = (
    1e-8, 1e-6, 1e-4, 1e-3, 1e-2, 3e-2,
    1e-1, 3e-1, 5e-1, 1.0, 3.0, 10.0,
    1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8,
)


@dataclass(frozen=True)
class HyperparameterGrid:
    """Auditable grids used by the external research notebook.

    ``n_alphas`` controls a penalty-specific relative path: the absolute alpha
    reference is recomputed independently for L0, L1, L2 and every Elastic-Net
    ratio.  Equal relative alphas therefore never imply equal absolute alphas.
    """

    penalties: tuple[str, ...] = ("l0", "l1", "l2", "elastic_net")
    n_alphas: int = 25
    # Kept as two serialised fields for compatibility, but identical by design.
    exploratory_alpha_sparse: tuple[float, ...] = EXPLORATORY_ALPHA_GRID
    exploratory_alpha_ridge: tuple[float, ...] = EXPLORATORY_ALPHA_GRID
    min_alpha_ratio: float = 1e-3
    ridge_min_alpha_ratio: float = 1e-4
    ridge_max_alpha_ratio: float = 1e2
    # A 0.025 mesh near the former upper boundary; pure L1 is evaluated separately.
    elastic_net_l1_ratios: tuple[float, ...] = (
        0.05, 0.10, 0.25, 0.50, 0.75, 0.775, 0.80, 0.825, 0.85,
        0.875, 0.90, 0.925, 0.95, 0.975, 0.99,
    )
    tail_alpha_ratios: tuple[float, ...] = (1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.001, 1e-4, 1e-5)
    lambda_es_values: tuple[float, ...] = (0.0, 0.05, 0.10, 0.25, 0.50, 1.0, 2.0)
    # Common absolute ES ceilings, expressed as a percentage of notional.
    es_budget_pct_notional: tuple[float, ...] = (5.0, 10.0, 15.0)
    importance_candidates: tuple[tuple[tuple[float, ...], tuple[float, ...]], ...] = (
        ((0.0, -1.0), (0.70, 0.30)),
        ((0.0, -1.0, -2.0), (0.50, 0.30, 0.20)),
        ((0.0, -1.5, -3.0), (0.55, 0.30, 0.15)),
        ((0.0, -2.0, -4.0), (0.60, 0.25, 0.15)),
    )

    def validate(self) -> None:
        if self.n_alphas < 3:
            raise ValueError("La grille alpha doit contenir au moins trois points.")
        for values in (self.exploratory_alpha_sparse, self.exploratory_alpha_ridge):
            if not values or any(not np.isfinite(value) or value <= 0 for value in values):
                raise ValueError("Les alphas exploratoires doivent être finis et positifs.")
        if self.exploratory_alpha_sparse != self.exploratory_alpha_ridge:
            raise ValueError("Les contrôles exploratoires doivent partager la même grille alpha.")
        if not 0.0 < self.min_alpha_ratio < 1.0:
            raise ValueError("min_alpha_ratio doit appartenir à ]0, 1[.")
        if not 0.0 < self.ridge_min_alpha_ratio < self.ridge_max_alpha_ratio:
            raise ValueError("La grille L2 est invalide.")
        if not self.elastic_net_l1_ratios or any(
            not 0.0 < value < 1.0 for value in self.elastic_net_l1_ratios
        ):
            raise ValueError("Les ratios Elastic Net doivent appartenir à ]0, 1[.")
        if not self.tail_alpha_ratios or any(
            not 0.0 < value <= 1.0 for value in self.tail_alpha_ratios
        ) or len(set(self.tail_alpha_ratios)) != len(self.tail_alpha_ratios):
            raise ValueError("Les ratios alpha ES doivent être uniques et appartenir à ]0, 1].")
        if not self.lambda_es_values or any(value < 0.0 for value in self.lambda_es_values):
            raise ValueError("Les lambda ES doivent être positifs ou nuls.")
        if 0.0 not in self.lambda_es_values:
            raise ValueError("La grille lambda ES doit contenir zéro comme référence RMSE.")
        if (
            len(self.es_budget_pct_notional) != 3
            or any(not np.isfinite(value) or value <= 0 for value in self.es_budget_pct_notional)
            or tuple(sorted(set(self.es_budget_pct_notional))) != self.es_budget_pct_notional
        ):
            raise ValueError("Les trois plafonds ES en pourcentage du nominal doivent être positifs et croissants.")
        for tilts, probabilities in self.importance_candidates:
            if len(tilts) != len(probabilities) or not np.isclose(sum(probabilities), 1.0):
                raise ValueError("Chaque mélange IS doit avoir des probabilités valides.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def product_configuration(
    *,
    product: Any,
    spot0: float,
    valuation_date: Any,
    contract_start_date: Any,
    maturity_date: Any,
    rate: float,
    dividend_yield: float,
    volatility: float,
    families: Sequence[str],
) -> dict[str, Any]:
    """Return the complete contract/model identity used for compatibility checks."""

    return {
        "product": {
            "notional": float(product.notional),
            "autocall_strike": float(product.autocall_strike),
            "coupon_barrier": float(product.coupon_barrier),
            "coupon_rate": float(product.coupon_rate),
            "down_barrier": float(product.down_barrier),
            "observation_months": [int(value) for value in product.observation_months],
        },
        "market": {
            "spot0": float(spot0),
            "valuation_date": pd.Timestamp(valuation_date).isoformat(),
            "contract_start_date": pd.Timestamp(contract_start_date).isoformat(),
            "maturity_date": pd.Timestamp(maturity_date).isoformat(),
            "rate": float(rate),
            "dividend_yield": float(dividend_yield),
            "volatility": float(volatility),
        },
        "families": [str(value) for value in families],
        "model": "risk_neutral_black_scholes_gbm",
        "policy": "conditional_pathwise_one_period_instruments",
    }


def configuration_fingerprint(configuration: Mapping[str, Any]) -> str:
    """Stable SHA-256 identity for a contract and modelling configuration."""

    canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def importance_candidate_dicts(grid: HyperparameterGrid) -> list[dict[str, object]]:
    """Convert the immutable IS grid into the public comparison API format."""

    grid.validate()
    return [
        {"tilts": tilts, "mixture_probabilities": probabilities}
        for tilts, probabilities in grid.importance_candidates
    ]


def exploratory_alpha_values(grid: HyperparameterGrid, penalty: str) -> tuple[float, ...]:
    """Fixed, mode-independent candidate grid for the preliminary benchmarks."""

    grid.validate()
    return grid.exploratory_alpha_ridge if penalty == "l2" else grid.exploratory_alpha_sparse


def select_exploratory_benchmark_alphas(table: pd.DataFrame) -> pd.DataFrame:
    """Pick the lowest validation RMSE per benchmark/family/penalty, never a test metric."""

    required = {"benchmark", "family", "penalty", "alpha", "validation_rmse", "converged"}
    missing = required.difference(table.columns)
    if missing:
        raise KeyError(f"Colonnes absentes de la grille exploratoire : {sorted(missing)}")
    eligible = table.loc[
        table["converged"].astype(bool)
        & np.isfinite(table["validation_rmse"])
    ].copy()
    if "n_options_active" in eligible:
        eligible = eligible.loc[eligible["n_options_active"].ge(2)].copy()
    if eligible.empty:
        return eligible
    sort_columns = ["benchmark", "family", "penalty", "validation_rmse"]
    if "n_options_active" in eligible:
        sort_columns.append("n_options_active")
    sort_columns.append("alpha")
    if "l1_ratio" in eligible:
        sort_columns.append("l1_ratio")
    return (
        eligible.sort_values(sort_columns)
        .drop_duplicates(["benchmark", "family", "penalty"], keep="first")
        .reset_index(drop=True)
    )


def plot_exploratory_benchmark_schematic() -> plt.Figure:
    """Contrast the three calibration targets before comparing alpha curves."""

    figure, axis = plt.subplots(figsize=(13, 4.3))
    axis.set_xlim(0, 13)
    axis.set_ylim(-0.5, 3.4)
    axis.axis("off")
    axis.text(3.45, 3.1, "Cible sur une trajectoire simulée", ha="center", weight="bold")
    axis.text(10.8, 3.1, "Poids calibrés au départ", ha="center", weight="bold")
    rows = (
        (2.25, "Pathwise payoff", "Un total actualisé", "Un panier global", "#deebf7"),
        (1.25, "Static cashflows", "Paiements par date", "Un panier global", "#d9f0e3"),
        (0.25, "Conditional cashflows", "Paiements par date", "Par date et état", "#fff0ce"),
    )
    for y, name, target, weights, color in rows:
        axis.text(0.15, y, name, va="center", weight="bold", fontsize=10)
        if name == "Pathwise payoff":
            box = FancyBboxPatch((3.05, y - 0.31), 5.0, 0.62,
                                 boxstyle="round,pad=0.04", facecolor=color, edgecolor="#64748b")
            axis.add_patch(box)
            axis.text(5.55, y, "PV(C₁ + C₂ + C₃ + C₄)", ha="center", va="center")
        else:
            for index in range(4):
                x = 3.05 + index * 1.27
                box = FancyBboxPatch((x, y - 0.31), 1.12, 0.62,
                                     boxstyle="round,pad=0.04", facecolor=color,
                                     edgecolor="#64748b")
                axis.add_patch(box)
                axis.text(x + 0.56, y, f"PV(C{index + 1})", ha="center", va="center")
        axis.text(8.35, y, "→", ha="center", va="center", fontsize=17)
        axis.text(10.8, y, weights, ha="center", va="center", fontsize=10)
    axis.text(0.15, -0.35,
              "Conditionnel : états vivants à chaque date ; séparation par barrière à maturité si l’échantillon suffit. "
              "Aucune recalibration en direct.", fontsize=8.5, color="#334155")
    figure.suptitle("Trois questions de réplication différentes — mêmes familles Calls + Puts / Full",
                    fontsize=13, weight="bold")
    figure.tight_layout()
    return figure


def plot_exploratory_alpha_grid(
    table: pd.DataFrame,
    selected: pd.DataFrame,
    *,
    benchmark: str,
    nominal: float = 100.0,
) -> plt.Figure:
    """Compare penalties, showing only the selected Elastic Net ratio."""

    # IPython autoreload may update this function on a previously imported object
    # while keeping its old globals dictionary. Resolve the helper from the live module.
    from autocall_replication.replication.hyperparameter_study import (
        _plot_exploratory_alpha_grid as plot_grid,
    )

    return plot_grid(
        table, selected, benchmark=benchmark, nominal=nominal,
        elastic_net_only=False,
    )


def plot_exploratory_elastic_net_grid(
    table: pd.DataFrame,
    selected: pd.DataFrame,
    *,
    benchmark: str,
    nominal: float = 100.0,
) -> plt.Figure:
    """Show every Elastic Net ratio separately from the penalty comparison."""

    from autocall_replication.replication.hyperparameter_study import (
        _plot_exploratory_alpha_grid as plot_grid,
    )

    return plot_grid(
        table, selected, benchmark=benchmark, nominal=nominal,
        elastic_net_only=True,
    )


def _plot_exploratory_alpha_grid(
    table: pd.DataFrame,
    selected: pd.DataFrame,
    *,
    benchmark: str,
    nominal: float,
    elastic_net_only: bool,
) -> plt.Figure:
    """Draw one family per panel, without mixing all rho curves and penalties."""

    figure, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    for axis, family in zip(axes, ("calls_puts", "full")):
        nonconverged_labeled = False
        undersized_labeled = False
        family_table = table.loc[
            table["benchmark"].eq(benchmark) & table["family"].eq(family)
        ].copy()
        if "l1_ratio" not in family_table:
            family_table["l1_ratio"] = np.nan
        for (penalty, ratio), group in family_table.groupby(
            ["penalty", "l1_ratio"], sort=False, dropna=False,
        ):
            if elastic_net_only and penalty != "elastic_net":
                continue
            winner = selected.loc[
                selected["benchmark"].eq(benchmark)
                & selected["family"].eq(family)
                & selected["penalty"].eq(penalty)
            ]
            if penalty == "elastic_net" and "l1_ratio" in winner:
                winner = winner.loc[winner["l1_ratio"].eq(ratio)]
                if not elastic_net_only and winner.empty:
                    continue
            ordered = group.sort_values("alpha")
            errors = ordered["validation_rmse"].to_numpy(dtype=float) * 100.0 / nominal
            converged = ordered["converged"].to_numpy(dtype=bool)
            enough_options = (
                ordered["n_options_active"].ge(2).to_numpy(dtype=bool)
                if "n_options_active" in ordered else np.ones(len(ordered), dtype=bool)
            )
            finite = np.isfinite(errors)
            eligible = converged & enough_options & finite
            label = (
                f"Elastic Net (ρ={ratio:g})" if pd.notna(ratio) else "Elastic Net"
                if penalty == "elastic_net" else str(penalty).upper()
            )
            line, = axis.plot(
                ordered["alpha"], np.where(eligible, errors, np.nan),
                marker="o", label=label,
            )
            nonconverged = ~converged & finite
            if nonconverged.any():
                axis.scatter(
                    ordered.loc[nonconverged, "alpha"], errors[nonconverged],
                    s=20, marker="o", color="#94a3b8", alpha=0.55, zorder=2,
                    label="Non convergé · valeur à l'arrêt" if not nonconverged_labeled else "_nolegend_",
                )
                nonconverged_labeled = True
            undersized = converged & ~enough_options & finite
            if undersized.any():
                axis.scatter(
                    ordered.loc[undersized, "alpha"], errors[undersized],
                    s=23, marker="^", color="#cbd5e1", alpha=0.75, zorder=2,
                    label="Convergé · moins de 2 options" if not undersized_labeled else "_nolegend_",
                )
                undersized_labeled = True
            if not winner.empty:
                row = winner.iloc[0]
                axis.scatter(
                    [row["alpha"]], [row["validation_rmse"] * 100.0 / nominal],
                    marker="*", s=160, facecolor=line.get_color(),
                    edgecolor="black", linewidth=0.8,
                    zorder=5, label="_nolegend_",
                )
        axis.set_xscale("log")
        axis.set_xlabel("Alpha" if elastic_net_only else "Alpha (échelle propre à chaque pénalité)")
        axis.set_title("Calls + Puts" if family == "calls_puts" else "Full (avec binaires)")
        axis.grid(alpha=0.25)
        if axis.lines:
            axis.legend(fontsize=8)
    axes[0].set_ylabel("RMSE de validation (% du nominal)")
    benchmark_label = {
        "static_cashflows": "Cashflows statiques",
        "conditional_cashflows": "Cashflows conditionnels",
    }.get(benchmark, benchmark)
    title = (
        "Elastic Net : tous les ratios ρ testés"
        if elastic_net_only else
        "L0 / L1 / L2 + Elastic Net au ratio ρ retenu"
    )
    figure.suptitle(f"{benchmark_label} — {title} (RMSE de validation)")
    figure.tight_layout()
    return figure


def combine_conditional_elastic_net_profiles(
    base_result: Mapping[str, Any],
    ratio_results: Mapping[float, Mapping[str, Any]],
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Select three (rho, alpha) pairs over the whole admissible Elastic Net grid.

    Every ratio must use the same simulated paths and conditional design. The
    complete per-ratio paths remain in the merged audit table; each selected
    profile points to its own weights and ratio for later stability checks.
    """
    from .regularization_path import candidate_policies, select_three_profiles_per_penalty

    if not ratio_results:
        raise ValueError("La grille des ratios Elastic Net est vide.")
    family = str(base_result["family"])
    base_A = np.asarray(base_result["A"])
    base_b = np.asarray(base_result["b"])
    base_features = pd.DataFrame(base_result["feature_table"])
    elastic_tables: list[pd.DataFrame] = []
    elastic_raw_tables: list[pd.DataFrame] = []
    elastic_solutions: list[dict[str, Any]] = []
    elastic_duplicates: list[pd.DataFrame] = []
    for rho, result in sorted(ratio_results.items()):
        if str(result["family"]) != family:
            raise ValueError("Les familles de la grille Elastic Net diffèrent.")
        if not (
            np.array_equal(base_A, np.asarray(result["A"]))
            and np.array_equal(base_b, np.asarray(result["b"]))
            and base_features.equals(pd.DataFrame(result["feature_table"]))
        ):
            raise ValueError("La grille Elastic Net n'utilise pas le même design pathwise.")
        offset = len(elastic_solutions)
        path = result["results"]["elastic_net"]
        for solution in path["solutions"]:
            copied = dict(solution)
            copied["solution_index"] = offset + int(solution["solution_index"])
            copied["l1_ratio"] = float(rho)
            elastic_solutions.append(copied)
        for source, target in ((result["table"], elastic_tables),
                               (result["raw_table"], elastic_raw_tables)):
            table = pd.DataFrame(source).loc[lambda frame: frame["penalty"].eq("elastic_net")].copy()
            table["solution_index"] = table["solution_index"].astype(int) + offset
            table["family"] = family
            table["searched_l1_ratio"] = float(rho)
            target.append(table)
        duplicates = pd.DataFrame(result["duplicate_report"])
        if not duplicates.empty:
            elastic_duplicates.append(duplicates.assign(family=family, l1_ratio=float(rho)))

    elastic_table = pd.concat(elastic_tables, ignore_index=True)
    selected = select_three_profiles_per_penalty(elastic_table)
    if selected.empty:
        raise ValueError(f"Aucun couple (rho, alpha) admissible pour {family}.")
    selected.insert(0, "family", family)
    selected["searched_l1_ratio"] = selected["l1_ratio"].astype(float)
    base_table = pd.DataFrame(base_result["table"])
    base_profiles = pd.DataFrame(base_result["profiles"])
    merged = dict(base_result)
    merged["table"] = pd.concat(
        [base_table.loc[base_table["penalty"].ne("elastic_net")], elastic_table],
        ignore_index=True,
    )
    merged["raw_table"] = pd.concat(
        [pd.DataFrame(base_result["raw_table"]).loc[
            lambda frame: frame["penalty"].ne("elastic_net")
        ], *elastic_raw_tables], ignore_index=True,
    )
    merged["profiles"] = pd.concat(
        [base_profiles.loc[base_profiles["penalty"].ne("elastic_net")], selected],
        ignore_index=True,
    )
    merged["candidates"] = merged["table"].loc[
        merged["table"]["is_candidate_after_duplicates"]
    ].copy()
    merged["candidate_policies"] = candidate_policies(merged["table"])
    for policy in merged["candidate_policies"]:
        policy["family"] = family
    merged["profile_policies"] = merged["profiles"].to_dict(orient="records")
    results = dict(base_result["results"])
    elastic_path = dict(results["elastic_net"])
    elastic_path["solutions"] = elastic_solutions
    elastic_path["table"] = elastic_table
    elastic_path["ratio_paths"] = {float(rho): result["results"]["elastic_net"]
                                   for rho, result in ratio_results.items()}
    results["elastic_net"] = elastic_path
    merged["results"] = results
    coverage = pd.DataFrame(base_result["profile_coverage"]).copy()
    elastic_mask = coverage["penalty"].eq("elastic_net")
    coverage.loc[elastic_mask, "n_distinct_candidates"] = len(
        elastic_table.loc[elastic_table["is_candidate_after_duplicates"]]
    )
    coverage.loc[elastic_mask, "n_profiles"] = len(selected)
    coverage.loc[elastic_mask, "status"] = "three_global_alpha_rho_profiles"
    merged["profile_coverage"] = coverage
    duplicate_parts = [pd.DataFrame(base_result["duplicate_report"]).loc[
        lambda frame: frame["penalty"].ne("elastic_net")
    ], *elastic_duplicates]
    merged["duplicate_report"] = pd.concat(duplicate_parts, ignore_index=True)
    merged["elastic_net_profile_ratios"] = {
        str(row["profile"]): float(row["l1_ratio"]) for _, row in selected.iterrows()
    }
    return merged, selected


def select_profiles_after_candidate_stability(
    base_result: Mapping[str, Any],
    stability_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply Pareto, performance and duplicate filters only to stable candidates.

    All candidates retain their original validation RMSE and active count. The
    only methodological change is the order of the stability filter; no final
    test data or ES estimate is used to choose profiles.
    """
    from .regularization_path import (
        apply_static_performance_filter,
        candidate_policies,
        remove_duplicate_candidates,
        select_regularization_candidates,
        select_three_profiles_per_penalty,
    )

    raw = pd.DataFrame(base_result["raw_table"]).copy()
    summary = pd.DataFrame(stability_result["summary"])
    keys = ["penalty", "solution_index"]
    if raw.duplicated(keys).any():
        raise ValueError("Les indices de solutions doivent être uniques par pénalité.")
    if summary.empty:
        raw["passes_stability_filter"] = False
    else:
        flags = summary.loc[:, keys + ["passes_stability_filter"]]
        raw = raw.merge(flags, on=keys, how="left", validate="one_to_one")
        raw["passes_stability_filter"] = raw["passes_stability_filter"].fillna(False).astype(bool)
    previous_filters = dict(base_result.get("candidate_filters", {}))
    annotated = select_regularization_candidates(
        raw,
        min_active_options=int(previous_filters.get("min_active_options", 2)),
        max_active_options=int(previous_filters.get("max_active_options", 100)),
        stability_column="passes_stability_filter",
    )
    performance = apply_static_performance_filter(
        annotated, results=base_result["results"],
    )
    deduplicated, duplicate_report = remove_duplicate_candidates(
        performance, results=base_result["results"],
        active_threshold=float(base_result["active_threshold"]),
    )
    selected = select_three_profiles_per_penalty(deduplicated)
    if selected.empty:
        selected = pd.DataFrame(base_result["profiles"]).iloc[0:0].copy()
    elif "family" not in selected:
        selected.insert(0, "family", str(base_result["family"]))

    result = dict(base_result)
    result["raw_table"] = raw
    result["table"] = deduplicated
    result["candidates"] = deduplicated.loc[
        deduplicated["is_candidate_after_duplicates"]
    ].copy()
    result["candidate_policies"] = candidate_policies(deduplicated)
    for policy in result["candidate_policies"]:
        policy["family"] = str(base_result["family"])
    result["profiles"] = selected
    result["profile_policies"] = selected.to_dict(orient="records")
    result["duplicate_report"] = duplicate_report
    result["stability_result"] = stability_result
    result["candidate_filters"] = {
        **previous_filters,
        "ordering": "stability_before_pareto_performance_duplicates_profiles",
        "stability_rule": stability_result.get("candidate_rule"),
    }
    result["profile_coverage"] = pd.DataFrame([
        {
            "penalty": penalty,
            "n_distinct_candidates": int(result["candidates"]["penalty"].eq(penalty).sum()),
            "n_profiles": int(selected["penalty"].eq(penalty).sum()),
            "status": (
                "three_distinct_profiles"
                if int(result["candidates"]["penalty"].eq(penalty).sum()) >= 3
                else "profiles_reuse_candidates"
                if int(result["candidates"]["penalty"].eq(penalty).sum()) > 0
                else "no_candidate_after_stability_and_filters"
            ),
        }
        for penalty in dict.fromkeys(raw["penalty"])
    ])
    result["elastic_net_profile_ratios"] = {
        str(row["profile"]): float(row["l1_ratio"])
        for _, row in selected.loc[selected["penalty"].eq("elastic_net")].iterrows()
    }
    return result


def regularization_filter_flow(
    result: Mapping[str, Any],
    *,
    family: str,
    stable_result: Mapping[str, Any] | None = None,
    stability_stage_label: str = "Robustes sur dix graines",
) -> pd.DataFrame:
    """Auditable candidate counts from the raw alpha grid to stable profiles."""

    table = pd.DataFrame(result["table"])
    profiles = pd.DataFrame(result["profiles"])
    stable_profiles = (
        pd.DataFrame(stable_result["profiles"])
        if stable_result is not None else None
    )
    rows: list[dict[str, object]] = []
    for penalty, group in table.groupby("penalty", sort=False):
        groups = [
            ("Grille initiale", group),
            ("Convergés", group.loc[group["converged"]]),
            ("≥ 2 options", group.loc[
                group["converged"] & group["n_options_active"].ge(2)
            ]),
        ]
        if "passes_stability_filter" in group:
            groups.append((stability_stage_label, group.loc[
                group["converged"] & group["n_options_active"].ge(2)
                & group["passes_stability_filter"]
            ]))
        groups.extend([
            ("Non dominés", group.loc[group["is_candidate"]]),
            ("Performance statique", group.loc[group["is_candidate_after_performance"]]),
            ("Sans doublons stricts", group.loc[
                group["is_candidate_after_performance"]
                & group["duplicate_status"].ne("strict_duplicate")
            ]),
            ("Sans quasi-doublons", group.loc[group["is_candidate_after_duplicates"]]),
        ])
        selected = profiles.loc[profiles["penalty"].eq(penalty)] if not profiles.empty else profiles
        groups.append(("Profils distincts", selected.drop_duplicates("solution_index")))
        if stable_profiles is not None:
            selected_stable = (
                stable_profiles.loc[stable_profiles["penalty"].eq(penalty)]
                if not stable_profiles.empty else stable_profiles
            )
            groups.append(("Profils stables", selected_stable.drop_duplicates("solution_index")))
        previous = None
        for stage, remaining_group in groups:
            count = len(remaining_group)
            rows.append({
                "family": family, "penalty": penalty, "stage": stage,
                "remaining": count,
                "removed_at_stage": 0 if previous is None else previous - count,
            })
            previous = count
    return pd.DataFrame(rows)


def plot_regularization_filter_map(flow: pd.DataFrame) -> plt.Figure:
    """A labelled matrix of survivor counts for every policy family."""

    order = list(dict.fromkeys(flow["stage"]))
    pairs = list(dict.fromkeys(zip(flow["family"], flow["penalty"])))
    remaining = np.full((len(pairs), len(order)), np.nan)
    for row_index, (family, penalty) in enumerate(pairs):
        subset = flow.loc[flow["family"].eq(family) & flow["penalty"].eq(penalty)]
        for col_index, stage in enumerate(order):
            matching = subset.loc[subset["stage"].eq(stage)]
            if not matching.empty:
                remaining[row_index, col_index] = float(matching.iloc[0]["remaining"])
    figure, axis = plt.subplots(figsize=(15, max(5, 0.58 * len(pairs) + 2)))
    colors = axis.imshow(remaining, cmap="YlGn", aspect="auto", vmin=0)
    axis.set_xticks(np.arange(len(order)), order, rotation=35, ha="right")
    axis.set_yticks(np.arange(len(pairs)), [f"{family} / {penalty}" for family, penalty in pairs])
    axis.set_title("Nombre de solutions restantes après chaque filtre")
    for row_index in range(len(pairs)):
        for col_index in range(len(order)):
            if np.isfinite(remaining[row_index, col_index]):
                count = int(remaining[row_index, col_index])
                axis.text(
                    col_index, row_index, str(count),
                    ha="center", va="center", fontsize=8,
                    color="white" if count > 0.55 * np.nanmax(remaining) else "black",
                )
    figure.colorbar(colors, ax=axis, label="Solutions restantes", shrink=0.8)
    figure.tight_layout()
    return figure


def _pareto_mask(table: pd.DataFrame, x: str, y: str) -> pd.Series:
    """Minimisation Pareto mask, retaining ties for an auditable frontier."""

    values = table[[x, y]].to_numpy(dtype=float)
    result = np.ones(len(table), dtype=bool)
    for index, point in enumerate(values):
        dominates = np.all(values <= point, axis=1) & np.any(values < point, axis=1)
        result[index] = not bool(np.any(dominates))
    return pd.Series(result, index=table.index)


def select_three_frontier_profiles(
    table: pd.DataFrame,
    *,
    rmse_column: str = "validation_rmse",
    es_column: str = "validation_es",
    parameter_column: str,
    feasible_column: str | None = None,
    feasible_columns: Sequence[str] = (),
) -> pd.DataFrame:
    """Select RMSE, compromise and ES profiles from validation outcomes.

    Profiles are outcome-based.  They are not the numerical minimum, median
    and maximum of lambda or the ES budget.  Non-converged, infeasible and
    dominated rows are excluded before the three decision points are chosen.
    """

    required = {rmse_column, es_column, parameter_column, "converged"}
    missing = required.difference(table.columns)
    if missing:
        raise KeyError(f"Colonnes absentes pour la sélection : {sorted(missing)}")
    eligible = table.loc[table["converged"].astype(bool)].copy()
    for column in ((feasible_column,) if feasible_column is not None else ()) + tuple(feasible_columns):
        if column not in eligible:
            raise KeyError(f"Colonne de faisabilité absente : {column}")
        eligible = eligible.loc[eligible[column].astype(bool)].copy()
    eligible = eligible.loc[
        np.isfinite(eligible[rmse_column]) & np.isfinite(eligible[es_column])
    ].copy()
    if eligible.empty:
        return eligible.assign(profile=pd.Series(dtype=str))
    eligible["is_pareto"] = _pareto_mask(eligible, rmse_column, es_column)
    frontier = eligible.loc[eligible["is_pareto"]].copy()

    rmse_range = float(frontier[rmse_column].max() - frontier[rmse_column].min())
    es_range = float(frontier[es_column].max() - frontier[es_column].min())
    rmse_scale = rmse_range if rmse_range > 0.0 else 1.0
    es_scale = es_range if es_range > 0.0 else 1.0
    frontier["compromise_score"] = np.sqrt(
        ((frontier[rmse_column] - frontier[rmse_column].min()) / rmse_scale) ** 2
        + ((frontier[es_column] - frontier[es_column].min()) / es_scale) ** 2
    )

    selections = [
        ("rmse_priority", frontier.sort_values([rmse_column, es_column]).iloc[0]),
        (
            "compromise",
            frontier.sort_values(["compromise_score", rmse_column, es_column]).iloc[0],
        ),
        ("es_priority", frontier.sort_values([es_column, rmse_column]).iloc[0]),
    ]
    rows: list[pd.Series] = []
    for profile, row in selections:
        selected = row.copy()
        selected["profile"] = profile
        selected["selection_reason"] = {
            "rmse_priority": "minimum validation RMSE on the non-dominated frontier",
            "compromise": "minimum normalised distance to the RMSE-ES ideal point",
            "es_priority": "minimum validation ES on the non-dominated frontier",
        }[profile]
        rows.append(selected)
    return pd.DataFrame(rows).reset_index(drop=True)


def select_budget_ceiling_profiles(
    table: pd.DataFrame, *, ceilings: Sequence[float],
) -> pd.DataFrame:
    """Choose one lowest-RMSE policy under each common validated ES ceiling.

    ``es_budget`` records the budget used to fit the weights. ``risk_limit_es``
    records the common limit against which they are selected. A policy fitted
    under a tighter budget may qualify for a looser limit even if it missed its
    own training budget on validation; these two checks remain visible.
    """

    limits = tuple(sorted(float(value) for value in ceilings))
    if len(limits) != 3 or any(not np.isfinite(value) or value <= 0 for value in limits):
        raise ValueError("Trois plafonds ES finis et positifs sont requis.")
    if limits != tuple(sorted(set(limits))):
        raise ValueError("Les plafonds ES doivent être distincts et croissants.")
    required = {"converged", "feasible_calibration", "validation_rmse", "validation_es", "es_budget"}
    missing = required.difference(table.columns)
    if missing:
        raise KeyError(f"Colonnes absentes pour les plafonds ES : {sorted(missing)}")
    eligible = table.loc[
        table["converged"].astype(bool)
        & table["feasible_calibration"].astype(bool)
        & np.isfinite(table["validation_rmse"])
        & np.isfinite(table["validation_es"])
    ].copy()
    profiles = (
        (limits[0], "es_priority", "strict"),
        (limits[1], "compromise", "intermédiaire"),
        (limits[2], "rmse_priority", "souple"),
    )
    rows: list[pd.Series] = []
    for ceiling, profile, level in profiles:
        admissible = eligible.loc[eligible["validation_es"] <= ceiling].copy()
        if admissible.empty:
            continue
        sort_columns = [column for column in (
            "validation_rmse", "validation_es", "n_options_active", "alpha", "l1_ratio", "es_budget",
        ) if column in admissible]
        chosen = admissible.sort_values(sort_columns, na_position="last").iloc[0].copy()
        chosen["profile"] = profile
        chosen["budget_level"] = level
        chosen["risk_limit_es"] = ceiling
        chosen["validation_cap_respected"] = True
        chosen["selection_reason"] = (
            "lowest validation RMSE among calibration-feasible candidates "
            f"with validation ES <= common {level} ceiling"
        )
        rows.append(chosen)
    return pd.DataFrame(rows).reset_index(drop=True) if rows else eligible.head(0).assign(
        profile=pd.Series(dtype=str), budget_level=pd.Series(dtype=str),
        risk_limit_es=pd.Series(dtype=float), validation_cap_respected=pd.Series(dtype=bool),
    )


def tail_budget_filter_flow(table: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    """Counts after each cumulative common-ceiling filter."""

    required = {
        "converged", "feasible_calibration", "validation_budget_respected",
        "validation_rmse", "validation_es",
    }
    missing = required.difference(table.columns)
    if missing:
        raise KeyError(f"Colonnes absentes pour la carte des filtres : {sorted(missing)}")
    stages: list[tuple[str, int]] = [("Solutions calculées", len(table))]
    eligible = table.loc[table["converged"].astype(bool)].copy()
    stages.append(("Convergence numérique", len(eligible)))
    eligible = eligible.loc[eligible["feasible_calibration"].astype(bool)].copy()
    stages.append(("Budget respecté en calibration", len(eligible)))
    maximum_ceiling = float(table["es_budget"].max()) if not table.empty else float("nan")
    eligible = eligible.loc[eligible["validation_es"] <= maximum_ceiling].copy()
    stages.append(("ES validé sous plafond souple", len(eligible)))
    eligible = eligible.loc[
        np.isfinite(eligible["validation_rmse"])
        & np.isfinite(eligible["validation_es"])
    ].copy()
    stages.append(("Mesures de validation finies", len(eligible)))
    if not eligible.empty:
        eligible = eligible.loc[_pareto_mask(eligible, "validation_rmse", "validation_es")]
    stages.append(("Frontière non dominée", len(eligible)))
    if profiles.empty:
        distinct = 0
    else:
        identity = [column for column in ("alpha", "l1_ratio", "es_budget", "support_id") if column in profiles]
        distinct = len(profiles[identity].drop_duplicates())
    stages.append(("Politiques distinctes retenues", distinct))
    rows = []
    previous = None
    for stage, count in stages:
        rows.append({
            "stage": stage, "remaining": count,
            "removed_at_stage": 0 if previous is None else previous - count,
        })
        previous = count
    return pd.DataFrame(rows)


def plot_tail_budget_filter_flow(flow: pd.DataFrame, *, title: str) -> plt.Figure:
    """A readable funnel showing retained and rejected budget candidates."""

    figure, axis = plt.subplots(figsize=(11, 5.5))
    positions = np.arange(len(flow))
    axis.barh(positions, flow["remaining"], color="#2c7a7b")
    axis.set_yticks(positions, flow["stage"])
    axis.invert_yaxis()
    axis.set_xlabel("Nombre de solutions encore admissibles")
    axis.set_title(title)
    axis.grid(axis="x", alpha=0.2)
    axis.set_axisbelow(True)
    maximum = max(int(flow["remaining"].max()), 1)
    axis.set_xlim(0, maximum * 1.27)
    for index, row in flow.iterrows():
        removed = int(row["removed_at_stage"])
        axis.text(
            float(row["remaining"]) + maximum * 0.015, index,
            f'{int(row["remaining"])}  ({removed} éliminée(s))',
            va="center", fontsize=9,
        )
    figure.tight_layout()
    return figure


def run_tail_hyperparameter_grid(
    *,
    calibration_A: np.ndarray,
    calibration_b: np.ndarray,
    validation_A: np.ndarray,
    validation_b: np.ndarray,
    penalty: str,
    alpha_values: Sequence[float],
    l1_ratio_values: Sequence[float],
    lambda_es_values: Sequence[float],
    es_budget_values: Sequence[float],
    es_level: float = 0.975,
    calibration_sample_weights: np.ndarray | None = None,
    unpenalized_indices: tuple[int, ...] = (),
    active_threshold: float = 1e-6,
    max_iter: int = 3000,
    tolerance: float = 1e-8,
) -> dict[str, pd.DataFrame]:
    """Evaluate complete lambda-ES and ES-budget grids on validation data."""

    calibration_A = np.asarray(calibration_A, dtype=float)
    calibration_b = np.asarray(calibration_b, dtype=float)
    validation_A = np.asarray(validation_A, dtype=float)
    validation_b = np.asarray(validation_b, dtype=float)
    ratios = tuple(float(value) for value in l1_ratio_values)
    if penalty != "elastic_net":
        ratios = (0.5,)
    rows: list[dict[str, object]] = []
    results: dict[tuple[object, ...], Any] = {}
    option_mask = np.ones(calibration_A.shape[1], dtype=bool)
    option_mask[list(unpenalized_indices)] = False

    specifications: list[tuple[str, float, float | None]] = [
        ("penalized_es", float(value), None) for value in lambda_es_values
    ] + [("constrained_es", 0.0, float(value)) for value in es_budget_values]
    for ratio in ratios:
        for alpha in (float(value) for value in alpha_values):
            warm_start: np.ndarray | None = None
            for objective, lambda_es, es_budget in specifications:
                config = TailRiskOptimizationConfig(
                    objective=objective,
                    penalty=penalty,
                    alpha=alpha,
                    l1_ratio=ratio,
                    es_level=es_level,
                    lambda_es=lambda_es,
                    es_budget=es_budget,
                    unpenalized_indices=unpenalized_indices,
                    active_threshold=active_threshold,
                    max_iter=max_iter,
                    tolerance=tolerance,
                )
                fitted = solve_tail_risk_replication(
                    calibration_A,
                    calibration_b,
                    config,
                    sample_weights=calibration_sample_weights,
                    initial_weights=warm_start,
                )
                if fitted.converged and fitted.feasible:
                    warm_start = fitted.weights
                losses = validation_b - validation_A @ fitted.weights
                risk = empirical_var_es(losses, es_level)
                key = (objective, ratio, alpha, lambda_es, es_budget)
                results[key] = fitted
                rows.append(
                    {
                        "objective": objective,
                        "penalty": penalty,
                        "alpha": alpha,
                        "l1_ratio": ratio if penalty == "elastic_net" else np.nan,
                        "lambda_es": lambda_es if objective == "penalized_es" else np.nan,
                        "es_budget": es_budget if objective == "constrained_es" else np.nan,
                        "converged": fitted.converged,
                        "feasible_calibration": fitted.feasible,
                        "calibration_rmse": fitted.rmse,
                        "calibration_es": fitted.expected_shortfall,
                        "validation_rmse": float(np.sqrt(np.mean(losses**2))),
                        "validation_mae": float(np.mean(np.abs(losses))),
                        "validation_var": float(risk["var"]),
                        "validation_es": float(risk["es"]),
                        "validation_budget_respected": bool(
                            objective != "constrained_es"
                            or float(risk["es"]) <= float(es_budget)
                        ),
                        "n_active_coefficients": int(
                            np.count_nonzero(np.abs(fitted.weights) > active_threshold)
                        ),
                        "n_options_active": int(np.count_nonzero(
                            (np.abs(fitted.weights) > active_threshold) & option_mask
                        )),
                        "n_iterations": fitted.n_iterations,
                    }
                )
    table = pd.DataFrame(rows)
    lambda_table = table.loc[table["objective"].eq("penalized_es")].copy()
    budget_table = table.loc[table["objective"].eq("constrained_es")].copy()
    lambda_table["lambda_response_detected"] = False
    for _, group in lambda_table.groupby(["alpha", "l1_ratio"], dropna=False):
        group = group.loc[group["converged"] & group["feasible_calibration"]]
        if group["lambda_es"].nunique() < 2:
            continue
        rmse_values = group["validation_rmse"].to_numpy(dtype=float)
        es_values = group["validation_es"].to_numpy(dtype=float)
        responsive = (
            not np.allclose(rmse_values, rmse_values[0], rtol=1e-3, atol=1e-4)
            or not np.allclose(es_values, es_values[0], rtol=1e-3, atol=1e-4)
        )
        lambda_table.loc[group.index, "lambda_response_detected"] = responsive
    table["lambda_response_detected"] = False
    table.loc[lambda_table.index, "lambda_response_detected"] = lambda_table[
        "lambda_response_detected"
    ]
    # With signed ES and unpenalized cash, lambda >= 1 can reward an
    # arbitrarily large positive cash shift more than RMSE penalizes it.
    table["lambda_selection_allowed"] = (
        table["objective"].ne("penalized_es") | table["lambda_es"].lt(1.0)
    )
    lambda_table["lambda_selection_allowed"] = lambda_table["lambda_es"].lt(1.0)
    lambda_profiles = select_three_frontier_profiles(
        lambda_table.loc[
            lambda_table["lambda_response_detected"]
            & lambda_table["lambda_selection_allowed"]
        ],
        parameter_column="lambda_es",
    )
    budget_profiles = (
        select_budget_ceiling_profiles(budget_table, ceilings=es_budget_values)
        if len(es_budget_values) == 3 else select_three_frontier_profiles(
            budget_table, parameter_column="es_budget",
            feasible_columns=("feasible_calibration", "validation_budget_respected"),
        )
    )
    budget_filter_flow = tail_budget_filter_flow(budget_table, budget_profiles)
    return {
        "table": table,
        "lambda_table": lambda_table,
        "budget_table": budget_table,
        "lambda_profiles": lambda_profiles,
        "budget_profiles": budget_profiles,
        "budget_filter_flow": budget_filter_flow,
        "results": results,
    }


def merge_tail_rho_grids(grids: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Combine separately scaled Elastic-Net rho grids before selecting profiles."""

    if not grids:
        raise ValueError("Au moins une grille rho est requise.")
    table = pd.concat([grid["table"] for grid in grids], ignore_index=True)
    lambda_table = table.loc[table["objective"].eq("penalized_es")].copy()
    budget_table = table.loc[table["objective"].eq("constrained_es")].copy()
    table["lambda_selection_allowed"] = (
        table["objective"].ne("penalized_es") | table["lambda_es"].lt(1.0)
    )
    lambda_table["lambda_selection_allowed"] = lambda_table["lambda_es"].lt(1.0)
    lambda_profiles = select_three_frontier_profiles(
        lambda_table.loc[
            lambda_table["lambda_response_detected"]
            & lambda_table["lambda_selection_allowed"]
        ],
        parameter_column="lambda_es",
    )
    ceilings = sorted(budget_table["es_budget"].dropna().unique())
    budget_profiles = (
        select_budget_ceiling_profiles(budget_table, ceilings=ceilings)
        if len(ceilings) == 3 else select_three_frontier_profiles(
            budget_table, parameter_column="es_budget",
            feasible_columns=("feasible_calibration", "validation_budget_respected"),
        )
    )
    return {
        "table": table, "lambda_table": lambda_table, "budget_table": budget_table,
        "lambda_profiles": lambda_profiles, "budget_profiles": budget_profiles,
        "budget_filter_flow": tail_budget_filter_flow(budget_table, budget_profiles),
        "results": {key: value for grid in grids for key, value in grid["results"].items()},
    }


def run_l0_tail_support_grid(
    *,
    calibration_A: np.ndarray,
    calibration_b: np.ndarray,
    validation_A: np.ndarray,
    validation_b: np.ndarray,
    support_weights: Sequence[np.ndarray],
    alpha_ratios: Sequence[float],
    lambda_es_values: Sequence[float],
    es_budget_values: Sequence[float],
    es_level: float = 0.975,
    unpenalized_indices: tuple[int, ...] = (),
    active_threshold: float = 1e-6,
    max_iter: int = 3000,
) -> dict[str, Any]:
    """Heuristic L0 search over previously found supports, with ES refits.

    This never claims to solve the global non-convex L0 problem. Within each
    fixed support the refit is convex; alpha changes which support wins on
    calibration, never the validation data or the held-out test.
    """

    A = np.asarray(calibration_A, dtype=float)
    b = np.asarray(calibration_b, dtype=float).reshape(-1)
    V = np.asarray(validation_A, dtype=float)
    v = np.asarray(validation_b, dtype=float).reshape(-1)
    if A.ndim != 2 or V.ndim != 2 or A.shape[1] != V.shape[1] or A.shape[0] != len(b) or V.shape[0] != len(v):
        raise ValueError("Matrices et cibles de calibration/validation incompatibles.")
    if not unpenalized_indices:
        raise ValueError("La recherche L0 requiert la colonne cash non pénalisée.")
    if not all(np.all(np.isfinite(value)) for value in (A, b, V, v)):
        raise ValueError("Les données L0 doivent être finies.")
    cash = tuple(sorted(set(int(index) for index in unpenalized_indices)))
    if any(index < 0 or index >= A.shape[1] for index in cash):
        raise ValueError("Indice cash L0 invalide.")
    option_mask = np.ones(A.shape[1], dtype=bool)
    option_mask[list(cash)] = False
    supports: list[tuple[int, ...]] = []
    for weights in support_weights:
        weights = np.asarray(weights, dtype=float).reshape(-1)
        if weights.shape != (A.shape[1],) or not np.all(np.isfinite(weights)):
            raise ValueError("Les poids L0 doivent correspondre aux colonnes de la matrice.")
        support = tuple(np.flatnonzero((np.abs(weights) > active_threshold) & option_mask).tolist())
        if len(support) >= 2 and support not in supports:
            supports.append(support)
    if not supports:
        raise ValueError("Aucun support L0 convergé avec au moins deux options.")
    cash_fit, *_ = np.linalg.lstsq(A[:, cash], b, rcond=None)
    cash_rmse = float(np.sqrt(np.mean((b - A[:, cash] @ cash_fit) ** 2)))
    support_rmse = []
    for support in supports:
        columns = cash + support
        fitted_weights, *_ = np.linalg.lstsq(A[:, columns], b, rcond=None)
        support_rmse.append(float(np.sqrt(np.mean((b - A[:, columns] @ fitted_weights) ** 2))))
    best_index = int(np.argmin(support_rmse))
    alpha_reference = max(
        (cash_rmse - support_rmse[best_index]) / len(supports[best_index]), 1e-10
    )
    specifications = [("penalized_es", float(value), None) for value in lambda_es_values]
    specifications += [("constrained_es", 0.0, float(value)) for value in es_budget_values]
    rows: list[dict[str, Any]] = []
    solutions: dict[tuple[Any, ...], Any] = {}
    for objective, lambda_es, budget in specifications:
        refits: list[dict[str, Any]] = []
        for support_id, support in enumerate(supports):
            columns = cash + support
            fitted = solve_tail_risk_replication(
                A[:, columns], b,
                TailRiskOptimizationConfig(
                    objective=objective, penalty="l2", alpha=0.0,
                    lambda_es=lambda_es, es_budget=budget, es_level=es_level,
                    unpenalized_indices=tuple(range(len(columns))),
                    active_threshold=active_threshold, max_iter=max_iter,
                ),
            )
            full_weights = np.zeros(A.shape[1])
            full_weights[list(columns)] = fitted.weights
            losses = v - V @ full_weights
            risk = empirical_var_es(losses, es_level)
            n_options = int(np.count_nonzero((np.abs(full_weights) > active_threshold) & option_mask))
            refits.append({
                "support_id": support_id, "support_size": len(support),
                "weights": full_weights, "fitted": fitted, "n_options_active": n_options,
                "validation_rmse": float(np.sqrt(np.mean(losses**2))),
                "validation_var": float(risk["var"]), "validation_es": float(risk["es"]),
            })
        for ratio in alpha_ratios:
            alpha = float(ratio) * alpha_reference
            admissible = [item for item in refits if item["fitted"].converged and item["fitted"].feasible]
            # Still report a failed point when no support meets the calibration constraint.
            candidates = admissible or refits
            chosen = min(candidates, key=lambda item: (
                item["fitted"].rmse + lambda_es * item["fitted"].expected_shortfall
                + alpha * item["n_options_active"], item["support_id"],
            ))
            fitted = chosen["fitted"]
            key = (objective, alpha, lambda_es, budget)
            solutions[key] = chosen["weights"]
            rows.append({
                "objective": objective, "penalty": "l0", "alpha": alpha,
                "alpha_relative_tail": float(ratio), "l1_ratio": np.nan,
                "lambda_es": lambda_es if objective == "penalized_es" else np.nan,
                "es_budget": budget if objective == "constrained_es" else np.nan,
                "converged": bool(fitted.converged), "feasible_calibration": bool(fitted.feasible),
                "calibration_rmse": float(fitted.rmse),
                "calibration_es": float(fitted.expected_shortfall),
                "validation_rmse": chosen["validation_rmse"],
                "validation_var": chosen["validation_var"],
                "validation_es": chosen["validation_es"],
                "validation_budget_respected": bool(
                    objective != "constrained_es" or chosen["validation_es"] <= float(budget)
                ),
                "n_active_coefficients": int(np.count_nonzero(np.abs(chosen["weights"]) > active_threshold)),
                "n_options_active": chosen["n_options_active"],
                "support_id": chosen["support_id"], "support_size": chosen["support_size"],
                "n_iterations": int(fitted.n_iterations),
                "method_status": "L0 support-refit heuristic; not a global optimum",
            })
    table = pd.DataFrame(rows)
    lambda_table = table.loc[table["objective"].eq("penalized_es")].copy()
    budget_table = table.loc[table["objective"].eq("constrained_es")].copy()
    lambda_table["lambda_response_detected"] = False
    for _, group in lambda_table.groupby("alpha"):
        valid = group.loc[group["converged"] & group["feasible_calibration"]]
        if len(valid) < 2:
            continue
        responsive = (
            not np.allclose(valid["validation_rmse"], valid["validation_rmse"].iloc[0], rtol=1e-3, atol=1e-4)
            or not np.allclose(valid["validation_es"], valid["validation_es"].iloc[0], rtol=1e-3, atol=1e-4)
        )
        lambda_table.loc[valid.index, "lambda_response_detected"] = responsive
    table["lambda_response_detected"] = False
    table.loc[lambda_table.index, "lambda_response_detected"] = lambda_table["lambda_response_detected"]
    table["lambda_selection_allowed"] = (
        table["objective"].ne("penalized_es") | table["lambda_es"].lt(1.0)
    )
    lambda_table["lambda_selection_allowed"] = lambda_table["lambda_es"].lt(1.0)
    lambda_profiles = select_three_frontier_profiles(
        lambda_table.loc[
            lambda_table["lambda_response_detected"]
            & lambda_table["lambda_selection_allowed"]
        ], parameter_column="lambda_es",
    )
    budget_profiles = (
        select_budget_ceiling_profiles(budget_table, ceilings=es_budget_values)
        if len(es_budget_values) == 3 else select_three_frontier_profiles(
            budget_table, parameter_column="es_budget",
            feasible_columns=("feasible_calibration", "validation_budget_respected"),
        )
    )
    return {
        "table": table, "lambda_table": lambda_table, "budget_table": budget_table,
        "lambda_profiles": lambda_profiles, "budget_profiles": budget_profiles,
        "budget_filter_flow": tail_budget_filter_flow(budget_table, budget_profiles),
        "results": solutions, "alpha_reference": alpha_reference,
        "n_distinct_supports": len(supports),
    }


def fixed_tail_profile_policies(
    grid_results: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Retrieve the fitted weights of every retained tail-risk profile.

    The returned weights are copies. This function performs no refit and does
    not choose policies using the importance-sampling pilot.
    """

    by_family: dict[str, list[dict[str, Any]]] = {}
    for (family, penalty), result in grid_results.items():
        for objective, profile_key in (
            ("penalized_es", "lambda_profiles"),
            ("constrained_es", "budget_profiles"),
        ):
            profiles = pd.DataFrame(result[profile_key])
            for _, row in profiles.iterrows():
                alpha = float(row["alpha"])
                lambda_es = float(row["lambda_es"]) if objective == "penalized_es" else 0.0
                budget = float(row["es_budget"]) if objective == "constrained_es" else None
                if penalty == "l0":
                    key = (objective, alpha, lambda_es, budget)
                else:
                    rho = float(row["l1_ratio"]) if penalty == "elastic_net" else 0.5
                    key = (objective, rho, alpha, lambda_es, budget)
                if key not in result["results"]:
                    raise KeyError(f"Poids du profil ES introuvables : {family}/{penalty}/{key}.")
                fitted = result["results"][key]
                weights = np.asarray(fitted if penalty == "l0" else fitted.weights, dtype=float).copy()
                if weights.ndim != 1 or not np.all(np.isfinite(weights)):
                    raise ValueError(f"Poids non finis pour {family}/{penalty}/{key}.")
                by_family.setdefault(family, []).append({
                    "family": family, "penalty": penalty, "objective": objective,
                    "profile": str(row["profile"]), "alpha": alpha,
                    "l1_ratio": float(row["l1_ratio"]) if penalty == "elastic_net" else np.nan,
                    "lambda_es": lambda_es if objective == "penalized_es" else np.nan,
                    "es_budget": budget if budget is not None else np.nan,
                    "risk_limit_es": float(row["risk_limit_es"]) if objective == "constrained_es" and "risk_limit_es" in row else np.nan,
                    "weights": weights,
                    "method_status": (
                        "L0 support-refit heuristic; not a global optimum"
                        if penalty == "l0" else "convex fixed-policy fit"
                    ),
                })
    return by_family


def evaluate_alpha_tail_frontier(
    result: Mapping[str, Any],
    validation_A: np.ndarray,
    validation_b: np.ndarray,
    *,
    es_level: float = 0.975,
) -> pd.DataFrame:
    """Evaluate every converged alpha on new paths, without changing selection.

    The original RMSE/sparsity filter is intentionally not reused: a candidate
    dominated on those two axes may still improve ES. The final test block in
    ``result`` remains untouched.
    """

    A = np.asarray(validation_A, dtype=float)
    b = np.asarray(validation_b, dtype=float).reshape(-1)
    if A.ndim != 2 or A.shape[0] != len(b) or not len(b):
        raise ValueError("La matrice et la cible de validation sont incompatibles.")
    if not np.all(np.isfinite(A)) or not np.all(np.isfinite(b)):
        raise ValueError("La validation doit contenir uniquement des valeurs finies.")
    table = pd.DataFrame(result["table"])
    required = {"penalty", "solution_index", "alpha", "converged", "n_options_active"}
    missing = required.difference(table.columns)
    if missing:
        raise KeyError(f"Colonnes alpha absentes : {sorted(missing)}")
    profiles = pd.DataFrame(result["profiles"])
    filters = result.get("candidate_filters", {})
    min_options = int(filters.get("min_active_options", 2))
    max_options = int(filters.get("max_active_options", 100))
    rows: list[dict[str, object]] = []
    for _, candidate in table.loc[
        table["converged"].astype(bool) & table["n_options_active"].ge(2)
    ].iterrows():
        penalty = str(candidate["penalty"])
        solution_index = int(candidate["solution_index"])
        weights = np.asarray(
            result["results"][penalty]["solutions"][solution_index]["weights"],
            dtype=float,
        )
        if weights.shape != (A.shape[1],):
            raise ValueError("La politique et la matrice externe n'ont pas les mêmes instruments.")
        losses = b - A @ weights
        risk = empirical_var_es(losses, es_level)
        retained = profiles.loc[
            profiles["penalty"].eq(penalty)
            & profiles["solution_index"].eq(solution_index)
        ] if not profiles.empty else pd.DataFrame()
        rows.append({
            "family": result["family"],
            "penalty": penalty,
            "solution_index": solution_index,
            "alpha": float(candidate["alpha"]),
            "n_options_active": int(candidate["n_options_active"]),
            "alpha_relative": float(candidate.get("alpha_relative", np.nan)),
            "l1_ratio": float(candidate.get("l1_ratio", np.nan)),
            "eligible_for_es_profiles": (
                bool(candidate.get("passes_stability_filter", False))
                and min_options <= int(candidate["n_options_active"]) <= max_options
            ),
            "validation_rmse": float(np.sqrt(np.mean(losses**2))),
            "validation_mae": float(np.mean(np.abs(losses))),
            "validation_var": float(risk["var"]),
            "validation_es": float(risk["es"]),
            "validation_tail_ess": float(risk["tail_effective_sample_size"]),
            "retained_profiles": ", ".join(retained["profile"].astype(str))
                if not retained.empty else "",
        })
    evaluated = pd.DataFrame(rows)
    if evaluated.empty:
        return evaluated
    evaluated["pareto_rmse_es_options"] = False
    columns = ("validation_rmse", "validation_es", "n_options_active")
    for _, group in evaluated.groupby("penalty", sort=False):
        values = group.loc[:, columns].to_numpy(dtype=float)
        for position, index in enumerate(group.index):
            dominated = np.all(values <= values[position], axis=1) & np.any(
                values < values[position], axis=1
            )
            evaluated.loc[index, "pareto_rmse_es_options"] = not bool(np.any(dominated))
    return evaluated


ES_SELECTION_PROFILES = {
    "es_minimum": ("validation_es",),
    "rmse_es_compromise": ("validation_rmse", "validation_es"),
    "rmse_es_sparsity_compromise": ("validation_rmse", "validation_es", "n_options_active"),
}
ES_SELECTION_MARKERS = dict(zip(ES_SELECTION_PROFILES, ("E", "RE", "REP")))


def select_es_profiles(table: pd.DataFrame) -> pd.DataFrame:
    """Choose one candidate per ES rule, universe and penalty."""
    if table.empty:
        return table.assign(profile=pd.Series(dtype=str))
    eligible = table.loc[table["eligible_for_es_profiles"]]
    metrics = ["validation_es", "validation_rmse", "n_options_active"]
    selected = []
    for _, group in eligible.groupby(["family", "penalty"], sort=False):
        values = group[metrics]
        span = values.max() - values.min()
        normalized = (values - values.min()).div(span.mask(span.eq(0), 1.0))
        for profile, axes in ES_SELECTION_PROFILES.items():
            distance = np.sqrt(normalized[list(axes)].pow(2).sum(axis=1))
            ranked = group.assign(selection_score=distance).sort_values(
                ["selection_score", *metrics, "solution_index"]
            )
            selected.append(ranked.head(1).assign(profile=profile))
    if not selected:
        return eligible.assign(profile=pd.Series(dtype=str))
    return pd.concat(selected, ignore_index=True)


def plot_alpha_tail_frontier(
    table: pd.DataFrame,
    *,
    nominal: float = 100.0,
    title: str = "Politiques conditionnelles B",
    language: str = "fr",
    panel: str | None = None,
) -> plt.Figure:
    """Plot the full candidate set and zoom, together or separately."""
    if table.empty:
        raise ValueError("Aucun candidat convergé à représenter.")
    if language not in {"fr", "en"}:
        raise ValueError("language doit être fr ou en.")
    if panel not in {None, "overview", "zoom"}:
        raise ValueError("panel must be overview or zoom.")
    english = language == "en"
    colors = {"l0": "#9467bd", "l1": "#1f77b4", "l2": "#ff7f0e", "elastic_net": "#2ca02c"}
    names = {"l0": "$L^0$", "l1": "Lasso", "l2": "Ridge", "elastic_net": "Elastic Net"}
    data = table.copy()
    data["plot_rmse"] = data["validation_rmse"] * 100.0 / nominal
    data["plot_es"] = data["validation_es"] * 100.0 / nominal
    frontier_mask = data["pareto_rmse_es_options"].astype(bool)
    retained_mask = data["retained_profiles"].fillna("").ne("")
    es_profiles = (
        select_es_profiles(data)
        if "eligible_for_es_profiles" in data
        else data.iloc[:0]
    )
    eligible_mask = (
        data["eligible_for_es_profiles"].astype(bool)
        if "eligible_for_es_profiles" in data else pd.Series(True, index=data.index)
    )
    # Recompute dominance on the same admissible pool used for ES selection.
    frontier_mask = pd.Series(False, index=data.index)
    for _, group in data.loc[eligible_mask].groupby("penalty", sort=False):
        values = group[["plot_rmse", "plot_es", "n_options_active"]].to_numpy()
        for position, index in enumerate(group.index):
            dominated = np.all(values <= values[position], axis=1) & np.any(
                values < values[position], axis=1
            )
            frontier_mask.loc[index] = not dominated.any()
    selected_labels = {}
    codes = {"performance": "P", "compromise": "C", "parsimony": "S"}
    for row in data.loc[retained_mask].itertuples():
        selected_labels[(row.penalty, row.solution_index)] = [
            codes.get(profile.strip(), profile.strip())
            for profile in row.retained_profiles.split(",")
        ]
    for row in es_profiles.itertuples():
        selected_labels.setdefault((row.penalty, row.solution_index), []).append(
            ES_SELECTION_MARKERS[row.profile]
        )
    selected_mask = pd.Series(
        [(row.penalty, row.solution_index) in selected_labels for row in data.itertuples()],
        index=data.index,
    )
    panels = ("overview", "zoom") if panel is None else (panel,)
    figure, axes = plt.subplots(
        len(panels), 1, figsize=(10, 10 if panel is None else 6.0), squeeze=False,
    )

    def marker_area(count):
        return 36.0 + 1.4 * np.asarray(count, dtype=float)

    for name, axis in zip(panels, axes[:, 0]):
        overview = name == "overview"
        if overview:
            other = data.loc[eligible_mask & ~frontier_mask]
            axis.scatter(other.plot_rmse, other.plot_es, s=12, alpha=0.35,
                         color="#94a3b8", edgecolors="none", zorder=1)
            excluded = data.loc[~eligible_mask]
            axis.scatter(excluded.plot_rmse, excluded.plot_es, s=20, marker="x",
                         color="#707987", linewidths=0.8, zorder=2)
            pool = data.loc[frontier_mask]
        else:
            pool = data.loc[selected_mask]
        for penalty, group in pool.groupby("penalty", sort=False):
            axis.scatter(group.plot_rmse, group.plot_es,
                         s=marker_area(group.n_options_active), facecolors="none",
                         edgecolors=colors[penalty], linewidths=1.6, zorder=3)
        axis.set_xlabel("RMSE totale (% du nominal)" if not english else "Total RMSE (% of notional)")
        axis.set_ylabel("ES à 97,5 % (% du nominal)" if not english else "97.5% ES (% of notional)")
        axis.grid(alpha=0.18)
        axis.set_title(
            ("Tous les candidats" if overview else "Profils sélectionnés")
            if not english else ("All candidates" if overview else "Selected profiles")
        )
        if not overview and not pool.empty:
            for column, setter in (("plot_rmse", axis.set_xlim), ("plot_es", axis.set_ylim)):
                low, high = pool[column].min(), pool[column].max()
                margin = max((high - low) * 0.20, 0.4)
                setter(low - margin, high + margin)
            # Place short profile labels in free display-space slots, with leaders.
            figure.canvas.draw()
            boxes = []
            offsets = [(12, 10), (12, -22), (-12, 12), (-12, -22),
                       (35, 30), (35, -40), (-35, 30), (-35, -40),
                       (65, 55), (65, -65), (-65, 55), (-65, -65)]
            for row in pool.sort_values(["plot_es", "plot_rmse"]).itertuples():
                labels = selected_labels[(row.penalty, row.solution_index)]
                label = "/".join(labels)
                x, y = axis.transData.transform((row.plot_rmse, row.plot_es))
                scale = figure.dpi / 72
                width, height = max(len(label) * 5.0, 12) * scale, 13 * scale
                candidates = []
                bounds = axis.get_window_extent()
                for dx, dy in offsets:
                    left = x + dx * scale - (width if dx < 0 else 0)
                    bottom = y + dy * scale
                    box = (left, bottom, left + width, bottom + height)
                    overlap = sum(
                        max(0, min(box[2], other[2]) - max(box[0], other[0]))
                        * max(0, min(box[3], other[3]) - max(box[1], other[1]))
                        for other in boxes
                    )
                    outside = not (
                        bounds.x0 < box[0] and box[2] < bounds.x1
                        and bounds.y0 < box[1] and box[3] < bounds.y1
                    )
                    candidates.append((outside, overlap, dx * dx + dy * dy, dx, dy, box))
                _, _, _, dx, dy, box = min(candidates)
                boxes.append(box)
                axis.annotate(
                    label, (row.plot_rmse, row.plot_es), xytext=(dx, dy),
                    textcoords="offset points", ha="right" if dx < 0 else "left",
                    va="bottom", fontsize=8, color=colors[row.penalty],
                    bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "none", "pad": 1},
                    arrowprops={"arrowstyle": "-", "color": colors[row.penalty],
                                "lw": 0.6, "alpha": 0.7},
                    zorder=5,
                )
    if panel != "overview":
        penalty_handles = [
            Line2D([], [], linestyle="None", marker="o", markerfacecolor="none",
                   markeredgecolor=color, label=names[penalty])
            for penalty, color in colors.items() if penalty in set(data.penalty)
        ]
        figure.legend(handles=penalty_handles, loc="lower center", ncol=4,
                      fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.19))
        counts = sorted(set(int(value) for value in np.quantile(data.n_options_active, [0, 0.5, 1])))
        size_handles = [
            Line2D([], [], linestyle="None", marker="o",
                   markersize=float(np.sqrt(marker_area(count))), markerfacecolor="none",
                   markeredgecolor="#64748b", label=f"{count} options")
            for count in counts
        ]
        if "overview" in panels:
            size_handles += [
                Line2D([], [], linestyle="None", marker="o", color="#94a3b8",
                       label="Autres admissibles" if not english else "Other eligible"),
                Line2D([], [], linestyle="None", marker="x", color="#707987",
                       label="Hors sélection" if not english else "Ineligible"),
            ]
        figure.legend(handles=size_handles, loc="lower center", ncol=len(size_handles),
                      fontsize=8, frameon=False, bbox_to_anchor=(0.5, 0.115))

        note = (
            "P performance · C RMSE/sparsity · S sparsity · E minimum ES · RE RMSE/ES · REP RMSE/ES/sparsity"
            if english else
            "P performance · C RMSE/parcimonie · S parcimonie · E ES minimale · RE RMSE/ES · REP RMSE/ES/parcimonie"
        )
        figure.text(0.5, 0.045, note, ha="center", fontsize=8)
    if panel is None:
        figure.suptitle(title.split(" — ")[0], fontsize=13)
    else:
        axes[0, 0].set_title("")
    figure.tight_layout(rect=(0, 0.29, 1, 0.94))
    if panel == "zoom":
        figure.set_layout_engine(None)
        axes[0, 0].set_position([0.09, 0.295, 0.89, 0.685])
        figure.legends[0].set_loc("center")
        figure.legends[0].set_bbox_to_anchor((0.5, 0.15))
        figure.legends[1].set_loc("center")
        figure.legends[1].set_bbox_to_anchor((0.5, 0.10))
        figure.texts[0].set_verticalalignment("center")
        figure.texts[0].set_position((0.5, 0.0625))

    return figure


def plot_regularization_grid(
    table: pd.DataFrame,
    profiles: pd.DataFrame | None = None,
    *,
    nominal: float = 100.0,
    title: str = "Chemins de régularisation — erreur de validation et taille du portefeuille",
) -> plt.Figure:
    """Show converged paths, unfinished solver states and retained profiles."""

    penalties = [value for value in ("l0", "l1", "l2", "elastic_net") if value in set(table["penalty"])]
    figure, axes = plt.subplots(len(penalties), 2, figsize=(13, 4.0 * len(penalties)), squeeze=False)
    colors = {"calls_puts": "tab:blue", "full": "tab:green"}
    profile_labels = {"performance": "P", "compromise": "C", "parsimony": "S"}
    selected = pd.DataFrame() if profiles is None else pd.DataFrame(profiles)
    for row, penalty in enumerate(penalties):
        subset = table.loc[table["penalty"].eq(penalty)]
        grouping = ["family"] + (["l1_ratio"] if penalty == "elastic_net" and "l1_ratio" in subset else [])
        for keys, group in subset.groupby(grouping, dropna=False, sort=False):
            family = keys[0] if isinstance(keys, tuple) else keys
            ratio = keys[1] if isinstance(keys, tuple) and len(keys) > 1 else None
            label = str(family) + (f" · rho={ratio:g}" if ratio is not None and pd.notna(ratio) else "")
            valid = group.loc[group["converged"]].sort_values("alpha_relative", ascending=False)
            unfinished = group.loc[~group["converged"]]
            color = colors.get(str(family))
            for column, metric in enumerate(("validation_rmse", "n_options_active")):
                scale = 100.0 / nominal if metric == "validation_rmse" else 1.0
                if not valid.empty:
                    axes[row, column].plot(
                        valid["alpha_relative"], valid[metric] * scale,
                        marker="o", label=label, color=color,
                    )
                if not unfinished.empty:
                    axes[row, column].scatter(
                        unfinished["alpha_relative"], unfinished[metric] * scale,
                        marker="x", s=55, color="#808080", alpha=0.8,
                        zorder=4, label="_nolegend_",
                    )
            if selected.empty:
                continue
            retained = selected.loc[
                selected["penalty"].eq(penalty) & selected["family"].eq(family)
            ]
            if ratio is not None and "l1_ratio" in retained:
                retained = retained.loc[np.isclose(retained["l1_ratio"].astype(float), float(ratio))]
            for alpha, chosen in retained.groupby("alpha_relative", sort=False):
                matching = valid.loc[np.isclose(valid["alpha_relative"], float(alpha))]
                if len(matching) != 1:
                    raise ValueError("Un profil retenu doit correspondre à un point convergé unique.")
                point = matching.iloc[0]
                initials = "/".join(profile_labels.get(name, str(name)) for name in chosen["profile"])
                for column, metric in enumerate(("validation_rmse", "n_options_active")):
                    value = float(point[metric]) * (100.0 / nominal if metric == "validation_rmse" else 1.0)
                    axes[row, column].scatter(
                        [alpha], [value], marker="*", s=210, facecolor=color,
                        edgecolor="black", linewidth=0.8, zorder=6,
                        label="_nolegend_",
                    )
                    axes[row, column].annotate(
                        initials, (alpha, value), xytext=(6, 6),
                        textcoords="offset points", fontsize=8,
                        fontweight="bold", color="black",
                    )
        for axis in axes[row]:
            axis.set_xscale("log")
            axis.invert_xaxis()
            axis.grid(alpha=0.25)
            axis.set_xlabel("Alpha relatif (régularisation forte → faible)")
        axes[row, 0].set_ylabel("RMSE de validation (% du nominal)")
        axes[row, 1].set_ylabel("Options actives")
        axes[row, 0].set_title(f"{penalty.upper()} — erreur de validation")
        axes[row, 1].set_title(f"{penalty.upper()} — taille du portefeuille")
    legend = [
        Line2D([], [], color=colors["calls_puts"], marker="o", label="Calls + Puts"),
        Line2D([], [], color=colors["full"], marker="o", label="Full"),
        Line2D([], [], linestyle="None", marker="x", color="#808080",
               label="Non convergé : état à l'arrêt du solveur"),
    ]
    legend.extend(
        Line2D([], [], linestyle="None", marker="*", markersize=11,
               markerfacecolor="white", markeredgecolor="black",
               label=f"{initial} : {name}")
        for name, initial in profile_labels.items()
    )
    figure.legend(handles=legend, loc="lower center", ncol=3, fontsize=8)
    figure.suptitle(title, fontsize=14)
    unfinished = table.loc[~table["converged"]]
    if not unfinished.empty:
        iterations = (
            f" (jusqu'à {int(unfinished['n_iterations'].max()):,} itérations)"
            if "n_iterations" in unfinished else ""
        )
        figure.text(
            0.5, 0.045,
            "Croix grises : métriques du portefeuille à l'arrêt du solveur"
            + iterations + "; valeurs provisoires, exclues de la sélection.",
            ha="center", fontsize=8, color="#555555",
        )
    figure.tight_layout(rect=(0, 0.10, 1, 0.96))
    return figure


def plot_rho_grid(
    table: pd.DataFrame,
    *,
    selected: pd.DataFrame | None = None,
    nominal: float = 100.0,
) -> plt.Figure:
    """Heatmaps: family in rows, metric in columns, alpha/rho on the axes."""

    data = table.loc[table["penalty"].eq("elastic_net")].copy()
    if data.empty:
        raise ValueError("Aucun résultat Elastic Net à représenter.")
    if not np.isfinite(nominal) or nominal <= 0:
        raise ValueError("Le nominal doit être strictement positif et fini.")
    ratios = np.sort(data["l1_ratio"].dropna().astype(float).unique())
    if not len(ratios):
        raise ValueError("La grille Elastic Net ne contient aucun ratio rho.")
    families = ("calls_puts", "full")
    reference_family = next(
        (family for family in families if data["family"].eq(family).any()), None,
    )
    if reference_family is None:
        raise ValueError("La grille Elastic Net ne contient aucune famille connue.")
    reference = data.loc[
        data["family"].eq(reference_family)
        & np.isclose(data["l1_ratio"], ratios[0])
    ].sort_values(
        "alpha_relative", ascending=False,
    )["alpha_relative"].to_numpy(dtype=float)
    if not len(reference) or not np.all(np.isfinite(reference)):
        raise ValueError("La grille d'alpha relatif est vide ou non finie.")
    metrics = ("validation_rmse", "n_options_active")
    matrices: dict[tuple[str, str], np.ndarray] = {}
    for family in families:
        for metric in metrics:
            matrices[(family, metric)] = np.full((len(reference), len(ratios)), np.nan)
        for column, ratio in enumerate(ratios):
            group = data.loc[
                data["family"].eq(family) & np.isclose(data["l1_ratio"], ratio)
            ].sort_values("alpha_relative", ascending=False)
            values = group["alpha_relative"].to_numpy(dtype=float)
            if len(values) != len(reference) or not np.allclose(
                values, reference, rtol=1e-7, atol=1e-12,
            ):
                raise ValueError(f"Grille d'alpha relatif incohérente pour {family}, rho={ratio:g}.")
            converged = group["converged"].astype(bool).to_numpy()
            for metric in metrics:
                entries = group[metric].to_numpy(dtype=float)
                if metric == "validation_rmse":
                    entries = entries * 100.0 / nominal
                matrices[(family, metric)][:, column] = np.where(
                    converged & np.isfinite(entries), entries, np.nan,
                )

    figure, axes = plt.subplots(2, 2, figsize=(14, 10), layout="constrained")
    family_names = {
        "calls_puts": "Calls + Puts (sans binaires)",
        "full": "Full (Calls + Puts + binaires)",
    }
    metric_names = {
        "validation_rmse": "Erreur de validation (RMSE)",
        "n_options_active": "Nombre d'options actives",
    }
    selected_rows = pd.DataFrame() if selected is None else pd.DataFrame(selected)
    images = {}
    for column, metric in enumerate(metrics):
        finite_values = np.concatenate([
            matrices[(family, metric)][np.isfinite(matrices[(family, metric)])]
            for family in families
        ])
        if not len(finite_values):
            raise ValueError(f"Aucune valeur convergée pour {metric}.")
        lower = 0.0 if metric == "n_options_active" else float(finite_values.min())
        upper = float(finite_values.max())
        if upper <= lower:
            upper = lower + 1.0
        cmap = plt.get_cmap(
            "RdYlGn_r" if metric == "validation_rmse" else "Blues"
        ).with_extremes(bad="#e5e7eb")
        for row, family in enumerate(families):
            axis = axes[row, column]
            image = axis.imshow(
                np.ma.masked_invalid(matrices[(family, metric)]),
                aspect="auto", interpolation="nearest", cmap=cmap,
                vmin=lower, vmax=upper,
            )
            images[(row, column)] = image
            axis.set_title(f"{family_names[family]} — {metric_names[metric]}")
            axis.set_xticks(range(len(ratios)), [f"{ratio:g}" for ratio in ratios])
            axis.set_xlabel("Ratio L1 ρ")
            if column == 0:
                ticks = np.unique(np.linspace(0, len(reference) - 1, 5).round().astype(int))
                axis.set_yticks(ticks, [f"{reference[index]:.3g}" for index in ticks])
                axis.set_ylabel("Alpha relatif (fort en haut → faible en bas)")
            else:
                axis.set_yticks([])
            chosen = selected_rows.loc[selected_rows["family"].eq(family)] if not selected_rows.empty else selected_rows
            profile_marks = {"performance": ("P", "#111827"),
                             "compromise": ("C", "#1d4ed8"),
                             "parsimony": ("S", "#7c2d12")}
            for _, selected_row in chosen.iterrows():
                ratio_key = "searched_l1_ratio" if "searched_l1_ratio" in selected_row else "l1_ratio"
                chosen_ratio = float(selected_row[ratio_key])
                chosen_alpha = float(selected_row["alpha_relative"])
                ratio_index = np.flatnonzero(np.isclose(ratios, chosen_ratio))
                alpha_index = np.flatnonzero(np.isclose(reference, chosen_alpha))
                if len(ratio_index) != 1 or len(alpha_index) != 1:
                    raise ValueError(f"Couple retenu absent de la grille pour {family}.")
                label, edge = profile_marks.get(str(selected_row.get("profile", "compromise")), ("C", "#1d4ed8"))
                axis.add_patch(Rectangle(
                    (ratio_index[0] - 0.5, alpha_index[0] - 0.5), 1, 1,
                    fill=False, edgecolor=edge, linewidth=2.8,
                ))
                axis.text(ratio_index[0], alpha_index[0], label, ha="center", va="center",
                          color=edge, fontsize=10, fontweight="bold",
                          bbox={"facecolor": "white", "alpha": 0.82, "pad": 0.7,
                                "edgecolor": "none"})
        figure.colorbar(
            images[(0, column)], ax=axes[:, column], shrink=0.82,
            label="RMSE (% du nominal)" if metric == "validation_rmse" else "Options actives",
        )
    figure.suptitle(
        "Elastic Net — grille conjointe (ρ, alpha) : trois profils retenus par famille",
        fontsize=13,
    )
    figure.text(0.5, 0.005, "P : performance · C : compromis · S : parcimonie · Gris : non convergé ou absent.", ha="center", fontsize=9)
    return figure


def plot_tail_frontiers(
    result: Mapping[str, pd.DataFrame],
    *,
    nominal: float = 100.0,
) -> plt.Figure:
    """Keep all candidates visible while emphasizing admissible Pareto policies."""

    figure, axes = plt.subplots(1, 2, figsize=(14, 5.2))
    specifications = (
        ("lambda_table", "lambda_profiles", "lambda_es", "ES pénalisé — grille lambda"),
        ("budget_table", "budget_profiles", "es_budget", "ES contraint — grille de budgets"),
    )
    markers = {"rmse_priority": "*", "compromise": "X", "es_priority": "P"}
    for axis, (table_key, profile_key, parameter, title) in zip(axes, specifications):
        table = pd.DataFrame(result[table_key]).copy()
        profiles = pd.DataFrame(result[profile_key]).copy()
        finite = table.loc[
            table["converged"].astype(bool)
            & np.isfinite(table["validation_rmse"])
            & np.isfinite(table["validation_es"])
        ].copy()
        axis.scatter(
            finite["validation_rmse"] * 100.0 / nominal,
            finite["validation_es"] * 100.0 / nominal,
            s=13, alpha=0.20, color="#94a3b8", edgecolors="none",
            label="Tous les candidats convergés",
        )
        eligible = finite.copy()
        if parameter == "lambda_es":
            if "lambda_selection_allowed" in eligible:
                eligible = eligible.loc[eligible["lambda_selection_allowed"].astype(bool)]
            if "lambda_response_detected" in eligible:
                eligible = eligible.loc[eligible["lambda_response_detected"].astype(bool)]
        required_flags = (
            ("feasible_calibration",)
            if parameter == "es_budget" else
            ("feasible_calibration", "validation_budget_respected")
        )
        for required in required_flags:
            if required in eligible:
                eligible = eligible.loc[eligible[required].astype(bool)].copy()
        if parameter == "es_budget" and not table.empty:
            eligible = eligible.loc[eligible["validation_es"] <= float(table["es_budget"].max())]
        frontier = eligible.loc[_pareto_mask(eligible, "validation_rmse", "validation_es")]
        scatter = axis.scatter(
            frontier["validation_rmse"] * 100.0 / nominal,
            frontier["validation_es"] * 100.0 / nominal,
            c=frontier[parameter], cmap="viridis", s=64, alpha=0.90,
            edgecolors="#334155", linewidths=0.6,
            vmin=float(table[parameter].min()) if len(table) else None,
            vmax=float(table[parameter].max()) if len(table) else None,
            label="Admissibles non dominés" if not frontier.empty else None,
        )
        for _, row in profiles.iterrows():
            axis.scatter(
                row["validation_rmse"] * 100.0 / nominal,
                row["validation_es"] * 100.0 / nominal,
                marker=markers[str(row["profile"])], s=170,
                edgecolor="black", linewidth=1.0,
                label=(
                    f"Plafond {row['budget_level']} : {float(row['risk_limit_es']) * 100.0 / nominal:g} %"
                    if parameter == "es_budget" and "risk_limit_es" in row and pd.notna(row["risk_limit_es"])
                    else {
                        "rmse_priority": "Priorité RMSE", "compromise": "Compromis",
                        "es_priority": "Priorité ES",
                    }.get(str(row["profile"]), str(row["profile"]))
                ),
            )
        axis.set_title(title)
        axis.set_xlabel("RMSE en validation indépendante (% du nominal)")
        axis.set_ylabel("ES 97,5 % en validation indépendante (% du nominal)")
        axis.grid(alpha=0.25)
        if parameter == "es_budget" and frontier.empty:
            minimum_es = float(finite["validation_es"].min()) if not finite.empty else float("nan")
            maximum_budget = float(table["es_budget"].max()) if not table.empty else float("nan")
            axis.text(
                0.5, 0.5,
                "Aucun candidat ne respecte le plafond ES souple\n"
                f"en validation ({len(finite)} convergés).\n"
                f"ES validé min. : {minimum_es * 100.0 / nominal:.2f} % ; "
                f"plafond souple : {maximum_budget * 100.0 / nominal:.2f} %",
                transform=axis.transAxes, ha="center", va="center", fontsize=10,
                bbox={"facecolor": "white", "edgecolor": "#475569", "alpha": 0.94},
            )
        if parameter == "lambda_es" and not eligible.empty and "lambda_selection_allowed" in finite:
            visible = finite.loc[finite["lambda_selection_allowed"].astype(bool)]
            excluded = finite.loc[~finite["lambda_selection_allowed"].astype(bool)]
            if not excluded.empty and (
                excluded["validation_rmse"].max() > 5.0 * visible["validation_rmse"].max()
                or excluded["validation_es"].min() < visible["validation_es"].min()
                - 5.0 * (visible["validation_es"].max() - visible["validation_es"].min())
            ):
                x_min, x_max = visible["validation_rmse"].agg(["min", "max"])
                y_min, y_max = visible["validation_es"].agg(["min", "max"])
                x_pad = max((x_max - x_min) * 0.06, 0.2 * nominal / 100.0)
                y_pad = max((y_max - y_min) * 0.06, 0.2 * nominal / 100.0)
                axis.set_xlim((x_min - x_pad) * 100.0 / nominal, (x_max + x_pad) * 100.0 / nominal)
                axis.set_ylim((y_min - y_pad) * 100.0 / nominal, (y_max + y_pad) * 100.0 / nominal)
                axis.text(
                    0.98, 0.03,
                    f"λ ≥ 1 exclu de la sélection ; {len(excluded)} points diagnostiques "
                    "(certains hors cadre).",
                    transform=axis.transAxes, ha="right", va="bottom", fontsize=8,
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9},
                )
        handles, labels = axis.get_legend_handles_labels()
        deduplicated = dict(zip(labels, handles))
        axis.legend(deduplicated.values(), deduplicated.keys(), fontsize=8)
        if not frontier.empty:
            figure.colorbar(scatter, ax=axis, label="Lambda ES" if parameter == "lambda_es" else "Budget ES absolu")
    figure.suptitle("Contrôle du risque de queue — tous les candidats, frontière et profils retenus", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, 0.95))
    return figure


def plot_seed_robustness(
    details: pd.DataFrame,
    *,
    metric: str = "validation_rmse",
    nominal: float = 100.0,
) -> plt.Figure:
    """Show converged-seed distributions and unfinished runs separately."""

    required = {"family", "penalty", "profile", "seed", metric}
    missing = required.difference(details.columns)
    if missing:
        raise KeyError(f"Colonnes absentes pour la stabilité : {sorted(missing)}")
    data = details.copy()
    families = list(dict.fromkeys(data["family"]))
    max_candidates = max(
        data.loc[data["family"].eq(family), ["penalty", "profile"]]
        .drop_duplicates().shape[0]
        for family in families
    )
    figure, axes = plt.subplots(
        1, len(families), figsize=(6.7 * len(families), max(6.0, 0.62 * max_candidates)),
        sharex=True, squeeze=False,
    )
    profile_names = {
        "performance": "Performance", "compromise": "Compromis", "parsimony": "Parcimonie"
    }
    scale = 100.0 / nominal if "rmse" in metric or "es" in metric else 1.0
    has_unfinished = False
    for axis, family in zip(axes[0], families):
        subset = data.loc[data["family"].eq(family)].copy()
        pairs = list(dict.fromkeys(zip(subset["penalty"], subset["profile"])))
        labels = []
        for position, (penalty, profile) in enumerate(pairs, start=1):
            group = subset.loc[
                subset["penalty"].eq(penalty) & subset["profile"].eq(profile)
            ]
            converged = group.loc[group["converged"].astype(bool), metric].to_numpy(dtype=float) * scale
            unfinished = group.loc[~group["converged"].astype(bool), metric].to_numpy(dtype=float) * scale
            converged = converged[np.isfinite(converged)]
            unfinished = unfinished[np.isfinite(unfinished)]
            labels.append(
                f"{'Elastic Net' if penalty == 'elastic_net' else penalty.upper()} · "
                f"{profile_names.get(profile, profile)}"
            )
            if len(converged):
                axis.boxplot(
                    [converged], positions=[position], vert=False, widths=0.5,
                    showmeans=True, showfliers=False, patch_artist=True,
                    boxprops={"facecolor": "#bfdbfe", "edgecolor": "#475569"},
                    medianprops={"color": "#ea580c", "linewidth": 1.8},
                    meanprops={"marker": "^", "markerfacecolor": "#16a34a",
                               "markeredgecolor": "#166534", "markersize": 7},
                )
                axis.scatter(
                    converged, np.full(len(converged), position),
                    s=22, alpha=0.65, color="tab:blue", zorder=4,
                )
            if len(unfinished):
                has_unfinished = True
                axis.scatter(
                    unfinished, np.full(len(unfinished), position),
                    marker="x", s=46, color="#808080", alpha=0.85, zorder=5,
                )
        axis.set_title("Calls + Puts" if family == "calls_puts" else "Full (avec binaires)")
        axis.set_yticks(range(1, len(labels) + 1), labels=labels)
        axis.set_xlabel(
            "RMSE de validation (% du nominal)" if metric == "validation_rmse"
            else metric.replace("_", " ") + (" (% du nominal)" if scale != 1.0 else "")
        )
        axis.invert_yaxis()
        axis.grid(axis="x", alpha=0.25)
    legend_handles = [
        Patch(facecolor="#bfdbfe", edgecolor="#475569", label="Boîte : 25e–75e percentile"),
        Line2D([], [], color="black", linewidth=1.4, marker="|", markersize=8,
               label="Moustaches : limite à 1,5 × IQR"),
        Line2D([], [], color="#ea580c", linewidth=2, label="Trait orange : médiane"),
        Line2D([], [], linestyle="None", marker="^", color="#16a34a", label="Triangle vert : moyenne"),
        Line2D([], [], linestyle="None", marker="o", color="tab:blue", label="Point bleu : recalibration"),
    ]
    if has_unfinished:
        legend_handles.append(
            Line2D([], [], linestyle="None", marker="x", color="#808080",
                   label="Croix grise : non convergé, résultat provisoire")
        )
    figure.legend(
        handles=legend_handles, loc="upper center", bbox_to_anchor=(0.5, 0.995),
        ncol=len(legend_handles), fontsize=9.5, frameon=False,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.91))
    return figure


def promote_hyperparameter_selection(
    *,
    source_run_dir: str | Path,
    destination: str | Path,
    current_configuration: Mapping[str, Any],
) -> Path:
    """Explicitly promote one completed study; never select the newest implicitly."""

    source = Path(source_run_dir)
    manifest_path = source / "manifest.json"
    selection_path = source / "selected_hyperparameters.json"
    if not manifest_path.exists() or not selection_path.exists():
        raise FileNotFoundError("La recherche ne contient pas son manifeste et sa sélection.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("completed", False):
        raise ValueError("Une recherche incomplète ne peut pas être promue.")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("run_mode") == "sprint":
        raise ValueError("Un run SPRINT est une prévisualisation et ne peut pas être promu.")
    expected = configuration_fingerprint(current_configuration)
    if selection.get("configuration_fingerprint") != expected:
        raise ValueError("La sélection ne correspond pas au produit et au modèle actuels.")
    budget_profiles = selection.get("selected_profiles", {}).get("es_budget")
    if budget_profiles is not None:
        for family in current_configuration.get("families", ()):
            matches = [
                row for row in budget_profiles
                if row.get("family") == family and row.get("profile") == "compromise"
            ]
            if len(matches) != 1:
                raise ValueError(f"Budget ES non validé pour {family} : profil intermédiaire absent ou ambigu.")
            chosen = matches[0]
            common_ceiling = chosen.get("risk_limit_es")
            valid = all(chosen.get(key) is True for key in ("converged", "feasible_calibration"))
            if common_ceiling is not None:
                valid = valid and (
                    chosen.get("validation_cap_respected") is True
                    and float(chosen["validation_es"]) <= float(common_ceiling)
                )
            else:
                valid = valid and chosen.get("validation_budget_respected") is True
            if not valid:
                raise ValueError(
                    f"Budget ES non validé pour {family} : promotion refusée. "
                    "Réexaminer les plafonds avant usage dans le notebook principal."
                )
    mixtures = selection.get("selected_profiles", {}).get("selected_importance_mixture")
    if mixtures is not None:
        missing_mixtures = [
            family for family in current_configuration.get("families", ())
            if family not in mixtures
        ]
        if missing_mixtures:
            raise ValueError(
                "Aucun mélange d'importance sampling admissible pour : "
                + ", ".join(missing_mixtures)
                + ". La sélection ne peut pas être utilisée par le notebook principal."
            )
    target = Path(destination)
    for mode in ("fast", "report"):
        if target.stem.endswith(f"_{mode}") and selection.get("run_mode") != mode:
            raise ValueError(f"Une recherche {selection.get('run_mode')} ne peut pas être promue en {mode}.")
    policy_source = source / "selected_policy_results.pkl"
    if not policy_source.is_file():
        raise FileNotFoundError("La recherche ne contient pas les politiques sélectionnées.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    policy_name = target.stem.replace("selected_hyperparameters", "selected_policy_results")
    policy_target = target.with_name(policy_name + ".pkl")
    policy_temporary = policy_target.with_suffix(policy_target.suffix + ".tmp")
    shutil.copyfile(selection_path, temporary)
    shutil.copyfile(policy_source, policy_temporary)
    policy_temporary.replace(policy_target)
    temporary.replace(target)
    return target


def load_selected_hyperparameters(
    path: str | Path,
    *,
    current_configuration: Mapping[str, Any],
) -> dict[str, Any]:
    """Load a promoted selection only when its full configuration matches."""

    selection_path = Path(path)
    if not selection_path.exists():
        raise FileNotFoundError(
            "Aucune sélection promue. Exécuter hyperparameter_research.ipynb puis "
            "promouvoir explicitement une recherche validée."
        )
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    expected = configuration_fingerprint(current_configuration)
    if selection.get("configuration_fingerprint") != expected:
        raise ValueError("Les hyperparamètres promus appartiennent à une autre configuration.")
    if selection.get("test_status") != "reserved_not_evaluated":
        raise ValueError("La sélection doit avoir été faite sans consulter le test final.")
    return selection


def export_hyperparameter_study(
    *,
    output_root: str | Path,
    run_mode: str,
    configuration: Mapping[str, Any],
    grid: HyperparameterGrid,
    tables: Mapping[str, Any],
    figures: Mapping[str, Any],
    selected_profiles: Mapping[str, Any],
    policy_results: Mapping[str, Any] | None = None,
    run_started_at: Any = None,
) -> dict[str, Any]:
    """Export one immutable hyperparameter run plus its machine-readable selection."""

    grid.validate()
    fingerprint = configuration_fingerprint(configuration)
    export = export_research_run(
        output_root=output_root,
        run_mode=run_mode,
        run_started_at=run_started_at,
        configuration={
            "contract_and_model": configuration,
            "configuration_fingerprint": fingerprint,
            "hyperparameter_grid": grid.to_dict(),
        },
        tables=tables,
        figures=figures,
        metadata={
            "study": "external_hyperparameter_research",
            "selection_status": "research_result_not_promoted_automatically",
            "test_status": "reserved_not_evaluated",
        },
        update_latest=True,
    )
    selection = {
        "source_run": export["run_id"],
        "run_mode": run_mode,
        "configuration_fingerprint": fingerprint,
        "configuration": configuration,
        "grid": grid.to_dict(),
        "selected_profiles": selected_profiles,
        "selection_status": "awaiting_explicit_promotion",
        "test_status": "reserved_not_evaluated",
    }
    selection_path = export["run_dir"] / "selected_hyperparameters.json"
    selection_path.write_text(
        json.dumps(selection, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if policy_results is not None:
        with (export["run_dir"] / "selected_policy_results.pkl").open("wb") as stream:
            pickle.dump(dict(policy_results), stream, protocol=pickle.HIGHEST_PROTOCOL)

    # Refresh latest only after the selection and optional policy objects exist.
    latest_dir = Path(output_root) / "latest"
    latest_tmp = Path(output_root) / ".latest_hyperparameter_tmp"
    if latest_tmp.exists():
        shutil.rmtree(latest_tmp)
    shutil.copytree(export["run_dir"], latest_tmp)
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    latest_tmp.rename(latest_dir)
    export["selection_path"] = selection_path
    return export


def load_selected_policy_results(
    path: str | Path,
    *,
    current_configuration: Mapping[str, Any],
) -> dict[str, Any]:
    """Load promoted policy objects after validating the adjacent JSON selection."""

    policy_path = Path(path)
    selection_name = policy_path.stem.replace("selected_policy_results", "selected_hyperparameters")
    load_selected_hyperparameters(
        policy_path.with_name(selection_name + ".json"),
        current_configuration=current_configuration,
    )
    if not policy_path.exists():
        raise FileNotFoundError("Les politiques sélectionnées n'ont pas été promues.")
    # This pickle is generated and consumed locally by this project.  Never use
    # this loader on an untrusted external file.
    with policy_path.open("rb") as stream:
        result = pickle.load(stream)
    if not isinstance(result, dict):
        raise TypeError("Le fichier de politiques promues doit contenir un dictionnaire.")
    return result

