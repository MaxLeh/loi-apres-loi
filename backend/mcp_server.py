"""Serveur MCP — expose la constellation comme un outil pour agents.

Permet à un assistant (Claude, etc.) d'appeler `constellation` en langage
naturel et de récupérer, pour une loi, tous ses textes rattachés avec leurs
identifiants vérifiables. Lecture seule.

Lancer (stdio) :  python -m backend.mcp_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from backend.orchestrator import constellation

mcp = FastMCP("loi-apres-loi")


@mcp.tool()
def constellation_loi(saisie: str) -> dict:
    """Reconstitue la « vie » d'une loi promulguée après sa publication.

    À partir d'une loi (n° comme « 2023-1196 » ou intitulé en langage naturel),
    renvoie ses décrets/arrêtés d'application, sa jurisprudence (CE, Cass.,
    Conseil constit., CNIL), sa doctrine (HAL/Isidore) et les questions
    parlementaires liées — chaque élément avec un identifiant officiel
    vérifiable et sa provenance. Lecture seule.

    Args:
        saisie: numéro de loi ou intitulé (« loi plein emploi »).
    """
    from backend.plugins import load_adapter
    return constellation(saisie, load_adapter()).to_front()


if __name__ == "__main__":
    mcp.run()
