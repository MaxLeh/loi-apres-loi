"""Expansion de requête : le pont entre la barre en langage naturel et les
cinq recherches.

Enseignement de la validation : deux modes de liaison coexistent.
  - CITATION (application, jurisprudence, connexes) : a besoin du **n° de loi**.
  - THÈME (doctrine, parlement) : a besoin de **mots-clés**. La recherche FTS
    est sensible aux termes — « revenu solidarité active sanction » remonte des
    résultats, « RSA suspension contrat d'engagement » n'en remonte aucun.

D'où cette couche, qui produit à partir d'une saisie libre :
  - `numero`   : pour les clusters par citation ;
  - `mots_cles`: pour les clusters thématiques.

Couche **déterministe** (regex + titre de la loi résolue). La COMPRÉHENSION de la
requête (choix de la loi, désambiguïsation, classification, synthèse) est confiée
à la couche LLM `backend/llm.py` — pas à cette couche, qui se contente de dériver
des mots-clés thématiques et reste donc reproductible sans réseau.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.models import Loi

_NUM_RE = re.compile(r"\b(\d{4})[-\s]?(\d{3,4})\b")

# mots vides à écarter des mots-clés dérivés du titre
_STOP = {
    "loi", "n", "du", "de", "la", "le", "les", "des", "et", "pour", "portant",
    "relative", "relatif", "aux", "à", "au", "d", "l", "en", "sur", "par",
    "modifiant", "création", "un", "une", "dispositions", "diverses",
}


@dataclass
class Expansion:
    numero: str
    mots_cles: list[str]


def expand(saisie: str, loi: Loi | None = None) -> Expansion:
    """Produit le n° + les mots-clés pour alimenter les cinq recherches."""
    numero = _extract_numero(saisie) or (loi.numero if loi else "")
    base = (loi.titre if loi else saisie)
    mots = _keywords(base)
    return Expansion(numero=numero, mots_cles=mots)


def _extract_numero(s: str) -> str:
    m = _NUM_RE.search(s)
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def _keywords(titre: str, k: int = 6) -> list[str]:
    """Extrait des mots-clés thématiques du titre (heuristique MVP)."""
    titre = re.sub(r"n[°º]\s*\d{4}[-\s]?\d+", " ", titre, flags=re.I)
    titre = re.sub(r"du\s+\d{1,2}\s+\w+\s+\d{4}", " ", titre, flags=re.I)
    mots = re.findall(r"[a-zàâäéèêëîïôöùûüç']{3,}", titre.lower())
    out: list[str] = []
    for m in mots:
        m = m.strip("'")
        if m and m not in _STOP and m not in out:
            out.append(m)
    return out[:k]


# Piste d'amélioration : enrichir les mots-clés par synonymes/sigles (RSA ↔
# revenu de solidarité active…). La couche LLM existe déjà (`backend/llm.py`) et
# pourrait produire ces variantes ; cette couche-ci reste néanmoins volontairement
# déterministe pour garder la génération de mots-clés reproductible sans clé.
