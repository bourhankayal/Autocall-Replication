"""Replace in-notebook hyperparameter selection by a promoted-result loader."""

from __future__ import annotations

import json
from pathlib import Path
import re
import textwrap


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "notebooks" / "autocall_research.ipynb"


def source(text: str) -> list[str]:
    return (textwrap.dedent(text).strip("\n") + "\n").splitlines(keepends=True)


notebook = json.loads(PATH.read_text(encoding="utf-8"))
cells = notebook["cells"]
if not any(
    "run_naive_benchmark_price(" in "".join(cell.get("source", []))
    for cell in cells if cell.get("cell_type") == "code"
):
    raise SystemExit(
        "Migration historique déjà effectuée ; les benchmarks exploratoires sont "
        "désormais dans notebooks/exploratory_benchmarks.ipynb."
    )

_selection_bootstrap = source(
    r"""
    from autocall_replication.replication.hyperparameter_study import (
        load_selected_hyperparameters,
        product_configuration,
    )

    CURRENT_STUDY_CONFIGURATION = product_configuration(
        product=prod, spot0=spot0, valuation_date=valuation_date,
        contract_start_date=contract_start_date, maturity_date=maturity_date,
        rate=rate, dividend_yield=dividend_yield, volatility=vol,
        families=MAIN_FAMILIES,
    )
    _promoted_config_path = (
        _project_root / "config" / f"selected_hyperparameters_{RUN_MODE}.json"
    )
    _promoted_policy_path = (
        _project_root / "config" / f"selected_policy_results_{RUN_MODE}.pkl"
    )
    if not _promoted_config_path.is_file() or not _promoted_policy_path.is_file():
        raise FileNotFoundError(
            f"Aucune étude Hyperparameters {RUN_MODE.upper()} n'est promue pour ce contrat. "
            "Exécuter entièrement notebooks/hyperparameter_research.ipynb dans ce mode, "
            "vérifier les filtres et promouvoir la recherche avant de lancer le notebook principal."
        )
    selected_hyperparameters = load_selected_hyperparameters(
        _promoted_config_path,
        current_configuration=CURRENT_STUDY_CONFIGURATION,
    )
    if selected_hyperparameters["run_mode"] != RUN_MODE:
        raise ValueError("Le mode de la sélection ne correspond pas au mode du notebook principal.")
    _exploratory_alpha_rows = selected_hyperparameters["selected_profiles"].get(
        "exploratory_benchmarks", []
    )
    def selected_benchmark_alpha(benchmark, family, penalty):
        matches = [
            row for row in _exploratory_alpha_rows
            if row["benchmark"] == benchmark
            and row["family"] == family
            and row["penalty"] == penalty
        ]
        if len(matches) != 1:
            if not matches and penalty == "l0":
                return None
            raise ValueError(
                f"Alpha exploratoire absent ou ambigu pour {benchmark}/{family}/{penalty}. "
                "Relancer la recherche Hyperparameters complète dans le même mode."
            )
        value = float(matches[0]["alpha"])
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"Alpha exploratoire invalide : {benchmark}/{family}/{penalty}.")
        return value
    print("Hyperparamètres importés :", selected_hyperparameters["source_run"])
    """
)
_contract_cell = "".join(cells[6]["source"])
_bootstrap_start = "from autocall_replication.replication.hyperparameter_study import ("
if _bootstrap_start in _contract_cell:
    _contract_cell = _contract_cell.split(_bootstrap_start, 1)[0].rstrip("\n") + "\n\n"
else:
    _contract_cell = _contract_cell.rstrip("\n") + "\n\n"
cells[6]["source"] = (_contract_cell + "".join(_selection_bootstrap)).splitlines(keepends=True)

cells[35]["source"] = source(
    r"""
    ## 4. Hyperparamètres sélectionnés dans une étude externe

    ### 4.1 Séparation entre recherche et évaluation

    Les grilles d’alpha, de $\rho$, de $\lambda_{ES}$, de budgets d’ES et de mélanges
    d’importance sampling sont calculées dans `hyperparameter_research.ipynb`.

    Ce notebook principal ne choisit plus ses hyperparamètres. Il charge une recherche :

    - complète et explicitement promue ;
    - réalisée sur calibration et validation uniquement ;
    - compatible avec le contrat, le modèle et les familles actuels ;
    - accompagnée des politiques conditionnelles retenues et de leur audit multi-graines.

    Le test final demeure réservé. FAST ou REPORT ne modifie jamais le produit ; seul le volume
    numérique des expériences change.
    """
)

