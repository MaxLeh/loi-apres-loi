"""Test hors-ligne du mapping PISTE /search (cluster jurisprudence).

Exécutable sans réseau :
    python -m tests.test_piste_mapping
Ou avec pytest :
    pytest tests/

Pour VALIDER contre la vraie API : remplacer tests/sample_piste_cetat.json par
une réponse live de PISTE /search (fond CETAT), puis relancer. Si un assert
casse, ajuster les noms de champs marqués « ? » dans
backend/adapters/reference._normalize_piste_hits.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from backend.adapters.reference import _normalize_piste_hits, _legi_url, _fmt_date

FIXTURE = Path(__file__).parent / "sample_piste_cetat.json"
_DDMMYYYY = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def test_dates():
    assert _fmt_date("2026-04-28") == "28/04/2026"
    assert _DDMMYYYY.match(_fmt_date(1780012800000))   # epoch ms → date
    assert _fmt_date("") == ""


def test_legi_url():
    assert _legi_url("CETATEXT000053980087") == "https://www.legifrance.gouv.fr/ceta/id/CETATEXT000053980087"
    assert _legi_url("JORFTEXT000048581935").endswith("/jorf/id/JORFTEXT000048581935")
    assert _legi_url("INCONNU000") == ""


def test_mapping_jurisprudence():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hits = _normalize_piste_hits(data)

    assert len(hits) == 2, "deux décisions attendues"

    h0 = hits[0]
    assert h0["id"] == "CETATEXT000053980087", "identifiant vérifiable extrait"
    assert h0["date"] == "28/04/2026", "date de décision ISO normalisée"
    assert h0["juridiction"] == "Conseil d'État"
    assert h0["formation"] == "1ère chambre"
    assert h0["solution"] == "Rejet"
    assert h0["url"] == "https://www.legifrance.gouv.fr/ceta/id/CETATEXT000053980087"

    h1 = hits[1]
    assert h1["id"] == "CETATEXT000054178558"
    assert _DDMMYYYY.match(h1["date"]), "date epoch normalisée en DD/MM/YYYY"

    # Garde-fou traçabilité : aucun identifiant vide
    assert all(h["id"] for h in hits)


def _run():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {name}")
    print("Tous les tests passent.")


if __name__ == "__main__":
    _run()
