"""Client de l'API Canutes-Légifrance (Tricoteuses / LegiWatch).

API REST JSON sous Licence Ouverte, ressource officielle du hackathon. Elle
agrège Légifrance (textes promulgués ET consolidés), le DOLE (échéancier
d'application) et l'amont parlementaire (dossiers, amendements, votes) reconstruits
depuis les dépôts Git de l'AN et du Sénat.

⚠️ Les chemins d'endpoints ci-dessous sont des PLACEHOLDERS : la doc OpenAPI est
protégée par un anti-bot et n'a pas pu être lue automatiquement. À confirmer en
navigateur :
    https://www.tricoteuses.fr/services/api-canutes-legifrance/documentation
Chaque appel est isolé dans une méthode pour que le recâblage se fasse à un seul
endroit une fois les vrais chemins connus.

Avantage vs PISTE : pas d'OAuth, pas de 500 transitoires sur les grosses lois,
et l'échéancier DOLE donne le STATUT d'application (publié / en attente) — bien
plus riche que la simple recherche VISA.
"""
from __future__ import annotations

import os
import httpx

CANUTES_BASE = os.environ.get("CANUTES_BASE_URL", "https://api.canutes.tricoteuses.fr")  # TODO: confirmer


class CanutesClient:
    def __init__(self, base_url: str | None = None):
        self.base = (base_url or CANUTES_BASE).rstrip("/")
        self._http = httpx.Client(timeout=30.0, headers={"Accept": "application/json"})

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        r = self._http.get(f"{self.base}{path}", params=params or {})
        r.raise_for_status()
        return r.json()

    # ---------- résolution ----------
    def resolve_loi(self, q: str) -> dict:
        """Résout une saisie (n° ou intitulé) en métadonnées de loi.

        TODO(doc) : endpoint réel. Placeholder : /lois?q=... → premier hit.
        Retour attendu (à mapper) : numero, titre, legitext, jorftext, nor,
        date_signature, date_publication.
        """
        data = self._get("/lois", {"q": q, "limit": 1})  # TODO: chemin/params réels
        items = data.get("results", data) if isinstance(data, dict) else data
        return items[0] if items else {}

    # ---------- application (échéancier DOLE) ----------
    def echeancier(self, loi_id: str) -> list[dict]:
        """Mesures d'application attendues + statut (le cœur du cluster app).

        TODO(doc) : endpoint réel. Placeholder : /lois/{id}/echeancier.
        Retour attendu par mesure : titre, type (decret/arrete), reference
        (JORFTEXT/LEGITEXT si publié), statut (publie/en_attente), date.
        """
        data = self._get(f"/lois/{loi_id}/echeancier")  # TODO: chemin réel
        return _as_list(data)

    # ---------- connexes ----------
    def textes_lies(self, loi_id: str) -> list[dict]:
        """Lois / codes / ordonnances liés (cluster connexes).

        TODO(doc) : endpoint réel. Placeholder : /lois/{id}/liens.
        """
        data = self._get(f"/lois/{loi_id}/liens")  # TODO
        return _as_list(data)

    # ---------- parlement (questions écrites) ----------
    def questions(self, mots_cles: list[str], loi_id: str | None = None) -> list[dict]:
        """Questions écrites AN + Sénat liées au sujet de la loi.

        TODO(doc) : endpoint réel. Placeholder : /questions?q=...
        Retour attendu : titre, uid, chambre, auteur, date_question, statut, url.
        """
        params = {"q": " ".join(mots_cles), "limit": 8}
        if loi_id:
            params["loi"] = loi_id
        data = self._get("/questions", params)  # TODO
        return _as_list(data)

    # ---------- amont (bonus) ----------
    def dossier_legislatif(self, loi_id: str) -> dict:
        """Amont parlementaire : dépôt, amendements clés, scrutins (bonus timeline).

        TODO(doc) : endpoint réel. Placeholder : /dossiers/{id}.
        """
        return self._get(f"/dossiers/{loi_id}")  # TODO


def _as_list(data) -> list[dict]:
    if isinstance(data, dict):
        return data.get("results", data.get("items", []))
    return data if isinstance(data, list) else []