cells[36]["source"] = source(
    r"""
    from autocall_replication.replication.hyperparameter_study import (
        load_selected_policy_results,
    )
    from autocall_replication.replication.conditional_policy import (
        conditional_policy_cashflow_ledger,
        policy_information_audit,
        policy_profile_metrics,
    )

    stable_profile_results = load_selected_policy_results(
        _promoted_policy_path,
        current_configuration=CURRENT_STUDY_CONFIGURATION,
    )
    conditional_alpha_results = stable_profile_results

    _hyperparameter_run_dir = (
        _project_root / "output" / "hyperparameters" / "runs"
        / selected_hyperparameters["source_run"]
    )
    _hyperparameter_table_dir = _hyperparameter_run_dir / "tables"

    def _read_hyperparameter_table(name):
        path = _hyperparameter_table_dir / f"{name}.csv"
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    alpha_table = _read_hyperparameter_table("alpha_grid")
    profile_table = _read_hyperparameter_table("selected_regularisation_profiles")
    candidate_table = alpha_table.loc[alpha_table.get("is_candidate", False)].copy()
    candidate_policy_table = pd.DataFrame()
    profile_coverage = pd.DataFrame()
    duplicate_report = pd.DataFrame()
    l0_initialization_audit = _read_hyperparameter_table("l0_initialization_audit")
    chronology_audit = pd.concat(
        [policy_information_audit(result).assign(family=family)
         for family, result in stable_profile_results.items()],
        ignore_index=True,
    )

    print("Recherche d’hyperparamètres chargée :", selected_hyperparameters["source_run"])
    print("Mode ayant produit la sélection :", selected_hyperparameters["run_mode"])
    print("Statut du test final :", selected_hyperparameters["test_status"])
    print("Profils de régularisation importés :")
    display(profile_table)
    print("Audit chronologique — aucune information future autorisée :")
    display(chronology_audit.groupby("family")["chronology_valid"].agg(["count", "all"]))
    print("Métriques pathwise recalculables des politiques importées :")
    display(pd.concat(
        [policy_profile_metrics(result) for result in stable_profile_results.values()],
        ignore_index=True,
    ))
    """
)

cells[37]["source"] = source(
    r"""
    ### 4.2 Résultats visuels importés de la recherche

    Les graphiques suivants ne relancent aucune grille. Ils montrent les résultats qui ont conduit
    à la sélection actuellement promue : alpha par pénalité, grille Elastic Net $(\rho,\alpha)$,
    audit L0, robustesse multi-graines, frontières $\lambda_{ES}$ et budgets d’ES, puis choix du
    mélange d’importance sampling.

    Chaque figure conserve son titre, ses axes, sa légende et tous les points de grille nécessaires
    pour comprendre pourquoi les profils ont été retenus.
    """
)

cells[38]["source"] = source(
    r"""
    from IPython.display import Image as NotebookImage

    _imported_figure_names = (
        "exploratory_alpha_price_surface",
        "exploratory_alpha_mean_payoff",
        "exploratory_alpha_pathwise_payoff",
        "exploratory_alpha_static_cashflows",
        "exploratory_alpha_conditional_cashflows",
        "alpha_grid",
        "elastic_net_rho_grid",
        "l0_initialization_audit",
        "multi_seed_stability",
        "regularization_filter_map",
        "tail_frontiers_calls_puts",
        "tail_frontiers_full",
        "tail_budget_filters_calls_puts",
        "tail_budget_filters_full",
        "importance_sampling_grid",
    )
    for _figure_name in _imported_figure_names:
        _figure_path = _hyperparameter_run_dir / "figures" / f"{_figure_name}.png"
        if _figure_path.exists():
            print(_figure_name.replace("_", " ").title())
            display(NotebookImage(filename=str(_figure_path)))
        else:
            print(f"Figure non disponible dans la recherche promue : {_figure_name}")

    if SHOW_TECHNICAL_DETAILS:
        print("Tous les points de la grille alpha :")
        display(alpha_table)
        print("Audit complet L0 :")
        display(l0_initialization_audit)
    """
)

cells[39]["source"] = source(
    r"""
    ## 5. Quatre axes de stabilité importés

    Les profils ont été choisis dans le notebook Hyperparameters. Cette section importe
    l'audit sur dix recalibrations ; elle ne choisit aucun nouveau profil.

    Nous séparons la stabilité numérique, celle des instruments (Jaccard), celle du
    nombre d'options et celle de la couverture (RMSE et ES 97,5 %). La couverture
    est évaluée sur les mêmes trajectoires indépendantes pour tous les paniers ;
    elle ne sert ni à la sélection ni au test final. Le filtre actuel ne garantit
    que la convergence et une taille admissible. En FAST, l'ES reste exploratoire.
    Pour L0, l'écart des objectifs entre initialisations convergées renseigne sur
    les optima locaux sans certifier l'optimum global.
    """
)

