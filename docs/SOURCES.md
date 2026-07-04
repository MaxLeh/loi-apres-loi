# Sources & ouverture des données

L'adaptateur de référence mobilise exclusivement des **données ouvertes**. La
couche IA n'ajoute aucune donnée : elle comprend et classe le matériel sourcé.

| Source | Contenu | Cluster / rôle | Ouverture / licence | Accès |
|---|---|---|---|---|
| **Légifrance (API PISTE)** | Lois (LODA), décrets/arrêtés, jurisprudence `CETAT/JURI/CONSTIT/CNIL` | résolution, application, jurisprudence | Licence Ouverte Etalab 2.0 | OAuth2, clé gratuite sur piste.gouv.fr |
| **HAL** (archives-ouvertes.fr) | Doctrine en accès ouvert (articles, thèses), collection `AO-DROIT` | doctrine | API ouverte ; dépôts sous droits de leurs auteurs | API publique, **sans clé** |
| **`parlement.tricoteuses.fr`** | Questions écrites AN/Sénat | parlement | open data | API REST JSON, **sans clé** |
| **Mistral** (API) | *Aucune donnée* — compréhension de la requête, classification, synthèse | couche LLM | modèle propriétaire (API) ou **open-weight Apache-2.0** (auto-hébergeable) | clé sur console.mistral.ai ; **optionnel** (repli déterministe sans clé) |

## Notes de reproductibilité

- **Clé PISTE requise** : l'API Légifrance impose une inscription (gratuite).
  Les données restent ouvertes ; seul le client est authentifié. Une variante
  sans clé pourrait pointer vers les **dumps LEGI / JORF** de data.gouv.fr
  (plus lourd).
- **HAL** et **`parlement.tricoteuses.fr`** sont les maillons 100 % ouverts et
  sans clé.
- **Mistral est optionnel** : sans `MISTRAL_API_KEY`, la résolution/classification
  bascule sur un repli déterministe (`HeuristicLLM`). Pour la souveraineté, la
  couche `backend/llm.py` accepte un **modèle open-weight auto-hébergé** derrière
  la même interface.

## Sur la nature « IA de confiance »

Appeler une API LLM propriétaire depuis un projet AGPL est licite (appel réseau
à un service tiers — pas une combinaison de code). Pour ce défi (secteur public,
souveraineté), un modèle **open-weight auto-hébergé** est toutefois préférable :
pas d'egress de données juridiques, pleine reproductibilité.

## Ce que la doctrine n'est PAS

La doctrine propriétaire (Dalloz, LexisNexis…) est **hors périmètre** : non
ouverte, non incluse. Le cluster doctrine s'appuie exclusivement sur HAL (accès
ouvert). Isidore et BOFiP sont des compléments possibles (non encore branchés).
