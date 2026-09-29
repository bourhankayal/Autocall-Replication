# Rapport d’avancement — réplication d’un autocall

**Date du rapport : 2 septembre 2026**  
**Périmètre : état du projet jusqu’au benchmark de risque et de pricing**

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Le projet cherche à répliquer les engagements d’un autocall avec un portefeuille parcimonieux d’options, puis à mesurer le risque qui subsiste pour l’émetteur. |
| **Problème** | Une faible erreur moyenne ne garantit ni une bonne protection dans les scénarios extrêmes, ni une stratégie finançable ou exécutable en pratique. |
| **Méthode** | Contrat figé, pricing Monte-Carlo, benchmarks successifs, politique conditionnelle pathwise, sélection régulière d’alpha, mesure indépendante du risque et compte de financement autofinancé. |
| **Modifications** | Le code a été structuré en package, les tests et rapports centralisés, les erreurs calendaires corrigées, les optimisations unifiées et le notebook réorganisé autour d’un parcours lisible. |
| **Résultats** | La réplication réduit fortement le RMSE global, mais dégrade actuellement l’Expected Shortfall 97,5 % dans les scénarios de sous-réplication extrême. Le financement et les trois niveaux de prix sont maintenant mesurables. |

---

## 1. Objectif général

Le produit étudié est vendu par un émetteur à un client. En contrepartie de la
prime encaissée, l’émetteur promet les flux contractuels de l’autocall. Le but
du projet n’est donc pas seulement de calculer une valeur théorique, mais de
répondre à la question suivante :

> Dans quelle mesure un portefeuille d’options parcimonieux, compréhensible et
> potentiellement négociable permet-il de financer les flux de l’autocall et de
> réduire le risque restant à la charge de l’émetteur ?

Le travail est organisé en trois niveaux :

1. **Risque brut de l’autocall** : dette de l’émetteur sans réplication.
2. **Risque résiduel de réplication** : dette moins flux du portefeuille
   statique ou conditionnel.
3. **Risque final après couverture dynamique** : dette moins réplication moins
   gains de la couverture dynamique.

Les niveaux 1 et 2 sont aujourd’hui implémentés. Le niveau 3 reste à construire.

---

## 2. Contrat de référence

Le notebook utilise actuellement un autocall synthétique mono-sous-jacent avec
les paramètres suivants :

| Paramètre | Valeur |
|---|---:|
| Nominal | 100 |
| Spot initial | 100 |
| Seuil de rappel | 100 % du spot initial |
| Coupon par observation éligible | 2 % du nominal |
| Barrière coupon par défaut du produit | 80 % du spot initial |
| Barrière de protection | 70 % du spot initial |
| Observations | 3, 6, 9 et 12 mois |
| Taux sans risque | 3 % |
| Rendement du dividende | 1 % |
| Volatilité Black-Scholes | 20 % |

Les dates contractuelles sont reportées au premier jour ouvré disponible selon
le calendrier simplifié du projet. Les seuils sont toujours exprimés par
rapport au spot initial contractuel.

Les principales branches du payoff sont testées : rappels aux différentes
observations, coupons, absence de rappel, perte à maturité, franchissement de
barrière, égalité exacte aux seuils, trajectoires incomplètes et dates tombant
un week-end.

---

## 3. Pricing Monte-Carlo

L’autocall est valorisé sous mesure risque-neutre dans un modèle
Black-Scholes à volatilité constante. Le moteur comprend :

- simulation vectorisée des trajectoires ;
- graines reproductibles ;
- variables antithétiques ;
- variable de contrôle ;
- intervalle de confiance ;
- études de convergence en nombre de trajectoires ;
- contrôle de la fréquence de surveillance de la barrière.

Le prix obtenu dans l’estimation rapide utilisée pour l’analyse économique est
d’environ :

\[
V_{\mathrm{autocall}} \approx 100{,}48
\]

pour un nominal de 100. Cette valeur reste dépendante du modèle retenu. Elle ne
constitue pas encore un prix de marché exécutable, car la volatilité est
constante et les données bid-ask ne sont pas intégrées.

