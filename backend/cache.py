"""Cache disque JSON — deux rôles.

1. ROBUSTESSE : PISTE renvoie des 500 transitoires (observé en live). Un hit de
   cache évite de re-solliciter l'API.
2. MODE DÉMO : le jour du pitch, on NE joue PAS contre PISTE dans une salle
   bondée. `DEMO_MODE=1` force la lecture seule depuis le cache : toute la ou
   les lois de démo doivent avoir été « réchauffées » (warmup) au préalable.

Clé de cache = (adaptateur, méthode, arguments). Valeur = liste de nœuds
sérialisés (ou dict loi).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable

CACHE_DIR = Path(os.environ.get("CACHE_DIR", "data/cache"))
DEMO_MODE = os.environ.get("DEMO_MODE", "0") == "1"


class CacheMiss(RuntimeError):
    """Levé en mode démo quand une clé n'est pas pré-chauffée."""


def _key(adapter: str, method: str, args: dict) -> str:
    raw = json.dumps({"a": adapter, "m": method, "args": args}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def cached(adapter: str, method: str, args: dict, producer: Callable[[], list | dict]):
    """Renvoie la valeur en cache, sinon la produit et l'écrit.

    En `DEMO_MODE`, ne produit jamais : lève `CacheMiss` si la clé manque.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{adapter}_{method}_{_key(adapter, method, args)}.json"

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    if DEMO_MODE:
        raise CacheMiss(f"[DÉMO] clé non réchauffée : {adapter}.{method} {args}")

    value = producer()
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return value


def warmup_note() -> str:
    return ("Pour réchauffer la démo : DEMO_MODE=0 python -m backend.warmup <numero_loi>, "
            "puis basculer DEMO_MODE=1 pour le pitch.")
