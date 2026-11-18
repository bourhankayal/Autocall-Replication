import json

import matplotlib
from matplotlib.colors import to_rgba
import numpy as np
import pandas as pd
import pytest
import types
from types import SimpleNamespace

import autocall_replication.replication.hyperparameter_study as hyperparameter_study

from autocall_replication.replication.hyperparameter_study import (
    HyperparameterGrid,
    combine_conditional_elastic_net_profiles,
    configuration_fingerprint,
    export_hyperparameter_study,
    exploratory_alpha_values,
    evaluate_alpha_tail_frontier,
    load_selected_hyperparameters,
    load_selected_policy_results,
    plot_regularization_grid,
    plot_seed_robustness,
    plot_regularization_filter_map,
    plot_exploratory_benchmark_schematic,
    plot_exploratory_alpha_grid,
    plot_exploratory_elastic_net_grid,
    plot_rho_grid,
    plot_alpha_tail_frontier,
    plot_tail_frontiers,
    plot_tail_budget_filter_flow,
    promote_hyperparameter_selection,
    regularization_filter_flow,
    select_profiles_after_candidate_stability,
    run_tail_hyperparameter_grid,
    run_l0_tail_support_grid,
    merge_tail_rho_grids,
    fixed_tail_profile_policies,
    select_budget_ceiling_profiles,
    select_three_frontier_profiles,
    select_exploratory_benchmark_alphas,
    tail_budget_filter_flow,
)

matplotlib.use("Agg")


def _configuration():
    return {
        "product": {"notional": 100.0, "coupon_rate": 0.02},
        "market": {"spot0": 100.0, "volatility": 0.20},
        "families": ["calls_puts", "full"],
    }


def test_default_grid_covers_every_agreed_hyperparameter():
    grid = HyperparameterGrid()
    grid.validate()

    assert grid.penalties == ("l0", "l1", "l2", "elastic_net")
    assert grid.elastic_net_l1_ratios == (
        0.05, 0.10, 0.25, 0.50, 0.75, 0.775, 0.80, 0.825, 0.85,
        0.875, 0.90, 0.925, 0.95, 0.975, 0.99,
    )
    assert grid.tail_alpha_ratios[-2:] == (1e-4, 1e-5)
    assert 0.0 in grid.lambda_es_values
    assert len(grid.lambda_es_values) >= 5
    assert grid.es_budget_pct_notional == (5.0, 10.0, 15.0)
    assert len(grid.importance_candidates) >= 3
    assert exploratory_alpha_values(grid, "l1") == grid.exploratory_alpha_sparse
    assert exploratory_alpha_values(grid, "l2") == grid.exploratory_alpha_ridge
    assert grid.exploratory_alpha_sparse == grid.exploratory_alpha_ridge
    assert grid.exploratory_alpha_sparse[0] == 1e-8
    assert grid.exploratory_alpha_sparse[-1] == 1e8
    assert grid.exploratory_alpha_sparse[-7:] == (
        1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8,
    )


def test_exploratory_alpha_selection_is_by_validation_and_convergence():
    table = pd.DataFrame({
        "benchmark": ["price_surface"] * 3,
        "family": ["full"] * 3,
        "penalty": ["l1"] * 3,
        "alpha": [0.01, 0.1, 1.0],
        "validation_rmse": [1.0, 2.0, 0.5],
        "converged": [True, True, True],
        "n_options_active": [3, 2, 1],
    })
    selected = select_exploratory_benchmark_alphas(table)
    assert selected["alpha"].tolist() == [0.01]


def test_exploratory_alpha_plot_separates_ineligible_points_from_selected_curve():
    table = pd.DataFrame({
        "benchmark": ["static_cashflows"] * 3,
        "family": ["calls_puts"] * 3,
        "penalty": ["l0"] * 3,
        "alpha": [0.3, 3.0, 100.0],
        "validation_rmse": [27.49, 32.87, 46.80],
        "converged": [False, True, True],
        "n_options_active": [80, 3, 0],
    })
    selected = select_exploratory_benchmark_alphas(table)
    figure = plot_exploratory_alpha_grid(
        table, selected, benchmark="static_cashflows", nominal=100.0,
    )
    axis = figure.axes[0]
    assert selected["alpha"].tolist() == [3.0]
    assert np.isnan(axis.lines[0].get_ydata()[0])
    assert axis.lines[0].get_ydata()[1] == pytest.approx(32.87)
    assert np.isnan(axis.lines[0].get_ydata()[2])
    assert {item.get_text() for item in axis.get_legend().get_texts()} == {
        "L0", "Non convergé · valeur à l'arrêt", "Convergé · moins de 2 options",
    }
    assert axis.collections[-1].get_offsets()[0, 0] == pytest.approx(3.0)


