# Vérification fonctionnelle du projet

## Résumé rapide

| Rubrique | Synthèse |
|---|---|
| **Contexte** | Plusieurs erreurs de dates et d’imports avaient affecté le notebook. |
| **Problème** | Vérifier le fonctionnement du package et des benchmarks concernés. |
| **Méthode** | Contrôles d’import, syntaxe, calendriers et tests automatisés. |
| **Modifications** | Ajout de protections de régression sur les fonctions conditionnelles. |
| **Résultats** | Le rapport consigne l’état fonctionnel observé à sa date de validation. |


Date de vérification : 8 août 2026

## Périmètre vérifié

Cette vérification porte sur le package Python, les imports utilisés par les
notebooks, les conventions de calendrier et le benchmark de réplication
conditionnel à l'origine des dernières erreurs.

## Résultats

- installation Python cohérente : `pip check` ne détecte aucune dépendance cassée ;
- syntaxe valide pour les 13 fichiers Python suivis par le script de validation ;
- structure JSON valide pour les deux notebooks ;
- suite automatique : **36 tests réussis sur 36** ;
- les sept fonctions importées depuis `replication.semi_static` sont présentes ;
- le rechargement du module restaure correctement
  `conditional_features_on_path` dans un noyau ayant conservé un ancien module ;
- les neuf combinaisons `famille × pénalité` du benchmark conditionnel passent :
  `calls`, `calls_puts`, `full` avec `l2`, `l1` et `elastic_net` ;
- le scénario signalé avec **2 000 trajectoires**, `calls`, `l2`, séparation
  finale par barrière et `min_state_paths=20` termine correctement ;
- les dates obtenues sont le 22 septembre 2026, le 22 décembre 2026,
  le 22 mars 2027 et le 22 juin 2027 ;
- les trois courbes produites contiennent quatre lignes et aucune valeur manquante.

## Protection contre la régression

Le test du pipeline conditionnel importe et contrôle maintenant explicitement
`conditional_features_on_path` et `predict_conditional_path_data`. Une future
suppression ou un futur déplacement incomplet de ces fonctions fera donc échouer
la validation automatique.

## Commande de validation

Depuis la racine du projet :

```powershell
.\.venv\Scripts\python.exe scripts\validate.py
```

## Points ne bloquant pas l'exécution

- Le notebook contient encore des sorties historiques correspondant à d'anciennes
  erreurs. Elles ne sont pas réexécutées et ne décrivent pas l'état actuel du code.
- Ruff signale encore des problèmes de présentation et quelques imports inutilisés.
  Ils ne provoquent pas les erreurs fonctionnelles observées, mais constituent une
  étape séparée de nettoyage du code.
- Les cellules utilisant des données de marché externes dépendent par nature de la
  disponibilité du fournisseur et n'ont pas été utilisées pour valider le moteur
  local de réplication.
