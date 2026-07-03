"""Adaptateur de RÉFÉRENCE — données ouvertes, reproductible par tous.

C'est l'implémentation publiée avec le défi. Elle n'exige aucun composant
Silexia. Sources :
  - Légifrance / API PISTE (Licence Ouverte Etalab) : lois, décrets, arrêtés,
    jurisprudence CETAT/JURI/CONSTIT/CNIL. Auth OAuth2 (clé gratuite PISTE).
  - HAL / archives-ouvertes.fr (API ouverte, sans clé) : doctrine open access.
  - Questions écrites AN + Sénat (open data) : cluster parlementaire.

⚠️ Enseignements de la validation live (câblés ci-dessous) :
  - APPLICATION : `search(fond=LODA_ETAT, field_type=VISA, query=<numero>)`.
    NE PAS utiliser les liens de `consult_jorf_text` → HTTP 500 sur grosses lois.
  - PISTE est instable : chaque appel passe par `_piste()` avec retry/backoff.
"""
from __future__ import annotations

import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.adapters.base import ConnectorAdapter
from backend.models import Loi, Noeud, Cluster, Provenance

PISTE_BASE = os.environ.get("PISTE_BASE", "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app")
PISTE_OAUTH = "https://oauth.piste.gouv.fr/api/oauth/token"
HAL_API = "https://api.archives-ouvertes.fr/search/"
PARLEMENT_API = os.environ.get("PARLEMENT_API", "https://parlement.tricoteuses.fr")


class PisteError(RuntimeError):
    pass


