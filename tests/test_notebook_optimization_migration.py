import ast
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "autocall_research.ipynb"
BENCHMARK_FUNCTIONS = (
    "run_naive_benchmark_price(",
    "run_naive_benchmark_payoff(",
    "run_naive_benchmark_payoff_pathwise(",
    "run_naive_benchmark_curve(",
    "run_conditional_benchmark_curve(",
)


class NotebookOptimizationMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        cls.code_sources = [
            "".join(cell.get("source", []))
            for cell in cls.notebook["cells"]
            if cell.get("cell_type") == "code"
        ]
        cls.all_code = "\n".join(cls.code_sources)
        cls.markdown_sources = [
            "".join(cell.get("source", []))
            for cell in cls.notebook["cells"]
            if cell.get("cell_type") == "markdown"
        ]
        cls.all_markdown = "\n".join(cls.markdown_sources)

    def test_notebook_does_not_import_fit_linear_directly(self):
        self.assertNotIn("fit_linear", self.all_code)

    def test_solver_is_explicit_on_every_benchmark_call(self):
        self.assertIn('SOLVER = "legacy"', self.all_code)
        calls = []
        for source in self.code_sources:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if f"{node.func.id}(" not in BENCHMARK_FUNCTIONS:
                    continue
                calls.append(node)

        self.assertEqual({call.func.id for call in calls}, {
            "run_naive_benchmark_price",
            "run_naive_benchmark_payoff",
            "run_naive_benchmark_payoff_pathwise",
            "run_naive_benchmark_curve",
            "run_conditional_benchmark_curve",
        })
        for call in calls:
            with self.subTest(call=call.func.id):
                solver = next(
                    (keyword.value for keyword in call.keywords if keyword.arg == "solver"),
                    None,
                )
                self.assertIsInstance(solver, ast.Name)
                self.assertIn(solver.id, {"SOLVER", "benchmark_solver"})
        self.assertIn('benchmark_solver = "proximal" if penalty == "l0" else SOLVER', self.all_code)

    def test_notebook_displays_optimization_and_portfolio_metrics(self):
        self.assertIn("price_benchmark_table", self.all_code)
        self.assertIn("mean_payoff_table", self.all_code)
        self.assertIn("pathwise_benchmark_table", self.all_code)
        self.assertIn("decision_table", self.all_code)
        self.assertGreaterEqual(self.all_code.count('["portfolio_metrics"]'), 8)
        self.assertIn("if SHOW_TECHNICAL_DETAILS:", self.all_code)

    def test_notebook_uses_readable_portfolio_diagnostics(self):
        self.assertIn("format_portfolio_metrics,", self.all_code)
        self.assertIn("portfolio_metrics_summary,", self.all_code)
        self.assertIn("format_grouped_portfolio_metrics,", self.all_code)
        self.assertNotIn('display(pd.Series(res_calls["portfolio_metrics"]))', self.all_code)
        self.assertNotIn("Parcimonie du portefeuille :", self.all_code)
        self.assertGreaterEqual(self.all_code.count("format_portfolio_metrics("), 3)
        self.assertGreaterEqual(self.all_code.count("format_grouped_portfolio_metrics("), 1)

    def test_notebook_contains_no_stored_error_output(self):
        errors = [
            output
            for cell in self.notebook["cells"]
            for output in cell.get("outputs", [])
            if output.get("output_type") == "error"
        ]
        self.assertEqual(errors, [])

    def test_every_notebook_code_cell_has_valid_python_syntax(self):
        for index, source in enumerate(self.code_sources):
            with self.subTest(code_cell=index):
                ast.parse(source)

    def test_conditional_alpha_path_is_imported_and_documented(self):
        self.assertIn("run_conditional_policy_penalty_comparison,", self.all_code)
        self.assertIn("Politique conditionnelle pathwise", self.all_markdown)
        self.assertIn("même pénalité", self.all_markdown)
        self.assertIn("fixé à 0,5", self.all_markdown)

    def test_conditional_alpha_path_uses_authorized_split_and_keeps_test_closed(self):
        alpha_cells = [
            source
            for source in self.code_sources
            if "conditional_alpha_results = {}" in source
        ]
        self.assertEqual(len(alpha_cells), 1)
        alpha_cell = alpha_cells[0]

        self.assertIn("train_fraction=0.60", alpha_cell)
        self.assertIn("validation_fraction=0.20", alpha_cell)
        self.assertIn("for family in MAIN_FAMILIES", alpha_cell)
        self.assertIn("family=family", alpha_cell)
        self.assertIn('penalties=("l0", "l1", "l2", "elastic_net")', alpha_cell)
        self.assertIn("elastic_net_l1_ratio=0.5", alpha_cell)
        self.assertIn("ridge_min_alpha_ratio=1e-4", alpha_cell)
        self.assertIn("ridge_max_alpha_ratio=1e2", alpha_cell)
        self.assertIn("min_candidate_options=2", alpha_cell)
        self.assertIn("max_candidate_options=100", alpha_cell)
        self.assertIn("test_status", alpha_cell)
        self.assertIn('result["candidates"]', alpha_cell)
        self.assertIn('result["candidate_policies"]', alpha_cell)
        self.assertIn('result["profiles"]', alpha_cell)
        self.assertIn('result["duplicate_report"]', alpha_cell)
        self.assertIn('result["profile_coverage"]', alpha_cell)
        self.assertIn('alpha_table["selection_status"]', alpha_cell)
        self.assertNotIn("metrics_test", alpha_cell)
        self.assertNotIn("test_rmse", alpha_cell)
        self.assertNotIn("L1_RATIOS", self.all_code)

    def test_conditional_alpha_plots_treat_l2_as_non_sparse(self):
        plot_cells = [
            source
            for source in self.code_sources
            if "penalty_labels =" in source
        ]
        self.assertEqual(len(plot_cells), 1)
        plot_cell = plot_cells[0]
        self.assertIn('penalty_table["converged"]', plot_cell)
        self.assertIn('sparse_penalties = ("l0", "l1", "elastic_net")', plot_cell)
        self.assertIn('penalty_table["is_candidate"]', plot_cell)
        self.assertIn('alpha_table["penalty"] == "l2"', plot_cell)
        self.assertIn('"sum_abs_option_weights"', plot_cell)
        self.assertIn('"max_abs_option_weight"', plot_cell)
        self.assertIn('"top_5_option_concentration"', plot_cell)
        self.assertIn('set_xscale("log")', plot_cell)
        self.assertIn('converged["alpha_relative"]', plot_cell)
        self.assertNotIn("log10", plot_cell)
        self.assertIn('groupby(["family", "penalty"]', plot_cell)
        self.assertIn('profile_markers = {"performance": "*", "compromise": "X", "parsimony": "P"}', plot_cell)
        self.assertIn("Couleur = pénalité · Marqueur = profil retenu", plot_cell)
        self.assertIn("Couleur = famille · Marqueur = profil retenu", plot_cell)
        self.assertIn("Solutions admissibles dominées", plot_cell)
        self.assertIn('dominated = eligible.loc[~eligible["is_candidate_pareto"]]', plot_cell)
        self.assertIn("Choix d’alpha — compromis entre erreur de validation et nombre d’options actives", plot_cell)
        self.assertIn("if SHOW_TECHNICAL_DETAILS:", plot_cell)
        self.assertNotIn(".annotate(", plot_cell)

    def test_profiles_flow_through_stability_risk_and_costs(self):
        self.assertIn("run_conditional_policy_profile_stability", self.all_code)
        self.assertIn('"stability_calibrations": 10', self.all_code)
        self.assertIn('n_calibrations=CFG["stability_calibrations"]', self.all_code)
        self.assertIn("min_valid_calibrations=9", self.all_code)
        self.assertIn("apply_stability_filter", self.all_code)
        self.assertIn("evaluate_conditional_policy_profile_risk", self.all_code)
        self.assertIn('"risk_paths": 20_000', self.all_code)
        self.assertIn('n_paths=CFG["risk_paths"]', self.all_code)
        self.assertIn("download_yfinance_option_snapshot", self.all_code)
        self.assertIn("estimate_conditional_policy_transaction_costs", self.all_code)
        self.assertIn("OTC_COST_SCENARIOS", self.all_code)
        self.assertIn("compare_transaction_cost_to_risk_reduction", self.all_code)
        self.assertIn('risk_metric="es_975_reduction"', self.all_code)
        self.assertIn("Aucun coût de marché n'est imputé silencieusement", self.all_code)
        self.assertIn("Stabilité des portefeuilles retenus", self.all_markdown)
        self.assertIn("Risque terminal de la politique conditionnelle", self.all_markdown)
        self.assertIn("Coûts bid-ask et données de marché", self.all_markdown)

    def test_notebook_readability_structure_and_families(self):
        for section in range(9):
            self.assertIn(f"## {section}.", self.all_markdown)
        self.assertIn('RUN_MODE = "fast"', self.all_code)
        self.assertIn('MAIN_FAMILIES = ("calls_puts", "full")', self.all_code)
        self.assertNotIn('MAIN_FAMILIES = ("calls",', self.all_code)

    def test_contract_variables_are_defined_only_in_contract_cell(self):
        protected_names = {
            "prod", "valuation_date", "contract_start_date", "maturity_date",
            "spot0", "rate", "dividend_yield", "vol",
        }
        defining_cells = set()
        for index, source in enumerate(self.code_sources):
            tree = ast.parse(source)
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in protected_names:
                        defining_cells.add(index)
        self.assertEqual(len(defining_cells), 1)

    def test_main_notebook_contains_decision_visuals(self):
        self.assertIn("Surface de prix de l’autocall — date × spot", self.all_code)
        self.assertIn("Calls + Puts contre Full", self.all_code)
        self.assertIn("profile_markers", self.all_code)
        self.assertIn("Expected Shortfall 97,5 %", self.all_code)
        self.assertIn("Erreur globale — réduction de la RMSE après réplication", self.all_code)
        self.assertIn("Risque extrême — multiplicateur de l’ES 97,5 % après réplication", self.all_code)
        self.assertIn('risk_penalty_order = ("l0", "l1", "l2", "elastic_net")', self.all_code)
        self.assertIn("es_975_residual_to_gross", self.all_code)
        self.assertIn("L2 dense : limite ≤ 100 options", self.all_code)
        self.assertIn("Lecture visuelle : apport des binaires", self.all_markdown)
        self.assertIn("Lecture visuelle de l’exposition résiduelle", self.all_markdown)

    def test_three_risk_levels_and_units_are_explicit(self):
        self.assertIn("Progression en trois niveaux", self.all_markdown)
        self.assertIn("Validation technique pathwise — alpha provisoire", self.all_markdown)
        self.assertIn("Niveau 3 — future couverture dynamique du résidu", self.all_markdown)
        self.assertIn('risk_result["risk_summary"]', self.all_code)
        self.assertIn('risk_result["conditional_comparison"]', self.all_code)
        self.assertIn("rmse_relative_reduction", self.all_code)
        self.assertIn("residual_rmse_bps_notional", self.all_code)
        self.assertIn("le financement théorique de 7.1 reste disponible", self.all_code)
        self.assertIn("importlib.reload(_risk_module)", self.all_code)
        self.assertIn("importlib.reload(_transaction_costs_module)", self.all_code)

    def test_importance_sampling_is_additive_and_documented(self):
        self.assertIn("Importance sampling — comparaison avec le Monte-Carlo standard", self.all_markdown)
        self.assertIn("À ne pas confondre", self.all_markdown)
        self.assertIn("ne recalcule ni alpha ni le portefeuille", self.all_markdown)
        self.assertIn("RUN_IMPORTANCE_SAMPLING = True", self.all_code)
        self.assertIn("evaluate_conditional_policy_profile_risk_importance", self.all_code)
        self.assertIn("compare_standard_and_importance_risk", self.all_code)
        self.assertIn("poids financiers", self.all_code)
        self.assertIn("figés avant les deux évaluations", self.all_code)
        self.assertIn("Estimation du même ES 97,5 % par deux méthodes — portefeuilles et alphas figés", self.all_code)
        self.assertIn("importance_precision_table", self.all_code)
        self.assertIn("Une valeur plus élevée ne signifie pas", self.all_code)
        self.assertIn('risk_colors = {"l0": "tab:purple"', self.all_code)
        self.assertIn('penalty_color = risk_colors.get(penalty, "tab:gray")', self.all_code)

    def test_funding_section_documents_formulas_and_binary_implementations(self):
        self.assertIn("Coût et financement de la politique conditionnelle", self.all_markdown)
        self.assertIn("V_t^{\\mathrm{panier}}", self.all_markdown)
        self.assertIn("E_t^{\\mathrm{brute}}", self.all_markdown)
        self.assertIn("BC_t=", self.all_markdown)
        self.assertIn("BP_t=", self.all_markdown)
        self.assertIn("Full théorique", self.all_markdown)
        self.assertIn("Full transformé en spreads", self.all_markdown)
        self.assertIn("Full OTC", self.all_markdown)
        self.assertIn("favorable, central et stressé", self.all_markdown)
        self.assertIn("evaluate_conditional_policy_funding", self.all_code)
        self.assertIn('"funding_paths": 2_000', self.all_code)
        self.assertIn('RUN_MARKET_COSTS = False', self.all_code)
        self.assertIn("additional_capital_p95_bps_notional", self.all_code)
        self.assertIn("terminal_pnl_mean_bps_notional", self.all_code)


if __name__ == "__main__":
    unittest.main()
