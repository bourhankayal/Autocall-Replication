"""Stabilité multi-calibrations des profils de réplication pathwise."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..products import AutocallProduct
from .common import benchmark_metrics
from .optimization import SolverConfig, solve_l0_multistart, solve_replication
from .portfolio_diagnostics import DEFAULT_ACTIVE_THRESHOLD
from .regularization_path import (
    l0_alpha_max,
    lasso_alpha_max,
    ridge_alpha_reference,
    train_validation_test_slices,
)
from .risk import empirical_var_es


def _jaccard(left: np.ndarray, right: np.ndarray) -> float:
    union = np.count_nonzero(left | right)
    return 1.0 if union == 0 else float(np.count_nonzero(left & right) / union)


def _relative_distance(left: np.ndarray, right: np.ndarray) -> float:
    scale = max(float(np.linalg.norm(left)), float(np.linalg.norm(right)), 1e-15)
    return float(np.linalg.norm(left - right) / scale)


def run_pathwise_profile_stability(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_calibrations: int = 10,
    seeds: Sequence[int] | None = None,
    n_paths: int | None = None,
    min_active_options: int = 2,
    max_active_options: int = 100,
    min_valid_calibrations: int | None = None,
    active_threshold: float = DEFAULT_ACTIVE_THRESHOLD,
    max_iter: int = 5000,
    tolerance: float = 1e-6,
) -> dict[str, object]:
    """Recalibre les profils sur au moins dix jeux de trajectoires indépendants.

    L'alpha absolu est recalculé à partir de l'alpha relatif et de la référence
    propre à chaque calibration. Le bloc de test du résultat de base n'est ni
    lu ni évalué.
    """
    from .pathwise_payoff import build_pathwise_payoff_dataset

    if n_calibrations < 10:
        raise ValueError("La stabilité requiert au moins dix calibrations.")
    if seeds is None:
        base_seed = int(base_result.get("seed", 42))
        seeds = tuple(base_seed + offset for offset in range(n_calibrations))
    else:
        seeds = tuple(int(seed) for seed in seeds)
        if len(seeds) < 10:
            raise ValueError("seeds doit contenir au moins dix graines.")
        n_calibrations = len(seeds)
    if len(set(seeds)) != len(seeds):
        raise ValueError("Les graines de stabilité doivent être uniques.")

    profiles = pd.DataFrame(base_result["profiles"]).copy()
    if profiles.empty:
        return {
            "details": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "seeds": seeds,
            "n_calibrations": n_calibrations,
            "test_status": "reserved_not_evaluated",
        }
    vanillas = list(base_result["vanillas"])
    n_paths = int(n_paths if n_paths is not None else base_result["n_paths"])
    min_valid_calibrations = (
        n_calibrations - 1
        if min_valid_calibrations is None
        else int(min_valid_calibrations)
    )
    if not 1 <= min_valid_calibrations <= n_calibrations:
        raise ValueError("min_valid_calibrations est incompatible avec les graines.")

    base_weights: dict[tuple[str, int], np.ndarray] = {}
    for _, profile in profiles.iterrows():
        key = (str(profile["penalty"]), int(profile["solution_index"]))
        base_weights[key] = np.asarray(
            base_result["results"][key[0]]["solutions"][key[1]]["weights"],
            dtype=float,
        )

    detail_rows: list[dict[str, object]] = []
    for seed in seeds:
        X, y = build_pathwise_payoff_dataset(
            product=product,
            vanillas=vanillas,
            spot0=spot0,
            valuation_date=valuation_date,
            maturity_date=maturity_date,
            rate=rate,
            dividend_yield=dividend_yield,
            vol=vol,
            n_paths=n_paths,
            seed=seed,
        )
        slices = train_validation_test_slices(
            n_paths,
            train_fraction=float(base_result["split"]["train_fraction"]),
            validation_fraction=float(base_result["split"]["validation_fraction"]),
        )
        X_train, y_train = X[slices["train"]], y[slices["train"]]
        X_validation, y_validation = X[slices["validation"]], y[slices["validation"]]
        solved: dict[tuple[str, float, float | None], dict[str, object]] = {}

        for _, profile in profiles.iterrows():
            penalty = str(profile["penalty"])
            ratio = None if pd.isna(profile["l1_ratio"]) else float(profile["l1_ratio"])
            key = (penalty, float(profile["alpha_relative"]), ratio)
            if key not in solved:
                if penalty == "l2":
                    reference = ridge_alpha_reference(X_train)
                elif penalty == "l0":
                    reference = l0_alpha_max(X_train, y_train)
                else:
                    reference = lasso_alpha_max(
                        X_train,
                        y_train,
                        l1_ratio=1.0 if penalty == "l1" else float(ratio),
                    )
                alpha = float(profile["alpha_relative"]) * reference
                optimization = solve_replication(
                    X_train,
                    y_train,
                    SolverConfig(
                        solver="proximal" if penalty == "l0" else "fista",
                        penalty=penalty,
                        alpha=alpha,
                        l1_ratio=0.5 if ratio is None else ratio,
                        max_iter=max_iter,
                        tolerance=tolerance,
                    ),
                )
                weights = optimization.weights
                solved[key] = {
                    "alpha": alpha,
                    "weights": weights,
                    "optimization": optimization,
                    "metrics": benchmark_metrics(y_validation, X_validation @ weights),
                }

            calibration = solved[key]
            weights = np.asarray(calibration["weights"], dtype=float)
            reference_weights = base_weights[
                (penalty, int(profile["solution_index"]))
            ]
            support = np.abs(weights[1:]) > active_threshold
            reference_support = np.abs(reference_weights[1:]) > active_threshold
            active_count = int(np.count_nonzero(support))
            optimization = calibration["optimization"]
            detail_rows.append(
                {
                    "penalty": penalty,
                    "profile": str(profile["profile"]),
                    "seed": seed,
                    "alpha": float(calibration["alpha"]),
                    "alpha_relative": float(profile["alpha_relative"]),
                    "converged": bool(optimization.converged),
                    "validation_rmse": float(calibration["metrics"]["rmse"]),
                    "validation_mae": float(calibration["metrics"]["mae"]),
                    "n_options_active": active_count,
                    "active_count_is_valid": (
                        min_active_options <= active_count <= max_active_options
                    ),
                    "support_jaccard_vs_base": _jaccard(
                        support,
                        reference_support,
                    ),
                    "relative_weight_distance_vs_base": _relative_distance(
                        weights,
                        reference_weights,
                    ),
                    "sum_abs_option_weights": float(np.sum(np.abs(weights[1:]))),
                    "max_abs_option_weight": (
                        float(np.max(np.abs(weights[1:])))
                        if len(weights) > 1
                        else 0.0
                    ),
                }
            )

    details = pd.DataFrame(detail_rows)
    summary_rows: list[dict[str, object]] = []
    for (penalty, profile), group in details.groupby(
        ["penalty", "profile"], sort=False
    ):
        n_converged = int(group["converged"].sum())
        n_valid = int(group["active_count_is_valid"].sum())
        summary_rows.append(
            {
                "penalty": penalty,
                "profile": profile,
                "n_calibrations": len(group),
                "n_converged": n_converged,
                "convergence_rate": n_converged / len(group),
                "n_valid_active_counts": n_valid,
                "validation_rmse_mean": float(group["validation_rmse"].mean()),
                "validation_rmse_std": float(group["validation_rmse"].std(ddof=1)),
                "n_options_active_mean": float(group["n_options_active"].mean()),
                "n_options_active_std": float(group["n_options_active"].std(ddof=1)),
                "support_jaccard_median": float(
                    group["support_jaccard_vs_base"].median()
                ),
                "relative_weight_distance_mean": float(
                    group["relative_weight_distance_vs_base"].mean()
                ),
                "passes_stability_filter": (
                    n_converged == n_calibrations
                    and n_valid >= min_valid_calibrations
                ),
            }
        )

    return {
        "details": details,
        "summary": pd.DataFrame(summary_rows),
        "seeds": seeds,
        "n_calibrations": n_calibrations,
        "min_valid_calibrations": min_valid_calibrations,
        "candidate_rule": (
            f"convergence {n_calibrations}/{n_calibrations} et nombre d'actifs valide "
            f"sur au moins {min_valid_calibrations}/{n_calibrations} calibrations"
        ),
        "test_status": "reserved_not_evaluated",
    }


def apply_stability_filter(
    base_result: dict[str, object],
    stability_result: dict[str, object],
) -> dict[str, object]:
    """Retourne une vue du résultat limitée aux profils stables."""
    summary = pd.DataFrame(stability_result["summary"])
    profiles = pd.DataFrame(base_result["profiles"])
    if summary.empty or profiles.empty:
        stable_profiles = profiles.iloc[0:0].copy()
    else:
        accepted = summary.loc[
            summary["passes_stability_filter"], ["penalty", "profile"]
        ]
        stable_profiles = profiles.merge(
            accepted,
            on=["penalty", "profile"],
            how="inner",
            validate="one_to_one",
        )
    filtered = dict(base_result)
    filtered["profiles"] = stable_profiles
    filtered["profile_policies"] = stable_profiles.to_dict(orient="records")
    filtered["stability_filter_status"] = {
        "n_profiles_before": len(profiles),
        "n_profiles_after": len(stable_profiles),
        "rule": stability_result.get("candidate_rule"),
        "test_status": stability_result.get("test_status"),
    }
    return filtered


def run_conditional_policy_profile_stability(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_calibrations: int = 10,
    seeds: Sequence[int] | None = None,
    n_paths: int | None = None,
    min_active_options: int = 2,
    max_active_options: int = 100,
    min_valid_calibrations: int | None = None,
    active_threshold: float = DEFAULT_ACTIVE_THRESHOLD,
    max_iter: int = 5000,
    tolerance: float = 1e-6,
    l0_multistart: bool = False,
    evaluation_n_paths: int | None = None,
    evaluation_seed: int = 84000,
    es_level: float = 0.975,
    minimum_calibrations: int = 10,
) -> dict[str, object]:
    """Teste les profils conditionnels sur des recalibrations indépendantes.

    La topologie date/état est figée par la calibration initiale. Chaque graine
    régénère les trajectoires, recalcule l'échelle d'alpha et réestime tous les
    poids, sans jamais lire son bloc de test. Dix graines restent le minimum par
    défaut ; l'aperçu SPRINT peut explicitement en demander deux.
    """
    from .conditional_policy import build_external_policy_design

    if minimum_calibrations < 2 or n_calibrations < minimum_calibrations:
        raise ValueError("Nombre de calibrations insuffisant pour cet audit de stabilité.")
    if seeds is None:
        base_seed = int(base_result.get("seed", 42))
        seeds = tuple(base_seed + offset for offset in range(n_calibrations))
    else:
        seeds = tuple(int(seed) for seed in seeds)
        if len(seeds) < minimum_calibrations:
            raise ValueError("Nombre de graines insuffisant pour cet audit de stabilité.")
        n_calibrations = len(seeds)
    if len(set(seeds)) != len(seeds):
        raise ValueError("Les graines de stabilité doivent être uniques.")
    if evaluation_n_paths is not None:
        if evaluation_n_paths < 40:
            raise ValueError("L'évaluation commune requiert au moins 40 trajectoires.")
        if evaluation_seed in seeds or evaluation_seed == int(base_result.get("seed", 42)):
            raise ValueError("La graine d'évaluation doit être indépendante des calibrations.")
        if not 0.0 < es_level < 1.0:
            raise ValueError("Le niveau d'ES doit appartenir à ]0, 1[.")

    profiles = pd.DataFrame(base_result["profiles"]).copy()
    if profiles.empty:
        return {
            "details": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "seeds": seeds,
            "n_calibrations": n_calibrations,
            "test_status": "reserved_not_evaluated",
        }
    n_paths = int(n_paths if n_paths is not None else base_result["n_paths"])
    min_valid_calibrations = (
        n_calibrations - 1
        if min_valid_calibrations is None
        else int(min_valid_calibrations)
    )
    if not 1 <= min_valid_calibrations <= n_calibrations:
        raise ValueError("min_valid_calibrations est incompatible avec les graines.")

    base_weights = {
        (str(row["penalty"]), int(row["solution_index"])): np.asarray(
            base_result["results"][str(row["penalty"])]["solutions"][
                int(row["solution_index"])
            ]["weights"],
            dtype=float,
        )
        for _, row in profiles.iterrows()
    }
    cash_indices = tuple(int(index) for index in base_result["unpenalized_indices"])
    option_mask = np.ones(len(base_result["vanillas"]), dtype=bool)
    option_mask[list(cash_indices)] = False
    evaluation_design = (
        build_external_policy_design(
            base_result=base_result, product=product, spot0=spot0,
            valuation_date=valuation_date, maturity_date=maturity_date,
            rate=rate, dividend_yield=dividend_yield, vol=vol,
            n_paths=evaluation_n_paths, seed=evaluation_seed,
        ) if evaluation_n_paths is not None else None
    )
    evaluation_A = None if evaluation_design is None else np.asarray(evaluation_design["A"])
    evaluation_b = None if evaluation_design is None else np.asarray(evaluation_design["b"])
    base_common_metrics: dict[tuple[str, int], tuple[float, float]] = {}
    if evaluation_A is not None and evaluation_b is not None:
        for policy_key, reference_weights in base_weights.items():
            losses = evaluation_b - evaluation_A @ reference_weights
            base_common_metrics[policy_key] = (
                float(np.sqrt(np.mean(losses**2))),
                float(empirical_var_es(losses, es_level)["es"]),
            )
    detail_rows: list[dict[str, object]] = []
    supports_by_profile: dict[tuple[str, str], list[np.ndarray]] = {}

    for seed in seeds:
        design = build_external_policy_design(
            base_result=base_result,
            product=product,
            spot0=spot0,
            valuation_date=valuation_date,
            maturity_date=maturity_date,
            rate=rate,
            dividend_yield=dividend_yield,
            vol=vol,
            n_paths=n_paths,
            seed=seed,
        )
        A, y = np.asarray(design["A"]), np.asarray(design["b"])
        slices = train_validation_test_slices(
            n_paths,
            train_fraction=float(base_result["split"]["train_fraction"]),
            validation_fraction=float(base_result["split"]["validation_fraction"]),
        )
        A_train, y_train = A[slices["train"]], y[slices["train"]]
        A_validation, y_validation = A[slices["validation"]], y[slices["validation"]]
        solved: dict[tuple[str, float, float | None], dict[str, object]] = {}
        alpha_references: dict[tuple[str, float | None], float] = {}

        for _, profile in profiles.iterrows():
            penalty = str(profile["penalty"])
            ratio = None if pd.isna(profile["l1_ratio"]) else float(profile["l1_ratio"])
            key = (penalty, float(profile["alpha_relative"]), ratio)
            if key not in solved:
                reference_key = (penalty, ratio)
                if reference_key not in alpha_references:
                    if penalty == "l2":
                        reference = ridge_alpha_reference(
                            A_train, unpenalized_indices=cash_indices
                        )
                    elif penalty == "l0":
                        reference = l0_alpha_max(
                            A_train,
                            y_train,
                            unpenalized_indices=cash_indices,
                        )
                    else:
                        reference = lasso_alpha_max(
                            A_train,
                            y_train,
                            l1_ratio=1.0 if penalty == "l1" else float(ratio),
                            unpenalized_indices=cash_indices,
                        )
                    alpha_references[reference_key] = reference
                reference = alpha_references[reference_key]
                alpha = float(profile["alpha_relative"]) * reference
                config = SolverConfig(
                    solver="proximal" if penalty == "l0" else "fista",
                    penalty=penalty,
                    alpha=alpha,
                    l1_ratio=0.5 if ratio is None else ratio,
                    max_iter=max_iter,
                    tolerance=tolerance,
                    unpenalized_indices=cash_indices,
                )
                if penalty == "l0" and l0_multistart:
                    optimization, start_audit = solve_l0_multistart(
                        A_train, y_train, config,
                        seed=seed + int(profile["solution_index"]),
                        random_starts=3,
                    )
                    converged_objectives = [
                        float(start["objective_train"]) for start in start_audit
                        if start["converged"]
                    ]
                    l0_start_gap = (
                        (max(converged_objectives) - min(converged_objectives))
                        / max(abs(min(converged_objectives)), 1e-12)
                        if len(converged_objectives) >= 2 else np.nan
                    )
                else:
                    optimization = solve_replication(A_train, y_train, config)
                    l0_start_gap = np.nan
                weights = optimization.weights
                solved[key] = {
                    "alpha": alpha,
                    "weights": weights,
                    "optimization": optimization,
                    "l0_start_objective_gap": l0_start_gap,
                    "metrics": benchmark_metrics(y_validation, A_validation @ weights),
                }

            calibration = solved[key]
            weights = np.asarray(calibration["weights"], dtype=float)
            reference_weights = base_weights[(penalty, int(profile["solution_index"]))]
            support = (np.abs(weights) > active_threshold) & option_mask
            reference_support = (
                (np.abs(reference_weights) > active_threshold) & option_mask
            )
            active_count = int(np.count_nonzero(support))
            optimization = calibration["optimization"]
            profile_key = (penalty, str(profile["profile"]))
            supports_by_profile.setdefault(profile_key, []).append(support.copy())
            common_rmse = np.nan
            common_es = np.nan
            base_common_rmse = np.nan
            base_common_es = np.nan
            if evaluation_A is not None and evaluation_b is not None:
                common_losses = evaluation_b - evaluation_A @ weights
                common_rmse = float(np.sqrt(np.mean(common_losses**2)))
                common_es = float(empirical_var_es(common_losses, es_level)["es"])
                base_common_rmse, base_common_es = base_common_metrics[
                    (penalty, int(profile["solution_index"]))
                ]
            detail_rows.append(
                {
                    "family": base_result["family"],
                    "penalty": penalty,
                    "profile": str(profile["profile"]),
                    "solution_index": int(profile["solution_index"]),
                    "seed": seed,
                    "alpha": float(calibration["alpha"]),
                    "alpha_relative": float(profile["alpha_relative"]),
                    "converged": bool(optimization.converged),
                    "n_iterations": optimization.n_iterations,
                    "l0_start_objective_gap": calibration["l0_start_objective_gap"],
                    "validation_rmse": float(calibration["metrics"]["rmse"]),
                    "validation_mae": float(calibration["metrics"]["mae"]),
                    "n_options_active": active_count,
                    "base_n_options_active": int(np.count_nonzero(reference_support)),
                    "active_count_is_valid": min_active_options <= active_count <= max_active_options,
                    "support_jaccard_vs_base": _jaccard(support, reference_support),
                    "relative_weight_distance_vs_base": _relative_distance(weights, reference_weights),
                    "common_evaluation_rmse": common_rmse,
                    "common_evaluation_es": common_es,
                    "base_common_evaluation_rmse": base_common_rmse,
                    "base_common_evaluation_es": base_common_es,
                }
            )

    details = pd.DataFrame(detail_rows)
    summary_rows: list[dict[str, object]] = []
    for (family, penalty, profile), group in details.groupby(
        ["family", "penalty", "profile"], sort=False
    ):
        n_converged = int(group["converged"].sum())
        n_valid = int(group["active_count_is_valid"].sum())
        supports = [
            support for support, converged in zip(
                supports_by_profile[(str(penalty), str(profile))],
                group["converged"],
                strict=True,
            ) if converged
        ]
        pairwise_jaccard = [
            _jaccard(supports[left], supports[right])
            for left in range(len(supports)) for right in range(left + 1, len(supports))
        ]
        summary_rows.append(
            {
                "family": family,
                "penalty": penalty,
                "profile": profile,
                "solution_index": int(group["solution_index"].iloc[0]),
                "n_calibrations": len(group),
                "n_converged": n_converged,
                "convergence_rate": n_converged / len(group),
                "iterations_median": float(group["n_iterations"].median()),
                "l0_start_objective_gap_mean": float(group["l0_start_objective_gap"].mean()),
                "n_valid_active_counts": n_valid,
                "validation_rmse_mean": float(group["validation_rmse"].mean()),
                "validation_rmse_std": float(group["validation_rmse"].std(ddof=1)),
                "n_options_active_mean": float(group["n_options_active"].mean()),
                "n_options_active_std": float(group["n_options_active"].std(ddof=1)),
                "n_options_active_median": float(group["n_options_active"].median()),
                "n_options_active_min": int(group["n_options_active"].min()),
                "n_options_active_max": int(group["n_options_active"].max()),
                "base_n_options_active": int(group["base_n_options_active"].iloc[0]),
                "support_jaccard_median": float(group.loc[
                    group["converged"], "support_jaccard_vs_base"
                ].median()),
                "support_pairwise_jaccard_median": (
                    float(np.median(pairwise_jaccard)) if pairwise_jaccard else np.nan
                ),
                "relative_weight_distance_mean": float(group["relative_weight_distance_vs_base"].mean()),
                "common_evaluation_rmse_mean": float(group["common_evaluation_rmse"].mean()),
                "common_evaluation_rmse_std": float(group["common_evaluation_rmse"].std(ddof=1)),
                "common_evaluation_es_mean": float(group["common_evaluation_es"].mean()),
                "common_evaluation_es_std": float(group["common_evaluation_es"].std(ddof=1)),
                "base_common_evaluation_rmse": float(group["base_common_evaluation_rmse"].iloc[0]),
                "base_common_evaluation_es": float(group["base_common_evaluation_es"].iloc[0]),
                "common_evaluation_n_paths": evaluation_n_paths,
                "common_evaluation_seed": evaluation_seed if evaluation_design is not None else None,
                "passes_stability_filter": n_converged == n_calibrations and n_valid >= min_valid_calibrations,
            }
        )
    return {
        "details": details,
        "summary": pd.DataFrame(summary_rows),
        "seeds": seeds,
        "n_calibrations": n_calibrations,
        "min_valid_calibrations": min_valid_calibrations,
        "candidate_rule": (
            f"convergence {n_calibrations}/{n_calibrations} et nombre d'actifs valide "
            f"sur au moins {min_valid_calibrations}/{n_calibrations} calibrations"
        ),
        "topology_status": "base_policy_nodes_frozen",
        "common_evaluation_status": (
            "independent_common_paths_not_used_for_selection"
            if evaluation_design is not None else "not_evaluated"
        ),
        "common_evaluation_seed": evaluation_seed if evaluation_design is not None else None,
        "common_evaluation_n_paths": evaluation_n_paths,
        "test_status": "reserved_not_evaluated",
    }


def run_conditional_policy_candidate_stability(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    **stability_kwargs: object,
) -> dict[str, object]:
    """Audit every converged, nontrivial candidate before Pareto selection.

    The same independent seeds are used for every candidate. L0 receives a
    reproducible multistart rather than the single cold start used by the
    legacy profile-only diagnostic.
    """
    candidates = pd.DataFrame(base_result["raw_table"]).copy()
    candidates = candidates.loc[
        candidates["converged"].astype(bool)
        & candidates["n_options_active"].ge(2)
    ].copy()
    if not candidates.empty:
        candidates["profile"] = candidates.apply(
            lambda row: f"candidate_{row['penalty']}_{int(row['solution_index'])}",
            axis=1,
        )
    candidate_result = dict(base_result)
    candidate_result["profiles"] = candidates
    result = run_conditional_policy_profile_stability(
        base_result=candidate_result,
        product=product,
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        l0_multistart=True,
        **stability_kwargs,
    )
    result["scope"] = "all_converged_candidates_before_pareto"
    result["n_candidates_audited"] = len(candidates)
    return result
