"""Compact, exportable research tables; full audit tables remain untouched.

These views are descriptive only. They never select a policy, change a weight,
or read a reserved test set. Values retain their original units unless the
column name explicitly says ``pct_notional`` or ``bps_notional``.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


REPORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "contract_summary": ("Paramètre", "valeur"),
    "alpha_table": ("family", "penalty", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active", "converged"),
    "alpha_grid": ("family", "penalty", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active", "converged"),
    "elastic_net_rho_grid": ("family", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active", "converged"),
    "candidate_table": ("family", "penalty", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active"),
    "candidate_policy_table": ("family", "penalty", "alpha_relative", "l1_ratio", "validation_rmse", "n_options_active"),
    "exploratory_alpha_grid": ("benchmark", "family", "penalty", "l1_ratio", "alpha", "validation_rmse", "n_options_active"),
    "exploratory_alpha_missing": ("benchmark", "family", "penalty", "reason"),
    "alpha_tail_frontier": ("family", "penalty", "alpha", "validation_rmse", "validation_es", "n_options_active", "retained_profiles"),
    "es_budget_filter_flow": ("family", "penalty", "stage", "remaining", "removed_at_stage"),
    "tail_grid": ("family", "penalty", "objective", "l1_ratio", "alpha_relative_tail", "lambda_es", "lambda_selection_allowed", "optimisation_budget_pct_notional", "validation_budget_respected", "validation_rmse", "validation_es", "n_options_active", "method_status"),
    "tail_alpha_references": ("family", "penalty", "l1_ratio", "alpha_reference", "reference_type"),
    "exploratory_alpha_selected": ("benchmark", "family", "penalty", "l1_ratio", "alpha", "validation_rmse", "n_options_active"),
    "alpha_profiles": ("family", "penalty", "profile", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active"),
    "selected_regularisation_profiles": ("family", "penalty", "profile", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active"),
    "profile_table": ("family", "penalty", "profile", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active"),
    "stable_profiles_table": ("family", "penalty", "profile", "l1_ratio", "alpha_relative", "validation_rmse", "n_options_active"),
    "elastic_net_rho_profiles": ("family", "searched_l1_ratio", "profile", "alpha_relative", "validation_rmse", "n_options_active"),
    "elastic_net_selected_pairs": ("family", "profile", "searched_l1_ratio", "alpha_relative", "validation_rmse", "n_options_active"),
    "stability_summary": ("family", "penalty", "profile", "n_converged", "n_calibrations", "validation_rmse_mean", "validation_rmse_std", "n_options_active_mean", "support_jaccard_median", "passes_stability_filter"),
    "stability_size_diagnostic": ("family", "penalty", "profiles_represented", "base_n_options_active", "n_options_active_mean", "n_options_active_min", "n_options_active_max", "size_multiplier", "support_pairwise_jaccard_median", "n_converged", "n_calibrations"),
    "decision_synthesis_compact": ("family", "penalty", "method", "profile", "alpha_relative", "l1_ratio", "lambda_es", "es_budget_pct_notional", "optimisation_budget_pct_notional", "validation_rmse_pct_notional", "validation_es_pct_notional", "n_options_active", "selection_status"),
    "sampling_decision": ("family", "method", "mixture_description", "worst_precision_ratio_to_mc", "median_precision_ratio_to_mc", "effective_sample_ratio_min"),
    "stability_details": ("family", "penalty", "profile", "n_calibrations", "convergence_rate", "validation_rmse_mean", "n_options_active_mean", "support_jaccard_median"),
    "l0_initialization_audit": ("family", "n_alphas", "initializations_mean", "distinct_supports_mean", "jaccard_median"),
    "exploratory_l0_initialization_audit": ("benchmark", "family", "n_trials", "n_selected", "convergence_rate"),
    "regularization_filter_flow": ("family", "penalty", "stage", "remaining", "removed_at_stage"),
    "alpha_tail_comparison": ("family", "penalty", "current_compromise_rmse", "current_compromise_es_975", "minimum_es_rmse", "minimum_es_975", "current_compromise_n_options", "minimum_es_n_options"),
    "lambda_es_profiles": ("family", "penalty", "profile", "l1_ratio", "alpha_relative_tail", "lambda_es", "validation_rmse", "validation_es", "n_options_active", "method_status"),
    "es_budget_profiles": ("family", "penalty", "budget_level", "profile", "l1_ratio", "alpha_relative_tail", "optimisation_budget_pct_notional", "risk_limit_pct_notional", "validation_budget_respected", "validation_rmse", "validation_es", "n_options_active", "method_status"),
    "es_budget_level_status": ("family", "penalty", "level", "risk_limit_pct_notional", "n_admissible", "selected_validation_rmse_pct_notional", "selected_validation_es_pct_notional", "selected_n_options_active", "selected_optimisation_budget_pct_notional", "selected_own_budget_respected", "status"),
    "importance_sampling_grid": ("family", "mixture_description", "n_policies", "worst_precision_ratio_to_mc", "median_precision_ratio_to_mc", "effective_sample_ratio_min", "tail_ess_min", "recommended"),
    "importance_sampling_policy_summary": ("family", "penalty", "objective", "profile", "candidate_index", "es_mean", "standard_mc_es_mean", "es_mean_difference_to_mc", "es_std", "standard_mc_es_std", "precision_ratio_to_mc", "tail_ess_min", "recommended"),
    "importance_sampling_details": ("family", "candidate_index", "method", "seed", "penalty", "objective", "profile", "es", "tail_effective_sample_size", "effective_sample_ratio"),
    "importance_sampling_diagnostics": ("family", "n_paths", "effective_sample_size", "effective_sample_ratio", "maximum_normalized_weight"),
    "importance_component_summary": ("family", "component", "tilt", "configured_probability", "simulated_frequency", "weighted_target_mass"),
    "importance_tail_decomposition": ("family", "penalty", "profile", "condition", "level", "share_of_tail_probability", "share_of_es"),
    "price_benchmark_table": ("family", "penalty", "n_options_active", "test_rmse", "test_mae"),
    "static_cashflow_benchmark": ("family", "penalty", "alpha", "rho_elastic_net", "test_rmse", "test_mae", "terminal_mean_error_pct_notional", "terminal_mae_pct_notional", "terminal_rmse_pct_notional", "terminal_under_replication_rate", "terminal_es_975_pct_notional", "terminal_max_loss_pct_notional", "n_options_active"),
    "conditional_cashflow_benchmark": ("family", "penalty", "alpha", "rho_elastic_net", "test_rmse", "test_mae", "terminal_mean_error_pct_notional", "terminal_mae_pct_notional", "terminal_rmse_pct_notional", "terminal_under_replication_rate", "terminal_es_975_pct_notional", "terminal_max_loss_pct_notional"),
    "method_comparison_summary": ("family", "penalty", "method", "cashflow_rmse_pct_notional", "terminal_mean_error_pct_notional", "terminal_mae_pct_notional", "terminal_rmse_pct_notional", "terminal_under_replication_rate", "terminal_es_975_pct_notional", "terminal_max_loss_pct_notional", "p95_funding_need_pct_notional"),
    "risk_summary": ("family", "penalty", "profile", "mean_replication_error_pct_notional", "mae_replication_error_pct_notional", "under_replication_rate", "gross_rmse_pct_notional", "residual_rmse_pct_notional", "rmse_relative_reduction", "gross_es_975_pct_notional", "residual_es_975_pct_notional", "es_975_relative_reduction", "residual_max_loss_pct_notional"),
    "risk_comparison": ("family", "penalty", "profile", "condition", "gross_rmse", "residual_rmse", "gross_es_975", "residual_es_975"),
    "unified_benchmark_table": ("method", "family", "rebalancing", "sparse", "risk_object", "mean_error_pct_notional", "mae_pct_notional", "rmse_pct_notional", "under_replication_rate", "es_975_pct_notional", "max_loss_pct_notional", "capital_aligned", "transaction_costs_included"),
    "calls_puts_gross_risk": ("condition", "n_observations", "mean_loss", "mae", "rmse", "under_replication_rate", "es_975", "max_loss"),
    "full_gross_risk": ("condition", "n_observations", "mean_loss", "mae", "rmse", "under_replication_rate", "es_975", "max_loss"),
    "calls_puts_residual_risk": ("family", "penalty", "profile", "condition", "n_observations", "mean_loss", "mae", "rmse", "under_replication_rate", "es_975", "max_loss"),
    "full_residual_risk": ("family", "penalty", "profile", "condition", "n_observations", "mean_loss", "mae", "rmse", "under_replication_rate", "es_975", "max_loss"),
    "calls_puts_gross_risk_units": ("condition", "metric", "pct_notional", "bps_notional"),
    "full_gross_risk_units": ("condition", "metric", "pct_notional", "bps_notional"),
    "calls_puts_residual_risk_units": ("family", "penalty", "profile", "condition", "metric", "pct_notional", "bps_notional"),
    "full_residual_risk_units": ("family", "penalty", "profile", "condition", "metric", "pct_notional", "bps_notional"),
    "calls_puts_risk_by_condition": ("condition", "n_observations", "condition_frequency", "quantile_reliability"),
    "full_risk_by_condition": ("condition", "n_observations", "condition_frequency", "quantile_reliability"),
    "importance_ci_table": ("family", "penalty", "profile", "standard_es_975_pct_notional", "standard_ci_low", "standard_ci_high", "importance_es_975_pct_notional", "importance_ci_low", "importance_ci_high", "confidence_intervals_overlap"),
    "importance_comparison": ("family", "penalty", "profile", "standard_residual_es_975", "importance_residual_es_975", "difference_residual_es_975", "standard_residual_rmse", "importance_residual_rmse"),
    "importance_precision_table": ("Famille", "Pénalité", "Profil", "Écart IS − MC (point de nominal)", "Largeur IC Monte-Carlo", "Largeur IC importance sampling", "Intervalles compatibles"),
    "tail_concentration_decision_table": ("family", "penalty", "profile", "es_975_pct_notional", "es_99_pct_notional", "top_1pct_share_pct", "top_5pct_share_pct", "effective_positive_tail_contributors"),
    "tail_concentration_summary": ("family", "penalty", "profile", "level", "es", "tail_effective_sample_size", "effective_positive_tail_contributors"),
    "tail_concentration_curve": ("family", "penalty", "profile", "level", "tail_mass_fraction", "positive_tail_loss_share"),
    "tail_exclusive_regime_decomposition": ("family", "penalty", "profile", "condition", "level", "share_of_tail_probability", "share_of_es"),
    "tail_risk_component_summary": ("family", "component", "tilt", "configured_probability", "simulated_frequency", "weighted_target_mass"),
    "tail_risk_sampling_diagnostics": ("family", "n_paths", "effective_sample_size", "effective_sample_ratio", "maximum_normalized_weight"),
    "tail_risk_experiment_table": ("family", "profile", "calibration_sampling", "risk_control", "penalty", "es_budget_pct_notional", "risk_limit_es_pct_notional", "constraint_feasible_in_calibration", "evaluation_mean_error_pct_notional", "evaluation_mae_pct_notional", "evaluation_rmse_pct_notional", "evaluation_under_replication_rate", "evaluation_es_pct_notional", "evaluation_max_loss_pct_notional", "evaluation_cap_respected", "n_active_coefficients"),
    "funding_summary": ("family", "penalty", "profile", "implementation", "initial_net_cost_mean_pct_notional", "terminal_pnl_mean_pct_notional", "additional_capital_p95_pct_notional", "loss_es_975_pct_notional", "cumulative_otc_execution_cost_mean_bps_notional"),
    "funding_path_summary": ("family", "penalty", "profile", "binary_mode", "n_paths", "terminal_pnl_mean", "additional_capital_p95", "otc_cost_mean"),
    "funding_ledger": ("family", "penalty", "profile", "n_events", "cash_min", "otc_cost_sum"),
    "chronology_audit": ("family", "n_decisions", "chronology_valid_all", "fallback_rate"),
    "retained_policy_weights": ("family", "penalty", "profile", "payment_date", "decision_state", "name", "kind", "weight"),
    "internal_hedge_benchmark": ("family", "penalty", "profile", "residual_rmse_pct_notional", "residual_es_975_pct_notional", "rmse_improvement_vs_reference", "es_975_improvement_vs_reference"),
    "public_pricing_benchmark": ("issuer", "document_date", "structure", "issue_price", "estimated_value_low", "estimated_value_high", "gap_pct_mid"),
    "pricing": ("actualized_price", "std_error", "ci95_low", "ci95_high", "n_paths"),
    "three_price_summary": ("family", "penalty", "profile", "implementation", "price_type", "price_pct_notional", "cushion_vs_theoretical_pct_notional"),
    "decision_table": ("family", "penalty", "profile", "implementation", "n_options_active", "residual_rmse_pct_notional", "residual_es_975_pct_notional", "terminal_pnl_mean_pct_notional", "additional_capital_p95_pct_notional"),
    "transaction_cost_summary": ("family", "penalty", "profile", "cost_scenario", "expected_transaction_cost", "expected_transaction_cost_bps", "n_priced_lines", "n_missing_lines", "cost_complete"),
    "risk_conditional_comparison": ("family", "penalty", "profile", "condition", "n_observations", "rmse_relative_reduction", "es_975_relative_reduction", "residual_rmse", "residual_es_975"),
    "cost_risk_filter": ("family", "penalty", "profile", "cost_scenario", "transaction_cost_pct_notional", "risk_reduction_pct_notional", "cost_to_risk_reduction_ratio", "net_risk_reduction_pct_notional", "passes_cost_risk_filter"),
    "profile_coverage": ("family", "penalty", "n_distinct_candidates", "n_profiles", "status"),
}


FRENCH_LABELS = {
    "family": "Famille", "benchmark": "Benchmark", "penalty": "Pénalité",
    "profile": "Profil", "implementation": "Implémentation", "condition": "Régime",
    "l1_ratio": "Ratio L1 (ρ)", "searched_l1_ratio": "Ratio L1 (ρ)",
    "alpha": "Alpha", "alpha_relative": "Alpha relatif",
    "alpha_relative_tail": "Alpha relatif (queue)",
    "validation_rmse": "RMSE validation", "validation_rmse_mean": "RMSE moyenne",
    "validation_rmse_std": "Écart-type RMSE", "validation_es": "ES validation",
    "n_options_active": "Options actives", "n_options_active_mean": "Options moyennes",
    "profiles_represented": "Profils représentés",
    "base_n_options_active": "Options initiales",
    "n_options_active_min": "Options min.", "n_options_active_max": "Options max.",
    "size_multiplier": "Rapport moyen / initial",
    "support_pairwise_jaccard_median": "Jaccard entre graines",
    "rho_elastic_net": "Ratio L1 (ρ)", "test_rmse": "RMSE (évaluation)",
    "test_mae": "MAE (évaluation)", "method": "Méthode",
    "cashflow_rmse_pct_notional": "RMSE paiements (% nominal)",
    "terminal_rmse_pct_notional": "RMSE terminale (% nominal)",
    "terminal_mean_error_pct_notional": "Erreur moyenne terminale (% nominal)",
    "terminal_mae_pct_notional": "MAE terminale (% nominal)",
    "terminal_under_replication_rate": "Taux de sous-réplication terminale",
    "terminal_max_loss_pct_notional": "Perte maximale terminale (% nominal)",
    "evaluation_mean_error_pct_notional": "Erreur moyenne (% nominal)",
    "evaluation_mae_pct_notional": "MAE (% nominal)",
    "evaluation_under_replication_rate": "Taux de sous-réplication",
    "evaluation_max_loss_pct_notional": "Perte maximale (% nominal)",
    "terminal_es_975_pct_notional": "ES terminal 97,5 % (% nominal)",
    "p95_funding_need_pct_notional": "Besoin de financement P95 (% nominal)",
    "n_active_coefficients": "Coefficients actifs",
    "n_converged": "Convergences", "n_calibrations": "Graines",
    "passes_stability_filter": "Stable", "support_jaccard_median": "Jaccard médian",
    "stage": "Étape", "remaining": "Restantes", "removed_at_stage": "Éliminées",
    "selection_status": "Statut", "method": "Méthode",
    "lambda_es": "Lambda ES", "es_budget_pct_notional": "Plafond ES (% nominal)",
    "optimisation_budget_pct_notional": "Budget d'optimisation (% nominal)",
    "risk_limit_pct_notional": "Plafond commun (% nominal)",
    "risk_limit_es_pct_notional": "Plafond ES commun (% nominal)",
    "evaluation_cap_respected": "Plafond respecté en évaluation",
    "validation_budget_respected": "Budget d'optimisation respecté en validation",
    "budget_level": "Niveau de plafond",
    "level": "Niveau de plafond", "n_admissible": "Candidats admissibles",
    "selected_validation_rmse_pct_notional": "RMSE retenue (% nominal)",
    "selected_validation_es_pct_notional": "ES retenu (% nominal)",
    "selected_n_options_active": "Options actives retenues",
    "selected_optimisation_budget_pct_notional": "Budget d'optimisation retenu (% nominal)",
    "selected_own_budget_respected": "Budget d'optimisation respecté en validation",
    "status": "Statut",
    "validation_rmse_pct_notional": "RMSE validation (% nominal)",
    "validation_es_pct_notional": "ES validation (% nominal)",
    "worst_precision_ratio_to_mc": "Pire écart-type IS / MC",
    "median_precision_ratio_to_mc": "Ratio médian IS / MC",
    "gross_rmse_pct_notional": "RMSE brute (% nominal)",
    "residual_rmse_pct_notional": "RMSE résiduelle (% nominal)",
    "mean_replication_error_pct_notional": "Erreur moyenne (% nominal)",
    "mae_replication_error_pct_notional": "MAE (% nominal)",
    "mean_error_pct_notional": "Erreur moyenne (% nominal)",
    "mae_pct_notional": "MAE (% nominal)",
    "under_replication_rate": "Taux de sous-réplication",
    "max_loss_pct_notional": "Perte maximale (% nominal)",
    "residual_max_loss_pct_notional": "Perte maximale résiduelle (% nominal)",
    "gross_es_975_pct_notional": "ES brut 97,5 % (% nominal)",
    "residual_es_975_pct_notional": "ES résiduel 97,5 % (% nominal)",
    "rmse_relative_reduction": "Réduction RMSE (ratio)",
    "es_975_relative_reduction": "Réduction ES (ratio)",
    "terminal_pnl_mean_pct_notional": "P&L moyen (% nominal)",
    "additional_capital_p95_pct_notional": "Capital P95 (% nominal)",
    "initial_net_cost_mean_pct_notional": "Coût initial (% nominal)",
    "loss_es_975_pct_notional": "ES perte 97,5 % (% nominal)",
    "cumulative_otc_execution_cost_mean_bps_notional": "Coût OTC (bps nominal)",
    "price_pct_notional": "Prix (% nominal)",
    "cushion_vs_theoretical_pct_notional": "Marge vs théorique (% nominal)",
    "candidate_index": "Mélange IS", "es_mean": "ES moyen", "es_std": "Écart-type ES",
    "mixture_description": "Distribution simulée",
    "effective_sample_ratio_min": "ESS minimale (ratio)", "recommended": "Recommandé",
    "cost_scenario": "Scénario de coût", "expected_transaction_cost": "Coût attendu",
    "expected_transaction_cost_bps": "Coût attendu (bps)",
    "n_priced_lines": "Lignes chiffrées", "n_missing_lines": "Lignes sans prix",
    "cost_complete": "Coût complet",
    "transaction_cost_pct_notional": "Coût (% nominal)",
    "risk_reduction_pct_notional": "Risque évité (% nominal)",
    "cost_to_risk_reduction_ratio": "Coût / risque évité",
    "net_risk_reduction_pct_notional": "Risque évité net (% nominal)",
    "passes_cost_risk_filter": "Passe le filtre économique",
    "standard_residual_es_975": "ES MC 97,5 %", "importance_residual_es_975": "ES IS 97,5 %",
    "difference_residual_es_975": "Écart ES (IS − MC)",
    "standard_residual_rmse": "RMSE MC", "importance_residual_rmse": "RMSE IS",
    "n_paths": "Trajectoires", "n_events": "Événements", "cash_min": "Cash minimum",
    "otc_cost_sum": "Coût OTC total", "otc_cost_mean": "Coût OTC moyen",
    "terminal_pnl_mean": "P&L moyen", "additional_capital_p95": "Capital P95",
    "n_decisions": "Décisions", "chronology_valid_all": "Chronologie valide",
    "fallback_rate": "Part des décisions en repli",
    "n_alphas": "Alphas", "initializations_mean": "Initialisations moyennes",
    "distinct_supports_mean": "Supports distincts moyens", "jaccard_median": "Jaccard médian",
    "n_trials": "Essais", "n_selected": "Sélectionnés", "convergence_rate": "Taux de convergence",
    "n_repetitions": "Répétitions",
    "converged": "Convergé", "n_observations": "Observations",
    "mean_loss": "Erreur moyenne", "mae": "MAE", "rmse": "RMSE",
    "es_975": "ES 97,5 %", "max_loss": "Perte maximale",
    "pct_notional": "% du nominal", "bps_notional": "bps du nominal",
}


def make_report_view(name: str, value: pd.DataFrame | pd.Series | Mapping) -> pd.DataFrame | None:
    """Return a concise copy for presentation; never mutate the complete table."""
    if name not in REPORT_COLUMNS:
        return None
    if name == "contract_summary":
        frame = pd.DataFrame(value).copy()
        if isinstance(value, pd.Series):
            frame = value.rename_axis("Paramètre").reset_index()
            frame = frame.rename(columns={frame.columns[1]: "valeur"})
        elif "Unnamed: 0" in frame:
            frame = frame.rename(columns={"Unnamed: 0": "Paramètre"})
        elif not isinstance(frame.index, pd.RangeIndex):
            frame = frame.reset_index().rename(columns={"index": "Paramètre"})
    elif isinstance(value, Mapping):
        # A scalar summary such as pricing is one record, not a column of arrays.
        frame = pd.DataFrame([value]).copy()
    else:
        frame = pd.DataFrame(value).copy()
    if frame.empty:
        return frame
    if name in {"alpha_table", "alpha_grid", "elastic_net_rho_grid", "candidate_table"}:
        if "is_candidate_after_duplicates" in frame:
            frame = frame.loc[frame["is_candidate_after_duplicates"].fillna(False)]
        elif "is_candidate" in frame:
            frame = frame.loc[frame["is_candidate"].fillna(False)]
    elif name == "exploratory_alpha_grid":
        eligible = frame.loc[frame["converged"] & frame["n_options_active"].ge(2)]
        if not eligible.empty:
            keys = [column for column in ("benchmark", "family", "penalty") if column in eligible]
            frame = eligible.loc[eligible.groupby(keys)["validation_rmse"].idxmin()]
    elif name == "alpha_tail_frontier" and "pareto_rmse_es_options" in frame:
        frame = frame.loc[frame["pareto_rmse_es_options"]]
    elif name == "tail_grid":
        eligible = frame.loc[frame["converged"] & frame["feasible_calibration"]]
        if "lambda_selection_allowed" in eligible:
            eligible = eligible.loc[eligible["lambda_selection_allowed"].astype(bool)]
        if "validation_budget_respected" in eligible:
            eligible = eligible.loc[eligible["validation_budget_respected"]]
        if not eligible.empty:
            keys = [column for column in ("family", "objective") if column in eligible]
            frame = eligible.loc[eligible.groupby(keys)["validation_es"].idxmin()]
    elif name == "stability_details":
        frame = frame.groupby(["family", "penalty", "profile"], as_index=False).agg(
            n_calibrations=("seed", "size"),
            convergence_rate=("converged", "mean"),
            validation_rmse_mean=("validation_rmse", "mean"),
            n_options_active_mean=("n_options_active", "mean"),
            support_jaccard_median=("support_jaccard_vs_base", "median"),
        )
    elif name == "l0_initialization_audit":
        frame = frame.groupby("family", as_index=False).agg(
            n_alphas=("alpha_relative", "size"),
            initializations_mean=("n_initializations", "mean"),
            distinct_supports_mean=("n_distinct_supports", "mean"),
            jaccard_median=("warm_cold_support_jaccard", "median"),
        )
    elif name == "exploratory_l0_initialization_audit":
        frame = frame.groupby(["benchmark", "family"], as_index=False).agg(
            n_trials=("alpha", "size"),
            n_selected=("selected", "sum"),
            convergence_rate=("converged", "mean"),
        )
    elif name == "importance_sampling_details":
        frame = frame.groupby(["family", "candidate_index"], as_index=False).agg(
            n_repetitions=("seed", "size"),
            es_mean=("es", "mean"),
            es_std=("es", "std"),
            effective_sample_ratio_min=("effective_sample_ratio", "min"),
        )
    elif name == "chronology_audit":
        frame = frame.groupby("family", as_index=False).agg(
            n_decisions=("chronology_valid", "size"),
            chronology_valid_all=("chronology_valid", "all"),
            fallback_rate=("uses_fallback", "mean"),
        )
    elif name == "funding_path_summary":
        aggregations = {
            "n_paths": ("terminal_pnl", "size"),
            "terminal_pnl_mean": ("terminal_pnl", "mean"),
            "additional_capital_p95": (
                "additional_capital_without_borrowing",
                lambda values: values.quantile(0.95),
            ),
        }
        if "cumulative_otc_execution_cost" in frame:
            aggregations["otc_cost_mean"] = (
                "cumulative_otc_execution_cost", "mean",
            )
        frame = frame.groupby(
            ["family", "penalty", "profile", "binary_mode"], as_index=False,
        ).agg(**aggregations)
    elif name == "funding_ledger":
        aggregations = {
            "n_events": ("event_type", "size"),
            "cash_min": ("cash_after_event", "min"),
        }
        if "otc_execution_cost" in frame:
            aggregations["otc_cost_sum"] = ("otc_execution_cost", "sum")
        frame = frame.groupby(
            ["family", "penalty", "profile"], as_index=False,
        ).agg(**aggregations)
    elif name == "retained_policy_weights":
        frame = frame.loc[frame["is_active"] & frame["kind"].ne("Cash")].copy()
        frame["abs_weight_for_sort"] = frame["weight"].abs()
        frame = frame.sort_values("abs_weight_for_sort", ascending=False).groupby(
            ["family", "penalty", "profile"], sort=False,
        ).head(5)
    elif name.endswith("_risk_units") and "metric" in frame:
        frame = frame.loc[
            frame["metric"].isin(("rmse", "es_975", "max_loss"))
            & frame["condition"].eq("all")
        ]
    elif name in {"importance_tail_decomposition", "tail_exclusive_regime_decomposition",
                  "tail_concentration_summary", "tail_concentration_curve"} and "level" in frame:
        frame = frame.loc[frame["level"].eq(0.975)]
        if name == "tail_concentration_curve":
            frame = frame.loc[frame["tail_mass_fraction"].isin((0.01, 0.05, 0.10))]
    if name in {"three_price_summary", "funding_summary", "funding_path_summary",
                "risk_conditional_comparison", "importance_tail_decomposition",
                "tail_concentration_curve", "tail_exclusive_regime_decomposition"}:
        if "profile" in frame:
            compromise = frame.loc[frame["profile"].eq("compromise")]
            if not compromise.empty:
                frame = compromise
    columns = [column for column in REPORT_COLUMNS[name] if column in frame]
    if not columns:
        return None
    view = frame.loc[:, columns].copy()
    if "method" in view:
        view["method"] = view["method"].replace({
            "par_echeance": "Conditionnel par échéance",
            "total_pathwise": "Politique totale pathwise",
        })
    number_columns = view.select_dtypes(include="number").columns
    view.loc[:, number_columns] = view.loc[:, number_columns].round(4)
    return view.rename(columns=FRENCH_LABELS)


def build_report_views(
    full_tables: Mapping[str, pd.DataFrame | pd.Series],
) -> dict[str, pd.DataFrame]:
    """Create one exportable concise companion for every registered result."""
    views = {}
    for name, value in full_tables.items():
        view = make_report_view(name, value)
        if view is not None and not view.empty:
            views[f"report_{name}"] = view
    return views