def test_elastic_net_temporal_selection_jointly_chooses_ratio_and_alpha():
    table = pd.DataFrame({
        "benchmark": ["conditional_cashflows"] * 4,
        "family": ["full"] * 4,
        "penalty": ["elastic_net"] * 4,
        "l1_ratio": [0.1, 0.1, 0.9, 0.9],
        "alpha": [0.01, 0.1, 0.01, 0.1],
        "validation_rmse": [3.0, 2.0, 1.5, 1.0],
        "converged": [True, True, True, True],
        "n_options_active": [3, 3, 1, 4],
    })
    selected = select_exploratory_benchmark_alphas(table)
    assert len(selected) == 1
    assert selected.iloc[0]["l1_ratio"] == 0.9
    assert selected.iloc[0]["alpha"] == 0.1
    comparison = plot_exploratory_alpha_grid(
        table, selected, benchmark="conditional_cashflows",
    )
    assert [line.get_label() for line in comparison.axes[1].lines] == [
        "Elastic Net (ρ=0.9)",
    ]
    elastic = plot_exploratory_elastic_net_grid(
        table, selected, benchmark="conditional_cashflows",
    )
    assert {line.get_label() for line in elastic.axes[1].lines} == {
        "Elastic Net (ρ=0.1)", "Elastic Net (ρ=0.9)",
    }
    for figure in (comparison, elastic):
        axis = figure.axes[1]
        selected_line = next(line for line in axis.lines if "ρ=0.9" in line.get_label())
        assert any(
            np.allclose(collection.get_facecolors()[0], to_rgba(selected_line.get_color()))
            for collection in axis.collections if len(collection.get_facecolors())
        )
        assert all(
            "retenu" not in item.get_text().lower()
            for axis in figure.axes if axis.get_legend() is not None
            for item in axis.get_legend().get_texts()
        )

    # Simulate an IPython autoreload-updated function that retained old globals.
    stale_callable = types.FunctionType(
        plot_exploratory_elastic_net_grid.__code__,
        {"__builtins__": __builtins__},
    )
    assert len(stale_callable(
        table, selected, benchmark="conditional_cashflows", nominal=100.0,
    ).axes) == 2


def test_rho_heatmap_separates_families_and_shares_metric_scales():
    rows = []
    for family, offset in (("calls_puts", 2.0), ("full", 0.0)):
        for rho in (0.25, 0.75):
            for index, alpha_relative in enumerate((1.0, 0.1, 0.01)):
                rows.append({
                    "family": family, "penalty": "elastic_net",
                    "l1_ratio": rho, "alpha_relative": alpha_relative + 1e-16 * rho,
                    "converged": not (family == "full" and rho == 0.75 and index == 0),
                    "validation_rmse": offset + index + rho,
                    "n_options_active": 2 + 3 * index,
                })
    selected = pd.DataFrame([
        {"family": "calls_puts", "searched_l1_ratio": 0.25, "alpha_relative": 0.1},
        {"family": "full", "searched_l1_ratio": 0.75, "alpha_relative": 0.01},
    ])
    figure = plot_rho_grid(pd.DataFrame(rows), selected=selected)
    panels = [axis for axis in figure.axes if axis.images]
    assert len(panels) == 4
    assert "sans binaires" in panels[0].get_title()
    assert "Calls + Puts + binaires" in panels[2].get_title()
    assert panels[0].images[0].get_clim() == panels[2].images[0].get_clim()
    assert panels[1].images[0].get_clim() == panels[3].images[0].get_clim()
    assert all(len(axis.patches) == 1 for axis in panels)
    assert np.ma.getmaskarray(panels[3].images[0].get_array())[0, 1]


