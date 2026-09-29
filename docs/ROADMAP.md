# Feuille de route — réplication robuste d'un autocall

## Objectif du projet

Construire et évaluer une réplication **statique, dynamique et hybride** d'un
autocall mono-sous-jacent, puis déterminer quels risques peuvent être capturés
par un portefeuille parcimonieux d'options vanilles et dans quelles conditions
la réplication se dégrade.

Question de recherche proposée :

> Jusqu'où une réplication statique simple, liquide et interprétable peut-elle
> réduire le risque d'un autocall avant qu'une couverture dynamique devienne
> indispensable ?

## État déjà atteint

- [x] Définition d'un autocall discret mono-sous-jacent.
- [x] Pricing Monte-Carlo sous Black-Scholes à volatilité constante.
- [x] Implémentation de calls, puts et options binaires synthétiques.
- [x] Première réplication statique par portefeuille de vanilles.
- [x] Comparaison de trois objectifs : surface de prix, espérance de payoff et
      payoff pathwise.
- [x] Premières métriques : MAE, RMSE, biais et erreur maximale.
- [x] Première exploration d'une base spectrale.

---

## P0 — Bloquants pour être crédible

### 1. Figer la définition contractuelle

- [x] Rédiger une mini-term-sheet unique servant de source de vérité.
- [x] Préciser la nature exacte du produit : Athena, Phoenix ou autre variante.
- [x] Préciser si les coupons sont conditionnels, garantis et/ou à mémoire.
- [x] Préciser si le coupon est payé à la date de rappel.
- [x] Préciser si la barrière de protection est européenne, américaine ou
      observée à une fréquence donnée.
- [x] Préciser les règles `>` ou `>=` pour chaque barrière.
- [x] Préciser le remboursement à maturité dans chaque scénario.
- [x] Définir le calendrier, la convention de jour ouvré et le report des dates.
- [x] Définir les conventions de taux, dividendes, actualisation et fraction
      d'année.
- [ ] Vérifier que le code et tous les notebooks utilisent exactement ces mêmes
      conventions.

**Critère de validation :** une table exhaustive des scénarios contractuels
permet de calculer manuellement chaque cashflow sans ambiguïté.

### 2. Tester le payoff et les cas limites

- [x] Ajouter des tests unitaires déterministes sur chaque branche du payoff.
- [x] Tester un rappel à chacune des dates d'observation.
- [x] Tester spot exactement sur, juste sous et juste au-dessus des barrières.
- [x] Tester coupon payé, non payé et, le cas échéant, coupon à mémoire.
- [x] Tester barrière de protection touchée et non touchée.
- [x] Tester le produit non rappelé avec remboursement au pair et avec perte.
- [x] Tester une date d'observation tombant un week-end. Les jours fériés sont
      hors périmètre du calendrier simplifié validé en version 1.0.
- [x] Tester données manquantes, trajectoire trop courte et dates mal ordonnées.
- [x] Vérifier que le produit cesse d'accumuler du risque et des flux après son
      rappel.
- [x] Créer quelques trajectoires jouets dont le résultat attendu est calculé
      à la main.

**Critère de validation :** toutes les branches contractuelles sont couvertes
par des tests automatisés et reproductibles.

### 3. Fiabiliser le Monte-Carlo

- [x] Corriger et documenter la grille temporelle : jours calendaires ou jours
      de bourse, sans contradiction entre le code et les commentaires.
- [x] Séparer clairement simulation sous mesure risque-neutre et simulation
      historique/réelle.
- [x] Vectoriser les simulations pour obtenir des temps de calcul raisonnables.
- [x] Utiliser une graine reproductible et des générateurs aléatoires contrôlés.
- [x] Ajouter des variables antithétiques.
- [x] Ajouter une variable de contrôle après avoir mesuré son gain.
- [x] Utiliser des nombres aléatoires communs pour comparer deux stratégies.
- [x] Produire un intervalle de confiance, pas uniquement une erreur standard.
- [x] Fournir une étude de convergence en nombre de trajectoires.
- [x] Réaliser une étude de convergence en pas de
      temps.
- [x] Mesurer le biais de sous-échantillonnage de la barrière par rapport à la
      surveillance quotidienne contractuelle.
- [x] Comparer le moteur à des cas dégénérés disposant d'une solution analytique
      ou d'un benchmark indépendant.

**Critère de validation :** le prix converge, l'incertitude statistique est
publiée et deux exécutions avec la même configuration donnent le même résultat.

### 4. Rendre l'expérience reproductible

- [x] Créer une structure de package claire (`src/`, `tests/`, `notebooks/`,
      `data/`, `reports/`).
