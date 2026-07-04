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
from backend.llm import LLM, LawCandidate, RankResult, get_llm
from backend.models import Loi, Noeud, Constellation, Resolution, Cluster


def _noeuds_from(raw: list[dict]) -> list[Noeud]:
    from backend.models import Provenance
    return [Noeud(
        cluster=Cluster(d["cluster"]), titre=d["titre"], identifiant=d["identifiant"],
        provenance=Provenance(d["provenance"]), kind=d.get("kind", ""),
        who=d.get("who", ""), date=d.get("date", ""), note=d.get("note", ""),
        url=d.get("url", ""), tag=d.get("tag", ""),
    ) for d in raw]


def _run(adapter: ConnectorAdapter, method: str, args: dict, fn) -> list[Noeud]:
    raw = cached(adapter.name, method, args, lambda: [_dump(n) for n in fn()])
    return _noeuds_from(raw)


def _dump(n: Noeud) -> dict:
    return {
        "cluster": n.cluster.value, "titre": n.titre, "identifiant": n.identifiant,
        "provenance": n.provenance.value, "kind": n.kind, "who": n.who,
        "date": n.date, "note": n.note, "url": n.url, "tag": n.tag,
    }


def _lite(l: Loi) -> dict:
    return {"numero": l.numero, "titre": l.titre, "legitext": l.legitext,
            "date": l.date_signature or l.date_publication}


def _dump_rank(r: RankResult) -> dict:
    return {"chosen_index": r.chosen_index, "confidence": r.confidence,
            "ambiguous": r.ambiguous, "reason": r.reason,
            "alt_indices": r.alt_indices, "source": r.source}


def constellation(saisie: str, adapter: ConnectorAdapter, llm: LLM | None = None) -> Constellation:
    llm = llm or get_llm()

    # 1. candidats (cachés) — déjà sourcés via PISTE
    cand_raw = cached(adapter.name, "resolve_candidates", {"q": saisie},
                      lambda: [asdict(l) for l in adapter.resolve_candidates(saisie)])
    candidates = [Loi(**d) for d in cand_raw]
    if not candidates:
        raise ValueError(f"Loi introuvable : {saisie!r}")

    # 2. COMPRÉHENSION (LLM, cachée) : choisir PARMI les candidats. Contrat de
    #    confiance = indice validé ∈ candidats, jamais d'invention de loi.
    lc = [LawCandidate(legitext=c.legitext, numero=c.numero, titre=c.titre,
                       date=c.date_signature or c.date_publication) for c in candidates]
    rank = cached("llm", "rank",
                  {"q": saisie, "ids": [c.legitext for c in candidates], "llm": llm.name},
                  lambda: _dump_rank(llm.rank_laws(saisie, lc)))
    idx = rank["chosen_index"]
    if not (0 <= idx < len(candidates)):
        idx = 0
    loi = candidates[idx]

    # 3. expansion (mots-clés thématiques dérivés de la loi choisie)
    kw = expand(saisie, loi).mots_cles

    # 4. clusters — clé de cache = n°, ou legitext pour les lois sans numéro (1881)
    key = loi.numero or loi.legitext
    noeuds: list[Noeud] = []
    noeuds += _run(adapter, "application", {"num": key},
                   lambda: adapter.cluster_application(loi))
    noeuds += _run(adapter, "jurisprudence", {"num": key},
                   lambda: adapter.cluster_jurisprudence(loi))
    noeuds += _run(adapter, "doctrine", {"kw": kw},
                   lambda: adapter.cluster_doctrine(loi, kw))
    noeuds += _run(adapter, "parlement", {"kw": kw},
                   lambda: adapter.cluster_parlement(loi, kw))
    noeuds += _run(adapter, "connexes", {"num": key},
                   lambda: adapter.cluster_connexes(loi))

    # 5. garde-fou traçabilité : on écarte tout nœud sans identifiant vérifiable
    noeuds = [n for n in noeuds if n.identifiant]

    # 5bis. CLASSIFICATION des textes d'application « à vérifier » (LLM, cachée).
    #       Union + classification : on ne JETTE rien, on ÉTIQUETTE. Les décrets
    #       qui visent la loi sont déjà "application" ; on ne classe que ceux
    #       trouvés par citation du n° (application / citation / codification).
    a_classer = [n for n in noeuds
                 if n.cluster == Cluster.APPLICATION and n.tag == "a_verifier"]
    if a_classer:
        verdicts = cached(
            "llm", "classify_app",
            {"num": key, "llm": llm.name, "ids": [n.identifiant for n in a_classer]},
            lambda: llm.classify_application(loi.titre, [n.titre for n in a_classer]),
        )
        for n, v in zip(a_classer, verdicts):
            n.tag = v.get("label") or "application"
            if v.get("reason"):
                n.note = v["reason"]

    # 6. résolution : confiance + alternatives (pour la désambiguïsation front)
    alts = [candidates[i] for i in rank.get("alt_indices", [])
            if 0 <= i < len(candidates) and i != idx]
    resolution = Resolution(
        confidence=rank.get("confidence", 1.0), ambiguous=rank.get("ambiguous", False),
        reason=rank.get("reason", ""), source=rank.get("source", ""),
        alternatives=[_lite(a) for a in alts],
    )

    # 7. SYNTHÈSE IA ancrée (description + points clés), cachée. Le LLM ne résume
    #    QUE le matériel sourcé (intitulé officiel + intitulés des textes remontés)
    #    et n'invente aucun chiffre. Étiquetée « synthèse IA » côté front.
    synth = cached("llm", "synthese", {"num": key, "llm": llm.name},
                   lambda: llm.synthesize({
                       "titre": loi.titre, "domaine": loi.domaine,
                       "echantillon": _echantillon(noeuds),
                   }))
    synthese = synth or None

    return Constellation(loi=loi, noeuds=noeuds, resolution=resolution, synthese=synthese)


def _echantillon(noeuds: list[Noeud], per: int = 4) -> list[tuple[str, str]]:
    """Échantillon d'intitulés RÉELS par cluster — matériel d'ancrage de la synthèse."""
    from collections import defaultdict
    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for n in noeuds:
        c = n.cluster.value
        if n.titre and len(buckets[c]) < per:
            buckets[c].append((c, n.titre))
    out: list[tuple[str, str]] = []
    for c in ("app", "con", "jur", "doc", "par"):
        out += buckets.get(c, [])
    return out
