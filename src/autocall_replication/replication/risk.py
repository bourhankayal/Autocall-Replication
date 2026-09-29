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
        value_at_risk = float(np.quantile(losses, level))
        tail = losses[losses >= value_at_risk]
        suffix = _level_suffix(float(level))
        metrics[f"var_{suffix}"] = value_at_risk
        metrics[f"es_{suffix}"] = float(np.mean(tail))
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
    for _, profile in profiles.iterrows():
        penalty, profile_name = str(profile["penalty"]), str(profile["profile"])
        weights = np.asarray(
            base_result["results"][penalty]["solutions"][
                int(profile["solution_index"])
            ]["weights"],
            dtype=float,
        )
        losses = y - A @ weights
        profile_losses[(penalty, profile_name)] = losses
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
