# Journal de relecture finale

Ce fichier rassemble les remarques formulées pendant la lecture du rapport. Il servira de liste de contrôle pour la relecture finale. Il doit être complété au fil des commentaires, sans déclencher une réécriture générale pendant la lecture ligne par ligne.

## Règle de modification

- Le texte situé après le point de lecture actuel peut être corrigé normalement.
- Toute modification d'un passage déjà lu doit être proposée avant d'être appliquée, avec l'ancienne et la nouvelle formulation.
- Une correction explicitement demandée par Bourhan est autorisée au passage concerné et doit être reportée dans les versions française et anglaise lorsque les deux textes ont un équivalent.
- Éviter les refontes globales pendant la lecture. Privilégier des modifications courtes, localisées et vérifiables.

## Point de lecture actuel

Figure 2, dans la partie consacrée à la stabilité multi-graines.

Tout ce qui précède ce point est désormais figé. Aucune modification ne doit y être appliquée sans présenter au préalable l'ancienne formulation, la nouvelle formulation proposée et obtenir l'autorisation explicite de Bourhan.

## Principes éditoriaux à vérifier à la fin

### 1. Supprimer les phrases inutiles ou répétitives

- Retirer les explications déjà évidentes dans le contexte.
- Éviter de définir deux fois la même idée à quelques lignes d'intervalle.
- Vérifier chaque phrase de prudence : la conserver seulement si elle ajoute une limite précise.
- Réduire les transitions qui répètent la phrase précédente sans apporter d'information.

Exemples déjà corrigés :

- suppression de « La valeur 100,423 est la moyenne actualisée des flux de l'autocall, et non un paiement identique sur chaque trajectoire » ;
- suppression de « il ne constitue pas une couverture recommandée » après une phrase qui présentait déjà le résultat comme une mesure de capacité d'ajustement.

### 2. Présenter le travail au lieu de commenter le rapport

- Éviter les phrases qui évaluent la qualité, le sérieux ou le degré d'avancement du rapport.
- Décrire directement ce qui est fait, mesuré ou observé.
- Éviter les formulations qui donnent l'impression qu'un observateur extérieur juge le projet.

Exemple déjà corrigé :

- « La méthodologie est suffisamment développée pour soutenir un rapport de recherche rigoureux » a été remplacé par une description directe des composantes du projet.

### 3. Employer des tournures simples

- Préférer une phrase directe à une formulation abstraite ou excessivement académique.
- Éviter les groupes nominaux longs lorsqu'un verbe simple suffit.
- Ne pas utiliser de vocabulaire technique uniquement pour donner un ton académique.
- Expliquer les termes nécessaires au premier emploi, puis employer une terminologie stable.

### 4. Stabiliser la terminologie

- Conserver le terme anglais « importance sampling » dans la version française.
- Présenter clairement le filtrage de Pareto comme l'élimination des solutions dominées selon la RMSE de validation et le nombre d'options actives.
- Distinguer l'intervalle de confiance du prix à 95 % du niveau de 97,5 % utilisé pour l'Expected Shortfall.
- Employer « nœud » seulement après avoir précisé qu'il s'agit d'un état de décision à une échéance, et non simplement de l'échéance elle-même.

### 5. Rester précis sur les comparaisons de risque

- Expliquer que la RMSE du passif brut mesure la dispersion des flux autour de leur moyenne.
- Expliquer que la RMSE résiduelle mesure l'écart entre les flux de l'autocall et ceux de la réplication.
- Ne pas laisser entendre que RMSE et ES doivent être ordonnés : ils ne mesurent pas la même partie de la distribution.
- Lorsque Monte Carlo standard et importance sampling sont comparés, dire concrètement que leurs intervalles de confiance se recouvrent et que l'importance sampling génère davantage de scénarios défavorables avant repondération.

### 6. Éviter les références ou comparateurs insuffisamment développés

- Toute méthode citée comme benchmark doit être réellement expliquée, implémentée et comparée de manière cohérente.
- Toute trace de Kim--Lim et du benchmark structurel inspiré a été supprimée, car la méthode complète n'était pas implémentée.
- La couverture delta doit rester explicitée : construction de la surface de valeur conditionnelle, calcul du delta, compte de trésorerie autofinancé et fréquences de rééquilibrage.

### 7. Garder les versions française et anglaise alignées

- Reporter chaque modification de fond dans les deux langues.
- Ne pas traduire littéralement une tournure maladroite : conserver le même sens avec une phrase naturelle dans chaque langue.
- Vérifier en fin de lecture les tableaux, légendes, titres, résumés et annexes, pas seulement le corps du texte.

### 8. Procédure de relecture de chaque figure

Pour chaque figure, vérifier systématiquement :

- son utilité réelle dans la démonstration
- le résultat précis qu'elle permet d'établir
- la lisibilité des axes, des légendes et des unités
- sa cohérence avec le texte qui la précède et sa légende
- sa place dans le corps du rapport ou dans les annexes
- les éléments graphiques ou textuels à supprimer, rapprocher ou reformuler

La figure ne doit pas répéter tout le texte. Elle doit apporter une comparaison ou un diagnostic qu'un court paragraphe ou un tableau ne montrerait pas aussi clairement.

Toute figure conservée doit aussi être explicitement utilisée dans le corps du rapport :

- le texte doit renvoyer à la figure par son numéro
- au moins une phrase doit expliquer le résultat ou le diagnostic qu'il faut en retenir
- cette phrase doit interpréter la figure, et non simplement annoncer qu'elle existe
- si aucune conclusion utile ne peut être formulée à partir de la figure, celle-ci doit être déplacée en annexe ou supprimée

## Remarques à ajouter pendant la lecture

Ajouter chaque nouvelle remarque sous cette section avec :

- le passage concerné ;
- le problème identifié ;
- la décision prise ;
- le statut : à corriger, corrigé ou à revoir lors de la relecture finale.

### Figure 2 : stabilité multi-graines

- Utilité : comparer la dispersion de la RMSE de validation des profils sur 30 recalibrations indépendantes.
- Ce qu'elle démontre : la stabilité des performances moyennes et la présence de recalibrations atypiques. Elle ne mesure pas directement la stabilité du support des options.
- Défauts relevés : titre général redondant, répétition de « 30/30 convergés » sur chaque ligne et légende trop éloignée et trop petite.
- Décision : supprimer le titre général, alléger les étiquettes des lignes, indiquer une seule fois dans la légende sous la figure que toutes les recalibrations ont convergé, puis rapprocher et agrandir la légende graphique.
- Placement : conserver la figure dans le corps du rapport, après l'explication de la stabilité multi-graines.
- Statut : corrigé dans les figures et les versions française et anglaise locales.

### « Convention de débouclage en cas d'autocall anticipé »

- Passage concerné : résumé étendu, paragraphe sur les coûts de transaction.
- Problème identifié : « débouclage » est un terme de marché peu transparent pour un lecteur non spécialiste.
- Sens : préciser ce que deviennent les options dont l'échéance est postérieure au remboursement anticipé de l'autocall, notamment si elles sont revendues immédiatement, conservées ou remplacées, et à quels prix et coûts.
- Proposition : « une règle de liquidation des positions devenues inutiles après un remboursement anticipé ».
- Décision prise : suppression du segment dans le résumé étendu, sans reformulation de remplacement.
- Statut : corrigé dans les versions française et anglaise.

### Fin de lecture du résumé détaillé

- Point de lecture : résumé détaillé terminé le 12 novembre 2026.
- Impression générale de Bourhan : contenu validé, aucun problème de fond identifié.
- Demande pour la relecture finale : rechercher les répétitions, les détails trop fins et les développements disproportionnés par rapport à la taille du projet.
- Diagnostic provisoire : le résumé répète parfois l'introduction et les sections méthodologiques ; les principaux gains possibles concernent la modularité, les détails du contrat, la sélection des hyperparamètres, l'importance sampling, la liste des limites et l'équation prospective sur les coûts.
- Objectif proposé : ramener le résumé détaillé à environ deux pages et distinguer la longueur du corps principal de celle des annexes.
- Décisions appliquées : fusion des paragraphes sur la modularité, raccourcissement des usages possibles, renvoi des paramètres contractuels à la section dédiée, allègement modéré de la présentation des méthodes, suppression des détails de queue dans les résultats, raccourcissement du diagnostic sur les flux datés et condensation de la liste des limites sans suppression d'une catégorie de risque.
- Décisions non appliquées : le paragraphe sur les hyperparamètres reste détaillé et l'équation prospective sur les coûts est conservée.
- Correction de l'équation : la norme $L^1$, qui ne correspondait pas à toutes les régularisations étudiées, est remplacée par une pénalisation générique $\mathcal P(w)$.
- Statut : corrigé dans les versions française et anglaise.

### Calendrier des flux et calendrier de marché réel

- Passage concerné : liste des limites du résumé détaillé.
- Problème identifié : écrire que les « calendriers réels » sont absents peut laisser croire que le calendrier des paiements et les besoins de financement ne sont pas modélisés.
- Distinction à préserver : le projet tient compte des dates simulées de paiement, de l'accumulation du compte de trésorerie et du besoin de financement qui en résulte ; il n'intègre pas encore un calendrier de marché complet avec jours fériés, conventions exactes de règlement et contraintes opérationnelles réelles.
- Décision prise : distinguer explicitement, dans le résumé, la spécification du contrat, les limites de modèle et la section de financement, le calendrier simplifié effectivement utilisé des calendriers de marché complets et des conventions réelles de règlement encore absents.
- Statut : corrigé dans les versions française et anglaise.

### Audit de la bibliographie

