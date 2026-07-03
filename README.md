# La loi après la loi

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

> Relier chaque texte voté à sa vie réglementaire et jurisprudentielle.
> Défi du Hackathon Assemblée nationale 2026 — *« Le parcours de la loi : vers une IA de confiance »*.

L'open data parlementaire documente admirablement la loi **jusqu'à sa
promulgation**. Après, le fil se coupe : décrets d'application, jurisprudence,
doctrine et questions parlementaires vivent dans des silos séparés. Ce projet
reconstruit cette **constellation aval** à partir d'une simple recherche en
langage naturel — et **chaque nœud porte un identifiant officiel vérifiable**.
C'est le sens de « IA de confiance » : zéro affirmation non sourcée.

## Les cinq branches de la constellation

| Cluster | Contenu | Source (adaptateur `canutes`) | Mode de liaison |
|---|---|---|---|
| **Application** | Décrets, arrêtés **+ statut d'application** | Échéancier DOLE (API Canutes) | échéancier officiel |
| **Connexes** | Lois, codes, ordonnances liés | API Canutes | liens Légifrance |
| **Parlement** | Questions écrites AN/Sénat | API Canutes / open data | thématique (mots-clés) |
| **Jurisprudence** | CE, Cass., Conseil constit., CNIL | Légifrance PISTE *(hors ressources hackathon)* | citation du n° de loi |
| **Doctrine** | Articles, thèses | HAL | thématique (mots-clés) |

> Répartition retenue : **amont + application + consolidé + parlement → open data
> du hackathon (API Canutes)** ; **jurisprudence + doctrine → sources propres**
> (aucune ressource hackathon ne les couvre). L'échéancier DOLE donne le
> **reste-à-appliquer** (mesures publiées / en attente) — l'angle « contrôle de
> l'application des lois ».

## Architecture (open-core)

Le code du défi tourne **entièrement sur données ouvertes**. Les connecteurs
Silexia de production sont une implémentation *alternative et optionnelle* du
même contrat — un backend premium interchangeable, non requis pour reproduire
la démo.

```
                    barre langage naturel
                            │
                    expansion (n° + mots-clés)
                            │
                     orchestrator.constellation()
                            │  (chaque appel passe par le cache)
        ┌───────────────────┼───────────────────────────┐
   CanutesAdapter      ReferenceAdapter            SilexiaAdapter
   (open data          (tout PISTE + HAL,          (MCP prod,
    hackathon,          sans Canutes)               plugin privé,
    recommandé)                                     optionnel)
        └───────────────────┴───────────────────────────┘
                     Constellation → front (constellation + timeline)
```

`CanutesAdapter` est l'adaptateur recommandé : il source l'aval (application,
connexes, parlement) et l'amont via l'API ouverte du hackathon, et ne délègue à
PISTE que la **jurisprudence** (+ HAL pour la doctrine). `BACKEND=canutes`.

Voir [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) et
[`docs/SOURCES.md`](docs/SOURCES.md).

## Ce qui est déjà validé (en live, loi 2023-1196)

- **Application** par recherche VISA sur le n° de loi → 19 décrets. ✅
  *Ne pas* passer par les liens de `consult_jorf_text` : **HTTP 500** sur les
  grosses lois.
- **Jurisprudence** CETAT sur le n° de loi → décisions du Conseil d'État. ✅
- **Doctrine** HAL (collection droit national) → articles sur le cœur du texte. ✅
- **Parlement** questions AN + Sénat par mots-clés. ✅ (sensible aux termes →
  d'où la couche d'expansion.)

## Démarrage

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # BACKEND=canutes ; PISTE_* requis pour la jurisprudence

# API + front (adaptateur canutes par défaut)
uvicorn backend.api:app --reload      # http://localhost:8000

# ou serveur MCP (pour un agent)
python -m backend.mcp_server
```

### Pitch : mode démo (sans PISTE live)

```bash
DEMO_MODE=0 python -m backend.warmup "loi plein emploi"   # réchauffe le cache
DEMO_MODE=1 uvicorn backend.api:app                       # lecture seule cache
```

### Tests

```bash
python -m tests.test_piste_mapping     # sans réseau, sur fixture
# ou : pytest tests/
```

Le mapping PISTE du cluster **jurisprudence** est implémenté et testé hors-ligne.
Pour le valider contre l'API réelle : remplacer `tests/sample_piste_cetat.json`
par une réponse live de PISTE `/search` (fond CETAT) et relancer — si un assert
casse, ajuster les champs marqués « ? » dans `_normalize_piste_hits`.

## Statut du squelette

Structure complète et exécutable. Mapping PISTE **jurisprudence** fait et testé.
Restent en `TODO(24h)` : confirmer les endpoints de l'API **Canutes** sur la doc
OpenAPI, compléter la doctrine (Isidore/BOFiP), la bascule LLM de l'expansion, et
le câblage final du front sur `/constellation` (voir `frontend/README.md`).

## Adaptateur premium (non inclus)

Ce dépôt public n'embarque que l'adaptateur de **référence** (open data). Un
adaptateur **Silexia** optionnel — qui branche l'orchestrateur sur des
connecteurs MCP de production — existe mais est distribué séparément. Il n'est
pas requis : le défi est intégralement reproductible sur données ouvertes.

Pour l'activer dans un déploiement privé, on dépose `silexia.py` dans
`backend/adapters/` puis on lance `BACKEND=silexia` ; sinon, `plugins.load_adapter`
renvoie un message d'erreur explicite. Le contrat qu'il implémente est public
([`backend/adapters/base.py`](backend/adapters/base.py)) — seule l'implémentation
premium ne l'est pas.

## Licence

**AGPL-3.0-or-later** — voir [`LICENSE`](LICENSE). Toute exploitation en SaaS
d'une version modifiée doit rouvrir ses modifications. La licence couvre le code
de ce dépôt ; un service distant appelé via API (ex. connecteurs Silexia) reste
un programme indépendant sous sa propre licence.
