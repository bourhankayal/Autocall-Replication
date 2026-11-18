# Passation du rapport V1

Ce document accompagne `rapport_autocall_v1.tex`. Il distingue ce qui manque
réellement au notebook, les affichages utiles à ajouter et les fichiers à
importer dans Overleaf.

## 1. Statut actuel du rapport

La V1 est rédigée intégralement à partir de deux sources traçables :

- la recherche d'hyperparamètres REPORT promue du 15 octobre 2026 ;
- le notebook FAST terminé le 9 novembre 2026.

Les chiffres du run FAST sont explicitement présentés comme provisoires. Le jeu
de test final est toujours réservé et n'a pas été utilisé. La V1 ne remplace pas
la V0 et peut évoluer indépendamment.

## 2. Ce qui manque encore dans le notebook

### Obligatoire avant de figer les résultats

1. **Réexécuter le notebook depuis un noyau propre en mode REPORT.** Les ajouts
   OLS, delta hedge et tableau unifié sont plus récents
   que le dernier export de `output/latest`.
2. **Exporter le tableau unifié des benchmarks.** Il doit réunir, avec des
   conventions clairement comparables : autocall non couvert, delta hedge
   quotidien, delta hedge cinq jours, réplication statique,
   politique conditionnelle dense et politiques
   conditionnelles parcimonieuses.
3. **Faire apparaître les lignes OLS** dans les tableaux statique et
   conditionnel. Elles permettront de mesurer l'effet propre de la
   régularisation par rapport à une régression non pénalisée.
4. **Exporter les résultats delta** dans un CSV séparé, même s'ils sont ensuite
   repris dans le tableau unifié.
5. **Relancer la recherche REPORT sur la grille étendue.** Plusieurs solutions
   ES de l'ancien run touchaient la borne minimale d'alpha ; elles ne peuvent
   pas encore être qualifiées d'optima intérieurs.
6. **Geler la méthode, puis ouvrir le test final une seule fois.** Le manifeste
   final doit garder la trace de la date, des graines, des volumes et des
   identifiants de politiques.

### Théorie ou conventions à expliciter dans le notebook

- Définir une seule fois le signe du résidu : `passif autocall - flux du hedge`.
- Expliquer le centrage utilisé pour le risque brut, afin que l'ES brut de 4,49
  ne soit pas interprété comme le montant du passif.
- Définir précisément l'information disponible dans l'état conditionnel à
  chaque date et montrer qu'aucune information future n'y entre.
- Distinguer le hedge conditionnel à dates fixes d'un delta hedge dynamique.
- Indiquer que le delta hedge actuel porte sur l'autocall brut, pas sur le
  résidu après réplication optionnelle.
- Distinguer poids financiers du portefeuille et poids statistiques de
  l'importance sampling.
- Justifier pourquoi le coût de transaction reste une extension conceptuelle :
  aucune donnée crédible de bid-ask, profondeur, taille ou OTC n'est disponible.

Il ne manque pas de théorème indispensable pour écrire la V1. Ce qui manque est
surtout l'alignement expérimental final et l'explicitation de ces conventions.

## 3. Affichages utiles qui manquent encore

### Priorité haute

1. **Tableau comparatif unifié**, avec pour chaque benchmark : univers,
   fréquence de décision, capital initial, nombre de positions, RMSE, ES 97,5 %,
   perte maximale, besoin de financement et statut des coûts.
2. **Distribution du résidu** des quatre stratégies principales sur un même
   axe, avec un zoom séparé sur la queue droite. Une densité seule masque les
   observations extrêmes : préférer histogramme ou fonction de survie
   empirique en échelle logarithmique.
3. **Décomposition de l'ES par régime contractuel** : rappel au premier,
   deuxième ou troisième fixing, survie à maturité, barrière de protection
   touchée ou non. Le notebook exporte déjà des tables de décomposition ; il
   manque un visuel simple pour le rapport.
4. **Support du portefeuille retenu** : heatmap maturité × strike des quantités
   pour Calls + Puts Elastic Net et Full Elastic Net. Cela rend la parcimonie
   réellement interprétable.
