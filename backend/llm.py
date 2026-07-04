"""Couche LLM — COMPRÉHENSION seulement (le « contrat de confiance »).

Principe : le LLM ne produit JAMAIS un fait affiché. Il ne fait que **choisir
parmi des candidats déjà récupérés et identifiés** (sourcés via PISTE). Pour la
résolution : étant donné une saisie libre et une liste de lois candidates, il
désigne LAQUELLE correspond — en renvoyant un INDICE de la liste. L'indice est
validé (∈ candidats) : impossible d'inventer une loi. En cas de doute ou d'échec
réseau, on retombe sur l'heuristique déterministe.

Deux implémentations derrière une interface unique (swappable) :
  - `MistralLLM`   : API Mistral (souveraineté FR). Nécessite `MISTRAL_API_KEY`.
  - `HeuristicLLM` : repli déterministe, sans réseau ni clé (démo reproductible).

Pour la souveraineté/reproductibilité en production : brancher un modèle
open-weight (Apache-2.0) derrière la même interface — le pipeline ne change pas.
"""
from __future__ import annotations

import os
import re
import json
import unicodedata
from dataclasses import dataclass, field

import httpx


@dataclass
class LawCandidate:
    """Une loi candidate, déjà récupérée et identifiée (jamais inventée)."""
    legitext: str
    numero: str
    titre: str
    date: str = ""


@dataclass
class RankResult:
    chosen_index: int          # indice DANS la liste des candidats (jamais hors-liste)
    confidence: float          # 0..1
    ambiguous: bool            # vrai si plusieurs candidats plausibles
    reason: str = ""
    alt_indices: list[int] = field(default_factory=list)  # autres candidats plausibles
    source: str = "heuristic"  # "mistral" | "heuristic"


class LLM:
    name = "base"

    def rank_laws(self, query: str, candidates: list[LawCandidate]) -> RankResult:  # pragma: no cover
        raise NotImplementedError

    def classify_application(self, loi_titre: str, decrees: list[str]) -> list[dict]:
        """Classe chaque texte d'application. Aligné par indice sur `decrees`.
        Défaut prudent : tout « application » (aucun texte écarté)."""
        return [{"label": "application", "reason": ""} for _ in decrees]

    def synthesize(self, context: dict) -> dict:
        """Synthèse ANCRÉE (description + points clés) à partir du matériel sourcé.
        Défaut : rien (le front retombe sur une description générique). Ne génère
        JAMAIS de chiffre inventé."""
        return {}


