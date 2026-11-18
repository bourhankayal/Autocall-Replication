"""One-off, checked split of historical price/mean-payoff experiments.

Historical one-off script for the initial price/mean-payoff split. Existing run
exports are never touched. Pathwise payoff was moved in a later migration by
``move_pathwise_payoff_to_exploration.py``; this script now exits without changes
when the exploratory notebook already exists.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / "notebooks" / "autocall_research.ipynb"
HYPER_PATH = ROOT / "notebooks" / "hyperparameter_research.ipynb"
EXPLORATORY_PATH = ROOT / "notebooks" / "exploratory_benchmarks.ipynb"


def source(text: str) -> list[str]:
    return (textwrap.dedent(text).strip("\n") + "\n").splitlines(keepends=True)


def markdown(text: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": source(text)}


def code(text: str) -> dict[str, object]:
    return {
        "cell_type": "code", "execution_count": None, "metadata": {},
        "outputs": [], "source": source(text),
    }


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"Expected exactly one occurrence of {old!r}; found {text.count(old)}")
    return text.replace(old, new, 1)


def copy_cell(cell: dict[str, object], *, heading: str | None = None) -> dict[str, object]:
    result = copy.deepcopy(cell)
    if heading is not None:
        original = "".join(result["source"])
        first_line, rest = original.split("\n", 1)
        if not first_line.startswith("#"):
            raise ValueError("Expected a markdown heading")
        result["source"] = (heading + "\n" + rest).splitlines(keepends=True)
    if result["cell_type"] == "code":
        # The moved code now uses its own alpha search. Old executed outputs
        # would falsely look like results from that new notebook.
        result["outputs"] = []
        result["execution_count"] = None
    return result


main = json.loads(MAIN_PATH.read_text(encoding="utf-8"))
hyper = json.loads(HYPER_PATH.read_text(encoding="utf-8"))
main_cells = main["cells"]
hyper_cells = hyper["cells"]
if EXPLORATORY_PATH.exists():
    # A failed manual Run All may have stored an error output after the split.
    # Remove only those stale tracebacks; preserve all successful cell outputs.
    cleaned = 0
    for cell in main_cells:
        if cell.get("cell_type") == "code":
            original_outputs = cell.get("outputs", [])
            cell["outputs"] = [
                output for output in original_outputs
                if output.get("output_type") != "error"
            ]
            cleaned += len(original_outputs) - len(cell["outputs"])
    if cleaned:
        MAIN_PATH.write_text(json.dumps(main, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Explorations déjà isolées ; {cleaned} sortie(s) d'erreur obsolète(s) retirée(s).")
    raise SystemExit(0)
assert "### 3.3 Benchmark sur l’espérance du payoff" in "".join(main_cells[23]["source"])
assert "## 1.1 Alphas des benchmarks exploratoires" in "".join(hyper_cells[6]["source"])

exploratory_alpha_search = code(
    r"""
    from autocall_replication.replication.mean_payoff import run_naive_benchmark_payoff
    from autocall_replication.replication.optimization import SolverConfig, solve_replication
    from autocall_replication.replication.hyperparameter_study import (
        HyperparameterGrid, exploratory_alpha_values,
        plot_exploratory_alpha_grid, select_exploratory_benchmark_alphas,
    )

    GRID = HyperparameterGrid()
    _benchmark_penalties = {
        "price_surface": ("l0", "l1", "l2", "elastic_net", "l1_2"),
        "mean_payoff": ("l2",),
    }
    _benchmark_functions = {
        "price_surface": run_naive_benchmark_price,
        "mean_payoff": run_naive_benchmark_payoff,
    }
    benchmark_alpha_rows = []
    for benchmark, penalties in _benchmark_penalties.items():
        for family in MAIN_FAMILIES:
            common = dict(
                product=prod, spot0=spot0, valuation_date=valuation_date,
                maturity_date=maturity_date, rate=rate,
                dividend_yield=dividend_yield, vol=vol, family=family,
                n_spots=15, n_paths=CFG["alpha_paths"], seed=42,
            )
            baseline = _benchmark_functions[benchmark](
                **common, penalty="l2", alpha=1e-4, solver="legacy",
            )
            matrix = np.asarray(baseline["A"], dtype=float)
            target = np.asarray(baseline["target_tensor"], dtype=float).reshape(-1)
            split = int(0.7 * len(baseline["dates"])) * len(baseline["spots"])
            train_A, train_b = matrix[:split], target[:split]
            validation_A, validation_b = matrix[split:], target[split:]
            for penalty in penalties:
                for alpha in exploratory_alpha_values(GRID, penalty):
                    fit = solve_replication(
                        train_A, train_b,
                        SolverConfig(
                            solver="proximal" if penalty == "l0" else "legacy",
                            penalty=penalty, alpha=float(alpha),
                        ),
                    )
                    benchmark_alpha_rows.append({
                        "benchmark": benchmark, "family": family,
                        "penalty": penalty, "alpha": float(alpha),
                        "converged": bool(fit.converged),
                        "validation_rmse": float(np.sqrt(np.mean(
                            (validation_b - validation_A @ fit.weights) ** 2
                        ))),
                        "n_options_active": int(np.count_nonzero(
                            np.abs(fit.weights[1:]) > 1e-6
                        )),
                    })
        print(f"Recherche d'alpha terminée : {benchmark}")

    benchmark_alpha_table = pd.DataFrame(benchmark_alpha_rows)
    benchmark_alpha_selected = select_exploratory_benchmark_alphas(benchmark_alpha_table)
    display(benchmark_alpha_selected[[
        "benchmark", "family", "penalty", "alpha",
        "validation_rmse", "n_options_active",
    ]])
    for benchmark in _benchmark_penalties:
        figure = plot_exploratory_alpha_grid(
            benchmark_alpha_table, benchmark_alpha_selected,
            benchmark=benchmark, nominal=prod.notional,
        )
        plt.show()

    def selected_benchmark_alpha(benchmark, family, penalty):
        matches = benchmark_alpha_selected.loc[
            benchmark_alpha_selected["benchmark"].eq(benchmark)
            & benchmark_alpha_selected["family"].eq(family)
            & benchmark_alpha_selected["penalty"].eq(penalty)
        ]
        if len(matches) != 1:
            if matches.empty and penalty == "l0":
                return None
            raise ValueError(
                f"Aucun alpha valide et unique pour {benchmark}/{family}/{penalty}."
            )
        return float(matches.iloc[0]["alpha"])
    """
)

exploratory_cells = [
    markdown(
        """
        # Explorations historiques : surface de prix et payoff moyen

        Ce notebook autonome conserve deux expériences de réplication qui ont aidé à
        comprendre le problème, mais **ne sélectionnent pas la politique finale**.
        Le notebook principal conserve la valorisation Monte-Carlo ponctuelle, le
        contrôle pathwise non conditionnel, le benchmark de cashflows statiques et
        la méthode conditionnelle. Les alphas ci-dessous ne sont valables que pour
        les objectifs exploratoires et ne sont jamais importés par le parcours final.

        Les anciens exports restent conservés dans `output/`. Les cellules déplacées
        sont livrées sans sorties d'exécution pour éviter d'afficher des résultats
        historiques comme s'ils provenaient de cette nouvelle recherche autonome.
        """
    ),
    copy_cell(main_cells[2]),
    code(
        """
        RUN_MODE = "fast"  # "report" augmente uniquement le volume numérique.
        SHOW_TECHNICAL_DETAILS = False
        RUN_FIGURES = {}
        EXECUTION_CONFIGS = {
            "fast": {"pricing_paths": 2_500, "surface_paths": 250,
                     "benchmark_paths": 250, "alpha_paths": 200},
            "report": {"pricing_paths": 20_000, "surface_paths": 2_000,
                       "benchmark_paths": 2_000, "alpha_paths": 2_000},
        }
        if RUN_MODE not in EXECUTION_CONFIGS:
            raise ValueError("RUN_MODE doit être 'fast' ou 'report'.")
        CFG = EXECUTION_CONFIGS[RUN_MODE]
        MAIN_FAMILIES = ("calls_puts", "full")
        FAMILY_LABELS = {"calls_puts": "Calls + Puts", "full": "Full (avec binaires)"}
        SOLVER = "legacy"
        display(pd.Series({"mode": RUN_MODE, **CFG}, name="configuration exploratoire"))
        """
    ),
    copy_cell(main_cells[4]),
    copy_cell(main_cells[5]),
]
contract_source = "".join(main_cells[6]["source"])
contract_source = contract_source.split(
    "from autocall_replication.replication.hyperparameter_study import (", 1
)[0].rstrip() + "\n"
exploratory_cells.append(code(contract_source))
exploratory_cells.extend(copy_cell(main_cells[i]) for i in range(11, 18))
exploratory_cells.extend([
    markdown(
        """
        ## Recherche d'alpha propre aux deux objectifs exploratoires

        Les alphas sont choisis sur une validation interne distincte de la calibration.
        Ils ne sont ni réutilisés par la politique conditionnelle ni promus vers le
        notebook principal. FAST et REPORT parcourent les mêmes valeurs d'alpha ;
        seul le nombre de trajectoires change.
        """
    ),
    exploratory_alpha_search,
    copy_cell(main_cells[19], heading="## 1. Réplication de la surface de prix"),
    copy_cell(main_cells[20]),
    copy_cell(main_cells[21]),
    copy_cell(main_cells[22]),
    copy_cell(main_cells[23], heading="## 2. Réplication du payoff moyen"),
    copy_cell(main_cells[24]),
    copy_cell(main_cells[25]),
])
exploratory = {
    "cells": exploratory_cells,
    "metadata": copy.deepcopy(main["metadata"]),
    "nbformat": main["nbformat"], "nbformat_minor": main["nbformat_minor"],
}

# Main notebook: keep the pathwise control and both temporal benchmarks.
main_cells[0]["source"] = source(
    """
    # Réplication conditionnelle d'un autocall par options vanilles

    Ce notebook présente la valorisation de référence, le contrôle pathwise non
    conditionnel, le benchmark de cashflows statiques et la politique conditionnelle.
    Les expériences historiques de surface de prix et de payoff moyen sont isolées
    dans `exploratory_benchmarks.ipynb` : leurs alphas ne pilotent pas cette étude.

    ## Progression en trois niveaux

    1. Dette autocall sans réplication : risque brut de la promesse au client.
    2. Réplication conditionnelle : exposition résiduelle `autocall − politique`.
    3. Couverture dynamique du résidu : étape future, non encore évaluée.

    Calls + Puts et Full (avec binaires) restent les deux familles comparées.
    Les détails techniques sont disponibles avec `SHOW_TECHNICAL_DETAILS = True`.
    """
)
config_source = "".join(main_cells[3]["source"])
for line in ('        "surface_paths": 200,\n', '        "surface_paths": 2_000,\n',
             '        "benchmark_paths": 200,\n', '        "benchmark_paths": 2_000,\n'):
    config_source = replace_once(config_source, line, "")
main_cells[3]["source"] = config_source.splitlines(keepends=True)
contract_source = "".join(main_cells[6]["source"])
contract_source = contract_source.replace("_exploratory_alpha_rows", "_benchmark_alpha_rows")
contract_source = replace_once(
    contract_source,
    '        if not matches and penalty == "l0":\n            return None\n',
    "",
)
contract_source = contract_source.replace("Alpha exploratoire", "Alpha du benchmark temporel")
main_cells[6]["source"] = contract_source.splitlines(keepends=True)
main_cells[12]["source"] = source(
    """
    from autocall_replication.monte_carlo import simulate_gbm_path, price_autocall_bs_mc
    from autocall_replication.replication.portfolio_diagnostics import (
        format_grouped_portfolio_metrics,
        format_portfolio_metrics,
    )
    """
)
main_cells[18]["source"] = source(
    """
    ## 3. Benchmarks de cashflows et contrôle pathwise

    Le contrôle pathwise non conditionnel vérifie les évaluations sur des trajectoires
    communes. Le benchmark de cashflows statiques donne un point de comparaison :
    il ne change pas de panier selon l'état du contrat. La méthode principale est
    conditionnelle à la date et à l'état contractuel. Une bonne approximation de
    prix moyen ne suffit pas à établir la capacité de paiement à chaque échéance.
    """
)
main_cells[26]["source"] = source(
    """
    ### 3.1 Contrôle pathwise non conditionnel

    Cette cellule vérifie que l'autocall et les instruments sont évalués sur les
    mêmes trajectoires. L'alpha L2 vient de la validation du notebook Hyperparameters.
    Le portefeuille obtenu ici n'est **pas** la politique finale : il n'adapte pas
    ses paniers aux états contractuels ni à la chronologie des cashflows.
    """
)
main_cells[29]["source"] = replace_once(
    "".join(main_cells[29]["source"]), "### 3.5 Cashflows dans le temps",
    "### 3.2 Benchmark de cashflows statiques dans le temps",
).splitlines(keepends=True)
main_cells[32]["source"] = replace_once(
    "".join(main_cells[32]["source"]), "### 3.6 Benchmark conditionnel",
    "### 3.3 Méthode principale : cashflows conditionnels",
).splitlines(keepends=True)
figure_source = "".join(main_cells[38]["source"])
for name in ("exploratory_alpha_price_surface", "exploratory_alpha_mean_payoff"):
    figure_source = replace_once(figure_source, f'    "{name}",\n', "")
main_cells[38]["source"] = figure_source.splitlines(keepends=True)
export_source = "".join(main_cells[62]["source"])
export_source = replace_once(export_source, '"contract_summary", "price_benchmark_table", ', '"contract_summary", ')
main_cells[62]["source"] = export_source.splitlines(keepends=True)
main["cells"] = [
    cell for index, cell in enumerate(main_cells)
    if index not in set(range(14, 18)) | set(range(19, 26))
]

# Hyperparameter notebook: keep only pathwise, static-cashflow and conditional
# preliminary alpha searches. Keep all unrelated executed outputs unchanged.
hyper_cells[6]["source"] = source(
    """
    ## 1.1 Alphas des contrôles et benchmarks temporels du notebook principal

    Les trois graphiques répondent à trois questions différentes. Chaque graphique
    compare Calls + Puts et Full, les deux familles d'instruments.

    - Pathwise payoff : un total actualisé par trajectoire ; un panier global.
    - Static cashflows : un paiement par date ; les mêmes poids à toutes les dates.
    - Conditional cashflows : un paiement par date et état ; des poids calibrés
      au départ pour chaque date/état, sans recalibration en direct.

    Les trois benchmarks utilisent la même grille d'alpha, de 10^-8 à 10^1.
    La surface de prix et le payoff moyen vivent uniquement dans
    `exploratory_benchmarks.ipynb`.

    L'alpha retenu est optimal uniquement sur cette grille et cette validation,
    sous les autres réglages fixés. Ce n'est pas un optimum conjoint ; ni le
    budget ES ni lambda ES n'interviennent dans cette section.

    Les anciennes colonnes `metrics_test` servent ici à la validation de sélection,
    et non à un test final indépendant. FAST et REPORT parcourent les mêmes alphas ;
    REPORT augmente seulement le nombre de trajectoires. Les faibles écarts en
    FAST ne constituent pas un classement définitif des pénalités.
    """
)
alpha_source = "".join(hyper_cells[7]["source"])
for line in (
    "from autocall_replication.replication.price_surface import run_naive_benchmark_price\n",
    "from autocall_replication.replication.mean_payoff import run_naive_benchmark_payoff\n",
    '    "price_surface": ("l0", "l1", "l2", "elastic_net", "l1_2"),\n',
    '    "mean_payoff": ("l2",),\n',
    '    "price_surface": run_naive_benchmark_price,\n',
    '    "mean_payoff": run_naive_benchmark_payoff,\n',
    '    if benchmark in ("price_surface", "mean_payoff"):\n'
    '        matrix = np.asarray(result["A"], dtype=float)\n'
    '        target = np.asarray(result["target_tensor"], dtype=float).reshape(-1)\n'
    '        split = int(0.7 * len(result["dates"])) * len(result["spots"])\n'
    '        return matrix[:split], target[:split], matrix[split:], target[split:]\n',
    '            if benchmark in ("price_surface", "mean_payoff"):\n'
    '                baseline_kwargs["n_spots"] = 15\n',
):
    alpha_source = replace_once(alpha_source, line, "")
hyper_cells[7]["source"] = alpha_source.splitlines(keepends=True)
hyper_cells[7]["outputs"] = []
hyper_cells[7]["execution_count"] = None

for path, notebook in (
    (EXPLORATORY_PATH, exploratory), (MAIN_PATH, main), (HYPER_PATH, hyper),
):
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path)
