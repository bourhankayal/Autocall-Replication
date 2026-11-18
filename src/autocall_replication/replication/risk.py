"""Mesure du risque terminal des profils de réplication statique."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from ..products import AutocallProduct


DEFAULT_RISK_LEVELS = (0.95, 0.975, 0.99)
BASE_MONETARY_RISK_METRICS = ("mean_loss", "mae", "loss_std", "rmse", "max_loss")


def _level_suffix(level: float) -> str:
    return str(int(round(level * 1000))).rstrip("0")


def empirical_var_es(
    losses: np.ndarray,
    level: float,
    likelihood_weights: np.ndarray | None = None,
) -> dict[str, object]:
    """Calcule une VaR et un ES empiriques avec exactement ``1-level`` de masse.

    La formule de Rockafellar--Uryasev

    ``ES_q = VaR_q + E[(L - VaR_q)+] / (1 - q)``

    évite le biais de la moyenne naïve ``L >= VaR`` lorsque la distribution
    empirique possède un atome à la VaR. C'est fréquent pour un autocall, dont
    plusieurs trajectoires peuvent produire exactement le même cashflow.
    Les poids sont auto-normalisés ; avec des poids unitaires, cette fonction
    redonne l'estimateur empirique standard.
    """
    losses = np.asarray(losses, dtype=float).reshape(-1)
    if likelihood_weights is None:
        weights = np.ones(len(losses), dtype=float)
    else:
        weights = np.asarray(likelihood_weights, dtype=float).reshape(-1)
        if losses.shape != weights.shape:
            raise ValueError("losses et likelihood_weights doivent avoir la même taille.")
    if not 0.5 < float(level) < 1.0:
        raise ValueError("level doit appartenir à ]0.5, 1[.")
    valid = np.isfinite(losses) & np.isfinite(weights) & (weights >= 0.0)
    losses, weights = losses[valid], weights[valid]
    total_weight = float(np.sum(weights))
    if len(losses) == 0 or total_weight <= 0.0:
        raise ValueError("Les pertes pondérées ne contiennent aucune observation valide.")

    normalized = weights / total_weight
    order = np.argsort(losses, kind="stable")
    sorted_losses = losses[order]
    sorted_weights = normalized[order]
    cumulative = np.cumsum(sorted_weights)
    quantile_index = min(
        int(np.searchsorted(cumulative, float(level), side="left")),
        len(sorted_losses) - 1,
    )
    value_at_risk = float(sorted_losses[quantile_index])
    tail_probability = 1.0 - float(level)
    excess = np.maximum(losses - value_at_risk, 0.0)
    expected_shortfall = value_at_risk + float(np.sum(normalized * excess)) / tail_probability

    # Pour l'ESS de queue, on attribue seulement la fraction de masse à la VaR
    # nécessaire pour compléter exactement la queue de probabilité 1-q.
    strict_mask = losses > value_at_risk
    equal_mask = losses == value_at_risk
    tail_contributions = np.zeros_like(normalized)
    tail_contributions[strict_mask] = normalized[strict_mask]
    strict_mass = float(np.sum(tail_contributions))
    required_at_var = float(np.clip(tail_probability - strict_mass, 0.0, tail_probability))
    equal_mass = float(np.sum(normalized[equal_mask]))
    if required_at_var > 0.0 and equal_mass > 0.0:
        tail_contributions[equal_mask] = (
            normalized[equal_mask] * required_at_var / equal_mass
        )
    contribution_sum = float(np.sum(tail_contributions))
    tail_ess = (
        contribution_sum**2 / float(np.sum(tail_contributions**2))
        if contribution_sum > 0.0
        else 0.0
    )
    return {
        "var": value_at_risk,
        "es": expected_shortfall,
        "tail_probability": tail_probability,
        "tail_effective_sample_size": tail_ess,
        "normalized_weights": normalized,
        "tail_probability_contributions": tail_contributions,
    }


def exclusive_autocall_regimes(
    called: np.ndarray,
    barrier_hit: np.ndarray,
) -> dict[str, np.ndarray]:
    """Construit trois régimes terminaux exclusifs couvrant toutes les trajectoires."""
    called = np.asarray(called, dtype=bool).reshape(-1)
    barrier_hit = np.asarray(barrier_hit, dtype=bool).reshape(-1)
    if called.shape != barrier_hit.shape:
        raise ValueError("called et barrier_hit doivent avoir la même taille.")
    return {
        "recalled": called,
        "maturity_protected": (~called) & (~barrier_hit),
        "maturity_barrier_hit": (~called) & barrier_hit,
    }


def tail_regime_decomposition(
    losses: np.ndarray,
    conditions: dict[str, np.ndarray],
    level: float = 0.975,
    likelihood_weights: np.ndarray | None = None,
) -> pd.DataFrame:
    """Décompose exactement la masse et l'ES entre régimes exclusifs ou non.

    Si les masques sont exclusifs et couvrent l'échantillon, les parts de masse
    de queue et les contributions à l'ES totalisent 100 % et l'ES global.
    """
    losses = np.asarray(losses, dtype=float).reshape(-1)
    risk = empirical_var_es(losses, level, likelihood_weights)
    normalized = np.asarray(risk["normalized_weights"], dtype=float)
    tail_contributions = np.asarray(
        risk["tail_probability_contributions"], dtype=float
    )
    tail_probability = float(risk["tail_probability"])
    expected_shortfall = float(risk["es"])
    rows: list[dict[str, object]] = []
    for condition, raw_mask in conditions.items():
        mask = np.asarray(raw_mask, dtype=bool).reshape(-1)
        if mask.shape != losses.shape:
            raise ValueError("Chaque condition doit contenir un booléen par trajectoire.")
        tail_mass = float(np.sum(tail_contributions[mask]))
        es_contribution = (
            float(np.sum(tail_contributions[mask] * losses[mask]))
            / tail_probability
        )
        rows.append(
            {
                "condition": condition,
                "level": float(level),
                "condition_probability": float(np.sum(normalized[mask])),
                "tail_probability_mass": tail_mass,
                "share_of_tail_probability": tail_mass / tail_probability,
                "contribution_to_es": es_contribution,
                "share_of_es": (
                    es_contribution / expected_shortfall
                    if abs(expected_shortfall) > 1e-14
                    else np.nan
                ),
                "n_paths": int(np.sum(mask)),
            }
        )
    return pd.DataFrame(rows)


def tail_concentration_analysis(
    losses: np.ndarray,
    levels: Sequence[float] = DEFAULT_RISK_LEVELS,
    likelihood_weights: np.ndarray | None = None,
    curve_fractions: Sequence[float] = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 1.0),
) -> dict[str, pd.DataFrame]:
    """Mesure la profondeur et la concentration de la queue de pertes.

    Les parts ``top_*`` indiquent quelle fraction de la perte positive contenue
    dans l'ES est expliquée par la fraction la plus défavorable de la masse de
    queue, et non par une fraction brute du nombre de simulations. Cette
    définition reste comparable entre Monte-Carlo standard et importance
    sampling.
    """
    losses = np.asarray(losses, dtype=float).reshape(-1)
    if likelihood_weights is None:
        weights = np.ones(len(losses), dtype=float)
    else:
        weights = np.asarray(likelihood_weights, dtype=float).reshape(-1)
        if weights.shape != losses.shape:
            raise ValueError("losses et likelihood_weights doivent avoir la même taille.")
    fractions = np.asarray(tuple(float(value) for value in curve_fractions))
    if len(fractions) == 0 or np.any((fractions <= 0.0) | (fractions > 1.0)):
        raise ValueError("curve_fractions doit contenir des fractions dans ]0, 1].")

    summary_rows: list[dict[str, float]] = []
    curve_rows: list[dict[str, float]] = []
    for level in levels:
        risk = empirical_var_es(losses, float(level), weights)
        tail_mass = np.asarray(risk["tail_probability_contributions"], dtype=float)
        adverse_contributions = tail_mass * np.maximum(losses, 0.0)
        positive_total = float(np.sum(adverse_contributions))
        order = np.argsort(losses, kind="stable")[::-1]
        ordered_mass = tail_mass[order]
        ordered_contributions = adverse_contributions[order]
        probability = float(risk["tail_probability"])

        shares: dict[float, float] = {}
        for fraction in fractions:
            target_mass = fraction * probability
            consumed_mass = 0.0
            captured_contribution = 0.0
            for observation_mass, contribution in zip(
                ordered_mass, ordered_contributions, strict=True
            ):
                if observation_mass <= 0.0 or consumed_mass >= target_mass:
                    continue
                used_mass = min(float(observation_mass), target_mass - consumed_mass)
                captured_contribution += float(contribution) * used_mass / observation_mass
                consumed_mass += used_mass
            share = (
                captured_contribution / positive_total
                if positive_total > 0.0
                else np.nan
            )
            shares[float(fraction)] = share
            curve_rows.append(
                {
                    "level": float(level),
                    "tail_mass_fraction": float(fraction),
                    "positive_tail_loss_share": share,
                }
            )

        normalized_contributions = (
            adverse_contributions / positive_total
            if positive_total > 0.0
            else np.zeros_like(adverse_contributions)
        )
        hhi = float(np.sum(normalized_contributions**2))
        summary_rows.append(
            {
                "level": float(level),
                "var": float(risk["var"]),
                "es": float(risk["es"]),
                "tail_effective_sample_size": float(
                    risk["tail_effective_sample_size"]
                ),
                "positive_tail_loss_hhi": hhi,
                "effective_positive_tail_contributors": 1.0 / hhi if hhi > 0.0 else 0.0,
                "top_1pct_tail_mass_share": shares.get(0.01, np.nan),
                "top_5pct_tail_mass_share": shares.get(0.05, np.nan),
                "top_10pct_tail_mass_share": shares.get(0.10, np.nan),
            }
        )
    summary = pd.DataFrame(summary_rows)
    es_by_level = summary.set_index("level")["es"]
    steepness = (
        float(es_by_level.loc[0.99] / es_by_level.loc[0.975])
        if 0.99 in es_by_level.index
        and 0.975 in es_by_level.index
        and abs(float(es_by_level.loc[0.975])) > 1e-14
        else np.nan
    )
    summary["es_99_to_es_975_ratio"] = steepness
    return {"summary": summary, "curve": pd.DataFrame(curve_rows)}


def tail_risk_metrics(
    losses: np.ndarray,
    levels: Sequence[float] = DEFAULT_RISK_LEVELS,
) -> dict[str, float]:
    """Calcule RMSE, VaR et Expected Shortfall sur des pertes signées."""
    losses = np.asarray(losses, dtype=float).reshape(-1)
    losses = losses[np.isfinite(losses)]
    if len(losses) == 0:
        raise ValueError("Le vecteur de pertes ne contient aucune valeur finie.")
    metrics = {
        "n_observations": float(len(losses)),
        "mean_loss": float(np.mean(losses)),
        "mae": float(np.mean(np.abs(losses))),
        "loss_std": float(np.std(losses, ddof=1)) if len(losses) > 1 else 0.0,
        "rmse": float(np.sqrt(np.mean(losses**2))),
        "max_loss": float(np.max(losses)),
        "under_replication_rate": float(np.mean(losses > 0.0)),
    }
    for level in levels:
        if not 0.5 < float(level) < 1.0:
            raise ValueError("Chaque niveau de risque doit appartenir à ]0.5, 1[.")
        tail = empirical_var_es(losses, float(level))
        suffix = _level_suffix(float(level))
        metrics[f"var_{suffix}"] = float(tail["var"])
        metrics[f"es_{suffix}"] = float(tail["es"])
        metrics[f"tail_effective_sample_size_{suffix}"] = float(
            tail["tail_effective_sample_size"]
        )
        metrics[f"tail_probability_{suffix}"] = float(tail["tail_probability"])
    return metrics


def risk_table_in_notional_units(
    table: pd.DataFrame,
    notional: float,
    identifier_columns: Sequence[str],
) -> pd.DataFrame:
    """Convertit une table de risque en montant, % et bps du nominal.

    La sortie est volontairement longue : une ligne représente une métrique
    d'un profil et d'un régime. Les fréquences et nombres d'observations ne sont
    pas convertis en unités monétaires.
    """
    if notional <= 0.0:
        raise ValueError("notional doit être strictement positif.")
    missing = set(identifier_columns) - set(table.columns)
    if missing:
        raise ValueError(f"Colonnes d'identification manquantes : {sorted(missing)}")
    metric_columns = [
        column
        for column in table.columns
        if column in BASE_MONETARY_RISK_METRICS
        or column.startswith("var_")
        or column.startswith("es_")
    ]
    rows: list[dict[str, object]] = []
    for _, source_row in table.iterrows():
        identifiers = {column: source_row[column] for column in identifier_columns}
        for metric in metric_columns:
            amount = float(source_row[metric])
            rows.append(
                {
                    **identifiers,
                    "metric": metric,
                    "amount": amount,
                    "pct_notional": 100.0 * amount / notional,
                    "bps_notional": 10_000.0 * amount / notional,
                }
            )
    return pd.DataFrame(rows)


def _risk_comparison_row(
    residual_row: pd.Series,
    gross_row: pd.Series,
    levels: Sequence[float],
) -> dict[str, object]:
    comparison: dict[str, object] = {
        "penalty": residual_row["penalty"],
        "profile": residual_row["profile"],
        "condition": residual_row["condition"],
        "n_observations": float(residual_row["n_observations"]),
        "condition_frequency": float(residual_row["condition_frequency"]),
        "quantile_reliability": residual_row["quantile_reliability"],
        "mean_replication_error": float(residual_row["mean_loss"]),
        "mae_replication_error": float(residual_row["mae"]),
        "under_replication_rate": float(residual_row["under_replication_rate"]),
    }
    compared_metrics = ["rmse", "max_loss"]
    for level in levels:
        suffix = _level_suffix(float(level))
        compared_metrics.extend((f"var_{suffix}", f"es_{suffix}"))
    for metric in compared_metrics:
        gross_value = float(gross_row[metric])
        residual_value = float(residual_row[metric])
        absolute_reduction = gross_value - residual_value
        relative_is_valid = bool(np.isfinite(gross_value) and gross_value > 0.0)
        comparison[f"gross_{metric}"] = gross_value
        comparison[f"residual_{metric}"] = residual_value
        comparison[f"{metric}_reduction"] = absolute_reduction
        comparison[f"{metric}_relative_reduction"] = (
            absolute_reduction / gross_value if relative_is_valid else np.nan
        )
        comparison[f"{metric}_relative_reduction_is_valid"] = relative_is_valid
    return comparison


def evaluate_pathwise_profile_risk(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int = 20_000,
    seed: int = 10500,
    levels: Sequence[float] = DEFAULT_RISK_LEVELS,
    min_condition_observations: int = 200,
) -> dict[str, object]:
    """Évalue le risque brut et résiduel sur un échantillon indépendant.

    L'échantillon n'est jamais utilisé pour recalibrer les poids ou choisir un
    alpha. Le risque brut est la variation de la dette autocall autour de son
    espérance Monte-Carlo. Le risque résiduel est ``autocall - réplication``.
    """
    from .pathwise_payoff import build_pathwise_payoff_dataset

    if n_paths < 100:
        raise ValueError("L'analyse de risque requiert au moins 100 trajectoires.")
    if min_condition_observations < 1:
        raise ValueError("min_condition_observations doit être strictement positif.")
    profiles = pd.DataFrame(base_result["profiles"]).copy()
    if profiles.empty:
        raise ValueError("Aucun profil n'est disponible pour l'analyse de risque.")
    X, y, states = build_pathwise_payoff_dataset(
        product=product,
        vanillas=list(base_result["vanillas"]),
        spot0=spot0,
        valuation_date=valuation_date,
        maturity_date=maturity_date,
        rate=rate,
        dividend_yield=dividend_yield,
        vol=vol,
        n_paths=n_paths,
        seed=seed,
        return_metadata=True,
    )
    gross_reference_value = float(np.mean(y))
    gross_losses = y - gross_reference_value
    conditions = {
        "all": np.ones(n_paths, dtype=bool),
        "recalled": states["called"].to_numpy(dtype=bool),
        "maturity": ~states["called"].to_numpy(dtype=bool),
        "barrier_hit": states["barrier_hit"].to_numpy(dtype=bool),
    }

    condition_rows: list[dict[str, object]] = []
    gross_rows: list[dict[str, object]] = []
    for condition, mask in conditions.items():
        if not np.any(mask):
            continue
        condition_count = int(np.sum(mask))
        condition_frequency = condition_count / n_paths
        quantile_reliability = (
            "sufficient"
            if condition_count >= min_condition_observations
            else "warning_low_observation_count"
        )
        condition_rows.append(
            {
                "condition": condition,
                "n_observations": condition_count,
                "condition_frequency": condition_frequency,
                "quantile_reliability": quantile_reliability,
            }
        )
        gross_rows.append(
            {
                "condition": condition,
                "condition_frequency": condition_frequency,
                "quantile_reliability": quantile_reliability,
                **tail_risk_metrics(gross_losses[mask], levels=levels),
            }
        )

    residual_rows: list[dict[str, object]] = []
    profile_losses: dict[tuple[str, str], np.ndarray] = {}
    for _, profile in profiles.iterrows():
        penalty = str(profile["penalty"])
        profile_name = str(profile["profile"])
        solution = base_result["results"][penalty]["solutions"][
            int(profile["solution_index"])
        ]
        weights = np.asarray(solution["weights"], dtype=float)
        residual_losses = y - X @ weights
        profile_losses[(penalty, profile_name)] = residual_losses
        for condition, mask in conditions.items():
            if not np.any(mask):
                continue
            condition_count = int(np.sum(mask))
            residual_rows.append(
                {
                    "penalty": penalty,
                    "profile": profile_name,
                    "condition": condition,
                    "condition_frequency": condition_count / n_paths,
                    "quantile_reliability": (
                        "sufficient"
                        if condition_count >= min_condition_observations
                        else "warning_low_observation_count"
                    ),
                    **tail_risk_metrics(residual_losses[mask], levels=levels),
                }
            )

    gross_table = pd.DataFrame(gross_rows)
    residual_table = pd.DataFrame(residual_rows)
    comparison_rows: list[dict[str, object]] = []
    gross_by_condition = gross_table.set_index("condition")
    for _, row in residual_table.iterrows():
        comparison_rows.append(
            _risk_comparison_row(
                residual_row=row,
                gross_row=gross_by_condition.loc[row["condition"]],
                levels=levels,
            )
        )
    conditional_comparison = pd.DataFrame(comparison_rows)
    comparison = conditional_comparison.loc[
        conditional_comparison["condition"] == "all"
    ].reset_index(drop=True)

    gross_risk_units = risk_table_in_notional_units(
        gross_table,
        product.notional,
        identifier_columns=("condition",),
    )
    residual_risk_units = risk_table_in_notional_units(
        residual_table,
        product.notional,
        identifier_columns=("penalty", "profile", "condition"),
    )
    risk_summary_columns = [
        "penalty",
        "profile",
        "mean_replication_error",
        "mae_replication_error",
        "under_replication_rate",
        "gross_rmse",
        "residual_rmse",
        "rmse_reduction",
        "rmse_relative_reduction",
        "gross_es_975",
        "residual_es_975",
        "es_975_reduction",
        "es_975_relative_reduction",
        "gross_max_loss",
        "residual_max_loss",
    ]
    risk_summary = comparison.loc[:, risk_summary_columns].copy()
    for column in (
        "mean_replication_error",
        "mae_replication_error",
        "gross_rmse",
        "residual_rmse",
        "rmse_reduction",
        "gross_es_975",
        "residual_es_975",
        "es_975_reduction",
        "gross_max_loss",
        "residual_max_loss",
    ):
        risk_summary[f"{column}_pct_notional"] = (
            100.0 * risk_summary[column] / product.notional
        )
        risk_summary[f"{column}_bps_notional"] = (
            10_000.0 * risk_summary[column] / product.notional
        )

    return {
        "gross_risk": gross_table,
        "residual_risk": residual_table,
        "gross_risk_units": gross_risk_units,
        "residual_risk_units": residual_risk_units,
        "comparison": comparison,
        "conditional_comparison": conditional_comparison,
        "condition_summary": pd.DataFrame(condition_rows),
        "risk_summary": risk_summary,
        "profile_losses": profile_losses,
        "states": states,
        "gross_reference_value": gross_reference_value,
        "notional": float(product.notional),
        "n_paths": n_paths,
        "seed": seed,
        "levels": tuple(float(level) for level in levels),
        "min_condition_observations": min_condition_observations,
        "value_convention": "discounted_to_valuation_date",
        "loss_convention": "issuer_shortfall_positive_autocall_minus_replication",
        "analysis_level": "level_2_static_replication_residual_before_dynamic_hedging",
        "dynamic_hedging_status": "level_3_not_implemented",
        "evaluation_status": "independent_sample_not_used_for_alpha_selection",
        "test_status": base_result.get("test_status", "reserved_not_evaluated"),
    }


def evaluate_conditional_policy_profile_risk(
    base_result: dict[str, object],
    product: AutocallProduct,
    spot0: float,
    valuation_date: str | pd.Timestamp,
    maturity_date: str | pd.Timestamp,
    rate: float,
    dividend_yield: float,
    vol: float,
    n_paths: int = 20_000,
    seed: int = 10500,
    levels: Sequence[float] = DEFAULT_RISK_LEVELS,
    min_condition_observations: int = 200,
) -> dict[str, object]:
    """Mesure le risque terminal d'une politique conditionnelle figée.

    Les trajectoires sont indépendantes de la calibration et de la sélection
    d'alpha. La topologie date/état, les replis et les poids restent figés.
    """
    from .conditional_policy import build_external_policy_design

    if n_paths < 100:
        raise ValueError("L'analyse de risque requiert au moins 100 trajectoires.")
    profiles = pd.DataFrame(base_result["profiles"]).copy()
    if profiles.empty:
        raise ValueError("Aucun profil n'est disponible pour l'analyse de risque.")
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
    path_results = [
        product.compute_autocall_payoff(
            item["path"], start_date=pd.Timestamp(valuation_date)
        )
        for item in design["dataset"]
    ]
    called = np.asarray([item["call_date"] is not None for item in path_results])
    barrier_hit = np.asarray(
        [bool(item["barrier_hit"][-1]) for item in design["dataset"]]
    )
    conditions = {
        "all": np.ones(n_paths, dtype=bool),
        "recalled": called,
        "maturity": ~called,
        "barrier_hit": barrier_hit,
    }
    exclusive_regimes = exclusive_autocall_regimes(called, barrier_hit)
    missed_coupons = np.asarray([
        result["coupon_observations"].count(False) for result in path_results
    ])
    observed_coupons = np.asarray([
        len(result["coupon_observations"]) for result in path_results
    ])
    # Keep the full joint partition for later aggregation by any event.
    contract_events = pd.DataFrame({
        "recalled": called,
        "protection_barrier_hit": [result["barrier_hit"] for result in path_results],
        "coupon_opportunities": observed_coupons,
        "coupons_missed": missed_coupons,
        "coupon_pattern": [
            "".join("P" if paid else "M" for paid in result["coupon_observations"])
            for result in path_results
        ],
    })
    event_groups = contract_events.groupby(list(contract_events.columns)).indices
    event_masks = {}
    event_labels = []
    for group, indices in event_groups.items():
        mask = np.zeros(n_paths, dtype=bool)
        mask[indices] = True
        event_id = str(len(event_labels))
        event_masks[event_id] = mask
        event_labels.append({"condition": event_id, **dict(zip(contract_events.columns, group))})
    event_labels = pd.DataFrame(event_labels)
    contract_event_rows = []
    contract_group_rows = []
    contract_path_rows = []
    date_contribution_rows = []
    feature_dates = pd.to_datetime(design["feature_table"]["payment_date"]).to_numpy()
    payment_dates = pd.to_datetime(design["dataset"][0]["dates"])
    targets_by_date = np.asarray([item["y_curve"] for item in design["dataset"]])
    gross_reference_value = float(np.mean(y))
    gross_losses = y - gross_reference_value
    gross_rows: list[dict[str, object]] = []
    condition_rows: list[dict[str, object]] = []
    for condition, mask in conditions.items():
        if not np.any(mask):
            continue
        count = int(mask.sum())
        reliability = (
            "sufficient"
            if count >= min_condition_observations
            else "warning_low_observation_count"
        )
        condition_rows.append(
            {
                "condition": condition,
                "n_observations": count,
                "condition_frequency": count / n_paths,
                "quantile_reliability": reliability,
            }
        )
        gross_rows.append(
            {
                "condition": condition,
                "condition_frequency": count / n_paths,
                "quantile_reliability": reliability,
                **tail_risk_metrics(gross_losses[mask], levels=levels),
            }
        )

    residual_rows: list[dict[str, object]] = []
    profile_losses: dict[tuple[str, str], np.ndarray] = {}
    concentration_rows: list[pd.DataFrame] = []
    concentration_curve_rows: list[pd.DataFrame] = []
    exclusive_regime_rows: list[pd.DataFrame] = []
    losses_by_solution: dict[tuple[str, int], np.ndarray] = {}
    for _, profile in profiles.iterrows():
        penalty, profile_name = str(profile["penalty"]), str(profile["profile"])
        solution_index = int(profile["solution_index"])
        key = (penalty, solution_index)
        if key not in losses_by_solution:
            weights = np.asarray(
                base_result["results"][penalty]["solutions"][solution_index]["weights"],
                dtype=float,
            )
            losses_by_solution[key] = y - A @ weights
        losses = losses_by_solution[key]
        profile_losses[(penalty, profile_name)] = losses
        weights = np.asarray(
            base_result["results"][penalty]["solutions"][solution_index]["weights"],
            dtype=float,
        )
        tail = empirical_var_es(losses, 0.975)
        tail_mass = np.asarray(tail["tail_probability_contributions"], dtype=float)
        date_losses = []
        for date_index, date in enumerate(payment_dates):
            columns = feature_dates == date.to_datetime64()
            residual = targets_by_date[:, date_index] - A[:, columns] @ weights[columns]
            date_losses.append(residual)
            contribution = float(tail_mass @ residual / 0.025)
            date_contribution_rows.append({
                "family": base_result["family"], "penalty": penalty, "profile": profile_name,
                "payment_date": date, "contribution_to_global_es": contribution,
                "share_of_global_es": contribution / tail["es"] if abs(tail["es"]) > 1e-14 else np.nan,
                "global_es": tail["es"],
            })
        if not np.allclose(np.sum(date_losses, axis=0), losses):
            raise ValueError("Date residuals must reconstruct the total residual.")
        contract_path_rows.append(contract_events.assign(
            path_index=np.arange(n_paths), loss=losses,
            family=base_result["family"], penalty=penalty, profile=profile_name,
        ))
        # A complete cube retains absent categories and avoids summing conditional ES.
        for recalled in (False, True):
            for breached in (False, True):
                for missed in (False, True):
                    mask = (
                        contract_events["recalled"].eq(recalled).to_numpy()
                        & contract_events["protection_barrier_hit"].eq(breached).to_numpy()
                        & (missed_coupons > 0 if missed else missed_coupons == 0)
                    )
                    count = int(mask.sum())
                    decomposition = tail_regime_decomposition(
                        losses, {"group": mask}, level=0.975,
                    ).iloc[0].to_dict()
                    metrics = tail_risk_metrics(losses[mask], levels=(0.975,)) if count else {}
                    contract_group_rows.append({
                        "family": base_result["family"], "penalty": penalty,
                        "profile": profile_name, "recalled": recalled,
                        "protection_barrier_hit": breached, "missed_coupon": missed,
                        "n_paths": count, "sample_frequency": count / n_paths,
                        "conditional_rmse": float(np.sqrt(np.mean(losses[mask] ** 2))) if count else np.nan,
                        "conditional_es_975": metrics.get("es_975", np.nan),
                        "conditional_mean_loss": float(np.mean(losses[mask])) if count else np.nan,
                        "conditional_positive_loss_frequency": float(np.mean(losses[mask] > 0)) if count else np.nan,
                        "conditional_max_loss": float(np.max(losses[mask])) if count else np.nan,
                        "conditional_tail_path_equivalents": 0.025 * count,
                        "global_tail_probability_share": decomposition["share_of_tail_probability"],
                        "global_es_contribution": decomposition["contribution_to_es"],
                        "global_es_share": decomposition["share_of_es"],
                    })
        events = tail_regime_decomposition(losses, event_masks, level=0.975)
        events = events.merge(event_labels, on="condition", validate="one_to_one")
        contract_event_rows.append(events.drop(columns="condition").assign(
            family=base_result["family"], penalty=penalty, profile=profile_name,
        ))
        concentration = tail_concentration_analysis(losses, levels=levels)
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
            decomposition = tail_regime_decomposition(
                losses,
                exclusive_regimes,
                level=float(level),
            )
            decomposition.insert(0, "profile", profile_name)
            decomposition.insert(0, "penalty", penalty)
            decomposition.insert(0, "family", base_result["family"])
            exclusive_regime_rows.append(decomposition)
        for condition, mask in conditions.items():
            if not np.any(mask):
                continue
            count = int(mask.sum())
            residual_rows.append(
                {
                    "family": base_result["family"],
                    "penalty": penalty,
                    "profile": profile_name,
                    "condition": condition,
                    "condition_frequency": count / n_paths,
                    "quantile_reliability": (
                        "sufficient"
                        if count >= min_condition_observations
                        else "warning_low_observation_count"
                    ),
                    **tail_risk_metrics(losses[mask], levels=levels),
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
        "tail_concentration": pd.concat(concentration_rows, ignore_index=True),
        "tail_concentration_curve": pd.concat(
            concentration_curve_rows, ignore_index=True
        ),
        "exclusive_tail_regime_decomposition": pd.concat(
            exclusive_regime_rows, ignore_index=True
        ),
        "tail_contract_event_decomposition": pd.concat(contract_event_rows, ignore_index=True),
        "tail_contract_group_diagnostics": pd.DataFrame(contract_group_rows),
        "tail_payment_date_contributions": pd.DataFrame(date_contribution_rows),
        "tail_contract_path_diagnostics": pd.concat(contract_path_rows, ignore_index=True),
        "gross_reference_value": gross_reference_value,
        "notional": float(product.notional),
        "n_paths": n_paths,
        "seed": seed,
        "levels": tuple(float(level) for level in levels),
        "value_convention": "discounted_to_valuation_date",
        "loss_convention": "issuer_shortfall_positive_autocall_minus_replication",
        "analysis_level": "level_2_conditional_replication_residual_before_dynamic_hedging",
        "chronology": base_result["chronology"],
        "dynamic_hedging_status": "level_3_not_implemented",
        "evaluation_status": "independent_sample_not_used_for_alpha_selection",
        "test_status": base_result.get("test_status", "reserved_not_evaluated"),
    }


def compare_transaction_cost_to_risk_reduction(
    risk_comparison: pd.DataFrame,
    cost_summary: pd.DataFrame,
    autocall_notional: float,
    risk_metric: str = "es_975_reduction",
) -> pd.DataFrame:
    """Applique le filtre économique coût inférieur au risque réduit."""
    if autocall_notional <= 0.0:
        raise ValueError("autocall_notional doit être strictement positif.")
    if risk_metric not in risk_comparison:
        raise ValueError(f"Métrique de réduction inconnue : {risk_metric}")
    required_cost_columns = {
        "penalty",
        "profile",
        "cost_scenario",
        "transaction_cost",
        "cost_complete",
    }
    missing = required_cost_columns - set(cost_summary.columns)
    if missing:
        raise ValueError(f"Colonnes de coût manquantes : {sorted(missing)}")
    merge_keys = ["penalty", "profile"]
    if "family" in cost_summary and "family" in risk_comparison:
        merge_keys.insert(0, "family")
    merged = cost_summary.merge(
        risk_comparison,
        on=merge_keys,
        how="left",
        validate="many_to_one",
    )
    merged["risk_reduction"] = merged[risk_metric]
    merged["transaction_cost_bps"] = (
        10_000.0 * merged["transaction_cost"] / autocall_notional
    )
    merged["transaction_cost_pct_notional"] = (
        100.0 * merged["transaction_cost"] / autocall_notional
    )
    merged["risk_reduction_bps"] = (
        10_000.0 * merged["risk_reduction"] / autocall_notional
    )
    merged["risk_reduction_pct_notional"] = (
        100.0 * merged["risk_reduction"] / autocall_notional
    )
    merged["net_risk_reduction"] = (
        merged["risk_reduction"] - merged["transaction_cost"]
    )
    merged["net_risk_reduction_bps"] = (
        10_000.0 * merged["net_risk_reduction"] / autocall_notional
    )
    merged["net_risk_reduction_pct_notional"] = (
        100.0 * merged["net_risk_reduction"] / autocall_notional
    )
    merged["cost_to_risk_reduction_ratio"] = np.where(
        merged["risk_reduction"] > 0.0,
        merged["transaction_cost"] / merged["risk_reduction"],
        np.nan,
    )
    merged["passes_cost_risk_filter"] = (
        merged["cost_complete"]
        & (merged["risk_reduction"] > 0.0)
        & (merged["transaction_cost"] <= merged["risk_reduction"])
        & (merged["residual_max_loss"] <= merged["gross_max_loss"])
    )
    merged["filter_reason"] = np.select(
        [
            ~merged["cost_complete"],
            merged["risk_reduction"] <= 0.0,
            merged["transaction_cost"] > merged["risk_reduction"],
            merged["residual_max_loss"] > merged["gross_max_loss"],
        ],
        [
            "rejected_incomplete_cost",
            "rejected_no_positive_risk_reduction",
            "rejected_cost_exceeds_risk_reduction",
            "rejected_worse_max_loss",
        ],
        default="accepted_cost_below_risk_reduction",
    )
    return merged