- Demande : ne conserver que les références générales indispensables ou les travaux spécialisés réellement utiles au positionnement du projet.
- Références générales recommandées : Black--Scholes (modèle), Carr--Madan (décomposition des payoffs), Glasserman 2004 (Monte Carlo et importance sampling), Hastie--Tibshirani--Friedman (régularisation), McNeil--Frey--Embrechts (mesures de risque) et Rockafellar--Uryasev si l'expérience d'optimisation sous contrainte d'ES est conservée.
- Références spécialisées défendables : Guillaume pour les autocalls, Di Tella et al. pour la couverture parcimonieuse, et éventuellement Derman--Ergener--Kani comme unique référence de réplication statique d'options exotiques.
- Candidats prioritaires à la suppression : Cui et al. (chaînes de Markov non utilisées), Lokeshwar et al. (réseau neuronal non utilisé), Glasserman--Heidelberger--Shahabuddin 1999 (méthode asymptotique et stratification non implémentées), Kamtchueng (papier de travail spécifique et redondant), Breeden--Litzenberger (redondant avec Carr--Madan pour l'usage actuel) et Carr--Ellis--Gupta si Derman est conservé comme seule référence spécialisée de réplication statique.
- Décision prise : conservation des neuf références recommandées et suppression de Breeden--Litzenberger, Carr--Ellis--Gupta, Cui--Li--Zhang, Glasserman--Heidelberger--Shahabuddin (1999), Kamtchueng et Lokeshwar--Bharadwaj--Jain.
- Statut : bibliographie et citations corrigées dans les versions française et anglaise.

### Relecture rapide du résumé détaillé après validation

- Remarque générale : le résumé est cohérent, mais il peut être raccourci sans perdre ses résultats centraux.
- Répétition possible : les paragraphes sur la procédure transférable et sur la séparation en blocs modulaires se recouvrent ; envisager de les fusionner.
- Détail secondaire : la liste des usages possibles (interprétation, scénarios, couverture, valeur relative, validation) peut être raccourcie ou retirée du résumé.
- Détail secondaire : les paramètres contractuels complets de l'autocall peuvent être condensés en une phrase et renvoyés à la section consacrée au contrat.
- Détail secondaire : la construction précise de la couverture delta et ses deux fréquences de rééquilibrage peuvent rester dans le corps méthodologique plutôt que dans le résumé.
- Détail technique : les nombres d'observations dans les queues à 97,5 % et 99 % ainsi que le contrôle par importance sampling peuvent être retirés du résumé et conservés dans la section sur le risque de queue.
- Répétition possible : l'encadré de résultat répète les deux paragraphes qui le précèdent ; décider à la fin s'il faut conserver l'encadré ou raccourcir les paragraphes.
- Répétition possible : la première phrase de « Ce qui peut et ne peut pas être conclu » récapitule de nouveau toute la méthode.
- Allègement prioritaire : l'équation prospective combinant RMSE, ES, norme $L^1$ et coûts de transaction est trop détaillée pour le résumé ; envisager de la déplacer ou de la supprimer du résumé.
- Allègement prioritaire : condenser la longue liste des éléments de marché absents en quelques catégories générales.
- Statut : propositions uniquement, aucune modification appliquée.

### Longueur générale du rapport

- Constat de Bourhan : 56 pages paraissent excessives pour un projet volontairement humble.
- Objectif indicatif pour la relecture finale : viser environ 40 à 45 pages au total, ou 25 à 30 pages de corps principal hors pages liminaires, annexes et bibliographie.
- Méthode de réduction : supprimer d'abord les répétitions, les justifications défensives, les détails exploratoires et les explications présentes à la fois dans le résumé, la méthode, les résultats et les limites.
- Statut : à traiter lors de la relecture finale, section par section.

### Réintroduction de Kim et Lim comme référence historique

- Décision : réintroduire Kim et Lim uniquement comme référence historique et méthodologique sur la réplication statique récursive des autocalls.
- Positionnement à préserver : l'article relie les différentes dates d'observation par une construction récursive fondée sur des spreads de strikes et de maturités ; cette méthode n'est pas implémentée dans le notebook et ne constitue pas un benchmark numérique du rapport.
- Formulation prudente : parler de « l'un des premiers travaux directement consacrés » à cette question, sans affirmer qu'il s'agit du premier article.
- Emplacements : section 1.1, revue de littérature et bibliographie, dans les versions française et anglaise.
- Statut : appliqué sans modification des pages antérieures à la section 1.1.

### Fin de lecture de la partie 2

- Point de lecture : partie 2, « Étude de cas de l'autocall : contrat, modèle et valorisation », terminée le 13 novembre 2026.
- Allègement appliqué : condensation de la justification du contrat figé et du paragraphe sur le calendrier simplifié.
- Clarification de l'état : suppression de l'événement terminal redondant $D$ ; l'indicateur historique $J_i$ est désormais défini une seule fois et le remboursement terminal est exprimé avec $J_m$.
- Clarification méthodologique : reformulation de la limite des options européennes dépendant seulement du spot à leur échéance.
- Modularité : maintien explicite de l'extension aux modèles de volatilité locale, stochastique ou rugueuse, sous une forme raccourcie.
- Répétition supprimée : retrait des trois phrases précédant le plan de simulation, déjà couvertes par les sous-sections voisines.
- Notation : l'erreur standard est désormais écrite $\widehat{\operatorname{SE}}(\widehat V_0)$ ; la version française utilise la virgule décimale et un point-virgule dans l'intervalle.
- Valeur de modèle : suppression de la définition isolée du « prix minimal de couverture » et remplacement par une distinction plus directe entre valeur de modèle, capital initial de la stratégie et prix commercial.
- Statut : corrigé dans les versions française et anglaise.

### Niveau de détail et ton pédagogique

- Point de lecture : fin de la section 3.3.
- Consigne générale : éviter d'expliquer longuement une conséquence immédiate des équations ou de répéter sous forme d'exemple élémentaire une distinction déjà formulée mathématiquement.
- Supprimer en priorité les commentaires défensifs sur le rapport (« cela ne signifie pas que », « le rapport ne doit pas prétendre », « il ne s'agit pas d'un concours ») lorsqu'une formulation factuelle suffit.
- Conserver les explications nécessaires à la lecture des conventions de risque, des procédures de sélection et des limites économiques, même si elles sont pédagogiques.
- Nettoyage appliqué après 3.3 : transitions méthodologiques redondantes, analogie élémentaire avec l'apprentissage supervisé, justification défensive des références, exemple numérique élémentaire de compensation des flux et plusieurs commentaires métadiscursifs dans les résultats et limites.
- Les parties antérieures à 3.3 restent soumises à validation explicite avant modification.
- Autorisation reçue : condensation du mécanisme à états finis, de la définition du prix de modèle et de l'introduction de la réplication statique ; correction de « for every » en « pour tout » dans l'équation française. Modifications appliquées dans les deux versions le 13 novembre 2026.
- Autorisation reçue : suppression des répétitions sur les coûts et la négociabilité dans l'abstract et le résumé détaillé. Les informations supprimées du résumé restent regroupées dans les sections finales sur le risque de modèle, les coûts, le financement et dans l'annexe consacrée à l'objectif tenant compte des coûts.
- OLS : définition méthodologique raccourcie et ajout d'un tableau complet des quatre références statique/conditionnelle et Calls + Puts/Full. Le tableau général conserve uniquement l'OLS conditionnel Full comme borne de capacité principale.

### Fin de lecture de la partie 3

- Point de lecture : partie 3, « Cadre de réplication et références », terminée le 15 novembre 2026.
- Dictionnaire : les calls et puts restent la base pratique ; les digitales peuvent être structurées de gré à gré mais ne sont conservées que comme référence théorique dans l'univers Full.
- Notation : la maturité générique des options reste notée $u$, tandis que $T$ désigne la maturité finale de l'autocall ; l'approximation de la digitale par call spread est harmonisée avec $S_u$.
- Moindres carrés ordinaires : leur rôle est formulé comme le meilleur ajustement quadratique offert par le dictionnaire, et non comme une capacité maximale absolue.
- Références denses : la liste distingue explicitement les politiques conditionnelles obtenues par moindres carrés ordinaires et par Ridge.
- Couverture delta : la description a été vérifiée contre l'implémentation — grille logarithmique de 801 spots, quadrature gaussienne à 40 points, état de barrière, compte autofinancé et rééquilibrages quotidien ou tous les cinq jours.
- Financement : le diagnostic P95 est reformulé à partir du déficit maximal de trésorerie de chaque trajectoire et du montant couvrant 95 % de ces déficits.
- Allègement : suppression de la phrase répétitive concluant la présentation de la couverture delta.
- Statut : partie 3 relue et fixée dans les versions française et anglaise. Toute modification ultérieure devra être proposée avant application.

### Titres interrogatifs

- Constat : les titres commençant par « Pourquoi » donnaient un ton scolaire et retardaient l'annonce de l'idée principale.
- Décision : remplacer ces titres par des formulations nominales et directes dans tout le rapport, sans modifier le contenu des passages concernés.
- Exemples : « Pourquoi utiliser Black--Scholes » devient « Black--Scholes comme modèle de référence » ; « Pourquoi conserver trois profils » devient « Profils performance, compromis et parcimonie » ; « Pourquoi la RMSE et l'ES peuvent évoluer en sens opposés » devient « Opposition possible entre la RMSE et l'ES ».
- Extension de la règle : traiter de la même manière les titres introduits par « Comment », « Ce que » et « Ce qui », ainsi que leurs équivalents anglais « How » et « What ».
- Les formulations faussement interrogatives restantes ont été remplacées par des intitulés affirmatifs, sans modifier le contenu des sections.
- Statut : appliqué dans les versions française et anglaise le 15 novembre 2026.

### Présentation du risque avant couverture

- Remplacer les formulations abstraites telles que « centrer le passif brut » par une explication concrète du calcul.
- Préciser que les flux simulés sont comparés à leur moyenne de 100,423 et que la RMSE de 7,76 et l'ES de 4,42 mesurent la variation du payoff avant couverture, non son prix.

### Hiérarchie des métriques de risque

- Métriques principales : RMSE et Expected Shortfall à 97,5 %.
- Diagnostics secondaires : erreur moyenne, MAE, taux de sous-réplication et perte maximale observée.
- La VaR n'est plus présentée comme un résultat autonome.
- Toute métrique annoncée doit être chiffrée et commentée ; le tableau global doit employer les mêmes définitions statistiques tout en signalant les différences d'objet de risque, de capital et de coûts.
- Le carnet des éléments à régénérer lors des prochains FAST et REPORT se trouve dans `docs/FINAL_REPORT_REFRESH.md`.

### Reproductibilité des figures

- Toute modification visuelle doit être appliquée au notebook ou à la fonction canonique qui génère la figure, et non uniquement au PDF placé dans Overleaf.
- La même correction doit être vérifiée dans les exports français et anglais.
- Un run FAST sert à contrôler le rendu avant le REPORT final.
- La procédure complète et l'inventaire des figures déjà corrigées sont conservés dans `docs/FIGURE_REPRODUCIBILITY.md`.

### Actualisation du 15 novembre et frontière de relecture 4.3

- Signaler au lecteur de la relecture chaque modification située avant 4.3.
- Actualisation numérique annoncée : prix 100,538, évaluation de risque sur 2 500 trajectoires, RMSE résiduelle proche de 2,11 et ES entre 7,96 et 8,18.
- Figure 1 : remplacer le commentaire de l'ancienne sélection par les valeurs du dernier diagnostic (Lasso/Elastic Net : 2 à 19 options, Ridge : 92 à 211, L0 : 2 à 5).
- Figure 2 : 10 recalibrations au lieu de 30 ; convergence du profil Full--L0 compromis dans 6 cas sur 10. Supprimer l'affirmation erronée de convergence générale et mettre le commentaire en accord avec ce diagnostic.
- Ne pas confondre les nouveaux diagnostics d'hyperparamètres `2026-11-15_172546_fast` avec les politiques évaluées par `2026-11-15_200419_fast`, qui emploient toujours la sélection promue `2026-10-15_225308_report`.
- Aucun recalcul de notebook n'est lancé par l'assistant ; les deux REPORT finaux seront exécutés par l'utilisateur.
- Le 16 novembre, suppression autorisée de la phrase « Ces profils de diagnostic sont distincts de la sélection antérieure figée utilisée pour l'évaluation du risque présentée en section 5. » et de son équivalent anglais, dans les fichiers locaux et par remplacement ciblé sur Overleaf. Aucune autre modification avant 4.3 dans cette intervention.
- Le 16 novembre, introduction de 4.4 reformulée après accord : présenter le but de l'importance sampling avant le mélange gaussien, définir les densités p et q, expliquer le poids d'une trajectoire surreprésentée et la normalisation. Versions FR et EN alignées, sans modification avant 4.3.
- Distinguer les deux usages effectifs de l'IS : estimation du risque à positions fixées et calibration de nouveaux poids financiers sur trajectoires pondérées. Ne pas affirmer globalement que l'IS laisse les positions inchangées. Distinction intégrée en 4.4 après accord, FR et EN.
- Diagnostics IS clarifiés après accord : expliquer l'ESS par la concentration des poids et le cas de poids égaux, distinguer précision globale et précision en queue, préciser le rôle des diagnostics complémentaires et des intervalles bootstrap. La sélection vise la précision, pas une ES plus basse. Appliqué en 4.4 uniquement, FR et EN.

### Reprise de la section 4.4 le 16 novembre 2026

- Développement d'ESS synchronisé par remplacement ciblé sur Overleaf dans les deux sources. Compilations FR et EN vérifiées dans les journaux Overleaf (0 erreur, 0 avertissement). La source FR est le document principal.
- Passage sur le mélange validé et appliqué en local et sur Overleaf dans les deux langues. Il précise le rôle des composantes standard et décalées, puis relie le ciblage par la baisse terminale aux contributions à l'ES mesurées par type de trajectoire. Compilations vérifiées (0 erreur, 0 avertissement), document principal FR.
- Pour la suite de la relecture, limiter l'affirmation sur les positions inchangées à l'estimation du risque sur portefeuilles figés. Dans le 2×2, commenter l'effet du plan de simulation sur les positions recalibrées à objectif d'optimisation fixé, à partir du seul échantillon de cette expérience.
- Après accord, passage « Limites de l'importance sampling » resserré en 4.4 dans les deux langues, en local et sur Overleaf : précision en queue propre à chaque portefeuille, distinction entre positions fixées et recalibrage dans le 2×2. Retrait de la phrase générale sur l'absence de biais et du rappel des diagnostics. Les deux compilations affichent 0 erreur et 0 avertissement. Document principal FR.
- Dans le tableau global, conserver les 15 lignes exportées. Pour le passif centré, employer « fréquence des pertes positives ». Les comparaisons statiques et conditionnelles supplémentaires seront vérifiées aux prochains exports.
- Expérience 2×2 explicitée en 4.4, en local et sur Overleaf, FR et EN. Les quatre cas croisent le mode de simulation (Monte Carlo standard ou importance sampling) et l'objectif (RMSE seule ou RMSE avec contrainte d'ES). Chaque cas est recalibré et seuls les cas avec importance sampling utilisent des trajectoires pondérées. Deux compilations vérifiées sans erreur ni avertissement. Document principal FR.

