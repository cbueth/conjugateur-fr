## Conjugateur FR (table + IPA)

Ce repo génère :

- **Une démo HTML générée (v8)** : `french_conjugator_v8.py` → `french_conjugations.html`
- **Un site statique interactif (Pages)** : `docs/` (ouvrez `docs/index.html`)

### Pré-requis

- Python via `./.venv/bin/python`
- Données Kaikki/Wiktionary : `fr-extract.jsonl.gz`
- Données de fréquence Lexique : `lexique.tsv`

### Liens (placeholders)

- Dépôt Codeberg : `https://codeberg.org/cbueth/conjugateur-fr`
- Pages Codeberg : `https://cbueth.codeberg.page/conjugateur-fr/` (à ajuster si besoin)
- Issues : `https://codeberg.org/cbueth/conjugateur-fr/issues`

### Build (site Pages)

Téléchargement du dump (si absent) + build complet :

- `make build-pages`

Les fichiers générés sont :

- `docs/data/manifest.json`
- `docs/data/most_common_verbs.json.gz` (200 verbes les plus fréquents)
- `docs/data/common_verbs.json.gz` (2300 verbes fréquents)
- `docs/data/letter_chunks/*.json.gz` (chargement gzip côté navigateur)

### Build (Démo)

- `make build-demo`

### Ouvrir

- Pages : ouvrez `docs/index.html` dans le navigateur
- Démo : ouvrez `french_conjugations.html`

### Notes

- L'audio AudioFrench est en `http://` (pas `https://`) : selon l'hébergement, le navigateur peut bloquer la lecture (mixed content). Les liens MP3 restent ouvrables.

## Attribution et remerciements

Ce projet utilise les données et ressources suivantes :

### Données de conjugaison et prononciation

- **Wiktextract** par Tatu Ylonen : extraction structurée des données Wiktionnaire  
  *Citation* : Tatu Ylonen: Wiktextract: Wiktionary as Machine-Readable Structured Data, Proceedings of the 13th Conference on Language Resources and Evaluation (LREC), pp. 1317-1325, Marseille, 20-25 June 2022.  
  [PDF](http://www.lrec-conf.org/proceedings/lrec2022/pdf/2022.lrec-1.140.pdf) | [kaikki.org](https://kaikki.org)

- **Wiktionnaire** (Wikimedia Foundation) : conjugaisons et fichiers audio des infinitifs sous licence [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)

### Données de fréquence

- **Lexique** : base de données des fréquences lexicales du français  
  [lexique.org](http://www.lexique.org/) — fréquences combinées corpus film + livres

### Audio

- **AudioFrench.com** : fichiers audio des formes conjuguées (présent, imparfait, futur)  
  © 2004-2017 AudioFrench.com

### Remerciements

Un grand merci à toutes les personnes ayant contribué aux données ouvertes du Wiktionnaire français et aux projets permettant leur exploitation automatisée.