class ReferenceAdapter(ConnectorAdapter):
    name = "reference"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self._id = client_id or os.environ.get("PISTE_CLIENT_ID", "")
        self._secret = client_secret or os.environ.get("PISTE_CLIENT_SECRET", "")
        self._token: str | None = None
        self._http = httpx.Client(timeout=30.0)

    # ---------- infrastructure PISTE (auth + retry) ----------
    def _auth(self) -> str:
        if self._token:
            return self._token
        r = self._http.post(PISTE_OAUTH, data={
            "grant_type": "client_credentials", "client_id": self._id,
            "client_secret": self._secret, "scope": "openid",
        })
        r.raise_for_status()
        self._token = r.json()["access_token"]
        return self._token

    @retry(
        retry=retry_if_exception_type(PisteError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.8, min=0.8, max=8),
        reraise=True,
    )
    def _piste(self, path: str, payload: dict) -> dict:
        """Appel PISTE avec retry — PISTE renvoie des 500 transitoires."""
        r = self._http.post(
            f"{PISTE_BASE}{path}",
            headers={"Authorization": f"Bearer {self._auth()}", "Content-Type": "application/json"},
            json=payload,
        )
        if r.status_code >= 500:
            raise PisteError(f"PISTE {r.status_code} sur {path}")
        r.raise_for_status()
        return r.json()

    def _search(self, fond: str, query: str, field: str = "ALL", nature: str | None = None, size: int = 10) -> list[dict]:
        """Recherche générique PISTE. Renvoie une liste normalisée de hits.

        TODO(24h) : figer le mapping exact du payload PISTE /search selon le
        fond. La forme ci-dessous est le squelette ; adapter aux champs réels.
        """
        criteria = [{"typeRecherche": "TOUS_LES_MOTS_DANS_UN_CHAMP", "valeur": query, "operateur": "ET"}]
        payload = {
            "recherche": {
                "champs": [{"typeChamp": field, "criteres": criteria, "operateur": "ET"}],
                "pageNumber": 1, "pageSize": size, "sort": "PERTINENCE",
                "typePagination": "DEFAUT",
            },
            "fond": fond,
        }
        if nature:
            payload["recherche"]["filtres"] = [{"facette": "NATURE", "valeurs": [nature]}]
        data = self._piste("/search", payload)
        return _normalize_piste_hits(data)

    # ---------- resolve ----------
    def resolve_loi(self, numero_ou_titre: str) -> Loi:
        hits = self._search("LODA_ETAT", numero_ou_titre, nature="LOI", size=1)
        if not hits:
            raise ValueError(f"Loi introuvable : {numero_ou_titre!r}")
        h = hits[0]
        return Loi(
            numero=h.get("num", ""), titre=h.get("title", ""),
            legitext=h.get("id", ""), nor=h.get("nor", ""),
            date_signature=h.get("date_sig", ""), date_publication=h.get("date_pub", ""),
        )

    # ---------- clusters ----------
    def cluster_application(self, loi: Loi) -> list[Noeud]:
        # ✅ pattern validé : VISA + n° de loi sur LODA_ETAT
        out: list[Noeud] = []
        for nature in ("DECRET", "ARRETE"):
            for h in self._search("LODA_ETAT", loi.numero, field="VISA", nature=nature, size=15):
                out.append(Noeud(
                    cluster=Cluster.APPLICATION, titre=h.get("title", ""),
                    identifiant=h.get("id", ""), provenance=Provenance.LEGIFRANCE,
                    kind=nature.capitalize(), who="Légifrance",
                    date=h.get("date_pub", ""), url=h.get("url", ""),
                ))
        return out

    def cluster_jurisprudence(self, loi: Loi) -> list[Noeud]:
        # Cluster non couvert par les ressources hackathon → fonds PISTE.
        out: list[Noeud] = []
        vus: set[str] = set()
        prov = {"CETAT": Provenance.CETAT, "JURI": Provenance.JUDILIBRE,
                "CONSTIT": Provenance.CONSTIT, "CNIL": Provenance.CNIL}
        for fond, p in prov.items():
            for h in self._search(fond, loi.numero, size=8):
                ident = h.get("id", "")
                if not ident or ident in vus:   # traçabilité + dédup
                    continue
                # Précision : le fond CONSTIT matche parfois une décision dont le
                # NUMÉRO coïncide avec le n° de loi (ex. « 2024-42…/53 ELEC »).
                # On ne garde que les décisions substantielles (DC / QPC).
                if fond == "CONSTIT" and not _CONSTIT_TYPES.search(h.get("title", "")):
                    continue
                vus.add(ident)
                who = " · ".join(x for x in (h.get("juridiction", ""), h.get("formation", "")) if x)
                out.append(Noeud(
                    cluster=Cluster.JURISPRUDENCE, titre=h.get("title", ""),
                    identifiant=ident, provenance=p, kind=_jur_kind(fond),
                    who=who or _jur_kind(fond), date=h.get("date", ""),
                    note=h.get("solution", ""), url=h.get("url", ""),
                ))
        return out

    def cluster_doctrine(self, loi: Loi, mots_cles: list[str]) -> list[Noeud]:
        # HAL : API ouverte, sans clé. Collection droit national.
        q = " ".join(mots_cles) or loi.titre
        params = {
            "q": q, "fq": "collCode_s:AO-DROIT", "rows": 8,
            "fl": "halId_s,title_s,authFullName_s,producedDate_s,uri_s",
            "wt": "json",
        }
        out: list[Noeud] = []
        try:
            r = self._http.get(HAL_API, params=params)
            r.raise_for_status()
            for d in r.json().get("response", {}).get("docs", []):
                out.append(Noeud(
                    cluster=Cluster.DOCTRINE,
                    titre=(d.get("title_s") or [""])[0],
                    identifiant=d.get("halId_s", ""), provenance=Provenance.HAL,
                    kind="Article de revue",
                    who=", ".join(d.get("authFullName_s", [])[:2]),
                    date=(d.get("producedDate_s") or ""), url=d.get("uri_s", ""),
                ))
        except httpx.HTTPError:
            pass  # HAL indisponible → cluster doctrine vide, non bloquant
        # TODO(24h) : ajouter Isidore (source='all') et BOFiP (search) en complément.
        return out

    def cluster_parlement(self, loi: Loi, mots_cles: list[str]) -> list[Noeud]:
        # Questions écrites AN + Sénat via l'API OUVERTE parlement.tricoteuses.fr
        # (open data, sans clé). Recherche plein texte sur les mots-clés
        # thématiques de la loi (sensible aux termes → alimentés par l'expansion,
        # pas le n° de loi brut).
        q = " ".join(mots_cles).strip() or loi.titre
        if not q:
            return []
        try:
            r = self._http.get(
                f"{PARLEMENT_API}/questions/json",
                params={"search": q, "type": "QE", "perPage": 8},
            )
            r.raise_for_status()
            items = r.json().get("data", [])
        except (httpx.HTTPError, ValueError):
            return []  # source indisponible → cluster parlement vide, jamais bloquant
        out: list[Noeud] = []
        for h in items:
            uid = h.get("uid", "")
            if not uid:  # traçabilité : pas d'identifiant officiel → on écarte
                continue
            cham = (h.get("chambre") or "").upper()
            out.append(Noeud(
                cluster=Cluster.PARLEMENT,
                titre=h.get("titre") or _strip_html(h.get("texteQuestion", ""))[:90],
                identifiant=uid,
                provenance=Provenance.QP,
                kind="Question écrite " + {"AN": "AN", "SN": "Sénat"}.get(cham, cham),
                who=_question_auteur(h.get("texteQuestion", "")),
                date=_fmt_date(h.get("dateDepot", "")),
                note=h.get("libelleCloture", ""),
                url=_question_url(cham, h.get("legislature"), h.get("numero")),
            ))
        return out

    def cluster_connexes(self, loi: Loi) -> list[Noeud]:
        # TODO(24h) : lois/codes/ordonnances citées dans le dispositif.
        return []