def test_global_elastic_net_profiles_keep_their_own_ratio_and_weights():
    def path_for(rho, errors, counts):
        table = pd.DataFrame({
            "penalty": ["elastic_net"] * 3,
            "l1_ratio": [rho] * 3,
            "solution_index": [0, 1, 2],
            "alpha": [3.0, 2.0, 1.0],
            "alpha_relative": [1.0, 0.1, 0.01],
            "validation_rmse": errors,
            "n_options_active": counts,
            "converged": [True] * 3,
            "is_candidate": [True] * 3,
            "is_candidate_after_performance": [True] * 3,
            "is_candidate_after_duplicates": [True] * 3,
            "duplicate_status": ["kept_representative"] * 3,
        })
        solutions = [
            {"solution_index": i, "weights": np.array([float(rho), float(i)]),
             "policy_metrics": {"n_policy_nodes": 1}}
            for i in range(3)
        ]
        return {
            "family": "full", "A": np.ones((3, 2)), "b": np.arange(3.0),
            "feature_table": pd.DataFrame({"name": ["cash", "call"]}),
            "table": table, "raw_table": table.copy(),
            "duplicate_report": pd.DataFrame(columns=["penalty"]),
            "results": {"elastic_net": {"solutions": solutions}},
        }

    ratio_results = {
        0.1: path_for(0.1, [1.0, 1.5, 2.0], [10, 8, 6]),
        0.9: path_for(0.9, [1.2, 2.0, 3.0], [4, 2, 1]),
    }
    base = dict(ratio_results[0.1])
    base["profiles"] = pd.DataFrame(columns=["penalty", "profile"])
    base["profile_coverage"] = pd.DataFrame([
        {"penalty": "elastic_net", "n_distinct_candidates": 3, "n_profiles": 3}
    ])
    combined, selected = combine_conditional_elastic_net_profiles(base, ratio_results)
    assert len(selected) == 3
    assert selected.loc[selected["profile"].eq("performance"), "l1_ratio"].iloc[0] == 0.1
    assert selected.loc[selected["profile"].eq("parsimony"), "l1_ratio"].iloc[0] == 0.9
    for _, row in selected.iterrows():
        solution = combined["results"]["elastic_net"]["solutions"][int(row["solution_index"])]
        assert solution["l1_ratio"] == row["l1_ratio"]
        assert solution["weights"][0] == row["l1_ratio"]
    assert len(combined["table"]) == 6
    assert {policy["family"] for policy in combined["candidate_policies"]} == {"full"}


def test_rho_heatmap_marks_three_distinct_profiles_per_family():
    rows = [
        {"family": family, "penalty": "elastic_net", "l1_ratio": rho,
         "alpha_relative": alpha, "converged": True,
         "validation_rmse": 2.0 + rho + alpha, "n_options_active": 3 + i}
        for family in ("calls_puts", "full")
        for rho in (0.1, 0.9)
        for i, alpha in enumerate((1.0, 0.1, 0.01))
    ]
    selected = pd.DataFrame([
        {"family": family, "profile": profile, "searched_l1_ratio": rho,
         "alpha_relative": alpha}
        for family in ("calls_puts", "full")
        for profile, rho, alpha in (("performance", 0.1, 1.0),
                                    ("compromise", 0.9, 0.1),
                                    ("parsimony", 0.9, 0.01))
    ])
    figure = plot_rho_grid(pd.DataFrame(rows), selected=selected)
    assert all(len(axis.patches) == 3 for axis in figure.axes if axis.images)


def test_regularization_filter_map_reconciles_every_stage():
    table = pd.DataFrame({
        "penalty": ["l1"] * 5,
        "converged": [True, True, True, True, False],
        "n_options_active": [3, 3, 3, 1, 3],
        "is_candidate": [True, True, True, False, False],
        "is_candidate_after_performance": [True, True, True, False, False],
        "duplicate_status": ["kept_representative", "strict_duplicate",
                             "quasi_strict_duplicate", "not_eligible", "not_eligible"],
        "is_candidate_after_duplicates": [True, False, False, False, False],
    })
    profiles = pd.DataFrame({"penalty": ["l1"] * 3, "solution_index": [0] * 3})
    base = {"table": table, "profiles": profiles}
    stable = {"profiles": profiles.iloc[:2]}
    flow = regularization_filter_flow(base, family="full", stable_result=stable)
    assert flow["remaining"].tolist() == [5, 4, 3, 3, 3, 2, 1, 1, 1]
    assert flow["removed_at_stage"].sum() == 4
    figure = plot_regularization_filter_map(flow)
    axis = figure.axes[0]
    assert "restantes" in axis.get_title()
    assert [label.get_text() for label in axis.texts] == [str(value) for value in flow["remaining"]]
    assert all("\n" not in label.get_text() for label in axis.texts)


