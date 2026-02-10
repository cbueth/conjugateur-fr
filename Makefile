.PHONY: help download-data build-pages-full build-pages-limit build-demo build-all clean

PY := ./.venv/bin/python
DATA_URL := https://kaikki.org/dictionary/downloads/fr/fr-extract.jsonl.gz
DATA_FILE := fr-extract.jsonl.gz

help:
	@echo "Targets:"
	@echo "  download-data        Download $(DATA_FILE) if missing"
	@echo "  build-pages-full     Build docs/data/verbs.json (+ .gz) from fr-extract.jsonl.gz"
	@echo "  build-pages-limit    Build with LIMIT=N (default 2000)"
	@echo "  build-demo           Build french_conjugations.html demo"
	@echo "  build-all            Build pages + demo"
	@echo "  clean                Remove generated artifacts"

download-data: $(DATA_FILE)

$(DATA_FILE):
	@echo "Downloading $(DATA_FILE)…"
	@if command -v curl >/dev/null 2>&1; then \
		curl -L --fail --progress-bar -o "$(DATA_FILE)" "$(DATA_URL)"; \
	elif command -v wget >/dev/null 2>&1; then \
		wget -O "$(DATA_FILE)" "$(DATA_URL)"; \
	else \
		echo "Error: need curl or wget to download $(DATA_URL)"; \
		exit 1; \
	fi

build-pages-full: $(DATA_FILE)
	$(PY) build_github_pages.py

LIMIT ?= 2000
build-pages-limit: $(DATA_FILE)
	$(PY) build_github_pages.py --limit $(LIMIT)

build-demo:
	$(PY) french_conjugator_v8.py

build-all: build-pages-full build-demo

clean:
	rm -f docs/data/manifest.json french_conjugations.html
	rm -f docs/data/verbs.json docs/data/verbs.json.gz
	rm -rf docs/data/chunks
