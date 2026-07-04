# Front

`index.html` (constellation + parcours + badges de provenance) est l'UI du défi.
La **barre de recherche en langage naturel** est câblée sur le backend : elle
reconstruit dynamiquement la constellation d'une loi à partir d'une saisie libre.

## Barre NL (fait)

La barre (`#nlform` / `#nlq` / bouton « Explorer ») appelle
`GET /constellation?q=<saisie>` puis injecte la réponse dans le moteur de rendu
existant, sans rien coder en dur :

```js
async function chargerLoi(saisie) {
  const r = await fetch(`${API_BASE}/constellation?q=${encodeURIComponent(saisie)}`);
  if (!r.ok) { /* statut d'erreur actionnable dans #nl-status */ return; }
  LAWS['_live'] = adapt(await r.json(), saisie);  // mappe → structure interne
  current = '_live';
  renderPills(); renderLaw();                     // rendu constellation + parcours
}
```

- `adapt()` mappe la sortie `/constellation` (`related[]`, `counts`, identifiants +
  `prov`, `url`) vers la structure de carte du proto. Le back renvoie déjà
  `related[]` au format attendu par `renderLaw()` — pas de retraitement.
- `API_BASE` vaut `''` (même origine, cas nominal : le front est servi par
  l'API FastAPI). En dev via `http.server:8181`, il cible `http://127.0.0.1:8000`.
- État de chargement + erreurs : ligne `#nl-status` (spinner / « ✓ N textes
  rattachés » / message actionnable). Jamais d'`alert()`.
- Les **pastilles** sous la barre (`#lawpills`) sont désormais des **exemples /
  historique** : lois de démo pré-rendues + la dernière recherche live (`_live`).
- `#q` (barre de la toolbar) reste le **filtre local** de la fiche affichée.

## Servir le front + l'API

Le front est servi par l'API (même origine), donc `/constellation` fonctionne
sans CORS :

```
py -m uvicorn backend.api:app --port 8000   # http://localhost:8000/
```

(ou, côté éditeur, le serveur `loi-api` de `.claude/launch.json`.)

## Cible du défi

La barre n'est plus un filtre local mais une **recherche en langage naturel** :
« la loi plein emploi », « loi immigration 2024 », « 2023-1196 » → la
constellation se peuple depuis les sources officielles, chaque nœud portant un
identifiant vérifiable et cliquable.
