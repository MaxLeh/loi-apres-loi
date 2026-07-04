"""Réchauffe le cache pour la démo.

Usage :
    DEMO_MODE=0 BACKEND=reference python -m backend.warmup "loi plein emploi" "2023-1196"

Puis, pour le pitch, lancer l'API avec DEMO_MODE=1 : toutes les recherches
seront servies depuis le cache, sans toucher PISTE.
"""
from __future__ import annotations

import os
import sys

from backend.env import load_env
load_env()  # charge .env avant l'import de cache.py (qui lit DEMO_MODE à l'import)

from backend.orchestrator import constellation


def main(argv: list[str]) -> int:
    if not argv:
        print("Donner au moins une loi à réchauffer (n° ou intitulé).")
        return 2
    backend = os.environ.get("BACKEND", "reference")
    if backend == "silexia":
        print("Warmup Silexia : injecter un client MCP dans _adapter().")
        return 2
    from backend.adapters.reference import ReferenceAdapter
    adapter = ReferenceAdapter()
    for saisie in argv:
        c = constellation(saisie, adapter)
        counts = c.compte_par_cluster()
        print(f"✓ {saisie!r} → {c.loi.numero} · {sum(counts.values())} nœuds {counts}")
    print("Cache prêt. Basculer DEMO_MODE=1 pour le pitch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
