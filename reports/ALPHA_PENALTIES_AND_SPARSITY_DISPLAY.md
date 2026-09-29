# Comparaison des pénalités et lisibilité de la parcimonie

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | La recherche d’alpha doit comparer plusieurs normes sur la famille full. |
| **Problème** | Traiter correctement L2 et rendre la parcimonie lisible. |
| **Méthode** | Chemins communs L1, L2 et Elastic Net avec diagnostics adaptés. |
| **Modifications** | Ajout des comparaisons et d’un affichage spécifique à Ridge. |
| **Résultats** | Les pénalités sont comparées sans attribuer artificiellement des zéros à L2. |


Date de dernière validation : 19 août 2026

## 1. Périmètre autorisé

Cette étape réalise uniquement les deux évolutions validées :

1. étendre la recherche d'alpha de L1 à L2 et Elastic Net ;
2. rendre les diagnostics de parcimonie du notebook plus lisibles.

La recherche du `l1_ratio` n'est pas implémentée. Elastic Net utilise un ratio
fixe égal à `0,5`. Aucun alpha n'est sélectionné et le test final reste fermé.

## 2. Comparaison des trois pénalités

Le benchmark payoff pathwise simule désormais le dataset une seule fois, puis
résout trois chemins sur exactement les mêmes trajectoires et le même split :

- L1 ;
- L2 ;
- Elastic Net avec `l1_ratio = 0,5`.

La recherche du notebook porte désormais exclusivement sur la famille `full` :
cash, calls, puts et options binaires. Les familles `calls` et `calls_puts` ne
sont pas explorées dans cette section.

Chaque chemin utilise 25 valeurs d'alpha dans le notebook. Les données sont
séparées en 60 % train, 20 % validation et 20 % test final réservé. La table ne
contient aucune colonne de métrique de test.

### L1 et Elastic Net

Leur référence est `alpha_max`, valeur capable d'annuler toutes les options
pénalisées. La grille descend jusqu'à `0,001 × alpha_max`.

### L2

Ridge ne crée généralement pas de poids exactement nuls. Son échelle est donc
fondée sur :

```text
alpha_reference = lambda_max(X_options.T X_options / n)
```

après normalisation des colonnes et exclusion du cash de la pénalisation. La
grille couvre `100 × alpha_reference` à `0,0001 × alpha_reference`.

La colonne `alpha_relative = alpha / alpha_reference` facilite la lecture des
trois chemins sans prétendre rendre leurs pénalités mathématiquement identiques.

L2 n'est plus affiché sur les graphiques de nombre d'options actives, car Ridge
réduit les poids sans les annuler. Une figure dédiée affiche à la place le poids
brut, le poids maximal absolu et la concentration top 5. L'échelle logarithmique
existante d'alpha relatif est conservée sans transformation supplémentaire.

## 3. Sélection de plusieurs candidats

La table brute des 75 solutions est conservée pour l'audit. Une table annotée
ajoute un statut explicite et une table séparée contient uniquement les
candidats satisfaisant les quatre règles autorisées :

1. convergence obligatoire ;
2. au moins 2 options actives ;
3. au plus 100 options actives ;
4. absence de domination au sein de la même pénalité.

La domination n'est jamais calculée entre deux pénalités différentes. L1, L2
et Elastic Net conservent donc chacun leur propre frontière admissible. Plusieurs
solutions peuvent rester candidates et sont sérialisées sous forme de politiques
contenant famille, pénalité, alpha absolu, alpha relatif, ratio éventuel, nombre
d'options actives et RMSE de validation.

## 4. Affichage de la parcimonie

Les dictionnaires techniques bruts restent présents dans les résultats Python,
mais ne sont plus affichés directement dans le notebook. Ils sont remplacés par :

- une synthèse indiquant options actives, taux d'activation, positions longues
  et courtes, poids brut, poids net et concentration top 5 ;
- un tableau en français organisé par sélection, direction, exposition, risque,
  concentration et cash ;
- une explication associée à chaque mesure ;
- une vue compacte par date et état pour le benchmark conditionnel.

Les poids bruts et nets sont explicitement présentés comme des nombres de
contrats/poids, et non comme des expositions monétaires. L'exposition monétaire
reste une étape future.

## 5. Notebook

La section alpha affiche :

- les trois pénalités et le ratio Elastic Net fixe ;
- le split et le statut du test final ;
- le type et la valeur de la référence d'alpha de chaque pénalité ;
- les filtres, les motifs de rejet, les candidats par pénalité et les politiques
  réutilisables ;
- un graphique de RMSE pour les trois pénalités ;
- deux graphiques de parcimonie réservés à L1 et Elastic Net ;
- trois graphiques L2 dédiés à la réduction et à la concentration des poids.

Les anciennes sorties enregistrées des cellules modifiées ont été retirées afin
qu'elles ne contredisent pas le nouveau code. Le solveur historique global reste
`SOLVER = "legacy"` pour les benchmarks existants.

## 6. Validation

- 71 tests réussis sur 71 ;
- 16 fichiers Python syntaxiquement valides ;
- 2 notebooks JSON valides ;
- contrôle Ruff réussi sur les fichiers modifiés ;
- tests dédiés au solveur L2, à son échelle spectrale, à la comparaison des
  pénalités, à la fermeture du test final et aux nouveaux affichages.

Le scénario complet du notebook n'est pas exécuté automatiquement par la suite
de tests, car il demande 75 optimisations sur une base pathwise complète. Des
tests réduits exécutent toutefois les trois pénalités de bout en bout.

## 7. Éléments volontairement reportés

- recherche du `l1_ratio` Elastic Net ;
- choix éventuel d'un candidat unique ;
- réentraînement sur train + validation ;
- ouverture du test final ;
- coûts de transaction, bid-ask et slippage ;
- exposition monétaire ;
- extension des chemins d'alpha aux quatre autres benchmarks.