- [x] Ajouter `pyproject.toml` ou un fichier de dépendances versionnées.
- [x] Ajouter `.gitignore` et retirer du suivi les caches et sorties temporaires.
- [x] Remplacer le README incomplet par un README racine lisible et correctement
      encodé.
- [ ] Transformer les paramètres dispersés en configuration explicite.
- [x] Ajouter une commande unique reproduisant les résultats principaux.
- [ ] Nettoyer les notebooks, leurs sorties lourdes et le code dupliqué.
- [ ] Ajouter formatage, lint, contrôle des types et tests automatiques.
- [x] Ajouter une intégration continue exécutant la validation sous Python 3.11,
      3.12 et 3.13.

**Critère de validation :** une personne extérieure peut cloner le dépôt,
installer les dépendances et reproduire une figure/table principale sans aide.

---

## P1 — Transformer le prototype en étude quantitative solide

### 5. Formaliser le problème de réplication

- [ ] Écrire mathématiquement les trois objectifs actuellement étudiés.
- [x] Dire précisément à quelle date les poids sont estimés et quand ils sont
      autorisés à changer.
- [x] Séparer strictement scénarios d'entraînement, de validation et de test.
- [x] Éviter toute information future dans la construction du portefeuille.
- [x] Inclure une position cash/obligataire pour représenter le nominal et les
      flux certains.
- [x] Vérifier le coût initial de la réplication et sa cohérence avec le prix de
      l'autocall.
- [x] Vérifier si la stratégie est autofinancée ou documenter les apports/retraits
      de cash.
- [ ] Documenter les ventes à découvert et autres contraintes autorisées.
- [ ] Mesurer le conditionnement de la matrice et l'instabilité des poids.
- [x] Ajouter une interface commune de solveurs en conservant le comportement
      historique comme référence `legacy`.
- [ ] Migrer les futurs solveurs derrière cette interface puis supprimer
      `fit_linear` lorsque plus aucun appel direct ni notebook n'en dépendra.
- [ ] Ajouter une régularisation ridge comme benchmark de stabilité.
- [x] Ajouter un vrai solveur proximal FISTA pour L1 et Elastic Net, avec
      zéros exacts, cash non pénalisé et diagnostic de convergence.
- [x] Ajouter une formulation L0 pénalisée
      `erreur + alpha_0 * nombre_de_lignes`, résolue par gradient proximal et
      seuillage dur sans imposer à l'avance un nombre fixe d'instruments.
- [ ] Comparer rigoureusement L0 à L1 et Elastic Net : plusieurs initialisations,
      stabilité des supports, minima locaux, coût et performance hors
      échantillon. Ne jamais présenter la solution L0 comme un optimum global.
- [x] Construire le chemin de régularisation en `alpha` et conserver toute la
      frontière erreur / nombre d'instruments avant sélection économique.
- [x] Implémenter ce chemin avec un split 60/20/20 sur le benchmark payoff
      pathwise, en laissant le test final fermé pendant l'exploration.
- [ ] Étendre le chemin d'`alpha` aux cashflows statiques avec le même principe
      train / validation / test.
- [x] Étendre le chemin d'`alpha` au benchmark conditionnel en définissant si un
      alpha unique doit être partagé entre toutes les dates et tous les états.
- [ ] Étendre Elastic Net à une recherche conjointe de l'`alpha` et du ratio
      `rho` (`l1_ratio`) au lieu de conserver arbitrairement `rho = 0,5` :
      construire une grille bidimensionnelle reproductible, sélectionner les
      couples `(alpha, rho)` uniquement sur train/validation, laisser le test
      final fermé, puis comparer erreur, parcimonie, stabilité des supports,
      exposition monétaire, risque résiduel et coûts de transaction. Inclure
      les limites `rho = 0` (Ridge) et `rho = 1` (Lasso) comme contrôles, et
      éviter de retenir plusieurs couples économiquement quasi identiques.
- [ ] Étendre le chemin d'`alpha` aux surfaces de prix et de payoff moyen après
      définition d'un split adapté au faible nombre de dates disponibles.
- [ ] Intégrer ensuite les comparaisons de chemins d'`alpha` dans le notebook,
      après validation séparée de chaque protocole.
- [ ] Comparer optimisation non contrainte, contraintes de positions et solution
      parcimonieuse.
- [ ] Étudier VarPro après stabilisation du benchmark parcimonieux principal :
      distinguer le VarPro classique de Golub-Pereyra et VPAL, puis tester son
      apport pour les strikes ou les paramètres de la base spectrale.

### 6. Construire des benchmarks incontestables

- [x] Séparer benchmark technique interne et benchmark public de pricing ;
      publier trois prix et documenter explicitement que l'écart public
      prix–valeur estimée n'est pas le P&L réalisé d'un desk.
- [ ] Ajouter les benchmarks triviaux : cash seul, sous-jacent + cash, calls
      seuls et calls + puts.
