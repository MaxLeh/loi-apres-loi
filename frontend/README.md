# Front

Le prototype `loi_hub_adaptatif.html` (constellation + timeline + badges de
provenance) est le socle UI. Deux étapes pour le rendre vivant :

1. ✅ **Fait** — le proto est intégré ici sous `index.html` (4 lois codées en
   dur : LFI 2026, statut de l'élu local, plein emploi, liberté de la presse 1881).
2. **Remplacer** l'objet `LAWS` codé en dur par un appel à `/constellation`,
   piloté par la barre de recherche.

## Câblage minimal

Le back renvoie déjà le format attendu par le moteur de rendu (`related[]`,
`counts`, identifiants + `prov`). Il suffit de brancher la barre :

```js
async function chargerLoi(saisie) {
  const r = await fetch(`/constellation?q=${encodeURIComponent(saisie)}`);
  if (!r.ok) { alert("Loi introuvable ou source indisponible"); return; }
  const data = await r.json();
  LAWS["_live"] = adapt(data);   // injecte dans le moteur existant
  current = "_live";
  renderLaw();
}

// mappe la sortie /constellation vers la structure interne du proto
function adapt(d) {
  return {
    pillName: "LOI " + d.numero, pillDesc: d.numero,
    short: d.numero, title: d.title, subt: d.subt, dom: d.dom,
    legitext: d.legitext, nor: d.nor, sig: d.sig, pub: d.pub,
    measures: [], toc: [],            // TODO(24h) : dériver KPIs / plan
    related: d.related,               // déjà au bon format (f, badge, id, prov…)
  };
}

// barre de recherche → recherche en langage naturel
document.getElementById("q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") chargerLoi(e.target.value.trim());
});
```

## Cible du défi

La barre n'est plus un filtre local mais une **recherche en langage naturel** :
« la loi plein emploi », « RSA 2023 », « loi SREN » → la constellation se
peuple dynamiquement depuis les sources officielles. Le sélecteur de lois codé
en dur devient un simple historique des recherches.
