"""API HTTP — sert le front et expose /constellation.

Lancer :  uvicorn backend.api:app --reload
Le front (frontend/index.html) appelle GET /constellation?q=... et injecte le
JSON dans son moteur de rendu (constellation + timeline).
"""
from __future__ import annotations

import os

from backend.env import load_env
load_env()  # charge .env avant l'import de cache.py (qui lit DEMO_MODE à l'import)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.cache import CacheMiss
from backend.orchestrator import constellation

app = FastAPI(title="La loi après la loi", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


from backend.plugins import load_adapter


def _adapter():
    """Adaptateur actif via BACKEND=reference|silexia (défaut: reference)."""
    return load_adapter()


@app.get("/constellation")
def get_constellation(q: str = Query(..., min_length=2, description="Loi en langage naturel ou n°")):
    try:
        c = constellation(q, _adapter())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CacheMiss:  # démo hors-ligne : requête non pré-chauffée
        raise HTTPException(
            status_code=503,
            detail="Requête non préparée pour la démo hors-ligne. Essayez « la loi plein emploi » ou « loi immigration ».",
        )
    except Exception as e:  # noqa: BLE001 — remonter une erreur actionnable au front
        raise HTTPException(status_code=502, detail=f"Source indisponible : {e}")
    return JSONResponse(c.to_front())


# Sert le front en dernier (après les routes API).
_front = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_front):
    app.mount("/", StaticFiles(directory=_front, html=True), name="front")
