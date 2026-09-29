# Dossier de passation CV — Autocall Replication

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Projet quantitatif et logiciel consacré au pricing, à la réplication parcimonieuse et à l’analyse du risque d’un autocall mono-sous-jacent. |
| **Problème** | Passer d’un payoff path-dependent complexe à une couverture interprétable, stable, finançable et progressivement rapprochée des contraintes d’un desk. |
| **Méthode** | Monte-Carlo Black-Scholes, benchmarks de réplication, optimisation régularisée L1/L2/Elastic Net, politique conditionnelle pathwise, validation hors échantillon, risque de queue et ledger de financement. |
| **Modifications** | Construction d’un package Python testé, d’un notebook de recherche structuré, de solveurs et diagnostics, de scénarios de coûts, de rapports reproductibles et d’une CI multi-version. |
| **Résultats** | Moteur Monte-Carlo validé, 103 tests et 65 sous-tests réussis, forte réduction du RMSE par la réplication mais dégradation actuelle de l’ES 97,5 %, ce qui motive la future couverture dynamique du résidu. |

## 1. Usage de ce document

Ce fichier est destiné à être transmis à une personne ou à une IA chargée de
rédiger un CV, une lettre, un portfolio ou une présentation d’entretien. Il
décrit :

- ce que fait réellement le projet ;
- les choix mathématiques et financiers ;
- l’architecture logicielle ;
- les résultats quantitatifs actuellement disponibles ;
- les difficultés résolues ;
- les limites et travaux futurs ;
- les affirmations utilisables sur un CV ;
- les affirmations qu’il ne faut pas faire.

Le projet est une **étude quantitative expérimentale**. Il ne doit pas être
présenté comme un pricer de production bancaire ni comme une stratégie de
couverture déjà rentable en conditions réelles.

---

## 2. Identité du projet

### Nom

**Autocall Replication**

### Type

Projet de recherche quantitative, développement Python et ingénierie
financière.

### Version logicielle actuelle

`0.1.0`

### Question de recherche

> Jusqu’où une réplication statique simple, liquide, parcimonieuse et
> interprétable peut-elle réduire le risque d’un autocall avant qu’une
> couverture dynamique du résidu devienne indispensable ?

### Résumé en une phrase

Développement d’un framework Python reproductible pour valoriser un autocall
par Monte-Carlo, construire des réplications statiques et conditionnelles par
options vanilles, sélectionner des portefeuilles parcimonieux, puis mesurer
leur risque résiduel, leur stabilité, leur coût et leur besoin de financement.

### Résumé court en trois phrases

Le projet modélise un autocall mono-sous-jacent, valide son payoff et le
valorise sous Black-Scholes par simulation Monte-Carlo. Il compare plusieurs
formulations de réplication et plusieurs régularisations afin d’obtenir des
portefeuilles d’options plus parcimonieux et interprétables. Les stratégies
sont ensuite évaluées hors échantillon en RMSE, VaR, Expected Shortfall,
stabilité, coût initial, exposition brute et besoin de financement.

---

## 3. Contexte financier

Un autocall est un produit structuré dont les paiements dépendent du chemin du
sous-jacent :

- il peut être remboursé avant maturité à certaines dates d’observation ;
- il peut verser un coupon sous condition de niveau du sous-jacent ;
- il comporte une protection conditionnelle du capital ;
- une baisse suffisamment forte peut entraîner une perte à maturité ;
- le produit cesse d’exister après un rappel anticipé.

Du point de vue de l’émetteur, la vente du produit crée une dette aléatoire
envers le client. Le problème étudié consiste à utiliser du cash et des options
pour générer des flux proches de cette dette.

Le projet sépare trois niveaux de risque :

1. **dette brute de l’autocall sans réplication** ;
2. **exposition résiduelle après réplication statique ou conditionnelle** ;
3. **risque final après future couverture dynamique du résidu**.

Les niveaux 1 et 2 sont implémentés. Le niveau 3 est explicitement identifié
mais pas encore implémenté.

---

## 4. Produit contractuel implémenté

### Nature du produit

Autocall discret mono-sous-jacent, proche d’un Athena sans mémoire. Le nom
commercial est secondaire : les règles numériques de la term-sheet constituent
la source de vérité.

### Configuration contractuelle et de marché unique

| Élément | Convention par défaut |
|---|---|
| Nominal | 100 |
| Seuil de rappel | 100 % du spot initial |
| Barrière coupon | 80 % du spot initial |
| Coupon périodique | 2 % du nominal |
| Barrière de protection | 70 % du spot initial |
| Observations | 3, 6, 9 et 12 mois |
| Coupon | Conditionnel, non garanti, sans mémoire |
| Rappel | Déclenché si le spot est supérieur ou égal au seuil |
| Barrière de protection | Surveillée sur toutes les cotations disponibles |
| Calendrier | Lundi–vendredi, sans calendrier de jours fériés |
| Report | Première cotation disponible postérieure |
| Day count | ACT/365 |
| Actualisation | Capitalisation continue |
| Taux sans risque | 3 % |
| Dividende continu | 1 % |
| Volatilité | 20 % |

Cette configuration est utilisée par défaut dans le moteur, la term-sheet, le
notebook principal et les rapports de référence.