# ----------------------------------------------------------------------------
# Repli déterministe — aucun réseau, aucune clé. Distingue la loi FONDATRICE
# des lois qui ne font que la modifier (« visant à… », « modifiant… »).
# ----------------------------------------------------------------------------
_META = (
    "modifiant", "modifiee", "visant", "portant modification", "portant reforme",
    "harmoniser", "abrogeant", "ratifiant", "completant", "prorogeant",
    "modification", "adaptation", "relative a la loi", "prevues par la loi",
)
_STOP = {"loi", "des", "les", "une", "aux", "sur", "par", "pour", "relative",
         "relatif", "portant", "dispositions", "diverses", "janvier", "fevrier",
         "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
         "octobre", "novembre", "decembre"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _content_words(s: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", _norm(s)):
        if len(w) > 2 and not w.isdigit() and w not in _STOP:
            out.append(w)
    return out


def _score(query_words: set[str], c: LawCandidate) -> float:
    tw = _content_words(c.titre)
    tset = set(tw)
    overlap = len(query_words & tset)
    ratio = overlap / max(len(tset), 1)          # concept requêté ≈ sujet du titre ?
    t = _norm(c.titre)
    penalty = sum(1 for m in _META if m in t)     # loi qui parle d'une AUTRE loi
    return overlap * 2 + ratio * 3 - penalty * 2.5


# Classification des textes d'application (cluster « application »).
# 3 étiquettes : "application" (met en œuvre la loi) | "citation" (modifie/cite
# sans être une mesure d'application) | "codification" (codification à droit
# constant / incorporation / abrogation — le bruit à écarter, ex. décret 2022-783).
APP_LABELS = ("application", "citation", "codification")
_CODIF_MARK = ("incorporation", "codifi", "droit constant", "partie reglementaire",
               "abrogeant", "abrogation", "toilettage")


def _heur_classify(titre: str) -> tuple[str, str]:
    t = _norm(titre)
    if any(m in t for m in _CODIF_MARK):
        return ("codification", "titre de codification/abrogation (heuristique)")
    return ("application", "rattaché par citation du n° de loi (heuristique)")


class HeuristicLLM(LLM):
    name = "heuristic"

    def rank_laws(self, query: str, candidates: list[LawCandidate]) -> RankResult:
        if not candidates:
            return RankResult(chosen_index=-1, confidence=0.0, ambiguous=False,
                              reason="aucun candidat", source=self.name)
        qw = set(_content_words(query))
        scored = sorted(
            ((_score(qw, c), i) for i, c in enumerate(candidates)),
            key=lambda x: -x[0],
        )
        best_i = scored[0][1]
        gap = scored[0][0] - scored[1][0] if len(scored) > 1 else 99.0
        ambiguous = gap < 1.5
        return RankResult(
            chosen_index=best_i,
            confidence=0.55 if ambiguous else 0.8,
            ambiguous=ambiguous,
            reason="heuristique : recouvrement de titre + pénalité des lois modificatives",
            alt_indices=[i for _, i in scored[1:4]],
            source=self.name,
        )

    def classify_application(self, loi_titre: str, decrees: list[str]) -> list[dict]:
        return [dict(zip(("label", "reason"), _heur_classify(d))) for d in decrees]


# ----------------------------------------------------------------------------
# Mistral — l'IA ne fait que COMPRENDRE la requête et pointer un candidat.
# ----------------------------------------------------------------------------
_SYS = (
    "Tu es un assistant de recherche juridique française. On te donne une requête "
    "en langage naturel et une liste NUMÉROTÉE de lois candidates (déjà trouvées "
    "dans Légifrance). Distingue DEUX cas :\n"
    "1) La requête vise UNE loi précise (numéro, ou intitulé spécifique) → désigne-la "
    "(index) et mets ambiguous=false.\n"
    "2) La requête est un THÈME couvert par PLUSIEURS lois DISTINCTES (des textes "
    "différents portant chacun sur ce thème — PAS de simples versions/modifications "
    "l'une de l'autre) → mets ambiguous=true et liste TOUS ces textes dans "
    "alternatives (le plus central d'abord). Garde comme index ton meilleur choix "
    "(souvent la loi fondatrice), mais NE MASQUE PAS les autres.\n"
    "Exemple thématique : « renseignement » → loi de 2015 relative au renseignement "
    "ET loi de 2021 sur la prévention du terrorisme et le renseignement.\n"
    "N'invente jamais de loi. Réponds UNIQUEMENT par un objet JSON."
)
_USER_TMPL = (
    "Requête : « {query} »\n\nCandidats :\n{cands}\n\n"
    "Réponds en JSON strict : {{\"index\": <entier du meilleur candidat>, "
    "\"confidence\": <0..1>, \"ambiguous\": <true si PLUSIEURS lois distinctes "
    "couvrent ce thème>, \"alternatives\": [<indices des autres lois de la même "
    "famille thématique, pertinence décroissante>], \"reason\": \"<courte "
    "justification>\"}}."
)

_SYS_CLASS = (
    "Tu es juriste. On te donne une LOI et une liste NUMÉROTÉE de décrets/arrêtés "
    "qui citent son numéro. Classe CHAQUE texte selon son lien RÉEL avec la loi : "
    "'application' = pris pour l'application de la loi / met en œuvre ses "
    "dispositions ; 'citation' = modifie ou mentionne la loi sans en être une "
    "mesure d'application directe ; 'codification' = codification à droit constant, "
    "incorporation dans un code, ou abrogation (ne mets PAS 'application' pour "
    "ceux-là). Réponds UNIQUEMENT en JSON."
)
_USER_CLASS = (
    "Loi : « {loi} »\n\nTextes :\n{items}\n\n"
    "Réponds en JSON strict : {{\"items\": [{{\"index\": <i>, \"label\": "
    "\"application|citation|codification\", \"reason\": \"<courte justification>\"}}"
    ", …]}} — une entrée par texte, dans l'ordre."
)

# Synthèse ANCRÉE : le LLM ne résume QUE le matériel fourni (intitulé officiel +
# métadonnées des textes remontés). Interdiction stricte d'inventer un fait/chiffre.
_SYS_SYNTH = (
    "Tu es juriste. À partir EXCLUSIVEMENT des données fournies (intitulé officiel "
    "de la loi et intitulés RÉELS des textes qui s'y rattachent — décrets, "
    "jurisprudence, questions parlementaires), tu rédiges une fiche synthétique. "
    "RÈGLES ABSOLUES : n'ajoute AUCUN fait, chiffre, montant, date ni disposition "
    "qui ne figure pas dans les données ; en cas de doute, reste général et neutre ; "
    "n'invente rien. Réponds UNIQUEMENT en JSON."
)
_USER_SYNTH = (
    "Loi : « {titre} »\nDomaine indicatif : {domaine}\n"
    "Textes rattachés (échantillon réel) :\n{ech}\n\n"
    "Réponds en JSON strict : {{\"description\": \"<2 phrases neutres décrivant "
    "l'objet de la loi, fondées UNIQUEMENT sur l'intitulé et les textes ci-dessus>\", "
    "\"points_cles\": [{{\"label\": \"<2-3 mots>\", \"text\": \"<une phrase "
    "factuelle, sans chiffre inventé>\"}}, … 3 à 4 éléments]}}."
)


class MistralLLM(LLM):
    name = "mistral"

    def __init__(self, api_key: str, model: str | None = None):
        self._key = api_key
        self._model = model or os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
        self._http = httpx.Client(timeout=30.0)

    def rank_laws(self, query: str, candidates: list[LawCandidate]) -> RankResult:
        if not candidates:
            return RankResult(chosen_index=-1, confidence=0.0, ambiguous=False,
                              reason="aucun candidat", source=self.name)
        cands = "\n".join(
            f"{i}. {c.titre}" + (f"  (n° {c.numero})" if c.numero else "  (sans numéro)")
            for i, c in enumerate(candidates)
        )
        try:
            r = self._http.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": _SYS},
                        {"role": "user", "content": _USER_TMPL.format(query=query, cands=cands)},
                    ],
                },
            )
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            idx = int(data["index"])
            if not (0 <= idx < len(candidates)):          # garde-fou anti-hallucination
                raise ValueError("indice hors candidats")
            alts = [i for i in data.get("alternatives", [])
                    if isinstance(i, int) and 0 <= i < len(candidates) and i != idx][:3]
            return RankResult(
                chosen_index=idx,
                confidence=float(data.get("confidence", 0.7)),
                ambiguous=bool(data.get("ambiguous", False)),
                reason=str(data.get("reason", ""))[:200],
                alt_indices=alts,
                source=self.name,
            )
        except Exception:
            # réseau/format/clé KO → repli déterministe (jamais bloquant)
            return HeuristicLLM().rank_laws(query, candidates)

    def classify_application(self, loi_titre: str, decrees: list[str]) -> list[dict]:
        if not decrees:
            return []
        items = "\n".join(f"{i}. {t}" for i, t in enumerate(decrees))
        fallback = HeuristicLLM().classify_application(loi_titre, decrees)
        try:
            r = self._http.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": _SYS_CLASS},
                        {"role": "user", "content": _USER_CLASS.format(loi=loi_titre, items=items)},
                    ],
                },
            )
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            out = list(fallback)  # défaut par indice si le LLM en oublie
            for it in data.get("items", []):
                i = it.get("index")
                label = it.get("label", "")
                if isinstance(i, int) and 0 <= i < len(out) and label in APP_LABELS:
                    out[i] = {"label": label, "reason": str(it.get("reason", ""))[:160]}
            return out
        except Exception:
            return fallback

    def synthesize(self, context: dict) -> dict:
        ech = "\n".join(f"- [{c}] {t}" for c, t in context.get("echantillon", []))
        if not ech:
            return {}
        try:
            r = self._http.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": _SYS_SYNTH},
                        {"role": "user", "content": _USER_SYNTH.format(
                            titre=context.get("titre", ""),
                            domaine=context.get("domaine") or "—", ech=ech)},
                    ],
                },
            )
            r.raise_for_status()
            data = json.loads(r.json()["choices"][0]["message"]["content"])
            desc = str(data.get("description", "")).strip()[:400]
            pts = []
            for p in (data.get("points_cles") or [])[:5]:
                txt = str(p.get("text", "")).strip()[:180]
                if txt:
                    pts.append({"label": str(p.get("label", "")).strip()[:32], "text": txt})
            return {"description": desc, "points_cles": pts} if desc else {}
        except Exception:
            return {}


def get_llm() -> LLM:
    """Mistral si `MISTRAL_API_KEY` est présent, sinon l'heuristique déterministe."""
    key = os.environ.get("MISTRAL_API_KEY", "").strip()
    return MistralLLM(key) if key else HeuristicLLM()