cells[40]["source"] = source(
    r"""
    stability_profiles = {
        "summary": _read_hyperparameter_table("stability_summary"),
        "details": _read_hyperparameter_table("stability_details"),
        "selected_summary": _read_hyperparameter_table("selected_stability_summary"),
        "selected_details": _read_hyperparameter_table("selected_stability_details"),
    }
    _stable = stability_profiles["selected_summary"]
    if _stable.empty:
        print("Quatre axes indisponibles : relancer puis promouvoir Hyperparameters.")
    else:
        _identity = ["family", "penalty", "profile"]
        print(f"Évaluation commune : {int(_stable.iloc[0]['common_evaluation_n_paths'])} trajectoires ; graine {int(_stable.iloc[0]['common_evaluation_seed'])} ; test final réservé.")
        print("1/4 — Stabilité numérique")
        display(_stable[_identity + ["n_converged", "n_calibrations", "n_valid_active_counts"]])
        print("L0 — écart relatif des objectifs entre initialisations convergées")
        display(_stable.loc[_stable["penalty"].eq("l0"), ["family", "profile", "iterations_median", "l0_start_objective_gap_mean"]].round(4))
        print("2/4 — Stabilité des instruments")
        display(_stable[_identity + ["support_jaccard_median", "support_pairwise_jaccard_median", "relative_weight_distance_mean"]].round(3))
        print("3/4 — Stabilité du nombre d'options")
        display(_stable[_identity + ["base_n_options_active", "n_options_active_median", "n_options_active_min", "n_options_active_max"]].round(1))
        print("4/4 — Stabilité de couverture sur trajectoires indépendantes (% du nominal)")
        for _label, _columns in [("RMSE", ["base_common_evaluation_rmse", "common_evaluation_rmse_mean", "common_evaluation_rmse_std"]), ("ES 97,5 %", ["base_common_evaluation_es", "common_evaluation_es_mean", "common_evaluation_es_std"])]:
            _view = _stable[_identity + _columns].copy()
            _view[_columns] = _view[_columns] * 100.0 / prod.notional
            print(_label)
            display(_view.round(2))
    print("Profils effectivement disponibles pour les analyses de risque et de coût :")
    display(pd.concat(
        [result["profiles"] for result in stable_profile_results.values()],
        ignore_index=True,
    ))
    if SHOW_TECHNICAL_DETAILS:
        display(stability_profiles["summary"])
        display(stability_profiles["selected_details"])
        print("Détail de tous les candidats recalibrés par graine :")
        display(stability_profiles["details"])
    """
)


def replace_in_cell(index: int, old: str, new: str) -> None:
    current = "".join(cells[index]["source"])
    if new in current:
        return
    if old not in current:
        raise ValueError(f"Texte à migrer introuvable dans la cellule {index}: {old[:65]}")
    cells[index]["source"] = current.replace(old, new).splitlines(keepends=True)


_price_cell = "".join(cells[20]["source"])
if 'alpha=selected_benchmark_alpha("price_surface", family, penalty),' in _price_cell:
    replace_in_cell(
        20,
        'alpha=selected_benchmark_alpha("price_surface", family, penalty),',
        'alpha=benchmark_alpha,',
    )
elif 'alpha=benchmark_alpha,' not in _price_cell:
    replace_in_cell(
        20, "            solver=benchmark_solver,",
        '            alpha=benchmark_alpha,\n'
        '            seed=1042, solver=benchmark_solver,',
    )
replace_in_cell(
    20, "    for family in MAIN_FAMILIES:\n        result = run_naive_benchmark_price(",
    '    for family in MAIN_FAMILIES:\n'
    '        benchmark_alpha = selected_benchmark_alpha("price_surface", family, penalty)\n'
    '        if benchmark_alpha is None:\n'
    '            print(f"{FAMILY_LABELS[family]} / L0 : exclu, aucun alpha convergé avec au moins deux options actives.")\n'
    '            continue\n'
    '        result = run_naive_benchmark_price(',
)
replace_in_cell(
    25, '        alpha=1e-6,\n        solver=SOLVER,',
    '        alpha=selected_benchmark_alpha("mean_payoff", family, "l2"),\n'
    '        seed=1042, solver=SOLVER,',
)
replace_in_cell(
    28, '        alpha=1e-6,\n        solver=SOLVER,',
    '        alpha=selected_benchmark_alpha("pathwise_payoff", family, "l2"),\n'
    '        seed=1042, solver=SOLVER,',
)
replace_in_cell(
    31, 'penalty=penalty, alpha=1e-4, solver=SOLVER,',
    'penalty=penalty, alpha=selected_benchmark_alpha("static_cashflows", family, penalty),\n'
    '            seed=1042, solver=SOLVER,',
)
replace_in_cell(
    34, 'alpha=1e-4, train_frac=0.7, seed=42, split_final_by_barrier=True,',
    'alpha=selected_benchmark_alpha("conditional_cashflows", family, penalty),\n'
    '            train_frac=0.7, seed=1042, split_final_by_barrier=True,',
)
replace_in_cell(
    26, 'Elle utilise provisoirement `penalty="l2"` et `alpha=1e-6`.',
    'Elle utilise `penalty="l2"` et un alpha choisi dans le notebook Hyperparameters sur validation, puis importé ici.',
)


