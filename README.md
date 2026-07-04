# La loi après la loi

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

> Relier chaque texte voté à sa vie réglementaire et jurisprudentielle.
> Défi du Hackathon Assemblée nationale 2026 — *« Le parcours de la loi : vers une IA de confiance »*.

L'open data parlementaire documente admirablement la loi **jusqu'à sa
promulgation**. Après, le fil se coupe : décrets d'application, jurisprudence,
doctrine et questions parlementaires vivent dans des silos séparés. Ce projet
reconstruit cette **constellation aval** à partir d'une simple **recherche en
langage naturel** — et **chaque nœud porte un identifiant officiel vérifiable
et cliquable**. C'est le sens de « IA de confiance » : **zéro affirmation non
sourcée**.

## Ce que fait l'application

1. **Barre de recherche en langage naturel** → `GET /constellation?q=…`. On tape
   « la loi plein emploi », « loi immigration 2024 » ou « 2023-1196 ».
2. **Compréhension de la requête** (LLM) : la requête est résolue vers une loi
   **choisie parmi des candidats officiels** (jamais inventée). Requête précise
   → une loi ; requête **thématique** (« renseignement ») → la **famille** des
   lois du domaine, présentée pour exploration.
3. **Reconstruction de la constellation** : cinq branches de textes rattachés,
   chacun avec son identifiant Légifrance/HAL/parlement et son lien source.
4. **Qualification des liens** : chaque texte d'application est classé
   *application / cite la loi / codification* (le bruit est signalé, pas masqué).
5. **Deux vues** : la **constellation** (les relations) et le **parcours**
   (la chronologie, du dépôt à la jurisprudence), textes cliquables vers la source.
6. **Synthèse ancrée** (LLM, étiquetée) : description + points clés résumés
   *uniquement* à partir du matériel sourcé.

## Les cinq branches de la constellation

| Cluster | Contenu | Source | Mode de liaison |
|---|---|---|---|
| **Application** | Décrets, arrêtés + **classification** | Légifrance/PISTE (`LODA_ETAT/VISA` ∪ `JORF`) + LLM | citation du n° **qualifiée** par le LLM |
| **Jurisprudence** | CE, Cass., Conseil constit., CNIL | Légifrance/PISTE (`CETAT/JURI/CONSTIT/CNIL`) | citation du n° (ou de la date pour les lois anciennes) |
| **Doctrine** | Articles, thèses (accès ouvert) | HAL (`api.archives-ouvertes.fr`, collection `AO-DROIT`) | thématique (mots-clés) |
| **Parlement** | Questions écrites AN/Sénat | `parlement.tricoteuses.fr` (open data) | thématique (mots-clés) |
| **Connexes** | Lois, codes, ordonnances liés | — | *à construire* |

## Le « contrat de confiance » : où l'IA intervient (et où non)

L'IA (Mistral — souveraineté FR, **remplaçable par un modèle open-weight
Apache-2.0** derrière la même interface `backend/llm.py`) ne fait que
**comprendre et classer du matériel déjà sourcé**. Elle ne produit jamais un
fait affiché.