### Relecture intégrale de la partie 4 — 16 novembre 2026

- Périmètre : sources locales FR/EN, deux figures PDF de 4.2 dans chaque langue, exports et implémentation. Les deux textes sont alignés sur le fond ; les remarques ci-dessous s'appliquent aux deux langues. Relecture seule, sans modification du rapport ni relance de notebook.
- 4.1 : fusionner les deux phrases qui décrivent les blocs disjoints. Préciser que 60/20/20 est le découpage de l'étude de sélection et que les 2 500 trajectoires de l'évaluation principale sont simulées séparément. Borner l'affirmation sur les trajectoires communes aux comparaisons qui les partagent effectivement.
- 4.2 : dans le diagnostic du 15 novembre, le journal des filtres place la stabilité avant Pareto, puis indique un contrôle face à la référence statique et la déduplication avant l'attribution des profils. Distinguer ce filtrage de l'audit des profils sélectionnés. La dominance inclut l'égalité sur un axe et une amélioration stricte sur l'autre. La normalisation utilise zéro sur un axe sans dispersion. Vérifier le rôle du plafond de positions avant de le présenter comme commun à tous les profils.
- Figure 1 : les comptes 2–19, 92–211 et 2–5 ainsi que la plage de RMSE 1,91–3,58 correspondent à la figure et à `selected_regularisation_profiles.csv`. Le fichier `report_regularisation_compromise.csv` donne 3,501 au lieu de 3,576 pour Lasso Calls + Puts ; réconcilier ces deux exports au rafraîchissement final. Conserver dans le corps. Décaler l'étiquette Elastic Net bleue, partiellement masquée par le point orange dans les deux PDF, et envisager des graduations utiles sous 10 sur l'axe logarithmique. Harmoniser « binaires » avec « options digitales » dans la figure FR si elle est régénérée.
- Figure 2 : 10 tentatives et 6 convergences sur 10 pour Full–L0 compromis, confirmées par l'export. Les boîtes décrivent les seules recalibrations convergées ; les croix grises montrent les résultats provisoires. L'axe et les unités sont explicites et la légende est dense à la taille du rapport. Pour alléger, garder les seuls profils compromis dans le corps et déplacer la figure complète en annexe, ou conserver le visuel complet si la comparaison des trois profils est commentée. Si une modification est validée, intervenir dans le générateur canonique et réexporter FR/EN. Aucun visuel changé.
- 4.3 : 100,538 provient du calcul de valorisation antithétique. Les valeurs 7,940 et 4,488 sont confirmées dans l'export de risque standard, dont le passif est centré sur la moyenne de son propre échantillon. Retirer 100,538 de la description du centrage de cet échantillon. Employer « erreur moyenne signée », « fréquence des pertes positives » pour toute variable de perte et « taux de sous-réplication » pour le résidu d'une couverture. La fréquence brute exportée vaut 93,28 %. Regrouper la convention de signe avec la définition du résidu, puis alléger la liste des métriques et la répétition des équations.
- 4.3–4.4 : parler de 62,5 et 25 équivalents-trajectoires de masse de queue, à 97,5 % et 99 %. Le code répartit au prorata la masse requise entre les pertes ex æquo au seuil. Dans l'export de risque du passif centré, l'ESS de queue vaut 437 à 97,5 % et à 99 %. Revoir aussi la phrase qui assimile cette masse à un nombre d'observations en 5.6.
- 4.4 : réserver le critère de précision au choix du plan de simulation pour l'estimation du risque. Le diagnostic du 15 novembre recommande le Monte Carlo standard pour les deux dictionnaires, tandis que les résultats IS du run de risque utilisent les mélanges promus en octobre. Pour le prochain REPORT, contrôler le choix effectivement promu et ses conséquences sur l'expérience 2×2 et les figures IS. Éviter de redéfinir l'IS dans le passage sur les faibles effectifs de queue. Dans le 2×2, les deux variantes gardent la pénalisation Elastic Net ; formuler « avec ou sans contrainte d'ES ».
- 4.4 : le diagnostic de contributions à l'ES distingue rappel, maturité sans franchissement de la barrière de protection et maturité avec franchissement. Le rappel manqué de peu suivi d'un rebond reste un exemple de trajectoire que le décalage terminal cible mal. L'export ne l'identifie pas comme une catégorie propre. Ajouter un renvoi vers les contributions par régime sans leur attribuer une résolution plus fine.

### Décisions et application après relecture de la partie 4

- Autorisés et appliqués dans les sources FR/EN, en local et sur Overleaf : chronologie sans la phrase sur la mise à l'écart du dernier bloc, périmètre des trajectoires communes, règle du compromis, commentaires et légende des figures, signe du résidu, hiérarchie des métriques et fréquence des pertes positives, centrage du passif, masse de queue en 4.3, décomposition de l'ES et formulation du 2×2.
- Conservation demandée de la procédure et des filtres en 4.2, ainsi que des paragraphes sur la précision du Monte Carlo en queue et le critère de choix du mélange en 4.4.
- La légende et le commentaire de la figure 2 ont été adaptés à la figure actuelle. Les modifications graphiques, dont la vue limitée aux profils compromis, restent à faire dans le générateur pour l'actualisation finale.
- Après autorisation de la bascule temporaire vers l'anglais, les deux compilations Overleaf ont été vérifiées (0 erreur, 0 avertissement). Le français a été rétabli comme document principal et l'aperçu affiche le PDF français.

### Début de la partie 5

- En 5.1, le paragraphe de lecture des tableaux distingue désormais la capacité d'ajustement, la validation utilisée pour sélectionner les profils et l'évaluation du risque à positions fixées sur des trajectoires indépendantes. Modifié après accord en local et sur Overleaf, FR et EN. Compilations vérifiées (0 erreur, 0 avertissement), document principal FR.
- En 5.2, le tableau 3 précise dans sa légende que les positions OLS sont calibrées avec alpha fixé à zéro, sans recherche d'hyperparamètres, puis évaluées sur les mêmes trajectoires indépendantes. Légende synchronisée FR/EN en local et sur Overleaf. Les deux compilations affichent 0 erreur et 0 avertissement. Document principal FR.
- Vérifications numériques : les six RMSE du tableau 2 concordent avec les exports, tout comme les trois nombres d'options actives statiques. L'export ne contient pas de décompte conditionnel. Dans le tableau 3, les quatre ES à 97,5 % concordent avec l'export. La RMSE OLS conditionnelle Calls + Puts (21,0104975) s'arrondit directement à 21,010, contre 21,011 affiché. À vérifier lors de la prochaine actualisation des chiffres.

### Frontière de relecture et proposition pour la partie 5

