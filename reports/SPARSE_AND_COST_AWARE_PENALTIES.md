# Pénalités L0 et sensibles aux coûts

## Résumé rapide

| Élément | Synthèse |
|---|---|
| **Contexte** | La réplication doit sélectionner des paniers parcimonieux sans fixer arbitrairement leur nombre de lignes. |
| **Problème** | L1 représente surtout un coût proportionnel au volume et ne représente pas directement un coût fixe par instrument. Les estimations de coûts actuelles ne sont pas encore assez fiables pour piloter la sélection économique. |
| **Méthode** | Ajout de L0 pénalisée, de L1 pondérée et d’une pénalité combinant coût fixe et proportionnel derrière l’interface commune des solveurs. |
| **Modifications** | Nouveau solveur proximal à seuillage dur, chemin d’alpha L0, propagation à la stabilité, retrait de Huber du notebook et tâches explicites de validation des coûts et d’optimisation CVaR. |
| **Résultats** | Les formulations sont testées. L0 est activée dans la recherche conditionnelle ; les formulations dépendant des coûts restent disponibles mais désactivées jusqu’à validation des coefficients économiques. |

## 1. Formulations

La cible de réplication est toujours décrite par la matrice de payoffs `A`, le
passif autocall `b` et les poids financiers `w`.

### L0 pénalisée

\[
\min_w \frac{1}{2n}\lVert Aw-b\rVert_2^2
+ \alpha_0\lVert w\rVert_0.
\]

Cette formulation ne fixe pas un nombre maximal d’instruments. Le paramètre
`alpha` représente le prix statistique de l’ajout d’une ligne. Le problème est
non convexe : le solveur utilise un gradient proximal avec seuillage dur et ne
certifie pas l’optimum global.

### L1 pondérée

\[
\min_w \frac{1}{2n}\lVert Aw-b\rVert_2^2
+ \alpha_1\sum_j c_j|w_j|.
\]

Le coefficient `c_j` représente un coût proportionnel par unité de position.
Les coûts sont appliqués aux poids financiers dans leurs unités originales,
même lorsque les colonnes du problème sont normalisées pour le solveur.

### Coût fixe et proportionnel

\[
\min_w \frac{1}{2n}\lVert Aw-b\rVert_2^2
+ \alpha_0\lVert w\rVert_0
+ \alpha_1\sum_j c_j|w_j|.
\]

Le premier terme représente le coût d’ouverture et de gestion d’une ligne. Le
second représente le coût qui augmente avec la quantité négociée.

## 2. Intégration au protocole

L0 est intégrée au chemin conditionnel en conservant :

- le split 60 % entraînement, 20 % validation et 20 % test fermé ;
- la sélection séparée au sein de chaque pénalité ;
- les filtres de nombre d’options, performance, Pareto et doublons ;
- dix recalibrations de stabilité ;
- l’évaluation indépendante du risque et du financement.

La référence d’alpha L0 est construite à partir du gradient du résidu après
ajustement des variables non pénalisées et du seuil dur du premier pas proximal.
Cette référence est algorithmique et ne transforme pas le problème en problème
convexe.

## 3. Décisions de prudence

Huber a été retirée des comparaisons du notebook. Son implémentation historique
reste isolée pour permettre une future comparaison complète des fonctions de
perte, distincte de l’étude des pénalités sur les poids.

L1 pondérée et la pénalité fixe + proportionnelle ne pilotent pas encore les
portefeuilles retenus. Avant leur activation, il faut revoir intégralement la
provenance et la qualité des coûts : bid-ask, profondeur, stale quotes,
multiplicateurs, slippage, liquidation anticipée et scénarios OTC des binaires.

## 4. Limites et prochaines validations

- tester L0 depuis plusieurs initialisations ;
- mesurer la stabilité de son support et la fréquence des minima locaux ;
- construire des chemins distincts pour les intensités fixe et proportionnelle ;
- éliminer les solutions économiquement quasi identiques ;
- comparer les méthodes à coût égal et à risque égal ;
- tester ultérieurement une fonction objectif combinant MSE et CVaR 97,5 %.
