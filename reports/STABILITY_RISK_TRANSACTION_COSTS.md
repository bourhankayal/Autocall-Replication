# Stabilité, risque et coûts de transaction des profils

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Les profils sélectionnés doivent être stables et économiquement évaluables. |
| **Problème** | Distinguer erreur de réplication, risque terminal et coût d’exécution. |
| **Méthode** | Dix recalibrations, échantillon indépendant et scénarios bid-ask/OTC. |
| **Modifications** | Ajout des filtres de stabilité, risque et coût sur les profils. |
| **Résultats** | Le rapport fournit les candidats stables et les limites des coûts disponibles. |


Date d'intégration : 19 août 2026

## 1. Objectif

Cette étape transforme les profils performance, compromis et parcimonie de
chaque pénalité en candidats économiquement évaluables. Elle ajoute :

1. un filtre de stabilité sur dix calibrations ;
2. une mesure indépendante du risque brut et de l'exposition résiduelle de réplication ;
3. des coûts bid-ask provenant de yfinance pour les options listées ;
4. trois scénarios OTC pour les options binaires ;
5. un filtre comparant le coût payé au risque effectivement réduit.

L1, L2 et Elastic Net restent toujours analysés séparément.

## 2. Filtre de stabilité

### Protocole

Chaque profil est recalibré avec dix graines distinctes, par défaut de `42` à
`51`. Pour chaque calibration :

- un nouveau dataset pathwise est simulé ;
- le split 60 % train, 20 % validation, 20 % test réservé est reconstruit ;
- la référence d'alpha est recalculée sur le train ;
- l'alpha absolu est obtenu à partir de l'alpha relatif du profil ;
- les poids sont réestimés par FISTA ;
- aucune observation du test réservé n'est évaluée.

### Mesures

Le rapport détaille pour chaque graine :

- convergence ;
- RMSE et MAE de validation ;
- nombre d'options actives ;
- Jaccard du support contre la calibration de base ;
- distance relative des poids ;
- somme et maximum des poids absolus.

### Règle éliminatoire

Un profil passe si :

```text
convergence = 10/10
et
2 à 100 options actives sur au moins 9/10 calibrations
```

Jaccard et variation des poids restent affichés, mais ne sont pas encore
éliminatoires : leurs seuils seront définis après observation des distributions.
`apply_stability_filter` construit une vue du résultat contenant uniquement les
profils stables.

## 3. Risque de l'autocall et des réplications

### Échantillon

Les profils stables sont évalués par défaut sur 20 000 trajectoires indépendantes
avec la graine `10500`. Cet échantillon ne sert ni à calibrer les poids ni à
choisir alpha. Le test final original conserve le statut
`reserved_not_evaluated`.

### Convention de perte

Du point de vue de l'émetteur :

```text
perte brute = payoff actualisé autocall - moyenne Monte-Carlo du payoff
perte résiduelle = payoff actualisé autocall - payoff actualisé réplication
```

La perte brute correspond donc à la variabilité de la dette non couverte autour
de sa valeur moyenne. La perte résiduelle inclut le biais éventuel de la
réplication.

### Mesures

- moyenne et écart-type de la perte ;
- RMSE ;
- perte maximale observée ;
- VaR 95 %, 97,5 % et 99 % ;
- Expected Shortfall 95 %, 97,5 % et 99 %.

Les mêmes mesures sont produites :

- sur toutes les trajectoires ;
- lorsque l'autocall est rappelé ;
- lorsqu'il arrive à maturité ;
- lorsque la barrière de protection est touchée.

## 4. Données yfinance

`download_yfinance_option_snapshot` récupère pour les calls et puts :

- symbole du contrat ;
- échéance et strike ;
- bid et ask ;
- volume et open interest ;
- volatilité implicite ;
- taille de contrat, devise et dernière transaction.

La date UTC du snapshot est toujours enregistrée. Il s'agit d'une photographie
courante, pas d'une chaîne historique.

Une cotation est valide lorsque :

```text
bid > 0
ask > bid
ask / bid <= 10
```

Cette dernière borne est un garde-fou de liquidité. Les cotations absentes,
infinies, à bid nul ou anormalement larges restent explicitement invalides.

Une échéance de marché située à trois jours calendaires au plus de l'échéance
contractuelle peut être utilisée. L'échéance contractuelle et l'échéance réelle
du marché sont toutes les deux conservées. Au-delà, le téléchargement échoue
explicitement.

Pour les calls et puts, la correspondance exacte est prioritaire. Si la
normalisation du spot produit un strike absent, le strike coté le plus proche
peut être retenu dans une limite configurable de 0,5 % du spot de marché. Le
strike demandé, le strike retenu et leur distance restent visibles. Au-delà de
cette limite, la ligne est déclarée indisponible ; aucune extrapolation n'est
effectuée.