def test_candidate_stability_reselects_profiles_before_pareto(monkeypatch):
    import autocall_replication.replication.regularization_path as path

    def performance(table, **_):
        return table.assign(is_candidate_after_performance=table["is_candidate"])

    def duplicates(table, **_):
        return table.assign(
            duplicate_status="kept_representative",
            is_candidate_after_duplicates=table["is_candidate_after_performance"],
        ), pd.DataFrame()

    monkeypatch.setattr(path, "apply_static_performance_filter", performance)
    monkeypatch.setattr(path, "remove_duplicate_candidates", duplicates)
    raw = pd.DataFrame({
        "penalty": ["l1", "l1", "l1"],
        "solution_index": [0, 1, 2],
        "converged": [True] * 3,
        "validation_rmse": [2.0, 2.4, 3.0],
        "n_options_active": [4, 5, 3],
        "alpha": [1.0, 0.1, 0.01],
        "alpha_relative": [1.0, 0.1, 0.01],
        "l1_ratio": [np.nan] * 3,
    })
    base = {
        "family": "full", "raw_table": raw, "table": raw,
        "results": {"l1": {"solutions": [{}, {}, {}]}},
        "profiles": pd.DataFrame(columns=["penalty", "profile", "solution_index"]),
        "active_threshold": 1e-8,
        "candidate_filters": {"min_active_options": 2, "max_active_options": 100},
    }
    stability = {"summary": pd.DataFrame({
        "penalty": ["l1"] * 3, "solution_index": [0, 1, 2],
        "passes_stability_filter": [False, True, True],
    }), "candidate_rule": "test"}
    result = select_profiles_after_candidate_stability(base, stability)
    assert result["candidates"]["solution_index"].tolist() == [1, 2]
    assert set(result["profiles"]["solution_index"]) == {1, 2}
    stages = regularization_filter_flow(result, family="full")["stage"].tolist()
    assert stages.index("Robustes sur dix graines") < stages.index("Non dominés")


def test_configuration_fingerprint_is_order_independent_and_sensitive():
    left = {"b": 2, "a": {"x": 1}}
    right = {"a": {"x": 1}, "b": 2}
    changed = {"a": {"x": 3}, "b": 2}

    assert configuration_fingerprint(left) == configuration_fingerprint(right)
    assert configuration_fingerprint(left) != configuration_fingerprint(changed)


def test_three_profiles_are_selected_from_outcomes_not_parameter_quantiles():
    table = pd.DataFrame(
        {
            "lambda_es": [0.0, 0.1, 0.2, 10.0],
            "validation_rmse": [2.0, 2.1, 2.2, 5.0],
            "validation_es": [10.0, 7.0, 6.9, 6.8],
            "converged": [True, True, True, True],
        }
    )
    profiles = select_three_frontier_profiles(table, parameter_column="lambda_es")

    assert set(profiles["profile"]) == {"rmse_priority", "compromise", "es_priority"}
    assert profiles.loc[profiles["profile"].eq("rmse_priority"), "lambda_es"].iloc[0] == 0.0
    assert profiles.loc[profiles["profile"].eq("es_priority"), "lambda_es"].iloc[0] == 10.0
    assert profiles.loc[profiles["profile"].eq("compromise"), "lambda_es"].iloc[0] in {0.1, 0.2}


def test_tail_grid_evaluates_every_lambda_and_budget_and_keeps_test_absent():
    rng = np.random.default_rng(7)
    calibration_A = rng.normal(size=(80, 4))
    true_weights = np.array([0.8, -0.4, 0.2, 0.0])
    calibration_b = calibration_A @ true_weights + rng.normal(scale=0.3, size=80)
    validation_A = rng.normal(size=(50, 4))
    validation_b = validation_A @ true_weights + rng.normal(scale=0.3, size=50)

    result = run_tail_hyperparameter_grid(
        calibration_A=calibration_A,
        calibration_b=calibration_b,
        validation_A=validation_A,
        validation_b=validation_b,
        penalty="l2",
        alpha_values=(0.001,),
        l1_ratio_values=(0.5,),
        lambda_es_values=(0.0, 0.1, 0.5),
        es_budget_values=(1.5, 1.0, 0.8),
        es_level=0.95,
        max_iter=500,
    )

    assert len(result["lambda_table"]) == 3
    assert len(result["budget_table"]) == 3
    assert "test_rmse" not in result["table"]
    assert "test_es" not in result["table"]
    assert set(result["lambda_profiles"]["profile"]) == {
        "rmse_priority", "compromise", "es_priority"
    }
    selected = result["budget_profiles"]
    assert selected.empty or (
        selected["feasible_calibration"].all()
        and selected["validation_budget_respected"].all()
    )
    assert result["budget_filter_flow"]["remaining"].is_monotonic_decreasing


