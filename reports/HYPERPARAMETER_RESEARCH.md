# Étude externe des hyperparamètres de réplication

## Résumé rapide

**Contexte** — Recherche externe des paramètres des politiques conditionnelles Calls + Puts et Full.

**Problème** — Séparer leur sélection de l'évaluation du notebook principal et préserver le test final.

**Méthode** — Grilles de calibration, validation indépendante et audit multi-graines ; 30 recalibrations dans le REPORT promu.

**Modifications** — Sélections et visuels exportés dans un run daté, puis importés sans recalibration par le notebook principal.

**Résultats** — Le REPORT du 15 octobre 2026 est promu ; les extensions de grille ultérieures ne sont pas encore réévaluées.

## État actuel — REPORT du 15 octobre 2026

Le run `output/hyperparameters/runs/2026-10-15_225308_report` est terminé et sa
sélection a été promue pour le notebook principal. Il demeure **figé** : sa grille
ES s'arrêtait à un alpha relatif de `0.001`, et la recherche Elastic Net à
`rho=0.90`. La grille du code descend désormais à `0.0001` puis `0.00001` pour
l'alpha ES et utilise quinze ratios Elastic Net : les points anciens, un pas
de `0.025` entre `rho=0.75` et `0.975`, puis `0.99`. L1 pur reste une norme séparée.
Ces extensions ne recalculent pas ni ne changent la sélection déjà promue. Sur le
REPORT conservé, six des huit compromis « RMSE sous budget ES » atteignaient
l'ancienne borne minimale. Leur statut d'optimum intérieur reste donc ouvert.

Ce notebook vise la **sélection documentée des hyperparamètres**, pas un verdict
global sur la meilleure réplication ni une couverture immédiatement négociable.
Les compromis ES pénalisé à 158 et 248 options sont gardés comme résultats
mathématiques, sans recommandation pratique. Un ES signé négatif est cohérent
avec la convention « flux dû moins flux répliqué » : il peut signaler une
surcouverture, mais ne tient pas lieu de profit après coûts. Coûts, liquidité et
financement limitent l'interprétation économique ; le cadre garde un intérêt
pour étudier la réplication pure d'un produit complexe. Son adaptation à un
autre produit exige de redéfinir les flux, les scénarios et les instruments.

Les constats FAST datés ci-dessous décrivent des étapes historiques et ne
remplacent pas le REPORT actuel.

## Synthèse méthodologique détaillée

**Contexte** — Le projet compare des politiques de réplication conditionnelle d'un autocall sur un sous-jacent, avec les familles Calls + Puts et Full (incluant des binaires).

**Problème** — Choisir des paramètres dans le notebook principal brouillait la frontière entre calibration, validation et évaluation. Les valeurs d'alpha, du ratio Elastic Net, du contrôle ES et du mélange d'importance sampling doivent pouvoir être examinées ensemble et reproduites.

**Méthode** — Un notebook dédié explore des grilles explicites sur la calibration, classe les candidats avec une validation indépendante et filtre leur stabilité sur dix graines. Un audit distinct des profils finaux utilise dix recalibrations en FAST et trente en REPORT ; le pilote IS compare trois graines en FAST et trente en REPORT. Le test final reste réservé.

**Modifications** — Les grilles, graphiques, audits et sélections sont exportés dans un dossier horodaté. Seuls les alphas des benchmarks de cashflows statiques et conditionnels sont désormais sélectionnés ici en section 1.1. Les recherches de surface de prix, de payoff moyen et de Pathwise payoff non conditionnel sont isolées dans `notebooks/exploratory_benchmarks.ipynb`. Le notebook principal charge dès le début une recherche explicitement promue dans son mode et vérifie la compatibilité du contrat et du modèle. Une carte des filtres compte les solutions restantes et éliminées à chaque étape.

**Résultats** — Le REPORT du 15 octobre 2026 est complet et promu. Il est la référence actuelle pour les hyperparamètres du notebook principal ; le test final reste réservé. Ses choix ont été faits sur la grille alors en vigueur, qui s'arrêtait à `0.001` pour l'alpha relatif des expériences ES. La nouvelle borne `0.00001` ne sera évaluée que lors d'un prochain run. Les résultats FAST détaillés plus bas sont des archives méthodologiques, non les conclusions courantes.