Lorsque l'univers de réplication est normalisé autour de `spot0=100`, les
strikes sont convertis vers le niveau courant du sous-jacent :

```text
strike marché = strike modèle × spot marché / spot0 modèle
```

La quantité d'un call ou put listé est divisée par le même facteur afin de
préserver son payoff dans les unités du modèle. Les binaires conservent leur
quantité puisque leur payout monétaire ne dépend pas de l'échelle du spot.

## 5. Construction du coût

Pour une option listée :

```text
demi-spread = (ask - bid) / 2
coût = quantité absolue × demi-spread
```

Les poids actuels représentent des unités de payoff par action et non des
nombres entiers de contrats. Aucun multiplicateur 100 n'est donc appliqué à ce
stade. L'arrondi en contrats et son multiplicateur restent une étape ultérieure.

Le coût total est affiché en montant monétaire et en points de base du nominal
de l'autocall. `cost_complete=False` dès qu'une seule ligne active ne possède
pas de coût valide.

## 6. Coût OTC des options binaires

### Ancrage observable

Une digitale call est approchée par deux calls entourant le strike :

```text
digitale call ≈ [Call(K inférieur) - Call(K supérieur)] / largeur de strikes
```

Le bid synthétique achète et vend aux côtés réellement exécutables :

```text
bid = [bid Call bas - ask Call haut] / largeur
ask = [ask Call bas - bid Call haut] / largeur
```

La digitale put utilise le put haut moins le put bas. Cette approximation est
une rampe finie, pas une digitale mathématique exacte.

### Trois scénarios

| Scénario | Multiplicateur du demi-spread synthétique | Plancher en pb du payout |
|---|---:|---:|
| `otc_favorable` | 1,0 | 5 pb |
| `otc_central` | 1,5 | 10 pb |
| `otc_stressed` | 2,5 | 25 pb |

Formule :

```text
demi-spread OTC = max(
    multiplicateur × demi-spread synthétique,
    plancher × payout / 10 000
)
```

Ces coefficients sont des hypothèses de scénario transparentes et réversibles.
Ils ne sont pas présentés comme des cotations OTC observées. Ils permettent de
tester la sensibilité économique tant qu'aucune cotation de dealer n'est
disponible.

## 7. Filtre coût contre risque

La métrique centrale est la réduction d'Expected Shortfall à 97,5 % :

```text
réduction de risque = ES brut autocall - ES résiduel réplication
```

Un couple profil/scénario est accepté seulement si :

```text
coût complet
réduction de risque > 0
coût de transaction <= réduction de risque
perte maximale résiduelle <= perte maximale brute
```

Le tableau conserve le coût et la réduction de risque en montant ainsi qu'en
points de base du nominal, et indique précisément le motif de rejet.

## 8. Limites

- yfinance est une source indicative et peut retourner des chaînes absentes ou
  incohérentes ; aucune valeur manquante n'est imputée.
- Les chaînes historiques ne sont pas reconstruites.
- Les scénarios OTC ne remplacent pas une cotation de dealer.
- Les coûts fixes, commissions, profondeur, slippage de taille et impact de
  marché ne sont pas encore ajoutés.
- Les quantités continues ne sont pas encore arrondies en contrats.
- L'exposition terminale de réplication ne remplace pas encore le suivi temporel de la future couverture dynamique du résidu.

## 9. Fichiers

- `replication/stability.py` : dix calibrations et filtre de stabilité ;
- `replication/risk.py` : VaR, ES, risque conditionnel et filtre coût/risque ;
- `replication/transaction_costs.py` : yfinance, validation des quotes et OTC ;
- `notebooks/autocall_research.ipynb` : exécution et affichage ;
- `tests/test_stability_risk_costs.py` : tests déterministes et mocks hors réseau.

## 10. Références publiques

- [Implémentation officielle de `option_chain` dans yfinance](https://github.com/ranaroussi/yfinance/blob/main/yfinance/ticker.py) : champs bid, ask, volume, open interest, volatilité implicite, taille de contrat et devise.
- [Méthodologie Cboe S&P 500 Left Tail](https://cdn.cboe.com/api/global/us_indices/governance/Cboe_SnP_500_Left_Tail_Volatility_Index_Methodology.pdf) : exclusion des bids nuls et des ratios ask/bid supérieurs à 10 comme contrôles de liquidité.
- [CFTC — Binary Options and Fraud](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/fraudadv_binaryoptions.html) : définition du payout cash-or-nothing et distinction entre instruments listés et marché hors cote.
- [Cadre de risque de marché du Comité de Bâle](https://www.bis.org/basel_framework/chapter/MAR/33.htm) : usage de l'Expected Shortfall à 97,5 % comme mesure de pertes extrêmes. Le filtre du projet reste toutefois une métrique expérimentale de réplication et non un calcul réglementaire de capital.