- **Résolution** : elle **choisit une loi parmi des candidats PISTE, par son
  indice** (validé ∈ candidats → impossible d'inventer une loi), et distingue
  requête référentielle vs thème (famille).
- **Classification** des textes d'application : *application / citation /
  codification*, avec justification.
- **Synthèse** (description, points clés) : résumé **exclusivement** de
  l'intitulé officiel + des intitulés réels des textes remontés, **étiqueté
  « synthèse IA »**.
- **Jamais** : inventer un texte, un identifiant ou un **chiffre**. Les mesures
  restent des **comptages déterministes**. Sans clé LLM, un **repli
  déterministe** prend le relais (rien ne casse).

## Architecture (open-core)

Le code du défi tourne **entièrement sur données ouvertes** via l'adaptateur de
**référence**. Un adaptateur Silexia de production (connecteurs MCP) est une
implémentation *alternative et optionnelle* du même contrat — non requis.

```
              barre langage naturel  →  GET /constellation?q=…
                            │
        resolve_candidates (PISTE)  →  LLM.rank_laws  (choisit / désambiguïse)
                            │
             orchestrator.constellation()   (chaque appel passe par le cache)
                            │
        ┌───── 5 clusters (adaptateur) ─────┐   →  LLM.classify_application
        │  application · jurisprudence      │   →  LLM.synthesize (ancrée)
        │  doctrine · parlement · connexes  │
        └───────────────────────────────────┘
                            │
        Constellation (loi + nœuds + résolution + synthèse)  →  front
```

- **`ReferenceAdapter`** (`BACKEND=reference`, défaut) — l'adaptateur publié :
  PISTE (application + jurisprudence), HAL (doctrine), `parlement.tricoteuses.fr`
  (parlement). 100 % open data.
- **`backend/llm.py`** — couche LLM **swappable** (`MistralLLM` si
  `MISTRAL_API_KEY`, sinon `HeuristicLLM` déterministe).
- **`SilexiaAdapter`** — connecteurs MCP de prod, plugin **privé optionnel**,
  absent du dépôt public.

Voir [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) et
[`docs/SOURCES.md`](docs/SOURCES.md). Câblage front :
[`frontend/README.md`](frontend/README.md).

## Démarrage

Prérequis : Python 3.11+ (le fichier `.env` est **auto-chargé** par
`backend/env.py`).

```bash
python -m pip install -r requirements.txt
cp .env.example .env    # renseigner PISTE_CLIENT_ID/SECRET (+ MISTRAL_API_KEY conseillé)

# API + front servis en même origine
python -m uvicorn backend.api:app --reload      # http://localhost:8000

# ou serveur MCP (pour un agent)
python -m backend.mcp_server
```

> Windows : utiliser `py` au lieu de `python`, et `$env:PYTHONUTF8=1` pour les
> accents. Un serveur de dev est aussi défini dans `.claude/launch.json`.

### Pitch : mode démo offline (sans réseau)

Le jour du pitch, on ne joue pas contre les API en salle bondée. On réchauffe le
cache une fois, puis on sert en lecture seule :

```bash
DEMO_MODE=0 python -m backend.warmup "la loi plein emploi" "loi immigration" "2023-1196"
DEMO_MODE=1 python -m uvicorn backend.api:app     # 0 appel réseau : PISTE ET LLM servis du cache
```

Une requête non réchauffée renvoie un **503 actionnable** (au lieu d'un résultat
arbitraire).

### Tests

```bash
python -m tests.test_piste_mapping     # sans réseau, sur fixture
```

## Déploiement (cible démo)

PaaS **Scalingo** (FR), domaine `hackathon.silexia.legal`. `Procfile` type :
`web: uvicorn backend.api:app --host 0.0.0.0 --port $PORT`. Variables :
`PISTE_CLIENT_ID/SECRET`, `MISTRAL_API_KEY`, `BACKEND=reference`, `DEMO_MODE=1`.
⚠️ En `DEMO_MODE=1`, le cache doit être présent dans le conteneur (hook
post-déploiement `warmup`, ou cache committé) — les conteneurs sont éphémères.

## Adaptateur premium (non inclus)

Ce dépôt public n'embarque que l'adaptateur de **référence** (open data). Un
adaptateur **Silexia** optionnel — qui branche l'orchestrateur sur des
connecteurs MCP de production — existe mais est distribué séparément. Il n'est
pas requis : le défi est intégralement reproductible sur données ouvertes. On le
dépose dans `backend/adapters/silexia.py` puis on lance `BACKEND=silexia` ;
sinon `plugins.load_adapter` renvoie une erreur explicite. Le contrat qu'il
implémente est public ([`backend/adapters/base.py`](backend/adapters/base.py)).

## Feuille de route

- Cluster **connexes** (lois/codes/ordonnances liés).
- **Pivot réglementaire** : résoudre les régimes sans loi éponyme (une racine
  peut être un décret) + seuil de confiance explicite.
- Qualification **dur/mou** généralisée à tous les clusters.
- Déploiement **open-weight** (souveraineté) derrière `backend/llm.py`.

## Licence

**AGPL-3.0-or-later** — voir [`LICENSE`](LICENSE). Toute exploitation en SaaS
d'une version modifiée doit rouvrir ses modifications. La licence couvre le code
de ce dépôt ; un service distant appelé via API (ex. API Mistral, connecteurs
Silexia) reste un programme indépendant sous sa propre licence.
