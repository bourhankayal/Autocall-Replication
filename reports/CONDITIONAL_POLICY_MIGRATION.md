# Migration vers une politique conditionnelle pathwise

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Le benchmark conditionnel donnait une réplication nettement meilleure que le portefeuille terminal unique. |
| **Problème** | L’ancien benchmark pouvait choisir le panier d’une date avec l’état observé à cette même date et sa métrique aplatie mélangeait cellules vivantes et zéros post-rappel. |
| **Méthode** | Politique chronologique par nœuds date–état, alpha global, erreur totale par trajectoire et séparation 60/20/20. |
| **Modifications** | Nouveau moteur conditionnel, audit d’information, registre de cashflows, stabilité sur dix graines, risque indépendant, coûts pondérés par fréquence d’atteinte et migration des sections 4 à 8 du notebook. |
| **Résultats** | Le pipeline compare désormais `calls_puts` et `full` sans anticipation et conserve le test final fermé. |

## 1. Pourquoi la méthode a changé

Le très faible RMSE de l’ancien benchmark conditionnel ne pouvait pas être
comparé directement à celui du benchmark terminal : le premier ajustait
plusieurs paniers date–état et sa métrique globale incluait les zéros après
rappel, tandis que le second ajustait un seul vecteur de poids sur le payoff
terminal total.

Le conditionnel reste la piste principale, mais il est reformulé comme une
politique effectivement exécutable :

```text
état connu à l'observation précédente
        ↓
choix du panier de la période suivante
        ↓
règlement à l'observation suivante
        ↓
rappel : arrêt ; survie : nouvelle décision
```

## 2. Convention chronologique

- Le premier panier est choisi au temps initial.
- À partir de la deuxième échéance, seuls `alive` et l’état cumulé de barrière
  connus à l’observation précédente peuvent sélectionner le panier suivant.
- L’état découvert à la date de paiement ne modifie jamais le panier qui vient
  d’expirer.
- Si un état contient trop peu de trajectoires train, un nœud mutualisé défini
  sur le train est utilisé. Validation et test ne créent aucun nœud.
- Les paniers ont une maturité d’une période. Au rappel, les positions courantes
  ont expiré et aucune position suivante n’est ouverte : la liquidation
  résiduelle vaut donc zéro par construction.

Le registre `conditional_policy_cashflow_ledger` affiche, pour chaque date,
l’information disponible, le nœud choisi, les flux actualisés de l’autocall et
de la réplique, le surplus cumulé, le rappel et la liquidation. Le financement
initial, la marge et la valorisation mark-to-market restent explicitement hors
de cette première phase.

## 3. Sélection de l’alpha

Une ligne de la matrice d’apprentissage représente une trajectoire complète.
Les colonnes représentent les instruments propres aux nœuds visités. L’objectif
de validation est donc :

```text
payoff total actualisé autocall − payoff total actualisé de la politique
```

Un seul alpha est partagé par tous les nœuds d’un couple
`famille × pénalité`. Cette convention évite de sélectionner de nombreux alphas
locaux avec trop peu d’observations. L1, L2 et Elastic Net sont comparés avec le
même split 60 % train, 20 % validation et 20 % test réservé. Toutes les jambes
cash des nœuds sont non pénalisées.

Les filtres déjà validés restent appliqués : convergence, 2 à 100 options
actives, Pareto au sein de chaque pénalité, bootstrap de performance et retrait
des doublons. Les trois profils performance, compromis et parcimonie sont
conservés lorsqu’ils existent.

## 4. Stabilité, risque et coûts

- **Stabilité :** dix jeux de trajectoires indépendants, topologie de la
  politique figée, alpha absolu recalculé depuis l’alpha relatif, test fermé.
- **Risque :** échantillon indépendant, risque brut de l’autocall et risque
  résiduel `autocall − politique`, globalement et par régime contractuel.
- **Coûts :** coût bid-ask/OTC de chaque nœud pondéré par sa probabilité
  empirique d’être atteint. La somme de tous les nœuds est conservée comme borne
  haute et non comme coût attendu.

Les familles `calls_puts` et `full` traversent désormais la même chaîne. Cette
comparaison permet de mesurer séparément le gain théorique des binaires et le
coût/liquidité de leur implémentation OTC.

## 5. Fichiers modifiés

- `replication/conditional_policy.py` : politique, matrice bloc, sélection,
  audit et registre de cashflows ;
- `replication/stability.py` : stabilité conditionnelle sur dix calibrations ;
- `replication/risk.py` : risque indépendant de la politique ;
- `replication/transaction_costs.py` : coût attendu par fréquence d’atteinte ;
- `notebooks/autocall_research.ipynb` : sections 4 à 8 conditionnelles ;
- `tests/test_conditional_policy.py` : tests de chronologie, split, cash,
  registre et topologie figée.

## 6. Limites et prochaine étape

Cette politique règle le problème d’anticipation et permet une sélection
pathwise cohérente. Elle n’est pas encore une stratégie autofinancée complète :
le prix d’achat des paniers aux dates de décision, leur valeur mark-to-market,
la marge et le P&L quotidien restent à construire dans la phase 2. La prochaine
étape logique est donc le suivi mark-to-market du risque résiduel, puis sa
couverture dynamique.