5. **Comparaison OLS / Ridge / Lasso / Elastic Net / L0** sur un graphique
   erreur--nombre de positions, à partir du nouveau run.

### Priorité moyenne

- chronologie visuelle du contrat et des décisions de hedge ;
- fréquence de rappel et probabilité de barrière touchée ;
- convergence du prix avec intervalle de confiance en fonction du nombre de
  trajectoires ;
- comparaison des cashflows dus et répliqués par date ;
- besoins de financement par quantiles, une fois le capital initial aligné.

### À ne pas mettre au centre

- un graphique de coûts calculé avec des hypothèses arbitraires ;
- un prix commercial présenté comme une estimation de marge réelle ;
- trop de courbes d'alpha individuelles dans le corps du rapport ;
- les figures de surface de prix ou de payoff moyen qui appartiennent aux
  benchmarks pédagogiques historiques.

## 4. Visuels à importer dans Overleaf

Créer un sous-dossier `figures` dans Overleaf et y déposer les PDF vectoriels.
Le `.tex` compile même s'ils sont absents : un encadré indique alors le nom du
fichier attendu.

### Corps du rapport — indispensables

| Fichier Overleaf | Source locale actuelle | Rôle |
|---|---|---|
| `figures/decision_dashboard.pdf` | `output/hyperparameters/runs/2026-10-15_225308_report/figures/decision_dashboard.pdf` | sélection des politiques |
| `figures/multi_seed_stability.pdf` | même dossier, `multi_seed_stability.pdf` | stabilité multi-graines |
| `figures/conditional_method_payment_comparison.pdf` | `output/latest/figures/conditional_method_payment_comparison.pdf` | cashflows datés vs total terminal |
| `figures/risk_rmse_reduction.pdf` | `output/latest/figures/risk_rmse_reduction.pdf` | gain moyen de réplication |
| `figures/risk_es_multiplier.pdf` | `output/latest/figures/risk_es_multiplier.pdf` | dégradation de la queue |
| `figures/importance_sampling_convergence.pdf` | `output/latest/figures/importance_sampling_convergence.pdf` | convergence MC / IS |
| `figures/tail_risk_concentration.pdf` | `output/latest/figures/tail_risk_concentration.pdf` | concentration des scénarios extrêmes |
| `figures/tail_risk_four_experiments.pdf` | `output/latest/figures/tail_risk_four_experiments.pdf` | expériences de contrôle ES |

### Annexes — recommandés

Tous proviennent de
`output/hyperparameters/runs/2026-10-15_225308_report/figures/` :

- `alpha_grid.pdf` ;
- `elastic_net_rho_grid.pdf` ;
- `regularization_filter_map.pdf` ;
- `l0_initialization_audit.pdf` ;
- `importance_sampling_grid.pdf` ;
- `importance_policy_precision_calls_puts.pdf` ;
- `importance_policy_precision_full.pdf`.

### Visuels à créer après le prochain run

- `unified_benchmark_comparison.pdf` ;
- `residual_loss_distribution.pdf` ;
- `tail_regime_decomposition.pdf` ;
- `selected_weights_calls_puts.pdf` ;
- `selected_weights_full.pdf` ;
- `regularization_accuracy_sparsity.pdf`.

Ces six nouveaux visuels sont plus utiles pour la version finale que des
graphiques supplémentaires de recherche d'alpha.

## 5. Remplacements numériques avant soumission

Rechercher dans le `.tex` les expressions suivantes après le run REPORT :

- `100.538`, `0.149`, `100.245`, `100.830` pour le pricing ;
- `7.940` et `4.488` pour le benchmark brut ;
- les valeurs du tableau « Residual risk » ;
- les estimations MC / IS 8.175, 9.927, 7.958 et 9.046 ;
- les résultats de l'expérience 2 × 2 de contrôle ES ;
- les nombres d'options des profils compromis ;
- les identifiants des runs dans l'annexe de reproductibilité.

Le plus sûr sera de générer ces tableaux directement à partir du dernier export
plutôt que de modifier les valeurs à la main.
