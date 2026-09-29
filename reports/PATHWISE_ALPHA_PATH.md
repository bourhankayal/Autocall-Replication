# Chemin de régularisation pathwise

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Le benchmark pathwise doit sélectionner alpha sans utiliser le test final. |
| **Problème** | Éviter un alpha arbitraire et une contamination hors échantillon. |
| **Méthode** | Chemin logarithmique, split 60/20/20 et warm starts. |
| **Modifications** | Ajout du calcul d’alpha maximal et du statut de test réservé. |
| **Résultats** | Les candidats sont comparables sur un même dataset pathwise. |


Date de validation : 18 août 2026

## 1. Objectif

Explorer la relation entre pénalisation L1, erreur hors entraînement et
parcimonie sans choisir arbitrairement un nombre d'options ni contaminer le test
final.

Cette première implémentation concerne uniquement le benchmark de payoff
pathwise. L'extension aux cashflows statiques, au conditionnel, à la surface de
prix et au payoff moyen est inscrite dans la feuille de route.

## 2. Protocole

Les trajectoires sont simulées une seule fois puis séparées séquentiellement et
de manière reproductible :

- 60 % pour estimer les poids ;
- 20 % pour comparer les valeurs d'`alpha` ;
- 20 % réservés comme test final.

Aucune prédiction ni métrique n'est calculée sur le test final. Le résultat
porte explicitement le statut `reserved_not_evaluated`.

L'`alpha_max` est calculé après ajustement des variables non pénalisées. Il
correspond au niveau qui annule toutes les options et laisse le cash libre. La
grille contient 25 valeurs logarithmiques décroissantes entre `alpha_max` et
`0,001 × alpha_max`.

Les solutions sont calculées de la pénalisation la plus forte vers la plus
faible. Chaque solution convergée initialise la résolution suivante via le warm
start de FISTA.

## 3. Sorties produites

Pour chaque valeur d'`alpha`, la table contient :

- statut de convergence, itérations, objectif et message ;
- MAE, RMSE, erreur moyenne et erreur maximale sur train ;
- les mêmes métriques sur validation ;
- nombre et proportion d'options actives ;
- positions longues et courtes ;
- somme et maximum des poids absolus ;
- concentration sur la première et les cinq premières options ;
- appartenance ou non à la frontière de Pareto.

Une solution est dite dominée lorsqu'une autre solution convergée utilise au
plus autant d'options avec une RMSE de validation au plus aussi faible, et
améliore strictement au moins un de ces deux critères.

## 4. Expérience représentative

Configuration :

- autocall nominal 100, coupon 2 %, barrière 70 % ;
- famille `calls` ;
- 300 trajectoires ;
- graine 42 ;
- L1 avec FISTA ;
- 25 valeurs d'`alpha`.

Résultats structurels :

- `alpha_max = 1,418608` ;
- 180 trajectoires train ;
- 60 trajectoires validation ;
- 60 trajectoires test réservées ;
- 23 solutions convergées sur 25 ;
- 12 points sur la frontière de Pareto.

Extraits de la frontière :

| Alpha | Options actives | RMSE validation | MAE validation | Concentration top 5 |
|---:|---:|---:|---:|---:|
| 1,418608 | 0 | 5,3675 | 2,7100 | 0,0 % |
| 0,797742 | 1 | 5,1954 | 2,7185 | 100,0 % |
| 0,189174 | 10 | 4,2173 | 2,4390 | 71,5 % |
| 0,059822 | 20 | 3,2963 | 1,9168 | 73,0 % |
| 0,033640 | 32 | 2,9243 | 1,6404 | 52,9 % |
| 0,014186 | 44 | 2,6531 | 1,4983 | 57,0 % |
| 0,007977 | 60 | 2,6223 | 1,5046 | 48,4 % |

Ces résultats illustrent un compromis ; ils ne sélectionnent pas encore un
portefeuille final. La baisse de RMSE obtenue au-delà d'environ 40 options est
beaucoup plus faible que celle obtenue au début du chemin, mais cette observation
devra être confrontée aux futurs coûts de transaction.

## 5. Non-convergences

Deux solutions ont atteint `max_iter=5000` :

| Alpha | Options actives | RMSE validation |
|---:|---:|---:|
| 0,004486 | 75 | 2,8870 |
| 0,001419 | 121 | 3,4663 |

Elles sont conservées dans la table pour transparence mais exclues de la
frontière de Pareto et ne peuvent pas être retenues comme candidates valides.

La validation globale du projet termine désormais avec **71 tests réussis sur
71**, 16
fichiers Python syntaxiquement valides, deux notebooks JSON valides et un
contrôle Ruff réussi sur les fichiers de cette étape.

## 6. Modifications techniques

- `optimization.py` accepte un `initial_weights` facultatif pour FISTA ;
- les poids du warm start sont fournis dans les unités originales puis convertis
  dans les coordonnées normalisées du solveur ;
- les variables non pénalisées sont initialisées par moindres carrés ;
- `regularization_path.py` centralise split, `alpha_max`, grille, calibration,
  métriques et frontière de Pareto ;
- `pathwise_payoff.py` fournit `run_pathwise_regularization_path` et réutilise un
  dataset unique pour tous les alphas.

## 7. Limites et prochaines étapes

- aucun `alpha` n'est encore choisi automatiquement ;
- le test final ne doit être ouvert qu'après définition de la règle économique ;
- bid-ask, slippage et coûts de transaction ne sont pas encore disponibles ;
- la stabilité entre plusieurs graines reste à mesurer ;
- le protocole doit être adapté puis appliqué aux quatre autres benchmarks ;
- le protocole est désormais intégré au notebook dans une section dédiée ;
- cette section affiche le split, le statut du test final, la table complète, la
  frontière de Pareto, les non-convergences et deux graphiques de diagnostic ;
- elle ne choisit aucun `alpha`, n'ouvre pas le test final et ne modifie pas le
  solveur global `SOLVER = "legacy"` utilisé par les benchmarks historiques.

L'extension ultérieure à L2 et Elastic Net à ratio fixe, ainsi que la refonte de
l'affichage de parcimonie, sont documentées dans
`ALPHA_PENALTIES_AND_SPARSITY_DISPLAY.md`.
