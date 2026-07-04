"""Chargement optionnel d'un fichier `.env` — sans dépendance externe.

Les points d'entrée (`api`, `warmup`) appellent `load_env()` AVANT d'importer
les modules qui lisent l'environnement (`cache.py` lit `DEMO_MODE` à l'import).

En production (Scalingo), les variables sont injectées par la plateforme et le
fichier `.env` est absent : le chargement est alors un no-op. Les variables
déjà présentes dans l'environnement ont TOUJOURS priorité sur le fichier
(`setdefault`), pour qu'un `DEMO_MODE=1` passé au lancement l'emporte sur la
valeur du fichier.
"""
from __future__ import annotations

import os
from pathlib import Path

# Racine du dépôt = parent de backend/ ; le .env de démo y vit.
_DEFAULT = Path(__file__).resolve().parent.parent / ".env"


def load_env(path: str | os.PathLike | None = None) -> None:
    p = Path(path) if path is not None else _DEFAULT
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())