### Logique du payoff

À chaque observation, tant que le produit est vivant :

```text
coupon = c × nominal si spot >= barrière coupon × spot initial
coupon = 0 sinon
```

Après calcul du coupon :

```text
si spot >= seuil de rappel × spot initial :
    remboursement du nominal
    arrêt définitif du produit
```

À maturité, si le produit n’a jamais été rappelé :

```text
si la barrière de protection n’a jamais été touchée :
    remboursement = nominal
sinon :
    remboursement = nominal × spot final / spot initial
```

Le coupon final éventuel est ajouté au remboursement. Aucun coupon manqué
n’est mémorisé. Aucun flux ni risque ne subsiste après le rappel.

### Cas limites couverts

- rappel à chacune des dates d’observation ;
- spot exactement égal aux seuils ;
- coupon payé ou non payé ;
- absence de mémoire ;
- barrière touchée puis remontée du spot ;
- remboursement au pair ou indexé à la baisse ;
- absence de flux après rappel ;
- données manquantes, non finies, désordonnées ou dupliquées ;
- trajectoire trop courte ;
- dates contractuelles tombant le week-end ;
- valorisation d’un contrat déjà commencé avec état contractuel transmis.

---

## 5. Pricing Monte-Carlo

### Modèle

Le sous-jacent suit un mouvement brownien géométrique sous mesure
risque-neutre :

\[
\frac{dS_t}{S_t}=(r-q)dt+\sigma dW_t.
\]

Les paramètres actuels sont constants : taux, dividende et volatilité.

### Fonctionnalités numériques

- simulation vectorisée de trajectoires ;
- grille de jours ouvrés simplifiée ;
- graines reproductibles ;
- paires antithétiques ;
- variable de contrôle fondée sur le spot terminal actualisé ;
- calcul de l’erreur standard ;
- intervalle de confiance à 95 % ;
- étude de convergence en nombre de trajectoires ;
- étude de la fréquence de surveillance de la barrière ;
- comparaison du moteur vectorisé au moteur contractuel trajectoire par
  trajectoire ;
- traitement explicite des contrats en cours de vie.

### Résultat de référence

Pour le contrat par défaut, avec 20 000 trajectoires, taux 3 %, dividende 1 %,
volatilité 20 %, seed 42 et surveillance quotidienne :

| Mesure | Valeur |
|---|---:|
| Prix brut antithétique | 100,422920 |
| Intervalle à 95 % | [100,315489 ; 100,530352] |
| Prix avec variable de contrôle | 100,390169 |
| Erreur standard avec contrôle | 0,033270 |
| Ratio de réduction de variance observé | environ 2,71 |

### Étude de surveillance de barrière

Le prix de référence quotidien est 100,422920.
Une surveillance mensuelle donne environ 100,696402, soit une surestimation
d’environ 0,273482 : observer moins souvent la barrière manque des activations
défavorables à l’investisseur.

---

## 6. Instruments de réplication

Le package implémente :

- position cash ;
- call européen ;
- put européen ;
- call binaire cash-or-nothing ;
- put binaire cash-or-nothing.

Les options européennes sont valorisées par Black-Scholes. Pour une binaire de
payout \(Q\) :

\[
BC = Qe^{-rT}N(d_2),
\qquad
BP = Qe^{-rT}N(-d_2).
\]

Deux familles principales sont conservées :

- **Calls + Puts** : univers plus simple et plus proche d’instruments listés ;
- **Full** : cash, calls, puts et binaires, utile pour capter les discontinuités
  du payoff.

---

## 7. Benchmarks de réplication développés

Le projet ne s’est pas limité à une seule régression. Il a construit et comparé
plusieurs cibles :

### 7.1 Surface de prix

Approximation de la valeur de l’autocall sur une grille de dates et de niveaux
de spot par un portefeuille de vanilles.

### 7.2 Payoff moyen sur grille

Approximation de l’espérance de payoff conditionnelle aux points date–spot.

### 7.3 Payoff total pathwise

Une observation statistique correspond à une trajectoire complète. Le modèle
cherche à reproduire le payoff actualisé total de l’autocall trajectoire par
trajectoire.

### 7.4 Cashflows statiques par date

La cible est une courbe de flux dans le temps plutôt qu’un unique total
terminal.

### 7.5 Benchmark conditionnel

Le portefeuille dépend de l’état observable du produit aux dates
d’observation : vivant, rappelé, barrière déjà touchée ou non. Cette version est
mieux adaptée au caractère path-dependent de l’autocall.

### 7.6 Politique conditionnelle pathwise

C’est la méthode retenue pour la suite. Une ligne de la régression représente
une trajectoire entière et les colonnes représentent les instruments associés
aux nœuds date–état visités. Le portefeuille de la période suivante est choisi
à partir de l’information disponible avant le paiement, ce qui évite le
look-ahead bias.

Les premiers benchmarks restent dans le projet comme références et contrôles,
mais l’analyse économique principale part désormais de cette politique
conditionnelle.

### 7.7 Exploration spectrale

Une base spectrale fondée sur des fonctions propres et des straddles a été
explorée. Elle est encore expérimentale : orthogonalité, erreur de troncature,
interprétation économique et gain par rapport à une grille naïve doivent être
validés avant toute revendication de contribution scientifique.

