# Résultats du projet

Ce dossier sépare trois usages :

- `pdf/` : documents PDF sélectionnés et mis à jour manuellement ;
- `runs/<date>_<heure>_<mode>/` : historique immuable des exports complets du
  notebook, nommé avec l'heure de démarrage de l'exécution ;
- `latest/` : copie du dernier export complet, remplacée à chaque nouvelle sauvegarde.
- `hyperparameters/runs/<date>_<heure>_<mode>/` : recherches d'hyperparamètres
  complètes et immuables ;
- `hyperparameters/latest/` : copie pratique de la dernière recherche, qui
  n'est jamais chargée automatiquement par le notebook principal.

Chaque exécution exportée contient :

- `configuration.json` : produit, marché, mode, tailles d'échantillon et seeds ;
- `manifest.json` : inventaire des fichiers et environnement logiciel ;
- `tables/` : résultats numériques au format CSV. Chaque tableau complet
  possède une vue de synthèse `report_<nom>.csv` avec les colonnes essentielles,
  des intitulés lisibles et, pour les grands audits, une agrégation explicite ;
  le CSV sans préfixe reste l'audit intégral ;
- `figures/` : graphiques principaux en PDF vectoriel et PNG.

L'export est déclenché par la dernière cellule du notebook
`notebooks/autocall_research.ipynb`. Une exécution interrompue avant cette cellule
ne crée pas de résultat partiel et ne remplace pas `latest/`.

Le manifeste distingue `started_at`, capturé dans la première cellule de code,
et `exported_at`, enregistré lorsque la dernière cellule termine la sauvegarde.

Une recherche d'hyperparamètres contient en plus les grilles complètes, les
résultats multi-graines, les audits L0, les frontières lambda ES et budget ES,
les candidats d'importance sampling et les figures correspondantes. La cellule
finale de `notebooks/hyperparameter_research.ipynb` peut promouvoir volontairement
une recherche vers `config/selected_hyperparameters_fast.json` et
`config/selected_policy_results_fast.pkl`, ou vers les deux fichiers équivalents
suffixés `_report`. Le notebook principal exige le mode correspondant. Les
cartes de filtres et les alphas de chaque benchmark sont conservés avec les
autres résultats. Aucun ancien dossier daté n'est supprimé.