- Les parties antérieures à la section 5, résumé compris, sont désormais figées. Toute modification ultérieure demande un accord explicite. L'actualisation des chiffres à ces emplacements devra donc être proposée à partir des nouveaux exports.
- La proposition bilingue est dans `docs/relecture-partie-5/`. Elle ouvre sur la comparaison OLS à alpha fixé, puis traite l'objectif par échéance ou par total, les hyperparamètres effectivement utilisés, le risque hors échantillon, l'importance sampling à positions fixées et le recalibrage 2×2. Chaque version conserve les six tableaux, les sept figures et les 15 lignes de la comparaison globale. Le tableau des benchmarks pénalisés est proposé en annexe.
- La proposition corrige le double arrondi OLS conditionnel Calls + Puts, la RMSE de 2,35 restée dans le commentaire anglais et l'attribution du centrage au prix de valorisation. Les compléments chiffrés sur le financement, la concentration de la queue, les intervalles bootstrap et le 2×2 proviennent des exports existants et sont rattachés à leurs échantillons.
- Le notebook exploratoire est recensé dans l'annexe proposée. Ses cibles distinctes et ses scénarios OTC ne sont pas agrégés aux résultats qui évaluent les portefeuilles principaux. Les résultats exploratoires qui ne disposent pas encore d'un export identifié restent à documenter.
- Sur demande, proposition intégrée aux deux sources locales et aux deux sources Overleaf, pour relecture dans le PDF. Le texte antérieur à la partie 5 a été vérifié intégralement dans les deux sources avant et après insertion. Les deux compilations indiquent 0 erreur et 0 avertissement. Le français est le document principal. Les deux fragments de transfert restent dans l'arborescence Overleaf et ne sont inclus dans aucun rapport. Aucun notebook relancé.
- En 5.1, la méthode A est explicitée : calibration d'un panier par date sur les trajectoires encore vivantes et possibilité de deux paniers à maturité selon l'état de la barrière de protection. Sources locales et Overleaf alignées en FR et EN. Compilations vérifiées sans erreur ni avertissement. Document principal FR.
- Après accord, les objectifs A et B sont définis dans l'ouverture de la partie 5 et la référence OLS conditionnelle renvoie seulement à A. Le commentaire OLS interprète l'interaction entre conditionnement et digitales. À partir de la partie 5, plusieurs commentaires guident la lecture des panneaux, des échelles, des marqueurs et des intervalles, puis expliquent l'arbitrage ou l'effet observé. Les 15 lignes du tableau global sont conservées et les éléments avant la partie 5 sont intacts. Sources FR/EN synchronisées et compilées sur Overleaf avec 0 erreur et 0 avertissement. Document principal FR.
- Correction de l'ouverture et de 5.1 : A et B sont présentés comme deux objectifs de calibration. Les quatre références OLS sont calibrées sur les paiements datés (A). La RMSE et l'ES sont calculées ensuite sur la somme des écarts actualisés par trajectoire. La phrase générale sur les dernières décimales a été retirée. Sources FR/EN locales et Overleaf alignées, compilations sans erreur ni avertissement, document principal FR.
- Figure 3, légende FR/EN : les barres distinguent les deux calibrations. Les deux RMSE sont calculées pour chaque portefeuille à poids fixés, sur les mêmes 625 trajectoires d'évaluation. Légendes synchronisées en local et sur Overleaf. Compilations vérifiées sans erreur ni avertissement, document principal FR.
- L'ouverture de la partie 5 précise que les portefeuilles d'options étudiés après la comparaison OLS sont conditionnels, sauf mention contraire. La section 5.2 rapproche les barres A du bas de la Figure 3 des lignes OLS conditionnelles et explicite les différences de pénalisation et d'échantillon (625 contre 1 250). Modifié en local et sur Overleaf en FR et EN, compilations sans erreur ni avertissement, document principal FR.
- Après relecture, retrait du rapprochement entre les barres A du bas et le tableau OLS. Les protocoles et tailles d'échantillon restent indiqués en 5.1 et 5.2. Sources FR/EN synchronisées et recompilées sur Overleaf sans erreur ni avertissement. Document principal FR.
- Analyse A/B remplacée après accord dans les sources locales FR/EN : inversion Calls + Puts attendue au regard des objectifs, compensation temporelle confirmée par les erreurs moyennes par date, lien avec le déficit cumulé et résultat Full plus inattendu puisque A y domine sur les deux RMSE. L'interprétation tient compte des réglages et constructions différents. Le diagnostic du compte autofinancé sur 250 trajectoires a été déplacé dans la section sur le financement. Synchronisation Overleaf et compilation en attente : le navigateur intégré a signalé que l'accès local est indisponible pour ce chat.

- Accès au navigateur intégré rétabli. Analyse A/B et déplacement du diagnostic de financement sur 250 trajectoires synchronisés sur Overleaf en FR et EN. Les deux compilations affichent 0 erreur et 0 avertissement. Le français est rétabli comme document principal.
- Exemple de compensation temporelle précisé : Calls + Puts, méthode B, Elastic Net, 625 trajectoires. RMSE paiements 49,79 et RMSE total 1,49 ; excédent moyen initial 50,70 puis déficits moyens 12,26, 6,52 et 31,99. FR/EN synchronisés sur Overleaf et compilés sans erreur ni avertissement, document principal FR.
- Exemple de financement 36,65 contre 0,83 précisé : portefeuilles conditionnels Calls + Puts, pénalisation Elastic Net, mêmes 625 trajectoires. Sources locales et Overleaf FR/EN synchronisées, compilations sans erreur ni avertissement, document principal FR.
- Suppression autorisée de la phrase vague sur l'interprétation à examiner avec les réglages propres aux deux procédures. Les différences concrètes restent expliquées juste après. FR/EN synchronisés en local et sur Overleaf, compilations sans erreur ni avertissement, document principal FR.
- Date du 15 octobre retirée de la présentation des hyperparamètres retenus en 5.3, FR/EN en local et sur Overleaf. Les paramètres, profils, chiffres et figures associés seront remplacés après les exécutions finales de l'utilisateur, en vérifiant la sélection effectivement utilisée. Compilations sans erreur ni avertissement, document principal FR.
- Référence au diagnostic distinct de novembre retirée de 5.3, FR/EN en local et sur Overleaf. Convention rédactionnelle pour la version finale : tous les chiffres, hyperparamètres et figures proviendront des exports actualisés après les deux REPORT de l'utilisateur. Les identifiants et différences entre anciens runs restent des informations de suivi de production. Les deux compilations affichent 0 erreur et 0 avertissement, document principal FR.
- Explication des nœuds en 5.3 simplifiée : date, état connu au choix du panier, fréquence d'utilisation pour la moyenne et taille du plus grand panier pour le maximum. Mention de l'état mutualisé retirée de ce passage. FR/EN synchronisés en local et sur Overleaf, compilations sans erreur ni avertissement, document principal FR.
- Précision sur l'exclusion de la trésorerie retirée du paragraphe explicatif des nœuds à la demande de l'utilisateur. FR/EN en local et sur Overleaf, compilations sans erreur ni avertissement, document principal FR.
- Tableau 3 : présentation et légende précisent conditionnel B, calibration sur le total actualisé et RMSE totale de validation. En-tête clarifié FR/EN. Préciser conditionnel et objectif A/B dans chaque tableau ou figure concerné lors de la suite de la relecture. B définit l'objectif global de l'étude parcimonieuse ; les paiements datés restent un diagnostic indispensable. Sources locales et Overleaf alignées, compilations sans erreur ni avertissement, document principal FR.
- Clarifications systématiques après la frontière de relecture : 15 remplacements par langue sur les légendes et présentations OLS, A/B, frontières de validation, risque principal et secondaire, concentration, IS à poids fixés, 2×2 et benchmarks en annexe. Chaque comparaison identifie désormais explicitement les politiques conditionnelles B ou les ajustements datés A et l'objet de la RMSE/ES. Les lignes OLS statiques du tableau global portent A. Aucun chiffre modifié. FR/EN synchronisés sur Overleaf et compilés sans erreur ni avertissement, document principal FR.
- Audit avant 5, sans modification des passages figés : les légendes des figures de sélection et stabilité en 4.2 pourraient préciser méthode conditionnelle B et RMSE totale de validation. Les objectifs génériques de la partie 3 restent génériques. Ces éventuelles précisions seront proposées avant toute édition des parties figées.
- Tableau 3 : en-tête raccourci en RMSE à la demande de l'utilisateur, la définition totale de validation restant explicitée dans le texte et la légende. FR/EN en local et sur Overleaf, compilations sans erreur ni avertissement, document principal FR.
- En 5.3, formulation sur l'audit renforcé remplacée par un renvoi aux diagnostics d'initialisation et de stabilité déjà réalisés. Sources FR/EN locales et Overleaf alignées, compilations sans erreur ni avertissement, document principal FR.
- Figures 4 et 5 : vue complete et zoom, profils P/C/S reperes et echantillon de validation distingue du tableau 3. Generateur, notebook et export EN mis a jour. Figures et legendes FR/EN synchronisees sur Overleaf. Compilation EN verifiee sans erreur ni avertissement. Compilation FR lancee apres selection du document principal FR. La perte d'acces au navigateur integre a empeche de verifier le journal FR et le reglage final. Aucun notebook relance.
- Figures 4 et 5 : panneaux empilés sur toute la largeur, vue d’ensemble en haut, zoom en bas et légende commune. Générateur utilisé par le notebook et sources TeX FR/EN mis à jour. Visuels régénérés depuis les exports existants, sans relancer les notebooks. Synchronisation et compilations Overleaf en attente, accès au navigateur intégré indisponible.
- Figures 4 et 5 empilees : les quatre PDF et les legendes FR/EN ont ete synchronises sur Overleaf. Les deux compilations affichent 0 erreur et 0 avertissement. Le francais est le document principal et les deux figures ont ete controlees dans son apercu PDF.
- Figures 4 et 5 : barriere de placement apres leur commentaire en 5.3, en local et sur Overleaf. Les figures precedent la suite du texte. Compilations FR et EN sans erreur ni avertissement, document principal FR.
- Figures 4 et 5 : commentaire place entre les deux figures et placement fixe en 5.3. Sources locales et Overleaf FR/EN synchronisees. Dans le PDF FR, le commentaire suit la figure 4 et la suite de 5.3 partage la page de la figure 5. Un blanc subsiste avant la figure 4. Deux compilations sans erreur ni avertissement, document principal FR.
- Figures 4 et 5 : vues (a) et (b) exportees separement par le notebook et son generateur, avec une legende par panneau. Exports PDF/PNG FR/EN regeneres depuis les tables existantes sans lancer le notebook. Sources locales et Overleaf synchronisees, deux compilations sans erreur ni avertissement. PDF FR controle : les panneaux se repartissent sur trois pages et conservent la numerotation 4 et 5. Document principal FR.
- Fig. 4(b) : diagnostic Elastic Net Calls + Puts sur validation de queue, plafonds fixes a la RMSE et au nombre total de coefficients actifs du compromis initial. E = ES minimum, RE = minimum sous plafond RMSE, REP = minimum sous les deux plafonds et coincide avec le compromis actuel. Notebook et exports locaux FR/EN, Overleaf FR/EN synchronises et compiles sans erreur ni avertissement. Aucun notebook relance. Partie 4 intacte. Au renouvellement des exports, recalculer ces trois choix et confirmer le gain sur un echantillon commun distinct avant tout changement de profil principal.
- Suite figures 4 et 5 : trois nouvelles selections independantes du compromis initial (ES minimale, RMSE-ES, RMSE-ES-parcimonie), par univers et penalisation. Candidats converges et stables dans les bornes de taille. Distances a poids egaux apres normalisation pour les deux compromis. Le notebook Hyperparameters exporte la selection et la comparaison de validation. Le notebook principal exporte risk_profile_selection_comparison a poids fixes sur les memes trajectoires par univers et indique le run source. Ordre FAST : Hyperparameters, promotion explicite du nouveau FAST, notebook principal. Aucun notebook lance et Overleaf sera repris apres les nouveaux exports. Reprendre les quatre passages autorises en 4.2/5.3, figures 4 et 5, et remplacer les anciens chiffres et la coincidence C/REP par les nouveaux resultats.
- Controle FAST : Hyperparameters 2026-11-16_154918_fast et principal 2026-11-16_154950_fast termines, mais le principal et la configuration promue pointent sur 2026-11-15_172546_fast. Comparaison risque 24 lignes (3 profils), validation nouvelle 48 lignes (6 profils par groupe), comparaison globale 30 lignes. Panneaux de validation FR/EN prepares dans tmp/actualisation_2026-11-16_fast. Actualisation coherente en attente de la promotion du nouveau FAST et de la relance du principal uniquement.
- Le FAST promu suffixe _2 etait une reexportation des memes donnees sans figures. Poids, tables et selection compares au premier export. Les 26 figures et leurs entrees de manifeste ont ete restaurees dans _2 et latest. La promotion a maintenant sa propre cellule dans le notebook et son generateur, sans reexportation.
- FAST principal 2026-11-16_180227_fast aligne sur Hyperparameters 2026-11-16_154918_fast_2 : 48 evaluations et 30 lignes de comparaison globale. Sources FR/EN locales : 4.2 autorisee, tableaux des profils et risque, diagnostic A/B et analyse des six selections, figures 3-6 et 9 actualises. Le pilote a retenu le MC standard dans les deux univers : aucun nouvel export IS a positions fixees ni de concentration combinee, et le 2x2 compare deux echantillons MC. Les anciens resultats correspondants sont identifies dans le brouillon. Resume et passages proteges avec anciens chiffres a soumettre avant synchronisation. Aucune compilation Overleaf a ce stade.

