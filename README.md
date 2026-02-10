## Conjugateur FR (table + IPA)

Ce repo génère :

- **Une démo HTML générée (v8)** : `french_conjugator_v8.py` → `french_conjugations.html`
- **Un site statique interactif (Pages)** : `docs/` (ouvrez `docs/index.html`)

### Pré-requis

- Python via `./.venv/bin/python`
- Données Kaikki/Wiktionary : `fr-extract.jsonl.gz`

### Liens (placeholders)

- Dépôt Codeberg : `https://codeberg.org/cbueth/conjugateur-fr`
- Pages Codeberg : `https://cbueth.codeberg.page/conjugateur-fr/` (à ajuster si besoin)
- Issues : `https://codeberg.org/cbueth/conjugateur-fr/issues`

### Build (site Pages)

Téléchargement du dump (si absent) + build complet :

- `make build-pages-full`

Build avec sous-ensemble :

- `make build-pages-limit LIMIT=2000`

Les fichiers générés sont :

- `docs/data/manifest.json`
- `docs/data/chunks/verbs_XXXX.json.gz` (chargement gzip côté navigateur)

### Build (Démo)

- `make build-demo`

### Ouvrir

- Pages : ouvrez `docs/index.html` dans le navigateur
- Démo : ouvrez `french_conjugations.html`

### Notes

- L’audio AudioFrench est en `http://` (pas `https://`) : selon l’hébergement, le navigateur peut bloquer la lecture (mixed content). Les liens MP3 restent ouvrables.