---

## 4. Évolution des benchmarks de réplication

Plusieurs formulations ont été étudiées successivement :

1. réplication d’une surface de prix ;
2. réplication d’un payoff moyen sur une grille date–spot ;
3. réplication du payoff total trajectoire par trajectoire ;
4. réplication des cashflows par date ;
5. réplication conditionnelle selon la date et l’état du produit.

Les premiers benchmarks restent utiles comme contrôles pédagogiques, mais la
suite de l’étude repose sur la **politique conditionnelle pathwise**. Elle est
plus cohérente avec l’autocall : le portefeuille applicable à une date dépend
de la survie du produit et de son état contractuel, sans utiliser d’information
future.

Deux familles principales sont conservées :

- `calls_puts` : instruments usuels et généralement plus liquides ;
- `full` : calls, puts et options binaires, afin de mesurer l’apport des
  discontinuités même si les binaires sont moins directement négociables.

Pour rendre `full` plus réaliste, les binaires peuvent ensuite être :

- conservées théoriquement ;
- remplacées par des spreads verticaux de calls ou de puts ;
- traitées comme instruments OTC selon trois scénarios de coût.

---

## 5. Optimisation et parcimonie

L’objectif n’est pas seulement de minimiser l’erreur, mais également de limiter
le nombre d’instruments et l’instabilité des poids.

Les pénalités comparées sont :

- **L1** : produit des poids exactement nuls et favorise la sélection
  d’instruments ;
- **L2 ou Ridge** : stabilise les poids, mais ne crée normalement pas de zéros
  exacts ;
- **Elastic Net** : combine parcimonie L1 et stabilisation L2.

Le solveur proximal FISTA a été ajouté pour traiter proprement L1 et Elastic
Net. Le cash n’est pas pénalisé comme une option risquée. Les diagnostics
incluent notamment convergence, nombre d’options actives, positions longues et
courtes, concentration, exposition monétaire nette et brute.

### Sélection d’alpha

La sélection suit un protocole `train / validation / test` :

- entraînement des poids sur l’échantillon d’apprentissage ;
- sélection des candidats sur la validation ;
- conservation du test final pendant l’exploration.

Les candidats sont filtrés par pénalité. Sont notamment supprimés :

- les solutions ayant moins de 2 ou plus de 100 options actives ;
- les solutions dominées au sein d’une même pénalité ;
- les doublons stricts et quasi stricts, avec audit des suppressions ;
- les solutions ne passant pas le filtre de performance statique.

Trois profils sont conservés par pénalité lorsque cela est possible :

- **performance** : erreur de validation minimale ;
- **compromis** : équilibre entre erreur et parcimonie ;
- **parcimonie** : nombre minimal d’instruments parmi les solutions encore
  défendables.

La stabilité est ensuite vérifiée sur dix recalibrations. Alpha et poids sont
figés avant les évaluations de risque et de financement indépendantes.

---

## 6. Mesure du risque

### 6.1 Conventions

Tous les flux sont actualisés à la date de valorisation. Du point de vue de
l’émetteur :

\[
L_{\mathrm{brut}} = H_0 - V_0
\]

\[
E_{\mathrm{réplication}} = H_0 - R_0
\]

où :

- \(H_0\) est le payoff actualisé dû au client ;
- \(V_0\) est la valeur théorique de l’autocall ;
- \(R_0\) est le payoff actualisé fourni par la réplication.

Une valeur positive de \(E_{\mathrm{réplication}}\) représente une
**sous-réplication** : le portefeuille ne fournit pas assez pour payer le
client.

Les métriques publiées comprennent RMSE, MAE, biais, perte maximale, VaR et
Expected Shortfall à plusieurs niveaux. Elles sont exprimées en montant, en
pourcentage et en points de base du nominal. Les résultats sont aussi
conditionnés au rappel, à l’arrivée à maturité et au franchissement de la
barrière.

### 6.2 Interprétation du graphique RMSE

Le risque brut présente un RMSE proche de **7,7** pour un nominal de 100. Selon
la famille et le profil, la réplication ramène approximativement ce RMSE entre
**2,6 et 5,8** dans le graphique actuel.