- [ ] Comparer grille uniforme et grille concentrée autour des barrières.
- [ ] Comparer maturités aux observations, maturités mensuelles et maturités
      réellement cotées.
- [ ] Remplacer les binaires non cotées par des call spreads/put spreads lorsque
      la comparaison vise une stratégie tradable.
- [ ] Comparer réplication statique, delta-hedging et stratégie hybride.
- [ ] Publier aussi les résultats négatifs et les cas où une méthode échoue.

### 7. Évaluer autre chose que l'erreur moyenne

- [ ] Conserver MAE, RMSE, biais et erreur maximale.
- [ ] Ajouter quantiles de perte, VaR et Expected Shortfall/CVaR de l'erreur.
- [ ] Mesurer séparément les erreurs près des barrières.
- [ ] Mesurer séparément les erreurs près des dates d'observation.
- [ ] Conditionner les résultats au rappel précoce, à l'absence de rappel et à
      l'activation de la protection.
- [x] Mesurer le nombre d'instruments, les positions longues/courtes et la
      concentration des poids, en séparant explicitement le cash des options.
- [x] Ajouter l'exposition monétaire brute et nette à partir des prix des
      instruments ; ne pas la confondre avec la somme des quantités de contrats.
- [x] Mesurer la stabilité des poids entre graines, échantillons et calibrations.
- [ ] Mesurer coût initial, turnover et coûts de transaction. Le coût attendu
      conditionnel est disponible ; financement et turnover restent à faire.
- [ ] Présenter distributions complètes et intervalles de confiance.
- [ ] Normaliser les erreurs par le nominal pour faciliter l'interprétation.
- [ ] Refaire une étude distincte et complète des fonctions de perte, au lieu de
      mélanger robustification de l'erreur et pénalisation des poids : moindres
      carrés, MAE, Huber, quantile et pertes asymétriques, avec protocole commun.
- [ ] Tester une optimisation explicitement orientée risque de queue :
      `MSE + gamma * CVaR_97.5% + pénalité`, puis comparer au calibrage MSE sur
      RMSE, biais, VaR, Expected Shortfall et régimes contractuels critiques.

### 8. Justifier et valider l'approche spectrale

- [ ] Expliquer le lien exact entre le noyau spectral, les straddles et le payoff
      path-dependent de l'autocall.
- [ ] Démontrer les hypothèses et le domaine de validité de la décomposition.
- [ ] Vérifier numériquement orthogonalité, valeurs propres et erreur de
      troncature.
- [ ] Comparer la base spectrale à une grille naïve avec le même nombre
      d'instruments.
- [ ] Tester la sensibilité au nombre de composantes et au domaine de spot.
- [ ] Montrer si l'approche améliore réellement précision, parcimonie ou
      stabilité hors échantillon.
- [ ] Retirer ou repositionner cette partie si elle n'apporte pas un gain mesuré.

---

## P2 — Se rapprocher des contraintes d'un desk

### 9. Intégrer des données de marché

- [ ] Choisir un sous-jacent et une période d'étude précis.
- [ ] Documenter la source, la date, la licence et le nettoyage des données.
- [ ] Importer spot, courbe de taux, dividendes et chaîne d'options.
- [ ] Filtrer les quotes aberrantes, illiquides ou violant des bornes simples.
- [ ] Construire une surface de volatilité implicite cohérente.
- [ ] Contrôler les arbitrages calendaires et de butterfly.
- [ ] Interpoler/extrapoler la surface avec une méthode documentée.
- [ ] Utiliser uniquement strikes et maturités réellement disponibles dans le
      benchmark « tradable ».
- [ ] Intégrer bid, ask, tailles minimales et une hypothèse de liquidité.

### 10. Ajouter les coûts et contraintes d'exécution

- [ ] Valoriser l'achat à l'ask et la vente au bid.
- [ ] Ajouter coûts proportionnels et, si utile, coûts fixes.
- [ ] Ajouter contraintes de taille, de position et de maturité.
- [ ] Pénaliser les portefeuilles très concentrés ou instables.
- [ ] Définir une politique de rebalancement périodique et/ou par seuil.
- [ ] Mesurer le compromis erreur de hedge / coûts / turnover.
- [ ] Réaliser des stress de liquidité avec spreads élargis.

### 11. Ajouter la couverture dynamique et hybride

- [ ] Calculer delta, gamma et vega avec une méthode numériquement stable.
- [ ] Traiter les discontinuités du payoff pour limiter le bruit des grecques.
- [ ] Implémenter un delta-hedge avec plusieurs fréquences de rebalancement.
- [ ] Implémenter une politique par bande/seuil pour réduire le turnover.
- [ ] Couvrir dynamiquement le résidu après constitution du portefeuille statique.
- [ ] Comparer statique, dynamique et hybride à coût égal et à risque égal.
- [ ] Expliquer les P&L de couverture par facteur de risque.
- [ ] Étudier spécifiquement les sauts de delta près des observations/barrières.

