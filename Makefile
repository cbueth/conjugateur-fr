.PHONY: help download-data download-lexique build-pages build-demo clean check-data

PY := ./.venv/bin/python
DATA_URL := https://kaikki.org/dictionary/downloads/fr/fr-extract.jsonl.gz
DATA_FILE := fr-extract.jsonl.gz
LEXIQUE_URL := http://www.lexique.org/databases/Lexique383/Lexique383.tsv
LEXIQUE_FILE := lexique.tsv

help:
	@echo "Targets:"
	@echo "  download-data        Download $(DATA_FILE) from Kaikki if missing"
	@echo "  download-lexique     Download $(LEXIQUE_FILE) frequency data"
	@echo "  build-pages          Build docs/data/ with tiered chunking (200 + 2300 + letter chunks)"
	@echo "  build-demo           Build french_conjugations.html demo"
	@echo "  build-all            Build pages + demo"
	@echo "  clean                Remove generated artifacts"
	@echo "  check-data           Verify data files exist and are valid"

download-data: $(DATA_FILE)

download-lexique: $(LEXIQUE_FILE)

check-data: $(DATA_FILE) $(LEXIQUE_FILE)
	@echo "Checking data files..."
	@if [ ! -s "$(DATA_FILE)" ]; then \
		echo "Error: $(DATA_FILE) is empty or missing"; \
		exit 1; \
	fi
	@if [ ! -s "$(LEXIQUE_FILE)" ]; then \
		echo "Error: $(LEXIQUE_FILE) is empty or missing"; \
		exit 1; \
	fi
	@echo "Data files OK"

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
	@if [ ! -s "$(DATA_FILE)" ]; then \
		echo "Error: Download failed or file is empty"; \
		exit 1; \
	fi

$(LEXIQUE_FILE):
	@echo "Downloading $(LEXIQUE_FILE)…"
	@if command -v curl >/dev/null 2>&1; then \
		curl -L --fail --progress-bar -o "$(LEXIQUE_FILE)" "$(LEXIQUE_URL)"; \
	elif command -v wget >/dev/null 2>&1; then \
		wget -O "$(LEXIQUE_FILE)" "$(LEXIQUE_URL)"; \
	else \
		echo "Error: need curl or wget to download $(LEXIQUE_URL)"; \
		exit 1; \
	fi
	@if [ ! -s "$(LEXIQUE_FILE)" ]; then \
		echo "Error: Download failed or file is empty"; \
		exit 1; \
	fi
	@if ! head -1 "$(LEXIQUE_FILE)" | grep -q $$'\t'; then \
		echo "Error: Downloaded file does not appear to be a valid TSV"; \
		exit 1; \
	fi

build-pages: check-data
	$(PY) build_github_pages.py

build-demo:
	$(PY) french_conjugator_v8.py

build-all: build-pages build-demo

clean:
	rm -rf docs/data
	rm -f lexique.tsv fr-extract.jsonl.gz audiofrench_index.txt
	rm -f french_conjugations.html
