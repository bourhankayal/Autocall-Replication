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
    empirical_var_es,
    exclusive_autocall_regimes,
    risk_table_in_notional_units,
    tail_concentration_analysis,
    tail_regime_decomposition,
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


def _weight_diagnostics(weights: np.ndarray) -> dict[str, float]:
    """Résume la concentration des poids de vraisemblance."""
    weights = np.asarray(weights, dtype=float).reshape(-1)
    mean = float(np.mean(weights))
    std = float(np.std(weights, ddof=1)) if len(weights) > 1 else 0.0
    normalized = weights / np.sum(weights)
    positive = normalized[normalized > 0.0]
    entropy = -float(np.sum(positive * np.log(positive)))
    maximum_entropy = math.log(len(weights)) if len(weights) > 1 else 0.0
    return {
        "n_paths": int(len(weights)),
        "weight_mean": mean,
        "weight_min": float(np.min(weights)),
        "weight_q50": float(np.quantile(weights, 0.50)),
        "weight_q90": float(np.quantile(weights, 0.90)),
        "weight_q95": float(np.quantile(weights, 0.95)),
        "weight_q99": float(np.quantile(weights, 0.99)),
        "weight_max": float(np.max(weights)),
        "maximum_normalized_weight": float(np.max(normalized)),
        "weight_cv": std / mean if mean > 0.0 else np.inf,
        "effective_sample_size": _effective_sample_size(weights),
        "effective_sample_ratio": _effective_sample_size(weights) / len(weights),
        "normalized_weight_entropy": entropy,
        "normalized_weight_entropy_ratio": (
            entropy / maximum_entropy if maximum_entropy > 0.0 else 1.0
        ),
    }


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
            "diagnostics": _weight_diagnostics(likelihood_weights),
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
        "diagnostics": _weight_diagnostics(likelihood_weights),
    }


def tail_scenario_decomposition(
    losses: np.ndarray,
    likelihood_weights: np.ndarray,
    conditions: dict[str, np.ndarray],
    level: float = 0.975,
) -> pd.DataFrame:
    """Décompose l'ES selon les régimes contractuels observés.

    Les régimes peuvent se chevaucher : ``barrier_hit`` est notamment un
    sous-ensemble possible de ``maturity``. Les parts ne doivent donc pas être
    additionnées entre conditions sans tenir compte de ce chevauchement.
    """
    result = tail_regime_decomposition(
        losses,
        conditions,
        level=level,
        likelihood_weights=likelihood_weights,
    )
    # Alias conservé pour les anciennes sorties du notebook.
    result["share_of_es_tail"] = result["share_of_tail_probability"]
    return result


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
    for level in levels:
        level = float(level)
        tail = empirical_var_es(losses, level, likelihood_weights=weights)
        suffix = str(int(round(level * 1000))).rstrip("0")
        metrics[f"var_{suffix}"] = float(tail["var"])
        metrics[f"es_{suffix}"] = float(tail["es"])
        metrics[f"tail_effective_sample_size_{suffix}"] = float(
            tail["tail_effective_sample_size"]
        )
        metrics[f"tail_probability_{suffix}"] = float(tail["tail_probability"])
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