### 12. Mesurer le risque de modèle

- [ ] Garder Black-Scholes comme benchmark pédagogique.
- [ ] Ajouter au minimum un smile déterministe ou une volatilité locale.
- [ ] Ajouter ensuite un modèle de volatilité stochastique ou local-stochastique
      si le temps le permet.
- [ ] Tester des trajectoires avec sauts ou changements de régime.
- [ ] Construire la réplication sous un modèle et l'évaluer sous un autre.
- [ ] Choquer niveau de vol, skew, vol-of-vol, dividendes, taux et gap de spot.
- [ ] Distinguer erreur numérique, erreur statistique et erreur de modèle.
- [ ] Identifier les hypothèses qui influencent le plus le prix et le hedge.

---

## P3 — Contribution de recherche et présentation finale

### 13. Formuler l'apport original

- [ ] Positionner le projet comme une étude de réplication robuste et
      parcimonieuse, pas comme un nouveau pricer bancaire.
- [ ] Définir une fonction objectif combinant erreur, coût, parcimonie,
      instabilité et pertes extrêmes.
- [ ] Tester si une réplication statique réduit réellement le besoin de hedge
      dynamique.
- [ ] Identifier les risques « statiquement capturables » et ceux qui restent
      intrinsèquement dynamiques.
- [ ] Quantifier le gain marginal de chaque complexité ajoutée.
- [ ] Formuler une conclusion falsifiable, y compris si le résultat est négatif.

### 14. Produire une documentation professionnelle

- [x] Réécrire le README depuis le début avec résumé, question de recherche,
      installation, exemple minimal, résultats et limites.
- [ ] Ajouter un schéma du pipeline : contrat → pricing → réplication → hedge →
      évaluation.
- [ ] Ajouter la formule exacte du payoff et un diagramme des cashflows.
- [ ] Ajouter un tableau clair des hypothèses et conventions.
- [ ] Publier une table principale comparant toutes les stratégies.
- [ ] Publier des graphiques lisibles avec unités, légendes et intervalles.
- [ ] Ajouter une analyse économique des résultats, pas seulement numérique.
- [ ] Ajouter bibliographie et liens vers les références utilisées.
- [ ] Ajouter limites, risques de modèle et avertissement d'usage.
- [ ] Préparer un résumé d'une page et une présentation orale de 5 minutes.

### 15. Obtenir une validation extérieure

- [ ] Faire relire la term-sheet et le payoff par une personne connaissant les
      produits structurés.
- [ ] Faire relire la méthodologie par un quant ou chercheur indépendant.
- [ ] Préparer 5 à 10 questions précises plutôt qu'une demande générale d'avis.
- [ ] Recueillir et consigner les retours sans demander d'information
      confidentielle ou propriétaire.
- [ ] Transformer chaque retour accepté en issue ou tâche traçable.
- [ ] Documenter les désaccords et choix méthodologiques importants.

---

## Ordre d'exécution conseillé

1. Term-sheet et tests du payoff.
2. Reproductibilité, structure du dépôt et tests automatiques.
3. Monte-Carlo fiable avec convergence et intervalles de confiance.
4. Formalisation de la réplication et benchmarks simples.
5. Régularisation, parcimonie et validation hors échantillon.
6. Métriques de risque autour des barrières et dates d'observation.
7. Données de marché, surface de volatilité et instruments tradables.
8. Coûts de transaction et stratégie hybride.
9. Risque de modèle et scénarios de stress.
10. Validation de l'apport spectral et rédaction finale.

---

## Développement recommandé en trois phases

Cette séquence devient la référence pour poursuivre l'analyse du risque et de
la couverture. Une phase peut préparer les composants techniques d'une phase
ultérieure, mais les conclusions doivent respecter cet ordre de validation.

### Phase 1 — Risque terminal statique

Progression retenue :

```text
Niveau 1 : dette autocall sans réplication
        ↓
Niveau 2 : exposition résiduelle après réplication statique
        ↓
Niveau 3 : future couverture dynamique appliquée au résidu
```

À terminer et consolider maintenant :

- [x] mesurer le risque brut de l'autocall ;
- [x] mesurer l'exposition résiduelle de réplication de chaque candidat ;
- [x] calculer les ratios de réduction de risque ;
- [x] produire les métriques conditionnelles au rappel, à la maturité et au
      franchissement de la barrière ;
- [x] généraliser toutes les sorties en montant, pourcentage et points de base du
      nominal ;