### Présentation et sélection Elastic Net — vérifiées dans le FAST du 14 octobre 2026

Les trois profils de la méthode B sont maintenant choisis sur la grille admissible complète $(\rho,\alpha)$ de chaque famille. **Performance**, **compromis** et **parcimonie** peuvent donc retenir des ratios $\rho$ distincts. La carte de chaleur indique ces trois couples par les lettres P, C et S ; le tableau court affiche leurs métriques, tandis que toutes les solutions et leurs poids demeurent dans les tableaux et objets exportés. La stabilité recalibre chaque profil avec son propre ratio et son propre alpha relatif. Le ratio du profil compromis sert séparément de référence aux expériences de contrôle ES qui demandent encore un seul ratio scalaire ; il ne remplace pas celui des autres profils.

### Contrôle ES étendu aux quatre normes — protocole du REPORT promu

La section 5 du notebook Hyperparameters recherche les grilles $\lambda_{ES}$ et budget ES pour **L0, L1, L2 et Elastic Net**, séparément dans les deux familles. Elastic Net teste tous les couples $(\rho,\alpha)$, avec une référence alpha propre à chaque $\rho$ ; L1 et L2 ont chacun leur échelle. Les plafonds ES sont **5 %, 10 % et 15 % du nominal**, communs aux deux familles et aux quatre normes. Pour chaque plafond, le profil retenu minimise la RMSE de validation parmi les candidats faisables en calibration et sous ce plafond en validation ; le budget qui a servi à optimiser ses poids reste indiqué séparément. Le REPORT promu applique cette règle sur l'ancienne borne d'alpha `0.001`.

L0 n'est pas résolu globalement sous objectif ES : on réoptimise les poids uniquement sur les supports convergés issus de la recherche L0 antérieure, puis on choisit entre ces supports sur la calibration. La comparaison est donc **heuristique** et n'atteste pas un optimum global. Le notebook principal garde pour l'instant son expérience MC/IS détaillée sur Elastic Net uniquement. Il doit appliquer le **budget ES absolu** sélectionné, et non recalculer un ratio contre une nouvelle politique de référence.

### Importance sampling robuste entre normes — protocole du REPORT promu

La section 6 utilise **tous les profils ES admissibles de la section 5**, avec leurs poids figés. Pour chaque famille, graine et mélange IS, les mêmes trajectoires sont évaluées sous chaque portefeuille L0/L1/L2/Elastic Net effectivement retenu. Un pilote MC standard fournit l'écart-type de référence de l'ES par portefeuille et participe au choix. Parmi les mélanges respectant une ESS globale d'au moins 20 %, la recommandation minimise le **pire ratio d'écarts-types IS/MC** sur ces portefeuilles ; l'ESS de queue départage les égalités. Elle ne recherche jamais une faible valeur d'ES. Dans le dernier FAST, calculé avec l'ancienne grille de budgets, le MC standard restait préférable dans les deux familles ; cette conclusion pilote devra être revérifiée sur les nouveaux profils. Les tableaux exportent la synthèse par mélange, le détail par portefeuille et chaque répétition.

Les deux notebooks présentent des vues courtes pour les résultats principaux. À chaque exécution complète, les tableaux d'audit sont conservés et accompagnés de fichiers `report_*.csv` exploitables dans le rapport. Le réglage `SHOW_TECHNICAL_DETAILS = True` permet de réafficher les tableaux complets. Tous les exports existants, y compris celui du 14 octobre 2026, précèdent la nouvelle grille de plafonds 5/10/15 : ils ne doivent pas être présentés comme ses résultats.

### Mise à jour méthodologique du 12 octobre 2026 — intégrée dans le FAST du 14 octobre