Une valeur résiduelle de 3 correspond par exemple à :

\[
1 - \frac{3}{7{,}7} \approx 61\% 
\]

de réduction du RMSE. La réplication améliore donc nettement la précision
globale sur la majorité des trajectoires.

### 6.3 Interprétation du graphique Expected Shortfall 97,5 %

L’Expected Shortfall 97,5 % mesure la perte moyenne dans les 2,5 % de scénarios
les plus défavorables. Dans le graphique actuel :

- ES brut : environ **4,4** ;
- ES résiduel selon les candidats : environ **8,5 à 14**.

Les barres résiduelles sont donc supérieures à la barre brute. Cela signifie
que les portefeuilles actuels réduisent l’erreur habituelle, mais créent une
sous-couverture beaucoup plus importante dans certains scénarios extrêmes.

Ce résultat n’est pas contradictoire avec l’amélioration du RMSE : une méthode
peut être précise dans 97,5 % des scénarios et très mauvaise dans les 2,5 %
restants. L’optimisation actuelle est encore trop orientée vers l’erreur
globale et pas suffisamment vers la queue de distribution.

### 6.4 Conclusion sur le risque actuel

La réplication est **utile en moyenne mais insuffisante dans la queue**. Aucun
candidat ne doit être choisi uniquement parce que son RMSE est faible. La
décision doit simultanément considérer :

- RMSE résiduel ;
- ES 97,5 % résiduel ;
- biais de sous-réplication ;
- stabilité ;
- financement ;
- coût de transaction ;
- possibilité de couvrir dynamiquement le résidu.

---

## 7. Financement de la stratégie

Le moteur suit un compte cash autofinancé. L’émetteur :

1. encaisse la prime de l’autocall ;
2. achète le panier initial ;
3. place ou emprunte le solde ;
4. reçoit les payoffs des options aux observations ;
5. paie le client ;
6. achète le panier de l’état suivant si le produit survit.

La récurrence comptable est :

```text
cash avant règlement = cash précédent capitalisé
cash après règlement = cash avant + payoff options - paiement autocall
cash final de l’étape = cash après règlement - coût du panier suivant
```

Un compte négatif représente un besoin d’emprunt. Deux grandeurs sont
distinguées :

- **coût net** : valeur signée du portefeuille ;
- **exposition brute** : somme des valeurs absolues des positions, qui révèle
  le levier même lorsque des positions longues et courtes se compensent.

### Estimation rapide du profil représentatif

Le calcul exploratoire a utilisé le profil conditionnel L1 `compromis`, famille
`full`, avec remplacement des binaires par des spreads verticaux de largeur 5.
Il a donné, pour un nominal de 100 :

| Mesure | Estimation rapide |
|---|---:|
| Prime théorique encaissée | 100,48 |
| Coût initial net du panier | 101,17 |
| Besoin de financement initial | 0,69 |
| Besoin de capital supplémentaire P95 | 3,90 |
| Achats bruts cumulés | 105,55 |
| P&L terminal moyen | -0,23 |
| Écart-type du P&L terminal | 5,90 |
| Expected Shortfall de perte 97,5 % | 7,44 |

Ces nombres proviennent d’un calcul rapide avec peu de trajectoires. Ils sont
des ordres de grandeur, pas les résultats finaux du mode `report`.

Les achats bruts cumulés de 105,55 ne représentent pas 5,55 de frais : ils
mesurent le volume acheté au cours de la stratégie. Le bid-ask, le slippage, le
coût du capital et les commissions doivent encore être ajoutés.

---

## 8. Les trois niveaux de prix

Trois prix sont désormais calculés séparément :

### 8.1 Prix théorique

\[
P_{\mathrm{théorique}} = V_{\mathrm{autocall}}
\]

Il correspond à la valeur du passif sous le modèle choisi.

### 8.2 Prix minimal de couverture

\[
P_{\mathrm{couverture}}
= P_{\mathrm{simulation}} - \mathbb{E}[P\&L_{\mathrm{terminal}}]
\]