### Actualisation locale sur les deux exports apparies

- La nouvelle evaluation utilise bien la selection promue. OLS, valorisation et stabilite des trois profils initiaux verifiees. Exemples A/B, financement, annexe des ajustements penalises, identifiants de reproductibilite et figures d'annexes actualises a partir des exports correspondants. Les comparaisons IS a positions fixees conservees comme resultats anterieurs, avec provenance explicite.
- Passages proteges a valider : abstract et resume detaille FR/EN. Remplacer RMSE 2,11 (baisse 73,4 a 73,5 %) et ES 7,96 a 8,18 par RMSE 3,56 a 6,22 (baisse 21,7 a 55,2 %) et ES 10,05 a 15,64 pour les quatre compromis initiaux. Mentionner que la RMSE 7,94 du passif est calculee autour de la moyenne de ses flux sur les trajectoires d'evaluation. En 4.4, distinguer le plan prevu avec IS du repli realise sur deux echantillons MC.
- Overleaf : projet accessible, telechargement de la source de comparaison refuse par le navigateur apres refus utilisateur. Aucune synchronisation ni compilation effectuee pendant cette reprise.
- Accord utilisateur : abstract, resume detaille et 4.4 mis a jour en rouge en FR/EN. Titre et renvoi 5.3 autorises en 4.2 egalement marques en rouge. Six marques par source, toutes avant les resultats. Synchronisation et compilation Overleaf en attente.
- Overleaf : versions actualisees FR et EN transferees dans deux sources dediees, avec les 20 PDF par langue dans deux dossiers de revision. Les sources et figures precedentes restent accessibles. Deux compilations verifiees, 0 erreur et 0 avertissement. Document principal : rapport_autocall_actualise_fr.tex. Marques rouges dans les passages proteges.
- Marquage rouge retire apres validation, en local et dans les deux sources actualisees Overleaf. Compilations FR/EN : 0 erreur, 0 avertissement. Document principal FR.
- Audit de provenance : figures 7 (concentration), 8 (IS a positions fixees), decomposition par regimes, ESS/poids/intervalles et commentaires correspondants proviennent du principal 2026-11-15_200419_fast, lie a la selection 2026-10-15_225308_report. Le principal 2026-11-16_180227_fast n'exporte ni les intervalles IS ni la concentration/decomposition, actuellement produites seulement quand une branche IS est executee. Standard MC retenu pour les deux univers. Le 2x2 courant et les planches IS du pilote d'hyperparametres sont actualises. Figures 1 et 2 conservees avec selection et stabilite initiales numeriquement identiques. A revoir : phrase en 4.4 qui presente les deux usages comme realises dans la meme execution et conclusion qui devrait distinguer les compromis initiaux et ceux avec ES.

- Correction : diagnostics MC de concentration et decomposition sortis du bloc conditionnel IS dans le notebook principal. Syntaxe verifiee, aucun notebook relance. Introduction 4.4, conclusion et legendes des deux figures historiques corrigees en FR/EN local et Overleaf par remplacements cibles. Compilation EN lancee mais journal non verifie ; compilation FR a faire, acces navigateur devenu indisponible.
- Audit figures 4a/b et 5a/b sur les PDF actuels : les PNG FR sont anciens, seuls les PDF ont ete remplaces lors de la derniere actualisation. 4b : etiquettes en collision avec titre et autres reperes. 5b : etiquettes superposees et zoom vertical faible car profils Lasso a ES 25-27 inclus. Legende integree sans losange E/RE/REP. Cercle encode la taille du candidat mais etoile/losange a taille fixe, exige clarification. Frontiere calculee par penalisation sur tous les converges, y compris 8 non admissibles en Calls + Puts et 1 en Full ; statut admissible absent du visuel. Commentaire du rapport juxtapose points de validation et chiffres d'evaluation independante, necessite support tabulaire distinct. Audit seulement, aucun visuel modifie.

- Figures 4/5 : generateur du notebook corrige, annotations remplacees par liste de profils et coordonnees, frontiere recalculée sur candidats admissibles, exclus marques par croix, zoom Full resserre. PDF/PNG FR/EN regeneres depuis les exports. Legendes locales precisees. Aucun notebook relance. Overleaf indisponible, transfert et compilations en attente.
- Les panneaux 4a, 4b, 5a et 5b corriges ont ete transferes dans actualisation-fr et actualisation-en sur Overleaf. Legendes corrigees par remplacements cibles. Compilations anglaise et francaise : 0 erreur, 0 avertissement. Source principale rapport_autocall_actualise_fr.tex.
- Figures 4/5 revisees : (a) tous les candidats et legende en deux lignes (penalisation, effectifs, admissibilite) ; (b) uniquement les portefeuilles selectionnes, cercles a aire variable et etiquettes groupees au meme portefeuille, sans liste laterale. Code canonique du notebook et textes alignes. PDF/PNG FR/EN regeneres depuis les exports. Transfert Overleaf et compilations FR/EN sans erreur ni avertissement. Francais principal.
- Legendes 4a/5a allegees a la demande : retrait de la mention vue d'ensemble et des explications deja presentes dans la legende graphique. FR/EN local et Overleaf alignes. Deux compilations sans erreur ni avertissement, francais principal.
- Phrase explicative sous les panneaux (a) retiree du generateur et des PDF/PNG FR/EN, puis transfert Overleaf. Deux compilations sans erreur ni avertissement, francais principal.
- Texte sous le panneau 4b retire, seul le repere (b) reste. FR/EN local et Overleaf alignes, compilations sans erreur ni avertissement.
- Paragraphe repetant les definitions E/RE/REP sous les figures retire a la demande en FR/EN, local et Overleaf. Compilations sans erreur ni avertissement, francais principal.
- Figure 5 alignee sur figure 4 : titre complet en (a), aucun titre dans (b), texte sous (b) reduit au repere. Regeneration par le code du notebook en FR/EN et transfert Overleaf. Compilations sans erreur ni avertissement.

- Tableaux recap apres 4b et 5b ajoutes FR/EN : alpha relatif, rho, total options, RMSE et ES sur validation de queue. Regles groupees par solution : 13 lignes Calls + Puts et 15 Full. Exports tires du run hyperparametres promu. Quatre fragments inclus sur Overleaf pour insertion ciblee.
- Figure 4 : description placee au-dessus du panneau a, titre et legendes graphiques du a retires, espace avant b reduit. Generateur notebook, PDF/PNG FR/EN et sources locales modifies. Overleaf synchronise et deux compilations sans erreur ni avertissement, francais principal.
- Figure 4 : espace entre panneaux encore reduit et trois lignes de legende resserrees. Code notebook, PDF/PNG FR/EN et sources actualises. Overleaf compile dans les deux langues sans erreur ni avertissement, francais principal.
- Figure 5 alignée sur la figure 4 : description au-dessus, panneau a sans titre ni légende, panneau b sans légende LaTeX, panneaux rapprochés et légende du b resserrée. Générateur utilisé par le notebook et figures FR/EN actualisés depuis les exports existants. Synchronisation Overleaf à reprendre dès que le navigateur intégré répond.
- Panneaux 4b et 5b : léger dégagement sous le libellé RMSE totale et espacement harmonisé entre les trois lignes de légende. Générateur du notebook et exports FR/EN mis à jour depuis les données existantes. Les quatre panneaux b ont été transférés sur Overleaf. Compilation FR : 0 erreur, 0 avertissement. Compilation EN non vérifiée après ce transfert.
- Tableaux des profils après les figures 4 et 5 : unité en en-tête, légendes raccourcies avec renvoi à la figure et à son échantillon de validation de queue. Paragraphe intercalé sur les six profils Elastic Net supprimé. Sources locales et Overleaf FR/EN mises à jour. Compilation Overleaf FR : 0 erreur, 0 avertissement. Compilation EN non vérifiée.
- Figure 5 : panneaux FR/EN régénérés précédemment et désormais transférés dans actualisation-fr et actualisation-en. Les blocs LaTeX de main_fr.tex et main_en.tex reprennent la mise en page de la figure 4. Compilation FR vérifiée, 0 erreur, 0 avertissement et deux débordements déjà présents dans les tableaux des profils. Compilation EN non vérifiée.
- Figure 4 : panneau b à 86 % de la largeur, tableau Calls + Puts compact et regroupement des trois éléments sur une page. Sources locales et Overleaf FR/EN modifiées. Aperçu FR vérifié sur la page 30 du PDF (29 imprimé), compilation sans erreur. Seul le débordement horizontal du tableau Full reste signalé. Compilation EN non vérifiée.
- Figure 5 : même largeur de 86 % pour le panneau b et même format compact du tableau Full que pour la figure 4. Espacements verticaux légèrement réduits pour les deux lignes supplémentaires du tableau Full. Sources locales et Overleaf FR/EN synchronisées. Page 31 du PDF français vérifiée, 0 erreur et 0 avertissement. Rendu anglais non vérifié.
- Section 5.3 : après le tableau 4, comparaison de la RMSE des mêmes profils C de Calls + Puts à poids fixés entre les tableaux 3 et 4. Renvois LaTeX automatiques. Sources locales et Overleaf FR/EN synchronisées. Renvois 3 et 4 vérifiés dans le PDF FR, compilé sans erreur ni avertissement. Compilation EN non vérifiée.
- Tableaux 4 et 5 triés par profil P, C, S, E, RE, REP. Les 24 lignes de chaque tableau correspondent aux valeurs précédentes. Sources FR/EN locales et Overleaf synchronisées. Compilation FR vérifiée, tableaux sur la page suivant leur figure. Compilation EN non vérifiée.
- Figure 4 : description remontée de 3 mm et panneaux a/b à 95 % et 82 % de la largeur du texte. Sources locales et Overleaf FR/EN synchronisées. Compilation et aperçu FR vérifiés, 0 erreur et 0 avertissement. Compilation EN non vérifiée.
- Figure 4 : description remontée de 3 mm supplémentaires, panneaux à 80 % et 86 %, tableau Calls + Puts en 8 pt et regroupé avec les deux panneaux. FR/EN local et Overleaf synchronisés. Les deux panneaux et le tableau tiennent sur la page 30 du PDF FR, compilé sans erreur ni avertissement. Rendu EN non vérifié.
- Annulation du regroupement compact de la figure 4 et du tableau Calls + Puts. Retour aux panneaux à 95 % et 82 %, description remontée de 3 mm et tableau par profil sur la page suivante. Sources locales et Overleaf FR/EN restaurées. PDF FR vérifié, 0 erreur et 0 avertissement. Compilation EN non vérifiée.
- Figures 4 et 5 : vues générales retirées du rapport, graphiques des profils conservés et regroupés chacun avec son tableau. Légendes adaptées avec renvoi au tableau 3 pour distinguer les échantillons. Sources FR/EN locales et Overleaf synchronisées. Les deux regroupements ont été vérifiés dans le PDF FR, compilation sans erreur ni avertissement. Rendu EN non vérifié.
- Figures 4 et 5 : graphiques agrandis à la largeur du texte et espace avant les tableaux réduit. Sources locales et Overleaf FR/EN synchronisées. Les deux paires figure et tableau tiennent sur leurs pages respectives dans le PDF FR, compilé sans erreur ni avertissement. Compilation EN non vérifiée.
- Figures 4 et 5 : formulation raccourcie du renvoi aux trajectoires du tableau 3. Sources locales et Overleaf FR/EN mises à jour. Compilation FR sans erreur ni avertissement. Compilation EN non vérifiée.
- Section 5.3 : dernière phrase redondante de la comparaison des tableaux 3 et 4 supprimée dans les sources locales et Overleaf FR/EN. Compilation FR sans erreur ni avertissement. Compilation EN non vérifiée.
- Figures 4 et 5 : espace avant chaque tableau réduit de 2 mm supplémentaires, en local et sur Overleaf FR/EN. Compilation FR sans erreur ni avertissement. Les deux paires restent chacune sur leur page. Compilation EN non vérifiée.
- Figures 4 et 5 : nouvel ajustement de 2 mm entre graphique et tableau, local et Overleaf FR/EN. Compilation FR sans erreur ni avertissement. Les paires occupent les pages consécutives 29 et 30 du PDF. Rendu EN non vérifié.
- Section 5.3 : sous-titre et passage « Informations restant à ajouter au tableau des profils » supprimés en local et sur Overleaf FR/EN. Compilation FR sans erreur ni avertissement. Compilation EN non vérifiée.
- Section 5.4 : comparaison principale conservée dans le tableau 6, référence renommée passif centré sans couverture, introduction à poids fixés sur 2 500 trajectoires distinctes des figures 4 et 5. Tableau des diagnostics complémentaires déplacé en annexe avec renvoi dans le commentaire. Sources locales et Overleaf FR/EN synchronisées. Compilation FR sans erreur ni avertissement. Rendu EN non vérifié.
- Section 5.3 : synthèse après le tableau 5 sur les compromis RMSE, ES et parcimonie des profils des tableaux 4 et 5, avec transition vers la section 5.4. Renvois automatiques vérifiés en FR. Sources locales et Overleaf FR/EN synchronisées. Compilation FR sans erreur ni avertissement. Rendu anglais non vérifié. Revoir les exemples chiffrés au renouvellement des exports.