- [x] conserver le test final fermé ;
- [x] ne pas mélanger cette phase avec un suivi mark-to-market.

Cette phase réutilise directement le dataset pathwise. L'échantillon de risque
indépendant ne sert ni à recalibrer les poids ni à sélectionner `alpha`.

**Critère de sortie de phase :** tous les profils stables disposent d'une table
terminale comparable, dans les trois unités demandées, sans ouverture du test
final.

### Phase 2 — Suivi mark-to-market

À développer ensuite :

- [ ] valoriser l'autocall à chaque date de suivi ;
- [ ] valoriser sous Black-Scholes les options encore vivantes ;
- [x] construire un compte cash autofinancé aux dates d’observation ;
- [x] gérer explicitement les maturités et règlements des options ;
- [x] liquider le portefeuille de réplication lors d'un rappel anticipé ; avec
      les paniers une période actuels, aucune position ne subsiste après règlement.
- [ ] calculer le P&L et le drawdown chronologiques de la couverture ;
- [ ] distinguer les états juste avant et juste après chaque événement
      contractuel ;
- [ ] garantir l'absence de look-ahead dans toutes les valorisations.

La valorisation intermédiaire de l'autocall nécessitera probablement une
surface conditionnelle ou une approximation par régression afin d'éviter un
Monte-Carlo imbriqué très coûteux. La méthode retenue devra être comparée à un
petit benchmark Monte-Carlo imbriqué sur des points de contrôle.

**Critère de sortie de phase :** le ledger permet de reconstruire chaque flux,
chaque règlement, la valeur de liquidation et le P&L résiduel sur une
trajectoire complète.

### Phase 3 — Risque économique et coûts réels

À développer enfin :

- [ ] simuler des scénarios sous mesure réelle ;
- [ ] consolider les données bid-ask yfinance avec snapshots datés et contrôles
      de qualité ;
- [ ] calculer les coûts d'entrée et de liquidation ;
- [ ] stresser la volatilité et la liquidité ;
- [ ] comparer les stratégies statique, dynamique et hybride ;
- [ ] comparer les stratégies à risque égal et à coût égal ;
- [ ] séparer données de marché observées et hypothèses de scénarios OTC.

Les briques yfinance, validation bid-ask et scénarios OTC favorable, central et
stressé sont déjà disponibles. Elles constituent une préparation technique et
ne signifient pas que la phase économique complète est validée.

**Critère de sortie de phase :** la conclusion distingue clairement risque de
couverture, risque de modèle, coût d'exécution et risque économique sous mesure
réelle.

### Phase 4 — Cas pratique final de couverture sur SPY

Cette phase constitue l'application pratique finale des trois phases
méthodologiques précédentes. Elle doit adopter le point de vue d'un émetteur
ayant vendu un autocall et devant couvrir sa dette envers le client.

#### A. Définir une transaction réaliste

- [ ] Construire un autocall sur SPY avec le spot de marché réellement observé,
      sans normaliser artificiellement le sous-jacent à 100 dans le ticket final.
- [ ] Fixer un nominal de démonstration, par exemple 100 000 USD.
- [ ] Reprendre les conventions de la term-sheet validée : observations,
      coupon, seuil de rappel et barrière de protection.
- [ ] Valoriser la prime initiale reçue par l'émetteur.
- [ ] Enregistrer la date, le spot, les paramètres de marché et toutes les
      hypothèses utilisées pour rendre l'expérience reproductible.

#### B. Construire le portefeuille réellement exécutable

- [ ] Télécharger la chaîne d'options SPY disponible à la date de constitution.
- [ ] Construire un univers composé de calls et puts listés réellement cotés.
- [ ] Comparer l'univers `FULL` théorique à une version tradable où les binaires
      sont remplacées par des spreads verticaux.
- [ ] Produire un ticket de couverture indiquant instrument, échéance, strike,
      quantité, bid, ask, prix d'exécution et coût.
- [ ] Appliquer multiplicateurs, tailles minimales et arrondis en contrats.
- [ ] Recalculer le risque après passage des poids continus aux quantités
      réellement négociables.

#### C. Comparer quatre stratégies

- [ ] Mesurer l'autocall sans couverture, avec cash uniquement.
- [ ] Mesurer la couverture statique conservée jusqu'au rappel ou à maturité.
- [ ] Implémenter une couverture dynamique seule du delta de l'autocall.
- [ ] Implémenter une couverture hybride : portefeuille statique puis delta
      hedge du risque résiduel.
- [ ] Tester plusieurs fréquences de rebalancement : quotidienne, hebdomadaire
      et politique par seuil.

Le P&L économique sera défini par :

```text
P&L de couverture
= prime reçue pour l'autocall
− flux versés au client
+ P&L des options
+ P&L du cash
− coûts d'entrée
− coûts de rebalancement
− coûts de liquidation
```

