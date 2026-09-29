# Importance sampling — évaluation comparative du risque

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Les portefeuilles conditionnels ont déjà été sélectionnés et leur risque a été mesuré par Monte-Carlo standard. |
| **Problème** | Les scénarios rares qui pilotent l’Expected Shortfall peuvent être trop peu représentés et rendre son estimation instable. |
| **Méthode** | Ajouter un estimateur par importance sampling, corrigé par rapports de vraisemblance, sur exactement les mêmes portefeuilles figés. |
| **Modifications** | Ajout du simulateur pondéré, des diagnostics d’ESS, des intervalles bootstrap et d’une comparaison visuelle avec le Monte-Carlo standard. |
| **Résultats** | Les deux méthodes sont désormais comparables sans modifier les alphas ni les poids financiers ; l’intérêt de l’IS se juge sur la précision des métriques de queue. |

## Contexte

Les politiques conditionnelles de réplication sont calibrées et sélectionnées
avant l'analyse de risque. Le Monte-Carlo standard mesure ensuite la RMSE, la
VaR et l'Expected Shortfall du résidu `autocall - réplication` sur un
échantillon indépendant.

## Problème

Les niveaux ES 97,5 % et ES 99 % reposent sur une petite fraction des
trajectoires. Même avec un grand échantillon, peu de trajectoires décrivent les
régimes rares sans rappel, avec barrière touchée ou sous-réplication extrême.
L'estimation peut donc être instable et renseigne peu sur la structure de la
queue.

## Méthode

Un second moteur d'évaluation utilise un mélange gaussien :

- 50 % de trajectoires standards ;
- 30 % avec une inclinaison terminale de -1 écart-type ;
- 20 % avec une inclinaison terminale de -2 écarts-types.

La mesure cible reste le GBM risque-neutre original. Chaque trajectoire simulée
sous la proposition reçoit le poids de vraisemblance

\[
\omega_i=\frac{p(X_i)}{q(X_i)}.
\]

Les moyennes, fréquences, quantiles et Expected Shortfalls sont calculés avec
ces poids. L'Effective Sample Size contrôle leur concentration.

La distinction suivante est impérative :

- `w_j` : quantité financière du portefeuille, figée avant l'évaluation ;
- `omega_i` : poids statistique d'une trajectoire, utilisé uniquement dans les
  estimateurs de risque.

L'importance sampling ne recalcule ni alpha ni les quantités financières dans
cette phase.

## Modifications

- ajout du module `replication/importance_sampling.py` ;
- simulateur GBM par mélange gaussien avec rapport de vraisemblance exact ;
- métriques pondérées RMSE, VaR, ES et fréquence de sous-réplication ;
- diagnostics des poids, des composantes et de l'ESS ;
- bootstrap de l'ES 97,5 % ;
- évaluateur conditionnel indépendant conservant la politique figée ;
- comparaison explicite Monte-Carlo standard / importance sampling ;
- ajout d'une section méthodologique, de tableaux et de graphiques dans le
  notebook ;
- ajout de tests numériques et d'intégration.

## Résultats

Les contrôles automatisés vérifient actuellement :

- poids unitaires lorsque la déformation est nulle ;
- reproduction des métriques ordinaires avec des poids égaux ;
- cohérence de l'espérance du spot terminal sous repondération ;
- reproductibilité du bootstrap pondéré ;
- séparation des résultats standard et importance sampling ;
- conservation explicite des poids financiers dans l'évaluateur conditionnel.

Les résultats économiques MC/IS doivent être générés en exécutant la section
6.3 du notebook. Une différence ponctuelle n'est pas une amélioration : la
compatibilité des intervalles, l'ESS et la stabilité entre graines doivent être
examinées conjointement.

## Limites et prochaines étapes

La première proposition favorise une baisse terminale globale. Elle ne cible
pas encore directement les trajectoires proches du seuil de rappel, les
franchissements suivis d'un rebond ni une région précise de perte résiduelle.
Après validation contre le Monte-Carlo standard, les étapes suivantes sont :

1. analyser les scénarios qui contribuent réellement à l'ES ;
2. ajuster le mélange sans utiliser l'échantillon de test final ;
3. répéter l'expérience sur plusieurs graines ;
4. comparer la précision à temps de calcul égal ;
5. seulement ensuite, étudier une optimisation de portefeuille sensible à la
   queue comme expérience distincte.
