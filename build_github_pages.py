#!/usr/bin/env python3
"""
Build JSON data for the interactive GitHub Pages site in `docs/`.

This does NOT modify the demo HTML generator (v8).
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import tomllib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import french_conjugator_v8 as v8


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

    # Exclude pronominal/reflexive entries (usually tagged as "pronominal").
    # Fallback: some entries may lack the tag but still start with "se " / "s'".
    tags = {t.lower() for t in (entry.get("tags") or []) if isinstance(t, str)}
    raw_tags = {t.lower() for t in (entry.get("raw_tags") or []) if isinstance(t, str)}
    if "pronominal" in tags or "pronominal" in raw_tags:
        return False
    w = word.strip().lower()
    if w.startswith("se ") or w.startswith("s'") or w.startswith("s’"):
        return False

    # Prefer a structural signal that we're on the lemma page:
    # the word itself appears as an infinitive-tagged form.
    has_infinitive_self = any(
        (f.get("form") == word and "infinitive" in (f.get("tags") or [])) for f in forms
    )
    if not has_infinitive_self:
        # Fallback heuristic: infinitives usually end in -er/-ir/-re/-oir.
        if not word.endswith(("er", "ir", "re", "oir")):
            return False

    pr = v8.extract_tense_forms(forms, ["indicative", "present"])
    imp = v8.extract_tense_forms(forms, ["indicative", "imperfect"])
    fut = v8.extract_tense_forms(forms, ["indicative", "future"])
    ps = v8.extract_tense_forms(
        forms, ["indicative", "past"], ["multiword-construction", "anterior"]
    )
    return len(pr) == 6 and len(imp) == 6 and len(fut) == 6 and len(ps) == 6


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="fr-extract.jsonl.gz")
    parser.add_argument("--out-dir", default=os.path.join("docs", "data"))
    parser.add_argument("--limit", type=int, default=0, help="0 = no limit")
    parser.add_argument("--chunk-size", type=int, default=2000)
    args = parser.parse_args()

    out_dir = args.out_dir
    chunks_dir = os.path.join(out_dir, "chunks")
    os.makedirs(chunks_dir, exist_ok=True)

    # Avoid leaving behind legacy single-file outputs.
    for legacy in ("verbs.json", "verbs.json.gz"):
        try:
            os.remove(os.path.join(out_dir, legacy))
        except FileNotFoundError:
            pass

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
                if not issues_url and lk in {"issues", "bug tracker", "bugtracker", "tracker"}:
                    issues_url = v
        if repo_url and not issues_url:
            issues_url = repo_url.rstrip("/") + "/issues"
    except Exception:
        pass

    dump_dt = ""
    try:
        mtime = os.path.getmtime(args.input)
        dump_dt = datetime.fromtimestamp(mtime, tz=timezone.utc).date().isoformat()
    except Exception:
        dump_dt = ""

    count = 0
    chunk_size = max(50, int(args.chunk_size or 0))
    chunk_idx = 0
    current_chunk: List[Dict] = []
    chunk_files: List[str] = []

    def write_chunk(i: int, verbs_chunk: List[Dict]) -> str:
        filename = f"verbs_{i:04d}.json.gz"
        rel_path = os.path.join("chunks", filename)
        out_path = os.path.join(out_dir, rel_path)
        payload = {"verbs": verbs_chunk}
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with open(out_path, "wb") as f:
            with gzip.GzipFile(filename=filename[:-3], mode="wb", fileobj=f, mtime=0) as gz:
                gz.write(raw)
        return rel_path

    with gzip.open(args.input, "rt", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            if not is_lemma_candidate(entry):
                continue

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

            current_chunk.append(
                {
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
            )

            count += 1
            if len(current_chunk) >= chunk_size:
                chunk_files.append(write_chunk(chunk_idx, current_chunk))
                current_chunk = []
                chunk_idx += 1
            if args.limit and count >= args.limit:
                break

    if current_chunk:
        chunk_files.append(write_chunk(chunk_idx, current_chunk))

    manifest = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "repo_url": repo_url,
            "issues_url": issues_url,
            "wiktionary_extract_date": dump_dt,
        },
        "count": count,
        "chunk_size": chunk_size,
        "chunks": chunk_files,
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as out:
        json.dump(manifest, out, ensure_ascii=False, separators=(",", ":"))

    print(f"Wrote {count} verbs in {len(chunk_files)} chunks to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