---

## 8. Optimisation parcimonieuse

### Objectif

Réduire l’erreur de réplication tout en évitant des portefeuilles contenant un
très grand nombre de petites positions instables et coûteuses.

### Interface commune

Le projet introduit :

- `SolverConfig` pour les paramètres ;
- `SolverResult` pour les poids et diagnostics ;
- `solve_replication` comme point d’entrée commun ;
- `available_solvers` pour les méthodes disponibles.

Le solveur historique `legacy` est conservé comme référence de non-régression.
Les futurs solveurs peuvent être branchés derrière la même interface.

### Pénalités

#### L1 / Lasso

\[
\frac{1}{2n}\|Xw-y\|_2^2+\alpha\|w\|_1.
\]

L1 crée des poids exactement nuls et sélectionne les instruments.

#### L2 / Ridge

L2 réduit et stabilise les poids, mais ne produit généralement pas de zéros
exacts. Il ne doit donc pas être évalué avec le seul nombre de positions
actives.

#### Elastic Net

\[
\frac{1}{2n}\|Xw-y\|_2^2
+\alpha\left(\rho\|w\|_1+\frac{1-\rho}{2}\|w\|_2^2\right).
\]

Elastic Net combine sélection L1 et stabilisation L2. Le ratio actuellement
utilisé est fixé à 0,5 ; sa recherche n’est pas encore implémentée.

### Solveur FISTA

Un solveur proximal accéléré FISTA a été développé pour L1 et Elastic Net,
avec support de Ridge :

- normalisation RMS des colonnes ;
- seuillage proximal donnant des zéros exacts ;
- pas fondé sur la norme spectrale ;
- momentum accéléré ;
- redémarrage adaptatif ;
- critère relatif de convergence ;
- warm starts sur les chemins d’alpha ;
- cash explicitement non pénalisé ;
- restitution des itérations, convergence, objectif et message de statut.

Une limite documentée subsiste : certains petits problèmes mal conditionnés et
faiblement régularisés atteignent `max_iter` avant la tolérance demandée. Le
statut n’est jamais masqué.

---

## 9. Chemins de régularisation et sélection d’alpha

### Split expérimental

Les données sont séparées en :

- 60 % entraînement ;
- 20 % validation ;
- 20 % test final réservé.

Le test final n’est pas utilisé pendant l’exploration des hyperparamètres.

### Grilles d’alpha

Pour L1 et Elastic Net, `alpha_max` correspond au niveau annulant toutes les
options pénalisées. La grille descend logarithmiquement vers une fraction de
cette référence.

Pour Ridge, la référence utilise la plus grande valeur propre de
\(X^TX/n\), après normalisation et exclusion du cash. Cette échelle évite de
traiter arbitrairement un alpha L2 comme un alpha L1.

### Filtres de candidats

- convergence obligatoire ;
- au moins 2 options actives ;
- au plus 100 options actives ;
- suppression des solutions dominées au sein de chaque pénalité ;
- filtre de performance statique ;
- suppression de doublons stricts et quasi stricts ;
- rapports détaillant les doublons supprimés.

La domination n’est pas calculée globalement entre des normes différentes.

### Profils conservés

Pour chaque pénalité, jusqu’à trois profils sont conservés :

- **performance** : RMSE de validation minimale ;
- **compromis** : équilibre normalisé entre erreur et complexité ;
- **parcimonie** : nombre minimal d’instruments parmi les solutions encore
  admissibles.

Plusieurs solutions peuvent être conservées si elles présentent des compromis
pertinents. Le projet ne force pas artificiellement un nombre unique
d’instruments.

---

## 10. Diagnostics de portefeuille

Les diagnostics séparent explicitement quantités et exposition monétaire :

- nombre total et nombre actif d’instruments ;
- seuil d’activité à \(10^{-6}\) ;
- proportion active ;
- cash total et cash actif ;
- nombre d’options actives ;
- positions longues et courtes ;
- somme des valeurs absolues des poids ;
- poids net ;
- poids maximal absolu ;
- concentration de la première et des cinq premières positions ;
- exposition monétaire nette ;
- exposition monétaire brute.

La somme des poids n’est jamais présentée comme une exposition en euros. Le
cash est séparé des options dans les diagnostics et dans la pénalisation.

---

## 11. Stabilité

Chaque profil sélectionné est recalibré sur dix graines distinctes. Pour chaque
recalibration, le projet mesure :

- convergence ;
- RMSE et MAE de validation ;
- nombre d’options actives ;
- similarité de Jaccard des supports ;
- distance relative des poids ;
- somme et maximum des poids absolus.

La règle de stabilité actuelle exige :

```text
convergence sur 10/10 recalibrations
et
nombre d’options compris entre 2 et 100 sur au moins 9/10 recalibrations
```

Jaccard et distance des poids sont encore descriptifs. Leurs seuils
éliminatoires doivent être définis après analyse des distributions.

---

## 12. Mesure du risque

### Échantillon indépendant

Les profils stables sont évalués sur un nouvel échantillon de trajectoires qui
n’a servi ni à calibrer les poids ni à sélectionner alpha. Le mode `report`
prévoit 20 000 trajectoires indépendantes.

