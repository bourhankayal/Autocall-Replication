# Autocall Replication

Projet de recherche consacré au pricing Monte-Carlo et à la réplication d'un autocall mono-sous-jacent.

## Où trouver quoi ?

| Je cherche… | Dossier ou fichier |
|---|---|
| La définition exacte du produit | [`docs/TERM_SHEET.md`](docs/TERM_SHEET.md) |
| Les résultats et rapports | [`reports/`](reports/) |
| Les PDF de référence mis à jour manuellement | [`output/pdf/`](output/pdf/) |
| Le dernier export structuré du notebook | [`output/latest/`](output/latest/) |
| L'historique daté des exécutions | [`output/runs/`](output/runs/) |
| Les notebooks d'exploration | [`notebooks/`](notebooks/) |
| La feuille de route | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| Les instructions d'installation | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| Le moteur Python | [`src/autocall_replication/`](src/autocall_replication/) |
| Les tests automatiques | [`tests/`](tests/) |
| Les commandes techniques | [`scripts/`](scripts/) |

Si tu souhaites seulement lire les résultats, ouvre `reports/`. Si tu souhaites expérimenter, ouvre `notebooks/`. Les dossiers `src/`, `tests/` et `scripts/` contiennent la partie technique.

Le notebook ne génère aucun rapport PDF automatiquement. Sa dernière section
sauvegarde cependant les résultats importants sous une forme réutilisable :
tableaux CSV, figures PDF/PNG, configuration et manifeste JSON. Chaque export est
conservé dans `output/runs/<date>_<mode>/`, tandis que `output/latest/` contient une
copie du dernier export complet. Cette sauvegarde n'a lieu que lorsque la dernière
cellule est exécutée ; une exécution partielle ne crée donc pas de demi-export.

Les résultats validés sont figés manuellement dans
`output/pdf/resultats_courants.pdf`. Le rapport académique est maintenu séparément
sous LaTeX dans `overleaf/` afin de garder une distinction claire entre calcul
exploratoire, résultats de référence et rédaction.

## Résultat Monte-Carlo de référence

Pour la configuration pédagogique documentée dans le rapport :

```text
Prix brut                      : 100,422920
Intervalle à 95 %              : [100,315489 ; 100,530352]
Prix avec variable de contrôle : 100,390169
```

Le détail des paramètres, de la convergence et des limites se trouve dans [`reports/MONTE_CARLO_VALIDATION.md`](reports/MONTE_CARLO_VALIDATION.md).

## Installation rapide

```bash
python -m venv .venv
python -m pip install -e ".[dev,notebook]"
```

Voir [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) pour l'activation de l'environnement sous Windows, macOS ou Linux.

## Exemple minimal

```python
from autocall_replication import AutocallProduct, price_autocall_bs_mc

result = price_autocall_bs_mc(
    product=AutocallProduct(),
    spot0=100.0,
    valuation_date="2025-01-02",
    maturity_date="2026-01-02",
    rate=0.02,
    dividend_yield=0.01,
    vol=0.20,
    n_paths=20_000,
    seed=42,
    antithetic=True,
    control_variate=True,
)

print(result["actualized_price"])
print(result["confidence_interval_95"])
```

## Validation

```bash
python scripts/validate.py
```

Cette commande vérifie la configuration, compile les modules, valide les notebooks et exécute les tests.

Pour reproduire les tableaux du rapport Monte-Carlo :

```bash
python scripts/reproduce_mc_report.py
```

## Statut

Le payoff contractuel et le moteur Monte-Carlo Black-Scholes sont testés. Les méthodes de réplication restent expérimentales et ne constituent pas encore une stratégie de couverture validée ni un prix de marché.
