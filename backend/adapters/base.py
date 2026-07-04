"""Contrat commun des adaptateurs de données.

Deux implémentations respectent ce contrat (open-core) :
  - `ReferenceAdapter`  → données ouvertes, appels directs, REPRODUCTIBLE par
                          n'importe qui (c'est la version publiée avec le défi).
  - `SilexiaAdapter`    → connecteurs MCP Silexia de production (plus rapides,
                          plus robustes, supportés). Interchangeable.

Le défi tourne entièrement sur `ReferenceAdapter`. `SilexiaAdapter` est un
« backend premium » optionnel : il n'est PAS requis pour reproduire la démo.

Enseignement de la phase de validation (à respecter dans les implémentations) :
  - Le cluster APPLICATION se construit par recherche du n° de loi dans les
    VISA (LODA_ETAT, field_type=VISA), et NON via les liens de
    `consult_jorf_text` — ce dernier renvoie un HTTP 500 sur les grosses lois.
  - APPLICATION / JURISPRUDENCE / CONNEXES se lient par CITATION du n° de loi.
  - DOCTRINE / PARLEMENT se lient par THÈME (mots-clés) : HAL ne connaît pas
    « 2023-1196 », il connaît « conditionnalité du RSA ».
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from backend.models import Loi, Noeud


class ConnectorAdapter(ABC):
    """Interface unique consommée par l'orchestrateur."""

    name: str = "base"

    @abstractmethod
    def resolve_loi(self, numero_ou_titre: str) -> Loi:
        """Résout une saisie utilisateur en une `Loi` (identifiants complets).

        Doit renseigner au minimum : numero, titre, legitext ou jorftext, nor.
        """

    def resolve_candidates(self, saisie: str, size: int = 8) -> list[Loi]:
        """Lois candidates pour la saisie (les plus pertinentes d'abord).

        L'orchestrateur laisse la couche LLM (compréhension) choisir PARMI ces
        candidats déjà sourcés — jamais d'invention. Défaut : la résolution
        top-1 ; les adaptateurs qui savent lister plusieurs candidats surchargent.
        """
        try:
            return [self.resolve_loi(saisie)]
        except ValueError:
            return []

    @abstractmethod
    def cluster_application(self, loi: Loi) -> list[Noeud]:
        """Décrets et arrêtés d'application — via recherche VISA sur le n°."""

    @abstractmethod
    def cluster_jurisprudence(self, loi: Loi) -> list[Noeud]:
        """CE / Cass. / Conseil constit. / CNIL citant la loi."""

    @abstractmethod
    def cluster_doctrine(self, loi: Loi, mots_cles: list[str]) -> list[Noeud]:
        """Doctrine (HAL, Isidore, BOFiP) — recherche thématique."""

    @abstractmethod
    def cluster_parlement(self, loi: Loi, mots_cles: list[str]) -> list[Noeud]:
        """Questions écrites AN/Sénat — recherche thématique."""

    @abstractmethod
    def cluster_connexes(self, loi: Loi) -> list[Noeud]:
        """Textes de référence liés (lois, codes, ordonnances)."""
