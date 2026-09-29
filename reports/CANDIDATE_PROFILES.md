# Sélection de trois profils par pénalité

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | De nombreux alphas peuvent survivre aux premiers filtres. |
| **Problème** | Conserver des choix distincts sans fixer arbitrairement leur nombre d’actifs. |
| **Méthode** | Performance statique, Pareto, doublons puis trois rôles économiques. |
| **Modifications** | Ajout des profils performance, compromis et parcimonie par pénalité. |
| **Résultats** | Une courte liste interprétable alimente les étapes de stabilité et de risque. |


Date d'intégration : 19 août 2026

## Objectif

Réduire la frontière de candidats de chaque pénalité à trois lectures
économiquement compréhensibles, sans utiliser le test final et sans imposer
arbitrairement un nombre d'instruments dans l'optimisation :

1. **performance** : RMSE de validation minimale ;
2. **compromis** : meilleur équilibre normalisé entre RMSE et nombre d'options ;
3. **parcimonie** : nombre d'options actives minimal.

La sélection est effectuée séparément pour L1, L2 et Elastic Net. Une pénalité
ne peut jamais dominer ou éliminer un candidat d'une autre pénalité.

## Chaîne de filtrage

Les filtres sont appliqués dans cet ordre :

1. convergence du solveur ;
2. entre 2 et 100 options actives ;
3. frontière de Pareto calculée dans la pénalité ;
4. filtre de performance statique ;
5. suppression des doublons stricts ;
6. suppression des doublons quasi stricts ;
7. attribution des trois profils.

Le bloc de test de 20 % conserve le statut `reserved_not_evaluated` pendant
toute cette chaîne.

## Filtre de performance statique

Le meilleur candidat de chaque pénalité sert de référence. Pour chaque autre
candidat, 2 000 rééchantillonnages appariés du bloc de validation mesurent :

```text
différence = RMSE candidat - RMSE référence
```

La graine du bootstrap est `20260819`. Le candidat n'est rejeté que si la borne
basse unilatérale à 95 % de cette différence est strictement positive. Une
différence non démontrée reste admissible ; l'égalité numérique avec le meilleur
n'est donc pas exigée.

Les colonnes d'audit sont :

- `performance_reference_alpha` ;
- `rmse_difference_vs_best` ;
- `rmse_difference_ci_lower` et `rmse_difference_ci_upper` ;
- `passes_static_performance` ;
- `is_candidate_after_performance`.

## Doublons stricts et quasi stricts

Un doublon strict possède le même support, les mêmes poids et les mêmes
prédictions de validation avec `rtol=1e-8` et `atol=1e-10`.

Un quasi-doublon doit simultanément respecter :

- Jaccard des supports supérieur ou égal à 95 % ;
- distance relative entre les poids inférieure ou égale à 5 % ;
- performance statistiquement indiscernable selon le filtre précédent.

Le représentant est choisi par coût lorsque celui-ci sera disponible. En son
absence, la priorité est : moins d'options, RMSE plus faible, puis alpha relatif
plus élevé.

`duplicate_report` liste chaque suppression avec pénalité, type de doublon,
alpha conservé, alpha supprimé, nombres d'options, RMSE, Jaccard, distance des
poids et justification. Une table vide signifie explicitement qu'aucun doublon
n'a été trouvé ; elle conserve néanmoins toutes ses colonnes.

## Définition des profils

### Performance

Le candidat admissible de plus faible RMSE de validation. En cas d'égalité, le
plus parcimonieux puis l'alpha relatif le plus élevé sont préférés.

### Parcimonie

Après attribution du profil performance, le candidat non encore attribué
utilisant le moins d'options. En cas d'égalité, la RMSE puis l'alpha relatif
départagent les solutions. Cette convention évite de présenter deux fois la
même solution lorsque des alternatives admissibles existent.

### Compromis

Dans chaque pénalité, la RMSE et le nombre d'options sont ramenés sur `[0, 1]`.
Le score vaut :

```text
sqrt(RMSE_normalisée² + complexité_normalisée²)
```

Après attribution des profils performance et parcimonie, le profil de compromis
minimise cette distance parmi les candidats non encore attribués. Il ne mélange
aucune unité monétaire à ce stade. L'ordre d'attribution rend prioritaires les
deux extrêmes faciles à interpréter, puis réserve le troisième rôle au meilleur
compromis encore disponible.

## Moins de trois candidats distincts

Les profils sont rendus distincts lorsque le vivier le permet. S'il reste un ou
deux candidats, un même candidat peut remplir plusieurs rôles et
`profile_reuses_candidate=True` le signale. S'il n'existe aucun candidat après
les filtres, aucune solution n'est inventée.

La table `profile_coverage` distingue :

- `three_distinct_profiles` ;
- `profiles_reuse_candidates` ;
- `no_candidate_after_filters`.

Cette règle est importante pour L2 : Ridge ne crée généralement pas de zéros
exacts et peut donc ne laisser aucun candidat sous la limite de 100 options.

## Sorties réutilisables

- `table` : toutes les solutions et tous les statuts d'audit ;
- `candidates` : représentants admissibles après performance et doublons ;
- `candidate_policies` : tous ces représentants sérialisés ;
- `profiles` : les trois rôles par pénalité ;
- `profile_policies` : profils sérialisés avec `family` ;
- `profile_coverage` : contrôle de complétude ;
- `duplicate_report` : liste détaillée des doublons supprimés.

## Limites et suite

- Les trois profils ne sont pas encore départagés par le test final.
- Le profil de compromis ne contient pas encore de coût de transaction.
- La stabilité multi-graines sur dix calibrations est désormais implémentée.
- Les scénarios yfinance et OTC enrichissent les profils sans remplacer
  silencieusement les données manquantes.
- La comparaison coût/réduction de risque utilise l'Expected Shortfall à 97,5 %.
