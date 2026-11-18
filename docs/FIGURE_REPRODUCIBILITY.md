# Reproductibilité des figures du rapport

## Règle permanente

Une amélioration visuelle n'est considérée comme terminée que si elle est intégrée à la
source qui produit la figure lors d'une nouvelle exécution FAST ou REPORT. Remplacer
uniquement un PDF dans Overleaf ne suffit pas.

Pour chaque figure modifiée, vérifier systématiquement :

1. son utilité réelle et le message qu'elle démontre
2. la lisibilité des axes, légendes, unités et catégories
3. l'absence de titres, répétitions ou mentions évidentes inutiles
4. sa cohérence avec les données et le texte du rapport
5. sa place dans le corps ou en annexe
6. la présence de quelques phrases qui l'utilisent réellement dans le rapport
7. l'intégration de la correction dans le notebook ou la fonction appelée par celui-ci
8. l'export cohérent en français et en anglais
9. la vérification sur un run FAST avant le REPORT final

## Corrections déjà rendues reproductibles

| Figure | Source canonique | Correction conservée lors d'un nouveau run |
|---|---|---|
| Stabilité multi-graines | `plot_seed_robustness` | suppression de « 30/30 convergés » sur chaque ligne, légende rapprochée, explication des boîtes et moustaches |
| Tableau de bord de décision | notebook hyperparamètres et son générateur | une seule vue RMSE / nombre total d'options, sans panneaux secondaires qui déforment l'échelle |
| Frontières de queue | `plot_tail_frontiers` et `plot_alpha_tail_frontier` | axes allégés, sans répétition « plus bas = mieux » |
| Comparaison des objectifs A/B | notebook principal | barres séparées pour RMSE des paiements et RMSE du total, au lieu de deux points reliés |
| Erreurs par date de paiement | notebook principal | objectifs A et B séparés en lignes pour éviter qu'une série écrase les autres |
| Contrôle RMSE / ES en montants | notebook principal | points résiduels et référence brute, sans répétition de la même barre ni libellés illisibles |

Les scripts de traduction ou de régénération à partir des CSV restent des outils d'export.
Ils ne doivent pas contenir une version visuelle différente de celle produite par les
notebooks et leurs fonctions canoniques.
