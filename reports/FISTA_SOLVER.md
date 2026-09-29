# Solveur parcimonieux FISTA

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Les pénalités L1 et Elastic Net doivent pouvoir produire de vrais zéros. |
| **Problème** | Le solveur lissé historique ne garantit pas l’annulation des poids. |
| **Méthode** | Résolution proximale accélérée FISTA avec indices non pénalisés. |
| **Modifications** | Ajout du solveur, de sa convergence et de tests numériques. |
| **Résultats** | L1 et Elastic Net disposent d’un solveur parcimonieux dédié. |


Date de validation : 17 août 2026

## 1. Objectif

Ajouter un véritable solveur L1 et Elastic Net capable de produire des poids
exactement nuls. Le solveur historique lisse la valeur absolue et encourage des
petits poids sans garantir leur annulation.

Le notebook n'est pas modifié à cette étape : il reste configuré avec
`SOLVER = "legacy"` jusqu'à la construction du protocole de comparaison.

## 2. Problèmes résolus

Pour L1, FISTA minimise :

\[
\frac{1}{2n}\lVert Xw-y\rVert_2^2 + \alpha\lVert w\rVert_1.
\]

Pour Elastic Net :

\[
\frac{1}{2n}\lVert Xw-y\rVert_2^2
+ \alpha\left(
\rho\lVert w\rVert_1
+ \frac{1-\rho}{2}\lVert w\rVert_2^2
\right).
\]

Les indices non pénalisés sont explicités dans `SolverConfig`. Par défaut,
`unpenalized_indices=(0,)` protège la première colonne, qui correspond au cash
dans les bases de réplication actuelles.

## 3. Implémentation

Le fichier `replication/optimization.py` propose maintenant deux solveurs :

- `legacy`, qui délègue encore à `fit_linear` ;
- `fista`, disponible pour `penalty="l1"` et
  `penalty="elastic_net"`.

FISTA utilise :

- la même normalisation RMS des colonnes que le solveur historique ;
- un seuillage proximal créant les zéros exacts ;
- la norme spectrale de la matrice pour calculer un pas stable ;
- un redémarrage adaptatif du momentum pour limiter les oscillations liées aux
  payoffs d'options fortement corrélés ;
- un critère relatif sur la variation des poids ;
- des métadonnées complètes : convergence, itérations, objectif et message.

Les configurations incompatibles, indices invalides et paramètres non finis
sont rejetés avec un message explicite.

## 4. Validation numérique

Les tests unitaires vérifient :

- des poids exactement nuls sous L1 ;
- l'absence de pénalisation du cash ;
- une sélection plus forte lorsque `alpha` augmente ;
- le support d'Elastic Net ;
- une valeur d'objectif finie ;
- les erreurs de configuration ;
- la non-régression exacte du solveur `legacy`.

Un test d'intégration permanent exécute FISTA dans les cinq pipelines : surface
de prix, payoff moyen, payoff pathwise, cashflows statiques et réplication
conditionnelle.

La validation globale termine avec **52 tests réussis sur 52**, 15 fichiers
Python syntaxiquement valides, deux notebooks JSON valides et un contrôle Ruff
réussi sur les fichiers ajoutés ou modifiés pour cette étape.

Avec `family="calls"`, `penalty="l1"` et `alpha=1e-2`, les cinq pipelines
convergent sur le scénario de test. Les nombres d'options actives observés sont
respectivement 31, 71, 25, 27 et, pour les modèles conditionnels, 4, 8, 5, 0 et
0 selon la date et l'état. Ces valeurs valident le fonctionnement technique ;
elles ne constituent pas encore une recommandation de portefeuille.

## 5. Limite observée

Pour `alpha=1e-4`, certains petits scénarios pathwise et statiques très mal
conditionnés atteignent `max_iter=5000` avant la tolérance demandée. FISTA
retourne alors le résultat avec `converged=False` et un message explicite.

Cette situation ne doit pas être masquée. La future étude du chemin de
régularisation devra :

- vérifier systématiquement `converged` ;
- publier le nombre d'itérations ;
- éventuellement augmenter `max_iter` ou adapter la tolérance ;
- ne comparer les portefeuilles qu'après contrôle de l'optimalité numérique.

## 6. Étapes suivantes

1. construire une grille d'`alpha` commune et reproductible ;
2. séparer entraînement, validation et test final ;
3. tracer la frontière erreur / nombre d'options / concentration ;
4. comparer `legacy`, FISTA-L1 et FISTA-Elastic Net ;
5. ajouter ultérieurement bid-ask, slippage et coûts de transaction au critère
   de sélection ;
6. étudier VPAL puis VarPro après stabilisation de cette base.