- En section 1.1, la méthode A conditionnelle par échéance et le contrôle Static cashflows recherchent désormais **ensemble** l'alpha et le ratio $\rho$ d'Elastic Net. Pour chacun des ratios de la grille, tous les alphas sont évalués sur les mêmes trajectoires de validation ; le couple admissible de plus faible RMSE est retenu. L0, L1 et L2 gardent chacun leur recherche d'alpha.
- Dans la méthode B, la grille jointe Elastic Net $(\rho,\alpha)$ est exécutée **avant** la comparaison L0/L1/L2/Elastic Net. La règle initiale d'un ratio unique par famille décrite ici est remplacée par la sélection des trois couples propres aux profils ci-dessus. Les objectifs A (paiements par échéance) et B (payoff total actualisé par trajectoire) demeurent distincts : leurs alphas et ratios ne sont pas interchangeables.
- Le notebook principal importe également le ratio Elastic Net retenu pour ses deux benchmarks temporels. Le passage FAST du 14 octobre applique cette règle ; sa sélection n'est toutefois pas promue automatiquement. Examiner l'export, puis promouvoir explicitement un run compatible avant de lancer le notebook principal dans le même mode.
- Présentation des grilles temporelles : les deux graphiques généraux (Static, puis Conditional) précèdent les deux graphiques Elastic Net seuls. Le comparatif L0/L1/L2 n'affiche qu'Elastic Net au ratio $\rho$ retenu ; les graphiques dédiés montrent toutes les courbes $(\rho,\alpha)$. Pour chaque benchmark et famille, ce couple est celui de plus faible RMSE de validation parmi les solutions convergées avec au moins deux options actives ; les égalités sont départagées par le nombre d'options, puis l'alpha, puis le ratio. Un tableau affiche explicitement les quatre couples retenus. Les exports conservent l'intégralité des candidats, sans perte de données. Cette règle ne tient pas encore compte de l'ES, des coûts ou de la stabilité multi-graines.
- La méthode B est regroupée en section 2 : une première cellule définit les réglages communs, puis la cellule suivante lance réellement la recherche jointe Elastic Net. Sa comparaison avec L0/L1/L2 est en section 2.1. Les sections suivantes sont renumérotées sans changement des calculs.
- La grille jointe Elastic Net de la méthode B est affichée en quatre cartes de chaleur : Calls + Puts puis Full en lignes, RMSE de validation puis nombre d'options actives en colonnes. Le ratio $\rho$ est horizontal, l'alpha relatif vertical, et une même mesure conserve la même échelle de couleur entre familles. Une cellule grise signale une absence de convergence ou de mesure ; les marqueurs de trois profils décrits ci-dessus remplacent l'ancien contour unique. La cellule de visualisation est séparée du calcul coûteux et peut être relancée seule. Le tableau complet des couples reste exporté.

### Passage FAST historique : `output/hyperparameters/runs/2026-10-09_152048_fast`

Ce passage et celui du 10 octobre 2026 (`2026-10-10_112750_fast`) précèdent la réorganisation des notebooks. Leurs cinq recherches préliminaires et leurs figures restent consultables dans les exports datés, mais les prochains passages Hyperparameters n'en exécuteront plus que deux : cashflows statiques et cashflows conditionnels. La recherche Pathwise payoff L2 vit dans le notebook exploratoire. La réorganisation ne constitue pas une nouvelle validation numérique.

- Export complet et conservé : 30 fichiers de figures PDF/PNG, tableaux CSV, configuration et manifeste. Aucun ancien run n'a été supprimé.
- 24 des 26 combinaisons exploratoires benchmark/famille/pénalité possèdent un alpha convergé et au moins deux options actives. Les deux absences sont L0 sur la surface de prix, pour Calls + Puts et Full ; elles sont inscrites dans `exploratory_alpha_missing.csv`, pas remplacées par un alpha arbitraire.
- La carte de régularisation recense, pour chaque famille et pénalité, les effectifs de la grille initiale jusqu'aux profils stables.
- Budget ES Calls + Puts : 33 calculées → 33 convergées → 33 faisables en calibration → **0** dans le budget en validation. Budget ES Full : 33 → 33 → 33 → 27 → 5 non dominées → 3 politiques distinctes retenues.
- La promotion FAST est volontairement refusée tant que Calls + Puts n'a pas de profil de budget validé. Le notebook principal échoue donc clairement au chargement plutôt que d'utiliser les anciens résultats ou une politique non admissible.
- Cette absence peut provenir d'un surajustement de l'échantillon FAST (180 trajectoires de calibration pour cette grille), d'une variabilité de queue importante, ou d'une fragilité des poids sélectionnés. Elle ne permet pas, à elle seule, de trancher. Le mode REPORT et un audit ciblé de convergence/généralisation sont nécessaires.

