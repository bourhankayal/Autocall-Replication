# Risque terminal et exposition résiduelle de réplication

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Des portefeuilles statiques ont été sélectionnés par alpha puis filtrés par stabilité. |
| **Problème** | Distinguer la dette autocall, l’erreur de réplication et le futur risque après couverture dynamique. |
| **Méthode** | Échantillon pathwise indépendant, flux actualisés, métriques globales et conditionnelles. |
| **Modifications** | Ajout des unités montant/%/bps, réductions relatives, conventions de signe et contrôles d’effectif. |
| **Résultats** | Le pipeline fournit maintenant une mesure comparable du niveau 1 et du niveau 2 ; le niveau 3 reste à développer. |

## 1. Progression en trois niveaux

### Niveau 1 — Dette autocall sans réplication

Pour chaque trajectoire, `H0` représente la somme des flux contractuels de
l’autocall actualisés à la date de valorisation. La valeur de référence `V0`
est la moyenne de `H0` sur l’échantillon indépendant :

```text
perte brute = H0 - V0
```

Une valeur positive est défavorable à l’émetteur : la dette est supérieure à
la valeur initialement provisionnée par le modèle.

### Niveau 2 — Exposition résiduelle de réplication

`R0` est le payoff actualisé du portefeuille statique sur la même trajectoire :

```text
erreur de réplication = H0 - R0
```

Une valeur positive indique une sous-réplication. Cette quantité ne doit pas
être appelée « risque après couverture dynamique ».

### Niveau 3 — Couverture dynamique du résidu

La phase suivante construira les gains actualisés `G0_hedge` d’une stratégie
autofinancée appliquée au résidu :

```text
erreur finale = H0 - R0 - G0_hedge
```

Cette stratégie n’est pas encore implémentée. Le résultat expose donc le statut
`level_3_not_implemented`.

## 2. Hypothèses de la phase actuelle

- dynamique Black-Scholes sous mesure risque-neutre ;
- même trajectoire pour l’autocall et tous les instruments ;
- flux ramenés à la date initiale avec le taux sans risque constant ;
- poids statiques continus et fixés avant l’échantillon d’évaluation ;
- échantillon de risque indépendant de la sélection d’alpha ;
- test final de sélection conservé fermé ;
- aucun rebalancement, coût de financement, marge ou arrondi en contrats.

Cette phase mesure principalement la qualité de réplication sous le modèle. Elle
ne constitue pas encore une mesure du risque économique sous la probabilité
réelle.

## 3. Mesures produites

Les tables contiennent désormais :

- erreur moyenne et MAE ;
- écart-type et RMSE ;
- fréquence de sous-réplication ;
- VaR et Expected Shortfall à 95 %, 97,5 % et 99 % ;
- perte maximale simulée ;
- réductions absolues et relatives ;
- montant, pourcentage et points de base du nominal ;
- effectif, fréquence et fiabilité des quantiles de chaque régime.

Une réduction relative n’est publiée que lorsque la métrique brute est
strictement positive. Dans le cas contraire, la valeur reste manquante et un
indicateur signale que le ratio n’est pas interprétable.

## 4. Coût théorique et coût d’exécution

La valeur théorique initiale du panier est la somme des prix Black-Scholes
pondérés. Elle est séparée du coût de transaction :

- demi-spread bid-ask pour les calls et puts listés ;
- spread vertical synthétique et scénarios OTC pour les binaires ;
- aucune imputation silencieuse des cotations manquantes.

Le ratio `coût / réduction d’ES 97,5 %` est un filtre indicatif. Il compare un
coût certain à une variation de mesure de risque et ne représente pas une
rentabilité attendue.

## 5. Sorties techniques

`evaluate_pathwise_profile_risk` fournit notamment :

- `gross_risk` et `gross_risk_units` ;
- `residual_risk` et `residual_risk_units` ;
- `comparison` pour le régime global ;
- `conditional_comparison` pour tous les régimes ;
- `condition_summary` ;
- `risk_summary` pour le notebook principal ;
- les conventions, le niveau analysé et le statut du niveau 3.

## 6. Étape suivante

La prochaine phase devra spécifier le sous-jacent de couverture, les dates de
rebalancement, le compte cash autofinancé, la liquidation au rappel et la
valorisation intermédiaire de l’exposition résiduelle. Aucun de ces éléments ne
doit être mélangé aux résultats terminaux statiques actuels.