def test_tail_grid_counts_options_without_cash_and_combines_rho_pairs():
    rng = np.random.default_rng(191)
    A = np.column_stack((np.ones(90), rng.normal(size=(90, 3))))
    b = 2.0 + A[:, 1] - 0.4 * A[:, 2] + rng.normal(scale=0.3, size=90)
    grids = []
    for rho in (0.25, 0.75):
        result = run_tail_hyperparameter_grid(
            calibration_A=A[:60], calibration_b=b[:60],
            validation_A=A[60:], validation_b=b[60:],
            penalty="elastic_net", alpha_values=(0.02,), l1_ratio_values=(rho,),
            lambda_es_values=(0.0, 0.2), es_budget_values=(2.0,),
            es_level=0.9, unpenalized_indices=(0,), max_iter=300,
        )
        result["table"]["alpha_relative_tail"] = 0.1
        grids.append(result)
    merged = merge_tail_rho_grids(grids)
    assert set(merged["table"]["l1_ratio"]) == {0.25, 0.75}
    assert merged["table"]["n_options_active"].le(3).all()
    assert merged["table"]["n_options_active"].le(merged["table"]["n_active_coefficients"]).all()
    assert set(merged["budget_profiles"]["l1_ratio"]).issubset({0.25, 0.75})


def test_l0_tail_support_grid_is_labelled_heuristic_and_uses_prior_supports():
    rng = np.random.default_rng(192)
    A = np.column_stack((np.ones(80), rng.normal(size=(80, 3))))
    b = 1.0 + A[:, 1] - 0.5 * A[:, 2] + rng.normal(scale=0.35, size=80)
    result = run_l0_tail_support_grid(
        calibration_A=A[:55], calibration_b=b[:55],
        validation_A=A[55:], validation_b=b[55:],
        support_weights=(np.array([0.0, 1.0, -0.5, 0.0]),
                         np.array([0.0, 1.0, 0.0, 0.5])),
        alpha_ratios=(1.0, 0.1), lambda_es_values=(0.0, 0.2),
        es_budget_values=(2.0,), es_level=0.9,
        unpenalized_indices=(0,), max_iter=300,
    )
    assert result["n_distinct_supports"] == 2
    assert len(result["table"]) == 6
    assert result["table"]["penalty"].eq("l0").all()
    assert result["table"]["method_status"].str.contains("heuristic").all()
    assert result["table"]["n_options_active"].le(2).all()
    assert "test_es" not in result["table"]


def test_fixed_tail_policies_recover_weights_from_convex_and_l0_profiles():
    convex_row = pd.DataFrame([{
        "profile": "compromise", "alpha": 0.2, "l1_ratio": 0.5,
        "lambda_es": 0.1, "es_budget": np.nan,
    }])
    l0_row = pd.DataFrame([{
        "profile": "es_priority", "alpha": 0.3, "l1_ratio": np.nan,
        "lambda_es": np.nan, "es_budget": 1.5,
    }])
    grids = {
        ("calls_puts", "elastic_net"): {
            "lambda_profiles": convex_row, "budget_profiles": pd.DataFrame(),
            "results": {("penalized_es", 0.5, 0.2, 0.1, None): SimpleNamespace(
                weights=np.array([1.0, 2.0])
            )},
        },
        ("calls_puts", "l0"): {
            "lambda_profiles": pd.DataFrame(), "budget_profiles": l0_row,
            "results": {("constrained_es", 0.3, 0.0, 1.5): np.array([3.0, 4.0])},
        },
    }
    policies = fixed_tail_profile_policies(grids)["calls_puts"]
    assert {(row["penalty"], row["objective"]) for row in policies} == {
        ("elastic_net", "penalized_es"), ("l0", "constrained_es")
    }
    np.testing.assert_array_equal(policies[0]["weights"], [1.0, 2.0])
    assert "heuristic" in policies[1]["method_status"]


def test_tail_grid_does_not_select_lambda_profiles_when_lambda_has_no_effect(monkeypatch):
    def constant_solution(A, b, config, **kwargs):
        return SimpleNamespace(
            weights=np.zeros(A.shape[1]), converged=True, feasible=True,
            rmse=float(np.sqrt(np.mean(b**2))), expected_shortfall=float(max(b)),
            n_iterations=1,
        )

    monkeypatch.setattr(hyperparameter_study, "solve_tail_risk_replication", constant_solution)
    A = np.ones((10, 2))
    b = np.arange(10, dtype=float)
    result = run_tail_hyperparameter_grid(
        calibration_A=A, calibration_b=b, validation_A=A, validation_b=b,
        penalty="elastic_net", alpha_values=(0.1, 0.01),
        l1_ratio_values=(0.5,), lambda_es_values=(0.0, 0.5, 2.0),
        es_budget_values=(), es_level=0.9,
    )
    assert not result["lambda_table"]["lambda_response_detected"].any()
    assert not result["lambda_table"].loc[
        result["lambda_table"]["lambda_es"].ge(1.0), "lambda_selection_allowed"
    ].any()
    assert result["lambda_profiles"].empty
    assert not result["table"]["lambda_response_detected"].any()