- §5.3–5.4 (FR/EN) : le tableau de risque compare les huit profils C au passif centré sur les mêmes 2 500 trajectoires indépendantes. Les huit réduisent la RMSE et augmentent l’ES à 97,5 %. La figure et les diagnostics détaillés couvrent les quatre cas Lasso et Elastic Net. Sources synchronisées sur Overleaf ; compilation FR sans erreur ni avertissement, compilation EN non vérifiée.

- §5.4 (FR/EN) : l’introduction annonce la mesure de l’ampleur de la baisse de RMSE et de la hausse de l’ES à 97,5 % des profils C face au passif centré. Synchronisé sur Overleaf et compilation FR vérifiée.
§5.4 (FR/EN) : le tableau 6 est ancré avant son commentaire dans les sources locales et sur Overleaf.
§5.4 (FR/EN) : légende du tableau 6 raccourcie en local et sur Overleaf.
§5.4 (FR/EN) : figure de comparaison Lasso et Elastic Net retiree, car le tableau 6 couvre les huit profils. Retrait synchronise sur Overleaf.
§5.4 (FR/EN) : colonne gain RMSE / hausse ES du tableau 6, calculée à partir des valeurs non arrondies face au passif centré. Recalculer au renouvellement des exports. Sources locales et Overleaf synchronisées, compilation FR vérifiée.
§5.4 (FR/EN) : tableau 6 regroupé par univers selon la présentation du tableau 5. Sources locales et Overleaf synchronisées, compilation FR vérifiée.
§5.4 (FR/EN) : le commentaire du tableau 6 compare le meilleur ratio gain RMSE / hausse ES et le plus grand gain de RMSE, avec les tailles de portefeuille correspondantes. Sources locales et Overleaf synchronisées, compilation FR vérifiée.
§5.4 et annexe (FR/EN) : tableau 10 et son renvoi retirés. Les métriques figurent dans la comparaison générale du tableau 7, sur un autre échantillon. Sources locales et Overleaf synchronisées, compilation FR vérifiée.
§5.4 (FR/EN) : retrait du rappel sur le modèle Black–Scholes des trajectoires. Sources locales et Overleaf synchronisées, compilation FR vérifiée.

- Section 5.4 : ventilation de l’ES à 97,5 % par événements du contrat, en Monte Carlo standard à poids fixés sur l’échantillon du tableau 6. Export tail_contract_event_decomposition et figures tail_contract_events_fr/en pour les profils C Elastic Net. Dans le motif coupon, P = payé et M = manqué. Aperçu construit avec les parts déjà citées de l’expérience de 5.5. Après le prochain lancement, vérifier les totaux puis actualiser le visuel et le commentaire du rapport.
§5.4 : tableau 7 regroupé par univers et méthode en FR/EN. Les 30 lignes et leurs chiffres ont été conservés. Sources locales et Overleaf synchronisées, compilation FR vérifiée.

- À reprendre en fin de relecture — §5.4, « États à l’origine de la perte résiduelle de queue ». Après le prochain lancement du notebook principal, relire le commentaire et la figure 6 à partir de la décomposition de l’ES par rappel, barrière de protection et coupons manqués. Vérifier que le texte et le visuel renvoient à l’échantillon effectivement utilisé, puis aligner FR et EN.

- Tableau 7 (FR/EN) : la légende précise la définition de la RMSE pour les paniers A/B, les couvertures delta et le passif centré. Synchronisé sur Overleaf, compilation FR vérifiée.

- Tableau 7 (FR/EN) : légende raccourcie, en conservant les conventions de RMSE et la taille de l’échantillon. Synchronisé sur Overleaf, compilation FR vérifiée.

- Tableau 7 (FR/EN) : le commentaire analyse le conditionnement dans Full et la différence entre ES et perte maximale pour le delta quotidien. Sources locales et Overleaf synchronisées, compilation FR vérifiée.

- Tableau 7 (FR/EN) : retrait de la parenthèse A et B après paniers d’options. Compilation Overleaf FR vérifiée.

- Tableau 7 (FR/EN) : doublon sur le delta et le passif centré retiré de la légende. Compilation Overleaf FR vérifiée.

- Tableau 7 : analyse recentrée sur les références OLS, delta et le passif centré. Sources FR/EN synchronisées sur Overleaf ; compilation FR vérifiée.

- §5.5 : ouverture reformulée pour annoncer la comparaison de précision et identifier les portefeuilles de la sélection précédente. FR/EN synchronisés sur Overleaf, compilation FR vérifiée.

- Figure 7 (FR/EN) : largeur portée de 0,92 à 1,12 fois la largeur du texte, avec centrage. Synchronisé sur Overleaf, compilation FR vérifiée.

- §5.5 (FR/EN) : réécriture approuvée sur la cible ES, les deux calculs et la comparaison de précision par bootstrap. Diagnostics ESS déplacés dans l’annexe IS. Sources locales et Overleaf synchronisées ; compilation FR vérifiée.

- §5.4, États à l’origine de la perte résiduelle de queue : texte FR/EN et figure locale actualisés avec les exports du 16 novembre à 23:16, mêmes 2 500 trajectoires que le tableau 6. Synchronisation et compilation Overleaf en attente, navigateur intégré indisponible.

- Accès Overleaf rétabli. Passage sur les sources de l’ES et figures FR/EN transférés. Les fichiers tail_contract_events_fr/en.pdf sont à la racine du projet, sources locales alignées. Compilation FR : aucune erreur ni avertissement. Compilation EN non vérifiée.

- Figure 6 : présentation simplifiée dans le notebook, deux couleurs sans hachures, pourcentages directement sur les segments et rappel sous le graphique concernant les coupons manqués et le rappel anticipé. Le texte sous le graphique dépend des données et sera réévalué au prochain lancement. Figures FR/EN régénérées à partir du CSV existant, transférées sur Overleaf. Compilation FR : aucune erreur ni avertissement. Compilation EN non vérifiée.

- Figure 6 : introduction alignée sur le visuel simplifié en FR/EN. Le texte indique les critères examinés et la contribution nulle des catégories rappelées et sans coupon manqué sur cet échantillon. Sources locales et Overleaf synchronisées ; compilation FR vérifiée.

- §5.4 : tableau des effectifs ajouté et distinction explicitée entre part de l’échantillon et contribution à l’ES. La lecture des 100 %, 64,4 % et 35,6 % est expliquée. Légende de la figure adaptée. FR/EN synchronisés sur Overleaf ; compilation FR sans erreur ni avertissement. L’ajout du tableau renumérote les suivants.

- Tableau des événements : cinq catégories croisées observées (rappel/maturité, barrière, coupon manqué) et deux colonnes de contributions à l’ES ajoutées en FR/EN. Parmi les rappels, 9 trajectoires ont au moins un coupon manqué, contribution ES nulle. Corrige la précédente simplification qui regroupait tous les rappels. Sources locales et Overleaf synchronisées ; compilation FR vérifiée.

- Décomposition de l’ES : figure retirée au profit du tableau croisé. Analyse des contributions au regard des fréquences, du changement de répartition avec Full et du rôle conjoint des coupons manqués et de la maturité. FR/EN synchronisés sur Overleaf, compilation FR vérifiée. Les figures suivantes sont renumérotées.

- Tableau croisé : légende supprimée et deux phrases répétant les effectifs retirées du commentaire, FR/EN local et Overleaf. Compteur de tableau conservé pour les renvois. Compilation FR vérifiée.

