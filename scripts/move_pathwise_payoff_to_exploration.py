"""One-off notebook migration for the non-conditional Pathwise payoff experiment.

This deliberately leaves the pathwise library and previous run exports intact.
The existing notebooks are rewritten mechanically while unrelated cell outputs
are preserved. Re-running after success is a no-op.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "notebooks" / "autocall_research.ipynb"
HYPER = ROOT / "notebooks" / "hyperparameter_research.ipynb"
EXPLORATORY = ROOT / "notebooks" / "exploratory_benchmarks.ipynb"


def source(value: str) -> list[str]:
    return (textwrap.dedent(value).strip("\n") + "\n").splitlines(keepends=True)


def markdown(value: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": source(value)}


def code(value: str) -> dict[str, object]:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": source(value)}


def replace_once(value: str, old: str, new: str = "") -> str:
    if value.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r}, got {value.count(old)}")
    return value.replace(old, new, 1)


main = json.loads(MAIN.read_text(encoding="utf-8"))
hyper = json.loads(HYPER.read_text(encoding="utf-8"))
exploratory = json.loads(EXPLORATORY.read_text(encoding="utf-8"))
m = main["cells"]
h = hyper["cells"]
e = exploratory["cells"]
if any("Recherche d'alpha du contrôle Pathwise payoff" in "".join(c["source"]) for c in e):
    print("Pathwise payoff already isolated; no changes made.")
    raise SystemExit(0)
if not "Contrôle pathwise non conditionnel" in "".join(m[15]["source"]):
    raise ValueError("Unexpected main notebook layout")
if not "pathwise_payoff" in "".join(h[7]["source"]):
    raise ValueError("Unexpected hyperparameter notebook layout")

alpha_cell = code(r"""
    from autocall_replication.replication.pathwise_payoff import run_naive_benchmark_payoff_pathwise
    from autocall_replication.replication.optimization import SolverConfig, solve_replication
    from autocall_replication.replication.hyperparameter_study import (
        HyperparameterGrid, exploratory_alpha_values,
        plot_exploratory_alpha_grid, select_exploratory_benchmark_alphas,
    )

    pathwise_grid = HyperparameterGrid()
    pathwise_alpha_rows = []
    for family in MAIN_FAMILIES:
        baseline = run_naive_benchmark_payoff_pathwise(
            product=prod, spot0=spot0, valuation_date=valuation_date,
            maturity_date=maturity_date, rate=rate, dividend_yield=dividend_yield,
            vol=vol, family=family, n_paths=CFG["alpha_paths"],
            penalty="l2", alpha=1e-4, solver="legacy", seed=42,
        )
        split = int(baseline["split"])
        matrix = np.asarray(baseline["X"], dtype=float)
        target = np.asarray(baseline["y"], dtype=float)
        train_A, train_b = matrix[:split], target[:split]
        validation_A, validation_b = matrix[split:], target[split:]
        for alpha in exploratory_alpha_values(pathwise_grid, "l2"):
            fit = solve_replication(
                train_A, train_b,
                SolverConfig(solver="legacy", penalty="l2", alpha=float(alpha)),
            )
            pathwise_alpha_rows.append({
                "benchmark": "pathwise_payoff", "family": family,
                "penalty": "l2", "alpha": float(alpha),
                "converged": bool(fit.converged),
                "validation_rmse": float(np.sqrt(np.mean(
                    (validation_b - validation_A @ fit.weights) ** 2
                ))),
                "n_options_active": int(np.count_nonzero(np.abs(fit.weights[1:]) > 1e-6)),
            })

    pathwise_alpha_table = pd.DataFrame(pathwise_alpha_rows)
    pathwise_alpha_selected = select_exploratory_benchmark_alphas(pathwise_alpha_table)
    if len(pathwise_alpha_selected) != len(MAIN_FAMILIES):
        raise ValueError("Il faut un alpha pathwise L2 valide par famille.")
    display(pathwise_alpha_selected[[
        "benchmark", "family", "penalty", "alpha",
        "validation_rmse", "n_options_active",
    ]])
    plot_exploratory_alpha_grid(
        pathwise_alpha_table, pathwise_alpha_selected,
        benchmark="pathwise_payoff", nominal=prod.notional,
    )
    plt.show()

    def selected_pathwise_alpha(family):
        matches = pathwise_alpha_selected.loc[
            pathwise_alpha_selected["family"].eq(family)
            & pathwise_alpha_selected["penalty"].eq("l2")
        ]
        if len(matches) != 1:
            raise ValueError(f"Aucun alpha pathwise L2 valide et unique pour {family}.")
        return float(matches.iloc[0]["alpha"])
