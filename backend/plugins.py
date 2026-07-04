"""Sélection de l'adaptateur actif.

Le dépôt public embarque uniquement l'adaptateur de RÉFÉRENCE (open data).
L'adaptateur SILEXIA (premium) est distribué séparément (dépôt privé) et se
dépose dans `backend/adapters/silexia.py` au moment du déploiement. Ce sélecteur
le charge dynamiquement **s'il est présent** ; sinon, il renvoie un message
d'erreur actionnable au lieu de casser.
"""
from __future__ import annotations

import os

from backend.adapters.base import ConnectorAdapter


def load_adapter() -> ConnectorAdapter:
    backend = os.environ.get("BACKEND", "reference")

    if backend == "reference":
        from backend.adapters.reference import ReferenceAdapter
        return ReferenceAdapter()

    if backend == "silexia":
        try:
            from backend.adapters.silexia import SilexiaAdapter  # plugin privé
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "Adaptateur premium « silexia » absent de ce dépôt public. "
                "Il est distribué séparément et se dépose dans "
                "backend/adapters/silexia.py (voir README § Adaptateur premium)."
            ) from e
        return SilexiaAdapter(_build_mcp_client())

    raise RuntimeError(f"BACKEND inconnu : {backend!r} (attendu : reference | silexia).")


def _build_mcp_client():
    """Construit le client MCP Silexia (implémentation propre au déploiement privé)."""
    raise RuntimeError(
        "Client MCP Silexia à injecter — à implémenter dans le déploiement privé "
        "(auth + transport vers SILEXIA_MCP_URL)."
    )
