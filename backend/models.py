"""Modèle de données de « La loi après la loi ».

Le contrat de sortie est calé sur le front `loi_hub_adaptatif.html` : chaque
loi porte ses identifiants + un tableau `related[]` de nœuds, chaque nœud
appartenant à un cluster et portant un identifiant vérifiable + sa provenance.

Principe directeur du défi : AUCUNE affirmation non sourcée. Tout nœud
expose `identifiant` (JORFTEXT / LEGIARTI / CETATEXT / halId / UID…) et
`provenance`, pour que le lecteur puisse remonter à la source officielle.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class Cluster(str, Enum):
    """Les cinq branches de la constellation (clés alignées sur le front)."""
    APPLICATION = "app"      # décrets / arrêtés d'application
    CONNEXES = "con"         # textes liés (lois, codes, ordonnances de référence)
    DOCTRINE = "doc"         # doctrine / commentaires (HAL, Isidore, BOFiP…)
    JURISPRUDENCE = "jur"    # CE, Cass., Conseil constit., CNIL
    PARLEMENT = "par"        # questions écrites AN/Sénat, travaux, presse instit.


class Provenance(str, Enum):
    """Source officielle d'un nœud — sert au badge de provenance du front."""
    LEGIFRANCE = "legifrance"
    CETAT = "cetat"
    JUDILIBRE = "judilibre"
    CONSTIT = "constit"
    CNIL = "cnil"
    BOFIP = "bofip"
    HAL = "hal"
    ISIDORE = "isidore"
    JURIVEILLE = "juriveille"
    QP = "qp"                # questions parlementaires
    EURLEX = "eurlex"


@dataclass
class Noeud:
    """Un texte rattaché à la loi (une « étoile » de la constellation)."""
    cluster: Cluster
    titre: str
    identifiant: str                 # IDENTIFIANT VÉRIFIABLE — jamais vide
    provenance: Provenance
    kind: str = ""                   # libellé court : « Décret », « Conseil d'État »…
    who: str = ""                    # émetteur : « DGCL / Légifrance »…
    date: str = ""                   # DD/MM/YYYY ou libellé (« en continu »)
    note: str = ""
    url: str = ""                    # lien direct vers la source, si disponible

    def to_front(self) -> dict:
        """Sérialise au format attendu par le moteur de rendu du front."""
        badge = {
            Cluster.APPLICATION: "k-app", Cluster.CONNEXES: "k-con",
            Cluster.DOCTRINE: "k-doc", Cluster.JURISPRUDENCE: "k-jur",
            Cluster.PARLEMENT: "k-par",
        }[self.cluster]
        return {
            "f": self.cluster.value, "badge": badge, "kind": self.kind,
            "title": self.titre, "who": self.who, "date": self.date,
            "id": self.identifiant, "prov": self.provenance.value,
            "note": self.note, "url": self.url,
        }


@dataclass
class Loi:
    """La loi promulguée, point d'entrée de la constellation."""
    numero: str                      # ex. « 2023-1196 »
    titre: str
    legitext: str = ""               # LEGITEXT000…
    jorftext: str = ""               # JORFTEXT000…
    nor: str = ""
    date_signature: str = ""
    date_publication: str = ""
    sous_titre: str = ""
    domaine: str = ""


@dataclass
class Constellation:
    """Résultat complet : la loi + tous ses nœuds rattachés."""
    loi: Loi
    noeuds: list[Noeud] = field(default_factory=list)

    def compte_par_cluster(self) -> dict[str, int]:
        out = {c.value: 0 for c in Cluster}
        for n in self.noeuds:
            out[n.cluster.value] += 1
        return out

    def to_front(self) -> dict:
        """Format consommé directement par `loi_hub_adaptatif.html`."""
        return {
            "numero": self.loi.numero, "title": self.loi.titre,
            "subt": self.loi.sous_titre, "dom": self.loi.domaine,
            "legitext": self.loi.legitext, "nor": self.loi.nor,
            "sig": self.loi.date_signature, "pub": self.loi.date_publication,
            "counts": self.compte_par_cluster(),
            "related": [n.to_front() for n in self.noeuds],
        }
