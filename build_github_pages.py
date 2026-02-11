#!/usr/bin/env python3
"""
Build JSON data for the interactive GitHub Pages site in `docs/`.

Generates tiered chunks:
- most_common_verbs.json.gz: top 200 most frequent verbs (loaded at startup)
- common_verbs.json.gz: next 2300 frequent verbs (loaded at startup)
- letter_chunks/*.json.gz: remaining verbs organized by first letter (loaded on demand)

Frequency data from Lexique.org (combined film+book corpus).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
import tomllib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import french_conjugator_v8 as v8

# Use existing normalization from library
normalize_for_matching = v8.normalize_for_audiofrench

# URL for Lexique frequency data (TSV format)
LEXIQUE_URL = "http://www.lexique.org/databases/Lexique383/Lexique383.tsv"
AUDIOFRENCH_URL = "http://www.audiofrench.com/verbs/sounds/"
MOST_COMMON_COUNT = 200
COMMON_COUNT = 2300
TOTAL_COMMON = MOST_COMMON_COUNT + COMMON_COUNT  # 2500


def download_lexique(lexique_path: str) -> None:
    """Download Lexique frequency data if not present."""
    if os.path.exists(lexique_path):
        print(f"Using existing Lexique data: {lexique_path}")
        return

    print(f"Downloading Lexique frequency data from {LEXIQUE_URL}...")
    import urllib.request

    try:
        urllib.request.urlretrieve(LEXIQUE_URL, lexique_path)
        file_size = os.path.getsize(lexique_path)
        print(f"Downloaded {file_size:,} bytes")
        if file_size == 0:
            raise ValueError("Downloaded file is empty")
    except Exception as e:
        if os.path.exists(lexique_path):
            os.remove(lexique_path)
        raise RuntimeError(f"Failed to download Lexique data: {e}")


def download_audiofrench_index(audiofrench_index_path: str) -> set:
    """Download AudioFrench folder index and return set of normalized verb names."""
    if os.path.exists(audiofrench_index_path):
        print(f"Using existing AudioFrench index: {audiofrench_index_path}")
        with open(audiofrench_index_path, "r", encoding="utf-8") as f:
            return set(json.load(f))

    print(f"Downloading AudioFrench index from {AUDIOFRENCH_URL}...")
    import urllib.request

    try:
        response = urllib.request.urlopen(AUDIOFRENCH_URL, timeout=30)
        html = response.read().decode("utf-8", errors="ignore")

        folders: set = set()
        pattern = r'href="([a-zA-Z_]+)/"'
        matches = re.findall(pattern, html)

        for folder in matches:
            if folder in ["", "Parent", "Name", "Last", "Size", "Description"]:
                continue
            normalized = normalize_for_matching(folder)
            if normalized and folder.lower() != "parent directory":
                folders.add(normalized)

        print(f"Found {len(folders)} verb folders with audio")

        with open(audiofrench_index_path, "w", encoding="utf-8") as f:
            json.dump(list(sorted(folders)), f, ensure_ascii=False)

        return folders

    except Exception as e:
        print(f"Warning: Failed to download AudioFrench index: {e}")
        return set()


def load_lexique_frequencies(lexique_path: str) -> Dict[str, float]:
    """Load verb frequencies from Lexique TSV file.

    Returns dict mapping infinitive -> combined frequency (film + book).
    """
    frequencies: Dict[str, float] = {}

    print(f"Loading frequencies from {lexique_path}...")

    with open(lexique_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            if row.get("cgram") != "VER":
                continue

            infinitive = row.get("ortho", "").strip().lower()
            if not infinitive:
                continue

            film_freq = float(row.get("freqlemfilms2", 0) or 0)
            book_freq = float(row.get("freqlemlivres", 0) or 0)
            combined_freq = film_freq + book_freq

            if infinitive not in frequencies or combined_freq > frequencies[infinitive]:
                frequencies[infinitive] = combined_freq

    print(f"Loaded {len(frequencies):,} verb frequencies")
    return frequencies


def extract_participle(forms: List[Dict], tags: List[str]) -> Tuple[str, str]:
    forms_list = v8.extract_conjugation(forms, tags)
    text = forms_list[0] if forms_list else ""
    ipa = ""
    if text:
        raw = text
        if " ou " in raw:
            raw = raw.split(" ou ", 1)[0]
        text = v8.clean_form_text(raw)
        for f in forms:
            f_text, f_ipa = v8.extract_form_with_ipa(f)
            if f_text == text and f_ipa:
                ipa = f_ipa
                break
    return text, ipa


def lemma_ipa_and_audio(
    infinitive: str, forms: List[Dict], sounds: List[Dict]
) -> Tuple[str, str]:
    lemma_ipa = ""
    for f in forms:
        if f.get("form") == infinitive and "infinitive" in (f.get("tags") or []):
            _text, ipa = v8.extract_form_with_ipa(f)
            if ipa:
                lemma_ipa = ipa
                break
    if not lemma_ipa:
        for s in sounds:
            ipa = (s.get("ipa") or "").strip()
            if ipa:
                lemma_ipa = ipa.strip("[]").strip("\\")
                break
    audio_url = v8.pick_audio_url(sounds)
    return lemma_ipa, audio_url


def tense(forms: List[Dict], include: List[str], exclude: Optional[List[str]] = None):
    pairs = v8.extract_tense_forms(forms, include, exclude)
    out = []
    has_alt = False
    for text, ipa in pairs:
        raw = text or ""
        if " ou " in raw:
            raw = raw.split(" ou ", 1)[0]
            has_alt = True
        out.append({"f": v8.clean_form_text(raw), "ipa": ipa})
    return out, has_alt


def is_lemma_candidate(entry: Dict) -> bool:
    if entry.get("lang_code") != "fr" or entry.get("pos") != "verb":
        return False
    word = entry.get("word") or ""
    forms = entry.get("forms") or []

    tags = {t.lower() for t in (entry.get("tags") or []) if isinstance(t, str)}
    raw_tags = {t.lower() for t in (entry.get("raw_tags") or []) if isinstance(t, str)}

    # Common irregular verbs that can be used reflexively but aren't inherently pronominal
    PRONOMINAL_EXCEPTIONS = {
        "faire",
        "aller",
        "venir",
        "partir",
        "sortir",
        "entrer",
        "retourner",
    }
    is_pronominal_exception = word.strip().lower() in PRONOMINAL_EXCEPTIONS

    if "pronominal" in tags or "pronominal" in raw_tags:
        if not is_pronominal_exception:
            return False
    w = word.strip().lower()
    if w.startswith("se ") or w.startswith("s'") or w.startswith("s'"):
        return False

    has_infinitive_self = any(
        (f.get("form") == word and "infinitive" in (f.get("tags") or [])) for f in forms
    )
    if not has_infinitive_self:
        if not word.endswith(("er", "ir", "re", "oir")):
            return False

    pr = v8.extract_tense_forms(forms, ["indicative", "present"])
    imp = v8.extract_tense_forms(forms, ["indicative", "imperfect"])
    fut = v8.extract_tense_forms(forms, ["indicative", "future"])
    ps = v8.extract_tense_forms(
        forms, ["indicative", "past"], ["multiword-construction", "anterior"]
    )
    return len(pr) == 6 and len(imp) == 6 and len(fut) == 6 and len(ps) == 6


def process_verb_entry(entry: Dict) -> Optional[Dict]:
    """Process a Wiktionary entry into our verb format."""
    if not is_lemma_candidate(entry):
        return None

    word = entry.get("word") or ""
    forms = entry.get("forms") or []
    sounds = entry.get("sounds") or []

    pr, pr_alt = tense(forms, ["indicative", "present"])
    imp, imp_alt = tense(forms, ["indicative", "imperfect"])
    fut, fut_alt = tense(forms, ["indicative", "future"])
    ps, ps_alt = tense(
        forms,
        ["indicative", "past"],
        ["multiword-construction", "anterior"],
    )
    has_alt = pr_alt or imp_alt or fut_alt or ps_alt

    stems = v8.derive_stems(word, [(x["f"], x["ipa"]) for x in pr])
    irr = v8.compute_irregularity_marker(
        word,
        [(x["f"], x["ipa"]) for x in pr],
        [(x["f"], x["ipa"]) for x in imp],
        [(x["f"], x["ipa"]) for x in ps],
        [(x["f"], x["ipa"]) for x in fut],
        stems,
    )

    pres_part, pres_part_ipa = extract_participle(forms, ["participle", "present"])
    past_part, past_part_ipa = extract_participle(forms, ["participle", "past"])

    lemma_ipa, lemma_audio = lemma_ipa_and_audio(word, forms, sounds)

    return {
        "w": word,
        "ipa": lemma_ipa,
        "audio": lemma_audio,
        "irr": irr,
        "alt": has_alt,
        "part": {
            "pres": {"f": pres_part, "ipa": pres_part_ipa},
            "past": {"f": past_part, "ipa": past_part_ipa},
        },
        "t": {"pr": pr, "imp": imp, "ps": ps, "fut": fut},
    }


def write_chunk(out_path: str, verbs: List[Dict]) -> int:
    """Write a chunk file and return its size in bytes."""
    payload = {"verbs": verbs}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    with open(out_path, "wb") as f:
        with gzip.GzipFile(
            filename=os.path.basename(out_path)[:-3], mode="wb", fileobj=f, mtime=0
        ) as gz:
            gz.write(raw)

    return os.path.getsize(out_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="fr-extract.jsonl.gz")
    parser.add_argument("--out-dir", default=os.path.join("docs", "data"))
    parser.add_argument("--lexique", default="lexique.tsv")
    parser.add_argument(
        "--download-lexique",
        action="store_true",
        help="Download Lexique data if not present",
    )
    args = parser.parse_args()

    out_dir = args.out_dir
    letter_chunks_dir = os.path.join(out_dir, "letter_chunks")

    os.makedirs(out_dir, exist_ok=True)

    # Remove legacy files
    for legacy in ("verbs.json", "verbs.json.gz", "chunks"):
        legacy_path = os.path.join(out_dir, legacy)
        if os.path.exists(legacy_path):
            if os.path.isdir(legacy_path):
                import shutil

                shutil.rmtree(legacy_path)
            else:
                os.remove(legacy_path)

    # Clean letter_chunks directory
    if os.path.exists(letter_chunks_dir):
        import shutil

        shutil.rmtree(letter_chunks_dir)
    os.makedirs(letter_chunks_dir, exist_ok=True)

    # Download Lexique if requested
    if args.download_lexique or not os.path.exists(args.lexique):
        download_lexique(args.lexique)

    # Load frequencies
    frequencies = load_lexique_frequencies(args.lexique)

    # Download AudioFrench index for audio availability (saved as JSON for browser)
    audiofrench_index_path = os.path.join(out_dir, "audiofrench_index.json")
    audiofrench_verbs = download_audiofrench_index(audiofrench_index_path)
    print(f"AudioFrench verbs available: {len(audiofrench_verbs):,}")

    # Get repo metadata
    repo_url = ""
    issues_url = ""
    try:
        with open("pyproject.toml", "rb") as f:
            py = tomllib.load(f)
        urls = (py.get("project") or {}).get("urls") or {}
        if isinstance(urls, dict):
            for k, v in urls.items():
                if not isinstance(v, str):
                    continue
                lk = str(k).lower()
                if not repo_url and lk in {"repository", "repo", "source", "homepage"}:
                    repo_url = v
                if not issues_url and lk in {
                    "issues",
                    "bug tracker",
                    "bugtracker",
                    "tracker",
                }:
                    issues_url = v
        if repo_url and not issues_url:
            issues_url = repo_url.rstrip("/") + "/issues"
    except Exception:
        pass

    # Get dump date
    dump_dt = ""
    try:
        mtime = os.path.getmtime(args.input)
        dump_dt = datetime.fromtimestamp(mtime, tz=timezone.utc).date().isoformat()
    except Exception:
        pass

    # Collect all verbs with their frequencies
    print(f"Processing verbs from {args.input}...")
    all_verbs: List[Tuple[float, Dict]] = []

    with gzip.open(args.input, "rt", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            verb_data = process_verb_entry(entry)
            if verb_data is None:
                continue

            word = verb_data["w"].lower()
            freq = frequencies.get(word, 0.0)
            all_verbs.append((freq, verb_data))

    print(f"Total verbs collected: {len(all_verbs):,}")

    # Sort by frequency (descending)
    all_verbs.sort(key=lambda x: x[0], reverse=True)

    # Split into three tiers
    most_common_verbs = [v for _, v in all_verbs[:MOST_COMMON_COUNT]]
    common_verbs = [v for _, v in all_verbs[MOST_COMMON_COUNT:TOTAL_COMMON]]
    remaining_verbs = [v for _, v in all_verbs[TOTAL_COMMON:]]

    # Ensure "avoir" is in the most common verbs
    avoir_in_most_common = any(v["w"].lower() == "avoir" for v in most_common_verbs)
    if not avoir_in_most_common:
        print("Adding 'avoir' to most common verbs...")
        # Find "avoir" in common_verbs or remaining_verbs
        avoir_verb = None
        for i, v in enumerate(common_verbs):
            if v["w"].lower() == "avoir":
                avoir_verb = common_verbs.pop(i)
                break
        if avoir_verb is None:
            for i, v in enumerate(remaining_verbs):
                if v["w"].lower() == "avoir":
                    avoir_verb = remaining_verbs.pop(i)
                    break
        if avoir_verb:
            most_common_verbs.append(avoir_verb)
        else:
            print("Warning: 'avoir' not found in any verb list")

    print(f"Most common verbs: {len(most_common_verbs):,}")
    print(f"Common verbs: {len(common_verbs):,}")
    print(f"Remaining verbs: {len(remaining_verbs):,}")

    # Group remaining verbs by first letter
    letter_groups: Dict[str, List[Dict]] = {}
    for v in remaining_verbs:
        first_letter = v["w"][0].lower()
        if first_letter not in letter_groups:
            letter_groups[first_letter] = []
        letter_groups[first_letter].append(v)

    # Write most common verbs chunk
    most_common_path = os.path.join(out_dir, "most_common_verbs.json.gz")
    most_common_size = write_chunk(most_common_path, most_common_verbs)
    print(
        f"Wrote most_common_verbs.json.gz ({most_common_size:,} bytes, {len(most_common_verbs)} verbs)"
    )

    # Write common verbs chunk
    common_path = os.path.join(out_dir, "common_verbs.json.gz")
    common_size = write_chunk(common_path, common_verbs)
    print(
        f"Wrote common_verbs.json.gz ({common_size:,} bytes, {len(common_verbs)} verbs)"
    )

    # Write letter chunks
    letter_chunk_files: List[str] = []
    total_letter_size = 0

    for letter in sorted(letter_groups.keys()):
        verbs = letter_groups[letter]
        chunk_filename = f"{letter}.json.gz"
        chunk_path = os.path.join(letter_chunks_dir, chunk_filename)
        rel_path = f"letter_chunks/{chunk_filename}"

        size = write_chunk(chunk_path, verbs)
        letter_chunk_files.append(rel_path)
        total_letter_size += size

        print(f"Wrote {rel_path} ({size:,} bytes, {len(verbs)} verbs)")

    # Calculate total size in MB for UI
    total_size_mb = round(total_letter_size / (1024 * 1024), 1)

    # Create manifest
    manifest = {
        "version": 3,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "repo_url": repo_url,
            "issues_url": issues_url,
            "wiktionary_extract_date": dump_dt,
        },
        "strategy": "tiered",
        "most_common_verbs": {
            "count": len(most_common_verbs),
            "file": "most_common_verbs.json.gz",
            "size_bytes": most_common_size,
        },
        "common_verbs": {
            "count": len(common_verbs),
            "file": "common_verbs.json.gz",
            "size_bytes": common_size,
        },
        "letter_chunks": {
            "files": letter_chunk_files,
            "letters": sorted(letter_groups.keys()),
            "total_size_bytes": total_letter_size,
            "total_size_mb": total_size_mb,
        },
        "total_verbs": len(all_verbs),
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as out:
        json.dump(manifest, out, ensure_ascii=False, separators=(",", ":"))

    print("\nBuild complete:")
    print(f"  - Most common verbs: {len(most_common_verbs):,} (always loaded)")
    print(f"  - Common verbs: {len(common_verbs):,} (always loaded)")
    print(
        f"  - Letter chunks: {len(letter_chunk_files)} files ({total_size_mb} MB total)"
    )
    print(f"  - Total verbs: {len(all_verbs):,}")
    print(f"  - Manifest: {manifest_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
