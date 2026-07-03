"""Orchestrateur — le cœur du défi.

`constellation(saisie)` :
  1. résout la saisie libre en une `Loi` ;
  2. calcule l'expansion (n° + mots-clés) ;
  3. lance les cinq recherches de clusters (chacune passée au cache) ;
  4. assemble une `Constellation` sérialisable pour le front.

Chaque appel d'adaptateur transite par `cache.cached(...)` : robustesse
anti-500 en dev, lecture seule en mode démo.
"""
from __future__ import annotations

from dataclasses import asdict

from backend.adapters.base import ConnectorAdapter
from backend.cache import cached
from backend.expansion import expand
from backend.models import Loi, Noeud, Constellation


def _noeuds_from(raw: list[dict]) -> list[Noeud]:
    from backend.models import Cluster, Provenance
    return [Noeud(
        cluster=Cluster(d["cluster"]), titre=d["titre"], identifiant=d["identifiant"],
        provenance=Provenance(d["provenance"]), kind=d.get("kind", ""),
        who=d.get("who", ""), date=d.get("date", ""), note=d.get("note", ""),
        url=d.get("url", ""),
    ) for d in raw]


def _run(adapter: ConnectorAdapter, method: str, args: dict, fn) -> list[Noeud]:
    raw = cached(adapter.name, method, args, lambda: [_dump(n) for n in fn()])
    return _noeuds_from(raw)


def _dump(n: Noeud) -> dict:
    return {
        "cluster": n.cluster.value, "titre": n.titre, "identifiant": n.identifiant,
        "provenance": n.provenance.value, "kind": n.kind, "who": n.who,
        "date": n.date, "note": n.note, "url": n.url,
    }


def constellation(saisie: str, adapter: ConnectorAdapter) -> Constellation:
    # 1. résolution (cachée)
    loi_raw = cached(adapter.name, "resolve_loi", {"q": saisie},
                     lambda: asdict(adapter.resolve_loi(saisie)))
    loi = Loi(**loi_raw)

    # 2. expansion
    exp = expand(saisie, loi)
    kw = exp.mots_cles

    # 3. clusters
    noeuds: list[Noeud] = []
    noeuds += _run(adapter, "application", {"num": loi.numero},
                   lambda: adapter.cluster_application(loi))
    noeuds += _run(adapter, "jurisprudence", {"num": loi.numero},
                   lambda: adapter.cluster_jurisprudence(loi))
    noeuds += _run(adapter, "doctrine", {"kw": kw},
                   lambda: adapter.cluster_doctrine(loi, kw))
    noeuds += _run(adapter, "parlement", {"kw": kw},
                   lambda: adapter.cluster_parlement(loi, kw))
    noeuds += _run(adapter, "connexes", {"num": loi.numero},
                   lambda: adapter.cluster_connexes(loi))

    # 4. garde-fou traçabilité : on écarte tout nœud sans identifiant vérifiable
    noeuds = [n for n in noeuds if n.identifiant]

    return Constellation(loi=loi, noeuds=noeuds)
