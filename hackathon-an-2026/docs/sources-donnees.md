# Sources & répartition des données

Chaque branche de la constellation est alimentée par une source ouverte, avec un
identifiant vérifiable pour chaque élément affiché.

| Branche | Donnée | Source | Statut catalogue hackathon |
|---|---|---|---|
| **Application** | Décrets/arrêtés + statut d'application | Échéancier DOLE (`premier-ministre-dole`), JORF (`premier-ministre-jorf`) | ✅ Ressource hackathon |
| **Connexes** | Lois, codes, ordonnances liés | LEGI consolidé (`premier-ministre-legi`) | ✅ Ressource hackathon |
| **Parlement** | Questions écrites AN + Sénat | `an-questions-gouvernement-ecrites`, `senat-questions-gouvernement` | ✅ Ressource hackathon |
| **Amont** (bonus timeline) | Dépôt, amendements, votes | Dossiers/amendements/votes AN via API unifiée | ✅ Ressource hackathon |
| **Jurisprudence** | CE, Cassation, Conseil constit., CNIL | API PISTE de Légifrance | ⚠️ Source ouverte externe (hors catalogue) |
| **Doctrine** | Articles, thèses en accès ouvert | HAL (archives-ouvertes.fr) | ⚠️ Source ouverte externe (hors catalogue) |

Accès aux données du hackathon via l'API unifiée
(`an-et-co-api-regroupement-toutes-donnees` / `legiwatch-api-parlement`), qui
agrège LEGI, JORF, DOLE et les données parlementaires.

**Principe de traçabilité.** Amont, application, consolidé et parlement
proviennent des données ouvertes du hackathon. Jurisprudence et doctrine, que le
catalogue ne couvre pas, proviennent de sources ouvertes complémentaires (PISTE,
HAL). Toutes sous Licence Ouverte / accès ouvert.
