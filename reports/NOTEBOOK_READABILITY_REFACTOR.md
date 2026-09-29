# Réorganisation du notebook principal

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Le notebook principal était devenu difficile à suivre et à réexécuter. |
| **Problème** | Séparer narration, calculs principaux et diagnostics techniques. |
| **Méthode** | Sections numérotées, modes fast/report et sorties décisionnelles. |
| **Modifications** | Réorganisation des cellules, sécurisation des variables et nouveaux graphiques. |
| **Résultats** | Le parcours principal suit désormais la progression de l’étude. |


## Objectif

Rendre `notebooks/autocall_research.ipynb` lisible comme une étude financière, sans modifier les algorithmes du package. Le notebook doit expliquer la question posée, lancer le calcul correspondant et afficher une sortie directement interprétable.

## Périmètre validé

- ajout des modes d’exécution `fast` et `report` ;
- conservation des familles `calls_puts` et `full` dans les benchmarks principaux ;
- conservation de la recherche d’alpha pathwise sur la famille `full` ;
- présentation synthétique de la stabilité, du risque et des coûts ;
- maintien des tableaux techniques derrière `SHOW_TECHNICAL_DETAILS` ;
- séparation des variables contractuelles et des variables de marché ;
- aucune modification de l’API publique ni des algorithmes financiers.

## Nouvelle narration

0. mode d’exécution et préparation ;
1. contrat cible et hypothèses ;
2. validation du pricing Monte-Carlo ;
3. benchmarks de réplication statique ;
4. recherche d’alpha et sélection des profils ;
5. stabilité ;
6. risque terminal statique ;
7. coûts de transaction et données de marché ;
8. synthèse décisionnelle.

Chaque calcul important est précédé d’une cellule Markdown précisant son objectif, sa méthode et la lecture de sa sortie.

## Modes d’exécution

Le mode `fast` réduit surtout les calculs les plus longs. Il sert au développement et au contrôle de cohérence. Le mode `report` porte notamment l’échantillon indépendant de risque à 20 000 trajectoires et doit être utilisé pour les chiffres cités dans un rapport.

Le choix du mode ne modifie ni le contrat, ni la famille d’instruments, ni la pénalité. Il modifie uniquement les tailles numériques centralisées dans `EXECUTION_CONFIGS`.

## Lisibilité des sorties

Par défaut, le notebook affiche :

- les hypothèses contractuelles ;
- les principales métriques des benchmarks ;
- les profils sélectionnés ;
- le résumé de stabilité ;
- la réduction du risque ;
- le coût estimé et le filtre économique ;
- la table décisionnelle finale.

Les poids complets, résultats par graine, détails instrument par instrument et surfaces multiples restent accessibles avec `SHOW_TECHNICAL_DETAILS = True`.

## Visualisations décisionnelles

Quatre figures restent visibles dans le parcours principal :

- une heatmap de la surface date–spot avec la barrière et le seuil de rappel ;
- une comparaison `calls_puts` / `full` sur la RMSE et le nombre d'options actives ;
- les profils performance, compromis et parcimonie superposés aux chemins d'alpha ;
- une comparaison du risque brut et de l'exposition résiduelle de réplication avec RMSE et Expected Shortfall 97,5 %.

Ces figures complètent les tableaux chiffrés sans remplacer les données d'audit. Elles ont été testées avec des profils absents ou partiels afin de ne pas supposer que chaque pénalité fournit toujours trois candidats.

## Sécurisation de l’état Jupyter

L’exploration yfinance utilise maintenant des variables préfixées par `market_`. Elle ne réaffecte plus les variables centrales `prod`, `valuation_date`, `maturity_date` ou `spot0`. Cela supprime une dépendance dangereuse à l’ordre d’exécution des cellules.

## Limites de cette étape

Cette réorganisation ne crée pas encore de cache persistant et ne déplace pas les diagnostics dans des notebooks techniques séparés. Ces travaux appartiennent aux étapes suivantes et nécessiteront une validation distincte.