Il compense la perte terminale moyenne estimée de la stratégie. Il ne garantit
pas la couverture des scénarios extrêmes.

### 8.3 Prix commercial indicatif

\[
P_{\mathrm{commercial}}
= P_{\mathrm{couverture}} + \text{marge cible}
\]

La marge cible vaut provisoirement 1 % du nominal dans le notebook. C’est une
hypothèse de travail et non une marge observée.

Dans une émission structurée commercialisée au pair, le desk ne facture pas
nécessairement 101,71 au client : il peut conserver un prix d’émission de 100
et ajuster le coupon, la barrière ou une autre caractéristique jusqu’à obtenir
le coussin économique recherché. Les trois prix servent ici à rendre le besoin
de marge visible avant cette future étape de structuration inverse.

Avec l’estimation rapide :

| Prix | Valeur pour un nominal de 100 |
|---|---:|
| Prix théorique | 100,48 |
| Prix minimal de couverture | 100,71 |
| Prix commercial indicatif | 101,71 |

Si le produit était vendu exactement 100 dans cette estimation, le P&L moyen
serait proche de **-0,71 %**. S’il est vendu 100,48, le P&L moyen simulé est
proche de **-0,23 %**.

---

## 9. Benchmark externe

Le P&L effectivement réalisé par les desks de produits structurés n’est pas
public au niveau de chaque émission. Une comparaison directe de notre P&L avec
celui d’un desk précis serait donc impossible à justifier.

Le benchmark public retenu compare plutôt :

\[
\text{prix d’émission} - \text{valeur initiale estimée par l’émetteur}
\]

Quatre exemples SEC sont intégrés dans le projet : JPMorgan, Barclays, Morgan
Stanley et Goldman Sachs. Leur écart documenté se situe approximativement entre
**2,45 % et 11 %** selon l’émission et la borne de valorisation publiée.

Notre coussin commercial exploratoire vaut :

\[
101{,}71 - 100{,}48 = 1{,}23\% \text{ du nominal.}
\]

Il est inférieur à la fourchette des exemples publics. Cette comparaison doit
rester prudente : l’écart public agrège commissions de distribution, frais de
structuration, coûts de couverture, coûts opérationnels et profits projetés.
Il ne correspond ni à une marge nette, ni à un P&L réalisé.

Sources documentaires :

