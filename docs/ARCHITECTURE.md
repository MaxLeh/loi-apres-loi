# Architecture

## Flux d'une requête

1. **Saisie** en langage naturel (« loi plein emploi ») ou n° (« 2023-1196 »).
2. **`resolve_loi`** → identifiants complets (LEGITEXT, NOR, JORFTEXT).
3. **`expansion.expand`** → `{numero, mots_cles}`.
   - `numero` alimente les clusters par **citation** (application, jurisprudence, connexes).
   - `mots_cles` alimentent les clusters **thématiques** (doctrine, parlement).
4. **Cinq recherches** de clusters, chacune passée par `cache.cached(...)`.
5. **Assemblage** en `Constellation`, filtrage des nœuds sans identifiant,
   sérialisation `to_front()` pour le moteur de rendu.

## Le split open-core

`ConnectorAdapter` (abstrait) définit six méthodes : `resolve_loi` + un cluster
chacun. Trois implémentations :

- **`CanutesAdapter`** *(recommandé)* — source l'aval (application via échéancier
  DOLE, connexes, parlement) et l'amont via l'**API Canutes** ouverte du
  hackathon ; délègue la **jurisprudence** à PISTE et la **doctrine** à HAL (via
  un `ReferenceAdapter` composé). Neutralise la fragilité PISTE sur l'aval.
- **`ReferenceAdapter`** — variante « tout PISTE + HAL », sans Canutes.
  Utile en repli ou pour comparer.
- **`SilexiaAdapter`** — wrappe les connecteurs MCP Silexia via un client injecté.
- **`SilexiaAdapter`** — wrappe les connecteurs MCP Silexia via un client
  injecté (`call(tool, params)`). Plus rapide, plus robuste, supporté. **Non
  requis** pour la démo, et **livré séparément** : absent du dépôt public, il se
  dépose dans `backend/adapters/silexia.py` côté déploiement privé. Le sélecteur
  `backend/plugins.load_adapter` le charge s'il est présent, sinon renvoie une
  erreur actionnable.

Frontière : ce qui est publié = la logique de constellation, l'orchestration,
l'expansion, le cache, l'UI, et l'adaptateur de référence. Ce qui reste fermé =
les connecteurs Silexia de prod (antérieurs au hackathon, hors périmètre du
défi).

## Expansion de requête

La recherche plein-texte est **sensible aux termes** (constat live : « revenu
solidarité active sanction » remonte des questions, « RSA suspension contrat
d'engagement » n'en remonte aucune). L'expansion découple donc la liaison par
citation (robuste, sur le n°) de la liaison thématique (fragile, sur les mots).
MVP heuristique ; cible : dérivation LLM (Haiku) avec synonymes et sigles.

## Cache & robustesse PISTE

PISTE renvoie des **500 transitoires** (observés en préparation). Deux parades :

- `ReferenceAdapter._piste` : retry exponentiel (`tenacity`) sur les ≥500.
- `cache.cached` : mémoïsation disque. En `DEMO_MODE=1`, lecture seule — le
  pitch ne touche jamais l'API. Réchauffage via `backend.warmup`.

## Traçabilité (exigence du défi)

Tout nœud sans `identifiant` est **écarté** à l'assemblage. Un nœud non sourçable
n'existe pas. C'est ce qui distingue la constellation d'un résumé génératif.

## Points ouverts (`TODO(24h)`)

- Confirmer les endpoints de l'API Canutes sur la doc OpenAPI (`canutes_client`).
- Cluster parlement open data (AN + Sénat) dans `ReferenceAdapter`.
- Isidore + BOFiP en complément doctrine.
- `expand_llm` (bascule Haiku).
- Câblage front → `/constellation` (voir `frontend/README.md`).

Fait : mapping PISTE du cluster jurisprudence (`_normalize_piste_hits`), testé
hors-ligne (`tests/test_piste_mapping.py`).
