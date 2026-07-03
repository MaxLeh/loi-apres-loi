# Sources & ouverture des données

Toutes les données mobilisées par l'adaptateur de référence sont ouvertes.

| Source | Contenu | Ouverture / licence | Accès |
|---|---|---|---|
| **API Canutes-Légifrance** (Tricoteuses/LegiWatch) | Textes promulgués + consolidés, **échéancier DOLE**, amont parlementaire (dossiers, amendements, votes), questions | Licence Ouverte | API REST JSON, **sans clé** — ressource officielle du hackathon |
| **Légifrance (API PISTE)** | Jurisprudence CETAT/JURI/CONSTIT/CNIL *(cluster jurisprudence)* | Licence Ouverte Etalab 2.0 | OAuth2, clé gratuite sur piste.gouv.fr |
| **HAL** (archives-ouvertes.fr) | Doctrine en accès ouvert (articles, thèses) | Dépôts sous droits de leurs auteurs ; API ouverte | API publique, sans clé |
| **Isidore** (Huma-Num) | Doctrine SHS multi-plateformes (OpenEdition, Persée…) | Notices ouvertes ; plein-texte selon source | API publique |
| **BOFiP** | Doctrine fiscale officielle | Données publiques | API |
| **DOLE** (dossiers législatifs) | Échéancier d'application des lois | Licence Ouverte Etalab | via API Canutes (ou dumps data.gouv) |

## Notes de reproductibilité

- **Clé PISTE requise** : l'API Légifrance impose une inscription (gratuite).
  Les données restent ouvertes ; seul le client est authentifié. Pour une
  reproductibilité sans clé, une variante peut pointer vers les **dumps LEGI /
  JORF** publiés sur data.gouv.fr (plus lourd à mettre en œuvre).
- **HAL** est le maillon 100 % ouvert et sans clé — d'où son rôle de preuve
  d'ouverture dans l'adaptateur de référence.

## Ce que la doctrine n'est PAS

La doctrine propriétaire (Dalloz, LexisNexis…) est **hors périmètre** : non
ouverte, non incluse. Le cluster doctrine s'appuie exclusivement sur des
sources ouvertes (HAL, Isidore, BOFiP).
