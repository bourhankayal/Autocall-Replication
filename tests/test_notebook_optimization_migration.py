import ast
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "autocall_research.ipynb"
HYPERPARAMETER_NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "hyperparameter_research.ipynb"
EXPLORATORY_NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "exploratory_benchmarks.ipynb"
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
        cls.hyperparameter_notebook = json.loads(
            HYPERPARAMETER_NOTEBOOK_PATH.read_text(encoding="utf-8")
        )
        cls.hyperparameter_code_sources = [
            "".join(cell.get("source", []))
            for cell in cls.hyperparameter_notebook["cells"]
            if cell.get("cell_type") == "code"
        ]
        cls.hyperparameter_code = "\n".join(cls.hyperparameter_code_sources)
        cls.hyperparameter_markdown = "\n".join(
            "".join(cell.get("source", []))
            for cell in cls.hyperparameter_notebook["cells"]
            if cell.get("cell_type") == "markdown"
        )
        cls.exploratory_notebook = json.loads(
            EXPLORATORY_NOTEBOOK_PATH.read_text(encoding="utf-8")
        )
        cls.exploratory_code = "\n".join(
            "".join(cell.get("source", []))
            for cell in cls.exploratory_notebook["cells"]
            if cell.get("cell_type") == "code"
        )
        cls.exploratory_markdown = "\n".join(
            "".join(cell.get("source", []))
            for cell in cls.exploratory_notebook["cells"]
            if cell.get("cell_type") == "markdown"
        )

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
        self.assertNotIn("run_naive_benchmark_price(", self.all_code)
        self.assertNotIn("run_naive_benchmark_payoff(", self.all_code)
        self.assertIn('benchmark_solver = "proximal" if penalty == "l0" else SOLVER', self.exploratory_code)

    def test_temporal_benchmark_alphas_are_imported_before_use(self):
        selection_index = next(
            index for index, source in enumerate(self.code_sources)
            if "def selected_benchmark_alpha" in source
        )
        first_benchmark_index = next(
            index for index, source in enumerate(self.code_sources)
            if "run_naive_benchmark_curve(" in source
        )
        selection_cell = self.code_sources[selection_index]
        self.assertLess(selection_index, first_benchmark_index)
        self.assertIn('f"selected_hyperparameters_{RUN_MODE}.json"', selection_cell)
        self.assertNotIn('_report_config_path', selection_cell)
        self.assertIn('if RUN_MODE == "sprint":', selection_cell)
        self.assertIn('f"selected_policy_results_{RUN_MODE}.pkl"', selection_cell)
        self.assertIn('selected_hyperparameters["run_mode"] != _selection_source_mode', selection_cell)
        self.assertIn("def selected_benchmark_alpha", selection_cell)
        self.assertIn("exploratory_benchmarks", selection_cell)
        for source in self.code_sources:
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if f"{node.func.id}(" not in BENCHMARK_FUNCTIONS:
                    continue
                alpha = next((item.value for item in node.keywords if item.arg == "alpha"), None)
                self.assertIsNotNone(alpha, node.func.id)
                self.assertNotIsInstance(alpha, ast.Constant, node.func.id)
        self.assertIn("regularization_filter_map", self.all_code)

    def test_fast_and_report_share_the_same_alpha_grid(self):
        self.assertIn("GRID = HyperparameterGrid()", self.hyperparameter_code)
        self.assertIn("n_alphas=GRID.n_alphas", self.hyperparameter_code)
        self.assertNotIn('"n_alphas": 9', self.hyperparameter_code)
        self.assertNotIn('"n_alphas": 25', self.hyperparameter_code)

    def test_elastic_net_three_pairs_are_selected_before_method_b_comparison(self):
        self.assertIn("ratios = GRID.elastic_net_l1_ratios", self.hyperparameter_code)
        self.assertIn("precomputed_dataset=shared_dataset", self.hyperparameter_code)
        self.assertIn("l1_ratio=selected_benchmark_ratio", self.all_code)
        self.assertLess(
            self.hyperparameter_code.index("selected_rho[family] = float("),
            self.hyperparameter_code.index("base_regularisation_results = {}"),
        )
        self.assertLess(
            self.hyperparameter_code.index("selected_rho_table = pd.concat(selected_rho_rows"),
            self.hyperparameter_code.index("rho_figure = plot_rho_grid("),
        )
        self.assertIn("selected=selected_rho_table", self.hyperparameter_code)
        self.assertIn("combine_conditional_elastic_net_profiles(", self.hyperparameter_code)
        rho_plot_cells = [
            source for source in self.hyperparameter_code_sources
            if "rho_figure = plot_rho_grid(" in source
        ]
        self.assertEqual(len(rho_plot_cells), 1)
        self.assertNotIn("run_regularisation_path(", rho_plot_cells[0])
        plot_cells = [
            source for source in self.hyperparameter_code_sources
            if "plot_exploratory_elastic_net_grid(" in source
        ]
        self.assertEqual(len(plot_cells), 1)
        self.assertNotIn("run_conditional_benchmark_curve(", plot_cells[0])
        general_index = next(
            index for index, source in enumerate(self.hyperparameter_code_sources)
            if "figure = plot_exploratory_alpha_grid(" in source
        )
        elastic_index = next(
            index for index, source in enumerate(self.hyperparameter_code_sources)
            if "elastic_figure = plot_exploratory_elastic_net_grid(" in source
        )
        self.assertLess(general_index, elastic_index)
        self.assertIn("selected_elastic_net_temporal", self.hyperparameter_code_sources[general_index])

    def test_notebook_displays_optimization_and_portfolio_metrics(self):
        self.assertNotIn("price_benchmark_table", self.all_code)
        self.assertNotIn("mean_payoff_table", self.all_code)
        self.assertIn("price_benchmark_table", self.exploratory_code)
        self.assertIn("mean_payoff_table", self.exploratory_code)
        self.assertNotIn("pathwise_benchmark_table", self.all_code)
        self.assertIn("pathwise_benchmark_table", self.exploratory_code)
        self.assertIn("decision_table", self.all_code)
        self.assertGreaterEqual(self.exploratory_code.count('["portfolio_metrics"]'), 1)
        self.assertIn("if SHOW_TECHNICAL_DETAILS:", self.all_code)

    def test_notebook_uses_readable_portfolio_diagnostics(self):
        self.assertIn("format_portfolio_metrics,", self.exploratory_code)
        self.assertIn("format_grouped_portfolio_metrics,", self.all_code)
        self.assertNotIn('display(pd.Series(res_calls["portfolio_metrics"]))', self.all_code)
        self.assertNotIn("Parcimonie du portefeuille :", self.all_code)
        self.assertGreaterEqual(self.exploratory_code.count("format_portfolio_metrics("), 1)
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
        for notebook_name, notebook in (
            ("main", self.notebook),
            ("hyperparameters", self.hyperparameter_notebook),
            ("exploratory", self.exploratory_notebook),
        ):
            for index, cell in enumerate(notebook["cells"]):
                if cell["cell_type"] == "code":
                    with self.subTest(notebook=notebook_name, code_cell=index):
                        ast.parse("".join(cell["source"]))

    def test_conditional_alpha_path_is_imported_and_documented(self):
        self.assertIn("load_selected_hyperparameters,", self.all_code)
        self.assertIn("load_selected_policy_results,", self.all_code)
        self.assertIn("Hyperparamètres optimisés et figés avant comparaison", self.all_markdown)
        self.assertNotIn("run_conditional_policy_penalty_comparison,", self.all_code)
        self.assertIn("run_conditional_policy_penalty_comparison,", self.hyperparameter_code)
        self.assertIn("Méthode B — sélection des hyperparamètres de la politique totale pathwise", self.hyperparameter_markdown)
        self.assertIn("Méthode A : ajustement conditionnel", self.all_markdown)
        self.assertIn("Comparaison diagnostique des deux objectifs", self.all_markdown)
        self.assertIn("compare_conditional_methods", self.all_code)
        self.assertIn('"static_cashflows": ("l0", "l2", "l1", "elastic_net")', self.hyperparameter_code)
        self.assertIn('"conditional_cashflows": ("l0", "l2", "l1", "elastic_net")', self.hyperparameter_code)
        self.assertIn("benchmark_l0_initialization_audit", self.hyperparameter_code)
        self.assertIn("solver=benchmark_solver", self.all_code)

    def test_conditional_alpha_path_uses_authorized_split_and_keeps_test_closed(self):
        alpha_cells = [
            source for source in self.hyperparameter_code_sources
            if "def run_regularisation_path" in source
        ]
        self.assertEqual(len(alpha_cells), 1)
        alpha_cell = alpha_cells[0]
        self.assertIn("train_fraction=0.60", alpha_cell)
        self.assertIn("validation_fraction=0.20", alpha_cell)
        self.assertIn("family=family", alpha_cell)
        self.assertIn("elastic_net_l1_ratio=float(rho)", alpha_cell)
        self.assertIn("ridge_min_alpha_ratio=GRID.ridge_min_alpha_ratio", alpha_cell)
        self.assertIn("ridge_max_alpha_ratio=GRID.ridge_max_alpha_ratio", alpha_cell)
        self.assertIn("min_candidate_options=2", alpha_cell)
        self.assertIn("max_candidate_options=10**9", alpha_cell)
        exploratory_cells = [
            source for source in self.hyperparameter_code_sources
            if "_benchmark_penalties =" in source
        ]
        self.assertEqual(len(exploratory_cells), 1)
        # The legacy benchmark APIs call their held-out validation metric
        # "metrics_test". It is used only for the preliminary alpha search;
        # the conditional-policy path never accesses a final test metric.
        self.assertIn('result["metrics_test"]', exploratory_cells[0])
        self.assertNotIn("metrics_test", alpha_cell)
        self.assertNotIn("test_rmse", self.hyperparameter_code)
        self.assertIn("Le test final reste fermé", self.hyperparameter_markdown)

    def test_pathwise_payoff_is_isolated_with_price_and_mean_payoff(self):
        self.assertIn("run_naive_benchmark_price(", self.exploratory_code)
        self.assertIn("run_naive_benchmark_payoff(", self.exploratory_code)
        self.assertIn("run_naive_benchmark_payoff_pathwise(", self.exploratory_code)
        self.assertIn("pathwise_alpha_selected", self.exploratory_code)
        self.assertIn("pathwise_alpha_table", self.exploratory_code)
        self.assertNotIn("run_naive_benchmark_payoff_pathwise(", self.all_code)
        self.assertNotIn('"pathwise_payoff": ("l2",)', self.hyperparameter_code)
        self.assertNotIn('selected_benchmark_alpha("pathwise_payoff"', self.all_code)
        self.assertNotIn('"exploratory_alpha_pathwise_payoff"', self.all_code)
        self.assertIn("selected_pathwise_alpha(family)", self.exploratory_code)
        self.assertNotIn('"price_surface": (', self.hyperparameter_code)
        self.assertNotIn('"mean_payoff": (', self.hyperparameter_code)

    def test_conditional_alpha_plots_treat_l2_as_non_sparse(self):
        self.assertIn("plot_regularization_grid", self.hyperparameter_code)
        self.assertIn("plot_rho_grid", self.hyperparameter_code)
        self.assertIn("plot_tail_frontiers", self.hyperparameter_code)
        self.assertIn('HYPERPARAMETER_FIGURES["alpha_grid"]', self.hyperparameter_code)
        self.assertIn('HYPERPARAMETER_FIGURES["elastic_net_rho_grid"]', self.hyperparameter_code)
        self.assertIn('HYPERPARAMETER_FIGURES[f"tail_frontiers_{family}_{penalty}"]', self.hyperparameter_code)
        self.assertIn("Chaque figure conserve son titre, ses axes, sa légende", self.all_markdown)

    def test_research_benchmarks_include_ols_delta_and_one_table(self):
        self.assertIn("if penalty == 'none'", self.all_code)
        self.assertIn('for penalty in ["none", "l0", "l2", "l1", "elastic_net"]', self.all_code)
        self.assertIn("evaluate_delta_hedge", self.all_code)
        self.assertIn("build_unified_benchmark_table", self.all_code)
        self.assertIn("unified_benchmark_table", self.all_code)
        self.assertIn("Table comparative unique", self.all_markdown)

    def test_profiles_flow_through_stability_risk_and_costs(self):
        self.assertNotIn("run_conditional_policy_profile_stability", self.all_code)
        self.assertIn("run_conditional_policy_profile_stability", self.hyperparameter_code)
        self.assertIn('"stability_calibrations": 10', self.hyperparameter_code)
        self.assertIn('n_calibrations=CFG["stability_calibrations"]', self.hyperparameter_code)
        self.assertIn('minimum_calibrations=2 if RUN_MODE == "sprint" else 10', self.hyperparameter_code)
        self.assertIn('min_valid_calibrations=int(np.ceil(0.9 * CFG["stability_calibrations"]))', self.hyperparameter_code)
        self.assertIn('"final_stability_calibrations": 30', self.hyperparameter_code)
        self.assertIn('n_calibrations=CFG["final_stability_calibrations"]', self.hyperparameter_code)
        self.assertIn('seeds=tuple(72000 + index', self.hyperparameter_code)
        self.assertIn('"importance_seeds": tuple(range(61000, 61030))', self.hyperparameter_code)
        self.assertIn("select_profiles_after_candidate_stability", self.hyperparameter_code)
        self.assertIn("load_selected_policy_results", self.all_code)
        self.assertIn("evaluate_conditional_policy_profile_risk", self.all_code)
        self.assertIn('"risk_paths": 20_000', self.all_code)
        self.assertIn('n_paths=CFG["risk_paths"]', self.all_code)
        self.assertNotIn("download_yfinance_option_snapshot", self.all_code)
        self.assertIn("download_yfinance_option_snapshot", self.exploratory_code)
        self.assertIn("estimate_conditional_policy_transaction_costs", self.exploratory_code)
        self.assertIn("OTC_COST_SCENARIOS", self.exploratory_code)
        self.assertIn("compare_transaction_cost_to_risk_reduction", self.exploratory_code)
        self.assertIn('risk_metric="es_975_reduction"', self.exploratory_code)
        self.assertIn("Quatre axes de stabilité importés", self.all_markdown)
        self.assertIn("Risque terminal de la politique conditionnelle", self.all_markdown)
        self.assertIn("Coûts bid-ask et données de marché", self.exploratory_markdown)

    def test_notebook_readability_structure_and_families(self):
        for section in range(11):
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
        self.assertIn("Surface de prix de l’autocall — date × spot", self.exploratory_code)
        self.assertIn("Calls + Puts contre Full", self.exploratory_code)
        self.assertIn("_imported_figure_names", self.all_code)
        self.assertIn("Expected Shortfall 97,5 %", self.all_code)
        self.assertIn("Erreur globale — réduction de la RMSE après réplication", self.all_code)
        self.assertIn("Risque extrême — multiplicateur de l’ES 97,5 % après réplication", self.all_code)
        self.assertIn('risk_penalty_order = ("l0", "l1", "l2", "elastic_net")', self.all_code)
        self.assertIn("es_975_residual_to_gross", self.all_code)
        self.assertIn("alpha_grid", self.all_code)
        self.assertIn("Lecture visuelle : apport des binaires", "\n".join(
            "".join(cell.get("source", []))
            for cell in self.exploratory_notebook["cells"]
            if cell.get("cell_type") == "markdown"
        ))
        self.assertIn("Lecture visuelle de l’exposition résiduelle", self.all_markdown)

    def test_three_risk_levels_and_units_are_explicit(self):
        self.assertIn("Progression en trois niveaux", self.all_markdown)
        self.assertIn("Pathwise payoff non conditionnel", self.all_markdown)
        self.assertIn("Niveau 3 — future couverture dynamique du résidu", self.exploratory_markdown)
        self.assertIn('risk_result["risk_summary"]', self.all_code)
        self.assertIn('risk_result["conditional_comparison"]', self.all_code)
        self.assertIn("rmse_relative_reduction", self.all_code)
        self.assertIn("residual_rmse_bps_notional", self.all_code)
        self.assertIn("### 8.1 Formules, deux traitements des binaires", self.all_markdown)
        self.assertIn("importlib.reload(_risk_module)", self.all_code)
        self.assertIn("importlib.reload(_transaction_costs_module)", self.exploratory_code)

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

    def test_main_applies_promoted_tail_and_importance_parameters(self):
        self.assertIn('selected_hyperparameters["selected_profiles"]["selected_importance_mixture"]', self.all_code)
        self.assertIn('selected_hyperparameters["selected_profiles"]["es_budget"]', self.all_code)
        self.assertIn('alpha_override=float(TAIL_SELECTED_GRID[family]["alpha"])', self.all_code)
        self.assertIn('l1_ratio_override=float(TAIL_SELECTED_GRID[family]["l1_ratio"])', self.all_code)
        self.assertIn('es_budget=TAIL_ES_BUDGETS[family]', self.all_code)
        self.assertIn('tilts=SELECTED_IMPORTANCE_MIXTURES[family]["tilts"]', self.all_code)
        self.assertNotIn('TAIL_ES_BUDGET_RATIO = 0.90', self.all_code)

    def test_funding_section_documents_formulas_and_binary_implementations(self):
        self.assertIn("Financement de la politique conditionnelle", self.all_markdown)
        self.assertIn("V_t^{\\mathrm{panier}}", self.all_markdown)
        self.assertIn("E_t^{\\mathrm{brute}}", self.all_markdown)
        self.assertIn("BC_t=", self.all_markdown)
        self.assertIn("BP_t=", self.all_markdown)
        self.assertIn("Full théorique", self.all_markdown)
        self.assertIn("Full transformé en spreads", self.all_markdown)
        self.assertIn("besoins de financement théoriques sous le modèle", self.all_markdown)
        self.assertNotIn("Full OTC", self.all_markdown)
        self.assertIn("evaluate_conditional_policy_funding", self.all_code)
        self.assertIn('"funding_paths": 2_000', self.all_code)
        self.assertNotIn('RUN_MARKET_COSTS = True', self.all_code)
        self.assertIn("additional_capital_p95_bps_notional", self.all_code)
        self.assertIn("terminal_pnl_mean_bps_notional", self.all_code)


if __name__ == "__main__":
    unittest.main()