def test_alpha_tail_frontier_evaluates_all_converged_alphas_not_only_old_candidates():
    result = {
        "family": "calls_puts",
        "table": pd.DataFrame({
            "penalty": ["l1", "l1", "l1", "l1"],
            "solution_index": [0, 1, 2, 3],
            "alpha": [0.1, 0.2, 0.3, 0.4],
            "converged": [True, True, True, False],
            "n_options_active": [3, 2, 1, 3],
            "is_candidate_after_duplicates": [True, False, False, False],
        }),
        "profiles": pd.DataFrame({
            "penalty": ["l1"], "solution_index": [0], "profile": ["compromise"],
        }),
        "results": {"l1": {"solutions": [
            {"weights": np.array([1.0, 0.0])},
            {"weights": np.array([0.0, 1.0])},
            {"weights": np.array([0.0, 0.0])},
            {"weights": np.array([0.5, 0.5])},
        ]}},
    }
    A = np.column_stack((np.arange(80) / 80.0, np.ones(80)))
    b = A[:, 0] + np.linspace(-0.1, 0.2, 80)
    table = evaluate_alpha_tail_frontier(result, A, b, es_level=0.975)
    assert table["solution_index"].tolist() == [0, 1]
    assert table.loc[table["solution_index"].eq(0), "retained_profiles"].iloc[0] == "compromise"
    assert table["validation_tail_ess"].gt(0).all()
    assert table["pareto_rmse_es_options"].dtype == bool
    figure = plot_alpha_tail_frontier(table)
    assert "ES" in figure.axes[0].get_ylabel()


def test_alpha_tail_plot_keeps_dominated_candidates_in_background():
    table = pd.DataFrame({
        "penalty": ["l1", "l1", "l2"],
        "validation_rmse": [2.0, 3.0, 2.5],
        "validation_es": [7.0, 9.0, 6.0],
        "n_options_active": [3, 5, 4],
        "pareto_rmse_es_options": [True, False, True],
        "retained_profiles": ["compromise", np.nan, "performance"],
    })
    figure = plot_alpha_tail_frontier(table)
    axis = figure.axes[0]
    assert len(axis.collections) == 5  # fond gris, deux fronts et deux profils
    assert axis.collections[0].get_sizes().tolist() == [13]
    assert axis.collections[0].get_alpha() == 0.23
    labels = [item.get_text() for item in figure.legends[0].get_texts()]
    assert "Dominé · arrière-plan" in labels
    assert "Étoile · profil déjà retenu" in labels
    assert all("tous les alphas" not in label for label in labels)


def test_common_budget_profiles_keep_own_budget_failure_visible():
    table = pd.DataFrame({
        "alpha": [1.0, 2.0, 3.0, 4.0],
        "es_budget": [8.0, 9.0, 10.0, 11.0],
        "l1_ratio": [0.5] * 4,
        "converged": [True, True, True, False],
        "feasible_calibration": [True, True, False, True],
        "validation_budget_respected": [False, True, True, True],
        "validation_rmse": [1.0, 2.0, 3.0, 4.0],
        "validation_es": [9.0, 8.0, 7.0, 6.0],
    })
    profiles = select_budget_ceiling_profiles(table, ceilings=(5.0, 9.0, 11.0))
    assert set(profiles["alpha"]) == {1.0}
    assert set(profiles["risk_limit_es"]) == {9.0, 11.0}
    assert not profiles["validation_budget_respected"].any()
    flow = tail_budget_filter_flow(table, profiles)
    assert flow["remaining"].tolist() == [4, 3, 2, 2, 2, 2, 1]
    assert flow["removed_at_stage"].tolist() == [0, 1, 1, 0, 0, 0, 1]
    figure = plot_tail_budget_filter_flow(flow, title="Budget ES — filtres")
    assert figure.axes[0].get_xlabel()


