# Architecture

## Flux d'une requête (`orchestrator.constellation`)

1. **Saisie** en langage naturel (« la loi plein emploi ») ou n° (« 2023-1196 »).
2. **`adapter.resolve_candidates`** → N lois candidates (PISTE `LODA_ETAT`,
   `nature=LOI`), chacune avec ses identifiants (LEGITEXT, NOR).
3. **`llm.rank_laws`** (caché) → choisit la loi **par son indice** parmi les
   candidats (jamais inventée), avec confiance + justification, et distingue
   requête **référentielle** (une loi) vs **thématique** (`ambiguous=true` +
   `alternatives` = la famille).
4. **`expansion.expand`** → `mots_cles` (dérivés du titre de la loi) pour les
   clusters thématiques.
5. **Cinq recherches** de clusters, chacune passée par `cache.cached(...)`.
6. **`llm.classify_application`** (caché) → qualifie les textes d'application
   *application / citation / codification*.
7. **`llm.synthesize`** (caché) → description + points clés, **ancrés** sur le
   matériel sourcé (jamais de chiffre inventé).
8. **Assemblage** en `Constellation` (loi + nœuds + `resolution` + `synthese`),
   filtrage des nœuds sans identifiant, `to_front()`.

## Couche LLM — le « contrat de confiance » (`backend/llm.py`)

Le LLM ne fait que **comprendre et classer du matériel déjà sourcé**. Interface
**swappable** :

- **`MistralLLM`** si `MISTRAL_API_KEY` (souveraineté FR ; remplaçable par un
  modèle open-weight Apache-2.0 derrière la même interface).
- **`HeuristicLLM`** (repli déterministe, sans réseau) sinon, ou si l'appel échoue.

Garde-fous : la résolution renvoie un **indice validé ∈ candidats** (pas de loi
inventée) ; la classification et la synthèse portent leur **justification** ;
les **mesures** (KPIs) restent des comptages déterministes — l'IA n'émet
**aucun chiffre**. Toutes les sorties LLM sont **cachées** (clé = requête +
identifiants + nom du modèle) → démo offline reproductible.

## Le split open-core

`ConnectorAdapter` (abstrait) définit `resolve_loi` / `resolve_candidates` + un
cluster chacun. Implémentations :

- **`ReferenceAdapter`** *(défaut, `BACKEND=reference`)* — l'adaptateur publié :
  PISTE (application + jurisprudence), HAL (doctrine), `parlement.tricoteuses.fr`
  (parlement). 100 % open data.
- **`SilexiaAdapter`** — wrappe les connecteurs MCP Silexia via un client injecté.
  Plus rapide/robuste, **non requis**, **livré séparément** (absent du dépôt
  public) : il se dépose dans `backend/adapters/silexia.py` côté déploiement privé.

> Note : l'API « Canutes » (Tricoteuses), pressentie côté hackathon, a été
> **écartée** en préparation (résolution non fiable) au profit de PISTE.

## Cluster application : union + classification

- **Union (recall)** : `LODA_ETAT/VISA` (décrets qui *visent* la loi → confirmés)
  **∪** `JORF/ALL` (textes qui citent le n° sans la viser, cas des lois qui
  s'appliquent en modifiant un **code**), dédoublonnés par n° de décret.
- **Classification** : le LLM tranche *application / citation / codification*.
  On ne **jette rien** — on **étiquette**. Le compteur reste l'union ; le front
  signale le bruit (ex. un décret de codification qui cite la loi sans l'appliquer).

## Résolution : référentiel vs thématique

La « confiance » d'un LLM porte sur la **canonicité**, pas sur l'**intention**.
D'où la distinction : n° / intitulé précis → une loi ; thème → une **famille**
de lois distinctes, présentée pour désambiguïsation (le front garde la famille
affichée pendant l'exploration). Les lois **anciennes sans numéro** (ex. 1881)
sont identifiées par `LEGITEXT` + date et citées par leur date dans les clusters.

## Cache & robustesse

- PISTE renvoie des **500 transitoires** → `ReferenceAdapter._piste` retente
  (`tenacity`).
- `cache.cached` : mémoïsation disque (clé = adaptateur/méthode/arguments). En
  `DEMO_MODE=1`, **lecture seule** : le pitch ne touche ni PISTE ni le LLM ;
  une clé absente lève `CacheMiss` → `503`. Réchauffage via `backend.warmup`.
- `backend/env.py` auto-charge `.env` avant l'import de `cache.py`.

## Traçabilité (exigence du défi)

Tout nœud sans `identifiant` est **écarté** à l'assemblage. Un nœud non
sourçable n'existe pas. C'est ce qui distingue la constellation d'un résumé
génératif — et pourquoi les identifiants sont affichés et **cliquables** vers
leur source (constellation **et** parcours).

## Feuille de route

- Cluster **connexes** (lois/codes/ordonnances liés) — actuellement vide.
- Pivot **réglementaire** (racine décret, pas seulement loi) + seuil de confiance.
- Qualification **dur/mou** généralisée à tous les clusters.
- Bascule **open-weight** derrière `backend/llm.py` (souveraineté, reproductibilité).