### Convention de perte

\[
L_{brut}=H_0-\mathbb{E}[H_0],
\qquad
L_{résiduel}=H_0-R_0.
\]

Une perte résiduelle positive signifie que la réplication ne fournit pas assez
pour payer le client.

### Mesures

- perte moyenne ;
- MAE ;
- écart-type ;
- RMSE ;
- fréquence de sous-réplication ;
- perte maximale ;
- VaR 95 %, 97,5 % et 99 % ;
- Expected Shortfall 95 %, 97,5 % et 99 %.

Les métriques sont produites :

- globalement ;
- sur les produits rappelés ;
- sur les produits allant à maturité ;
- sur les trajectoires ayant touché la barrière.

Elles sont exprimées en montant, en pourcentage et en points de base du
nominal. Les faibles effectifs conditionnels déclenchent une alerte de fiabilité
des quantiles.

### Résultat principal actuel

Dans les résultats visualisés :

- RMSE brut proche de 7,7 pour un nominal de 100 ;
- RMSE résiduel selon les candidats, approximativement entre 2,6 et 5,8 ;
- réduction typique du RMSE pouvant atteindre environ 60 % ;
- ES 97,5 % brut proche de 4,4 ;
- ES 97,5 % résiduel approximativement entre 8,5 et 14.

La réplication améliore donc nettement l’erreur globale mais détériore la queue
de sous-réplication. C’est un résultat négatif important et exploitable : une
stratégie optimisée seulement en erreur quadratique peut réussir sur la majorité
des trajectoires tout en devenant dangereuse dans les scénarios extrêmes.

Il ne faut pas écrire sur un CV que la stratégie « réduit le risque de 60 % »
sans préciser qu’il s’agit du RMSE et que l’Expected Shortfall se dégrade.

---

## 13. Coûts de transaction et liquidité

### Options listées

Une extension yfinance peut télécharger :

- contrat ;
- échéance et strike ;
- bid et ask ;
- volume et open interest ;
- volatilité implicite ;
- taille de contrat ;
- devise et dernière transaction.

Les quotes sont validées. Une ligne est rejetée si le bid est nul, si l’ask
n’est pas supérieur au bid ou si le ratio ask/bid dépasse 10. Une maturité
proche peut être retenue dans une tolérance de trois jours, et un strike voisin
dans une tolérance configurable de 0,5 % du spot. Les correspondances et écarts
restent audités.

Le coût indicatif d’une option listée est :

\[
coût=|quantité|\times\frac{ask-bid}{2}.
\]

Une cotation manquante ne devient jamais silencieusement un coût nul.

### Binaires synthétiques et OTC

Une binaire call peut être approchée par :

\[
\text{Binary Call}
\approx \frac{Q}{K_2-K_1}\left[C(K_1)-C(K_2)\right].
\]

La binaire put utilise de façon analogue un spread de puts. Trois scénarios OTC
transparents sont définis :

| Scénario | Multiplicateur de demi-spread synthétique | Plancher |
|---|---:|---:|
| Favorable | 1,0 | 5 bps du payout |
| Central | 1,5 | 10 bps du payout |
| Stressé | 2,5 | 25 bps du payout |

Ces chiffres sont des hypothèses, pas des quotes de dealer.

### Filtre coût/risque

Le coût est comparé à la réduction d’ES 97,5 %. Une stratégie passe le filtre
seulement si les données sont complètes, si la réduction d’ES est positive, si
le coût ne dépasse pas la réduction de risque et si la perte maximale ne se
détériore pas.

La partie yfinance est une préparation technique. Elle ne constitue pas encore
un backtest avec chaînes historiques d’options.

---

## 14. Financement et comptabilité de la couverture

Le projet ne s’arrête pas au payoff terminal. Un ledger simule le point de vue
de l’émetteur :

1. encaissement de la prime de l’autocall ;
2. achat du panier initial ;
3. placement ou emprunt du solde ;
4. capitalisation du compte cash ;
5. encaissement des payoffs d’options ;
6. paiement des flux au client ;
7. achat du panier suivant si le produit survit ;
8. arrêt et liquidation au rappel.

La récurrence est :

```text
cash avant règlement = cash précédent × exp(r × durée)
cash après règlement = cash avant + payoff options - flux autocall
cash après transaction = cash après règlement - coût du panier suivant
```

Mesures disponibles :

- coût initial net ;
- exposition brute initiale ;
- fréquence d’emprunt ;
- capital additionnel moyen, P95 et maximal ;
- achats bruts cumulés ;
- coût d’exécution OTC cumulé ;
- P&L terminal moyen et volatilité du P&L ;
- RMSE, VaR, ES et perte maximale du P&L.

Les trajectoires de financement sont indépendantes de la calibration. Alpha,
poids et topologie sont figés avant leur utilisation.

### Estimation rapide illustrative

Profil L1 `compromis`, famille `full`, binaires remplacées par des spreads de
largeur 5, avec petit échantillon exploratoire :