def test_regularization_plot_separates_unfinished_states_and_retained_profiles():
    grid = pd.DataFrame({
        "family": ["full"] * 4,
        "penalty": ["l0"] * 4,
        "converged": [True, True, True, False],
        "alpha_relative": [1.0, 0.1, 0.02, 0.01],
        "validation_rmse": [4.0, 3.0, 2.8, 0.7],
        "n_options_active": [2, 4, 6, 20],
        "n_iterations": [5, 8, 10, 5000],
    })
    profiles = pd.DataFrame({
        "family": ["full"] * 3,
        "penalty": ["l0"] * 3,
        "profile": ["performance", "compromise", "parsimony"],
        "alpha_relative": [0.02, 0.1, 1.0],
    })
    figure = plot_regularization_grid(grid, profiles)
    for axis in figure.axes:
        assert all(0.01 not in line.get_xdata() for line in axis.lines)
        assert len(axis.collections) == 4  # une croix grise et trois étoiles
        assert {label.get_text() for label in axis.texts} == {"P", "C", "S"}
    assert any("5,000" in label.get_text() for label in figure.texts)
    assert any("Non convergé" in handle.get_label() for handle in figure.legends[0].legend_handles)


def test_seed_robustness_legend_excludes_unfinished_runs_from_boxplots():
    details = pd.DataFrame({
        "family": ["full"] * 4,
        "penalty": ["l1", "l1", "l0", "l0"],
        "profile": ["performance"] * 4,
        "seed": [1, 2, 1, 2],
        "converged": [True, False, False, False],
        "validation_rmse": [2.0, 9.0, 5.0, 8.0],
    })
    figure = plot_seed_robustness(details)
    axis = figure.axes[0]
    y_labels = [label.get_text() for label in axis.get_yticklabels()]
    assert any("L1 · Performance" == label for label in y_labels)
    assert any("L0 · Performance" == label for label in y_labels)
    assert all("convergés" not in label for label in y_labels)
    assert len(axis.patches) == 1  # aucune boîte pour L0 : zéro convergence
    assert len(axis.collections) == 3  # points bleus et croix grises séparés
    legend_labels = [item.get_text() for item in figure.legends[0].get_texts()]
    assert any("résultat provisoire" in label for label in legend_labels)
    assert any("médiane" in label for label in legend_labels)


def test_visuals_have_explicit_titles_and_axis_labels():
    schematic = plot_exploratory_benchmark_schematic()
    assert "Trois questions" in schematic._suptitle.get_text()
    assert any("Conditionnel" in label.get_text() for label in schematic.axes[0].texts)
    regularization = pd.DataFrame(
        {
            "family": ["calls_puts", "calls_puts", "full", "full"],
            "penalty": ["l1", "l1", "l1", "l1"],
            "converged": [True] * 4,
            "alpha_relative": [1.0, 0.1, 1.0, 0.1],
            "validation_rmse": [3.0, 2.0, 3.2, 1.9],
            "n_options_active": [2, 5, 3, 8],
        }
    )
    figure = plot_regularization_grid(regularization)
    assert figure._suptitle.get_text()
    assert all(axis.get_xlabel() and axis.get_ylabel() for axis in figure.axes)

    lambda_table = pd.DataFrame(
        {
            "lambda_es": [0.0, 0.1, 0.5],
            "validation_rmse": [2.0, 2.1, 2.5],
            "validation_es": [10.0, 8.0, 7.0],
            "converged": [True] * 3,
        }
    )
    budget_table = pd.DataFrame(
        {
            "es_budget": [10.0, 9.0, 8.0],
            "validation_rmse": [2.0, 2.2, 2.6],
            "validation_es": [9.5, 8.8, 8.1],
            "converged": [True] * 3,
            "feasible_calibration": [True] * 3,
        }
    )
    tail = {
        "lambda_table": lambda_table,
        "lambda_profiles": select_three_frontier_profiles(
            lambda_table, parameter_column="lambda_es"
        ),
        "budget_table": budget_table,
        "budget_profiles": select_three_frontier_profiles(
            budget_table,
            parameter_column="es_budget",
            feasible_column="feasible_calibration",
        ),
    }
    tail_figure = plot_tail_frontiers(tail)
    data_axes = [axis for axis in tail_figure.axes if axis.get_xlabel()]
    assert len(data_axes) == 2
    assert all(axis.get_title() and axis.get_ylabel() for axis in data_axes)

    budget_table["validation_budget_respected"] = False
    budget_table["validation_es"] = [20.0, 21.0, 22.0]
    tail["budget_profiles"] = select_three_frontier_profiles(
        budget_table, parameter_column="es_budget",
        feasible_columns=("feasible_calibration", "validation_budget_respected"),
    )
    empty_figure = plot_tail_frontiers(tail)
    budget_axis = [axis for axis in empty_figure.axes if "budget" in axis.get_title().lower()][0]
    assert any("Aucun candidat" in label.get_text() for label in budget_axis.texts)