- Tableau croisé : numéro 7 rendu visible avec une légende courte, suite à la suppression de sa légende longue. FR/EN synchronisés ; compilation FR vérifiée.

- Diagnostic ES enrichi : cube de huit catégories avec effectifs nuls explicites, risque propre à chaque groupe, contributions globales et comparaisons à deux critères fixés. Export par trajectoire et contributions signées par date, dont la somme reconstitue l’ES globale. Les parts coupons/remboursement du résidu demandent une convention d’affectation des flux du portefeuille et ne sont pas calculées. Protocole et limites d’effectifs explicités FR/EN sur Overleaf, résultats nouveaux en attente du prochain lancement. Compilation FR vérifiée.

- §5.5 : définition répétée de l’ES et phrase sur la sélection précédente retirées en FR/EN local et Overleaf. Compilation FR vérifiée.

- §5.5 : largeur des intervalles bootstrap réduite de 21,4 % (Calls + Puts) et 18,0 % (Full), calculée sur importance_ci_table du run 2026-11-15_200419_fast, source de la figure. Commentaire FR/EN synchronisé sur Overleaf ; compilation FR vérifiée.

- Tableau 8 : placement ancré après le paragraphe introductif de la comparaison des références, FR/EN local et Overleaf. Compilation FR vérifiée.

- §5.5 : commentaire généralisé aux 24 profils de la figure, 22 intervalles réduits de 1,5 à 46,9 %, deux élargissements de 10,0 et 3,9 %. Phrase sur les poids raccourcie. Données de importance_ci_table du run 2026-11-15_200419_fast. FR/EN local et Overleaf synchronisés ; compilation FR vérifiée.

- EN PAUSE à la demande de l’utilisateur : « États à l’origine de la perte résiduelle de queue ». Reprendre après son prochain lancement du notebook, avec les exports des diagnostics par groupe, des comparaisons à critères fixés et des contributions par date. Le texte actuel reste en place en attendant la relecture de ces résultats.

- §5.4, pertes résiduelles de queue : pause levée après lancement utilisateur, exports du 17/11 à 15:01 intégrés en FR/EN local et Overleaf. Tableau croisé conservé ; ajout du risque propre aux groupes et des contributions signées par date. Vérifiés : 2 500 trajectoires par univers, contributions datées reconstituant l’ES globale. Analyse des critères à caractéristiques fixées, groupes absents et groupe de neuf trajectoires. La séparation coupons/remboursement reste une limite explicite. Deux tableaux supplémentaires renumérotent les suivants. Compilation FR sans erreur ni avertissement ; EN non vérifiée.

- Audit autorisé de la section des pertes de queue : chiffres contrôlés dans les nouveaux exports et additivité par échéance vérifiée. Explication des parts globales et du risque propre aux groupes renforcée, en-têtes harmonisés, commentaires chiffrés redondants retirés. Clarification de la différence entre hausse de part relative et hausse de risque propre. Décomposition par échéance expliquée avant son tableau, reliée aux compensations permises par B et au financement. Limites conservées pour les neuf trajectoires, groupes absents et attribution coupons/remboursement. FR/EN local et Overleaf synchronisés, compilation FR sans erreur ni avertissement ; compilation EN non vérifiée.

- Refonte intégrale autorisée de « États à l’origine de la perte résiduelle de queue » : trois tableaux de paires témoin/comparaison, un critère variable et deux fixes. Douze paires explicites dont cinq observables et sept incomplètes. RMSE, ES et effectifs des deux côtés, groupes absents visibles. Analyse spécifique à chaque critère puis contributions par date. Notebook enrichi pour afficher les comparaisons par facteur. Aucun nouveau run lancé. FR/EN local et Overleaf synchronisés ; compilation FR sans erreur ni avertissement, EN non vérifiée. Un tableau supplémentaire renumérote les suivants.

- Présentation des comparaisons : flèches remplacées par deux lignes verticales par paire, critères fixes en tête du groupe, colonnes regroupées par univers. Cinq paires observables conservées, sept incomplètes signalées dans le texte ; groupe de neuf trajectoires marqué. Correction de la correspondance entre les critères coupon/barrière et leurs tableaux. FR/EN synchronisés sur Overleaf, compilation FR sans erreur ni avertissement ; EN non vérifiée.

- Introduction des pertes de queue : définition répétée du résidu supprimée, introduction réunie au paragraphe suivant en FR/EN local et Overleaf. Compilation FR vérifiée.

- Introduction : phrase sur le critère variable retirée, remplacée par « Les trois critères de comparaison sont ». FR/EN local et Overleaf synchronisés, compilation FR vérifiée.

- Comparaisons par paires : deux phrases décrivant la présentation des lignes retirées. FR/EN local et Overleaf synchronisés, compilation FR vérifiée.

- Phrases sur les sept paires incomplètes et le caractère descriptif retirées à la demande de l’utilisateur. Notebook : évaluation indépendante dédiée de 25 000 trajectoires par univers, en lots de 2 500, profils C Elastic Net figés, export des groupes, paires et trajectoires sous noms large_sample distincts. Ne garantit pas que les catégories rares seront observées. Aucun run lancé. FR/EN Overleaf synchronisés et compilation FR vérifiée.

- §5.5 : niveau de 95 % des intervalles bootstrap précisé, bornes aux quantiles 2,5 % et 97,5 % des ES rééchantillonnées, coefficients fixés. Légende FR/EN actualisée, Overleaf synchronisé, compilation FR vérifiée.

- §5.7 réécrite après audit : synthèse des comparaisons aux références delta, des arbitrages RMSE/ES/parcimonie, des compensations temporelles et des rôles distincts de l’IS et de la contrainte ES. Procédure transférable rappelée. FR/EN local et Overleaf synchronisés ; compilation FR sans erreur ni avertissement.

- Section des pertes de queue entièrement actualisée sur les exports large_sample du 17/11 à 17:12, 25 000 trajectoires par univers. Sept comparaisons observables : 2 rappel/maturité, 3 coupons, 2 barrière. Nouveau groupe de dix maturités avec franchissement sans coupon manqué ; aucun rappel avec franchissement. ES globale 10,0046 Calls + Puts et 7,9512 Full, parts sans franchissement 52,7 % et 66,6 %. Ancien diagnostic par date à 2 500 trajectoires retiré de cette section pour éviter le mélange d’échantillons, exports conservés. FR/EN local et Overleaf synchronisés, compilation FR sans erreur ni avertissement ; EN non vérifiée.


## Audit de la section 5 avant gel — 17 novembre 2026

Audit demandé sans autorisation supplémentaire de modification des passages relus. Aucun texte du rapport modifié durant cet audit.

### Vérifications réalisées

- Comparaison automatique des 30 lignes du tableau global avec unified_benchmark_table.csv, FR et EN : aucune différence au niveau des arrondis affichés.
- Huit ratios gain RMSE / hausse ES recalculés à partir des valeurs non arrondies : tous corrects.
- Valeurs de la comparaison A/B contrôlées dans method_objective_tradeoff_table.csv.
- Profils C : RMSE de validation et nombre total de coefficients retrouvés dans stable_profiles_table.csv. Alpha du tableau initial correspond à alpha relatif, à distinguer de alpha absolu.
- Décomposition à 25 000 trajectoires : six catégories observées, sept paires observables, absence de rappels avec barrière franchie. Dix maturités avec barrière franchie sans coupon manqué et 80 rappels avec coupon manqué. ES globale recalculée par somme des contributions, 10,004556 Calls + Puts et 7,951234 Full. Parts sans franchissement 52,664 % et 66,554 %.
- Résultats bootstrap : 22 réductions sur 24, de 1,5 à 46,9 %, deux élargissements 10,0 et 3,9 %, tous les intervalles se chevauchent. Source conservée 2026-11-15_200419_fast.
- Renvois de section 5 vérifiés, y compris les labels passés aux macros de figures : aucun absent. Labels et structure des tableaux identiques FR/EN.
- La compilation anglaise et le rendu visuel complet des deux PDF restent non vérifiés dans cet audit.

### Points de fond à corriger avant gel

1. §5.5 — provenance de la figure IS devenue implicite. Le texte ne dit plus que la sélection des portefeuilles diffère de celle utilisée en 5.3–5.4. Rétablir une phrase courte qui distingue les deux ensembles de résultats, sans date de production.
2. §5.6 — budgets de contrainte non explicités : 10 points Calls + Puts et 5 points Full, à distinguer du seuil commun de 10 points utilisé dans les exports. Le lecteur ne peut pas interpréter le respect du budget sans ces valeurs.
3. §5.6 — attribution excessive à la contrainte ES. Les ES de calibration sans contrainte sont 3,90 et 9,41 pour Calls + Puts (budget 10), 4,07 et 9,03 pour Full (budget 5). Seule la seconde calibration Full dépasse son budget. Le solveur change aussi : L-BFGS-B sans contrainte, SLSQP avec contrainte. Les gains des autres cas ne prouvent donc pas l'effet d'une contrainte active. Pour Full, second échantillon, ES de calibration ramenée à 5,00 ; ES d'évaluation 6,92, donc budget de calibration dépassé en évaluation. C'est l'exemple le plus interprétable.
4. §5.7 — décomposition par échéance mentionnée alors que son tableau a été retiré du diagnostic actualisé à 25 000 trajectoires. Rattacher ce constat explicitement à la comparaison A/B en 5.2, ou reprendre la décomposition sur le grand échantillon avant de la présenter.

### Clarifications et allègements

5. §5.3 — « Les profils L0 sont beaucoup plus petits mais présentent une erreur de validation nettement supérieure » est trop général. Dans Calls + Puts, L0 et Lasso ont chacun deux coefficients actifs, avec RMSE 3,651 et 3,576. Réserver le commentaire au compromis observé dans Full ou préciser le comparateur.
6. §5.3 — tableau initial : en-tête alpha à préciser comme alpha relatif, pour être cohérent avec les tableaux de profils qui l'indiquent. Les valeurs numériques correspondent à cette échelle.
7. §5.5 — « les deux méthodes estiment cette même quantité » suit la définition d'une perte par trajectoire. Remplacer par « les deux méthodes estiment l'ES à 97,5 % du même portefeuille ». Fixer la politique conserve la règle conditionnelle, qui peut changer de panier aux dates prévues.
8. §5.4 — définition du ratio RMSE/ES uniquement dans son commentaire et l'en-tête. Une courte définition de son numérateur et dénominateur permettrait une lecture autonome. Conserver la référence au passif centré et la base en points.
9. §5.4 — les tableaux par groupes donnent le risque conditionnel ; les parts globales utilisent une queue différente pour chaque portefeuille. Le texte le distingue déjà, à conserver. Le diagnostic ne fournit aucune attribution additive de la perte aux événements ou aux flux coupons/remboursement.
10. §5.6 — « L'expérience est utile car… » et « Une politique promue devrait… » reprennent du suivi de projet et alourdissent la conclusion. Préférer la limite directement observable sur le budget et l'évaluation indépendante.
11. Typographie FR : tableaux de sélection et de risque mêlent virgules et points décimaux. Harmoniser les cellules numériques FR, sans toucher aux commandes ni aux identifiants.
12. Tableaux de comparaison conditionnelle : conserver les petits effectifs signalés. Ne pas remplir de valeurs estimées les rappels avec barrière franchie qui restent absents.
13. Provenance des figures : PDFs français locaux de la comparaison A/B et du 2x2 différents en octets des exports latest, pouvant résulter de traductions ou d'une mise en forme. Le hash ne prouve pas une divergence numérique. Vérifier le visuel rendu et sa source avant le gel final.