def build_conditional_policy_sampling_design(
    *,
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int,
    seed: int,
    sampling_method: str = "standard_mc",
    tilts: Sequence[float] = DEFAULT_IMPORTANCE_TILTS,
    mixture_probabilities: Sequence[float] = DEFAULT_IMPORTANCE_MIXTURE,
) -> dict[str, object]:
    """Construit ``A, b`` sur MC standard ou IS avec la même politique.

    Les nœuds, états et instruments sont repris de ``base_result``. La seule
    différence entre les deux expériences est donc la loi de simulation et,
    pour IS, les poids statistiques ``dP/dQ``.
    """
    if sampling_method not in {"standard_mc", "importance_sampling"}:
        raise ValueError("sampling_method doit être standard_mc ou importance_sampling.")
    valuation_date = pd.Timestamp(valuation_date)
    simulation_end = contractual_simulation_end_date(
        product=product,
        contract_start_date=valuation_date,
        requested_maturity_date=pd.Timestamp(maturity_date),
    )
    effective_tilts = (0.0,) if sampling_method == "standard_mc" else tilts
    effective_probabilities = (
        (1.0,) if sampling_method == "standard_mc" else mixture_probabilities
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
        tilts=effective_tilts,
        mixture_probabilities=effective_probabilities,
    )
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
    return {
        **design,
        "dataset": dataset,
        "likelihood_weights": np.asarray(simulation["likelihood_weights"], dtype=float),
        "sampling_diagnostics": simulation["diagnostics"],
        "sampling_diagnostics_table": pd.DataFrame([simulation["diagnostics"]]),
        "component_summary": simulation["component_summary"],
        "sampling_method": sampling_method,
        "tilts": simulation["tilts"],
        "mixture_probabilities": simulation["mixture_probabilities"],
        "seed": int(seed),
        "n_paths": int(n_paths),
        "test_status": "calibration_or_validation_only_final_sample_untouched",
    }


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
    exclusive_regimes = exclusive_autocall_regimes(called, barrier_hit)
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
    tail_decomposition_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_curve_rows: list[pd.DataFrame] = []
    exclusive_regime_rows: list[pd.DataFrame] = []
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
        concentration = tail_concentration_analysis(
            losses,
            levels=levels,
            likelihood_weights=likelihood_weights,
        )
        for table_name in ("summary", "curve"):
            table = concentration[table_name].copy()
            table.insert(0, "profile", profile_name)
            table.insert(0, "penalty", penalty)
            table.insert(0, "family", base_result["family"])
            if table_name == "summary":
                concentration_rows.append(table)
            else:
                concentration_curve_rows.append(table)
        for level in levels:
            decomposition = tail_scenario_decomposition(
                losses,
                likelihood_weights,
                conditions,
                level=float(level),
            )
            decomposition.insert(0, "profile", profile_name)
            decomposition.insert(0, "penalty", penalty)
            decomposition.insert(0, "family", base_result["family"])
            tail_decomposition_rows.append(decomposition)
            exclusive_decomposition = tail_regime_decomposition(
                losses,
                exclusive_regimes,
                level=float(level),
                likelihood_weights=likelihood_weights,
            )
            exclusive_decomposition.insert(0, "profile", profile_name)
            exclusive_decomposition.insert(0, "penalty", penalty)
            exclusive_decomposition.insert(0, "family", base_result["family"])
            exclusive_regime_rows.append(exclusive_decomposition)
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
        "sampling_diagnostics_table": pd.DataFrame([simulation["diagnostics"]]),
        "tail_scenario_decomposition": (
            pd.concat(tail_decomposition_rows, ignore_index=True)
            if tail_decomposition_rows
            else pd.DataFrame()
        ),
        "tail_concentration": pd.concat(concentration_rows, ignore_index=True),
        "tail_concentration_curve": pd.concat(
            concentration_curve_rows, ignore_index=True
        ),
        "exclusive_tail_regime_decomposition": pd.concat(
            exclusive_regime_rows, ignore_index=True
        ),
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


def compare_importance_mixture_candidates(
    *,
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    penalty: str,
    profile: str,
    candidates: Sequence[dict[str, object]],
    seeds: Sequence[int],
    n_paths: int,
    es_level: float = 0.975,
    minimum_effective_sample_ratio: float = 0.20,
) -> dict[str, object]:
    """Compare des mélanges IS sur un échantillon pilote multi-graines.

    Le mélange est classé par précision (dispersion inter-graines de l'ES),
    jamais par niveau d'ES estimé. Choisir la valeur la plus basse créerait un
    biais de sélection. Cette fonction est destinée à la recherche externe au
    notebook principal.
    """
    if len(candidates) == 0 or len(seeds) < 2:
        raise ValueError("Il faut au moins un candidat et deux graines pilotes.")
    suffix = str(int(round(es_level * 1000))).rstrip("0")
    rows: list[dict[str, object]] = []
    for candidate_index, candidate in enumerate(candidates):
        tilts = tuple(float(value) for value in candidate["tilts"])
        probabilities = tuple(
            float(value) for value in candidate["mixture_probabilities"]
        )
        for seed in seeds:
            result = evaluate_conditional_policy_profile_risk_importance(
                base_result=base_result,
                product=product,
                spot0=spot0,
                valuation_date=valuation_date,
                maturity_date=maturity_date,
                rate=rate,
                dividend_yield=dividend_yield,
                vol=vol,
                n_paths=n_paths,
                seed=int(seed),
                levels=(es_level,),
                tilts=tilts,
                mixture_probabilities=probabilities,
            )
            selected = result["residual_risk"]
            selected = selected.loc[
                (selected["penalty"] == penalty)
                & (selected["profile"] == profile)
                & (selected["condition"] == "all")
            ]
            if len(selected) != 1:
                raise ValueError("penalty/profile doit identifier un profil unique.")
            diagnostics = result["sampling_diagnostics"]
            rows.append(
                {
                    "candidate_index": candidate_index,
                    "tilts": repr(tilts),
                    "mixture_probabilities": repr(probabilities),
                    "seed": int(seed),
                    "es": float(selected.iloc[0][f"es_{suffix}"]),
                    "tail_effective_sample_size": float(
                        selected.iloc[0][f"tail_effective_sample_size_{suffix}"]
                    ),
                    "effective_sample_ratio": float(
                        diagnostics["effective_sample_ratio"]
                    ),
                    "weight_cv": float(diagnostics["weight_cv"]),
                    "maximum_normalized_weight": float(
                        diagnostics["maximum_normalized_weight"]
                    ),
                }
            )
    details = pd.DataFrame(rows)
    summary = (
        details.groupby(
            ["candidate_index", "tilts", "mixture_probabilities"], as_index=False
        )
        .agg(
            n_repetitions=("seed", "size"),
            es_mean=("es", "mean"),
            es_std=("es", "std"),
            tail_ess_mean=("tail_effective_sample_size", "mean"),
            effective_sample_ratio_mean=("effective_sample_ratio", "mean"),
            effective_sample_ratio_min=("effective_sample_ratio", "min"),
            weight_cv_mean=("weight_cv", "mean"),
            maximum_normalized_weight_max=("maximum_normalized_weight", "max"),
        )
    )
    summary["passes_weight_diagnostics"] = (
        summary["effective_sample_ratio_min"] >= minimum_effective_sample_ratio
    )
    eligible = summary.loc[summary["passes_weight_diagnostics"]].copy()
    recommended_index = (
        None
        if eligible.empty
        else int(eligible.sort_values(["es_std", "tail_ess_mean"], ascending=[True, False]).iloc[0]["candidate_index"])
    )
    summary["recommended"] = summary["candidate_index"].eq(recommended_index)
    return {
        "summary": summary,
        "details": details,
        "recommended_candidate_index": recommended_index,
        "selection_rule": "minimum_between_seed_es_std_subject_to_ess_ratio",
        "test_status": "pilot_only_final_sample_untouched",
    }