def test_export_is_immutable_and_promotion_is_explicit(tmp_path):
    grid = HyperparameterGrid()
    configuration = _configuration()
    export = export_hyperparameter_study(
        output_root=tmp_path / "hyperparameters",
        run_mode="fast",
        configuration=configuration,
        grid=grid,
        tables={"selected profiles": pd.DataFrame({"profile": ["compromise"]})},
        figures={},
        selected_profiles={"calls_puts": {"profile": "compromise"}},
        policy_results={"calls_puts": {"status": "test object"}},
    )

    assert (export["run_dir"] / "selected_hyperparameters.json").exists()
    assert (export["run_dir"] / "selected_policy_results.pkl").exists()
    assert not (tmp_path / "config" / "selected_hyperparameters.json").exists()

    promoted = promote_hyperparameter_selection(
        source_run_dir=export["run_dir"],
        destination=tmp_path / "config" / "selected_hyperparameters.json",
        current_configuration=configuration,
    )
    assert promoted.exists()
    loaded = load_selected_hyperparameters(
        promoted,
        current_configuration=configuration,
    )
    assert loaded["test_status"] == "reserved_not_evaluated"
    assert loaded["configuration_fingerprint"] == configuration_fingerprint(configuration)

    with pytest.raises(ValueError, match="autre configuration"):
        load_selected_hyperparameters(
            promoted,
            current_configuration={**configuration, "families": ["full"]},
        )


def test_incomplete_run_cannot_be_promoted(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"completed": False}), encoding="utf-8"
    )
    (run_dir / "selected_hyperparameters.json").write_text(
        json.dumps({"configuration_fingerprint": configuration_fingerprint(_configuration())}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="incomplète"):
        promote_hyperparameter_selection(
            source_run_dir=run_dir,
            destination=tmp_path / "selected.json",
            current_configuration=_configuration(),
        )


def test_mode_specific_promotion_keeps_matching_policy_and_rejects_invalid_budget(tmp_path):
    configuration = _configuration()
    rows = [
        {"family": family, "profile": "compromise", "converged": True,
         "feasible_calibration": True, "validation_budget_respected": True}
        for family in configuration["families"]
    ]
    export = export_hyperparameter_study(
        output_root=tmp_path / "hyperparameters", run_mode="fast",
        configuration=configuration, grid=HyperparameterGrid(), tables={}, figures={},
        selected_profiles={"es_budget": rows}, policy_results={"status": "sample"},
    )
    target = tmp_path / "config" / "selected_hyperparameters_fast.json"
    promote_hyperparameter_selection(
        source_run_dir=export["run_dir"], destination=target,
        current_configuration=configuration,
    )
    assert (target.parent / "selected_policy_results_fast.pkl").is_file()
    assert load_selected_policy_results(
        target.parent / "selected_policy_results_fast.pkl",
        current_configuration=configuration,
    ) == {"status": "sample"}
    selection = json.loads(export["selection_path"].read_text(encoding="utf-8"))
    selection["selected_profiles"]["es_budget"][0]["validation_budget_respected"] = False
    export["selection_path"].write_text(json.dumps(selection), encoding="utf-8")
    with pytest.raises(ValueError, match="Budget ES non validé"):
        promote_hyperparameter_selection(
            source_run_dir=export["run_dir"], destination=target,
            current_configuration=configuration,
        )


def test_common_ceiling_promotion_does_not_confuse_own_fitting_budget(tmp_path):
    configuration = _configuration()
    rows = [
        {"family": family, "profile": "compromise", "converged": True,
         "feasible_calibration": True, "validation_budget_respected": False,
         "es_budget": 5.0, "risk_limit_es": 10.0, "validation_es": 8.0,
         "validation_cap_respected": True}
        for family in configuration["families"]
    ]
    export = export_hyperparameter_study(
        output_root=tmp_path / "hyperparameters", run_mode="fast",
        configuration=configuration, grid=HyperparameterGrid(), tables={}, figures={},
        selected_profiles={"es_budget": rows}, policy_results={"status": "sample"},
    )
    target = tmp_path / "config" / "selected_hyperparameters_fast.json"
    promote_hyperparameter_selection(
        source_run_dir=export["run_dir"], destination=target,
        current_configuration=configuration,
    )
    assert target.is_file()
    selection = json.loads(export["selection_path"].read_text(encoding="utf-8"))
    selection["selected_profiles"]["es_budget"][0]["validation_es"] = 11.0
    export["selection_path"].write_text(json.dumps(selection), encoding="utf-8")
    with pytest.raises(ValueError, match="Budget ES non validé"):
        promote_hyperparameter_selection(
            source_run_dir=export["run_dir"], destination=target,
            current_configuration=configuration,
        )