# ---------- helpers de normalisation ----------
#
# Forme de la réponse PISTE /search (Légifrance) :
#   { "results": [ { "titles": [ {"id","cid","title"} ], ...métadonnées... } ],
#     "totalResultNumber": N }
# Les métadonnées au niveau `result` varient selon le fond. Le parseur ci-dessous
# est DÉFENSIF (plusieurs noms de champs possibles) : les clés marquées « ? » sont
# à confirmer contre une réponse live (voir tests/sample_piste_cetat.json).

def _first_title(res: dict) -> dict:
    titles = res.get("titles") or res.get("title") or []
    if isinstance(titles, dict):
        return titles
    return titles[0] if titles else {}


def _pick(res: dict, *keys):
    """Premier champ non vide parmi plusieurs noms possibles."""
    for k in keys:
        v = res.get(k)
        if v not in (None, "", [], {}):
            return v
    return ""


def _fmt_date(v) -> str:
    """Normalise une date PISTE (epoch ms, ISO, ou 'YYYY-MM-DD') en DD/MM/YYYY."""
    if not v:
        return ""
    if isinstance(v, (int, float)):  # epoch millisecondes
        import datetime as _dt
        try:
            return _dt.datetime.utcfromtimestamp(v / 1000).strftime("%d/%m/%Y")
        except (ValueError, OSError):
            return ""
    s = str(v)
    m = _re_iso.match(s)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else s


import re as _re
_re_iso = _re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_tag_re = _re.compile(r"<[^>]+>")
_CONSTIT_TYPES = _re.compile(r"D[eé]cision\s+\S+\s+(QPC|DC)\b")  # type juste après le n° (≠ ELEC/AN/SEN…)


def _strip_html(v):
    """PISTE surligne le terme cherché avec des <mark>…</mark> → on nettoie le HTML."""
    return _tag_re.sub("", v).strip() if isinstance(v, str) else v


_auteur_re = _re.compile(
    r"^\s*((?:M\.|Mme|MM\.|Mlle)\s+.{2,60}?)\s+"
    r"(?:interroge|attire|appelle|demande|rappelle|souhaite|expose|alerte|interpelle|saisit|signale)"
)


def _question_auteur(texte: str) -> str:
    """Extrait l'auteur au début du texte d'une question (« Mme X interroge… »)."""
    if not isinstance(texte, str):
        return ""
    m = _auteur_re.match(_strip_html(texte))
    return m.group(1).strip() if m else ""


def _question_url(chambre: str, legislature, numero) -> str:
    """Permalien officiel — construit seulement quand on en est sûr (AN)."""
    if chambre == "AN" and legislature and numero:
        return f"https://questions.assemblee-nationale.fr/q{legislature}/{legislature}-{numero}QE.htm"
    return ""  # Sénat : format d'UID non garanti ici → pas de lien plutôt qu'un lien cassé


def _legi_url(identifiant: str) -> str:
    """Construit le permalien Légifrance selon le préfixe de l'identifiant."""
    prefix = identifiant[:8]
    base = {
        "CETATEXT": "ceta", "JURITEXT": "juri", "CONSTEXT": "cnst",
        "CNILTEXT": "cnil", "JORFTEXT": "jorf", "LEGIARTI": "loda",
        "LEGITEXT": "loda",
    }.get(prefix)
    return f"https://www.legifrance.gouv.fr/{base}/id/{identifiant}" if base else ""


def _normalize_piste_hits(data: dict) -> list[dict]:
    """Aplati la réponse PISTE /search en dicts normalisés (LODA + jurisprudence)."""
    out = []
    for res in data.get("results", []):
        t = _first_title(res)
        identifiant = _pick(t, "id") or _pick(res, "id")
        out.append({
            "id": identifiant,
            "title": _strip_html(_pick(t, "title") or _pick(res, "title")),
            "nor": _pick(res, "nor"),
            "num": _pick(res, "num", "numero"),
            # dates : LODA (signature/publication) vs jurisprudence (décision)
            "date_pub": _fmt_date(_pick(res, "datePublication", "datePubli")),
            "date_sig": _fmt_date(_pick(res, "dateSignature", "dateSignaTexte")),
            "date": _fmt_date(_pick(res, "date", "dateDecision", "datePublication")),
            # jurisprudence
            "juridiction": _pick(res, "juridiction", "origin", "origine"),  # ?
            "formation": _pick(res, "formation"),                            # ?
            "numero_affaire": _pick(res, "numeroAffaire", "numeros", "numero"),  # ?
            "solution": _pick(res, "solution", "type"),                      # ?
            "url": _legi_url(identifiant),
        })
    return out


def _jur_kind(fond: str) -> str:
    return {"CETAT": "Conseil d'État", "JURI": "Cour de cassation",
            "CONSTIT": "Conseil constit.", "CNIL": "Délibération CNIL"}.get(fond, "Décision")
