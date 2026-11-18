# Importance sampling et contrôle direct de l’Expected Shortfall

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | La réplication conditionnelle réduit la RMSE globale mais peut augmenter le risque de sous-réplication extrême. |
| **Problème** | L’ancien ES empirique pouvait utiliser trop de masse à la VaR ; l’importance sampling restait uniquement un outil d’évaluation a posteriori. |
| **Méthode** | ES exact de Rockafellar--Uryasev, diagnostics complets des poids, calibration MC ou IS pondérée, puis optimisation RMSE seule, ES pénalisé ou ES contraint. |
| **Modifications** | Nouveau solveur de risque de queue, quatre expériences 2×2, frontières externes de `lambda_ES` et de budgets, décomposition des scénarios rares, tests et intégration au notebook/export. |
| **Résultats** | Les tests unitaires et un test d’intégration réel convergent. Le test final reste fermé ; les résultats économiques définitifs nécessitent un Run All puis une étude REPORT multi-graines. |

## 1. Convention de perte

Une ligne de la régression conditionnelle représente une trajectoire entière.
La perte de l’émetteur est

\[
L_i(w)=H_i-X_iw,
\]

où `H_i` est la somme actualisée des paiements de l’autocall et `X_i w` la
somme actualisée des paiements de la politique de réplication. Une valeur
positive est un shortfall : le portefeuille ne suffit pas à payer le client.

La mesure actuelle reste la mesure risque-neutre Black--Scholes. Elle doit être
présentée comme un risque de modèle, pas encore comme un ES économique réel.

## 2. Correction de la VaR et de l’ES

La moyenne naïve des observations `L >= VaR` est incorrecte lorsqu’une masse de
probabilité se trouve exactement sur la VaR. Elle peut alors utiliser plus que
les pires `1-q` pour cent. Le moteur commun standard/pondéré utilise désormais

\[
ES_q=VaR_q+\frac{\mathbb E[(L-VaR_q)_+]}{1-q}.
\]

La fonction retourne également la contribution exacte de chaque trajectoire à
la queue et son Effective Sample Size.

## 3. Importance sampling consolidé

Le mélange par défaut conserve les inclinaisons terminales `(0, -1, -2)` et les
probabilités `(0.50, 0.30, 0.20)`. Chaque trajectoire reçoit `dP/dQ`. Les
diagnostics exportés comprennent maintenant :

- moyenne, quantiles, minimum et maximum des poids ;
- coefficient de variation et poids normalisé maximal ;
- ESS global et ratio d’ESS ;
- entropie normalisée ;
- ESS de la queue pour chaque niveau de risque ;
- masse repondérée des composantes ;
- contribution à l’ES des régimes rappel, maturité et barrière touchée.

Une fonction de recherche externe compare plusieurs mélanges et plusieurs
graines. Elle classe les mélanges par précision inter-graines sous une exigence
minimale d’ESS, jamais par la valeur d’ES la plus faible afin d’éviter un biais
de sélection.

## 4. Trois objectifs d’optimisation

Le nouveau module `tail_risk_optimization.py` propose :

1. `rmse` : référence sans contrôle direct de la queue ;
2. `penalized_es` :

   \[
   RMSE(w)+\lambda_{ES}ES_q(w)+\alpha\Omega(w) ;
   \]

3. `constrained_es` :

   \[
   \min_w RMSE(w)+\alpha\Omega(w)
   \quad\text{sous}\quad ES_q(w)\leq B_{ES}.
   \]

Les poids statistiques sont uniformes en MC standard et proportionnels à
`dP/dQ` en importance sampling. Les pénalités directement admises sont L1, L2
et Elastic Net. L0 et L1/2 restent évaluées a posteriori, car leur combinaison
immédiate avec le contrôle de queue cumulerait deux non-convexités.

## 5. Quatre expériences principales

Le notebook compare :

| Calibration | Objectif |
|---|---|
| Monte-Carlo standard | RMSE |
| Importance sampling pondéré | RMSE |
| Monte-Carlo standard | RMSE sous contrainte d’ES |
| Importance sampling pondéré | RMSE sous contrainte d’ES |

Les nœuds, instruments, pénalité, alpha et échantillon indépendant d’évaluation
sont communs. Cela isole l’effet de l’échantillonnage et celui de la contrainte.
Le budget utilisé dans le notebook vaut provisoirement 90 % de l’ES de la
calibration standard ; il s’agit d’une démonstration, pas du budget final.

## 6. Profondeur et concentration de la queue

L’ES 97,5 % reste la mesure centrale, mais elle est désormais accompagnée de
l’ES 95 %, de l’ES 99 % et du ratio `ES 99 / ES 97,5`. Une forte augmentation
du ratio indique que quelques scénarios très profonds dominent la queue.

La concentration est mesurée sur la masse probabiliste de queue, afin de
rester comparable entre Monte-Carlo standard et importance sampling :

- parts de la perte positive expliquées par les pires 1 %, 5 % et 10 % de la
  masse de queue ;
- HHI des contributions positives à la queue ;
- inverse du HHI, interprété comme nombre effectif de contributeurs ;
- courbe cumulée masse de queue / perte positive expliquée ;
- décomposition entre rappel anticipé, maturité protégée et maturité avec
  barrière touchée.

Ces trois régimes sont mutuellement exclusifs et couvrent tout l’échantillon :
leurs parts de masse et d’ES doivent donc totaliser 100 %, contrairement aux
anciens diagnostics qui autorisaient le chevauchement entre maturité et
barrière touchée.

## 7. Recherche des hyperparamètres

Deux fonctions séparées du notebook principal produisent :

- une frontière en `lambda_ES` pour la formulation pénalisée ;
- une frontière en budgets `B_ES` pour la formulation contrainte.

La sélection définitive devra comparer RMSE, ES, VaR, parcimonie, stabilité,
coût initial, financement et temps de calcul. Elle utilisera seulement les
échantillons de calibration et de validation. Le test final reste réservé.

## 8. Vérification

- 133 tests du projet passent, avec 73 sous-tests.
- Les fichiers modifiés passent le contrôle Ruff.
- Un test d’intégration sur une vraie politique conditionnelle Calls + Puts a
  exécuté les quatre expériences ; les quatre solveurs ont convergé et les deux
  contraintes d’ES étaient satisfaites sur leur calibration.
- Cette vérification réduite valide l’enchaînement technique mais ne constitue
  pas un résultat économique.

## 9. Limites

- Le solveur contraint utilise SLSQP et doit encore être stressé sur les grandes
  dimensions du mode REPORT.
- Le budget de 90 % est exploratoire.
- La proposition IS par défaut n’est pas encore calibrée multi-graines.
- Une contrainte respectée en calibration peut être dépassée hors échantillon.
- Le risque est risque-neutre et n’inclut pas encore volatilité implicite,
  liquidité, modèle physique, stress ou couverture dynamique.

## 10. Prochaine décision

Après un Run All FAST, vérifier convergence, faisabilité, ESS et résultats hors
calibration. Ensuite seulement, lancer hors notebook les frontières de
`lambda_ES`, de budgets et de mélanges IS, puis confirmer en mode REPORT avant
d’ouvrir le test final.