#### D. Tester les scénarios contractuels critiques

- [ ] Rappel dès la première observation.
- [ ] Spot restant juste sous le seuil de rappel à plusieurs observations.
- [ ] Coupon non payé sans franchissement de la barrière de protection.
- [ ] Barrière touchée puis remontée du sous-jacent.
- [ ] Forte baisse finale avec remboursement indexé sur la performance.
- [ ] Choc de volatilité sans mouvement important du spot.
- [ ] Élargissement des spreads au moment du rappel et de la liquidation.

#### E. Ajouter des expériences complémentaires

- [ ] Rejouer plusieurs trajectoires historiques du sous-jacent : hausse,
      baisse progressive, choc, reprise et marché latéral.
- [ ] Présenter ces expériences comme des replays du sous-jacent avec options
      revalorisées par modèle tant qu'aucune chaîne historique fiable n'est
      disponible.
- [ ] Étudier la possibilité d'un portefeuille fictif suivi en temps réel avec
      snapshots datés et journal de P&L.

#### F. Produire les livrables pratiques

- [ ] Publier le ticket initial du portefeuille de couverture.
- [ ] Publier un journal chronologique contenant spot, état contractuel, valeur
      de l'autocall, valeur du hedge, cash, coûts et P&L résiduel.
- [ ] Publier un rapport de risque avec delta, exposition, drawdown, turnover et
      Expected Shortfall.
- [ ] Comparer non couvert, statique, dynamique et hybride dans une table unique.
- [ ] Comparer les stratégies à coût égal puis à risque égal.
- [ ] Quantifier le gain de risque et le coût marginal de chaque complexité.

**Critère de sortie de phase :** le projet doit pouvoir répondre de façon
chiffrée à la question suivante : une réplication statique ou hybride réduit-elle
réellement le risque économique de l'autocall après coûts, contraintes de
négociation, rappel anticipé et stress de marché ?

---

## Backlog décisionnel — idées à ressortir au bon moment

Cette section centralise les pistes validées comme pertinentes mais non encore
autorisées pour implémentation. Elles doivent être réexaminées lorsque leur
déclencheur devient vrai, et non ajoutées prématurément au cœur du modèle.

### A. Dès que les candidats `full` sont calculés

#### OPT-T01 — Mesurer l'exposition monétaire

- [x] Valoriser chaque ligne avec son prix, son poids et son multiplicateur.
- [x] Calculer exposition brute, longue, courte et nette.
- [ ] Ventiler les expositions par type d'option, maturité et zone de strike.
- [x] Ne plus confondre somme des poids et montant monétaire.

**Déclencheur :** la table des candidats L1/Elastic Net sur `family="full"` est
disponible et examinée.

#### OPT-T02 — Contrôler levier et positions extrêmes

- [ ] Calculer exposition brute / nominal de l'autocall.
- [ ] Mesurer poids maximal, exposition courte et ratio brut/net.
- [ ] Définir des limites configurables de ligne, levier et vente à découvert.
- [ ] Identifier les solutions dont la faible erreur repose sur de grandes
      positions longues et courtes qui se compensent.

**Dépendance :** OPT-T01.

#### OPT-T03 — Supprimer les candidats quasi identiques

- [x] Comparer supports actifs, poids normalisés, prédictions et RMSE.
- [x] Définir une équivalence statistique plutôt qu'une égalité numérique.
- [ ] Dans chaque groupe équivalent, conserver le plus parcimonieux, le moins
      coûteux ou le plus stable selon une règle documentée.
- [x] Ne pas imposer arbitrairement un nombre fixe de candidats avant
      l'attribution transparente des trois rôles de présentation.

**Déclencheur :** trop de points subsistent après convergence, bornes 2–100 et
Pareto calculé séparément dans chaque pénalité.

#### OPT-T04 — Mesurer le gain marginal de complexité

- [ ] Calculer la diminution de RMSE par option supplémentaire.
- [ ] Calculer ensuite la diminution de RMSE par unité de coût supplémentaire.
- [ ] Identifier les zones où ajouter des instruments n'apporte presque plus de
      précision.
- [ ] Afficher les points de coude sans les transformer automatiquement en règle
      de sélection.

**Déclencheur :** plusieurs candidats non dominés restent disponibles.

#### OPT-T05 — Conserver plusieurs profils réellement différents

- [x] Identifier un candidat orienté précision.
- [x] Identifier un candidat orienté parcimonie.
- [x] Identifier un candidat de compromis erreur-complexité.
- [ ] Identifier un candidat orienté coût lorsque les coûts seront disponibles.
- [ ] Identifier un candidat orienté stabilité après validation multi-graines.
- [ ] Éviter de présenter plusieurs variantes pratiquement identiques comme des
      choix économiquement distincts.