""")

pathwise_cells = [copy.deepcopy(cell) for cell in m[15:18]]
for cell in pathwise_cells:
    if cell["cell_type"] == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
pathwise_cells[0]["source"] = source("""
    ## 3. Contrôle Pathwise payoff non conditionnel

    Une trajectoire fournit ici un unique payoff total actualisé. Le panier est global :
    cette expérience ne garantit pas la reproduction des paiements à chaque date.
    L'alpha L2 est choisi dans la cellule précédente, uniquement pour ce contrôle
    exploratoire ; il n'est ni exporté ni utilisé par la politique conditionnelle.
""")
pathwise_run = "".join(pathwise_cells[2]["source"])
pathwise_cells[2]["source"] = replace_once(
    pathwise_run,
    'alpha=selected_benchmark_alpha("pathwise_payoff", family, "l2"),',
    "alpha=selected_pathwise_alpha(family),",
).splitlines(keepends=True)
e.extend([
    markdown("""
        ## Recherche d'alpha du contrôle Pathwise payoff

        Cette recherche L2 reste exploratoire. Pour chaque famille, on calibre les poids
        sur un ensemble de trajectoires, puis on choisit sur validation l'alpha donnant
        la plus faible RMSE parmi les solutions convergées avec au moins deux options.
        Les résultats ne sont pas promus vers le notebook principal.
    """),
    alpha_cell,
    *pathwise_cells,
])
e[0]["source"] = source("""
    # Explorations historiques : prix, payoff moyen et Pathwise payoff

    Ce notebook autonome conserve les expériences qui ont aidé à comprendre le
    problème mais ne sélectionnent pas la politique conditionnelle finale :
    surface de prix, payoff moyen et contrôle Pathwise payoff non conditionnel.
    Le notebook principal conserve la valorisation Monte-Carlo ponctuelle et les
    benchmarks de cashflows statiques et conditionnels. Les alphas exploratoires
    ne sont pas importés par le parcours final.

    Les anciens exports restent conservés dans `output/`. Les cellules déplacées
    sont livrées sans sorties d'exécution pour éviter de présenter des résultats
    historiques comme s'ils venaient de cette nouvelle exécution autonome.
""")
exploratory_cfg = "".join(e[2]["source"])
exploratory_cfg = replace_once(
    exploratory_cfg,
    '"benchmark_paths": 250, "alpha_paths": 200}',
    '"benchmark_paths": 250, "alpha_paths": 200, "pathwise_paths": 375}',
)
exploratory_cfg = replace_once(
    exploratory_cfg,
    '"benchmark_paths": 2_000, "alpha_paths": 2_000}',
    '"benchmark_paths": 2_000, "alpha_paths": 2_000, "pathwise_paths": 2_000}',
)
e[2]["source"] = exploratory_cfg.splitlines(keepends=True)

m[0]["source"] = source("""
    # Réplication conditionnelle d'un autocall par options vanilles

    Ce notebook présente la valorisation de référence, le benchmark de cashflows
    statiques et la politique conditionnelle. La surface de prix, le payoff moyen
    et le contrôle Pathwise payoff non conditionnel sont isolés dans
    `exploratory_benchmarks.ipynb` : leurs alphas ne pilotent pas cette étude.

    ## Progression en trois niveaux

    1. Dette autocall sans réplication : risque brut de la promesse au client.
    2. Réplication conditionnelle : exposition résiduelle `autocall − politique`.
    3. Couverture dynamique du résidu : étape future, non encore évaluée.

    Calls + Puts et Full (avec binaires) restent les deux familles comparées.
    Les détails techniques sont disponibles avec `SHOW_TECHNICAL_DETAILS = True`.
