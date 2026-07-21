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

- [ ] Rédiger une mini-term-sheet unique servant de source de vérité.
- [ ] Préciser la nature exacte du produit : Athena, Phoenix ou autre variante.
- [ ] Préciser si les coupons sont conditionnels, garantis et/ou à mémoire.
- [ ] Préciser si le coupon est payé à la date de rappel.
- [ ] Préciser si la barrière de protection est européenne, américaine ou
      observée à une fréquence donnée.
- [ ] Préciser les règles `>` ou `>=` pour chaque barrière.
- [ ] Préciser le remboursement à maturité dans chaque scénario.
- [ ] Définir le calendrier, la convention de jour ouvré et le report des dates.
- [ ] Définir les conventions de taux, dividendes, actualisation et fraction
      d'année.
- [ ] Vérifier que le code et tous les notebooks utilisent exactement ces mêmes
      conventions.

**Critère de validation :** une table exhaustive des scénarios contractuels
permet de calculer manuellement chaque cashflow sans ambiguïté.

### 2. Tester le payoff et les cas limites

- [ ] Ajouter des tests unitaires déterministes sur chaque branche du payoff.
- [ ] Tester un rappel à chacune des dates d'observation.
- [ ] Tester spot exactement sur, juste sous et juste au-dessus des barrières.
- [ ] Tester coupon payé, non payé et, le cas échéant, coupon à mémoire.
- [ ] Tester barrière de protection touchée et non touchée.
- [ ] Tester le produit non rappelé avec remboursement au pair et avec perte.
- [ ] Tester une date d'observation tombant un week-end ou un jour férié.
- [ ] Tester données manquantes, trajectoire trop courte et dates mal ordonnées.
- [ ] Vérifier que le produit cesse d'accumuler du risque et des flux après son
      rappel.
- [ ] Créer quelques trajectoires jouets dont le résultat attendu est calculé
      à la main.

**Critère de validation :** toutes les branches contractuelles sont couvertes
par des tests automatisés et reproductibles.

### 3. Fiabiliser le Monte-Carlo

- [ ] Corriger et documenter la grille temporelle : jours calendaires ou jours
      de bourse, sans contradiction entre le code et les commentaires.
- [ ] Séparer clairement simulation sous mesure risque-neutre et simulation
      historique/réelle.
- [ ] Vectoriser les simulations pour obtenir des temps de calcul raisonnables.
- [ ] Utiliser une graine reproductible et des générateurs aléatoires contrôlés.
- [ ] Ajouter antithétiques et, si possible, une variable de contrôle.
- [ ] Utiliser des nombres aléatoires communs pour comparer deux stratégies.
- [ ] Produire un intervalle de confiance, pas uniquement une erreur standard.
- [ ] Réaliser une étude de convergence en nombre de trajectoires et en pas de
      temps.
- [ ] Vérifier l'absence de biais important de discrétisation de la barrière.
- [ ] Comparer le moteur à des cas dégénérés disposant d'une solution analytique
      ou d'un benchmark indépendant.

**Critère de validation :** le prix converge, l'incertitude statistique est
publiée et deux exécutions avec la même configuration donnent le même résultat.

### 4. Rendre l'expérience reproductible

- [ ] Créer une structure de package claire (`src/`, `tests/`, `notebooks/`,
      `data/`, `reports/`).
- [ ] Ajouter `pyproject.toml` ou un fichier de dépendances versionnées.
- [ ] Ajouter `.gitignore` et retirer du suivi les caches et sorties temporaires.
- [ ] Corriger l'encodage du README actuellement mal affiché.
- [ ] Transformer les paramètres dispersés en configuration explicite.
- [ ] Ajouter une commande unique reproduisant les résultats principaux.
- [ ] Nettoyer les notebooks, leurs sorties lourdes et le code dupliqué.
- [ ] Ajouter formatage, lint, contrôle des types et tests automatiques.
- [ ] Ajouter une intégration continue exécutant au minimum les tests rapides.

**Critère de validation :** une personne extérieure peut cloner le dépôt,
installer les dépendances et reproduire une figure/table principale sans aide.

---

## P1 — Transformer le prototype en étude quantitative solide

### 5. Formaliser le problème de réplication

- [ ] Écrire mathématiquement les trois objectifs actuellement étudiés.
- [ ] Dire précisément à quelle date les poids sont estimés et quand ils sont
      autorisés à changer.
- [ ] Séparer strictement scénarios d'entraînement, de validation et de test.
- [ ] Éviter toute information future dans la construction du portefeuille.
- [ ] Inclure une position cash/obligataire pour représenter le nominal et les
      flux certains.
- [ ] Vérifier le coût initial de la réplication et sa cohérence avec le prix de
      l'autocall.
- [ ] Vérifier si la stratégie est autofinancée ou documenter les apports/retraits
      de cash.
- [ ] Documenter les ventes à découvert et autres contraintes autorisées.
- [ ] Mesurer le conditionnement de la matrice et l'instabilité des poids.
- [ ] Ajouter une régularisation ridge comme benchmark de stabilité.
- [ ] Ajouter une pénalisation L1 ou une sélection parcimonieuse d'instruments.
- [ ] Comparer optimisation non contrainte, contraintes de positions et solution
      parcimonieuse.

### 6. Construire des benchmarks incontestables

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
- [ ] Mesurer stabilité des poids, concentration et nombre d'instruments.
- [ ] Mesurer coût initial, turnover et coûts de transaction.
- [ ] Présenter distributions complètes et intervalles de confiance.
- [ ] Normaliser les erreurs par le nominal pour faciliter l'interprétation.

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

- [ ] Réécrire le README depuis le début avec résumé, question de recherche,
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

## Définition de « projet sérieux » — version minimale

Le projet peut être présenté comme sérieux lorsque tous les points suivants sont
vrais :

- [ ] Le contrat est non ambigu et intégralement testé.
- [ ] Les résultats sont reproductibles sur une installation propre.
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
