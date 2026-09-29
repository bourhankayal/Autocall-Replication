# Fondation pour l'optimisation parcimonieuse

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | La réplication nécessitait une interface commune aux solveurs. |
| **Problème** | Comparer les méthodes sans confondre poids, parcimonie et exposition. |
| **Méthode** | Création d’une interface d’optimisation et de diagnostics de portefeuille. |
| **Modifications** | Ajout de SolverConfig, SolverResult et des métriques de concentration. |
| **Résultats** | La base permet de brancher et comparer plusieurs solveurs. |


Date de validation : 17 août 2026

## Objectif

Préparer la comparaison future de plusieurs normes et solveurs sans modifier les
résultats numériques historiques. Cette étape ajoute les instruments de mesure
et une interface d'optimisation ; elle n'ajoute encore aucun nouveau solveur.

## Diagnostics ajoutés

Le module `replication/portfolio_diagnostics.py` mesure notamment :

- le nombre total et le nombre actif d'instruments ;
- la proportion de positions actives ;
- le nombre d'options longues et courtes ;
- la somme des valeurs absolues des poids ;
- le poids maximal ;
- la concentration sur la première et les cinq premières options.

Un poids est actif si sa valeur absolue est strictement supérieure à `1e-6`.
Le cash est isolé des options. La somme des poids est expressément présentée
comme une quantité de contrats, et non comme une exposition monétaire.

## Interface des solveurs

Le module `replication/optimization.py` introduit :

- `SolverConfig` pour décrire solveur, pénalité et paramètres numériques ;
- `SolverResult` pour restituer poids et informations de convergence ;
- `solve_replication` comme point d'entrée commun ;
- `available_solvers` pour annoncer les solveurs disponibles.

Le seul solveur disponible à cette étape est `legacy`. Il délègue à
`fit_linear` avec les mêmes paramètres, afin de reproduire exactement le
comportement antérieur. Les benchmarks de surface de prix, payoff moyen,
payoff pathwise, cashflows statiques et réplication conditionnelle utilisent
désormais ce point d'entrée.

## Décisions reportées

- ajouter de vrais solveurs L1 et Elastic Net produisant des zéros exacts ;
- construire un chemin de régularisation plutôt que fixer le nombre d'options ;
- sélectionner ultérieurement le compromis avec bid-ask, slippage et coûts ;
- calculer l'exposition monétaire à partir des prix des instruments ;
- retirer `fit_linear` après migration complète ;
- explorer VarPro une fois le benchmark parcimonieux principal stabilisé.

## Validation

La validation couvre les cas nuls, les résidus numériques, le cash, les
positions longues et courtes, les concentrations, les tableaux conditionnels,
les entrées invalides et l'égalité exacte entre l'interface `legacy` et
`fit_linear`.

La commande globale valide 15 fichiers Python, les deux notebooks et **47 tests
automatisés**. Un smoke test supplémentaire confirme que les cinq pipelines
retournent les diagnostics et les métadonnées du solveur `legacy`.

## Migration du notebook

Le notebook de recherche utilise désormais une constante unique
`SOLVER = "legacy"`, transmise explicitement aux douze appels de benchmark. Il
n'importe plus directement `fit_linear` et présente, pour chaque expérience,
les métadonnées d'optimisation ainsi que les diagnostics de parcimonie. Les
tableaux de surface de prix incluent également le nombre d'options actives, les
positions longues/courtes et la concentration des poids.

Pour les expériences conditionnelles, les diagnostics sont affichés par date et
par état observable. Les deux anciennes sorties d'erreur enregistrées ont été
supprimées sans effacer les sorties réussies. Un test dédié verrouille désormais
ces propriétés. L'API publique de `replication/__init__.py` n'a pas été modifiée.