- [JPMorgan — Auto Callable Notes](https://www.sec.gov/Archives/edgar/data/19617/000121390025028272/ea0236912-01_424b2.htm)
- [Barclays — Auto-Callable Notes](https://www.sec.gov/Archives/edgar/data/312070/000191870425019389/form424b2.htm)
- [Morgan Stanley — Jump Notes with Auto-Callable Feature](https://www.sec.gov/Archives/edgar/data/895421/000183988226023540/ms15872_424b2-15430.htm)
- [Goldman Sachs — Autocallable Contingent Coupon Notes](https://www.sec.gov/Archives/edgar/data/0000886982/000095017025052435/amznco11_auto_prelim.htm)

Le notebook distingue maintenant :

- amélioration technique par rapport au produit non couvert ;
- amélioration de `full` par rapport à `calls_puts`, à profil comparable ;
- coussin commercial par rapport aux exemples publics.

---

## 10. Traitement des coûts d’exécution

Les formules des prix Black-Scholes sont affichées dans le notebook. Pour les
binaires, trois implémentations économiques sont conservées :

1. **théorique** : binaire cash-or-nothing valorisée au modèle ;
2. **spread vertical** : approximation par deux calls ou deux puts ;
3. **OTC** : payoff exact avec scénario de charge favorable, central ou
   stressé.

Les hypothèses OTC provisoires sont 5, 10 et 25 points de base du payout. Elles
ne sont pas des quotes de dealer.

Une extension yfinance existe pour récupérer des bid et ask d’options cotées.
Elle est désactivée par défaut, car les maturités et strikes nécessaires ne sont
pas toujours disponibles et une donnée manquante ne doit jamais être remplacée
silencieusement par zéro.

---

## 11. État de validation technique

La validation complète réalisée après l’ajout du benchmark de pricing donne :

```text
103 tests réussis
65 sous-tests réussis
```

Elle couvre notamment :

- payoff contractuel et calendriers ;
- Monte-Carlo et convergence ;
- optimisation FISTA ;
- chemins de régularisation ;
- politique conditionnelle ;
- stabilité ;
- mesures de risque ;
- scénarios de coûts ;
- identité comptable du financement ;
- trois prix et benchmark public ;
- structure et imports du notebook.

Le passage des tests garantit la cohérence du code avec les conventions
implémentées. Il ne garantit pas encore la validité économique sous un modèle
de marché réaliste.

---

## 12. Limites actuelles

Les principales limites à conserver dans toute présentation sont :

1. modèle Black-Scholes à volatilité constante ;
2. absence de smile et de volatilité locale ou stochastique ;
3. sélection d’alpha encore fondée principalement sur l’erreur de validation ;
4. forte dégradation actuelle de l’ES 97,5 % ;
5. options binaires théoriques non directement liquides ;
6. spreads verticaux valorisés au mid dans le scénario central actuel ;
7. bid-ask réel et slippage non intégrés au parcours principal ;
8. compte suivi aux observations et non quotidiennement ;
9. absence de couverture dynamique du résidu ;
10. benchmark public réduit et non homogène ;
11. résultats économiques rapides à confirmer en mode `report` ;
12. test final encore réservé pendant l’exploration.

---

## 13. Conclusion intermédiaire

Le projet ne se limite plus à une régression donnant une erreur faible. Il
forme maintenant une chaîne cohérente :

```text
contrat non ambigu
        ↓
payoff testé
        ↓
Monte-Carlo validé
        ↓
benchmarks statiques
        ↓
politique conditionnelle pathwise
        ↓
sélection parcimonieuse et stable
        ↓
risque brut et risque résiduel
        ↓
financement autofinancé
        ↓
prix théorique / couverture / commercial
        ↓
benchmark public documentaire
```

La conclusion quantitative actuelle est nuancée :

> La réplication réduit sensiblement l’erreur globale, mais elle n’est pas
> encore défendable dans les scénarios extrêmes, où l’Expected Shortfall de
> sous-réplication dépasse le risque brut.

L’amélioration prioritaire ne consiste donc plus simplement à diminuer le
RMSE. Elle consiste à réduire la queue de perte tout en contrôlant coût,
stabilité, liquidité et financement.

---

## 14. Prochaines étapes recommandées

### Étape immédiate — diagnostic des pertes extrêmes

- identifier les trajectoires composant l’ES 97,5 % ;
- les classer par rappel, maturité, barrière touchée et niveau terminal du spot ;
- mesurer quels nœuds et quelles positions produisent la sous-réplication ;
- comparer `calls_puts`, `full` théorique et `full` transformé en spreads.

Cette étape doit précéder toute nouvelle optimisation : il faut comprendre si
la mauvaise queue provient du payoff, de la sélection d’alpha, des contraintes
de parcimonie ou de la transformation des binaires.

### Étape suivante — sélection sensible au risque de queue

- ajouter ES ou une perte asymétrique au critère de sélection ;
- ne pas choisir une solution uniquement avec le RMSE ;
- conserver plusieurs candidats sur une frontière coût–RMSE–ES ;
- ouvrir le test final seulement lorsque la règle de sélection sera figée.

### Phase 2 — suivi mark-to-market et couverture dynamique

- valoriser l’autocall et les options restantes à chaque date ;
- créer un compte cash autofinancé quotidien ou selon une fréquence explicite ;
- gérer maturités, rappels et liquidation ;
- couvrir dynamiquement le résidu ;
- mesurer P&L, turnover, drawdown et coût de couverture.

### Phase 3 — risque économique et coûts réels

- scénarios sous mesure réelle ;
- données bid-ask ;
- coûts de liquidation ;
- stress de volatilité et de liquidité ;
- comparaison statique, dynamique et hybride ;
- application finale à un cas pratique de couverture.
