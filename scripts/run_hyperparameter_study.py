"""Execute the dedicated notebook cells without changing the source notebook.

Usage: python scripts/run_hyperparameter_study.py --mode sprint|fast|report
The notebook's final cell remains responsible for its immutable run export.
Promotion remains disabled by default and must be done after inspection.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "hyperparameter_research.ipynb"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("sprint", "fast", "report"), required=True)
    parser.add_argument("--stop-after", type=int, default=None)
    arguments = parser.parse_args()
    os.environ.setdefault("MPLBACKEND", "Agg")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    namespace: dict[str, object] = {"__name__": "__main__"}
    cells = notebook["cells"]
    for index, cell in enumerate(cells):
        if arguments.stop_after is not None and index > arguments.stop_after:
            break
        if cell["cell_type"] != "code":
            continue
        code = "".join(cell["source"])
        if 'RUN_MODE = "fast"' in code:
            code = code.replace('RUN_MODE = "fast"', f'RUN_MODE = "{arguments.mode}"')
        first_line = next((line.strip() for line in code.splitlines() if line.strip()), "")
        print(f"[Hyperparameters {arguments.mode.upper()}] cellule {index}: {first_line}", flush=True)
        try:
            exec(compile(code, str(NOTEBOOK) + f":cell{index}", "exec"), namespace)
        except Exception:
            print(f"Échec dans la cellule {index}. Aucune promotion automatique.", flush=True)
            raise
    if arguments.stop_after is None:
        print(f"Étude {arguments.mode.upper()} terminée.", flush=True)
    else:
        print(
            f"Pré-contrôle {arguments.mode.upper()} arrêté après la cellule "
            f"{arguments.stop_after} ; aucune étude complète n'a été exportée.",
            flush=True,
        )


if __name__ == "__main__":
    main()
