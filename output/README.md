# Résultats du projet

Ce dossier sépare trois usages :

- `pdf/` : documents PDF sélectionnés et mis à jour manuellement ;
- `runs/<date>_<mode>/` : historique immuable des exports complets du notebook ;
- `latest/` : copie du dernier export complet, remplacée à chaque nouvelle sauvegarde.

Chaque exécution exportée contient :

- `configuration.json` : produit, marché, mode, tailles d'échantillon et seeds ;
- `manifest.json` : inventaire des fichiers et environnement logiciel ;
- `tables/` : résultats numériques au format CSV ;
- `figures/` : graphiques principaux en PDF vectoriel et PNG.

L'export est déclenché par la dernière cellule du notebook
`notebooks/autocall_research.ipynb`. Une exécution interrompue avant cette cellule
ne crée pas de résultat partiel et ne remplace pas `latest/`.
