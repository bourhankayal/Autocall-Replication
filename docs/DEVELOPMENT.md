# Installation et validation locale

Ce document décrit la procédure reproductible pour préparer un environnement de développement propre.

## 1. Prérequis

- Python 3.11, 3.12 ou 3.13 ;
- Git ;
- un terminal PowerShell, Bash ou équivalent.

## 2. Créer un environnement virtuel

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### macOS ou Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 3. Installer le projet

Pour exécuter le moteur et les tests :

```bash
python -m pip install -e ".[dev]"
```

Pour utiliser également les notebooks et yfinance :

```bash
python -m pip install -e ".[dev,notebook]"
```

Les dépendances sont déclarées dans `pyproject.toml` :

- cœur : NumPy, pandas, SciPy et Matplotlib ;
- notebooks : IPython, JupyterLab et yfinance ;
- développement : pytest et Ruff.

## 4. Lancer tous les contrôles

Depuis la racine du dépôt :

```bash
python scripts/validate.py
```

Cette commande effectue successivement :

1. la validation de `pyproject.toml` ;
2. la compilation syntaxique des modules Python ;
3. la validation JSON des notebooks ;
4. l'exécution de tous les tests unitaires.

Les mêmes contrôles sont exécutés automatiquement par GitHub Actions avec
Python 3.11, 3.12 et 3.13 grâce au workflow `.github/workflows/ci.yml`.

Un code de sortie nul et le message suivant indiquent que le dépôt est valide :

```text
Validation terminee avec succes.
```

La procédure d'installation propre a été vérifiée localement sous Python 3.12 :
installation éditable du paquet, contrôle des dépendances, import du package,
29 tests unitaires réussis et reproduction du résultat Monte-Carlo de référence
(`100.422920`). Le workflow GitHub Actions est configuré, mais son exécution
distante ne pourra être confirmée qu'après publication du dépôt sur GitHub.

## 5. Commandes ciblées

Reproduction des résultats du rapport Monte-Carlo :

```bash
python scripts/reproduce_mc_report.py
```

Tests uniquement :

```bash
python -m unittest discover -s tests -v
```

Tests avec pytest, si l'extra `dev` est installé :

```bash
python -m pytest
```

Contrôle statique minimal :

```bash
python -m ruff check .
```

## 6. Fichiers générés

Les caches Python, environnements virtuels, caches de tests et rendus situés dans `tmp/` sont ignorés par Git. Les rapports finalisés doivent être placés dans `reports/`.