replace_in_cell(
    45,
    "La proposition est un mélange explicite de trois lois : 50 % de trajectoires standards, 30 % avec une inclinaison terminale de $-1$ écart-type et 20 % avec une inclinaison de $-2$ écarts-types. La composante standard évite d’abandonner les scénarios ordinaires. Les poids corrigent exactement cette surreprésentation : la mesure cible reste le GBM risque-neutre utilisé par le reste du notebook.",
    "Le mélange utilisé pour chaque famille est celui retenu dans la grille multi-graines du notebook Hyperparameters. Sa composition est affichée dans la cellule suivante. Les poids corrigent la surreprésentation des scénarios rares : la mesure cible reste le GBM risque-neutre utilisé par le reste du notebook.",
)
replace_in_cell(
    46,
    "    DEFAULT_IMPORTANCE_MIXTURE,\n    DEFAULT_IMPORTANCE_TILTS,\n",
    "",
)
_importance_header = (
    'SELECTED_IMPORTANCE_MIXTURES = selected_hyperparameters["selected_profiles"]["selected_importance_mixture"]\n'
    'for _family in MAIN_FAMILIES:\n'
    '    if _family not in SELECTED_IMPORTANCE_MIXTURES:\n'
    '        raise ValueError(f"Aucun mélange IS validé pour {_family}.")\n'
    'print("Mélanges IS sélectionnés sur les graines pilotes :")\n'
    'display(pd.DataFrame.from_dict(SELECTED_IMPORTANCE_MIXTURES, orient="index"))\n\n'
)
_importance_cell = "".join(cells[46]["source"])
_importance_cell = re.sub(
    r'(?:SELECTED_IMPORTANCE_MIXTURES = selected_hyperparameters\["selected_profiles"\]'
    r'\["selected_importance_mixture"\][\s\S]*?'
    r'display\(pd\.DataFrame\.from_dict\(SELECTED_IMPORTANCE_MIXTURES, orient="index"\)\)\n\n)+',
    '',
    _importance_cell,
)
if _importance_cell.count("importance_risk_results = {}") != 1:
    raise ValueError("La cellule IS doit contenir un unique bloc de résultats.")
cells[46]["source"] = _importance_cell.replace(
    "importance_risk_results = {}",
    _importance_header + "importance_risk_results = {}",
).splitlines(keepends=True)
replace_in_cell(
    46,
    "tilts=DEFAULT_IMPORTANCE_TILTS,\n            mixture_probabilities=DEFAULT_IMPORTANCE_MIXTURE,",
    "tilts=SELECTED_IMPORTANCE_MIXTURES[family][\"tilts\"],\n"
    "            mixture_probabilities=SELECTED_IMPORTANCE_MIXTURES[family][\"mixture_probabilities\"],",
)
replace_in_cell(
    46,
    '"déformations terminales": DEFAULT_IMPORTANCE_TILTS,\n            "probabilités du mélange": DEFAULT_IMPORTANCE_MIXTURE,',
    '"mélanges sélectionnés par famille": SELECTED_IMPORTANCE_MIXTURES,',
)
replace_in_cell(
    47,
    "Dans le notebook principal, $B_{ES}$ vaut provisoirement 90 % de l’ES de la calibration RMSE standard. Ce choix sert uniquement à vérifier le mécanisme ; la grille de budgets et la grille de $\\lambda_{ES}$ doivent être étudiées hors de ce notebook.",
    "Dans le notebook principal, le ratio $B_{ES}/ES_{\\mathrm{référence}}$ correspond au profil « compromis » sélectionné sur la grille de validation du notebook Hyperparameters, séparément pour chaque famille. Les profils priorité RMSE et priorité ES et la grille de $\\lambda_{ES}$ restent consultables dans ce notebook et dans son export.",
)
_previous_budget_loader = (
    'TAIL_ES_BUDGET_RATIOS = {\n'
    '    family: float(next(row["es_budget_ratio"] for row in SELECTED_BUDGET_PROFILES\n'
    '                       if row["family"] == family and row["profile"] == "compromise"))\n'
    '    for family in MAIN_FAMILIES\n'
    '}'
)
if _previous_budget_loader in "".join(cells[48]["source"]):
    replace_in_cell(
        48,
        _previous_budget_loader,
        'TAIL_SELECTED_GRID = {\n'
        '    family: next(row for row in SELECTED_BUDGET_PROFILES\n'
        '                 if row["family"] == family and row["profile"] == "compromise")\n'
        '    for family in MAIN_FAMILIES\n'
        '}\n'
        'TAIL_ES_BUDGET_RATIOS = {family: float(row["es_budget_ratio"])\n'
        '                         for family, row in TAIL_SELECTED_GRID.items()}',
    )