L'ancien passage FAST corrigé est conservé dans `output/hyperparameters/runs/2026-10-09_103637_fast`. Il a produit les sept figures alors prévues. L'exécution antérieure `2026-10-09_101133_fast` reste archivée. Aucune de ces recherches n'a été promue vers le notebook principal.

### Constats du passage FAST historique du 9 octobre (non actualisés)

- Le ratio L1 d'Elastic Net retenu par la règle provisoire de validation est $\rho=0{,}1$ dans les deux familles. La grille complète des cinq ratios reste disponible.
- La correction du déclenchement du multistart fait apparaître des candidats L0/Full sur la grille, mais aucun de ses trois profils ne passe le filtre de stabilité multi-graines. L0/Full n'est donc pas une politique retenue. Pour Calls + Puts, les trois étiquettes de profil L0 désignent le même candidat, qui passe ce filtre.
- L'audit antérieur avait révélé que deux initialisations L0 non convergées mais identiques ne déclenchaient pas le multistart. Ce cas déclenche désormais les essais supplémentaires ; l'exécution corrigée ci-dessus intègre ce changement.
- Calls + Puts/L1 ne passe pas le filtre multi-graines pour ses profils ; les candidats sont conservés dans les tableaux d'audit.
- Les trois profils de budget ES se confondent dans cet ancien passage : ratio 75 % pour Calls + Puts, 90 % pour Full. Surtout, le budget Calls + Puts de 75 % dépasse l'ES observé en validation et **n'est plus admissible** selon la règle actuelle. Le chiffre ancien n'est donc pas une recommandation utilisable. Les nouvelles grilles élargies et la validation stricte doivent être recalculées.
- Parmi les quatre mélanges d'importance sampling, le candidat $(0,-1,-2)$ est retenu dans les deux familles par la dispersion inter-graines de l'ES, avec un ratio ESS minimal d'environ 0,76. Ce choix concerne la précision de mesure, pas la qualité de couverture.

## Périmètre des grilles

| Objet | Recherche | Lecture proposée |
|---|---|---|
| Régularisation | Alpha propre à L0, L1, L2 et Elastic Net | Erreur de validation et nombre d'options actives |
| Contrôle pathwise et benchmarks temporels | Alpha distinct par objectif, famille et pénalité | RMSE de validation ; les recherches prix/payoff moyen sont séparées du parcours final |
| Elastic Net | Grille jointe de ratio L1 et d'alpha | Compromis entre précision et parcimonie |
| L0 | Chemin alpha, warm start, cold start et multistart | Sensibilité à l'initialisation et changement de support |
| Stabilité | Dix graines de recalibration | Distribution des performances et robustesse du support |
| Contrôle ES pénalisé | Grille d'alpha et de $\lambda_{ES}$ pour L0/L1/L2/Elastic Net ; tous les $\rho$ d'Elastic Net | Frontière RMSE contre ES de validation ; L0 est heuristique |
| Contrôle ES contraint | Même périmètre, plafonds absolus de 5 %, 10 % et 15 % du nominal, communs aux deux familles | Faisabilité sous le budget d'optimisation en calibration ; ES observé sous le plafond commun en validation ; les deux budgets restent distincts |
| Importance sampling | Quatre mélanges et un pilote MC, répétés sur plusieurs graines et tous les profils ES admissibles | Pire ratio de dispersion IS/MC entre politiques, sous seuil ESS |

Pour l'ES pénalisé, les profils priorité RMSE, compromis et priorité ES sont choisis sur la frontière non dominée observée en validation. Pour l'ES **contraint**, ces noms désignent désormais les plafonds respectifs souple (15 %), intermédiaire (10 %) et strict (5 %). Une solution optimisée sous un budget plus strict peut être retenue sous un plafond plus souple si son ES validé le respecte ; le budget de départ et le plafond de décision sont tous deux exportés. Une absence de candidat sous un plafond est affichée explicitement. Plusieurs profils peuvent désigner les mêmes poids ; le rapport ne doit pas inventer trois paniers distincts.

