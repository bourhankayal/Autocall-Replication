# Carnet de mise à jour finale du rapport

Ce fichier recense les éléments qui devront être régénérés après les dernières
modifications méthodologiques. Il distingue le contrôle rapide en mode FAST des
résultats définitifs issus des deux exécutions REPORT.

## Règle générale

- Une exécution FAST vérifie la logique, les colonnes exportées, les tableaux et
  les figures. Ses nombres ne remplacent pas les résultats définitifs du rapport.
- L'exécution REPORT du notebook Hyperparameters doit être achevée et promue avant
  l'exécution REPORT du notebook principal.
- Après les deux exécutions REPORT, tous les tableaux numériques et toutes les
  figures des versions française et anglaise doivent provenir des exports promus.
- Le test final reste fermé jusqu'au gel de la méthode.

## Refonte des métriques du 15 novembre 2026

Le noyau commun de comparaison retient désormais six mesures :

1. erreur moyenne signée
2. MAE
3. RMSE
4. fréquence des pertes positives, appelée taux de sous-réplication pour un résidu
5. Expected Shortfall à 97,5 %
6. perte maximale observée

La VaR n'est plus présentée comme un résultat autonome. L'ES reste calculée avec
un traitement exact de la masse de probabilité située à la frontière de la queue.

## À vérifier lors du prochain FAST du notebook principal

- Présence des six mesures dans `delta_benchmark_summary.csv`.
- Présence des six mesures dans `unified_benchmark_table.csv` et sa vue `report_`.
- Présence de l'erreur moyenne, de la MAE, du taux de sous-réplication et de la
  perte maximale dans `report_profile_outcomes.csv`.
- Cohérence des signes : une perte positive doit toujours correspondre à un
  déficit de couverture.
- Cohérence des unités : montants en points ou pourcentage du nominal, fréquence
  comprise entre 0 et 1 dans les CSV et affichée en pourcentage dans le rapport.
- Vérification que les références statiques, conditionnelles, delta et le passif
  centré utilisent le même calcul statistique lorsqu'un vecteur de pertes commun
  est disponible.
- Vérification visuelle des tableaux larges et absence de débordement dans les PDF.
- Vérification de chaque figure modifiée selon `docs/FIGURE_REPRODUCIBILITY.md` :
  le FAST doit reproduire le visuel validé sans script correctif manuel.

## À actualiser après les deux exécutions REPORT finales

### Compléments métriques du 16 novembre 2026

- Les rapports FR et EN présentent les 15 lignes actuellement exportées dans la
  comparaison globale, avec les six métriques, des arrondis recalculés depuis les
  CSV et un commentaire distinguant les objectifs A et B.
- Le prochain FAST principal doit ajouter toutes les pénalisations disponibles
  des paniers statiques et conditionnels A à la comparaison sur les trajectoires
  communes aux deltas. Une méthode absente/non convergée ne doit pas être inventée.
- Les exports statiques et conditionnels A incluent désormais les six métriques
  du résidu total par trajectoire, distinctes des erreurs de paiement aplaties.
- La comparaison A/B exporte les six métriques terminales et par date. Son ES
  est désormais calculée avec `tail_risk_metrics`, y compris la masse fractionnée
  au seuil de VaR, au lieu d'une moyenne de toutes les observations >= au seuil.
- L'expérience de queue 2 x 2 exporte et affiche aussi l'erreur moyenne, la MAE,
  la fréquence de sous-réplication et la perte maximale sur son évaluation commune.
- Les nouveaux chiffres ne sont pas disponibles avant cette exécution : ne pas
  présenter les anciens CSV comme issus du nouveau calcul ni remplir les cases
  manquantes par des estimations.
- Budgets actuels : risque principal 2 500 trajectoires, comparaison commune avec
  delta 1 250, diagnostic A/B 625. Chaque comparaison est appariée en interne,
  mais leurs niveaux ne doivent pas être mélangés. Aligner les budgets ou garder
  cette distinction lors de la synthèse finale.
- Aucun changement dans les sections figées avant 4.3 pour ces compléments.
- L'utilisateur exécute les notebooks ; aucune exécution FAST/REPORT lancée ici.

- Tableau principal du risque résiduel.
- Tableau des diagnostics secondaires : erreur moyenne, MAE et taux de
  sous-réplication.
- Tableau global des références avec les six mesures.
- Chiffres cités dans l'abstract, le résumé détaillé, les résultats et la conclusion.
- Figures de comparaison RMSE/ES et toute figure dépendant des profils retenus.
- Figures bilingues exportées dans `overleaf/figures/fr` et `overleaf/figures/en`.
- Contrôle qu'aucune figure REPORT ne rétablit une ancienne mise en page remplacée
  pendant la relecture.
- Manifestes, nombres de trajectoires, graines, intervalles d'incertitude et date
  de l'exécution finale.
- Compilation des deux rapports Overleaf après remplacement des exports.

## Contrôle éditorial final

- Présenter RMSE et ES à 97,5 % comme métriques principales.
- Présenter erreur moyenne, MAE, fréquence de sous-réplication et perte maximale
  comme diagnostics secondaires.
- Ne jamais classer deux méthodes comme économiquement équivalentes lorsque le
  capital initial, l'objet de risque ou les coûts ne sont pas alignés.
- Pour le passif centré, employer « fréquence des pertes positives » plutôt que
  « taux de sous-réplication ».

## Synchronisation Overleaf vérifiée le 15 novembre 2026

- Sources française et anglaise transférées dans le projet existant.
- Les 18 PDF de `overleaf/figures/fr` et les 18 PDF de `overleaf/figures/en` ont été remplacés sur Overleaf.
- Les deux compilations finales indiquent 0 erreur, 0 avertissement et 0 autre message de mise en page.
- PDF français : 48 pages ; PDF anglais : 46 pages. Copies téléchargées et conservées dans `overleaf/rapport_autocall_v1_fr.pdf` et `overleaf/rapport_autocall_v1_en.pdf`.
- Contrôles du contenu extrait : prix 100,538 / 100.538, 2 500 trajectoires, 10 recalibrations, convergence Full--L0 compromis 6/10, absence de l'ancien prix 100,423 et absence de figures de remplacement manquantes.
- Vérification visuelle : figures 1 et 2 et tableau de risque actualisés ; débordements des en-têtes du tableau de risque et des identifiants d'exécution corrigés après 4.3.
- Le français a été rétabli comme document principal sur Overleaf.
- Point restant pour les REPORT finaux : aligner la sélection de politiques entre les deux notebooks. Le dernier diagnostic d'hyperparamètres FAST n'a pas été promu dans le notebook principal ; ses résultats de risque restent ceux des politiques promues en octobre. Cette distinction est explicitée dans les rapports.
- En 5.3, actualiser ensemble les hyperparamètres retenus, la RMSE de validation, les tailles des paniers et les résultats d'évaluation liés. Le texte de présentation omet la date de la sélection. Réviser aussi le renvoi au diagnostic distinct de novembre si les nouveaux exports sont alignés.
- Version finale : remplacer tous les chiffres et figures par les exports actualisés des deux REPORT, en alignant la sélection promue et l'évaluation. Les références à octobre et novembre ont été retirées de 5.3. Préserver la frontière de relecture avant 5 et présenter les remplacements nécessaires à ces endroits pour accord.
