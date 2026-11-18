import pandas as pd

from autocall_replication.research_presentation import build_report_views, make_report_view


def test_scalar_pricing_summary_has_a_report_view():
    view = make_report_view("pricing", {"actualized_price": 99.0, "std_error": 0.3, "n_paths": 250})
    assert view is not None
    assert len(view) == 1
    assert view.loc[0, "Trajectoires"] == 250


def test_report_view_is_compact_labelled_and_does_not_change_the_audit_table():
    complete = pd.DataFrame({
        "family": ["full"], "penalty": ["elastic_net"],
        "profile": ["performance"], "l1_ratio": [0.25],
        "alpha_relative": [0.123456], "validation_rmse": [2.123456],
        "n_options_active": [12], "solution_index": [4],
        "technical_trace": ["kept in full table"],
    })
    original = complete.copy(deep=True)
    view = make_report_view("profile_table", complete)
    assert view is not None
    assert "Famille" in view.columns
    assert "RMSE validation" in view.columns
    assert "technical_trace" not in view.columns
    assert view.loc[0, "RMSE validation"] == 2.1235
    pd.testing.assert_frame_equal(complete, original)


def test_report_exports_include_companions_without_replacing_full_tables():
    complete = pd.DataFrame({
        "family": ["full"], "penalty": ["l1"], "profile": ["compromise"],
        "validation_rmse": [3.0], "n_options_active": [10],
        "technical_trace": ["retained"],
    })
    tables = {"selected_regularisation_profiles": complete}
    views = build_report_views(tables)
    assert "report_selected_regularisation_profiles" in views
    assert "technical_trace" in tables["selected_regularisation_profiles"]
    assert "technical_trace" not in views["report_selected_regularisation_profiles"]


def test_stability_size_diagnostic_has_compact_report_view():
    diagnostic = pd.DataFrame({
        "family": ["full"], "penalty": ["l0"],
        "profiles_represented": ["performance, compromise, parsimony"],
        "base_n_options_active": [5], "n_options_active_mean": [73.2],
        "n_options_active_min": [4], "n_options_active_max": [92],
        "size_multiplier": [14.64],
        "support_pairwise_jaccard_median": [0.69],
        "n_converged": [10], "n_calibrations": [10],
        "technical_trace": ["kept in full table"],
    })
    view = make_report_view("stability_size_diagnostic", diagnostic)
    assert view is not None
    assert view.loc[0, "Options initiales"] == 5
    assert view.loc[0, "Options moyennes"] == 73.2
    assert view.loc[0, "Rapport moyen / initial"] == 14.64
    assert "technical_trace" not in view.columns


def test_report_tail_grid_excludes_diagnostic_high_lambda_candidate():
    complete = pd.DataFrame({
        "family": ["calls_puts", "calls_puts"],
        "penalty": ["elastic_net", "elastic_net"],
        "objective": ["penalized_es", "penalized_es"],
        "lambda_es": [0.5, 2.0],
        "lambda_selection_allowed": [True, False],
        "converged": [True, True], "feasible_calibration": [True, True],
        "validation_budget_respected": [True, True],
        "validation_es": [3.0, -18613.0],
    })
    view = make_report_view("tail_grid", complete)
    assert view is not None
    assert len(view) == 1
    assert view.loc[0, "Lambda ES"] == 0.5
    assert len(complete) == 2


def test_long_price_audit_report_keeps_compromise_and_preserves_full_rows():
    full = pd.DataFrame({
        "family": ["full", "full", "full"],
        "penalty": ["l1"] * 3,
        "profile": ["performance", "compromise", "parsimony"],
        "implementation": ["OTC central"] * 3,
        "price_type": ["commercial"] * 3,
        "price_pct_notional": [101.0, 102.0, 103.0],
        "cushion_vs_theoretical_pct_notional": [1.0, 2.0, 3.0],
    })
    compact = make_report_view("three_price_summary", full)
    assert compact is not None
    assert compact["Profil"].tolist() == ["compromise"]
    assert len(full) == 3


def test_funding_report_views_do_not_require_exploratory_otc_costs():
    paths = pd.DataFrame({
        "family": ["full", "full"],
        "penalty": ["l1", "l1"],
        "profile": ["compromise", "compromise"],
        "binary_mode": ["theoretical", "theoretical"],
        "terminal_pnl": [1.0, -1.0],
        "additional_capital_without_borrowing": [2.0, 4.0],
    })
    ledger = pd.DataFrame({
        "family": ["full", "full"],
        "penalty": ["l1", "l1"],
        "profile": ["compromise", "compromise"],
        "event_type": ["trade", "payment"],
        "cash_after_event": [-2.0, 1.0],
    })

    path_view = make_report_view("funding_path_summary", paths)
    ledger_view = make_report_view("funding_ledger", ledger)

    assert path_view is not None
    assert path_view.loc[0, "Trajectoires"] == 2
    assert "otc_cost_mean" not in path_view.columns
    assert ledger_view is not None
    assert -2.0 in ledger_view.iloc[0].values
    assert "otc_cost_sum" not in ledger_view.columns