## Règles de séparation des données

1. Les poids financiers et les paramètres de méthode sont choisis avec les blocs calibration et validation.
2. Les mélanges d'importance sampling sont comparés sur un pilote multi-graines et sur tous les portefeuilles ES retenus. Le critère est le pire rapport des dispersions IS/MC entre politiques, sous contrainte de qualité des poids ; on ne retient pas le mélange donnant l'ES le plus faible.
3. La recherche sauvegarde chaque exécution dans `output/hyperparameters/runs/<horodatage>` et une copie pratique dans `output/hyperparameters/latest`.
4. La promotion vers `config/selected_hyperparameters_fast.json` ou `config/selected_hyperparameters_report.json`, et le fichier de politiques portant le même suffixe, est explicite. Le notebook principal charge uniquement le mode correspondant dès la cellule du contrat. Une promotion est refusée si le profil Elastic Net intermédiaire est absent, non faisable en calibration ou dépasse le **plafond commun de 10 %** en validation. Les quatre expériences de risque de queue reprennent ensuite son alpha, son ratio Elastic Net et **son budget d'optimisation** pour réajuster les poids ; l'ES obtenu est comparé séparément au plafond commun de 10 %. La méthode d'échantillonnage sélectionnée peut être le MC standard. Les profils des autres normes sont exportés pour l'analyse comparative, sans modifier encore ces expériences 2×2.
5. FAST et REPORT testent **exactement les mêmes valeurs de grille**. Ils diffèrent par les volumes de simulation et de répétition ; leurs choix statistiques peuvent donc diverger. Les alphas préliminaires ne sont pas transférés arbitrairement depuis l'objectif conditionnel final. Le notebook principal utilise une autre graine pour recalculer ces benchmarks, sans prétendre que le découpage temporel inchangé constitue un test structurel totalement indépendant.
6. Les résultats FAST servent à vérifier le pipeline. Une interprétation quantitative finale demande une campagne REPORT et le test final réservé.

## Comment lire les graphiques

Dans le parcours actuel, deux graphiques généraux et deux graphiques Elastic Net dédiés montrent le choix d'alpha des benchmarks de cashflows statiques et conditionnels. Les exports antérieurs incluaient encore la surface de prix, le payoff moyen et le contrôle Pathwise payoff. La carte de filtrage indique, pour chaque famille et pénalité, le nombre de solutions **restantes** après convergence, taille minimale, robustesse numérique, dominance, performance, doublons et sélection des profils. Les boxplots multi-graines affichent la dispersion des recalibrations. Les frontières de risque de queue comparent RMSE et ES sur la validation ; une amélioration de l'un peut dégrader l'autre. Le graphique de budgets ES montre combien de solutions respectent finalement leur budget en validation. Le graphique d'échantillonnage compare la précision de l'estimation et l'ESS, sans représenter un gain de couverture.

## Limites à contrôler avant conclusion

- L0 est non convexe : la convergence numérique ne garantit pas l'optimum global. L'audit d'initialisation et la variation du support doivent être consultés.
- La pénalité $L^{1/2}$ reste dans les benchmarks exploratoires antérieurs ; le moteur conditionnel pathwise de cette étude accepte L0, L1, L2 et Elastic Net. Elle n'est donc pas incluse artificiellement dans une grille qu'il ne sait pas encore résoudre.
- Un budget d'optimisation ES respecté en calibration peut ne plus l'être en validation. Ce dépassement est conservé dans l'audit ; la sélection juge séparément l'ES validé face au plafond commun du profil. Ce contrôle empirique n'est pas une garantie du risque futur.
- Le choix d'un mélange d'importance sampling sur quelques graines reste sensible au bruit ; REPORT augmente le nombre de trajectoires et de graines.
- Les coûts d'exécution et la liquidité des binaires restent des hypothèses à approfondir avant une décision de desk.
- La couverture dynamique du résidu ne fait pas encore partie des résultats de risque terminal.
