"""Adaptateur de référence OUVERT, aligné sur les données du hackathon.

Répartition des sources (conclusion de l'analyse des ressources) :
  - résolution, application (échéancier DOLE), connexes, parlement → **Canutes**
    (API ouverte du hackathon, sans clé, sans 500 PISTE) ;
  - jurisprudence (CE, Cass., CC, CNIL) → **PISTE** (aucune ressource hackathon
    ne couvre la jurisprudence) — délégué à `ReferenceAdapter` ;
  - doctrine (HAL) → **HAL** (ouvert, sans clé) — délégué à `ReferenceAdapter`.

C'est l'adaptateur recommandé pour la démo : il maximise la part de données
ouvertes fournies par le hackathon et neutralise la fragilité PISTE sur l'aval.
Seul le cluster jurisprudence requiert encore une clé PISTE.

Bonus : `amont()` reconstitue le début du parcours (dépôt → amendements →
votes) pour allumer la phase amont de la timeline — hors des 5 clusters aval.
"""
from __future__ import annotations

from backend.adapters.base import ConnectorAdapter
from backend.adapters.reference import ReferenceAdapter
from backend.canutes_client import CanutesClient
from backend.models import Loi, Noeud, Cluster, Provenance


class CanutesAdapter(ConnectorAdapter):
    name = "canutes"

    def __init__(self, base_url: str | None = None, jurisprudence_doctrine: ReferenceAdapter | None = None):
        self.canutes = CanutesClient(base_url)
        # ReferenceAdapter fournit jurisprudence (PISTE) + doctrine (HAL).
        self._ref = jurisprudence_doctrine or ReferenceAdapter()

    # ---------- résolution (Canutes) ----------
    def resolve_loi(self, numero_ou_titre: str) -> Loi:
        h = self.canutes.resolve_loi(numero_ou_titre)
        if not h:
            raise ValueError(f"Loi introuvable via Canutes : {numero_ou_titre!r}")
        # TODO(doc) : aligner les clés sur la réponse réelle de l'API.
        return Loi(
            numero=h.get("numero", h.get("num", "")),
            titre=h.get("titre", h.get("title", "")),
            legitext=h.get("legitext", h.get("id", "")),
            jorftext=h.get("jorftext", ""),
            nor=h.get("nor", ""),
            date_signature=h.get("date_signature", h.get("date_sig", "")),
            date_publication=h.get("date_publication", h.get("date_pub", "")),
            sous_titre=h.get("objet", ""),
        )

    # ---------- application (échéancier DOLE, Canutes) ----------
    def cluster_application(self, loi: Loi) -> list[Noeud]:
        loi_id = loi.legitext or loi.numero
        out: list[Noeud] = []
        for m in self.canutes.echeancier(loi_id):
            statut = m.get("statut", "")
            publie = statut.startswith("publi")
            out.append(Noeud(
                cluster=Cluster.APPLICATION,
                titre=m.get("titre", m.get("title", "")),
                # identifiant vérifiable si publié ; sinon référence DOLE de la mesure attendue
                identifiant=m.get("reference", m.get("id", "")) or f"DOLE:{loi.numero}:{m.get('rang', '?')}",
                provenance=Provenance.LEGIFRANCE,
                kind=(m.get("type", "Mesure") or "Mesure").capitalize(),
                who="Échéancier DOLE",
                date=m.get("date", ""),
                note="Publié" if publie else "En attente de publication",
            ))
        return out

    # ---------- connexes (Canutes) ----------
    def cluster_connexes(self, loi: Loi) -> list[Noeud]:
        loi_id = loi.legitext or loi.numero
        out: list[Noeud] = []
        for t in self.canutes.textes_lies(loi_id):
            out.append(Noeud(
                cluster=Cluster.CONNEXES,
                titre=t.get("titre", t.get("title", "")),
                identifiant=t.get("id", t.get("legitext", "")),
                provenance=Provenance.LEGIFRANCE,
                kind=t.get("nature", "Texte lié").capitalize(),
                who="Légifrance (Canutes)",
                date=t.get("date", ""),
            ))
        return out

    # ---------- parlement (questions écrites, Canutes) ----------
    def cluster_parlement(self, loi: Loi, mots_cles: list[str]) -> list[Noeud]:
        loi_id = loi.legitext or loi.numero
        out: list[Noeud] = []
        for q in self.canutes.questions(mots_cles, loi_id=loi_id):
            out.append(Noeud(
                cluster=Cluster.PARLEMENT,
                titre=q.get("titre", q.get("title", "")),
                identifiant=q.get("uid", ""),
                provenance=Provenance.QP,
                kind="Question écrite " + (q.get("chambre", "") or "").upper(),
                who=q.get("auteur", ""),
                date=q.get("date_question", q.get("date", "")),
                note=q.get("statut", ""),
                url=q.get("url", q.get("source", "")),
            ))
        return out

    # ---------- jurisprudence (PISTE, délégué) ----------
    def cluster_jurisprudence(self, loi: Loi) -> list[Noeud]:
        # Aucune ressource hackathon ne couvre la jurisprudence → PISTE.
        return self._ref.cluster_jurisprudence(loi)

    # ---------- doctrine (HAL, délégué) ----------
    def cluster_doctrine(self, loi: Loi, mots_cles: list[str]) -> list[Noeud]:
        return self._ref.cluster_doctrine(loi, mots_cles)

    # ---------- BONUS : amont parlementaire (hors 5 clusters aval) ----------
    def amont(self, loi: Loi) -> list[dict]:
        """Événements amont pour la timeline : dépôt, amendements clés, votes.

        Renvoie une liste d'événements datés (pas des `Noeud` : ils n'appartiennent
        pas aux 5 clusters aval). À injecter dans la phase « amont » de la timeline.
        TODO(doc) : mapper la structure réelle du dossier législatif Canutes.
        """
        loi_id = loi.legitext or loi.numero
        try:
            dossier = self.canutes.dossier_legislatif(loi_id)
        except Exception:  # noqa: BLE001 — amont est un bonus, jamais bloquant
            return []
        evenements = dossier.get("etapes", dossier.get("actes", []))
        return [{
            "date": e.get("date", ""),
            "type": e.get("type", ""),
            "libelle": e.get("libelle", e.get("title", "")),
            "source": "Canutes / dossier législatif",
        } for e in evenements]