**Dépendances :** OPT-T03, puis OPT-T07 et OPT-T10 selon le profil.

### B. Avant d'utiliser les candidats dans les recherches suivantes

#### OPT-T06 — Renforcer les métriques d'erreur contractuelles

- [ ] Ajouter quantiles 95 % et 99 % de l'erreur absolue.
- [ ] Ajouter Expected Shortfall/CVaR des erreurs les plus fortes.
- [ ] Mesurer RMSE sous la barrière de protection.
- [ ] Mesurer RMSE près du seuil de rappel et des barrières de coupon.
- [ ] Séparer trajectoires rappelées et trajectoires allant à maturité.
- [ ] Écarter ou signaler un candidat bon en moyenne mais dangereux dans un
      régime contractuel important.

**Déclencheur :** les candidats de la frontière pathwise sont disponibles.

#### OPT-T07 — Tester stabilité et sélection des instruments

- [x] Répéter les calibrations sur dix graines.
- [x] Mesurer moyenne et dispersion de la RMSE.
- [x] Mesurer variation du nombre d'options et des poids.
- [ ] Calculer fréquence de sélection de chaque instrument dans une table dédiée.
- [x] Calculer similarité de Jaccard des supports.
- [ ] Étudier un portefeuille consensus fondé sur les instruments sélectionnés
      de manière récurrente.

**Déclencheur :** avant toute ouverture du test final ou propagation automatique
des candidats aux autres benchmarks.

#### OPT-T08 — Appliquer une tolérance statistique de performance

- [x] Utiliser un bootstrap apparié unilatéral à 95 % sur la validation fixe.
- [x] N'utiliser une tolérance relative fixe que comme solution provisoire et
      explicitement paramétrée.
- [x] Conserver les candidats statistiquement proches du meilleur de leur norme,
      sans imposer un candidat unique.

**Dépendance :** OPT-T07.

### C. Avant de qualifier un portefeuille de « tradable »

#### OPT-T09 — Séparer base théorique et univers réellement négociable

- [ ] Attribuer à chaque instrument un statut `tradable`,
      `tradable_with_restrictions` ou `theoretical_only`.
- [ ] Produire une comparaison `FULL théorique` / `FULL tradable`.
- [ ] Vérifier spécifiquement la disponibilité des options binaires.
- [ ] Si nécessaire, remplacer les binaires par des call spreads/put spreads et
      mesurer la dégradation de précision, le gamma et le nombre de lignes.
- [ ] Utiliser uniquement les instruments réellement disponibles dans les
      conclusions économiques.

**Déclencheur :** choix du marché, du sous-jacent et des données disponibles.

#### OPT-T10 — Construire un modèle de frais de transaction

- [ ] Revoir entièrement la qualité des coûts estimés avant toute conclusion :
      provenance et horodatage des quotes, nettoyage bid/ask, stale quotes,
      profondeur, multiplicateurs, unités, moneyness, maturité, scénarios OTC
      binaires, slippage, liquidation anticipée et cohérence en bps du nominal.
- [ ] Séparer clairement données observées, proxies construits et hypothèses de
      scénario ; associer à chaque coût un statut de qualité et une sensibilité.

- [ ] Calculer slippage, commission par contrat et coût fixe par ligne.
- [x] Calculer le bid-ask et traiter séparément calls/puts standards et binaires.
- [x] Prévoir deux modes : cotations yfinance et scénarios d'hypothèses.
- [x] Produire au minimum des scénarios liquide, central et stress, sans les
      présenter comme données de marché tant qu'ils ne sont pas sourcés.
- [x] Exprimer le coût total en points de base du nominal de l'autocall.
- [ ] Ajouter un budget maximal configurable, sans fixer sa valeur avant
      validation économique.
- [ ] Calculer une frontière RMSE / coût / parcimonie séparément dans chaque
      pénalité.

**Dépendances :** OPT-T01 et OPT-T09.

#### OPT-T11 — Mesurer concentration économique et liquidité

- [ ] Mesurer concentration par maturité, type d'option et moneyness.
- [ ] Compter maturités et strikes réellement utilisés.
- [ ] Ajouter tailles minimales, profondeur disponible et limites de position.
- [ ] Signaler les portefeuilles concentrés sur une maturité ou une zone de
      barrière même lorsque le nombre total d'options semble élevé.

**Dépendances :** OPT-T01 et données de marché.

#### OPT-T12 — Tester lots, multiplicateurs et arrondis

- [ ] Définir multiplicateurs, quantités minimales et pas de quantité.
- [ ] Arrondir les poids continus selon les règles de négociation.
- [ ] Recalculer après arrondi erreur, exposition et coût.
- [ ] Écarter les solutions dont la qualité disparaît après arrondi réaliste.