| Mesure, nominal 100 | Valeur approximative |
|---|---:|
| Prime autocall | 100,48 |
| Coût initial net du panier | 101,17 |
| Besoin initial de financement | 0,69 |
| Capital additionnel P95 | 3,90 |
| Achats bruts cumulés | 105,55 |
| P&L terminal moyen | -0,23 |
| Écart-type du P&L | 5,90 |
| ES 97,5 % de la perte | 7,44 |

Les achats bruts cumulés ne sont pas des frais. Les chiffres ci-dessus sont
exploratoires et doivent être recalculés en mode `report` avant publication
finale.

---

## 15. Trois prix

Le projet distingue :

### Prix théorique

Valeur Monte-Carlo du passif sous le modèle.

### Prix minimal de couverture

\[
P_{couverture}=P_{simulation}-\mathbb{E}[P\&L_{terminal}].
\]

Il annule le P&L terminal moyen estimé, mais ne protège pas contre les queues.

### Prix commercial indicatif

\[
P_{commercial}=P_{couverture}+marge\ cible.
\]

La marge cible du notebook vaut provisoirement 1 % du nominal.

Pour l’estimation rapide :

| Niveau | Valeur |
|---|---:|
| Théorique | 100,48 |
| Minimal de couverture | 100,71 |
| Commercial indicatif | 101,71 |

Dans la pratique, une émission peut rester vendue au pair à 100 et ajuster le
coupon ou les barrières plutôt que facturer 101,71. Les trois prix quantifient
le coussin nécessaire ; ils préparent une future structuration inverse.

---

## 16. Benchmark public

Le projet compare le coussin commercial à quatre exemples SEC : JPMorgan,
Barclays, Morgan Stanley et Goldman Sachs. Les écarts publics observés entre
prix d’émission et valeur estimée se situent approximativement entre 2,45 % et
11 % dans ce petit échantillon.

Notre coussin exploratoire est :

\[
101{,}71-100{,}48=1{,}23\%.
\]

Cette comparaison est uniquement documentaire. Les écarts publics agrègent
commissions, distribution, structuration, coûts de couverture, coûts
opérationnels et profits projetés. Ils ne sont pas le P&L réalisé du desk.

Sources intégrées :