replace_in_cell(
    48,
    "TAIL_ES_BUDGET_RATIO = 0.90  # démonstration, sélection définitive hors notebook",
    "SELECTED_BUDGET_PROFILES = selected_hyperparameters[\"selected_profiles\"][\"es_budget\"]\n"
    "TAIL_SELECTED_GRID = {\n"
    "    family: next(row for row in SELECTED_BUDGET_PROFILES\n"
    "                 if row[\"family\"] == family and row[\"profile\"] == \"compromise\")\n"
    "    for family in MAIN_FAMILIES\n"
    "}\n"
    "TAIL_ES_BUDGET_RATIOS = {family: float(row[\"es_budget_ratio\"])\n"
    "                         for family, row in TAIL_SELECTED_GRID.items()}\n"
    "print(\"Budgets ES sélectionnés (% de l’ES de référence) :\")\n"
    "display(pd.Series(TAIL_ES_BUDGET_RATIOS).mul(100.0))",
)
replace_in_cell(
    48,
    "es_level=0.975, es_budget_ratio=TAIL_ES_BUDGET_RATIO,\n            tilts=DEFAULT_IMPORTANCE_TILTS,\n            mixture_probabilities=DEFAULT_IMPORTANCE_MIXTURE,",
    "es_level=0.975, es_budget_ratio=TAIL_ES_BUDGET_RATIOS[family],\n"
    "            tilts=SELECTED_IMPORTANCE_MIXTURES[family][\"tilts\"],\n"
    "            mixture_probabilities=SELECTED_IMPORTANCE_MIXTURES[family][\"mixture_probabilities\"],",
)
replace_in_cell(
    48,
    "penalty=penalty, profile=profile,\n            calibration_paths=CFG['tail_calibration_paths'],",
    "penalty=penalty, profile=profile,\n"
    "            alpha_override=float(TAIL_SELECTED_GRID[family][\"alpha\"]),\n"
    "            l1_ratio_override=float(TAIL_SELECTED_GRID[family][\"l1_ratio\"]),\n"
    "            calibration_paths=CFG['tail_calibration_paths'],",
)
replace_in_cell(
    48,
    "'family', 'calibration_sampling', 'risk_control', 'penalty',\n            'converged'",
    "'family', 'calibration_sampling', 'risk_control', 'penalty', 'alpha',\n            'converged'",
)
replace_in_cell(
    43,
    "Pour Full/L2, l’absence est explicitée : aucun portefeuille Ridge/Full ne passe les filtres sous la limite de 100 options actives.",
    "L’absence éventuelle d’une politique signifie qu’aucun candidat de cette famille et pénalité n’a satisfait les filtres et l’audit de stabilité de la recherche promue.",
)
replace_in_cell(
    62,
    '    "solver": SOLVER,\n',
    '    "solver": SOLVER,\n'
    '    "hyperparameter_selection": {\n'
    '        "source_run": selected_hyperparameters["source_run"],\n'
    '        "mode": selected_hyperparameters["run_mode"],\n'
    '        "configuration_fingerprint": selected_hyperparameters["configuration_fingerprint"],\n'
    '    },\n',
)
replace_in_cell(
    62,
    '        "alpha_selection": 42,',
    '        "exploratory_benchmark_evaluation": 1042,',
)

for index in (6, 20, 25, 28, 31, 34, 35, 36, 37, 38, 39, 40, 46, 48, 62):
    cells[index]["outputs"] = [] if cells[index]["cell_type"] == "code" else cells[index].get("outputs", [])
    if cells[index]["cell_type"] == "code":
        cells[index]["execution_count"] = None

PATH.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(PATH)
