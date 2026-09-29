"""Stabilité multi-calibrations des profils de réplication pathwise."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..products import AutocallProduct
from .common import benchmark_metrics
from .optimization import SolverConfig, solve_replication
from .portfolio_diagnostics import DEFAULT_ACTIVE_THRESHOLD
from .regularization_path import (
    l0_alpha_max,
    lasso_alpha_max,
    ridge_alpha_reference,
    train_validation_test_slices,
)


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
) -> dict[str, object]:
    """Teste les profils conditionnels sur dix recalibrations indépendantes.

    La topologie date/état est figée par la calibration initiale. Chaque graine
    régénère les trajectoires, recalcule l'échelle d'alpha et réestime tous les
    poids, sans jamais lire son bloc de test.
    """
    from .conditional_policy import build_external_policy_design

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
    detail_rows: list[dict[str, object]] = []

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

        for _, profile in profiles.iterrows():
            penalty = str(profile["penalty"])
            ratio = None if pd.isna(profile["l1_ratio"]) else float(profile["l1_ratio"])
            key = (penalty, float(profile["alpha_relative"]), ratio)
            if key not in solved:
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
                alpha = float(profile["alpha_relative"]) * reference
                optimization = solve_replication(
                    A_train,
                    y_train,
                    SolverConfig(
                        solver="proximal" if penalty == "l0" else "fista",
                        penalty=penalty,
                        alpha=alpha,
                        l1_ratio=0.5 if ratio is None else ratio,
                        max_iter=max_iter,
                        tolerance=tolerance,
                        unpenalized_indices=cash_indices,
                    ),
                )
                weights = optimization.weights
                solved[key] = {
                    "alpha": alpha,
                    "weights": weights,
                    "optimization": optimization,
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
            detail_rows.append(
                {
                    "family": base_result["family"],
                    "penalty": penalty,
                    "profile": str(profile["profile"]),
                    "seed": seed,
                    "alpha": float(calibration["alpha"]),
                    "alpha_relative": float(profile["alpha_relative"]),
                    "converged": bool(optimization.converged),
                    "validation_rmse": float(calibration["metrics"]["rmse"]),
                    "validation_mae": float(calibration["metrics"]["mae"]),
                    "n_options_active": active_count,
                    "active_count_is_valid": min_active_options <= active_count <= max_active_options,
                    "support_jaccard_vs_base": _jaccard(support, reference_support),
                    "relative_weight_distance_vs_base": _relative_distance(weights, reference_weights),
                }
            )

    details = pd.DataFrame(detail_rows)
    summary_rows: list[dict[str, object]] = []
    for (family, penalty, profile), group in details.groupby(
        ["family", "penalty", "profile"], sort=False
    ):
        n_converged = int(group["converged"].sum())
        n_valid = int(group["active_count_is_valid"].sum())
        summary_rows.append(
            {
                "family": family,
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
                "support_jaccard_median": float(group["support_jaccard_vs_base"].median()),
                "relative_weight_distance_mean": float(group["relative_weight_distance_vs_base"].mean()),
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
        "test_status": "reserved_not_evaluated",
    }