- [JPMorgan](https://www.sec.gov/Archives/edgar/data/19617/000121390025028272/ea0236912-01_424b2.htm)
- [Barclays](https://www.sec.gov/Archives/edgar/data/312070/000191870425019389/form424b2.htm)
- [Morgan Stanley](https://www.sec.gov/Archives/edgar/data/895421/000183988226023540/ms15872_424b2-15430.htm)
- [Goldman Sachs](https://www.sec.gov/Archives/edgar/data/0000886982/000095017025052435/amznco11_auto_prelim.htm)

---

## 17. Architecture logicielle

### Racine

- `README.md` : présentation et démarrage rapide ;
- `pyproject.toml` : package, versions Python et dépendances ;
- `.github/workflows/ci.yml` : intégration continue ;
- `.gitignore` : exclusion des environnements, caches et rendus temporaires.

### Documentation

- `docs/TERM_SHEET.md` : source de vérité contractuelle ;
- `docs/ROADMAP.md` : feuille de route ;
- `docs/DEVELOPMENT.md` : installation et validation ;
- `docs/LEGACY_README.md` : documentation historique.

### Moteur Python

- `products.py` : contrat autocall, produits vanilles, payoffs et prix BS ;
- `monte_carlo.py` : simulation, pricing, convergence et surveillance ;
- `replication/common.py` : outils communs et métriques ;
- `price_surface.py` : benchmark de surface de prix ;
- `mean_payoff.py` : benchmark de payoff moyen ;
- `pathwise_payoff.py` : dataset et réplication trajectoire par trajectoire ;
- `static_cashflows.py` : réplication des courbes de cashflows ;
- `semi_static.py` : benchmark conditionnel ;
- `conditional_policy.py` : politique conditionnelle pathwise retenue ;
- `optimization.py` : interface de solveurs et FISTA ;
- `regularization_path.py` : grilles d’alpha, Pareto, filtres et profils ;
- `portfolio_diagnostics.py` : parcimonie et expositions ;
- `stability.py` : dix recalibrations et filtre de stabilité ;
- `risk.py` : VaR, ES, risques conditionnels et filtre coût/risque ;
- `transaction_costs.py` : yfinance, validation bid-ask et scénarios OTC ;
- `funding.py` : pricing des nœuds, remplacement des binaires et ledger ;
- `industry_benchmark.py` : trois prix et benchmark public ;
- `spectral.py` : exploration de la base spectrale.

### Notebooks

- `autocall_research.ipynb` : parcours principal de recherche ;
- `spectral_replication.ipynb` : exploration spectrale.

### Rapports

Le dossier `reports/` contient un rapport par étape : Monte-Carlo, optimisation,
FISTA, chemins d’alpha, sélection des candidats, stabilité, risque, coûts,
financement, benchmark public, refactorisation et vérification fonctionnelle.

### Scripts

- `scripts/validate.py` : validation complète en une commande ;
- `scripts/reproduce_mc_report.py` : reproduction du benchmark Monte-Carlo.

---

## 18. Qualité logicielle et reproductibilité

### Technologies

- Python 3.11 à 3.13 ;
- NumPy ;
- pandas ;
- SciPy ;
- Matplotlib ;
- JupyterLab / IPython ;
- pytest et unittest ;
- Ruff ;
- yfinance en dépendance optionnelle ;
- GitHub Actions.

### Packaging

Structure `src/`, installation éditable par `pip`, dépendances et extras
déclarés dans `pyproject.toml`.

### Validation automatisée

La commande unique vérifie :

1. la configuration `pyproject.toml` ;
2. la syntaxe des modules Python ;
3. la validité JSON des notebooks ;
4. l’ensemble des tests.

État validé le plus récent : **103 tests et 65 sous-tests réussis**.

### CI

GitHub Actions est configuré sur push et pull request avec une matrice Python
3.11, 3.12 et 3.13. L’exécution distante ne doit être annoncée comme confirmée
qu’après publication effective du dépôt et observation d’un workflow vert.

### Notebook

Le notebook possède :

- modes `fast` et `report` ;
- paramètres numériques centralisés ;
- séparation des cellules narratives et techniques ;
- sorties détaillées conditionnées par `SHOW_TECHNICAL_DETAILS` ;
- variables de marché préfixées pour éviter d’écraser le contrat ;
- contrôles syntaxiques de chaque cellule ;
- absence de sorties d’erreur stockées ;
- visualisations de surface, régularisation, parcimonie, risque et pricing.

Une nouvelle clarification des grands tableaux a été proposée mais n’est pas
encore appliquée : noms français, unités visibles et séparation des tableaux
économiques et techniques.

---

## 19. Problèmes techniques significatifs résolus

### Calendrier et maturités

Des options contractuelles arrivant un week-end étaient réglées le jour ouvré
suivant, alors que certaines grilles s’arrêtaient à la date contractuelle. Cela
provoquait des erreurs du type « trajectoire ne couvrant pas l’observation » ou
« maturité absente de la grille ». Le projet aligne désormais simulation,
observations, cash et maturités des vanilles sur la date effective de règlement.

### Imports et structure du package

Le dépôt a été migré vers une structure `src/autocall_replication`, avec
imports cohérents depuis le notebook et recherche robuste de la racine du
projet. Les fonctions techniques du notebook ont été déplacées dans le package.

### Vrais zéros de portefeuille

Une pénalisation lissée encourageait de petits poids sans les annuler. FISTA et
le seuillage proximal produisent maintenant des zéros exacts pour L1 et Elastic
Net.

### Traitement correct de Ridge

L2 ne crée pas de parcimonie exacte. Le projet utilise une référence spectrale
d’alpha et des diagnostics de poids/concentration plutôt qu’un graphique
trompeur du nombre d’actifs.

### Fuite d’information

La chronologie conditionnelle a été explicitée pour que l’état servant à
choisir le portefeuille précède le paiement. Entraînement, validation, test
réservé, stabilité, risque et financement utilisent des échantillons distincts
ou des rôles clairement séparés.

### Confusion quantité/exposition

Les poids, la valeur nette, l’exposition brute et le coût d’exécution sont
maintenant des objets distincts.

### Confusion erreur moyenne/risque extrême

L’ajout de VaR et d’Expected Shortfall a révélé que la baisse du RMSE pouvait
masquer une forte détérioration des pires scénarios.

### Confusion valeur/coût/marge

Le projet distingue désormais prix théorique, prix minimal de couverture et
prix commercial indicatif.

---

## 20. Résultats valorisables sur un CV

Les affirmations suivantes sont appuyées par le dépôt :

- développement d’un moteur Monte-Carlo vectorisé pour un autocall
  path-dependent ;
- validation par convergence, antithétiques, variable de contrôle et intervalle
  de confiance ;
- formalisation et test d’une term-sheet complète ;
- développement de cinq formulations de benchmark de réplication ;
- conception d’une politique conditionnelle pathwise sans look-ahead ;
- développement d’un solveur FISTA pour L1/Elastic Net avec cash non pénalisé ;
- sélection d’hyperparamètres par chemins de régularisation et split
  train/validation/test ;
- construction de filtres de Pareto, performance, doublons et stabilité ;
- mesure du risque par RMSE, VaR, ES et scénarios contractuels ;
- modélisation des coûts bid-ask et scénarios OTC ;
- construction d’un compte cash autofinancé et d’un ledger de couverture ;
- séparation du pricing théorique, du coût de couverture et du pricing
  commercial ;
- benchmark documentaire d’émissions structurées publiques ;
- industrialisation du prototype en package Python testé et documenté ;
- CI multi-version Python 3.11–3.13 ;
- 103 tests et 65 sous-tests réussis.

---

## 21. Résultats à présenter avec prudence

### Formulation correcte

> La réplication réduit jusqu’à environ 60 % le RMSE observé sur certains
> candidats, mais l’analyse de queue révèle une dégradation de l’Expected
> Shortfall 97,5 %, ce qui motive une stratégie hybride et une optimisation
> sensible au risque extrême.

### Formulations incorrectes

Ne pas écrire :

- « réduction globale du risque de 60 % » ;
- « stratégie rentable » ;
- « couverture complète de l’autocall » ;
- « modèle utilisé en production » ;
- « benchmark prouvant que la stratégie surperforme les desks » ;
- « coûts OTC calibrés sur des transactions réelles » ;
- « backtest historique complet » ;
- « couverture dynamique implémentée » ;
- « modèle de volatilité locale/stochastique » ;
- « VarPro implémenté » ;
- « CI distante validée » sans vérifier l’exécution GitHub ;
- « résultats finaux » pour les chiffres issus du mode rapide.

---

## 22. Limites actuelles

- Black-Scholes à volatilité, taux et dividende constants ;
- absence de smile, skew et surface de volatilité calibrée ;
- calendrier sans jours fériés ;
- barrière discrète sur les cotations disponibles ;
- sélection d’alpha encore principalement liée à l’erreur quadratique ;
- ratio Elastic Net fixé, non optimisé ;
- ES résiduel actuellement insuffisant ;
- binaires théoriques non directement liquides ;
- coûts OTC hypothétiques ;
- yfinance non adapté à une chaîne historique institutionnelle complète ;
- quantités continues non arrondies en contrats ;
- absence de multiplicateurs et tailles minimales dans l’expérience finale ;
- compte cash suivi aux observations, pas encore quotidiennement ;
- pas de suivi mark-to-market complet ;
- pas de couverture delta du résidu ;
- pas de scénarios sous mesure réelle ;
- pas de stress complet de liquidité et de modèle ;
- test final encore fermé ;
- exploration spectrale non validée ;
- benchmark public petit et non homogène.

---

## 23. Développements prévus

### Priorité immédiate

- analyser les trajectoires responsables de l’ES 97,5 % ;
- identifier les nœuds date–état et positions créant la sous-réplication ;
- intégrer une métrique de queue ou une perte asymétrique dans la sélection ;
- construire une frontière coût–RMSE–ES plutôt qu’un classement unique.

### Couverture dynamique

- valorisation mark-to-market de l’autocall ;
- delta, gamma et vega ;
- delta hedge du résidu ;
- stratégies de rebalancement quotidien, hebdomadaire ou par seuil ;
- compte cash chronologique ;
- liquidation au rappel ;
- P&L et drawdown ;
- comparaison statique, dynamique et hybride.

### Risque de modèle et marché

- smile déterministe ou volatilité locale ;
- volatilité stochastique ou local-stochastique ;
- sauts et régimes ;
- calibration d’une surface implicite ;
- évaluation sous un modèle différent de celui utilisé pour calibrer ;
- stress de taux, dividendes, volatilité, skew, liquidité et gap de spot.

### Cas pratique final

Application prévue sur SPY avec nominal de démonstration, spot et chaîne
d’options observés, portefeuille exécutable, bid/ask, multiplicateurs,
quantités entières et comparaison de quatre stratégies :

1. aucune couverture ;
2. réplication statique ;
3. couverture dynamique seule ;
4. couverture hybride, statique puis dynamique du résidu.

### Recherche de solveurs

VarPro et VPAL sont inscrits dans la feuille de route après stabilisation du
benchmark principal. Leur utilisation éventuelle concerne surtout
l’optimisation de paramètres non linéaires, par exemple les strikes ou les
paramètres d’une base spectrale. Ils ne sont pas encore implémentés.

---

## 24. Compétences démontrées

### Finance quantitative

- produits structurés et autocalls ;
- payoffs path-dependent ;
- mesure risque-neutre ;
- mouvement brownien géométrique ;
- Black-Scholes ;
- options européennes et digitales ;
- Monte-Carlo ;
- réduction de variance ;
- actualisation et conventions calendaires ;
- réplication statique et semi-statique ;
- risque de couverture ;
- VaR et Expected Shortfall ;
- financement d’une stratégie ;
- bid-ask, slippage, liquidité et scénarios OTC.

### Mathématiques et optimisation

- régression régularisée ;
- Lasso, Ridge et Elastic Net ;
- méthodes proximales ;
- FISTA ;
- norme spectrale ;
- warm starts ;
- sélection de modèles ;
- Pareto multi-critère ;
- stabilité des supports ;
- analyse de queue ;
- prévention du look-ahead bias.

### Data science

- simulation et génération de datasets ;
- splits reproductibles ;
- validation hors échantillon ;
- métriques globales et conditionnelles ;
- analyse de sensibilité ;
- visualisation scientifique ;
- données de marché et contrôles qualité.

### Software engineering

- architecture de package Python ;
- API modulaire ;
- dataclasses de configuration et résultats ;
- tests unitaires et d’intégration ;
- mocking de dépendances réseau ;
- gestion robuste des erreurs ;
- reproductibilité ;
- documentation technique ;
- refactorisation de notebook ;
- packaging `pyproject.toml` ;
- CI GitHub Actions multi-version.

---

## 25. Mots-clés pour ATS ou moteur de CV

`Python`, `NumPy`, `pandas`, `SciPy`, `Matplotlib`, `Jupyter`, `pytest`,
`GitHub Actions`, `Monte Carlo`, `Black-Scholes`, `GBM`, `structured products`,
`autocall`, `derivatives pricing`, `option replication`, `hedging`, `risk
management`, `VaR`, `Expected Shortfall`, `Lasso`, `Ridge`, `Elastic Net`,
`FISTA`, `proximal optimization`, `regularization path`, `model validation`,
`out-of-sample testing`, `transaction costs`, `bid-ask`, `OTC`, `portfolio
sparsity`, `quantitative finance`, `financial engineering`.

---

## 26. Exemples de formulations CV

Ces formulations sont des propositions factuelles à adapter à la place
disponible et au poste visé.

### Version quantitative

- Développé en Python un moteur Monte-Carlo vectorisé pour le pricing d’un
  autocall path-dependent, avec antithétiques, variable de contrôle,
  convergence et intervalles de confiance.
- Conçu une réplication conditionnelle pathwise par calls, puts et digitales,
  puis sélectionné des portefeuilles parcimonieux via L1, Ridge, Elastic Net et
  un solveur proximal FISTA.
- Évalué hors échantillon la stabilité, le financement et le risque résiduel
  par RMSE, VaR et Expected Shortfall ; identifié une réduction du RMSE mais une
  dégradation de la queue de perte, orientant le projet vers un hedge hybride.

### Version quant developer

- Transformé un prototype de recherche sur les autocalls en package Python
  modulaire, documenté et reproductible, avec validation automatique des
  notebooks et CI sur Python 3.11–3.13.
- Implémenté une interface de solveurs, FISTA avec variables non pénalisées,
  chemins de régularisation, filtres de Pareto et diagnostics de stabilité de
  portefeuille.
- Développé un ledger de financement autofinancé et des scénarios de coûts
  listés/OTC ; sécurisé calendriers, maturités, imports et absence de fuite
  d’information.

### Version risk/structuring

- Modélisé la dette d’un émetteur d’autocall et séparé risque brut, risque
  résiduel de réplication et futur risque après couverture dynamique.
- Construit un cadre de comparaison combinant erreur moyenne, risque de queue,
  parcimonie, stabilité, exposition brute, besoin de financement et coût
  d’exécution.
- Distingué valeur théorique, prix minimal de couverture et prix commercial,
  puis comparé le coussin économique à des émissions publiques documentées.

### Version très courte

- Framework Python de pricing Monte-Carlo et réplication parcimonieuse d’un
  autocall : FISTA L1/Elastic Net, validation hors échantillon, VaR/ES, coûts et
  financement ; 103 tests automatisés.

---

## 27. Questions d’entretien auxquelles le projet permet de répondre

### Pourquoi le produit est-il difficile à couvrir ?

Parce qu’il combine path dependence, rappels discrets, coupons conditionnels,
barrière de protection et discontinuités de payoff. Son exposition change
fortement près des dates d’observation et des barrières.

### Pourquoi utiliser L1 ?

Pour produire de vrais poids nuls et réduire le nombre d’instruments, ce qui
prépare une stratégie plus lisible et moins coûteuse à exécuter.

### Pourquoi ne pas utiliser uniquement le RMSE ?

Parce qu’une stratégie peut améliorer la majorité des trajectoires tout en
créant de très grandes sous-couvertures rares. C’est précisément ce que l’ES
97,5 % a révélé.

### Pourquoi une politique conditionnelle ?

Parce que le panier pertinent dépend de la survie et de l’état contractuel de
l’autocall. Un portefeuille unique ne représente pas correctement les
changements de cashflows après chaque observation.

### Pourquoi garder Calls + Puts et Full ?

Calls + Puts fournit une référence plus liquide. Full mesure le gain théorique
des digitales. Leur comparaison permet de distinguer précision mathématique et
négociabilité.

### Pourquoi remplacer les binaires par des spreads ?

Une digitale peut être approchée par un spread vertical de vanilles. Cela
permet de transformer une base théorique en positions plus proches
d’instruments disponibles, au prix d’une approximation du saut de payoff.

### Que signifie le besoin de financement ?

Même si le payoff terminal est bien répliqué, l’émetteur peut devoir avancer du
cash lors de l’achat initial ou des transitions entre paniers. Le ledger mesure
ce risque de liquidité intermédiaire.

### Quel est le principal résultat négatif ?

La baisse du RMSE ne s’accompagne pas d’une baisse de l’ES 97,5 %. La stratégie
actuelle protège les scénarios usuels mais sous-réplique trop fortement certains
scénarios extrêmes.

### Quelle serait la prochaine amélioration ?

Diagnostiquer la queue de perte, intégrer une pénalisation asymétrique ou
sensible à l’ES, puis couvrir dynamiquement le résidu et tester la stratégie
sous coûts réels et risque de modèle.

---

## 28. Formulation finale recommandée pour une autre IA

La rédaction finale du CV doit positionner ce travail comme :

> un projet de recherche en finance quantitative et de développement Python
> portant sur la réplication robuste, parcimonieuse et économiquement évaluée
> d’un autocall, avec une attention particulière à la validation numérique, au
> risque de queue et à la reproductibilité logicielle.

L’originalité la plus défendable à ce stade n’est pas d’avoir créé un nouveau
pricer bancaire. Elle réside dans la chaîne d’analyse intégrée : contrat testé,
Monte-Carlo validé, multiples benchmarks, sélection parcimonieuse, stabilité,
risque hors échantillon, coûts, financement et diagnostic honnête des échecs en
queue de distribution.