def compare_fixed_policy_importance_mixtures(
    *,
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    policies: Sequence[dict[str, object]],
    candidates: Sequence[dict[str, object]],
    seeds: Sequence[int],
    n_paths: int,
    es_level: float = 0.975,
    minimum_effective_sample_ratio: float = 0.20,
) -> dict[str, object]:
    """Choose one robust IS mixture across *fixed* retained policies.

    Every candidate is evaluated on all policies using the same simulated
    paths for a given seed. A standard-MC pilot supplies a policy-specific
    precision baseline; the selection minimizes the worst IS/MC standard-
    deviation ratio, subject to a global ESS floor. Standard MC remains an
    explicit candidate with ratio one. The selection never minimizes ES.
    """

    if not policies or not candidates or len(seeds) < 2:
        raise ValueError("Il faut des politiques, des mélanges et au moins deux graines.")
    if n_paths < 100 or not 0.0 < minimum_effective_sample_ratio <= 1.0:
        raise ValueError("Volume pilote ou seuil ESS invalide.")
    policy_rows = []
    for policy in policies:
        key = "|".join(str(policy[field]) for field in ("penalty", "objective", "profile"))
        weights = np.asarray(policy["weights"], dtype=float).reshape(-1)
        if not np.all(np.isfinite(weights)) or not len(weights):
            raise ValueError(f"Poids financiers invalides pour {key}.")
        if key in {item["policy_key"] for item in policy_rows}:
            raise ValueError(f"Profil ES dupliqué : {key}.")
        policy_rows.append({
            "policy_key": key, "penalty": str(policy["penalty"]),
            "objective": str(policy["objective"]), "profile": str(policy["profile"]),
            "weights": weights,
        })
    n_instruments = len(policy_rows[0]["weights"])
    if any(len(policy["weights"]) != n_instruments for policy in policy_rows):
        raise ValueError("Les politiques doivent partager la même base d'instruments.")
    weight_matrix = np.column_stack([policy["weights"] for policy in policy_rows])
    observations: list[dict[str, object]] = []
    settings = [(-1, "standard_mc", (0.0,), (1.0,))]
    settings.extend(
        (index, "importance_sampling", tuple(candidate["tilts"]),
         tuple(candidate["mixture_probabilities"]))
        for index, candidate in enumerate(candidates)
    )
    for candidate_index, method, tilts, probabilities in settings:
        for seed in seeds:
            design = build_conditional_policy_sampling_design(
                base_result=base_result, product=product, spot0=spot0,
                valuation_date=valuation_date, maturity_date=maturity_date,
                rate=rate, dividend_yield=dividend_yield, vol=vol,
                n_paths=n_paths, seed=int(seed), sampling_method=method,
                tilts=tilts, mixture_probabilities=probabilities,
            )
            A = np.asarray(design["A"], dtype=float)
            b = np.asarray(design["b"], dtype=float).reshape(-1)
            likelihood = np.asarray(design["likelihood_weights"], dtype=float)
            diagnostics = design["sampling_diagnostics"]
            if A.shape != (len(b), n_instruments):
                raise ValueError("Base d'instruments incompatible avec les politiques ES figées.")
            loss_matrix = b[:, None] - A @ weight_matrix
            for policy_index, policy in enumerate(policy_rows):
                losses = loss_matrix[:, policy_index]
                risk = empirical_var_es(losses, es_level, likelihood)
                observations.append({
                    "candidate_index": candidate_index, "method": method,
                    "tilts": repr(tilts), "mixture_probabilities": repr(probabilities),
                    "seed": int(seed), "policy_key": policy["policy_key"],
                    "penalty": policy["penalty"], "objective": policy["objective"],
                    "profile": policy["profile"], "es": float(risk["es"]),
                    "tail_effective_sample_size": float(risk["tail_effective_sample_size"]),
                    "effective_sample_ratio": float(diagnostics["effective_sample_ratio"]),
                    "maximum_normalized_weight": float(diagnostics["maximum_normalized_weight"]),
                })
    details = pd.DataFrame(observations)
    policy_summary = details.groupby(
        ["candidate_index", "method", "tilts", "mixture_probabilities",
         "policy_key", "penalty", "objective", "profile"], as_index=False,
    ).agg(
        n_repetitions=("seed", "size"), es_mean=("es", "mean"),
        es_std=("es", "std"),
        tail_ess_min=("tail_effective_sample_size", "min"),
        effective_sample_ratio_min=("effective_sample_ratio", "min"),
    )
    standard = policy_summary.loc[
        policy_summary["candidate_index"].eq(-1), ["policy_key", "es_mean", "es_std"]
    ].rename(columns={
        "es_mean": "standard_mc_es_mean", "es_std": "standard_mc_es_std",
    })
    policy_summary = policy_summary.merge(standard, on="policy_key", validate="many_to_one")
    policy_summary["precision_ratio_to_mc"] = (
        policy_summary["es_std"] / policy_summary["standard_mc_es_std"].clip(lower=1e-8)
    )
    policy_summary["es_mean_difference_to_mc"] = (
        policy_summary["es_mean"] - policy_summary["standard_mc_es_mean"]
    )
    candidate_summary = policy_summary.loc[policy_summary["candidate_index"].ge(0)].groupby(
        ["candidate_index", "tilts", "mixture_probabilities"], as_index=False,
    ).agg(
        n_policies=("policy_key", "nunique"),
        worst_precision_ratio_to_mc=("precision_ratio_to_mc", "max"),
        median_precision_ratio_to_mc=("precision_ratio_to_mc", "median"),
        worst_es_std=("es_std", "max"),
        tail_ess_min=("tail_ess_min", "min"),
        effective_sample_ratio_min=("effective_sample_ratio_min", "min"),
    )
    candidate_summary["passes_weight_diagnostics"] = (
        candidate_summary["effective_sample_ratio_min"] >= minimum_effective_sample_ratio
    ) & np.isfinite(candidate_summary["worst_precision_ratio_to_mc"])
    baseline = policy_summary.loc[policy_summary["candidate_index"].eq(-1)]
    baseline_row = pd.DataFrame([{
        "candidate_index": -1,
        "tilts": repr((0.0,)), "mixture_probabilities": repr((1.0,)),
        "n_policies": int(baseline["policy_key"].nunique()),
        "worst_precision_ratio_to_mc": 1.0,
        "median_precision_ratio_to_mc": 1.0,
        "worst_es_std": float(baseline["es_std"].max()),
        "tail_ess_min": float(baseline["tail_ess_min"].min()),
        "effective_sample_ratio_min": 1.0,
        "passes_weight_diagnostics": True,
    }])
    candidate_summary = pd.concat([baseline_row, candidate_summary], ignore_index=True)
    eligible = candidate_summary.loc[candidate_summary["passes_weight_diagnostics"]]
    recommended_index = int(eligible.sort_values(
        ["worst_precision_ratio_to_mc", "tail_ess_min", "candidate_index"],
        ascending=[True, False, True],
    ).iloc[0]["candidate_index"])
    candidate_summary["recommended"] = candidate_summary["candidate_index"].eq(recommended_index)
    policy_summary["recommended"] = policy_summary["candidate_index"].eq(recommended_index)
    return {
        "summary": candidate_summary, "policy_summary": policy_summary,
        "details": details, "recommended_candidate_index": recommended_index,
        "selection_rule": "minimum_worst_policy_es_std_ratio_including_standard_mc_subject_to_ess_ratio",
        "test_status": "pilot_only_final_sample_untouched",
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
