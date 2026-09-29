"""Importance sampling pour l'évaluation du risque de politiques figées.

Les poids de vraisemblance définis ici sont des poids statistiques attachés
aux trajectoires. Ils ne modifient jamais les quantités d'options du
portefeuille de réplication.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..monte_carlo import _validate_gbm_parameters, _validated_business_grid
from ..products import AutocallProduct, VanillaProduct
from .common import contractual_simulation_end_date
from .conditional_policy import assemble_policy_design
from .risk import (
    DEFAULT_RISK_LEVELS,
    _risk_comparison_row,
    risk_table_in_notional_units,
    tail_risk_metrics,
)
from .semi_static import autocall_state_curve_on_path
from .static_cashflows import (
    autocall_value_curve_on_path,
    effective_date_on_path,
)
from .pathwise_payoff import vanilla_discounted_payoff_from_path


DEFAULT_IMPORTANCE_TILTS = (0.0, -1.0, -2.0)
DEFAULT_IMPORTANCE_MIXTURE = (0.50, 0.30, 0.20)


def _effective_sample_size(weights: np.ndarray) -> float:
    weights = np.asarray(weights, dtype=float).reshape(-1)
    denominator = float(np.sum(weights**2))
    if denominator <= 0.0:
        return 0.0
    return float(np.sum(weights) ** 2 / denominator)


def _validate_importance_mixture(
    tilts: Sequence[float],
    mixture_probabilities: Sequence[float],
) -> tuple[np.ndarray, np.ndarray]:
    tilts_array = np.asarray(tuple(tilts), dtype=float)
    probabilities = np.asarray(tuple(mixture_probabilities), dtype=float)
    if tilts_array.ndim != 1 or len(tilts_array) == 0:
        raise ValueError("tilts doit contenir au moins une composante.")
    if probabilities.shape != tilts_array.shape:
        raise ValueError("tilts et mixture_probabilities doivent avoir la même taille.")
    if not np.all(np.isfinite(tilts_array)):
        raise ValueError("Les déformations doivent être finies.")
    if not np.all(np.isfinite(probabilities)) or np.any(probabilities <= 0.0):
        raise ValueError("Les probabilités du mélange doivent être finies et positives.")
    if not math.isclose(float(np.sum(probabilities)), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("Les probabilités du mélange doivent sommer à 1.")
    return tilts_array, probabilities


def simulate_gbm_paths_importance(
    spot0: float,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int,
    seed: int | None = None,
    tilts: Sequence[float] = DEFAULT_IMPORTANCE_TILTS,
    mixture_probabilities: Sequence[float] = DEFAULT_IMPORTANCE_MIXTURE,
) -> dict[str, object]:
    """Simule un mélange gaussien et retourne les poids cible/proposition.

    Une déformation ``theta`` est répartie sur les incréments selon
    ``sqrt(dt / T)``. Elle correspond donc à un déplacement terminal contrôlé
    en nombre d'écarts-types, indépendamment du nombre de dates simulées.
    La distribution cible reste le GBM risque-neutre non déformé.
    """
    if isinstance(n_paths, bool) or not isinstance(n_paths, (int, np.integer)):
        raise ValueError("n_paths doit être un entier strictement positif.")
    if n_paths < 1:
        raise ValueError("n_paths doit être un entier strictement positif.")
    _validate_gbm_parameters(spot0, rate, dividend_yield, vol)
    tilts_array, probabilities = _validate_importance_mixture(
        tilts, mixture_probabilities
    )
    dates = _validated_business_grid(pd.Timestamp(start_date), pd.Timestamp(end_date))
    paths = np.empty((n_paths, len(dates)), dtype=float)
    paths[:, 0] = float(spot0)
    rng = np.random.default_rng(seed)
    component_indices = rng.choice(
        len(tilts_array), size=n_paths, p=probabilities
    )

    if len(dates) == 1:
        likelihood_weights = np.ones(n_paths, dtype=float)
        return {
            "dates": dates,
            "paths": paths,
            "shocks": np.empty((n_paths, 0), dtype=float),
            "log_likelihood_weights": np.zeros(n_paths, dtype=float),
            "likelihood_weights": likelihood_weights,
            "component_indices": component_indices,
            "component_tilts": tilts_array[component_indices],
            "tilts": tuple(float(value) for value in tilts_array),
            "mixture_probabilities": tuple(float(value) for value in probabilities),
            "diagnostics": {
                "n_paths": n_paths,
                "weight_mean": 1.0,
                "weight_min": 1.0,
                "weight_max": 1.0,
                "weight_cv": 0.0,
                "effective_sample_size": float(n_paths),
                "effective_sample_ratio": 1.0,
            },
        }

    day_gaps = np.diff(dates.values).astype("timedelta64[D]").astype(float)
    dt = day_gaps / 365.0
    total_time = float(np.sum(dt))
    direction = np.sqrt(dt / total_time)
    base_shocks = rng.normal(size=(n_paths, len(dt)))
    component_tilts = tilts_array[component_indices]
    shocks = base_shocks + component_tilts[:, None] * direction[None, :]

    drift = (rate - dividend_yield - 0.5 * vol * vol) * dt
    diffusion = vol * np.sqrt(dt)[None, :] * shocks
    paths[:, 1:] = float(spot0) * np.exp(
        np.cumsum(drift[None, :] + diffusion, axis=1)
    )

    projection = shocks @ direction
    log_terms = (
        np.log(probabilities)[None, :]
        + projection[:, None] * tilts_array[None, :]
        - 0.5 * tilts_array[None, :] ** 2
    )
    row_max = np.max(log_terms, axis=1)
    log_q_over_p = row_max + np.log(
        np.sum(np.exp(log_terms - row_max[:, None]), axis=1)
    )
    log_likelihood_weights = -log_q_over_p
    likelihood_weights = np.exp(log_likelihood_weights)
    weight_mean = float(np.mean(likelihood_weights))
    weight_std = float(np.std(likelihood_weights, ddof=1)) if n_paths > 1 else 0.0
    ess = _effective_sample_size(likelihood_weights)

    component_rows = []
    normalized_weights = likelihood_weights / np.sum(likelihood_weights)
    for component_index, (tilt, probability) in enumerate(
        zip(tilts_array, probabilities)
    ):
        mask = component_indices == component_index
        component_rows.append(
            {
                "component": int(component_index),
                "tilt": float(tilt),
                "configured_probability": float(probability),
                "simulated_count": int(np.sum(mask)),
                "simulated_frequency": float(np.mean(mask)),
                "weighted_target_mass": float(np.sum(normalized_weights[mask])),
            }
        )

    return {
        "dates": dates,
        "paths": paths,
        "shocks": shocks,
        "log_likelihood_weights": log_likelihood_weights,
        "likelihood_weights": likelihood_weights,
        "component_indices": component_indices,
        "component_tilts": component_tilts,
        "tilts": tuple(float(value) for value in tilts_array),
        "mixture_probabilities": tuple(float(value) for value in probabilities),
        "component_summary": pd.DataFrame(component_rows),
        "diagnostics": {
            "n_paths": n_paths,
            "weight_mean": weight_mean,
            "weight_min": float(np.min(likelihood_weights)),
            "weight_max": float(np.max(likelihood_weights)),
            "weight_cv": weight_std / weight_mean if weight_mean > 0.0 else np.inf,
            "effective_sample_size": ess,
            "effective_sample_ratio": ess / n_paths,
        },
    }


def weighted_tail_risk_metrics(
    losses: np.ndarray,
    likelihood_weights: np.ndarray,
    levels: Sequence[float] = DEFAULT_RISK_LEVELS,
) -> dict[str, float]:
    """Calcule les métriques de risque avec les poids de vraisemblance."""
    losses = np.asarray(losses, dtype=float).reshape(-1)
    weights = np.asarray(likelihood_weights, dtype=float).reshape(-1)
    if losses.shape != weights.shape:
        raise ValueError("losses et likelihood_weights doivent avoir la même taille.")
    valid = np.isfinite(losses) & np.isfinite(weights) & (weights >= 0.0)
    losses, weights = losses[valid], weights[valid]
    if len(losses) == 0 or float(np.sum(weights)) <= 0.0:
        raise ValueError("Les pertes pondérées ne contiennent aucune observation valide.")
    normalized = weights / np.sum(weights)
    mean_loss = float(np.sum(normalized * losses))
    metrics = {
        "n_observations": float(len(losses)),
        "effective_sample_size": _effective_sample_size(weights),
        "mean_loss": mean_loss,
        "mae": float(np.sum(normalized * np.abs(losses))),
        "loss_std": float(np.sqrt(np.sum(normalized * (losses - mean_loss) ** 2))),
        "rmse": float(np.sqrt(np.sum(normalized * losses**2))),
        "max_loss": float(np.max(losses[weights > 0.0])),
        "under_replication_rate": float(np.sum(normalized * (losses > 0.0))),
    }
    order = np.argsort(losses, kind="stable")
    sorted_losses = losses[order]
    sorted_weights = normalized[order]
    cumulative = np.cumsum(sorted_weights)
    for level in levels:
        level = float(level)
        if not 0.5 < level < 1.0:
            raise ValueError("Chaque niveau de risque doit appartenir à ]0.5, 1[.")
        quantile_index = min(int(np.searchsorted(cumulative, level, side="left")), len(losses) - 1)
        value_at_risk = float(sorted_losses[quantile_index])
        tail_mask = losses >= value_at_risk
        tail_weights = weights[tail_mask]
        suffix = str(int(round(level * 1000))).rstrip("0")
        metrics[f"var_{suffix}"] = value_at_risk
        metrics[f"es_{suffix}"] = float(
            np.sum(tail_weights * losses[tail_mask]) / np.sum(tail_weights)
        )
        metrics[f"tail_effective_sample_size_{suffix}"] = _effective_sample_size(
            tail_weights
        )
    return metrics


def bootstrap_expected_shortfall_interval(
    losses: np.ndarray,
    level: float = 0.975,
    likelihood_weights: np.ndarray | None = None,
    n_bootstrap: int = 200,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> dict[str, float]:
    """Intervalle bootstrap de l'ES, standard ou auto-normalisé pondéré."""
    losses = np.asarray(losses, dtype=float).reshape(-1)
    is_weighted = likelihood_weights is not None
    weights = (
        np.ones(len(losses), dtype=float)
        if not is_weighted
        else np.asarray(likelihood_weights, dtype=float).reshape(-1)
    )
    if len(losses) != len(weights):
        raise ValueError("losses et likelihood_weights doivent avoir la même taille.")
    if n_bootstrap < 20:
        raise ValueError("n_bootstrap doit être supérieur ou égal à 20.")
    if not 0.5 < confidence_level < 1.0:
        raise ValueError("confidence_level doit appartenir à ]0.5, 1[.")
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_bootstrap, dtype=float)
    suffix = str(int(round(float(level) * 1000))).rstrip("0")
    for index in range(n_bootstrap):
        sample = rng.integers(0, len(losses), size=len(losses))
        sample_metrics = (
            weighted_tail_risk_metrics(
                losses[sample], weights[sample], levels=(level,)
            )
            if is_weighted
            else tail_risk_metrics(losses[sample], levels=(level,))
        )
        estimates[index] = sample_metrics[f"es_{suffix}"]
    alpha = 1.0 - confidence_level
    point_metrics = (
        weighted_tail_risk_metrics(losses, weights, levels=(level,))
        if is_weighted
        else tail_risk_metrics(losses, levels=(level,))
    )
    return {
        "estimate": point_metrics[f"es_{suffix}"],
        "ci_low": float(np.quantile(estimates, alpha / 2.0)),
        "ci_high": float(np.quantile(estimates, 1.0 - alpha / 2.0)),
        "bootstrap_std": float(np.std(estimates, ddof=1)),
        "n_bootstrap": int(n_bootstrap),
    }