""")
main_cfg = "".join(m[3]["source"])
main_cfg = replace_once(main_cfg, '        "pathwise_paths": 375,\n')
main_cfg = replace_once(main_cfg, '        "pathwise_paths": 2_000,\n')
m[3]["source"] = main_cfg.splitlines(keepends=True)
m[3]["execution_count"] = None
m[3]["outputs"] = []
main_imports = "".join(m[12]["source"])
m[12]["source"] = replace_once(
    main_imports, "    format_portfolio_metrics,\n"
).splitlines(keepends=True)
m[14]["source"] = source("""
    ## 3. Benchmarks de cashflows statiques et conditionnels

    Le benchmark statique donne un point de comparaison : le panier reste identique
    à toutes les dates et dans tous les états du contrat. La méthode principale
    adapte la politique à la date et à l'état contractuel, avec tous les poids
    calibrés au départ. Le contrôle Pathwise payoff global, qui ne distingue pas
    les échéances, est conservé uniquement dans le notebook exploratoire.
""")
m[18]["source"] = replace_once(
    "".join(m[18]["source"]), "### 3.2 Benchmark", "### 3.1 Benchmark"
).splitlines(keepends=True)
m[21]["source"] = replace_once(
    "".join(m[21]["source"]), "### 3.3 Méthode", "### 3.2 Méthode"
).splitlines(keepends=True)
main_figures = "".join(m[27]["source"])
main_figures = replace_once(main_figures, '    "exploratory_alpha_pathwise_payoff",\n')
m[27]["source"] = main_figures.splitlines(keepends=True)
main["cells"] = [cell for index, cell in enumerate(m) if index not in {15, 16, 17}]

hyper_intro = """\
    ## 1.1 Alphas des benchmarks temporels du notebook principal

    Les deux graphiques répondent à deux questions différentes. Chaque graphique
    possède deux panneaux, Calls + Puts et Full : ce sont les familles d'instruments.

    | Benchmark | Cible sur une trajectoire simulée | Poids du portefeuille |
    |:--|:--|:--|
    | Static cashflows | Un paiement actualisé à chacune des dates d'observation. | Les mêmes poids pour toutes les dates et tous les scénarios. |
    | Conditional cashflows | Un paiement à chaque date, compte tenu de l'état vivant du contrat et, à maturité, de l'état de barrière si l'échantillon suffit. | Des poids différents par date/état, tous calibrés au départ : aucune recalibration en direct. |

    Pour chaque benchmark, famille et pénalité, on calibre sur des trajectoires
    d'apprentissage, puis on choisit l'alpha de RMSE minimale en validation parmi
    les solutions convergées comportant au moins deux options actives. La grille
    numérique commune va de $10^{-8}$ à $10^{1}$ ; l'intensité effective dépend
    toutefois de la pénalité. Prix, payoff moyen et Pathwise payoff non conditionnel
    sont étudiés uniquement dans `exploratory_benchmarks.ipynb`.

    L'alpha est optimal seulement sur cette grille et cette validation, sous les
    autres réglages fixés. Ni l'ES, ni son budget, ni lambda ES n'interviennent ici.
    Les anciennes colonnes `metrics_test` servent à la validation, pas à un test
    final indépendant. FAST et REPORT parcourent les mêmes alphas ; REPORT augmente
    seulement le nombre de trajectoires.
"""
h[6]["source"] = source(hyper_intro)
hyper_alpha = "".join(h[7]["source"])
hyper_alpha = replace_once(
    hyper_alpha,
    "from autocall_replication.replication.pathwise_payoff import run_naive_benchmark_payoff_pathwise\n",
)
hyper_alpha = replace_once(hyper_alpha, "    plot_exploratory_benchmark_schematic,\n")
hyper_alpha = replace_once(hyper_alpha, '    "pathwise_payoff": ("l2",),\n')
hyper_alpha = replace_once(hyper_alpha, '    "pathwise_payoff": run_naive_benchmark_payoff_pathwise,\n')
hyper_alpha = replace_once(
    hyper_alpha,
    'schematic = plot_exploratory_benchmark_schematic()\n'
    'HYPERPARAMETER_FIGURES["exploratory_benchmark_schematic"] = schematic\n'
    'plt.show()\n',
)
hyper_alpha = replace_once(
    hyper_alpha,
    '    if benchmark == "pathwise_payoff":\n'
    '        split = int(result["split"])\n'
    '        matrix = np.asarray(result["X"], dtype=float)\n'
    '        target = np.asarray(result["y"], dtype=float)\n'
    '        return matrix[:split], target[:split], matrix[split:], target[split:]\n',
)
h[7]["source"] = hyper_alpha.splitlines(keepends=True)
h[7]["execution_count"] = None
h[7]["outputs"] = []

for path, notebook in ((EXPLORATORY, exploratory), (MAIN, main), (HYPER, hyper)):
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path)
