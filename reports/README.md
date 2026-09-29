# Rapports du projet

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Le projet accumule plusieurs validations techniques et méthodologiques. |
| **Problème** | Retrouver rapidement le document correspondant à chaque étape. |
| **Méthode** | Centralisation et classement des rapports dans un dossier unique. |
| **Modifications** | Ajout d’un index descriptif et d’une convention d’en-tête commune. |
| **Résultats** | Chaque évolution importante dispose d’un rapport identifiable. |


Ce dossier centralise les rapports méthodologiques et les documents de validation du projet.
Les résultats quantitatifs courants sont figés manuellement dans
`../output/pdf/resultats_courants.pdf`. Ce fichier est remplacé uniquement
lorsqu'une nouvelle exécution a été relue et retenue comme référence.

## Contenu

### Dossier de passation pour CV et portfolio

[CV_PROJECT_HANDOFF.md](CV_PROJECT_HANDOFF.md)

Description exhaustive et factuelle du projet destinée à une personne ou une
IA chargée de rédiger un CV : finance, mathématiques, architecture, résultats,
limites, compétences, mots-clés et formulations possibles.

### Rapport d’avancement général

[PROJECT_STATUS_REPORT.md](PROJECT_STATUS_REPORT.md)

Synthèse rédigée de l’ensemble du projet jusqu’au risque résiduel, au
financement, aux trois prix et au benchmark public. Elle distingue les
résultats validés, les estimations exploratoires et les limites actuelles.

### Trois prix et benchmark public

[INDUSTRY_PRICING_BENCHMARK.md](INDUSTRY_PRICING_BENCHMARK.md)

Prix théorique, prix minimal de couverture, prix commercial indicatif,
amélioration du risque face au non-couvert et à `calls_puts`, puis comparaison
documentaire aux écarts publics prix–valeur estimée.

### Coût et financement de la politique conditionnelle

[CONDITIONAL_FUNDING_COSTS.md](CONDITIONAL_FUNDING_COSTS.md)

Prix Black-Scholes, exposition brute, compte cash autofinancé, transformation
des binaires en spreads verticaux et variantes OTC favorable/centrale/stressée.

### Migration vers la politique conditionnelle pathwise

[CONDITIONAL_POLICY_MIGRATION.md](CONDITIONAL_POLICY_MIGRATION.md)

Politique sans anticipation, alpha global sur l’erreur totale par trajectoire,
comparaison `calls_puts` / `full`, stabilité, risque indépendant et coût attendu
pondéré par la fréquence d’atteinte des nœuds.

### Risque terminal et exposition résiduelle de réplication

[TERMINAL_REPLICATION_RISK.md](TERMINAL_REPLICATION_RISK.md)

Progression en trois niveaux, convention de perte de l'émetteur, valeurs
actualisées, résultats en montant/%/bps, réductions relatives et séparation
entre valeur théorique du panier et coût d'exécution.

### Stabilité, risque et coûts de transaction

[STABILITY_RISK_TRANSACTION_COSTS.md](STABILITY_RISK_TRANSACTION_COSTS.md)

Dix recalibrations par profil, métriques de risque terminales et conditionnelles,
cotations yfinance, scénarios OTC des binaires et filtre comparant le coût à la
réduction d'Expected Shortfall.

### Trois profils par pénalité

[CANDIDATE_PROFILES.md](CANDIDATE_PROFILES.md)

Filtre de performance statique par bootstrap apparié, audit des doublons
stricts et quasi stricts, puis profils performance, compromis et parcimonie
calculés séparément pour L1, L2 et Elastic Net.

### Comparaison des pénalités et affichage de la parcimonie

[ALPHA_PENALTIES_AND_SPARSITY_DISPLAY.md](ALPHA_PENALTIES_AND_SPARSITY_DISPLAY.md)

Recherche sur la famille `full` avec L1, L2 et Elastic Net à ratio fixe,
filtrage de plusieurs candidats par pénalité, traitement spécifique de Ridge et
diagnostics de parcimonie lisibles.

### Chemin de régularisation pathwise

[PATHWISE_ALPHA_PATH.md](PATHWISE_ALPHA_PATH.md)

Split 60/20/20, calcul automatique d'`alpha_max`, warm starts, métriques de
validation et frontière de Pareto du benchmark payoff pathwise.

### Solveur parcimonieux FISTA

[FISTA_SOLVER.md](FISTA_SOLVER.md)

Implémentation et validation du vrai L1/Elastic Net proximal, avec zéros exacts,
cash non pénalisé, convergence explicite et test dans les cinq pipelines.

### Fondation pour l'optimisation parcimonieuse

[PORTFOLIO_OPTIMIZATION_FOUNDATION.md](PORTFOLIO_OPTIMIZATION_FOUNDATION.md)

Diagnostic des poids, séparation cash/options et interface commune préparant
la comparaison future de L1, Elastic Net, VPAL et VarPro.

### Vérification fonctionnelle

[VERIFICATION_FONCTIONNELLE.md](VERIFICATION_FONCTIONNELLE.md)

Compte rendu reproductible des imports, tests, calendriers et scénarios du
benchmark conditionnel, dont le scénario de référence à 2 000 trajectoires.

### Refactorisation du notebook

[NOTEBOOK_REFACTORING.md](NOTEBOOK_REFACTORING.md)

Rapport de l'étape ayant déplacé le benchmark conditionnel hors du notebook,
centralisé son implémentation dans le package et ajouté les tests associés.

### Validation Monte-Carlo

[MONTE_CARLO_VALIDATION.md](MONTE_CARLO_VALIDATION.md)

Rapport reproductible présentant :

- la configuration numérique de référence ;
- le prix, l'erreur standard et l'intervalle de confiance à 95 % ;
- la convergence en nombre de trajectoires ;
- l'effet de la fréquence de surveillance de la barrière ;
- le gain obtenu avec la variable de contrôle ;
- les limites actuelles du moteur.

## Documents qui restent hors de ce dossier

- `docs/TERM_SHEET.md` : source de vérité contractuelle du produit ;
- `docs/ROADMAP.md` : feuille de route du projet ;
- `README.md` : documentation générale destinée aux utilisateurs du dépôt.

Les images temporaires de rendu situées dans `tmp/` ne sont pas des rapports et ne doivent pas être ajoutées ici.