### Décision de gel

Gel éditorial à différer jusqu'aux corrections 1–7 et à la vérification visuelle des PDF FR/EN. Les exécutions finales et l'actualisation de leurs exports restent planifiées en fin de relecture, conformément aux instructions utilisateur.

- Audit section 5, points 2 à 6 autorisés et appliqués FR/EN : budgets ES, cible et provenance IS, interprétation L0, alpha relatif, rattachement du constat temporel à 5.2. Point 1 en discussion : conserver les chiffres et expliciter le changement L-BFGS-B / SLSQP ; aucune modification correspondante faite. Sources locales et Overleaf synchronisées, compilation FR sans erreur ni avertissement.

- Audit section 5, point 1 autorisé : chiffres conservés, formulation « procédure contrainte », solveurs L-BFGS-B et SLSQP explicités. Distinction entre les trois calibrations déjà sous budget et le second cas Full contraint ; dépassement du budget en évaluation indiqué. FR/EN local et Overleaf synchronisés ; compilation FR sans erreur ni avertissement.

- §6.5 simplifiée sur autorisation : titre Besoins de financement, deux paragraphes conservant résultats, échantillon et limites utiles. Récursion sans renvoi supprimée. FR/EN local et Overleaf synchronisés, compilation FR sans erreur ni avertissement.

- §6.6 : affirmation générale sur le faible effectif retirée. Réserves et notes répétées sur les groupes rares allégées dans 5.4, explication de la queue des groupes de dix et 80 trajectoires conservée. Le diagnostic dédié reste fixé à 25 000 trajectoires même en REPORT ; revoir son paramétrage avant les runs finaux si un agrandissement est souhaité. FR/EN synchronisés, compilation FR vérifiée.

- Tableau 12 sur la validité : placement ancré dans sa sous-section en FR/EN local et Overleaf, compilation FR vérifiée.

- Préparation des runs finaux : décision à transcrire dans le notebook sur 25 000 trajectoires pour le diagnostic contractuel en FAST et 100 000 en REPORT. Avant lancement, vérifier la promotion du REPORT hyperparamètres, décider si l’IS doit aussi être évalué à politique fixée lorsque le pilote retient le Monte Carlo standard, et consolider les exports et contrôles de provenance du diagnostic contractuel. Le test final réservé relève d’une décision distincte du passage en mode REPORT.

- §6.7 : en-tête « Poursuite possible » / « Possible follow-up » appliqué aux sources locales. Synchronisation et compilation Overleaf en attente : navigateur intégré indisponible.

- Préparation finale, point 1 appliqué : diagnostic contractuel à 100 000 trajectoires par univers en REPORT et 25 000 en FAST, par lots de 2 500. L’export REPORT vérifie l’effectif de chaque univers et la configuration enregistre le budget. La décision sur l’IS à politique fixée reste ouverte. Aucun run lancé.

- Conclusion FR/EN : liste des étapes immédiates remplacée par le bilan des travaux réalisés et les prolongements validés. Sources locales vérifiées. Synchronisation et compilation Overleaf en attente, navigateur intégré indisponible.

## Audit de la partie 6 avant gel

- 6.1 — Raccourcir la liste de conditions en une distinction entre les diagnostics effectivement mesurés dans l’étude et les conditions d’exécution à caractériser. Éviter de reprendre les conclusions de 5.7.
- 6.2 — Conserver l’apport principal : comparer conditionnement, dictionnaire et parcimonie. Présenter la procédure comme adaptable via le payoff, le modèle, l’état, les instruments et le plan d’évaluation. Retirer l’attribution de régions du payoff à des formes convexes ou digitales, que les tableaux ne démontrent pas directement. Simplifier ou supprimer le catalogue d’usages génériques.
- 6.3 — Remplacer « au minimum » et « devrait » par des prolongements précis. Distinguer les hypothèses de volatilité constante de la sensibilité aux paramètres, dont le risque est distinct. Remplacer « sous-estime » par une description de ce que l’évaluation sous Q mesure. Indiquer que la barrière est suivie sur les jours de semaine simulés, sans calendrier de jours fériés. Garder le risque de grille et déplacer la convention de règlement vers 6.5, où elle figure déjà.
- 6.4 — Retenir la différence entre nombre de positions et coût d’exécution, ainsi que le compromis lié à la largeur des spreads. Raccourcir l’inventaire des données nécessaires.
- 6.5 — Valeurs vérifiées dans funding_summary.csv : 250 trajectoires, 4,08 pour Calls + Puts, 4,03 pour Full avec digitales, 4,07 pour Full avec spreads. Conserver la taille et les limites de comparabilité. Actualiser les valeurs depuis le REPORT.
- 6.6 — Fusionner l’ouverture et l’incertitude de sélection. Distinguer bootstrap à politique fixée, stabilité après recalibration et biais de sélection. Rappeler que le test réservé reste à évaluer. Rattacher « Objectifs multiples » à 5.3 si le passage est conservé, ou le retirer ici. Traiter une seule fois la dépendance au modèle entre 6.3 et 6.6.
- 6.7 — Raccourcir le tableau 12 aux limites non couvertes ailleurs, ou le retirer si les paragraphes reprennent son contenu utile. Si conservé, remplacer « Surapprentissage » par « Biais de sélection », expliciter le statut du test réservé et supprimer le renvoi générique à un échantillon plus grand. Vérifier la terminologie FR/EN ligne par ligne : « mise en œuvre de Full avec digitales théoriques » est plus précis que « fausse négociabilité », et le risque de coûts mal estimés peut aller dans les deux sens.

Sources locales FR et EN auditées. Aucun changement éditorial appliqué au rapport à ce stade. À vérifier avant gel final : compilation et rendu des deux PDF après intégration des changements approuvés, synchronisation de la conclusion et actualisation des chiffres REPORT.

- Partie 6 : sept corrections autorisées intégrées en FR/EN local. Tableau 12 supprimé, audit chronologique et convergence repris en 6.6. Les prolongements de la conclusion incluent une revue indépendante des décisions et des clauses contractuelles, ainsi que des essais de solveurs et de tolérances. Synchronisation et compilation Overleaf en attente : navigateur intégré indisponible.

- Synchronisation Overleaf rétablie : partie 6 et prolongements de la conclusion vérifiés dans les deux sources en ligne. Le français reste le document principal et compile sans erreur ni avertissement. Compilation EN non vérifiée.

## Audit de la conclusion et des annexes

- Conclusion : raccourcir les redites après 5.7, nommer le profil RE et le comparateur C pour Elastic Net. Vérifié sur l’évaluation commune : l’ES baisse dans les deux univers, la RMSE augmente et les nombres de coefficients passent de 16 à 10 et de 19 à 31. Conserver les prolongements validés.
- Annexe A : clarifier le versement unique du coupon d’observation et les inégalités inclusives de chaque seuil. Code produit vérifié.
- Annexe B : remplacer la prescription d’élargir la grille par la limite d’interprétation d’un résultat en bord de grille. Ajouter un renvoi commenté aux deux figures de queue, distinctes de la sélection principale.
- Annexe C : six lignes numériques vérifiées dans les exports statique et conditionnel. Remplacer « test » par « évaluation » pour distinguer du test final réservé. La comparaison des dictionnaires statiques doit préciser une pénalisation commune, par exemple Ridge.
- Annexe D : distinguer le symbole du mélange du niveau de confiance de l’ES. Retirer le détour sur la queue à 99 % si elle n’est pas commentée. Préciser que les trois figures de sélection du mélange relèvent de l’étude d’hyperparamètres et que la figure 5.5 évalue des politiques fixées.
- Annexe E : mettre la provenance à jour après les REPORT. Le manifeste principal actuel identifie 2026-11-17_162245_fast, distinct du principal cité dans l’annexe et de la source IS de 5.5. Le diagnostic contractuel a son propre échantillon. Conserver les identifiants techniques dans le suivi de production.
- Annexe F : conserver les formules, expliciter l’écart au prix de référence et présenter l’objectif comme une extension à évaluer.
- Audit des sources locales FR/EN. Propositions à valider avant édition. Rendu des figures et compilation des deux PDF à contrôler après les exports finaux.

- Conclusion et annexes A à F : corrections validées intégrées et synchronisées FR/EN. Profil RE identifié, logique du payoff clarifiée, terminologie d’évaluation corrigée en annexe C, notation IS dissociée du niveau de confiance, provenance renvoyée aux manifestes, formules de coûts conservées et expliquées. Compilation Overleaf FR sans erreur ni avertissement. Compilation EN et actualisation chiffrée après les REPORT à vérifier.

## Audit transversal de la V1

- Les deux sources locales ont un bloc de résumé incomplet. Les résumés d’Overleaf sont complets. Récupérer les blocs Overleaf dans les sources locales après validation, avant tout transfert global. La zone précède la section 4.3.
- En 5.3, Overleaf charge les tableaux des profils depuis des fichiers séparés. Les sources locales les contiennent directement. Vérifier les quatre tableaux FR/EN issus des nouveaux exports et conserver des mises à jour ciblées.
- En 4.4, remplacer le renvoi aux trois régimes par la description du diagnostic croisé de 5.4 (issue du contrat, coupon manqué et barrière de protection).
- Au prochain REPORT, harmoniser le périmètre des chiffres du résumé avec le tableau des huit profils C, ou identifier explicitement le sous-ensemble. Vérifier la provenance de l’expérience IS à poids fixés, le résultat du pilote, les effectifs du diagnostic de queue et les réglages retenus. Conserver les provenances distinctes si les expériences reposent sur des exports différents.
- Dans le notebook principal, la clé standard_risk du manifeste annonce 20500, alors que l’appel d’évaluation standard utilise 10500. Aligner la métadonnée sur l’appel et documenter les graines du diagnostic de queue (210500 + indice du lot). Mettre aussi à jour le suivi de production, qui évoque encore un tableau de 15 lignes.
- Les contrôles automatiques locaux couvrent les renvois, les clés bibliographiques et les chemins des figures. Vérifier les journaux des deux compilations et les pages sensibles sur Overleaf lors de la validation des exports finaux.

Le 17 novembre, les blocs de résumé locaux ont été restaurés depuis Overleaf. Le renvoi de 4.4 a été corrigé en français et en anglais en local et sur Overleaf. La graine standard_risk du notebook a été alignée sur l’appel d’évaluation (10500), sans changement de simulation. La structure des tableaux de 5.3 relève du suivi de production.