def _conditional_dataset_from_paths(
    product: AutocallProduct,
    vanillas: Sequence[VanillaProduct],
    dates: pd.DatetimeIndex,
    path_matrix: np.ndarray,
    valuation_date: pd.Timestamp,
    rate: float,
) -> list[dict[str, object]]:
    dataset: list[dict[str, object]] = []
    common_dates: pd.DatetimeIndex | None = None
    for path_values in np.asarray(path_matrix, dtype=float):
        path = pd.Series(path_values, index=dates)
        y_curve = autocall_value_curve_on_path(
            product=product,
            path=path,
            valuation_date=valuation_date,
            rate=rate,
            curve_dates=common_dates,
        )
        curve_dates = pd.DatetimeIndex(y_curve.index)
        if common_dates is None:
            common_dates = curve_dates
        elif not common_dates.equals(curve_dates):
            raise ValueError("Les dates de cashflows diffèrent entre les trajectoires.")
        X_curve = np.zeros((len(curve_dates), len(vanillas)), dtype=float)
        date_to_index = {pd.Timestamp(date): index for index, date in enumerate(curve_dates)}
        for vanilla_index, vanilla in enumerate(vanillas):
            payment_date = effective_date_on_path(path, vanilla.maturity_date)
            if payment_date not in date_to_index:
                raise ValueError(
                    f"La maturité {payment_date} de {vanilla.name} ne correspond à aucune date d'observation."
                )
            date_index = date_to_index[payment_date]
            X_curve[date_index, vanilla_index] = vanilla_discounted_payoff_from_path(
                vanilla=vanilla,
                path=path,
                valuation_date=valuation_date,
                rate=rate,
            )
        state_curve = autocall_state_curve_on_path(
            product=product,
            path=path,
            valuation_date=valuation_date,
            curve_dates=curve_dates,
        )
        dataset.append(
            {
                "path": path,
                "dates": curve_dates,
                "X_curve": X_curve,
                "y_curve": y_curve.to_numpy(dtype=float),
                "alive_before": state_curve["alive_before"].to_numpy(dtype=bool),
                "barrier_hit": state_curve["barrier_hit"].to_numpy(dtype=bool),
            }
        )
    return dataset