**Dépendances :** OPT-T01, OPT-T09 et OPT-T10.

#### OPT-T13 — Ajouter marge, collatéral et financement

- [ ] Modéliser besoins de marge des positions courtes.
- [ ] Mesurer collatéral et capital immobilisé.
- [ ] Séparer coût de financement du cash et frais d'exécution des options.
- [ ] Comparer les candidats en coût de capital, pas uniquement en coût initial.

**Déclencheur :** lorsque les règles de vente à découvert et le cadre de marché
sont définis.

### D. Après validation du modèle de coûts

#### OPT-T14 — Intégrer les coûts dans l'optimisation

- [ ] Commencer par utiliser les coûts comme filtre post-optimisation.
- [x] Implémenter dans le moteur une pénalisation L1 pondérée
      `lambda * sum(c_i * abs(w_i))`, sans encore l'activer dans la sélection
      économique tant que les coûts unitaires ne sont pas validés.
- [x] Implémenter la formulation combinant coût fixe et proportionnel
      `lambda_0 * ||w||_0 + lambda_1 * sum(c_i * abs(w_i))`.
- [ ] Après validation des coûts, construire les chemins bidimensionnels des
      intensités fixe et proportionnelle, puis sélectionner uniquement sur
      train/validation avec test final fermé.
- [ ] Vérifier que les options coûteuses sont pénalisées sans détériorer les
      scénarios contractuels critiques.
- [ ] Comparer sélection postérieure et optimisation directement coût-aware.
- [x] Garder les coefficients de coûts configurables et désactivés par défaut,
      afin qu'aucune hypothèse de spread non validée ne modifie les résultats.

**Dépendance :** OPT-T10 validé économiquement.

#### OPT-T15 — Étendre les coûts au semi-statique et au dynamique

- [ ] Calculer le turnover `abs(w_t - w_{t-1})` à chaque rebalancement.
- [ ] Mesurer coût moyen, quantiles et stress du coût pathwise.
- [ ] Comparer stratégies à coût égal et à risque égal.
- [ ] Étudier politiques de rebalancement périodiques et par seuil.

**Déclencheur :** début de la couverture dynamique du résidu.

### E. Avant la conclusion finale

#### OPT-T16 — Tester la robustesse hors Black-Scholes

- [ ] Choquer vol, skew, taux, dividendes et niveau de spot.
- [ ] Tester volatilité locale/stochastique, sauts et changements de régime.
- [ ] Construire sous un modèle et évaluer sous un autre.
- [ ] Inclure gaps baissiers et scénarios proches des barrières.
- [ ] Utiliser ces stress pour mesurer le risque de modèle, sans recalibrer alpha
      sur le test final.

**Déclencheur :** candidats stables, tradables et économiquement évalués.

### Règle de réactivation du backlog

À chaque fin d'étape, vérifier les déclencheurs ci-dessus. Lorsqu'un déclencheur
devient vrai :

1. ressortir les tâches concernées dans la discussion ;
2. présenter objectif, modifications, fichiers, hypothèses et tests ;
3. obtenir une autorisation explicite avant toute implémentation ;
4. consigner le résultat dans `reports/` et mettre à jour cette feuille de route.

## Définition de « projet sérieux » — version minimale

Le projet peut être présenté comme sérieux lorsque tous les points suivants sont
vrais :

- [ ] Le contrat est non ambigu et intégralement testé.
- [x] Les résultats sont reproductibles sur une installation propre.
- [ ] Le Monte-Carlo est accompagné d'une étude de convergence.
- [ ] Il existe des benchmarks simples et une séparation train/test honnête.
- [ ] Le coût initial, le cash et les contraintes de portefeuille sont traités.
- [ ] Les résultats incluent pertes extrêmes et zones proches des barrières.
- [ ] Au moins une comparaison statique / dynamique / hybride est disponible.
- [ ] Au moins un test hors Black-Scholes mesure le risque de modèle.
- [ ] Les limites et hypothèses sont affichées aussi clairement que les résultats.
- [ ] Une commande ou un notebook propre reproduit la conclusion principale.

## Hors périmètre initial

À ne traiter qu'après validation du cœur du projet :

- [ ] Autocalls worst-of multi-sous-jacents et corrélation dynamique.
- [ ] XVA, risque de contrepartie et capital réglementaire complet.
- [ ] Reinforcement learning ou deep hedging.
- [ ] Infrastructure temps réel ou moteur de production.
- [ ] Optimisation au niveau d'un book complet de produits structurés.

Ces sujets sont intéressants, mais ne compensent pas un payoff non testé, une
expérience non reproductible ou une évaluation sans coûts de transaction.
