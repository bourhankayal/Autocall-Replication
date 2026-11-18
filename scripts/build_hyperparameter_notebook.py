"""Build the dedicated hyperparameter notebook from readable cell sources."""

from __future__ import annotations

import json
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "notebooks" / "hyperparameter_research.ipynb"


def lines(source: str) -> list[str]:
    source = textwrap.dedent(source).strip("\n") + "\n"
    return source.splitlines(keepends=True)


def markdown(source: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": lines(source)}


def code(source: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": lines(source),
    }


cells = [
    markdown(
        r"""
        # Recherche externe des hyperparamètres de réplication

        Ce notebook sélectionne les hyperparamètres **avant** l’étude finale. Il est volontairement
        séparé de `autocall_research.ipynb` afin que le notebook principal applique une politique
        déjà choisie au lieu de choisir et d’évaluer la méthode sur les mêmes résultats.

        Après la séparation des expériences historiques, les sorties déjà affichées dans une
        copie locale du notebook peuvent provenir de l'ancien parcours. Seul un nouveau Run All
        et son export horodaté donnent des résultats pour le périmètre actuel.

        ## Règle scientifique

        - Calibration et validation servent à choisir les hyperparamètres.
        - Le test final reste fermé : aucune métrique de test n’est calculée ici.
        - FAST et REPORT utilisent le même contrat et exactement les mêmes points de grille.
          Seuls les volumes de simulation et les répétitions changent.
        - Chaque comparaison entre méthodes utilise des trajectoires communes lorsque cela est
          possible afin de réduire le bruit de comparaison.
        - Chaque famille de résultats possède un tableau complet et un graphique lisible.
        - Les cellules privilégient une **synthèse à reporter** : colonnes essentielles,
          unités explicites et profils effectivement retenus. Les données intégrales
          restent dans les CSV d'audit ; mettre `SHOW_TECHNICAL_DETAILS = True` pour
          les afficher aussi dans le notebook. Les exports `report_*.csv` sont les
          versions courtes prêtes à intégrer au rapport. Les graphiques détaillés
          de la grille ES sont également exportés, même s'ils sont masqués dans la
          lecture normale au profit d'une vue de synthèse.
        """
    ),
    markdown(
        r"""
        ## 0. Préparation et mode d’exécution

        Le mode SPRINT sert uniquement à prévisualiser la structure, les tableaux et les
        figures : ses grilles et ses échantillons réduits ne permettent aucune conclusion.
        Le mode FAST vérifie le pipeline complet. Le mode REPORT produit l’étude destinée aux
        conclusions finales. Seule une recherche FAST ou REPORT inspectée peut être promue.
        En SPRINT, le notebook principal peut lire le dernier export SPRINT achevé pour
        afficher ses visuels, sans le promouvoir.
        """
    ),
    code(
        r"""
        from __future__ import annotations

        from datetime import datetime
        from pathlib import Path
        import sys

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        from IPython.display import display

        HYPERPARAMETER_RUN_STARTED_AT = datetime.now().astimezone()
        _search_bases = (
            Path.cwd(), Path.cwd() / "autocall-replication",
            *(candidate for parent in Path.cwd().parents
              for candidate in (parent, parent / "autocall-replication")),
        )
        _project_root = next(
            (candidate for candidate in _search_bases
             if (candidate / "pyproject.toml").is_file()
             and (candidate / "src" / "autocall_replication").is_dir()),
            None,
        )
        if _project_root is None:
            raise RuntimeError("Projet autocall-replication introuvable.")
        _src_path = str(_project_root / "src")
        if _src_path not in sys.path:
            sys.path.insert(0, _src_path)

        try:
            _ipython = get_ipython()
        except NameError:
            _ipython = None
        if _ipython is not None:
            _ipython.run_line_magic("load_ext", "autoreload")
            _ipython.run_line_magic("autoreload", "2")
        """
    ),
    code(
        r"""
        from autocall_replication.replication.hyperparameter_study import HyperparameterGrid

        RUN_MODE = "fast"  # "sprint" pour prévisualiser, "report" pour la campagne finale.
        PROMOTE_THIS_RUN = False  # Action volontaire après inspection complète des résultats.
        SHOW_TECHNICAL_DETAILS = False  # True : afficher aussi les tableaux d'audit intégraux.

        EXECUTION_CONFIGS = {
            "sprint": {
                "alpha_paths": 120,
                "stability_paths": 120,
                "stability_calibrations": 2,
                "final_stability_calibrations": 2,
                "tail_calibration_paths": 120,
                "tail_validation_paths": 200,
                "importance_paths": 150,
                "importance_seeds": (61000, 62000),
            },
            "fast": {
                "alpha_paths": 200,
                "stability_paths": 200,
                "stability_calibrations": 10,
                "final_stability_calibrations": 10,
                "tail_calibration_paths": 225,
                "tail_validation_paths": 625,
                "importance_paths": 625,
                "importance_seeds": (61000, 62000, 63000),
            },
            "report": {
                "alpha_paths": 2_000,
                "stability_paths": 2_000,
                "stability_calibrations": 10,
                "final_stability_calibrations": 30,
                "tail_calibration_paths": 2_000,
                "tail_validation_paths": 10_000,
                "importance_paths": 10_000,
                "importance_seeds": tuple(range(61000, 61030)),
            },
        }
        if RUN_MODE not in EXECUTION_CONFIGS:
            raise ValueError("RUN_MODE doit valoir 'sprint', 'fast' ou 'report'.")
        CFG = EXECUTION_CONFIGS[RUN_MODE]
        MAIN_FAMILIES = ("calls_puts", "full")
        FAMILY_LABELS = {"calls_puts": "Calls + Puts", "full": "Full (avec binaires)"}
        if RUN_MODE == "sprint":
            # Sous-grille de présentation seulement ; FAST/REPORT gardent la grille intégrale.
            _preview_alphas = tuple(10.0 ** power for power in range(-8, 9, 4))
            GRID = HyperparameterGrid(
                n_alphas=5,
                exploratory_alpha_sparse=_preview_alphas,
                exploratory_alpha_ridge=_preview_alphas,
                elastic_net_l1_ratios=(0.1, 0.5, 0.9),
                tail_alpha_ratios=(1.0, 0.1, 0.01),
                lambda_es_values=(0.0, 0.25, 1.0, 2.0),
                importance_candidates=HyperparameterGrid().importance_candidates[:2],
            )
        else:
            GRID = HyperparameterGrid()
        GRID.validate()
        HYPERPARAMETER_FIGURES = {}

        print("Mode :", RUN_MODE)
        display(pd.Series(CFG, name="configuration numérique"))
        print(
            "Effectif théorique dans la queue ES 97,5 % (avant éventuelle pondération) : "
            f"calibration {CFG['tail_calibration_paths'] * 0.025:.1f}, "
            f"validation {CFG['tail_validation_paths'] * 0.025:.1f}, "
            f"importance sampling {CFG['importance_paths'] * 0.025:.1f} par graine."
        )
        if RUN_MODE == "sprint":
            print("SPRINT = aperçu visuel uniquement : résultats, ES, profils et choix non validés.")
        elif RUN_MODE == "fast":
            print("FAST vérifie le pipeline ; ses estimations d'ES ne sont pas destinées à conclure.")
        display(pd.Series(GRID.to_dict(), name="grilles recherchées"))
        """
    ),
    markdown(
        r"""
        ## 1. Contrat et modèle — identiques au notebook principal

        Les hyperparamètres ne sont valables que pour cette configuration. Une empreinte numérique
        du contrat, du marché et des familles d’instruments empêchera leur utilisation accidentelle
        sur un autre produit.
        """
    ),
    code(
        r"""
        from autocall_replication.products import AutocallProduct
        from autocall_replication.replication.hyperparameter_study import (
            configuration_fingerprint,
            product_configuration,
        )

        prod = AutocallProduct(
            notional=100.0,
            autocall_strike=1.00,
            coupon_rate=0.02,
            down_barrier=0.70,
            observation_months=[3, 6, 9, 12],
        )
        valuation_date = pd.Timestamp("2026-06-20")
        contract_start_date = pd.offsets.BDay().rollforward(valuation_date.normalize())
        maturity_date = pd.offsets.BDay().rollforward(
            prod.build_observation_dates(contract_start_date)[-1].normalize()
        )
        spot0, rate, dividend_yield, vol = 100.0, 0.03, 0.01, 0.20

        STUDY_CONFIGURATION = product_configuration(
            product=prod, spot0=spot0, valuation_date=valuation_date,
            contract_start_date=contract_start_date, maturity_date=maturity_date,
            rate=rate, dividend_yield=dividend_yield, volatility=vol,
            families=MAIN_FAMILIES,
        )
        print("Empreinte de configuration :", configuration_fingerprint(STUDY_CONFIGURATION))
        display(pd.json_normalize(STUDY_CONFIGURATION))
        """
    ),
    markdown(
        r"""
        ## 1.1 Alphas des benchmarks temporels : objectif par échéance

        **Chaque benchmark a deux graphiques complémentaires.** Nous affichons d'abord
        les deux comparatifs généraux (Static puis Conditional), puis les deux graphiques
        Elastic Net seuls. Le comparatif montre L0, L1, L2 et **une seule courbe Elastic Net**,
        celle du ratio $\rho$ retenu. Le graphique Elastic Net séparé montre **tous les ratios
        testés** et repère d'une étoile le couple $(\rho,\alpha)$ retenu. Chaque graphique possède
        deux panneaux, Calls + Puts et Full : ce sont les *familles d'instruments*,
        pas deux mesures répétées du même benchmark.

        | Benchmark | Cible sur une trajectoire simulée | Poids du portefeuille |
        |:--|:--|:--|
        | Static cashflows | Un paiement actualisé à chacune des dates d'observation. | Les mêmes poids pour toutes les dates et tous les scénarios. |
        | Conditional cashflows | Un paiement à chaque date, compte tenu de l'état vivant du contrat et, à maturité, de l'état de barrière si l'échantillon suffit. | Des poids différents par date/état, tous calibrés au départ : aucune recalibration en direct. |

        Pour chaque benchmark, famille et pénalité, on calibre sur des trajectoires d'apprentissage,
        puis on choisit la RMSE minimale sur des trajectoires de validation parmi les
        solutions convergées comportant au moins deux options actives. L0, L1 et L2
        cherchent leur alpha ; Elastic Net cherche **conjointement** son couple
        $(\rho,\alpha)$ : la grille complète d'alpha est parcourue pour chaque ratio.
        Sur les graphiques, seules ces solutions admissibles forment les courbes colorées.
        Les points gris ronds donnent la RMSE calculée à l'arrêt d'un solveur **non
        convergé** : ce sont des diagnostics, pas des candidats sélectionnables. Les
        triangles gris ont convergé mais contiennent moins de deux options. Les
        courbes ne relient pas ces points exclus à l'étoile retenue.
        Les deux benchmarks partagent la même grille absolue d'alpha, de $10^{-8}$ à $10^{8}$.
        Un même alpha numérique ne représente toutefois pas la même intensité effective
        pour L0, L1, L2 et Elastic Net.
        La surface de prix, le payoff moyen et le contrôle Pathwise payoff non conditionnel
        vivent uniquement dans `exploratory_benchmarks.ipynb`.

        **Portée des valeurs retenues.** Il s'agit d'optima *sur ces grilles et sur
        cette validation*, conditionnellement aux autres réglages fixés pour ce benchmark.
        Ce n'est ni un optimum conjoint de tous les hyperparamètres, ni une garantie de
        performance sur de nouvelles données. Le risque ES, son budget et $\lambda_{ES}$
        n'entrent pas dans l'objectif de cette section.

        **Que signifie « Elastic Net retenu » dans le comparatif ?** Pour chaque
        benchmark et famille, nous examinons tous les couples $(\rho,\alpha)$ testés
        sur les **mêmes trajectoires**. Nous écartons les ajustements non convergés,
        les erreurs non finies et les paniers de moins de deux options actives.
        Parmi les couples restants, nous prenons celui de **RMSE de validation la plus basse**.
        À égalité, nous préférons moins d'options actives, puis le plus petit alpha et le
        plus petit $\rho$. Le graphique général montre la courbe complète en alpha pour
        ce seul $\rho$ ; l'étoile indique l'alpha sélectionné. Ce choix n'optimise ni l'ES,
        ni les coûts, ni la stabilité multi-graines : « retenu » signifie seulement
        **meilleur selon cette règle de validation**. S'il n'existe aucun couple admissible,
        aucune courbe Elastic Net n'est présentée comme gagnante et l'absence est signalée.

        **Maillage de $\rho$.** Le REPORT précédent retenait souvent $\rho=0{,}9$,
        qui était la borne supérieure de sa grille. FAST et REPORT conservent
        tous les anciens points et utilisent désormais un pas de $0{,}025$
        entre $0{,}75$ et $0{,}975$, puis $0{,}99$ : quinze ratios au total.
        Cela vérifie si un peu de L2 apporte vraiment
        quelque chose près du L1 pur ; $\rho=1$ n'est pas dupliqué ici, puisque
        L1 fait déjà l'objet d'une recherche séparée. Une grande valeur de
        $\rho$ indique une dominante L1 dans la formule, mais ne donne pas à
        elle seule la part quantitative de L1 dans la pénalité effective.
        Le run REPORT déjà promu conserve sa grille et ses choix d'origine.
        Cette finesse augmente le nombre d'ajustements Elastic Net, notamment
        dans la grille ES ; elle ne doit pas être confondue avec un simple
        raffinement graphique sans coût de calcul.

        **L0 est inclus dans les deux benchmarks temporels.** Comme son objectif
        est non convexe, chaque ajustement compare un démarrage à froid et un
        démarrage issu de Ridge ; si leurs résultats diffèrent ou ne convergent
        pas, un démarrage aléatoire reproductible est essayé. Le meilleur
        objectif *d'apprentissage* parmi les solutions convergées est conservé ;
        la validation sert ensuite uniquement à choisir l'alpha. L'audit détaille
        tous les démarrages. Aucun optimum global n'est garanti ; un couple sans
        alpha convergé avec au moins deux options actives reste explicitement absent.

        **Méthode A (par échéance).** Le benchmark conditionnel ajuste séparément
        chaque paiement. Son alpha sert seulement à la section 3.2 du notebook
        principal ; il ne règle pas la politique globale. À maturité, le panier
        peut dépendre de l'état de barrière constaté le jour même : ce diagnostic
        bénéficie d'une information non disponible avant le règlement.

        Les anciennes colonnes `metrics_test` servent ici à la validation de sélection,
        et non à un test final indépendant. FAST et REPORT parcourent les mêmes alphas ;
        REPORT augmente seulement le nombre de trajectoires. Les faibles écarts observés en
        FAST ne constituent pas un classement définitif des pénalités.

        **Pourquoi une grille aussi large ?** Elle vérifie aussi le régime de
        régularisation extrême ; les grandes valeurs peuvent
        annuler presque toutes les options et sont alors exclues par le critère
        d'au moins deux options actives. Un même alpha absolu n'a pas la même
        intensité économique pour L0, L1, L2 et Elastic Net. Les graphiques
        montrent le balayage complet, pas une échelle de force comparable entre normes.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.static_cashflows import run_naive_benchmark_curve
        from autocall_replication.replication.semi_static import run_conditional_benchmark_curve
        from autocall_replication.replication.optimization import SolverConfig, solve_l0_multistart, solve_replication
        from autocall_replication.replication.hyperparameter_study import (
            exploratory_alpha_values,
            select_exploratory_benchmark_alphas,
        )

        _benchmark_penalties = {
            "static_cashflows": ("l0", "l2", "l1", "elastic_net"),
            "conditional_cashflows": ("l0", "l2", "l1", "elastic_net"),
        }
        _benchmark_functions = {
            "static_cashflows": run_naive_benchmark_curve,
            "conditional_cashflows": run_conditional_benchmark_curve,
        }

        def _shared_validation_design(benchmark, result):
            # Reuse identical simulated paths across alpha candidates.
            if benchmark == "static_cashflows":
                train = result["train_set"]
                validation = result["test_set"]
                train_A = np.vstack([item["X_curve"] for item in train])
                train_b = np.concatenate([item["y_curve"] for item in train])
                validation_A = np.vstack([item["X_curve"] for item in validation])
                validation_b = np.concatenate([item["y_curve"] for item in validation])
                scale = np.sqrt(np.mean(train_A**2, axis=0))
                scale[scale < 1e-12] = 1.0
                scale[0] = 1.0
                return train_A / scale, train_b, validation_A / scale, validation_b
            raise ValueError(f"Benchmark non partageable : {benchmark}")

        benchmark_alpha_rows = []
        benchmark_l0_audit_rows = []
        for benchmark, penalties in _benchmark_penalties.items():
            for family in MAIN_FAMILIES:
                common = dict(
                    product=prod, spot0=spot0, valuation_date=valuation_date,
                    maturity_date=maturity_date, rate=rate,
                    dividend_yield=dividend_yield, vol=vol,
                    family=family, n_paths=CFG["alpha_paths"], seed=42,
                )
                if benchmark == "conditional_cashflows":
                    baseline = run_conditional_benchmark_curve(
                        **common, penalty="l2", alpha=1e-4, solver="legacy",
                        min_state_paths=20, split_final_by_barrier=True,
                    )
                    shared_dataset = baseline["dataset"]
                else:
                    baseline_kwargs = dict(common, penalty="l2", alpha=1e-4, solver="legacy")
                    baseline = _benchmark_functions[benchmark](**baseline_kwargs)
                    train_A, train_b, validation_A, validation_b = _shared_validation_design(
                        benchmark, baseline
                    )
                for penalty in penalties:
                    ratios = GRID.elastic_net_l1_ratios if penalty == "elastic_net" else (0.5,)
                    for rho in ratios:
                      for alpha in exploratory_alpha_values(GRID, penalty):
                        if benchmark == "conditional_cashflows":
                            result = run_conditional_benchmark_curve(
                                **common, penalty=penalty, alpha=float(alpha),
                                l1_ratio=float(rho), precomputed_dataset=shared_dataset,
                                solver="proximal" if penalty == "l0" else "legacy",
                                min_state_paths=20,
                                split_final_by_barrier=True,
                            )
                            if penalty == "l0":
                                benchmark_l0_audit_rows.extend(
                                    result["l0_initialization_audit"].assign(
                                        benchmark=benchmark, family=family,
                                    ).to_dict(orient="records")
                                )
                            converged = bool(result["optimization"]["converged"].all())
                            validation_rmse = result["metrics_test"].get("rmse", np.nan)
                            weights = result["weights"]
                            n_active = int(weights.loc[
                                weights["kind"].ne("Cash") & weights["weight"].abs().gt(1e-6),
                                "name",
                            ].nunique())
                        else:
                            fit_config = SolverConfig(
                                solver="proximal" if penalty == "l0" else "legacy",
                                penalty=penalty, alpha=float(alpha), l1_ratio=float(rho),
                            )
                            if penalty == "l0":
                                fit, audit = solve_l0_multistart(
                                    train_A, train_b, fit_config, seed=7042,
                                )
                                benchmark_l0_audit_rows.extend([
                                    {"benchmark": benchmark, "family": family,
                                     "alpha": float(alpha), **row}
                                    for row in audit
                                ])
                            else:
                                fit = solve_replication(train_A, train_b, fit_config)
                            converged = bool(fit.converged)
                            validation_rmse = float(np.sqrt(np.mean(
                                (validation_b - validation_A @ fit.weights) ** 2
                            )))
                            n_active = int(np.count_nonzero(np.abs(fit.weights[1:]) > 1e-6))
                        benchmark_alpha_rows.append({
                            "benchmark": benchmark, "family": family,
                            "penalty": penalty, "alpha": float(alpha),
                            "l1_ratio": float(rho) if penalty == "elastic_net" else None,
                            "converged": converged,
                            "validation_rmse": validation_rmse,
                            "n_options_active": n_active,
                        })
            print(f"Grille exploratoire terminée : {benchmark}")

        benchmark_alpha_table = pd.DataFrame(benchmark_alpha_rows)
        benchmark_l0_initialization_audit = pd.DataFrame(benchmark_l0_audit_rows)
        benchmark_alpha_selected = select_exploratory_benchmark_alphas(benchmark_alpha_table)
        benchmark_alpha_missing = pd.DataFrame([
            {"benchmark": benchmark, "family": family, "penalty": penalty,
             "reason": "aucun alpha convergé avec au moins deux options actives"}
            for benchmark, penalties in _benchmark_penalties.items()
            for family in MAIN_FAMILIES for penalty in penalties
            if benchmark_alpha_selected.loc[
                benchmark_alpha_selected["benchmark"].eq(benchmark)
                & benchmark_alpha_selected["family"].eq(family)
                & benchmark_alpha_selected["penalty"].eq(penalty)
            ].empty
        ])
        if not benchmark_alpha_missing.empty:
            print("Combinaisons explicitement exclues :")
            display(benchmark_alpha_missing)
        if not benchmark_alpha_missing.empty and benchmark_alpha_missing["penalty"].ne("l0").any():
            raise ValueError(
                "Un benchmark non-L0 n'a aucun alpha valide. Examiner la grille avant promotion."
            )
        benchmark_alpha_report_table = benchmark_alpha_selected[[
            "benchmark", "family", "penalty", "l1_ratio", "alpha",
            "validation_rmse", "n_options_active",
        ]].copy()
        benchmark_alpha_report_table["validation_rmse_pct_notional"] = (
            benchmark_alpha_report_table.pop("validation_rmse") * 100.0 / prod.notional
        )
        print("À reporter — alpha retenu par objectif, famille et pénalité :")
        display(benchmark_alpha_report_table.rename(columns={
            "benchmark": "Objectif", "family": "Famille", "penalty": "Pénalité",
            "l1_ratio": "Ratio L1 (rho)", "alpha": "Alpha retenu",
            "n_options_active": "Options actives",
            "validation_rmse_pct_notional": "RMSE validation (% nominal)",
        }).round(4))
        print("Audit L0 (détail intégral conservé dans l'export) :")
        display(benchmark_l0_initialization_audit.groupby(
            ["benchmark", "family"], as_index=False,
        ).agg(
            n_initializations=("selected", "size"),
            n_selected=("selected", "sum"),
            n_converged=("converged", "sum"),
            random_trigger_rate=("random_multistart_triggered", "mean"),
        ))
        """
    ),
    markdown(
        r"""
        ### 1.1 — Comparaisons générales des pénalités

        Cette cellule ne recalcule aucun portefeuille. Les deux graphiques suivants
        comparent L0, L1, L2 et Elastic Net au seul $\rho$ retenu, d'abord pour
        Static cashflows, puis pour Conditional cashflows. Le tableau ci-dessous rend
        explicite le couple Elastic Net affiché dans chaque panneau.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.hyperparameter_study import (
            plot_exploratory_alpha_grid,
        )

        selected_elastic_net_temporal = benchmark_alpha_selected.loc[
            benchmark_alpha_selected["penalty"].eq("elastic_net"),
            ["benchmark", "family", "l1_ratio", "alpha", "validation_rmse", "n_options_active"],
        ].copy()
        display(selected_elastic_net_temporal)
        for benchmark in _benchmark_penalties:
            print(f"{benchmark} — comparatif des pénalités (Elastic Net : seul rho retenu).")
            figure = plot_exploratory_alpha_grid(
                benchmark_alpha_table, benchmark_alpha_selected,
                benchmark=benchmark, nominal=prod.notional,
            )
            HYPERPARAMETER_FIGURES[f"exploratory_alpha_{benchmark}"] = figure
            plt.show()
        """
    ),
    markdown(
        r"""
        ### 1.1 — Recherche Elastic Net seule : tous les ratios

        Les deux graphiques suivants montrent **tous** les couples $(\rho,\alpha)$
        testés, d'abord pour Static cashflows, puis pour Conditional cashflows.
        L'étoile repère le même couple retenu que dans le tableau précédent ;
        les autres courbes restent visibles pour auditer ce choix.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.hyperparameter_study import (
            plot_exploratory_elastic_net_grid,
        )

        for benchmark in _benchmark_penalties:
            print(f"{benchmark} — recherche Elastic Net complète : tous les couples (rho, alpha).")
            elastic_figure = plot_exploratory_elastic_net_grid(
                benchmark_alpha_table, benchmark_alpha_selected,
                benchmark=benchmark, nominal=prod.notional,
            )
            HYPERPARAMETER_FIGURES[f"exploratory_elastic_net_{benchmark}"] = elastic_figure
            plt.show()
        """
    ),
    markdown(
        r"""
        ## 2. Méthode B — sélection des hyperparamètres de la politique totale pathwise

        **Méthode B (total pathwise).** Les paiements actualisés des paniers sont
        additionnés sur chaque trajectoire avant de mesurer l'erreur. Des erreurs
        de dates opposées peuvent donc se compenser. Chaque panier est choisi
        avec l'information disponible avant son échéance. Cette politique
        alimente ensuite la stabilité, le risque et les coûts du notebook
        principal. Ses alphas sont distincts de ceux de la section 1.1.

        Un même alpha numérique ne mesure pas la même régularisation pour L1 et L2. Chaque pénalité
        reçoit donc sa propre référence et sa propre grille logarithmique. L’alpha relatif sert
        uniquement à représenter les chemins sur un axe commun.

        Nous cherchons d'abord conjointement $(\rho,\alpha)$ pour Elastic Net, par famille,
        en évaluant toute la grille d'alpha à chaque ratio $\rho$. Les trois profils
        sont ensuite sélectionnés **sur l'ensemble des couples admissibles** : chacun
        peut donc posséder son propre ratio et son propre alpha. Le profil performance
        minimise la RMSE, le profil parcimonie minimise le nombre d'options et le
        compromis minimise la distance normalisée aux deux idéaux, en conservant
        trois solutions distinctes lorsque la grille le permet. **À ce stade,
        ces couples sont préliminaires** : la section 4 testera tous les couples
        admissibles sur plusieurs graines (deux en SPRINT, dix en FAST/REPORT),
        puis reprendra cette sélection parmi les stables.
        Le test final reste réservé ; les alphas de cette méthode B ne remplacent pas ceux
        de la méthode A par échéance.

        **Étape 1 — recherche conjointe Elastic Net.** Pour chaque $\rho$, toute la grille
        alpha est recalculée. La carte de chaleur présente les couples testés :
        chaque **ligne de panneaux** est une famille d'instruments (Calls + Puts sans binaires,
        puis Full avec binaires), et chaque **colonne** est une mesure (RMSE ou nombre d'options).
        Dans chaque panneau, $\rho$ est horizontal et l'alpha relatif vertical.
        Les deux familles partagent la même échelle de couleur pour une même mesure.
        Une cellule grise signifie « non convergé ou mesure absente » ; le contour noir
        repère les trois couples préliminaires. La petite cellule de préparation ci-dessous définit
        seulement les réglages communs ; **la cellule suivante lance réellement la recherche**.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.conditional_policy import (
            run_conditional_policy_penalty_comparison,
        )

        def run_regularisation_path(family, penalties, rho, seed=42):
            return run_conditional_policy_penalty_comparison(
                product=prod, spot0=spot0, valuation_date=valuation_date,
                maturity_date=maturity_date, rate=rate,
                dividend_yield=dividend_yield, vol=vol, family=family,
                penalties=tuple(penalties), elastic_net_l1_ratio=float(rho),
                n_paths=CFG["alpha_paths"], n_alphas=GRID.n_alphas,
                min_alpha_ratio=GRID.min_alpha_ratio,
                ridge_min_alpha_ratio=GRID.ridge_min_alpha_ratio,
                ridge_max_alpha_ratio=GRID.ridge_max_alpha_ratio,
                train_fraction=0.60, validation_fraction=0.20,
                min_candidate_options=2, max_candidate_options=10**9,
                min_state_paths=20, seed=int(seed),
            )

        print("Réglages de la méthode B préparés ; recherche (rho, alpha) dans la cellule suivante.")
        """
    ),
    code(
        r"""
        elastic_rho_results = {}
        rho_tables = []
        rho_profiles = []
        for family in MAIN_FAMILIES:
            for rho in GRID.elastic_net_l1_ratios:
                result = run_regularisation_path(family, ("elastic_net",), rho=rho)
                table = result["table"].copy()
                profiles = result["profiles"].copy()
                elastic_rho_results[(family, float(rho))] = result
                rho_tables.append(table.assign(family=family, searched_l1_ratio=float(rho)))
                rho_profiles.append(profiles.assign(searched_l1_ratio=float(rho)))

        rho_table = pd.concat(rho_tables, ignore_index=True)
        rho_profile_table = pd.concat(rho_profiles, ignore_index=True)
        from autocall_replication.replication.regularization_path import (
            select_three_profiles_per_penalty,
        )

        selected_rho = {}  # Ratio du compromis : uniquement référence des expériences de queue.
        selected_rho_rows = []
        for family in MAIN_FAMILIES:
            pool = rho_table.loc[rho_table["family"].eq(family)].copy()
            chosen = select_three_profiles_per_penalty(pool)
            if chosen.empty:
                raise ValueError(f"Aucun couple Elastic Net admissible pour {family}.")
            chosen.insert(0, "family", family)
            chosen["searched_l1_ratio"] = chosen["l1_ratio"].astype(float)
            selected_rho_rows.append(chosen)
            selected_rho[family] = float(chosen.loc[
                chosen["profile"].eq("compromise"), "l1_ratio"
            ].iloc[0])
        selected_rho_table = pd.concat(selected_rho_rows, ignore_index=True)
        print("Sélection préliminaire — trois couples (rho, alpha) par famille ; sélection finale en section 4 :")
        display(selected_rho_table[[
            "family", "profile", "searched_l1_ratio", "alpha_relative",
            "validation_rmse", "n_options_active",
        ]].rename(columns={
            "family": "Famille", "profile": "Profil", "searched_l1_ratio": "Ratio L1 (rho)",
            "alpha_relative": "Alpha relatif", "validation_rmse": "RMSE validation",
            "n_options_active": "Options actives",
        }).round(4))
        if SHOW_TECHNICAL_DETAILS:
            print("Audit intégral : profils calculés séparément pour chaque ratio.")
            display(rho_profile_table)
        """
    ),
    markdown(
        r"""
        ### 2 — Lecture visuelle de la grille Elastic Net

        Cette cellule **ne relance pas la recherche** : elle utilise `rho_table` et
        `selected_rho_table` calculés juste au-dessus. Une ligne de panneaux par famille,
        une colonne par mesure ; les contours P, C et S indiquent les trois profils
        **préliminaires**. Le tableau final et les couples à reporter sont en section 4.
        """
    ),
    code(
        r"""

        from autocall_replication.replication.hyperparameter_study import plot_rho_grid
        rho_figure = plot_rho_grid(
            rho_table, selected=selected_rho_table, nominal=prod.notional,
        )
        HYPERPARAMETER_FIGURES["elastic_net_rho_grid"] = rho_figure
        plt.show()
        """
    ),
    markdown(
        r"""
        ## 2.1 Méthode B — comparer les pénalités et conserver les trois couples Elastic Net

        Chaque famille est maintenant comparée sur L0, L1, L2 et Elastic Net. Les trois
        profils Elastic Net conservent leur **propre couple** $(\rho,\alpha)$, sans les
        rabattre artificiellement sur un ratio commun. L0, L1 et L2 utilisent les mêmes
        réglages propres à leur pénalité.
        Les trajectoires, le découpage calibration/validation et l'objectif pathwise total
        restent identiques. Le ratio du compromis est la seule référence utilisée plus
        loin pour les expériences de queue qui requièrent encore un ratio scalaire ; cela
        ne change pas les trois paniers Elastic Net déjà sélectionnés.

        **Lecture des graphiques.** Les courbes colorées relient uniquement les essais
        convergés. Une croix grise indique un essai non convergé : sa position correspond
        aux poids obtenus à l'arrêt du solveur (après au plus 5 000 itérations dans cette
        configuration). Sa RMSE et son nombre d'options sont provisoires, ne valident pas
        un optimum et ne participent pas au choix des profils. Une étoile colorée marque
        un profil retenu ; P, C et S signifient performance, compromis et parcimonie.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.hyperparameter_study import (
            combine_conditional_elastic_net_profiles,
        )

        base_regularisation_results = {}
        for family in MAIN_FAMILIES:
            baseline = run_regularisation_path(family, GRID.penalties, rho=selected_rho[family])
            base_regularisation_results[family], verified_profiles = (
                combine_conditional_elastic_net_profiles(
                    baseline,
                    {rho: elastic_rho_results[(family, float(rho))]
                     for rho in GRID.elastic_net_l1_ratios},
                )
            )
            expected = selected_rho_table.loc[selected_rho_table["family"].eq(family)]
            for profile in ("performance", "compromise", "parsimony"):
                left = expected.loc[expected["profile"].eq(profile)].iloc[0]
                right = verified_profiles.loc[verified_profiles["profile"].eq(profile)].iloc[0]
                if not (np.isclose(left["l1_ratio"], right["l1_ratio"])
                        and np.isclose(left["alpha_relative"], right["alpha_relative"])):
                    raise RuntimeError("La sélection Elastic Net change après assemblage des chemins.")
        base_alpha_table = pd.concat(
            [result["table"].assign(family=family) for family, result in base_regularisation_results.items()],
            ignore_index=True,
        )
        base_profile_table = pd.concat(
            [result["profiles"] for result in base_regularisation_results.values()],
            ignore_index=True,
        )
        base_alpha_table["retained_profile"] = ""
        for _, chosen in base_profile_table.iterrows():
            match = (
                base_alpha_table["family"].eq(chosen["family"])
                & base_alpha_table["penalty"].eq(chosen["penalty"])
                & np.isclose(base_alpha_table["alpha_relative"], chosen["alpha_relative"])
            )
            if chosen["penalty"] == "elastic_net":
                match &= np.isclose(base_alpha_table["l1_ratio"], chosen["l1_ratio"])
            if match.sum() != 1 or not bool(base_alpha_table.loc[match, "converged"].iloc[0]):
                raise RuntimeError("Un profil retenu doit correspondre à un essai convergé unique.")
            previous = base_alpha_table.loc[match, "retained_profile"].iloc[0]
            base_alpha_table.loc[match, "retained_profile"] = (
                f"{previous} / {chosen['profile']}" if previous else chosen["profile"]
            )
        base_profile_report_table = base_profile_table.loc[
            base_profile_table["profile"].eq("compromise"),
            ["family", "penalty", "l1_ratio", "alpha_relative",
             "validation_rmse", "n_options_active"],
        ].copy()
        base_profile_report_table["validation_rmse_pct_notional"] = (
            base_profile_report_table.pop("validation_rmse") * 100.0 / prod.notional
        )
        print("À reporter — sélection préliminaire du profil compromis, avant le filtre de stabilité ; autres profils dans l'export :")
        display(base_profile_report_table.rename(columns={
            "family": "Famille", "penalty": "Pénalité",
            "l1_ratio": "Ratio L1 (rho)", "alpha_relative": "Alpha relatif",
            "n_options_active": "Options actives",
            "validation_rmse_pct_notional": "RMSE validation (% nominal)",
        }).round(4))
        print("Convergence — les essais non convergés restent visibles en gris, mais exclus de la sélection :")
        display(base_alpha_table.groupby(["family", "penalty"], as_index=False).agg(
            essais=("converged", "size"), converges=("converged", "sum"),
        ).assign(non_converges=lambda table: table["essais"] - table["converges"]).rename(
            columns={"family": "Famille", "penalty": "Pénalité",
                     "essais": "Essais", "converges": "Convergés",
                     "non_converges": "Non convergés"},
        ))
        if SHOW_TECHNICAL_DETAILS:
            print("Tous les profils retenus, y compris performance et parcimonie :")
            display(base_profile_table)
            print("Audit intégral — alpha / rho, convergence et profil retenu :")
            display(base_alpha_table.rename(columns={
                "converged": "Convergence", "retained_profile": "Profil retenu",
            }))
        missing_pairs = [
            (family, penalty)
            for family in MAIN_FAMILIES for penalty in GRID.penalties
            if base_profile_table.loc[
                base_profile_table["family"].eq(family)
                & base_profile_table["penalty"].eq(penalty)
            ].empty
        ]
        if missing_pairs:
            print("Familles/pénalités sans profil admissible sur cette grille :", missing_pairs)

        from autocall_replication.replication.hyperparameter_study import plot_regularization_grid
        alpha_figure = plot_regularization_grid(
            base_alpha_table.loc[base_alpha_table["penalty"].ne("elastic_net")],
            base_profile_table, nominal=prod.notional,
            title="Méthode B — chemins alpha L0, L1 et L2 (Elastic Net : carte conjointe ci-dessus)",
        )
        HYPERPARAMETER_FIGURES["alpha_grid"] = alpha_figure
        plt.show()
        """
    ),
    markdown(
        r"""
        ## 3. L0 — qualité de l’optimum local et stabilité du support

        L0 est non convexe. Une convergence numérique n’est pas une preuve d’optimum global. Le
        tableau et le graphique rendent donc visibles les comparaisons warm start/cold start, les
        déclenchements du multistart et le nombre de supports distincts.
        """
    ),
    code(
        r"""
        l0_initialization_audit = pd.concat([
            result["results"]["l0"]["initialization_audit"].assign(family=family)
            for family, result in base_regularisation_results.items()
        ], ignore_index=True)
        l0_initialization_report_table = l0_initialization_audit.groupby(
            "family", as_index=False,
        ).agg(
            n_alphas=("solution_index", "size"),
            support_jaccard_median=("warm_cold_support_jaccard", "median"),
            distinct_supports_mean=("n_distinct_supports", "mean"),
        )
        print("Synthèse à reporter — robustesse de l'initialisation L0 :")
        display(l0_initialization_report_table.rename(columns={
            "family": "Famille", "n_alphas": "Alphas testés",
            "support_jaccard_median": "Jaccard médian",
            "distinct_supports_mean": "Supports distincts (moy.)",
        }).round(3))
        if SHOW_TECHNICAL_DETAILS:
            display(l0_initialization_audit)

        fig, axes = plt.subplots(1, 2, figsize=(14, 4.8))
        for family, group in l0_initialization_audit.groupby("family", sort=False):
            ordered = group.sort_values("alpha_relative", ascending=False)
            axes[0].plot(
                ordered["alpha_relative"], ordered["warm_cold_support_jaccard"],
                marker="o", label=FAMILY_LABELS[family],
            )
            axes[1].plot(
                ordered["alpha_relative"], ordered["n_distinct_supports"],
                marker="o", label=FAMILY_LABELS[family],
            )
        for axis in axes:
            axis.set_xscale("log")
            axis.invert_xaxis()
            axis.set_xlabel("Alpha L0 relatif (fort → faible)")
            axis.grid(alpha=0.25)
            axis.legend()
        axes[0].set_title("Accord entre démarrage chaud et démarrage froid")
        axes[0].set_ylabel("Similarité de Jaccard des supports")
        axes[1].set_title("Multiplicité des solutions locales observées")
        axes[1].set_ylabel("Nombre de supports distincts")
        fig.suptitle("L0 — audit de dépendance à l’initialisation")
        fig.tight_layout()
        HYPERPARAMETER_FIGURES["l0_initialization_audit"] = fig
        plt.show()
        """
    ),
    markdown(
        r"""
        ## 4. Quatre axes de stabilité, avant et après la sélection

        Les sections 2 et 2.1 présentent une première sélection fondée sur une seule
        calibration. Elle n'est **pas** la sélection finale. Ici, chaque couple
        (pénalité, alpha), ou (pénalité, rho, alpha) pour Elastic Net, qui a convergé
        et utilise au moins deux options est recalibré sur les **mêmes graines**
        (deux en SPRINT pour le rendu seulement ; dix en FAST/REPORT) pour le
        filtre de sélection.
        La topologie des dates et états est figée ; les poids sont réestimés sur chaque
        nouvel échantillon. Pour L0, chaque recalibration utilise un multistart
        reproductible, et non un unique départ à zéro.

        L'ordre final est : grille initiale → convergence → au moins deux options →
        **robustesse numérique (toutes les convergences et au moins 90 % des tailles admissibles)** →
        dominance RMSE/parcimonie → filtre de performance → doublons → trois profils.
        On compare donc les solutions non dominées **parmi les candidats stables**.
        Les valeurs de RMSE et de taille utilisées pour la dominance restent celles
        de la validation initiale : la robustesse n'introduit pas de nouveau score
        moyen dans cette étape. L'ES et le test final n'interviennent pas dans la
        sélection. Le calcul est nettement plus long, surtout pour L0 ; le tableau
        complet des recalibrations est conservé pour audit.

        **Pour les profils finaux**, un second audit utilise des graines **distinctes**
        de celles du filtre : dix recalibrations en FAST, trente en REPORT. Il ne
        re-sélectionne aucun profil. Nous distinguons quatre axes, sans les
        fusionner dans un indicateur trompeur : (1) convergence numérique ;
        (2) stabilité des instruments, par Jaccard avec le panier initial et entre
        toutes les paires de graines ; (3) stabilité du nombre d'options, par
        médiane et étendue ; (4) stabilité de couverture, par RMSE et ES 97,5 %.
        Pour le quatrième axe, chaque portefeuille recalibré et le portefeuille
        initial sont évalués sur **les mêmes trajectoires indépendantes** (graine
        84000). Elles ne sont pas utilisées pour choisir les profils et ne sont
        pas le test final. Une petite taille de la queue en FAST rend l'ES
        exploratoire. Les Jaccards résumés ne portent que sur les recalibrations
        convergées. Un Jaccard faible peut signaler des instruments substituables ;
        il n'est pas à lui seul un motif de rejet. Le filtre de sélection actuel
        ne garantit donc **ni** un Jaccard élevé **ni** une taille proche de celle
        du panier initial **ni** une couverture stable.
        La synthèse placée en tête des résultats rapproche, pour chaque politique
        distincte, le nombre d'options initial, la moyenne et l'étendue sur les
        recalibrations finales du mode exécuté, le Jaccard entre graines et les
        convergences. Une
        alerte apparaît si la taille moyenne atteint au moins deux fois la
        taille initiale : c'est un **signal descriptif**, pas un nouveau filtre
        de sélection. Plusieurs noms de profils peuvent désigner les mêmes poids.
        Pour L0, l'axe numérique inclut aussi l'écart relatif des objectifs entre
        initialisations convergées du multistart ; un petit écart ne prouve pas
        l'optimalité globale de ce problème non convexe.

        Le graphique de stabilité ne montre que les **profils finaux**, afin de
        rester lisible ; ce n'est pas la population complète testée. Il affiche la
        distribution par profil, pas seulement la moyenne.
        Pour chaque ligne, les points bleus et la boîte ne concernent que les
        recalibrages convergés ; la boîte couvre les quartiles 25 % à 75 %, le
        trait orange est la médiane et le triangle vert la moyenne. Les croix
        grises montrent les métriques provisoires des essais non convergés,
        calculées avec les poids à l'arrêt du solveur. Une boîte
        absente signifie qu'aucune graine n'a convergé : elle ne prouve pas une
        RMSE nulle ni une couverture satisfaisante.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.stability import (
            run_conditional_policy_candidate_stability,
            run_conditional_policy_profile_stability,
        )
        from autocall_replication.replication.hyperparameter_study import (
            plot_seed_robustness,
            plot_regularization_filter_map,
            regularization_filter_flow,
            select_profiles_after_candidate_stability,
        )

        final_regularisation_results = base_regularisation_results
        stability_results = {}
        stable_profile_results = {}
        for family in MAIN_FAMILIES:
            final_result = final_regularisation_results[family]
            stability = run_conditional_policy_candidate_stability(
                base_result=final_result, product=prod, spot0=spot0,
                valuation_date=valuation_date, maturity_date=maturity_date,
                rate=rate, dividend_yield=dividend_yield, vol=vol,
                n_calibrations=CFG["stability_calibrations"],
                seeds=tuple(71000 + index for index in range(CFG["stability_calibrations"])),
                n_paths=CFG["stability_paths"], min_active_options=2,
                max_active_options=10**9,
                min_valid_calibrations=int(np.ceil(0.9 * CFG["stability_calibrations"])),
                minimum_calibrations=2 if RUN_MODE == "sprint" else 10,
            )
            stability_results[family] = stability
            stable_profile_results[family] = select_profiles_after_candidate_stability(
                final_result, stability,
            )

        stability_details = pd.concat(
            [result["details"] for result in stability_results.values()], ignore_index=True
        )
        stability_summary = pd.concat(
            [result["summary"] for result in stability_results.values()], ignore_index=True
        )
        stability_counts = stability_summary.groupby(
            ["family", "penalty"], as_index=False,
        ).agg(candidats_testes=("solution_index", "count"),
              candidats_stables=("passes_stability_filter", "sum"))
        print("Synthèse à reporter — stabilité avant dominance :")
        display(stability_counts.rename(columns={
            "family": "Famille", "penalty": "Pénalité",
            "candidats_testes": "Candidats testés",
            "candidats_stables": "Candidats stables",
        }))
        final_profile_table = pd.concat(
            [result["profiles"] for result in stable_profile_results.values()],
            ignore_index=True,
        )
        final_profile_report_table = final_profile_table.loc[
            final_profile_table["profile"].eq("compromise"),
            ["family", "penalty", "l1_ratio", "alpha_relative",
             "validation_rmse", "n_options_active"],
        ].copy()
        final_profile_report_table["validation_rmse_pct_notional"] = (
            final_profile_report_table.pop("validation_rmse") * 100.0 / prod.notional
        )
        print("À reporter — hyperparamètres finaux après le filtre de stabilité (profil compromis) :")
        display(final_profile_report_table.rename(columns={
            "family": "Famille", "penalty": "Pénalité",
            "l1_ratio": "Ratio L1 (rho)", "alpha_relative": "Alpha relatif",
            "n_options_active": "Options actives",
            "validation_rmse_pct_notional": "RMSE validation (% nominal)",
        }).round(4))
        selected_stability_results = {}
        for family, selected_result in stable_profile_results.items():
            selected_stability_results[family] = run_conditional_policy_profile_stability(
                base_result=selected_result, product=prod, spot0=spot0,
                valuation_date=valuation_date, maturity_date=maturity_date,
                rate=rate, dividend_yield=dividend_yield, vol=vol,
                n_calibrations=CFG["final_stability_calibrations"],
                seeds=tuple(72000 + index for index in range(CFG["final_stability_calibrations"])),
                n_paths=CFG["stability_paths"], min_active_options=2,
                max_active_options=10**9,
                min_valid_calibrations=int(np.ceil(0.9 * CFG["final_stability_calibrations"])),
                minimum_calibrations=2 if RUN_MODE == "sprint" else 10,
                l0_multistart=True,
                evaluation_n_paths=CFG["tail_validation_paths"],
                evaluation_seed=84000,
            )
        selected_stability_summary = pd.concat(
            [result["summary"] for result in selected_stability_results.values()],
            ignore_index=True,
        )
        selected_stability_details = pd.concat(
            [result["details"] for result in selected_stability_results.values()],
            ignore_index=True,
        )
        selected_profile_stability = final_profile_table.merge(
            selected_stability_summary,
            on=["family", "penalty", "profile", "solution_index"],
            how="left", validate="one_to_one", suffixes=("", "_stability"),
        )
        # Une politique peut porter plusieurs étiquettes de profil : ne la compter qu'une fois.
        stability_size_diagnostic = selected_profile_stability.copy()
        policy_keys = ["family", "penalty", "solution_index"]
        stability_size_diagnostic["profiles_represented"] = (
            stability_size_diagnostic.groupby(policy_keys)["profile"]
            .transform(lambda values: ", ".join(sorted(values.unique())))
        )
        stability_size_diagnostic = stability_size_diagnostic.drop_duplicates(policy_keys).copy()
        stability_size_diagnostic["size_multiplier"] = (
            stability_size_diagnostic["n_options_active_mean"]
            / stability_size_diagnostic["base_n_options_active"].clip(lower=1)
        )
        stability_size_diagnostic = stability_size_diagnostic.sort_values(
            "size_multiplier", ascending=False,
        )
        stability_report_table = stability_size_diagnostic.drop_duplicates(
            ["family", "penalty"]
        )[[
            "family", "penalty", "base_n_options_active", "n_options_active_mean",
            "size_multiplier", "support_pairwise_jaccard_median",
            "n_converged", "n_calibrations", "common_evaluation_es_mean",
        ]].copy()
        stability_report_table["convergence_rate"] = (
            stability_report_table.pop("n_converged")
            / stability_report_table.pop("n_calibrations")
        )
        stability_report_table["common_evaluation_es_mean_pct_notional"] = (
            stability_report_table.pop("common_evaluation_es_mean")
            * 100.0 / prod.notional
        )
        stability_report_table = stability_report_table.sort_values(["family", "penalty"])
        print(
            "Lecture indispensable : le filtre de stabilité ci-dessous vérifie la convergence "
            "et un nombre d'options admissible, pas la conservation du nombre d'options "
            "ni du support initial. Une politique répétée sous plusieurs profils n'apparaît "
            "qu'une fois dans cette synthèse."
        )
        from IPython.display import Markdown
        for _, row in stability_size_diagnostic.loc[
            stability_size_diagnostic["size_multiplier"].ge(2.0)
        ].iterrows():
            display(Markdown(
                f"> **Alerte de taille — {FAMILY_LABELS[row['family']]} / "
                f"{row['penalty'].upper()} :** {int(row['base_n_options_active'])} "
                f"options initialement, **{row['n_options_active_mean']:.1f} en moyenne** "
                f"sur {int(row['n_calibrations'])} recalibrations "
                f"(de {int(row['n_options_active_min'])} à "
                f"{int(row['n_options_active_max'])}). "
                f"Jaccard entre graines : {row['support_pairwise_jaccard_median']:.2f} ; "
                f"convergence : {int(row['n_converged'])}/{int(row['n_calibrations'])}. "
                "La convergence numérique ne suffit pas à établir la stabilité du panier."
            ))
        print("À reporter — un cas par famille et pénalité : celui dont la taille dérive le plus ; détails complets dans l'export.")
        display(stability_report_table.rename(columns={
            "family": "Famille", "penalty": "Pénalité",
            "base_n_options_active": "Options initiales",
            "n_options_active_mean": "Options recalibrées (moy.)",
            "size_multiplier": "Rapport de taille",
            "support_pairwise_jaccard_median": "Jaccard entre graines",
            "convergence_rate": "Taux de convergence",
            "common_evaluation_es_mean_pct_notional": "ES recalibré (% nominal)",
        }).round(2))
        if SHOW_TECHNICAL_DETAILS:
            print("Diagnostics complets des quatre axes de stabilité — un rang par profil :")
            display(stability_size_diagnostic)
            display(selected_profile_stability)
            display(stability_summary)
            display(stability_details)
            display(selected_stability_details)
        selected_seed_details = selected_stability_details
        if not selected_seed_details.empty:
            stability_figure = plot_seed_robustness(
                selected_seed_details, nominal=prod.notional,
            )
            HYPERPARAMETER_FIGURES["multi_seed_stability"] = stability_figure
            plt.show()

        # Les expériences de queue qui suivent doivent reprendre le ratio rho
        # du compromis final, éventuellement différent du choix préliminaire.
        for family, result in stable_profile_results.items():
            final_elastic = result["profiles"].loc[
                result["profiles"]["penalty"].eq("elastic_net")
                & result["profiles"]["profile"].eq("compromise")
            ]
            if final_elastic.empty:
                selected_rho.pop(family, None)
            else:
                selected_rho[family] = float(final_elastic.iloc[0]["l1_ratio"])

        regularization_filter_table = pd.concat(
            [regularization_filter_flow(
                stable_profile_results[family], family=family,
                stability_stage_label=f"Robustes sur {CFG['stability_calibrations']} graines",
            ) for family in MAIN_FAMILIES],
            ignore_index=True,
        )
        print("Carte des filtres : chaque case indique seulement les solutions restantes après l'étape.")
        display(regularization_filter_table.loc[
            regularization_filter_table["stage"].isin([
                "Grille initiale", f"Robustes sur {CFG['stability_calibrations']} graines", "Non dominés",
                "Sans quasi-doublons", "Profils distincts",
            ]),
            ["family", "penalty", "stage", "remaining"],
        ].rename(columns={"family": "Famille", "penalty": "Pénalité",
                          "stage": "Étape", "remaining": "Solutions restantes"}))
        if SHOW_TECHNICAL_DETAILS:
            display(regularization_filter_table)
        filter_map = plot_regularization_filter_map(regularization_filter_table)
        HYPERPARAMETER_FIGURES["regularization_filter_map"] = filter_map
        plt.show()
        """
    ),
    markdown(
        r"""
        ## 4.1 Contrôle ES des alphas conditionnels déjà calculés

        **Question.** Le choix d'alpha fondé sur l'erreur de validation et la parcimonie
        changerait-il si l'on regardait aussi le risque extrême ? Nous évaluons **tous les
        alphas convergés avec au moins deux options**, y compris ceux écartés par les anciens
        filtres RMSE/parcimonie : un point dominé sur ces deux axes peut être utile sur l'ES.

        Les poids, instruments et nœuds de chaque politique sont **figés**. Une nouvelle
        validation indépendante, commune aux candidats d'une même famille, mesure le
        shortfall $H-Xw$, sa RMSE, son ES 97,5 % et le nombre d'options actives. Il n'y a
        ici **ni réoptimisation des poids, ni nouveau choix d'alpha, ni test final**.
        Les étoiles des graphiques désignent les profils déjà retenus ; les cercles entourés
        sont non dominés sur les trois critères RMSE, ES et nombre d'options, séparément
        pour chaque pénalité. Une baisse d'ES obtenue avec une RMSE ou une taille fortement
        dégradée n'est pas automatiquement préférable. En mode FAST, l'ES repose sur peu
        de trajectoires de queue : cette comparaison est exploratoire et doit être confirmée
        en mode REPORT avant toute décision.

        **Lecture du visuel.** Un point correspond à **un portefeuille issu d'un alpha**
        (et d'un ratio $\rho$ pour Elastic Net), pas à une trajectoire. Les trajectoires
        servent à estimer les deux coordonnées de ce point ; en augmenter le nombre
        ne multiplie donc pas les points si la grille d'hyperparamètres reste fixe.
        Le premier panneau montre tous les candidats. Le second affiche uniquement
        les portefeuilles retenus par les six règles. La légende est reprise
        dans chaque panneau.
        Les points gris montrent les autres candidats admissibles et les croix les candidats hors sélection.
        sur RMSE, ES et nombre d'options ; les étoiles marquent les profils déjà retenus.
        Dans chaque univers et pour chaque pénalité, les losanges E, RE et REP indiquent
        les profils ES minimale, compromis RMSE–ES et compromis RMSE–ES–parcimonie.
        La sélection utilise les candidats stables dans les bornes de taille de la grille.
        Pour chaque compromis, les axes sont normalisés sur [0, 1] et pondérés à parts
        égales. Les règles peuvent retenir le même portefeuille.
        Le notebook principal compare les profils à poids fixés sur des trajectoires indépendantes.
        Le tableau complet conserve tous les candidats et leurs valeurs exactes.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.conditional_policy import build_external_policy_design
        from autocall_replication.replication.hyperparameter_study import (
            select_es_profiles,
            evaluate_alpha_tail_frontier, plot_alpha_tail_frontier,
        )

        alpha_tail_tables = []
        alpha_tail_comparisons = []
        for family, base_result in final_regularisation_results.items():
            external = build_external_policy_design(
                base_result=base_result, product=prod, spot0=spot0,
                valuation_date=valuation_date, maturity_date=maturity_date,
                rate=rate, dividend_yield=dividend_yield, vol=vol,
                n_paths=CFG["tail_validation_paths"], seed=83000,
            )
            evaluated = evaluate_alpha_tail_frontier(
                stable_profile_results[family], external["A"], external["b"],
                es_level=0.975,
            )
            if evaluated.empty:
                print(f"{family} : aucun alpha convergé admissible pour ce contrôle.")
                continue
            alpha_tail_tables.append(evaluated)
            for panel in ("overview", "zoom"):
                figure = plot_alpha_tail_frontier(
                    evaluated, nominal=prod.notional, panel=panel,
                    title=f"{FAMILY_LABELS[family]} — politiques conditionnelles B · validation indépendante de queue",
                )
                HYPERPARAMETER_FIGURES[f"alpha_tail_frontier_{family}_{panel}"] = figure
                plt.show()
            for penalty, group in evaluated.groupby("penalty", sort=False):
                current = group.loc[group["retained_profiles"].str.contains("compromise")]
                best_es = group.sort_values(["validation_es", "validation_rmse"]).iloc[0]
                if current.empty:
                    continue
                current = current.iloc[0]
                alpha_tail_comparisons.append({
                    "family": family, "penalty": penalty,
                    "current_compromise_alpha": current["alpha"],
                    "current_compromise_rmse": current["validation_rmse"],
                    "current_compromise_es_975": current["validation_es"],
                    "current_compromise_n_options": current["n_options_active"],
                    "minimum_es_alpha": best_es["alpha"],
                    "minimum_es_rmse": best_es["validation_rmse"],
                    "minimum_es_975": best_es["validation_es"],
                    "minimum_es_n_options": best_es["n_options_active"],
                })

        alpha_tail_table = pd.concat(alpha_tail_tables, ignore_index=True) if alpha_tail_tables else pd.DataFrame()
        alpha_tail_comparison = pd.DataFrame(alpha_tail_comparisons)
        print("Comparaison diagnostique seulement : minimum d'ES ≠ nouveau profil sélectionné.")
        es_selection_profiles = select_es_profiles(alpha_tail_table)
        tail_metrics = ["validation_rmse", "validation_es", "n_options_active"]
        tail_keys = ["family", "penalty", "solution_index"]
        initial_for_comparison = pd.concat([
            result["profiles"] for result in stable_profile_results.values()
        ], ignore_index=True)
        if not alpha_tail_table.empty:
            settings = ["profile", "alpha", "l1_ratio"]
            selection = pd.concat([
                initial_for_comparison[tail_keys + settings],
                es_selection_profiles[tail_keys + settings],
            ], ignore_index=True)
            validation_profile_selection_comparison = selection.merge(
                alpha_tail_table[tail_keys + tail_metrics], on=tail_keys,
                how="left", validate="many_to_one",
            )
            display(validation_profile_selection_comparison.round(3))
        else:
            validation_profile_selection_comparison = pd.DataFrame()

        if not alpha_tail_comparison.empty:
            display(alpha_tail_comparison[[
                "family", "penalty", "current_compromise_rmse",
                "current_compromise_es_975", "minimum_es_rmse", "minimum_es_975",
                "current_compromise_n_options", "minimum_es_n_options",
            ]].rename(columns={
                "family": "Famille", "penalty": "Pénalité",
                "current_compromise_rmse": "RMSE compromis", "current_compromise_es_975": "ES compromis",
                "minimum_es_rmse": "RMSE min ES", "minimum_es_975": "ES minimum",
                "current_compromise_n_options": "Options compromis",
                "minimum_es_n_options": "Options min ES",
            }).round(3))
        if SHOW_TECHNICAL_DETAILS and not alpha_tail_table.empty:
            display(alpha_tail_comparison)
            display(alpha_tail_table.loc[alpha_tail_table["pareto_rmse_es_options"]].sort_values(
                ["family", "penalty", "validation_es"]
            ))
        """
    ),
    markdown(
        r"""
        ## 5. Contrôle du risque extrême — quatre normes, deux grilles

        La recherche est réalisée sur des trajectoires de calibration, puis chaque solution est
        évaluée sur un échantillon indépendant de validation.

        Les deux familles d'instruments et les normes **L0, L1, L2 et Elastic Net** sont
        comparées sur les mêmes trajectoires de calibration et de validation. Pour Elastic
        Net, chaque ratio $\rho$ possède sa propre échelle d'alpha : tous les couples
        $(\rho,\alpha)$ sont testés avant de retenir les profils. Pour L1, la référence est
        le seuil de disparition des options ; pour L2, c'est une échelle de croisement
        entre amélioration de RMSE et pénalité quadratique, **pas** un seuil de parcimonie.
        Ces alphas ne sont pas ceux du premier solveur, qui travaille avec une perte et
        une normalisation différentes.
        La grille d'alpha relatif descend désormais jusqu'à $10^{-5}$ (avec un point
        intermédiaire à $10^{-4}$), car plusieurs compromis du REPORT précédent
        atteignaient l'ancienne borne $10^{-3}$. Cette extension est une analyse
        de sensibilité pour un prochain run : la sélection REPORT déjà promue
        reste celle de son export daté, sans recalcul ni changement rétroactif.

        **Que limite le « budget ES » ?** Pour une trajectoire, on note
        $L_i(w)=H_i-X_iw$ : paiements dus par l'autocall moins cashflows de la
        couverture. $L_i>0$ signifie un manque à payer. L'ES 97,5 % est la
        **moyenne des pertes dans les 2,5 % de trajectoires les plus défavorables**.
        Le budget ne limite donc **ni le prix des options, ni le nombre d'options,
        ni chaque perte individuelle**. Avec un nominal de 100, un plafond de
        10 % signifie $\widehat{ES}_{97,5\%}(L(w))\leq 10$ : certaines
        trajectoires peuvent néanmoins perdre plus de 10.

        Les trois plafonds communs sont **5 %, 10 % et 15 % du nominal**, identiques
        pour Calls + Puts, Full et les quatre normes. Ce sont des **seuils de recherche**
        fixés avant REPORT, pas des limites économiques de desk. Pour chaque budget
        d'optimisation $B_{\mathrm{optim}}$, on cherche sur la calibration les poids
        minimisant $\mathrm{RMSE}(w)+\alpha\Omega(w)$ sous
        $\widehat{ES}^{\mathrm{cal}}_{97,5\%}(L(w))\leq B_{\mathrm{optim}}$.
        Ensuite, **sans réajuster les poids**, on mesure l'ES sur la validation
        indépendante et on le compare à un plafond commun de décision
        $B_{\mathrm{décision}}\in\{5,10,15\}$, qui peut différer du budget
        d'optimisation du candidat. Par exemple, un panier calibré sous 5 peut
        obtenir un ES de 8 en validation : il dépasse son budget initial, mais
        reste sous le plafond de décision 10. Les deux constats sont affichés
        séparément ; respecter le budget en calibration ne garantit jamais le
        respect du plafond en validation.

        **Limite L0 :** l'optimisation ES globale sous pénalité L0 est non convexe. Nous
        reprenons les supports convergés trouvés dans la recherche L0 précédente,
        réoptimisons les poids *à support fixé* pour chaque contrôle ES, puis choisissons
        le support par le critère de calibration $\mathrm{RMSE}+\lambda_{ES}\mathrm{ES}
        +\alpha\,|S|$ ou, sous budget, $\mathrm{RMSE}+\alpha\,|S|$. Cela permet une
        comparaison honnête, mais **ne garantit pas l'optimum L0 global**. Aucun résultat
        de validation ne sert à choisir le support à l'intérieur d'un couple de paramètres.

        1. **ES pénalisé** : grille jointe d’alpha et de $\lambda_{ES}$.
           Avec un ES signé et du cash non pénalisé, $\lambda_{ES}\geq 1$
           peut récompenser une surcouverture sans borne économique. Ces essais
           restent dans les CSV d'audit mais **ne peuvent plus être sélectionnés** ;
           un éventuel point extrême hors cadre est annoncé sur le graphique.
           Cette garde mathématique ne remplace pas une contrainte future de
           financement ou d'exposition.
           Un ES signé négatif est mathématiquement possible : même la moyenne
           des plus grandes pertes résiduelles devient négative si la réplication
           dépasse le paiement dû. Cela ne prouve pas un profit économique,
           car le coût initial et la liquidité ne sont pas établis ici. Les
           portefeuilles très fournis sont conservés comme résultats de la
           recherche, mais ne sont pas recommandés sur cette seule base.
        2. **ES contraint** : même grille alpha sous les trois budgets absolus communs.
           Pour chaque plafond, nous retenons la plus faible RMSE de validation parmi les
           candidats convergés, faisables en calibration et dont l'ES de validation
           respecte ce plafond. Le profil « priorité ES » correspond au plafond strict,
           « compromis » à l'intermédiaire et « priorité RMSE » au souple. Si aucun
           candidat ne passe un niveau, il est déclaré absent. La validation sert ici
           au **choix des hyperparamètres** ; seul le test final réservé pourra estimer
           sans ce biais de sélection la performance de la politique choisie.

        Pour la grille lambda, jusqu'à trois profils sont retenus d'après la frontière
        RMSE–ES observée. Aucun profil lambda n'est
        retenu si faire varier lambda ne produit pas de réponse mesurable sur les solutions
        convergées. Les points dominés restent visibles dans le graphique.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.importance_sampling import (
            build_conditional_policy_sampling_design,
        )
        from autocall_replication.replication.tail_risk_optimization import (
            rmse_ridge_alpha_reference,
            rmse_sparse_alpha_reference,
        )
        from autocall_replication.replication.hyperparameter_study import (
            plot_tail_frontiers,
            plot_tail_budget_filter_flow,
            merge_tail_rho_grids,
            run_l0_tail_support_grid,
            run_tail_hyperparameter_grid,
        )

        tail_grid_results = {}
        tail_tables = []
        lambda_profiles = []
        budget_profiles = []
        budget_filter_flows = []
        tail_alpha_references = []
        budgets = tuple(
            prod.notional * pct / 100.0 for pct in GRID.es_budget_pct_notional
        )
        print("Plafonds ES communs (% du nominal) :", GRID.es_budget_pct_notional)
        for family, stable_result in stable_profile_results.items():
            available = stable_result["profiles"]
            reference_profile = available.loc[
                available["penalty"].eq("elastic_net")
                & available["profile"].eq("compromise")
            ]
            if reference_profile.empty:
                print(f"{FAMILY_LABELS[family]} : profil Elastic Net compromis absent après stabilité.")
                continue
            common = dict(
                base_result=stable_result, product=prod, spot0=spot0,
                valuation_date=valuation_date, maturity_date=maturity_date,
                rate=rate, dividend_yield=dividend_yield, vol=vol,
            )
            calibration = build_conditional_policy_sampling_design(
                **common, n_paths=CFG["tail_calibration_paths"], seed=81000,
                sampling_method="standard_mc",
            )
            validation = build_conditional_policy_sampling_design(
                **common, n_paths=CFG["tail_validation_paths"], seed=82000,
                sampling_method="standard_mc",
            )
            cash_indices = tuple(stable_result["unpenalized_indices"])
            active_threshold = float(stable_result["active_threshold"])
            for penalty in GRID.penalties:
                common_grid = dict(
                    calibration_A=calibration["A"], calibration_b=calibration["b"],
                    validation_A=validation["A"], validation_b=validation["b"],
                    lambda_es_values=GRID.lambda_es_values,
                    es_budget_values=budgets, es_level=0.975,
                    unpenalized_indices=cash_indices,
                    active_threshold=active_threshold,
                )
                if penalty == "l0":
                    raw = stable_result["raw_table"]
                    l0_rows = raw.loc[raw["penalty"].eq("l0") & raw["converged"].astype(bool)]
                    supports = [
                        stable_result["results"]["l0"]["solutions"][int(row["solution_index"])]["weights"]
                        for _, row in l0_rows.iterrows()
                    ]
                    if not supports:
                        print(f"{FAMILY_LABELS[family]} / L0 : aucun support convergé ; grille ES non calculable.")
                        continue
                    result = run_l0_tail_support_grid(
                        **common_grid, support_weights=supports,
                        alpha_ratios=GRID.tail_alpha_ratios,
                    )
                    tail_alpha_references.append(dict(
                        family=family, penalty=penalty, l1_ratio=np.nan,
                        alpha_reference=result["alpha_reference"],
                        reference_type="cash-vers-support ; heuristique L0",
                    ))
                elif penalty == "elastic_net":
                    rho_grids = []
                    for rho in GRID.elastic_net_l1_ratios:
                        alpha_reference = rmse_sparse_alpha_reference(
                            calibration["A"], calibration["b"], l1_ratio=rho,
                            unpenalized_indices=cash_indices,
                        )
                        tail_alpha_references.append(dict(
                            family=family, penalty=penalty, l1_ratio=rho,
                            alpha_reference=alpha_reference,
                            reference_type="seuil RMSE sparse propre au rho",
                        ))
                        rho_result = run_tail_hyperparameter_grid(
                            **common_grid, penalty=penalty,
                            alpha_values=tuple(alpha_reference * ratio for ratio in GRID.tail_alpha_ratios),
                            l1_ratio_values=(rho,),
                        )
                        rho_result["table"]["alpha_relative_tail"] = (
                            rho_result["table"]["alpha"] / alpha_reference
                        )
                        rho_grids.append(rho_result)
                    result = merge_tail_rho_grids(rho_grids)
                else:
                    if penalty == "l1":
                        alpha_reference = rmse_sparse_alpha_reference(
                            calibration["A"], calibration["b"], l1_ratio=1.0,
                            unpenalized_indices=cash_indices,
                        )
                        reference_type = "seuil RMSE sparse"
                    else:
                        l2_profile = available.loc[
                            available["penalty"].eq("l2") & available["profile"].eq("compromise")
                        ]
                        l2_weights = (
                            stable_result["results"]["l2"]["solutions"][int(l2_profile.iloc[0]["solution_index"])]["weights"]
                            if not l2_profile.empty else np.linalg.lstsq(calibration["A"], calibration["b"], rcond=None)[0]
                        )
                        alpha_reference = rmse_ridge_alpha_reference(
                            calibration["A"], calibration["b"], l2_weights,
                            unpenalized_indices=cash_indices,
                        )
                        reference_type = "croisement RMSE/coût L2 ; pas un seuil de sparsité"
                    tail_alpha_references.append(dict(
                        family=family, penalty=penalty, l1_ratio=np.nan,
                        alpha_reference=alpha_reference, reference_type=reference_type,
                    ))
                    result = run_tail_hyperparameter_grid(
                        **common_grid, penalty=penalty,
                        alpha_values=tuple(alpha_reference * ratio for ratio in GRID.tail_alpha_ratios),
                        l1_ratio_values=(0.5,),
                    )
                    result["table"]["alpha_relative_tail"] = result["table"]["alpha"] / alpha_reference
                for table_name in ("lambda_table", "budget_table", "lambda_profiles", "budget_profiles"):
                    table = result[table_name]
                    if not table.empty and "alpha_relative_tail" not in table:
                        table["alpha_relative_tail"] = table["alpha"] / alpha_reference
                for table_name in ("table", "budget_table", "budget_profiles"):
                    table = result[table_name]
                    if "es_budget" in table:
                        table["optimisation_budget_pct_notional"] = (
                            table["es_budget"] * 100.0 / prod.notional
                        )
                    if "risk_limit_es" in table:
                        table["risk_limit_pct_notional"] = (
                            table["risk_limit_es"] * 100.0 / prod.notional
                        )
                if not result["lambda_table"]["lambda_response_detected"].any():
                    print(f"{FAMILY_LABELS[family]} / {penalty} : pas de réponse lambda ES mesurable ; aucun profil lambda retenu.")
                tail_grid_results[(family, penalty)] = result
                tail_tables.append(result["table"].assign(family=family))
                lambda_profiles.append(result["lambda_profiles"].assign(family=family))
                budget_profiles.append(result["budget_profiles"].assign(family=family))
                flow = result["budget_filter_flow"].assign(family=family, penalty=penalty)
                budget_filter_flows.append(flow)
                figure = plot_tail_frontiers(result, nominal=prod.notional)
                figure.suptitle(
                    f"{FAMILY_LABELS[family]} — {penalty.upper()} — RMSE et ES sur validation indépendante",
                    fontsize=13,
                )
                HYPERPARAMETER_FIGURES[f"tail_frontiers_{family}_{penalty}"] = figure
                if SHOW_TECHNICAL_DETAILS:
                    plt.show()
                else:
                    plt.close(figure)  # Figure conservée dans l'export, sans encombrer la lecture.

        tail_grid_table = pd.concat(tail_tables, ignore_index=True) if tail_tables else pd.DataFrame()
        lambda_profile_table = pd.concat(lambda_profiles, ignore_index=True) if lambda_profiles else pd.DataFrame()
        budget_profile_table = pd.concat(budget_profiles, ignore_index=True) if budget_profiles else pd.DataFrame()
        budget_filter_table = pd.concat(budget_filter_flows, ignore_index=True) if budget_filter_flows else pd.DataFrame()
        tail_alpha_reference_table = pd.DataFrame(tail_alpha_references)
        budget_level_rows = []
        for (family, penalty), result in tail_grid_results.items():
            candidates = result["budget_table"]
            for profile, level, cap in zip(
                ("es_priority", "compromise", "rmse_priority"),
                ("strict", "intermédiaire", "souple"),
                budgets,
            ):
                admissible = candidates.loc[
                    candidates["converged"].astype(bool)
                    & candidates["feasible_calibration"].astype(bool)
                    & np.isfinite(candidates["validation_rmse"])
                    & np.isfinite(candidates["validation_es"])
                    & candidates["validation_es"].le(cap)
                ]
                chosen = result["budget_profiles"].loc[
                    result["budget_profiles"]["profile"].eq(profile)
                ]
                budget_level_rows.append({
                    "family": family, "penalty": penalty, "level": level,
                    "risk_limit_pct_notional": cap * 100.0 / prod.notional,
                    "n_admissible": len(admissible),
                    "selected_validation_rmse_pct_notional": (
                        float(chosen.iloc[0]["validation_rmse"]) * 100.0 / prod.notional
                        if not chosen.empty else np.nan
                    ),
                    "selected_validation_es_pct_notional": (
                        float(chosen.iloc[0]["validation_es"]) * 100.0 / prod.notional
                        if not chosen.empty else np.nan
                    ),
                    "selected_optimisation_budget_pct_notional": (
                        float(chosen.iloc[0]["es_budget"]) * 100.0 / prod.notional
                        if not chosen.empty else np.nan
                    ),
                    "selected_n_options_active": (
                        int(chosen.iloc[0]["n_options_active"])
                        if not chosen.empty else np.nan
                    ),
                    "selected_own_budget_respected": (
                        bool(chosen.iloc[0]["validation_budget_respected"])
                        if not chosen.empty else np.nan
                    ),
                    "status": "retenu" if not chosen.empty else "aucun candidat sous ce plafond",
                })
        budget_level_status_table = pd.DataFrame(budget_level_rows)
        lambda_report_rows = []
        for family in MAIN_FAMILIES:
            for penalty in GRID.penalties:
                matches = lambda_profile_table.loc[
                    lambda_profile_table["family"].eq(family)
                    & lambda_profile_table["penalty"].eq(penalty)
                    & lambda_profile_table["profile"].eq("compromise")
                ]
                chosen = matches.iloc[0] if not matches.empty else None
                lambda_report_rows.append({
                    "family": family, "penalty": penalty,
                    "lambda_es": chosen["lambda_es"] if chosen is not None else np.nan,
                    "validation_rmse_pct_notional": (
                        chosen["validation_rmse"] * 100.0 / prod.notional
                        if chosen is not None else np.nan
                    ),
                    "validation_es_pct_notional": (
                        chosen["validation_es"] * 100.0 / prod.notional
                        if chosen is not None else np.nan
                    ),
                    "n_options_active": chosen["n_options_active"] if chosen is not None else np.nan,
                    "status": "retenu" if chosen is not None else "aucun profil admissible",
                })
        lambda_report_table = pd.DataFrame(lambda_report_rows)
        budget_report_table = budget_level_status_table.loc[
            budget_level_status_table["level"].eq("intermédiaire"),
            ["family", "penalty", "selected_optimisation_budget_pct_notional",
             "selected_validation_rmse_pct_notional", "selected_validation_es_pct_notional",
             "selected_n_options_active", "status"],
        ].copy()
        print("À reporter — ES pénalisé, profil compromis (unités de risque : % du nominal) :")
        display(lambda_report_table.rename(columns={
            "family": "Famille", "penalty": "Pénalité", "lambda_es": "Lambda ES",
            "validation_rmse_pct_notional": "RMSE validation",
            "validation_es_pct_notional": "ES validation",
            "n_options_active": "Options actives", "status": "Statut",
        }).round(2))
        print("À reporter — ES contraint, plafond commun intermédiaire de 10 % du nominal :")
        display(budget_report_table.rename(columns={
            "family": "Famille", "penalty": "Pénalité",
            "selected_optimisation_budget_pct_notional": "Budget optim. (% nominal)",
            "selected_validation_rmse_pct_notional": "RMSE validation (% nominal)",
            "selected_validation_es_pct_notional": "ES validation (% nominal)",
            "selected_n_options_active": "Options actives", "status": "Statut",
        }).round(2))
        coverage = budget_level_status_table.pivot(
            index=["family", "penalty"], columns="level", values="n_admissible"
        ).reindex(
            index=pd.MultiIndex.from_product([MAIN_FAMILIES, GRID.penalties]),
            columns=["strict", "intermédiaire", "souple"],
        )
        fig, axis = plt.subplots(figsize=(8.7, 5.4))
        values = coverage.fillna(0).to_numpy(dtype=float)
        heatmap = axis.imshow(values, aspect="auto", cmap="Greens", vmin=0)
        axis.set_xticks(range(3), ["Strict · 5 %", "Intermédiaire · 10 %", "Souple · 15 %"])
        axis.set_yticks(range(len(coverage)), [
            f"{FAMILY_LABELS[family]} / {penalty.upper()}" for family, penalty in coverage.index
        ], fontsize=9)
        for row_index in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                count = int(values[row_index, column_index])
                axis.text(column_index, row_index, str(count) if count else "aucun",
                          ha="center", va="center", fontsize=9,
                          color="white" if count > values.max() / 2 else "black")
        axis.set_title("Politiques admissibles en validation sous chaque plafond ES commun")
        fig.colorbar(heatmap, ax=axis, label="Nombre de candidats admissibles")
        fig.tight_layout()
        HYPERPARAMETER_FIGURES["es_budget_coverage_summary"] = fig
        plt.show()
        if SHOW_TECHNICAL_DETAILS:
            print("Détails complets : références alpha, filtres et tous les profils ES :")
            display(tail_alpha_reference_table)
            display(budget_filter_table)
            display(lambda_profile_table)
            display(budget_profile_table)
            display(budget_level_status_table)
        for (family, penalty), group in budget_profile_table.groupby(["family", "penalty"]):
            identity = [column for column in ("alpha", "l1_ratio", "es_budget", "support_id") if column in group]
            n_distinct = group[identity].drop_duplicates().shape[0]
            if n_distinct < 3:
                print(
                    f"{FAMILY_LABELS[family]} / {penalty} : {n_distinct} politique(s) distincte(s) "
                    "derrière les trois profils de budget ES. La grille ne montre "
                    "pas trois compromis empiriquement différents."
                )
        """
    ),
    markdown(
        r"""
        ## 6. Grille d’importance sampling

        On **fige tous les portefeuilles retenus en section 5** : jusqu'à trois profils
        par objectif ES, norme et famille, à condition qu'ils aient passé leurs filtres.
        Aucune quantité d'option, aucun alpha et aucun budget n'est réoptimisé ici.
        Les supports L0 gardent leur statut heuristique. Si une norme n'a aucun profil
        admissible, son absence est signalée ; on ne fabrique pas de portefeuille.

        Chaque mélange IS est répété sur plusieurs graines. Pour une graine et un
        mélange, **les mêmes trajectoires servent à tous les portefeuilles** ; les
        poids de vraisemblance $dP/dQ$ corrigent la distribution simulée. Un pilote
        Monte-Carlo standard fournit, pour chaque portefeuille, l'écart-type de
        référence de son estimation d'ES 97,5 %. Le score d'un mélange est son
        **pire ratio d'écarts-types IS/MC parmi les portefeuilles** : moins de 1
        signifie une précision supérieure au MC dans ce pilote. Nous écartons
        d'abord les mélanges dont l'ESS globale minimale est inférieure à 20 %.
        Le mélange retenu est celui du plus petit pire ratio ; l'ESS de queue
        départage les égalités. **Le MC standard participe lui aussi au choix** :
        son rapport vaut 1 et il reste retenu si aucun mélange IS ne fait mieux
        sur ce critère. Dans ce cas, une composante à tilt nul sert seulement
        de représentation compatible avec les expériences du notebook principal ;
        elle ne constitue pas une méthode IS distincte. On ne sélectionne jamais la plus petite valeur
        estimée d'ES. Le nombre affiché de profils compte les **étiquettes**
        retenues : plusieurs profils peuvent désigner des poids identiques, sans
        modifier un critère de pire cas. L'écart entre les ES moyennes IS et MC
        reste affiché comme **diagnostic de compatibilité**, sans servir à choisir
        une estimation favorable. Le pilote utilise trois graines en FAST et trente
        en REPORT ; la décision FAST reste exploratoire. Les graines supplémentaires
        rendent la comparaison de précision plus fiable, sans garantir qu'un mélange
        IS mal ciblé deviendra meilleur que le MC.

        Les candidats sont des **mélanges distincts, pas les points d'une grille
        continue**. Le tableau sous cette explication donne, pour chacun, les
        déplacements gaussiens (en écarts-types) et la part de trajectoires
        simulées avec chaque composante. Ces parts ne sont **pas** des probabilités
        d'événements rares sous la loi d'origine. Les graphiques montrent donc
        des points non reliés et reprennent les mêmes libellés explicites.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.importance_sampling import (
            compare_fixed_policy_importance_mixtures,
        )
        from autocall_replication.replication.hyperparameter_study import (
            fixed_tail_profile_policies,
            importance_candidate_dicts,
        )

        fixed_tail_policies = fixed_tail_profile_policies(tail_grid_results)
        importance_results = {}
        importance_summaries = []
        importance_policy_summaries = []
        importance_details = []
        for family, stable_result in stable_profile_results.items():
            policies = fixed_tail_policies.get(family, [])
            if not policies:
                print(f"{FAMILY_LABELS[family]} : aucune politique ES admissible en section 5 ; mélange IS non choisi.")
                continue
            print(
                f"{FAMILY_LABELS[family]} : {len(policies)} profils ES figés, "
                f"normes présentes = {sorted(set(item['penalty'] for item in policies))}."
            )
            result = compare_fixed_policy_importance_mixtures(
                base_result=stable_result, product=prod, spot0=spot0,
                valuation_date=valuation_date, maturity_date=maturity_date,
                rate=rate, dividend_yield=dividend_yield, vol=vol,
                policies=policies,
                candidates=importance_candidate_dicts(GRID),
                seeds=CFG["importance_seeds"], n_paths=CFG["importance_paths"],
                es_level=0.975, minimum_effective_sample_ratio=0.20,
            )
            importance_results[family] = result
            importance_summaries.append(result["summary"].assign(family=family))
            importance_policy_summaries.append(result["policy_summary"].assign(family=family))
            importance_details.append(result["details"].assign(family=family))

        importance_summary = pd.concat(importance_summaries, ignore_index=True) if importance_summaries else pd.DataFrame()
        importance_policy_summary = pd.concat(importance_policy_summaries, ignore_index=True) if importance_policy_summaries else pd.DataFrame()
        importance_details = pd.concat(importance_details, ignore_index=True) if importance_details else pd.DataFrame()
        is_mixture_specs = [(-1, (0.0,), (1.0,))] + [
            (index, tilts, probabilities)
            for index, (tilts, probabilities) in enumerate(GRID.importance_candidates)
        ]
        is_mixture_labels = {
            index: ("MC standard" if index == -1 else "IS") + "\n" + "\n".join(
                f"{tilt:g} : {probability:.0%}"
                for tilt, probability in zip(tilts, probabilities)
            )
            for index, tilts, probabilities in is_mixture_specs
        }
        is_mixture_descriptions = {
            index: ("MC standard — " if index == -1 else "IS — ") + " ; ".join(
                f"{tilt:g} : {probability:.0%}"
                for tilt, probability in zip(tilts, probabilities)
            )
            for index, tilts, probabilities in is_mixture_specs
        }
        is_mixture_positions = {
            index: position for position, (index, _, _) in enumerate(is_mixture_specs)
        }
        print("Lecture des candidats : déplacement gaussien (écarts-types) → part des trajectoires simulées.")
        display(pd.DataFrame([
            {
                "Méthode": "MC standard" if index == -1 else "Importance sampling",
                "Composantes du mélange": " ; ".join(
                    f"{tilt:g} écart-type : {probability:.0%}"
                    for tilt, probability in zip(tilts, probabilities)
                ),
            }
            for index, tilts, probabilities in is_mixture_specs
        ]))
        if not importance_summary.empty:
            importance_summary["mixture_description"] = importance_summary["candidate_index"].map(is_mixture_descriptions)
        print("Synthèse à reporter — précision au pire portefeuille et ESS par mélange IS :")
        if importance_summary.empty:
            print("Aucune politique ES admissible : comparaison MC/IS non effectuée.")
        else:
            display(importance_summary[[column for column in (
                "family", "mixture_description", "n_policies", "worst_precision_ratio_to_mc",
                "median_precision_ratio_to_mc", "effective_sample_ratio_min",
                "tail_ess_min", "recommended"
            ) if column in importance_summary]].round(3))
        for family, result in importance_results.items():
            if result["recommended_candidate_index"] == -1:
                print(
                    f"{FAMILY_LABELS[family]} : MC standard retenu. "
                    "Aucun mélange IS testé n'améliore le pire rapport d'écarts-types."
                )
        if not importance_policy_summary.empty:
            print("Profils du mélange retenu — ratio de précision IS/MC par politique (plus bas = mieux) :")
            display(importance_policy_summary.loc[
                importance_policy_summary["recommended"], [
                    "family", "penalty", "objective", "profile", "es_mean",
                    "standard_mc_es_mean", "es_mean_difference_to_mc",
                    "es_std", "standard_mc_es_std", "precision_ratio_to_mc", "tail_ess_min",
                ]
            ].round(3))
        if SHOW_TECHNICAL_DETAILS:
            display(importance_summary)
            display(importance_policy_summary)
            display(importance_details)

        if not importance_summary.empty:
            fig, axes = plt.subplots(1, 2, figsize=(16, 6.0))
            for family, group in importance_summary.groupby("family", sort=False):
                # Décaler légèrement les familles : leurs points MC/ESS se superposent souvent.
                family_offset = -0.09 if family == "calls_puts" else 0.09
                positions = group["candidate_index"].map(is_mixture_positions) + family_offset
                color = "tab:blue" if family == "calls_puts" else "tab:orange"
                axes[0].scatter(positions, group["worst_precision_ratio_to_mc"], s=70, color=color, label=FAMILY_LABELS[family])
                axes[1].scatter(positions, group["effective_sample_ratio_min"], s=70, color=color, label=FAMILY_LABELS[family])
                recommended = group.loc[group["recommended"]]
                selected_positions = recommended["candidate_index"].map(is_mixture_positions) + family_offset
                axes[0].scatter(selected_positions, recommended["worst_precision_ratio_to_mc"], marker="*", s=210, color=color, edgecolor="black", zorder=5)
                axes[1].scatter(selected_positions, recommended["effective_sample_ratio_min"], marker="*", s=210, color=color, edgecolor="black", zorder=5)
            axes[0].axhline(1.0, color="black", linestyle=":", label="Même précision que MC")
            axes[1].axhline(0.20, color="black", linestyle=":", label="Seuil ESS 20 %")
            axes[0].set_title("Pire ratio de précision IS/MC parmi les politiques")
            axes[0].set_ylabel("Écart-type IS / écart-type MC ; plus bas = mieux")
            axes[1].set_title("Qualité des poids : ESS minimale")
            axes[1].set_ylabel("Ratio ESS / nombre de trajectoires")
            for axis in axes:
                axis.set_xticks(
                    range(len(is_mixture_specs)),
                    [is_mixture_labels[index] for index, _, _ in is_mixture_specs],
                    fontsize=8,
                )
                axis.set_xlim(-0.35, len(is_mixture_specs) - 0.65)
                axis.set_xlabel("Méthode testée · déplacement : part simulée")
                axis.grid(alpha=0.25)
                axis.legend()
            fig.suptitle("Choix d’un mélange IS robuste pour toutes les politiques ES retenues — étoile = recommandation")
            fig.tight_layout(rect=(0, 0, 1, 0.94))
            HYPERPARAMETER_FIGURES["importance_sampling_grid"] = fig
            plt.show()
            for family, group in importance_policy_summary.loc[
                importance_policy_summary["candidate_index"].ge(0)
            ].groupby("family", sort=False):
                heat = group.pivot(index="policy_key", columns="candidate_index", values="precision_ratio_to_mc")
                heat = heat.sort_index()
                fig, axis = plt.subplots(figsize=(11, max(6.0, 0.35 * len(heat) + 2.5)))
                values = heat.to_numpy(dtype=float)
                vmax = max(2.0, float(np.nanmax(values)))
                im = axis.imshow(values, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=vmax)
                axis.set_yticks(np.arange(len(heat)), heat.index, fontsize=8)
                chosen = importance_results[family]["recommended_candidate_index"]
                axis.set_xticks(np.arange(len(heat.columns)), [
                    is_mixture_labels[value] + ("\n★ retenu" if value == chosen else "")
                    for value in heat.columns
                ], fontsize=8)
                axis.set_title(
                    f"{FAMILY_LABELS[family]} — précision IS/MC par portefeuille ES figé"
                    + ("\nMC standard retenu ; mélanges IS affichés pour diagnostic" if chosen == -1 else "")
                )
                axis.set_xlabel("Mélange IS testé · déplacement : part simulée")
                fig.colorbar(im, ax=axis, label="Écart-type IS / écart-type MC (moins = mieux)")
                fig.tight_layout()
                HYPERPARAMETER_FIGURES[f"importance_policy_precision_{family}"] = fig
                plt.show()
        """
    ),
    markdown(
        r"""
        ## 7. Fiche de décision — hyperparamètres

        **Question de cette section : quels réglages transmettre au notebook principal,
        et avec quelles réserves ?** Trois tableaux courts séparent : (1) la
        régularisation RMSE, (2) le contrôle ES sous budget, (3) la méthode de
        mesure MC ou IS. Pour la régularisation, seul le profil compromis est
        montré ici ; les profils performance/parcimonie, les alphas temporels
        de la section 1.1 et les résultats des autres normes restent dans les
        exports complets. L'expérience 2×2 de contrôle ES du notebook principal
        importe actuellement les budgets **Elastic Net** seulement ; les autres
        normes de la section 5 sont des comparaisons de recherche, pas des choix
        supprimés.

        **Règle de lecture.** Un RMSE ou un ES mesuré dans deux expériences de
        validation différentes ne doit pas être classé dans un tableau commun.
        Les alertes ci-dessous décrivent les limites du choix, sans score global.
        Le test final reste réservé. Les coûts, la liquidité et le financement
        empêchent une interprétation de couverture immédiatement négociable ;
        l'objet du projet est d'abord un cadre mathématique reproductible de
        réplication et de sélection de modèle. Les tableaux intégraux et
        l'ancien graphique transversal sont toujours exportés pour l'audit,
        mais ne surchargent plus la lecture normale.
        """
    ),
    code(
        r"""
        decision_rows = []
        for method, table, alpha_column in (
            ("RMSE régularisée", final_profile_table, "alpha_relative"),
            ("RMSE + lambda ES", lambda_profile_table, "alpha_relative_tail"),
            ("RMSE sous budget ES", budget_profile_table, "alpha_relative_tail"),
        ):
            for _, row in table.iterrows():
                decision_rows.append({
                    "family": row["family"], "penalty": row["penalty"],
                    "method": method, "profile": row["profile"],
                    "alpha_relative": row.get(alpha_column, np.nan),
                    "l1_ratio": row.get("l1_ratio", np.nan),
                    "lambda_es": row.get("lambda_es", np.nan),
                    "es_budget_pct_notional": row.get("risk_limit_es", np.nan) * 100.0 / prod.notional,
                    "optimisation_budget_pct_notional": row.get("es_budget", np.nan) * 100.0 / prod.notional,
                    "validation_rmse_pct_notional": row["validation_rmse"] * 100.0 / prod.notional,
                    "validation_mae_pct_notional": row.get("validation_mae", np.nan) * 100.0 / prod.notional,
                    "validation_var_pct_notional": row.get("validation_var", np.nan) * 100.0 / prod.notional,
                    "validation_es_pct_notional": row.get("validation_es", np.nan) * 100.0 / prod.notional,
                    "n_options_active": row["n_options_active"],
                    "selection_status": "retenu",
                })
        for family in MAIN_FAMILIES:
            for penalty in GRID.penalties:
                for profile, cap in zip(
                    ("es_priority", "compromise", "rmse_priority"),
                    GRID.es_budget_pct_notional,
                ):
                    if not any(
                        row["family"] == family and row["penalty"] == penalty
                        and row["method"] == "RMSE sous budget ES"
                        and row["profile"] == profile
                        for row in decision_rows
                    ):
                        decision_rows.append({
                            "family": family, "penalty": penalty,
                            "method": "RMSE sous budget ES", "profile": profile,
                            "alpha_relative": np.nan, "l1_ratio": np.nan,
                            "lambda_es": np.nan, "es_budget_pct_notional": cap,
                            "optimisation_budget_pct_notional": np.nan,
                            "validation_rmse_pct_notional": np.nan,
                            "validation_mae_pct_notional": np.nan,
                            "validation_var_pct_notional": np.nan,
                            "validation_es_pct_notional": np.nan,
                            "n_options_active": np.nan,
                            "selection_status": "aucun candidat sous ce plafond commun en validation",
                        })
        decision_synthesis = pd.DataFrame(decision_rows)
        decision_synthesis_compact = decision_synthesis.loc[
            decision_synthesis["profile"].eq("compromise")
        ].copy().sort_values(["family", "penalty", "method"])
        decision_report_table = decision_synthesis_compact[[
            "family", "penalty", "method", "validation_rmse_pct_notional",
            "validation_es_pct_notional", "n_options_active", "selection_status",
        ]].copy()
        if SHOW_TECHNICAL_DETAILS:
            print("Audit transversal — mesures de validations différentes, non classables ensemble :")
            display(decision_report_table.rename(columns={
                "family": "Famille", "penalty": "Pénalité", "method": "Méthode",
                "validation_rmse_pct_notional": "RMSE validation (% nominal)",
                "validation_es_pct_notional": "ES validation (% nominal)",
                "n_options_active": "Options actives", "selection_status": "Statut",
            }).round(2))

        # Fiches prudentes : aucune métrique manquante n'est reconstituée depuis
        # une autre méthode. L'ES des politiques RMSE vient du contrôle 4.1,
        # effectué sur une validation indépendante avec les mêmes poids figés.
        regularized_tail = (
            alpha_tail_table[["family", "penalty", "solution_index", "validation_mae", "validation_var", "validation_es"]]
            .drop_duplicates(["family", "penalty", "solution_index"])
            .rename(columns={
                "validation_mae": "regularized_validation_mae",
                "validation_var": "regularized_validation_var",
                "validation_es": "regularized_validation_es",
            })
            if not alpha_tail_table.empty else pd.DataFrame(columns=[
                "family", "penalty", "solution_index", "regularized_validation_mae",
                "regularized_validation_var", "regularized_validation_es",
            ])
        )
        regularized_stability = selected_profile_stability.loc[
            selected_profile_stability["profile"].eq("compromise"),
            ["family", "penalty", "solution_index", "n_options_active_mean",
             "support_pairwise_jaccard_median"],
        ].drop_duplicates(["family", "penalty", "solution_index"])
        decision_method_review_rows = []
        for row in decision_synthesis_compact.itertuples(index=False):
            family, penalty, method = row.family, row.penalty, row.method
            selected = (
                final_profile_table.loc[
                    final_profile_table["family"].eq(family)
                    & final_profile_table["penalty"].eq(penalty)
                    & final_profile_table["profile"].eq("compromise")
                ] if method == "RMSE régularisée" else pd.DataFrame()
            )
            es_pct = float(row.validation_es_pct_notional)
            mae_pct = float(row.validation_mae_pct_notional)
            var_pct = float(row.validation_var_pct_notional)
            size_note = "non évaluée"
            if not selected.empty:
                solution_index = int(selected.iloc[0]["solution_index"])
                tail_match = regularized_tail.loc[
                    regularized_tail["family"].eq(family)
                    & regularized_tail["penalty"].eq(penalty)
                    & regularized_tail["solution_index"].eq(solution_index)
                ]
                if not tail_match.empty:
                    tail_row = tail_match.iloc[0]
                    mae_pct = float(tail_row["regularized_validation_mae"]) * 100.0 / prod.notional
                    var_pct = float(tail_row["regularized_validation_var"]) * 100.0 / prod.notional
                    es_pct = float(tail_row["regularized_validation_es"]) * 100.0 / prod.notional
                stability_match = regularized_stability.loc[
                    regularized_stability["family"].eq(family)
                    & regularized_stability["penalty"].eq(penalty)
                    & regularized_stability["solution_index"].eq(solution_index)
                ]
                if not stability_match.empty and pd.notna(row.n_options_active):
                    stability_row = stability_match.iloc[0]
                    ratio = float(stability_row["n_options_active_mean"]) / max(float(row.n_options_active), 1.0)
                    jaccard = float(stability_row["support_pairwise_jaccard_median"])
                    size_note = f"taille ×{ratio:.1f} ; Jaccard {jaccard:.2f}"
                else:
                    ratio = np.nan
            else:
                ratio = np.nan

            parameters = [f"α rel. {row.alpha_relative:.2g}" if pd.notna(row.alpha_relative) else "α n.é."]
            if penalty == "elastic_net":
                parameters.append(f"ρ {row.l1_ratio:.2g}" if pd.notna(row.l1_ratio) else "ρ n.é.")
            if method == "RMSE + lambda ES":
                parameters.append(f"λ ES {row.lambda_es:.2g}" if pd.notna(row.lambda_es) else "λ ES n.é.")
            if method == "RMSE sous budget ES":
                parameters.append(
                    f"B optim. {row.optimisation_budget_pct_notional:.1f} %"
                    if pd.notna(row.optimisation_budget_pct_notional) else "B optim. n.é."
                )
                parameters.append(f"plafond décision {row.es_budget_pct_notional:.0f} %")

            if row.selection_status != "retenu":
                opinion = "Aucun candidat admis en validation ; ne pas conclure."
            elif not np.isfinite(es_pct):
                opinion = "ES non évalué ; couverture de queue indéterminée."
            elif RUN_MODE == "sprint":
                opinion = "Aperçu visuel seulement ; aucun jugement quantitatif."
            elif es_pct < 0.0:
                opinion = "ES signé négatif possible ; vérifier coût initial et surcouverture."
            elif method == "RMSE + lambda ES" and row.n_options_active >= 100:
                opinion = "Panier très fourni : résultat mathématique, pas recommandation pratique."
            elif es_pct > 15.0:
                opinion = "ES au-dessus de 15 % ; risque de queue préoccupant."
            elif method == "RMSE sous budget ES" and es_pct > float(row.es_budget_pct_notional):
                opinion = "Plafond ES non respecté en validation ; à écarter pour ce plafond."
            elif np.isfinite(ratio) and ratio >= 2.0:
                opinion = "Panier très sensible aux recalibrations ; prudence."
            elif method != "RMSE régularisée":
                opinion = "ES observé ; stabilité propre à cette méthode non évaluée."
            else:
                opinion = "Paramètres retenus ; validation finale dans le notebook principal."
            decision_method_review_rows.append({
                "family": family, "penalty": penalty, "method": method,
                "profile": row.profile, "parameters": " · ".join(parameters),
                "validation_rmse_pct_notional": row.validation_rmse_pct_notional,
                "validation_mae_pct_notional": mae_pct,
                "validation_var_pct_notional": var_pct,
                "validation_es_pct_notional": es_pct,
                "n_options_active": row.n_options_active,
                "stability_note": size_note, "provisional_opinion": opinion,
                "selection_status": row.selection_status,
            })
        decision_method_review = pd.DataFrame(decision_method_review_rows)
        if SHOW_TECHNICAL_DETAILS:
            print("Audit détaillé des profils compromis, par méthode et famille :")
            for method in ("RMSE régularisée", "RMSE + lambda ES", "RMSE sous budget ES"):
                for family in MAIN_FAMILIES:
                    subset = decision_method_review.loc[
                        decision_method_review["method"].eq(method)
                        & decision_method_review["family"].eq(family)
                    ]
                    if not subset.empty:
                        print(f"{method} — {FAMILY_LABELS[family]}")
                        display(subset.round(2).fillna("non évalué"))
        sampling_columns = [
            "family", "candidate_index", "mixture_description", "worst_precision_ratio_to_mc",
            "median_precision_ratio_to_mc", "effective_sample_ratio_min",
        ]
        sampling_decision_table = (
            importance_summary.loc[importance_summary["recommended"], sampling_columns].copy()
            if not importance_summary.empty else pd.DataFrame(columns=sampling_columns)
        )
        sampling_decision_table["method"] = np.where(
            sampling_decision_table["candidate_index"].eq(-1),
            "MC standard", "importance sampling",
        )
        synthesis_alert_rows = []
        for family in MAIN_FAMILIES:
            stability_family = stability_report_table.loc[stability_report_table["family"].eq(family)]
            worst_size = (
                stability_family.sort_values("size_multiplier", ascending=False).iloc[0]
                if not stability_family.empty else None
            )
            is_family = (
                importance_summary.loc[
                    importance_summary["family"].eq(family)
                    & importance_summary["candidate_index"].ge(0)
                    & importance_summary["passes_weight_diagnostics"]
                ] if not importance_summary.empty else pd.DataFrame()
            )
            best_is = (
                is_family.sort_values("worst_precision_ratio_to_mc").iloc[0]
                if not is_family.empty else None
            )
            selected_measure = sampling_decision_table.loc[
                sampling_decision_table["family"].eq(family), "method"
            ]
            medium_budget = budget_level_status_table.loc[
                budget_level_status_table["family"].eq(family)
                & budget_level_status_table["level"].eq("intermédiaire")
            ]
            synthesis_alert_rows.append({
                "family": family,
                "worst_size_penalty": worst_size["penalty"] if worst_size is not None else "non évalué",
                "worst_size_multiplier": worst_size["size_multiplier"] if worst_size is not None else np.nan,
                "best_is_worst_precision_ratio_to_mc": (
                    best_is["worst_precision_ratio_to_mc"] if best_is is not None else np.nan
                ),
                "selected_risk_measurement": selected_measure.iloc[0] if not selected_measure.empty else "non évalué",
                "n_penalties_under_10pct_es_cap": int(medium_budget["status"].eq("retenu").sum()),
            })
        synthesis_alert_table = pd.DataFrame(synthesis_alert_rows)
        from IPython.display import Markdown
        display(Markdown("### 7.1 Paramètres transmis au notebook principal"))
        regularisation_compromise = final_profile_table.loc[
            final_profile_table["profile"].eq("compromise"),
            ["family", "penalty", "solution_index", "alpha_relative", "l1_ratio",
             "validation_rmse", "n_options_active"],
        ].copy()
        stability_compromise = selected_profile_stability.loc[
            selected_profile_stability["profile"].eq("compromise"),
            ["family", "penalty", "solution_index", "n_options_active_mean"],
        ].drop_duplicates(["family", "penalty", "solution_index"])
        regularisation_decision_table = regularisation_compromise.merge(
            stability_compromise,
            on=["family", "penalty", "solution_index"], how="left",
        ).drop(columns="solution_index")
        regularisation_decision_table["validation_rmse"] *= 100.0 / prod.notional
        print("Régularisation RMSE — profil compromis ; les deux autres profils sont exportés.")
        display(regularisation_decision_table.rename(columns={
            "family": "Famille", "penalty": "Norme", "alpha_relative": "α relatif",
            "l1_ratio": "ρ", "validation_rmse": "RMSE valid. (% nominal)",
            "n_options_active": "Options initiales",
            "n_options_active_mean": "Options moy. après recalibrations",
        }).round(3).fillna("—"))

        imported_budget = budget_profile_table.loc[
            budget_profile_table["penalty"].eq("elastic_net")
            & budget_profile_table["profile"].eq("compromise"),
            ["family", "alpha_relative_tail", "l1_ratio", "es_budget",
             "risk_limit_es", "validation_es", "n_options_active"],
        ].copy()
        print("Contrôle ES — profils Elastic Net intermédiaires importés par l'expérience 2×2.")
        if imported_budget.empty:
            print("Aucun profil admissible : la promotion vers le notebook principal doit échouer.")
        else:
            for column in ("es_budget", "risk_limit_es", "validation_es"):
                imported_budget[column] *= 100.0 / prod.notional
            display(imported_budget.rename(columns={
                "family": "Famille", "alpha_relative_tail": "α relatif ES",
                "l1_ratio": "ρ", "es_budget": "Budget optim. (%)",
                "risk_limit_es": "Plafond valid. (%)", "validation_es": "ES valid. (%)",
                "n_options_active": "Options",
            }).round(3))

        print("Mesure de l'ES — méthode sélectionnée par famille ; ratio de précision < 1 : IS plus précis que MC dans le pilote.")
        if sampling_decision_table.empty:
            print("Aucune méthode choisie : aucun portefeuille ES admissible à comparer.")
        else:
            display(sampling_decision_table[[
                "family", "method", "mixture_description",
                "worst_precision_ratio_to_mc", "effective_sample_ratio_min",
            ]].rename(columns={
                "family": "Famille", "method": "Méthode",
                "mixture_description": "Mélange retenu",
                "worst_precision_ratio_to_mc": "Pire ratio écart-type IS/MC",
                "effective_sample_ratio_min": "ESS min. / trajectoires",
            }).round(3))
        display(Markdown(
            "Les alphas des benchmarks temporels viennent de la section 1.1 ; "
            "les essais ES pénalisés et les autres normes ES restent dans la section 5 "
            "et les exports, mais ne sont pas importés par l'expérience 2×2 actuelle."
        ))

        if SHOW_TECHNICAL_DETAILS:
            print("Audit des signaux par famille :")
            display(synthesis_alert_table.round(3))

        from matplotlib.lines import Line2D

        # Vue synthétique retenue pour le rapport : elle répond à une seule question,
        # le compromis entre précision et nombre total d'options. Les diagnostics de
        # robustesse et de queue restent dans leurs figures dédiées.
        fig, tradeoff_axis = plt.subplots(figsize=(10.5, 5.6), constrained_layout=True)
        family_colors = {"calls_puts": "#2563a6", "full": "#d97706"}
        penalty_markers = {"l0": "s", "l1": "o", "l2": "^", "elastic_net": "D"}
        annotation_offsets = {
            "l0": (6, 5), "l1": (6, -12), "l2": (6, 5), "elastic_net": (6, 7),
        }

        decision_plot = final_profile_table.loc[
            final_profile_table["profile"].eq("compromise")
        ].drop_duplicates(["family", "penalty", "solution_index"]).copy()
        decision_plot["validation_rmse_pct"] = (
            decision_plot["validation_rmse"] * 100.0 / prod.notional
        )
        for row in decision_plot.itertuples():
            tradeoff_axis.scatter(
                row.n_options_active, row.validation_rmse_pct, s=85,
                marker=penalty_markers[row.penalty], color=family_colors[row.family],
                edgecolor="white", linewidth=0.7, zorder=3,
            )
            tradeoff_axis.annotate(
                row.penalty.upper(), (row.n_options_active, row.validation_rmse_pct),
                xytext=annotation_offsets[row.penalty], textcoords="offset points", fontsize=8,
            )
        tradeoff_axis.set_xscale("log")
        tradeoff_axis.set_xlabel("Options actives dans toute la politique (axe logarithmique)")
        tradeoff_axis.set_ylabel("RMSE de validation (% du nominal)")
        tradeoff_axis.grid(alpha=0.22)

        family_handles = [
            Line2D([], [], linestyle="None", marker="o", color=color, label=FAMILY_LABELS[family])
            for family, color in family_colors.items()
        ]
        tradeoff_axis.legend(
            handles=family_handles, title="Famille", loc="upper right",
            ncol=2, fontsize=8, title_fontsize=8,
        )
        fig.suptitle(
            "Profils compromis : RMSE et nombre d'options",
            fontsize=14,
        )
        HYPERPARAMETER_FIGURES["decision_dashboard"] = fig
        plt.close(fig)  # Conservé dans les exports, masqué dans la fiche de décision.

        size_alerts = stability_size_diagnostic.loc[
            stability_size_diagnostic["size_multiplier"].ge(2.0)
        ]
        if size_alerts.empty:
            size_message = "Aucune politique finale ne dépasse le signal descriptif de taille ×2 dans ce run."
        else:
            worst = size_alerts.sort_values("size_multiplier", ascending=False).iloc[0]
            size_message = (
                f"{len(size_alerts)} politique(s) distincte(s) ont une taille moyenne au moins doublée. "
                f"Cas le plus marqué : {FAMILY_LABELS[worst['family']]} / {worst['penalty'].upper()}, "
                f"{int(worst['base_n_options_active'])} options initiales contre "
                f"{worst['n_options_active_mean']:.1f} après recalibration en moyenne."
            )
        missing_caps = budget_level_status_table.loc[budget_level_status_table["status"].ne("retenu")]
        if missing_caps.empty:
            budget_message = "Tous les couples famille/pénalité ont au moins un candidat sous chacun des trois plafonds en validation."
        else:
            examples = "; ".join(
                f"{FAMILY_LABELS[row.family]}/{row.penalty.upper()} ({row.level})"
                for row in missing_caps.head(4).itertuples()
            )
            suffix = "…" if len(missing_caps) > 4 else "."
            budget_message = f"{len(missing_caps)} niveau(x) sans candidat admissible en validation : {examples}{suffix}"
        is_alerts = []
        for row in synthesis_alert_table.itertuples():
            if row.selected_risk_measurement == "MC standard":
                is_message = (
                    f"MC standard retenu ; meilleur IS admissible : ratio {row.best_is_worst_precision_ratio_to_mc:.2f}."
                    if np.isfinite(row.best_is_worst_precision_ratio_to_mc)
                    else "MC standard retenu ; aucun mélange IS admissible."
                )
            elif row.selected_risk_measurement == "importance sampling":
                is_message = f"IS retenu ; meilleur pire ratio IS/MC : {row.best_is_worst_precision_ratio_to_mc:.2f}."
            else:
                is_message = "Aucune comparaison MC/IS possible faute de portefeuille ES admissible."
            is_alerts.append(f"{FAMILY_LABELS[row.family]} : {is_message}")

        excluded_lambda = tail_grid_table.loc[
            tail_grid_table["objective"].eq("penalized_es")
            & ~tail_grid_table["lambda_selection_allowed"].astype(bool)
        ]
        dense_es = decision_synthesis_compact.loc[
            decision_synthesis_compact["method"].eq("RMSE + lambda ES")
            & decision_synthesis_compact["n_options_active"].ge(100)
        ]
        dense_message = (
            f"{len(dense_es)} compromis ES pénalisé(s) avec au moins 100 options "
            "(seuil descriptif) ; résultats mathématiques, pas paniers recommandés."
            if not dense_es.empty else "Aucun compromis ES pénalisé n'atteint 100 options."
        )
        dense_message += f" {len(excluded_lambda)} essai(s) à λ ES élevé exclus de la sélection et conservés dans l'audit."
        constrained_compromise = decision_synthesis_compact.loc[
            decision_synthesis_compact["method"].eq("RMSE sous budget ES")
            & decision_synthesis_compact["selection_status"].eq("retenu")
        ]
        if constrained_compromise.empty:
            boundary_message = "Aucun compromis ES contraint admis en validation."
        else:
            lower_alpha = min(GRID.tail_alpha_ratios)
            boundary_count = np.isclose(
                constrained_compromise["alpha_relative"].to_numpy(dtype=float),
                lower_alpha,
            ).sum()
            boundary_message = (
                f"{boundary_count}/{len(constrained_compromise)} compromis ES contraints à la borne "
                f"α relative {lower_alpha:g} ; ce n'est pas un optimum intérieur démontré."
            )
        display(Markdown(
            "### 7.2 Quatre réserves à conserver\n\n"
            + "\n".join([
                f"- **Bord de grille :** {boundary_message}",
                f"- **Taille des paniers :** {dense_message} {size_message}",
                "- **Stabilité L0 :** convergence et faible nombre initial d'options ne garantissent "
                "ni un support ni une taille stables après recalibration.",
                "- **Précision de l'ES :** " + " ".join(is_alerts)
                + " Un ratio IS/MC porte sur la dispersion de l'estimateur, pas sur la couverture.",
            ])
            + "\n\n**Plafonds ES :** " + budget_message
        ))
        display(Markdown(
            "### 7.3 Ce que la sélection ne démontre pas\n\n"
            "Les plafonds 5/10/15 % sont des niveaux de recherche, non des limites de desk. "
            "Le test final reste fermé ; aucune comparaison globale entre méthodes "
            "n'est déduite de validations différentes. Les coûts, la liquidité et "
            "le financement devront être précisés avant toute conclusion économique."
            + (" **SPRINT est uniquement un aperçu visuel : ces chiffres ne fondent aucun choix.**"
               if RUN_MODE == "sprint" else "")
        ))
        """
    ),
    markdown(
        r"""
        ## 8. Export permanent

        Tous les points des grilles, les résultats multi-graines et les figures sont conservés dans
        un dossier horodaté. Aucun ancien dossier n’est supprimé. La sélection exportée garde le
        statut `reserved_not_evaluated`.

        La promotion reste désactivée par défaut. Après inspection, définir
        `PROMOTE_THIS_RUN = True` puis réexécuter uniquement la dernière cellule pour rendre cette
        sélection disponible au notebook principal.
        """
    ),
    code(
        r"""
        from autocall_replication.replication.hyperparameter_study import (
            export_hyperparameter_study,
            promote_hyperparameter_selection,
        )
        from autocall_replication.research_presentation import build_report_views

        final_profile_table = pd.concat(
            [result["profiles"] for result in stable_profile_results.values()],
            ignore_index=True,
        )
        final_elastic_pairs = final_profile_table.loc[
            final_profile_table["penalty"].eq("elastic_net"),
            ["family", "profile", "l1_ratio", "alpha_relative"],
        ].rename(columns={"l1_ratio": "searched_l1_ratio"})
        selected_profiles = {
            "exploratory_benchmarks": benchmark_alpha_selected.astype(object).where(
                pd.notna(benchmark_alpha_selected), None
            ).to_dict(orient="records"),
            "exploratory_missing": benchmark_alpha_missing.to_dict(orient="records"),
            "regularisation": final_profile_table.to_dict(orient="records"),
            "es_selection_profiles": es_selection_profiles.astype(object).where(
                pd.notna(es_selection_profiles), None
            ).to_dict(orient="records"),
            # Compatibilité avec le notebook principal actuel : son expérience 2x2
            # utilise encore Elastic Net. Les autres normes restent exportées.
            "lambda_es": lambda_profile_table.loc[
                lambda_profile_table["penalty"].eq("elastic_net")
            ].to_dict(orient="records"),
            "es_budget": budget_profile_table.loc[
                budget_profile_table["penalty"].eq("elastic_net")
            ].to_dict(orient="records"),
            "lambda_es_all_norms": lambda_profile_table.to_dict(orient="records"),
            "es_budget_all_norms": budget_profile_table.to_dict(orient="records"),
            "importance_sampling": importance_summary.loc[
                importance_summary.get("recommended", False)
            ].to_dict(orient="records") if not importance_summary.empty else [],
            "elastic_net_profile_pairs": final_elastic_pairs.to_dict(orient="records"),
            "tail_risk_reference_elastic_net_rho": selected_rho,
            "selected_importance_mixture": {
                family: (
                    {"method": "standard_mc", "tilts": (0.0,), "mixture_probabilities": (1.0,)}
                    if result["recommended_candidate_index"] == -1
                    else {"method": "importance_sampling", **importance_candidate_dicts(GRID)[result["recommended_candidate_index"]]}
                )
                for family, result in importance_results.items()
                if result["recommended_candidate_index"] is not None
            },
        }
        export_tables = {
            "report_temporal_alpha": benchmark_alpha_report_table,
            "report_regularisation_compromise": base_profile_report_table,
            "report_l0_initialisation": l0_initialization_report_table,
            "report_final_hyperparameters": final_profile_report_table,
            "report_stability_worst_size_drift": stability_report_table,
            "report_es_lambda_compromise": lambda_report_table,
            "report_es_budget_intermediate": budget_report_table,
            "report_decision_overview": decision_report_table,
            "report_decision_method_review": decision_method_review,
            "report_decision_alerts": synthesis_alert_table,
            "exploratory_alpha_grid": benchmark_alpha_table,
            "exploratory_alpha_selected": benchmark_alpha_selected,
            "exploratory_alpha_missing": benchmark_alpha_missing,
            "exploratory_l0_initialization_audit": benchmark_l0_initialization_audit,
            "alpha_grid": base_alpha_table,
            "alpha_profiles": base_profile_table,
            "elastic_net_rho_grid": rho_table,
            "elastic_net_rho_profiles": rho_profile_table,
            "elastic_net_preliminary_pairs": selected_rho_table,
            "elastic_net_selected_pairs": final_elastic_pairs,
            "l0_initialization_audit": l0_initialization_audit,
            "stability_details": stability_details,
            "stability_summary": stability_summary,
            "selected_stability_details": selected_stability_details,
            "selected_stability_summary": selected_profile_stability,
            "stability_size_diagnostic": stability_size_diagnostic,
            "regularization_filter_flow": regularization_filter_table,
            "alpha_tail_frontier": alpha_tail_table,
            "alpha_tail_comparison": alpha_tail_comparison,
            "es_selection_profiles": es_selection_profiles,
            "validation_profile_selection_comparison": validation_profile_selection_comparison,
            "tail_grid": tail_grid_table,
            "tail_alpha_references": tail_alpha_reference_table,
            "lambda_es_profiles": lambda_profile_table,
            "es_budget_profiles": budget_profile_table,
            "es_budget_level_status": budget_level_status_table,
            "es_budget_filter_flow": budget_filter_table,
            "importance_sampling_grid": importance_summary,
            "importance_sampling_policy_summary": importance_policy_summary,
            "importance_sampling_details": importance_details,
            "selected_regularisation_profiles": final_profile_table,
            "decision_synthesis": decision_synthesis,
            "decision_synthesis_compact": decision_synthesis_compact,
            "decision_method_review": decision_method_review,
            "sampling_decision": sampling_decision_table,
        }
        # Les CSV complets restent inchangés ; chaque synthèse possède son propre CSV.
        export_tables.update(build_report_views(export_tables))
        hyperparameter_export = export_hyperparameter_study(
            output_root=_project_root / "output" / "hyperparameters",
            run_mode=RUN_MODE, configuration=STUDY_CONFIGURATION,
            grid=GRID, tables=export_tables, figures=HYPERPARAMETER_FIGURES,
            selected_profiles=selected_profiles,
            policy_results=stable_profile_results,
            run_started_at=HYPERPARAMETER_RUN_STARTED_AT,
        )
        print("Recherche sauvegardée :", hyperparameter_export["run_dir"])
        print("Aucun ancien résultat n’a été supprimé.")

        """
    ),
    code(
        r"""
        if PROMOTE_THIS_RUN and RUN_MODE == "sprint":
            raise ValueError("Un run SPRINT ne peut pas être promu : aperçu visuel uniquement.")
        if PROMOTE_THIS_RUN:
            promoted_path = promote_hyperparameter_selection(
                source_run_dir=hyperparameter_export["run_dir"],
                destination=_project_root / "config" / f"selected_hyperparameters_{RUN_MODE}.json",
                current_configuration=STUDY_CONFIGURATION,
            )
            print("Sélection explicitement promue :", promoted_path)
        elif RUN_MODE == "sprint":
            print("Aperçu SPRINT sauvegardé sans promotion ; lancer ensuite le notebook principal en SPRINT.")
        else:
            print("Sélection non promue. Inspecter les résultats avant de passer PROMOTE_THIS_RUN à True.")
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
TARGET.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(TARGET)