def evaluate_conditional_policy_profile_risk_importance(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int = 20_000,
    seed: int = 20500,
    levels: Sequence[float] = DEFAULT_RISK_LEVELS,
    min_condition_observations: int = 200,
    tilts: Sequence[float] = DEFAULT_IMPORTANCE_TILTS,
    mixture_probabilities: Sequence[float] = DEFAULT_IMPORTANCE_MIXTURE,
) -> dict[str, object]:
    """Évalue une politique figée par IS, sans recalibrer ses poids financiers."""
    if n_paths < 100:
        raise ValueError("L'analyse de risque requiert au moins 100 trajectoires.")
    profiles = pd.DataFrame(base_result["profiles"]).copy()
    if profiles.empty:
        raise ValueError("Aucun profil n'est disponible pour l'analyse de risque.")
    valuation_date = pd.Timestamp(valuation_date)
    simulation_end = contractual_simulation_end_date(
        product=product,
        contract_start_date=valuation_date,
        requested_maturity_date=pd.Timestamp(maturity_date),
    )
    simulation = simulate_gbm_paths_importance(
        spot0=spot0,
        start_date=valuation_date,
        end_date=simulation_end,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
        tilts=tilts,
        mixture_probabilities=mixture_probabilities,
    )
    likelihood_weights = np.asarray(simulation["likelihood_weights"], dtype=float)
    dataset = _conditional_dataset_from_paths(
        product=product,
        vanillas=list(base_result["source_vanillas"]),
        dates=pd.DatetimeIndex(simulation["dates"]),
        path_matrix=np.asarray(simulation["paths"], dtype=float),
        valuation_date=valuation_date,
        rate=rate,
    )
    design = assemble_policy_design(
        dataset=dataset,
        nodes=list(base_result["nodes"]),
        assignments=dict(base_result["assignments"]),
        vanillas=list(base_result["source_vanillas"]),
    )
    A, y = np.asarray(design["A"]), np.asarray(design["b"])
    path_results = [
        product.compute_autocall_payoff(item["path"], start_date=valuation_date)
        for item in dataset
    ]
    called = np.asarray([item["call_date"] is not None for item in path_results])
    barrier_hit = np.asarray([bool(item["barrier_hit"][-1]) for item in dataset])
    conditions = {
        "all": np.ones(n_paths, dtype=bool),
        "recalled": called,
        "maturity": ~called,
        "barrier_hit": barrier_hit,
    }
    normalized_weights = likelihood_weights / np.sum(likelihood_weights)
    gross_reference_value = float(np.sum(normalized_weights * y))
    gross_losses = y - gross_reference_value

    gross_rows: list[dict[str, object]] = []
    condition_rows: list[dict[str, object]] = []
    for condition, mask in conditions.items():
        if not np.any(mask):
            continue
        condition_weights = likelihood_weights[mask]
        condition_ess = _effective_sample_size(condition_weights)
        condition_frequency = float(np.sum(normalized_weights[mask]))
        reliability = (
            "sufficient"
            if condition_ess >= min_condition_observations
            else "warning_low_effective_sample_size"
        )
        condition_rows.append(
            {
                "condition": condition,
                "n_observations": int(np.sum(mask)),
                "effective_sample_size": condition_ess,
                "condition_frequency": condition_frequency,
                "quantile_reliability": reliability,
            }
        )
        gross_rows.append(
            {
                "condition": condition,
                "condition_frequency": condition_frequency,
                "quantile_reliability": reliability,
                **weighted_tail_risk_metrics(
                    gross_losses[mask], condition_weights, levels=levels
                ),
            }
        )

    residual_rows: list[dict[str, object]] = []
    profile_losses: dict[tuple[str, str], np.ndarray] = {}
    for _, profile in profiles.iterrows():
        penalty, profile_name = str(profile["penalty"]), str(profile["profile"])
        financial_weights = np.asarray(
            base_result["results"][penalty]["solutions"][
                int(profile["solution_index"])
            ]["weights"],
            dtype=float,
        )
        losses = y - A @ financial_weights
        profile_losses[(penalty, profile_name)] = losses
        for condition, mask in conditions.items():
            if not np.any(mask):
                continue
            condition_weights = likelihood_weights[mask]
            condition_ess = _effective_sample_size(condition_weights)
            residual_rows.append(
                {
                    "family": base_result["family"],
                    "penalty": penalty,
                    "profile": profile_name,
                    "condition": condition,
                    "condition_frequency": float(np.sum(normalized_weights[mask])),
                    "quantile_reliability": (
                        "sufficient"
                        if condition_ess >= min_condition_observations
                        else "warning_low_effective_sample_size"
                    ),
                    **weighted_tail_risk_metrics(
                        losses[mask], condition_weights, levels=levels
                    ),
                }
            )

    gross_table = pd.DataFrame(gross_rows)
    residual_table = pd.DataFrame(residual_rows)
    gross_by_condition = gross_table.set_index("condition")
    comparison_rows = []
    for _, row in residual_table.iterrows():
        comparison = _risk_comparison_row(
            row, gross_by_condition.loc[row["condition"]], levels
        )
        comparison["family"] = base_result["family"]
        comparison_rows.append(comparison)
    conditional_comparison = pd.DataFrame(comparison_rows)
    comparison = conditional_comparison.loc[
        conditional_comparison["condition"] == "all"
    ].reset_index(drop=True)
    risk_summary_columns = [
        "family", "penalty", "profile", "mean_replication_error",
        "mae_replication_error", "under_replication_rate", "gross_rmse",
        "residual_rmse", "rmse_reduction", "rmse_relative_reduction",
        "gross_es_975", "residual_es_975", "es_975_reduction",
        "es_975_relative_reduction", "gross_max_loss", "residual_max_loss",
    ]
    risk_summary = comparison.loc[:, risk_summary_columns].copy()
    monetary_columns = [
        "mean_replication_error", "mae_replication_error", "gross_rmse",
        "residual_rmse", "rmse_reduction", "gross_es_975", "residual_es_975",
        "es_975_reduction", "gross_max_loss", "residual_max_loss",
    ]
    for column in monetary_columns:
        risk_summary[f"{column}_pct_notional"] = (
            100.0 * risk_summary[column] / product.notional
        )
        risk_summary[f"{column}_bps_notional"] = (
            10_000.0 * risk_summary[column] / product.notional
        )
    return {
        "gross_risk": gross_table,
        "residual_risk": residual_table,
        "gross_risk_units": risk_table_in_notional_units(
            gross_table, product.notional, ("condition",)
        ),
        "residual_risk_units": risk_table_in_notional_units(
            residual_table,
            product.notional,
            ("family", "penalty", "profile", "condition"),
        ),
        "comparison": comparison,
        "conditional_comparison": conditional_comparison,
        "condition_summary": pd.DataFrame(condition_rows),
        "risk_summary": risk_summary,
        "profile_losses": profile_losses,
        "likelihood_weights": likelihood_weights,
        "sampling_diagnostics": simulation["diagnostics"],
        "component_summary": simulation["component_summary"],
        "gross_reference_value": gross_reference_value,
        "notional": float(product.notional),
        "n_paths": n_paths,
        "seed": seed,
        "levels": tuple(float(level) for level in levels),
        "tilts": simulation["tilts"],
        "mixture_probabilities": simulation["mixture_probabilities"],
        "sampling_method": "gaussian_mixture_importance_sampling",
        "portfolio_weights_status": "frozen_before_risk_evaluation",
        "calibration_status": "not_recalibrated_with_importance_sampling",
        "target_measure": "risk_neutral_gbm_unchanged_by_likelihood_reweighting",
        "evaluation_status": "independent_sample_not_used_for_alpha_selection",
        "test_status": base_result.get("test_status", "reserved_not_evaluated"),
    }


def compare_standard_and_importance_risk(
    standard_summary: pd.DataFrame,
    importance_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Aligne les estimations standard et IS d'un même portefeuille figé."""
    keys = ["family", "penalty", "profile"]
    metrics = [
        "residual_rmse", "residual_es_95", "residual_es_975",
        "residual_es_99", "under_replication_rate",
    ]
    available = [
        metric
        for metric in metrics
        if metric in standard_summary.columns and metric in importance_summary.columns
    ]
    standard = standard_summary[keys + available].rename(
        columns={metric: f"standard_{metric}" for metric in available}
    )
    importance = importance_summary[keys + available].rename(
        columns={metric: f"importance_{metric}" for metric in available}
    )
    comparison = standard.merge(importance, on=keys, how="outer", validate="one_to_one")
    for metric in available:
        comparison[f"difference_{metric}"] = (
            comparison[f"importance_{metric}"] - comparison[f"standard_{metric}"]
        )
        comparison[f"relative_difference_{metric}"] = np.where(
            comparison[f"standard_{metric}"].abs() > 1e-15,
            comparison[f"difference_{metric}"] / comparison[f"standard_{metric}"].abs(),
            np.nan,
        )
    return comparison
