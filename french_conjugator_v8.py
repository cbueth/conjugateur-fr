#!/usr/bin/env python3
"""
Extract French verb conjugations with enhanced formatting and coloring.
Version 8 - Enhanced formatting, UX improvements and French UI.
"""

import gzip
import json
import csv
from typing import Dict, List, Optional, Tuple, Set
import html
import re
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import quote

PRONUNCIATION_GUIDE_URL = (
    "https://fr.wiktionary.org/wiki/Annexe:Prononciation/fran%C3%A7ais"
)
AUDIOFRENCH_BASE_URL = "http://www.audiofrench.com/verbs/sounds"
AUDIOFRENCH_VERB_INDEX_URL = "http://www.audiofrench.com/verbs/verbes_index.htm"
LINGOLIA_TENSES_URL = "https://francais.lingolia.com/fr/grammaire/les-temps"

# Test verbs - these should be in our data
TEST_VERBS = [
    "aimer",
    "finir",
    "dormir",
    "vendre",
    "être",
    "avoir",
    "aller",
    "faire",
    "vouloir",
    "venir",
    "savoir",
]

# Irregularity markers based on a small curated list (heuristic).
IRREGULARITY_MARKERS = {
    "high": "🔴",  # k, w, x, z
    "medium": "🟡",  # h, j, q, y
    "low": "🟠",  # other uncommon patterns
}

IRREGULARITY_HINTS_FR = {
    IRREGULARITY_MARKERS["high"]: "Très irrégulier",
    IRREGULARITY_MARKERS["medium"]: "Irrégularité moyenne",
    IRREGULARITY_MARKERS["low"]: "Radical irrégulier / changement de radical",
    "🟢": "Régulier",
}

# Colors for highlighting
COLORS = {
    "red": "#FF6B6B",
    "red_hi": "#E11D48",
    # Used for imparfait endings; keep it darker for readability.
    "blue": "#0F766E",
    "blue_hi": "#0B5C56",
    "green": "#2E7D32",  # Darker green for better readability
    "green_hi": "#166534",
    # Used for IPA + futur; keep it less bright for readability.
    "purple": "#1E40AF",
    "purple_hi": "#1D4ED8",
    "orange": "#FB923C",
    "salmon": "#FFA07A",  # Light salmon for IPA
}


def get_irregularity_marker(verb: str, conjugations: Dict[str, str]) -> str:
    """Backwards-compatible wrapper; prefer score-based marker (see compute_irregularity_marker)."""
    return ""


def diff_score_mask(actual: str, expected: str) -> Tuple[int, List[bool], Optional[int]]:
    """
    Score differences between actual and expected.
    - score counts inserts + replaces + deletes
    - mask marks actual positions that are inserted/replaced (for highlighting)
    - first_mismatch is the earliest actual index affected (best-effort, includes deletes)
    """
    if not actual or not expected:
        return (0, [False] * len(actual), None)

    mask = [False] * len(actual)
    matcher = SequenceMatcher(a=expected, b=actual)
    score = 0
    first_mismatch: Optional[int] = None
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if first_mismatch is None:
            first_mismatch = j1
        if tag in {"replace", "insert"}:
            score += (j2 - j1)
            for j in range(j1, j2):
                if 0 <= j < len(mask):
                    mask[j] = True
        elif tag == "delete":
            score += (i2 - i1)
    return (score, mask, first_mismatch)


def best_expected_mask(actual: str, expected_variants: List[str]) -> Optional[List[bool]]:
    if not expected_variants:
        return None
    best_mask = None
    best_score = None
    for expected in expected_variants:
        score, mask, _ = diff_score_mask(actual, expected)
        if best_score is None or score < best_score:
            best_score = score
            best_mask = mask
            if best_score == 0:
                break
    return best_mask


def diff_score_and_stem_mismatch(actual: str, expected: str, ending: str) -> Tuple[int, bool]:
    """Return (score, stem_mismatch) for actual vs expected given a regular ending."""
    if not actual or not expected:
        return (0, False)
    matcher = SequenceMatcher(a=expected, b=actual)
    score = 0
    stem_mismatch = False
    boundary_expected = max(0, len(expected) - len(ending))
    boundary_actual = max(0, len(actual) - len(ending))
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in {"replace", "insert"}:
            score += (j2 - j1)
        elif tag == "delete":
            score += (i2 - i1)
        if i1 < boundary_expected or j1 < boundary_actual:
            stem_mismatch = True
    return (score, stem_mismatch)


def best_expected_diff_details(
    actual: str, expected_variants: List[str], ending: str
) -> Tuple[int, bool]:
    """Return (score, stem_mismatch) for the closest expected variant."""
    if not expected_variants:
        return (0, False)
    best_score = 10**9
    best_stem_mismatch = False
    for expected in expected_variants:
        score, stem_mismatch = diff_score_and_stem_mismatch(actual, expected, ending)
        if score < best_score:
            best_score = score
            best_stem_mismatch = stem_mismatch
            if best_score == 0:
                break
    return (best_score, best_stem_mismatch)


def compute_irregularity_marker(
    infinitive: str,
    present_forms: List[Tuple[str, str]],
    imparfait_forms: List[Tuple[str, str]],
    passe_simple_forms: List[Tuple[str, str]],
    futur_forms: List[Tuple[str, str]],
    stems: Dict[str, str],
) -> str:
    """
    Systematic irregularity rating based on how far attested forms deviate from
    the regular model (+ common spelling rules handled in expected_regular_variants).
    """
    tense_map = {
        "present": present_forms,
        "imparfait": imparfait_forms,
        "passe_simple": passe_simple_forms,
        "futur": futur_forms,
    }

    total_score = 0
    total_chars = 0
    stem_mismatch_forms = 0
    compared_forms = 0

    for tense_key, forms in tense_map.items():
        if len(forms) < 6:
            continue
        for i in range(6):
            form_text, _ipa = forms[i]
            actual = clean_form_text(form_text)
            if not actual:
                continue
            expected_variants = expected_regular_variants(
                infinitive, tense_key, i, stems=stems
            )
            if not expected_variants:
                continue
            ending = regular_ending(infinitive, tense_key, i)
            score, stem_mismatch = best_expected_diff_details(
                actual, expected_variants, ending
            )

            compared_forms += 1
            total_score += score
            total_chars += max(1, len(actual))

            if score > 0 and stem_mismatch:
                stem_mismatch_forms += 1

    if compared_forms == 0 or total_score == 0:
        return ""

    ratio = total_score / max(1, total_chars)

    # Heuristics:
    # - Many stem mismatches or high overall ratio => highly irregular
    # - Any stem mismatch => stem-changing / irregular stem
    # - Otherwise => medium irregularity (endings irregular but stem mostly stable)
    if stem_mismatch_forms >= 6 or ratio >= 0.18:
        return IRREGULARITY_MARKERS["high"]
    if stem_mismatch_forms >= 1:
        return IRREGULARITY_MARKERS["low"]
    return IRREGULARITY_MARKERS["medium"]


def extract_conjugation(forms: List[Dict], required_tags: List[str]) -> List[str]:
    """Extract specific conjugation forms based on required tags."""
    result = []
    for form in forms:
        tags = form.get("tags", [])
        # Check if ALL required tags are present
        if all(tag in tags for tag in required_tags):
            form_text = form.get("form", "")
            if form_text and form_text != "-":
                result.append(form_text)
    return result


def extract_form_with_ipa(form: Dict) -> Tuple[str, str]:
    """Extract form text and IPA separately."""
    form_text = form.get("form", "")
    ipas = form.get("ipas", [])

    if not form_text:
        return "", ""

    # Get first IPA if available
    if ipas and ipas[0]:
        ipa = ipas[0].strip("[]\\")  # Remove brackets and backslashes
        return form_text, ipa

    return form_text, ""


def extract_tense_forms(
    forms: List[Dict],
    required_tags: List[str],
    exclude_tags: Optional[List[str]] = None,
) -> List[Tuple[str, str]]:
    """Extract 6 forms with IPA for a specific tense."""
    if exclude_tags is None:
        exclude_tags = []

    # Find forms with ALL required tags and NO excluded tags
    tense_forms = []
    for form in forms:
        tags = form.get("tags", [])
        # Check if ALL required tags are present and NO excluded tags
        if all(tag in tags for tag in required_tags) and all(
            tag not in tags for tag in exclude_tags
        ):
            form_text, ipa = extract_form_with_ipa(form)
            if form_text and form_text != "-":
                tense_forms.append((form_text, ipa))

    return tense_forms[:6]  # Return exactly 6 forms


def verb_group(infinitive: str) -> str:
    if infinitive.endswith("er"):
        return "er"
    if infinitive.endswith("ir"):
        return "ir"
    if infinitive.endswith("re"):
        return "re"
    return "other"

def expected_base_form(
    infinitive: str,
    tense_key: str,
    person_index: int,
    stems: Optional[Dict[str, str]] = None,
) -> str:
    group = verb_group(infinitive)
    stem = infinitive[:-2] if group in {"er", "ir", "re"} else infinitive

    if tense_key == "present":
        if group == "er":
            endings = ["e", "es", "e", "ons", "ez", "ent"]
        elif group == "ir":
            endings = ["is", "is", "it", "issons", "issez", "issent"]
        elif group == "re":
            endings = ["s", "s", "", "ons", "ez", "ent"]
        else:
            return ""
        return stem + endings[person_index]

    if tense_key == "imparfait":
        endings = ["ais", "ais", "ait", "ions", "iez", "aient"]
        if stems and stems.get("imparfait_stem"):
            base = stems["imparfait_stem"]
        else:
            base = stem + "iss" if group == "ir" else stem
        return base + endings[person_index]

    if tense_key == "futur":
        endings = ["ai", "as", "a", "ons", "ez", "ont"]
        base = infinitive[:-1] if group == "re" else infinitive
        return base + endings[person_index]

    if tense_key == "passe_simple":
        if group == "er":
            endings = ["ai", "as", "a", "âmes", "âtes", "èrent"]
        elif group in {"ir", "re"}:
            endings = ["is", "is", "it", "îmes", "îtes", "irent"]
        else:
            return ""
        return stem + endings[person_index]

    return ""


def derive_stems(infinitive: str, present_forms: List[Tuple[str, str]]) -> Dict[str, str]:
    """Derive stems used by 'regular' conjugations from attested forms (Wikipedia-style)."""
    stems: Dict[str, str] = {}
    if len(present_forms) >= 4:
        nous_form_text, _ = present_forms[3]
        nous = clean_form_text(nous_form_text)
        stems["present_nous"] = nous
        if nous.endswith("ons"):
            stems["imparfait_stem"] = nous[: -len("ons")]
    stems["group"] = verb_group(infinitive)
    return stems


def regular_ending(infinitive: str, tense_key: str, person_index: int) -> str:
    group = verb_group(infinitive)
    if tense_key == "present":
        if group == "er":
            return ["e", "es", "e", "ons", "ez", "ent"][person_index]
        if group == "ir":
            return ["is", "is", "it", "issons", "issez", "issent"][person_index]
        if group == "re":
            return ["s", "s", "", "ons", "ez", "ent"][person_index]
        return ""
    if tense_key == "imparfait":
        return ["ais", "ais", "ait", "ions", "iez", "aient"][person_index]
    if tense_key == "futur":
        return ["ai", "as", "a", "ons", "ez", "ont"][person_index]
    if tense_key == "passe_simple":
        if group == "er":
            return ["ai", "as", "a", "âmes", "âtes", "èrent"][person_index]
        if group in {"ir", "re"}:
            return ["is", "is", "it", "îmes", "îtes", "irent"][person_index]
        return ""
    return ""


def apply_cer_ger_spelling(form: str, infinitive: str, ending: str) -> List[str]:
    """Return variants accounting for -cer/-ger spelling rules."""
    variants = [form]
    inf = infinitive.lower()
    if inf.endswith("cer") and ending and ending[0] in {"a", "â", "o"}:
        # c -> ç before a/o
        variants.append(re.sub(r"c(?=[aâo])", "ç", form))
    if inf.endswith("ger") and ending and ending[0] in {"a", "â", "o"}:
        # g -> ge before a/o
        variants.append(re.sub(r"g(?=[aâo])", "ge", form))
    # De-dup while preserving order
    out = []
    for v in variants:
        if v not in out:
            out.append(v)
    return out


def y_to_i_variants(stem: str, optional: bool) -> List[str]:
    if "y" not in stem:
        return [stem]
    # Change the last y in the stem (envoyer -> envoi-)
    idx = stem.rfind("y")
    if idx == -1:
        return [stem]
    changed = stem[:idx] + "i" + stem[idx + 1 :]
    return [stem, changed] if optional else [changed]


def apply_yer_spelling(
    stem: str, infinitive: str, tense_key: str, person_index: int
) -> List[str]:
    """Return acceptable stem variants for -yer spelling rules in present."""
    inf = infinitive.lower()
    if tense_key != "present":
        return [stem]

    # Endings with silent 'e' in present: je/tu/il/ils (plus ils/elles)
    silent_e_persons = {0, 1, 2, 5}
    if person_index not in silent_e_persons:
        return [stem]

    if inf.endswith("oyer") or inf.endswith("uyer"):
        return y_to_i_variants(stem, optional=False)
    if inf.endswith("ayer"):
        return y_to_i_variants(stem, optional=True)
    return [stem]


def apply_e_to_e_grave(stem: str) -> str:
    idx = stem.rfind("e")
    if idx == -1:
        return stem
    return stem[:idx] + "è" + stem[idx + 1 :]


def apply_e_acute_to_e_grave(stem: str) -> str:
    idx = stem.rfind("é")
    if idx == -1:
        return stem
    return stem[:idx] + "è" + stem[idx + 1 :]


def apply_eer_spelling(
    stem: str, infinitive: str, tense_key: str, person_index: int
) -> List[str]:
    """
    Handle common regular spelling changes:
    - -é.er: é -> è before silent endings
    - -e.er: e -> è before silent endings (including future/conditional per Wikipedia; we apply to present)
    """
    if tense_key != "present":
        return [stem]

    silent_e_persons = {0, 1, 2, 5}
    if person_index not in silent_e_persons:
        return [stem]

    inf = infinitive.lower()
    base = stem
    variants = [base]

    if re.search(r"é[^aeiouy]*er$", inf):
        variants.append(apply_e_acute_to_e_grave(base))
    elif re.search(r"e[^aeiouy]*er$", inf):
        variants.append(apply_e_to_e_grave(base))

    out = []
    for v in variants:
        if v not in out:
            out.append(v)
    return out


def apply_eler_eter_spelling(
    stem: str, infinitive: str, tense_key: str, person_index: int
) -> List[str]:
    """Allow common -eler/-eter regular variants (e->è and/or l/t doubling) in present."""
    if tense_key != "present":
        return [stem]
    silent_e_persons = {0, 1, 2, 5}
    if person_index not in silent_e_persons:
        return [stem]

    inf = infinitive.lower()
    if not (inf.endswith("eler") or inf.endswith("eter")):
        return [stem]

    variants = [stem]

    # e -> è (last e)
    variants.append(apply_e_to_e_grave(stem))

    # double final l/t in stem if present
    if inf.endswith("eler") and stem.endswith("el"):
        variants.append(stem[:-1] + "ll")
        variants.append(apply_e_to_e_grave(stem[:-1] + "ll"))
    if inf.endswith("eter") and stem.endswith("et"):
        variants.append(stem[:-1] + "tt")
        variants.append(apply_e_to_e_grave(stem[:-1] + "tt"))

    out = []
    for v in variants:
        if v not in out:
            out.append(v)
    return out


def expected_regular_variants(
    infinitive: str,
    tense_key: str,
    person_index: int,
    stems: Optional[Dict[str, str]] = None,
) -> List[str]:
    """
    Return a small set of acceptable *regular* spellings for this verb/tense/person.
    This intentionally covers common orthographic rules so they are not over-highlighted.
    """
    group = verb_group(infinitive)
    if group not in {"er", "ir", "re"}:
        base = expected_base_form(infinitive, tense_key, person_index, stems=stems)
        return [base] if base else []

    base = expected_base_form(infinitive, tense_key, person_index, stems=stems)
    if not base:
        return []

    # Determine ending by subtracting the (naive) stem or base used.
    # For cer/ger we only need the first letter of the ending; compute via base form.
    ending = ""
    if tense_key == "present":
        endings = (
            ["e", "es", "e", "ons", "ez", "ent"]
            if group == "er"
            else ["is", "is", "it", "issons", "issez", "issent"]
            if group == "ir"
            else ["s", "s", "", "ons", "ez", "ent"]
        )
        ending = endings[person_index]
    elif tense_key == "imparfait":
        ending = ["ais", "ais", "ait", "ions", "iez", "aient"][person_index]
    elif tense_key == "futur":
        ending = ["ai", "as", "a", "ons", "ez", "ont"][person_index]
    elif tense_key == "passe_simple":
        ending = (
            ["ai", "as", "a", "âmes", "âtes", "èrent"][person_index]
            if group == "er"
            else ["is", "is", "it", "îmes", "îtes", "irent"][person_index]
        )

    variants = [base]

    # Orthographic rules that are considered regular.
    variants = [v for form in variants for v in apply_cer_ger_spelling(form, infinitive, ending)]

    if tense_key == "present":
        # Stem-based alternations for -yer / -e.er / -é.er / -eler / -eter
        stem = infinitive[:-2]
        present_endings = (
            ["e", "es", "e", "ons", "ez", "ent"]
            if group == "er"
            else ["is", "is", "it", "issons", "issez", "issent"]
            if group == "ir"
            else ["s", "s", "", "ons", "ez", "ent"]
        )
        end = present_endings[person_index]

        stem_variants = apply_yer_spelling(stem, infinitive, tense_key, person_index)
        expanded = []
        for st in stem_variants:
            for st2 in apply_eer_spelling(st, infinitive, tense_key, person_index):
                for st3 in apply_eler_eter_spelling(st2, infinitive, tense_key, person_index):
                    expanded.append(st3 + end)

        for v in expanded:
            if v not in variants:
                variants.append(v)

    # De-dup
    out = []
    for v in variants:
        if v and v not in out:
            out.append(v)
    return out


def get_linguistic_stem(verb: str) -> str:
    """Get linguistic stem: infinitive without -re, -ir or -er."""
    stem = verb
    for ending in ["re", "ir", "er"]:
        if stem.endswith(ending):
            stem = stem[: -len(ending)]
            break
    return stem


def pick_audio_url(sounds: List[Dict]) -> str:
    """Pick a playable audio URL for the lemma pronunciation (if any)."""
    preferred_keys = ["mp3_url", "opus_url", "ogg_url", "oga_url", "wav_url", "flac_url"]
    for sound in sounds:
        for key in preferred_keys:
            url = (sound.get(key) or "").strip()
            if url:
                return url
    return ""


def normalize_for_audiofrench(text: str) -> str:
    text = text.replace("\u00A0", " ").replace("’", "'")
    text = text.replace("œ", "oe").replace("Œ", "Oe")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text


def audiofrench_infinitive_slug(infinitive: str) -> str:
    return normalize_for_audiofrench(infinitive).strip().lower()


def audiofrench_filename(form_text: str) -> str:
    text = normalize_for_audiofrench(form_text).strip().lower()
    # Wiktextract sometimes merges pronouns like "il/elle/on" or "ils/elles".
    # AudioFrench stores them separately; pick a representative form.
    text = re.sub(r"^il/elle/on\s+", "il ", text)
    text = re.sub(r"^ils/elles\s+", "ils ", text)
    text = re.sub(r"\s+", " ", text)
    return text.replace(" ", "_")


def audiofrench_url(infinitive: str, form_text: str) -> str:
    slug = quote(audiofrench_infinitive_slug(infinitive), safe="-._~")
    filename = quote(audiofrench_filename(form_text), safe="-._~'!()")
    return f"{AUDIOFRENCH_BASE_URL}/{slug}/{filename}.mp3"


def format_infinitive_with_ipa(verb: str, forms: List[Dict], sounds: List[Dict]) -> str:
    """Format infinitive with IPA below word."""
    # Try to get IPA from form first
    infinitive_forms = extract_conjugation(forms, ["infinitive", "present"])
    infinitive = infinitive_forms[0] if infinitive_forms else verb

    infinitive_escaped = html.escape(infinitive)
    audio_url = pick_audio_url(sounds)
    audio_attrs = ""
    audio_class = ""
    if audio_url:
        audio_attrs = (
            f" data-audio-url='{html.escape(audio_url, quote=True)}'"
            f" role='button' tabindex='0' title='Écouter la prononciation'"
        )
        audio_class = " clickable-audio"
    ipa_class_attr = f" class='{audio_class.strip()}'" if audio_class else ""
    speaker = (
        f"<span class='speaker{audio_class}'{audio_attrs} aria-label='Écouter'>🔊</span>"
        if audio_url
        else ""
    )

    wiktionary_url = (
        "https://fr.wiktionary.org/wiki/Conjugaison:fran%C3%A7ais/" + quote(infinitive)
    )
    wiktionary_link = (
        f"<a class='wiktionary-link' href='{html.escape(wiktionary_url, quote=True)}' "
        f"target='_blank' rel='noopener noreferrer'>Wiktionnaire</a>"
    )

    for form in forms:
        if form.get("form") == infinitive and "infinitive" in form.get("tags", []):
            _, ipa = extract_form_with_ipa(form)
            if ipa:
                ipa_html = (
                    f"<span{ipa_class_attr}{audio_attrs} style='color:{COLORS['purple']};font-style:italic'>"
                    f"\\{html.escape(ipa)}\\</span>"
                )
                return (
                    f"{infinitive_escaped}{speaker}<br>{ipa_html}<br>{wiktionary_link}"
                )

    # Fallback to sounds
    for sound in sounds:
        ipa = sound.get("ipa", "")
        if ipa and ipa.strip():
            ipa = ipa.strip("[]").strip("\\")
            ipa_html = (
                f"<span{ipa_class_attr}{audio_attrs} style='color:{COLORS['purple']};font-style:italic'>"
                f"\\{html.escape(ipa)}\\</span>"
            )
            return (
                f"{infinitive_escaped}{speaker}<br>{ipa_html}<br>{wiktionary_link}"
            )

    return f"{infinitive_escaped}<br>{wiktionary_link}"


def extract_ipa_ending(ipa: str, form_text: str) -> str:
    """Extract IPA ending with proper liaison and space handling."""
    if not ipa:
        return ""

    # Remove final bracket if present
    ipa = ipa.rstrip("]")

    # If there is a space, we want the second part (after the space)
    if " " in ipa:
        return ipa.split(" ", 1)[1]
    
    # If there is no space but there is a liaison mark, we want the part starting at the liaison mark
    if "‿" in ipa:
        # Find the first '‿' and return everything from there
        idx = ipa.find("‿")
        return ipa[idx:]

    # Fallback for simple cases: take last 2-3 characters
    if len(ipa) > 2:
        return ipa[-2:]
    return ipa


def apply_black_union_rules(forms: List[str]) -> str:
    """Find the shared beginning letters (prefix) of all forms."""
    if not forms:
        return ""
    
    # Start with the first form
    shared_prefix = forms[0]
    for form in forms[1:]:
        # Compare current shared_prefix with the next form
        temp_prefix = ""
        for i in range(min(len(shared_prefix), len(form))):
            if shared_prefix[i].lower() == form[i].lower():
                temp_prefix += shared_prefix[i]
            else:
                break
        shared_prefix = temp_prefix
        if not shared_prefix:
            break
    return shared_prefix


def colorize_form_with_black_union(
    form: str,
    shared_prefix: str,
    stem: str,
    color: str,
    irregular_mask: Optional[List[bool]] = None,
    highlight_color: Optional[str] = None,
) -> str:
    """
    Colorize form using black union rules:
    Rule 1: First appearances of the stem letters are black.
    Rule 2: Shared beginning letters (prefix) are black.
    Final black letters are the union of Rule 1 and Rule 2.
    """
    if not form:
        return form

    is_black = [False] * len(form)

    # Rule 1: First appearances of the stem letters
    temp_form = form.lower()
    last_idx = -1
    for char in stem.lower():
        idx = temp_form.find(char, last_idx + 1)
        # Only continue marking if current stem letter is found;
        # if one is missing, stop marking subsequent stem letters.
        if idx == -1:
            break
        is_black[idx] = True
        last_idx = idx

    # Rule 2: Shared beginning letters
    for i in range(len(shared_prefix)):
        if i < len(form) and form[i].lower() == shared_prefix[i].lower():
            is_black[i] = True
        else:
            break

    # Construct the colored HTML as spans (including black letters) so kerning/weight
    # stays consistent when switching colors.
    result: List[str] = []
    mode: Optional[str] = None  # black | color | hi

    def open_span(mode_name: str) -> None:
        if mode_name == "black":
            result.append(
                "<span style='color:#111827;font-weight:bold;font-kerning:none;font-feature-settings:\"kern\" 0'>"
            )
        elif mode_name == "hi":
            result.append(
                f"<span style='color:{highlight_color};font-weight:bold;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:2px;font-kerning:none;font-feature-settings:\"kern\" 0'>"
            )
        else:
            result.append(
                f"<span style='color:{color};font-weight:bold;font-kerning:none;font-feature-settings:\"kern\" 0'>"
            )

    for i, ch in enumerate(form):
        if is_black[i]:
            next_mode = "black"
        else:
            is_irregular = bool(
                irregular_mask and i < len(irregular_mask) and irregular_mask[i]
            )
            next_mode = "hi" if (is_irregular and highlight_color) else "color"

        if next_mode != mode:
            if mode is not None:
                result.append("</span>")
            open_span(next_mode)
            mode = next_mode

        result.append(html.escape(ch))

    if mode is not None:
        result.append("</span>")

    return "".join(result)


def format_participles_with_ipa(forms: List[Dict], infinitive: str) -> str:
    """Format participles with IPA below and black union coloring."""
    present_forms = extract_conjugation(forms, ["participle", "present"])
    past_forms = extract_conjugation(forms, ["participle", "past"])

    present_participle = present_forms[0] if present_forms else ""
    past_participle = past_forms[0] if past_forms else ""

    # Get IPA for each
    present_ipa = ""
    past_ipa = ""

    for form in forms:
        form_text, ipa = extract_form_with_ipa(form)
        if form_text == present_participle and ipa:
            present_ipa = ipa
        elif form_text == past_participle and ipa:
            past_ipa = ipa

    # Get stem for Rule 1
    stem = get_linguistic_stem(infinitive)

    # Apply black union rules to participle forms (Rule 2)
    participle_forms = [f for f in [present_participle, past_participle] if f]
    shared_prefix = apply_black_union_rules(participle_forms)

    present_colored = colorize_form_with_black_union(
        present_participle, shared_prefix, stem, COLORS["red"]
    )
    past_colored = colorize_form_with_black_union(
        past_participle, shared_prefix, stem, COLORS["red"]
    )

    # Participles use red color for non-black parts
    present_final = f"<span style='font-weight:bold'>{present_colored}</span>"
    past_final = f"<span style='font-weight:bold'>{past_colored}</span>"

    # Add IPA below each
    present_with_ipa = present_final
    past_with_ipa = past_final

    if present_ipa:
        guide_attr = (
            f" href='{html.escape(PRONUNCIATION_GUIDE_URL, quote=True)}' "
            f"target='_blank' rel='noopener noreferrer' "
            f"title='Guide de prononciation (IPA)'"
        )
        present_with_ipa += (
            f"<br><a class='ipa-link'{guide_attr} style='color:{COLORS['purple']};font-style:italic'>"
            f"\\{present_ipa}\\</a>"
        )

    if past_ipa:
        guide_attr = (
            f" href='{html.escape(PRONUNCIATION_GUIDE_URL, quote=True)}' "
            f"target='_blank' rel='noopener noreferrer' "
            f"title='Guide de prononciation (IPA)'"
        )
        past_with_ipa += (
            f"<br><a class='ipa-link'{guide_attr} style='color:{COLORS['purple']};font-style:italic'>"
            f"\\{past_ipa}\\</a>"
        )

    # Stack vertically
    if present_with_ipa and past_with_ipa:
        return f"{present_with_ipa}<br>{past_with_ipa}"
    elif present_with_ipa:
        return present_with_ipa
    elif past_with_ipa:
        return past_with_ipa
    else:
        return ""


def clean_form_text(form_text: str) -> str:
    """Remove subject pronoun and j' from form text."""
    # Remove j' first as it destroys matching
    text = re.sub(r"^[jJ]’", "", form_text)
    if " " in text:
        return text.split(" ", 1)[1]
    return text


def format_tense_intelligent(
    forms_with_ipa: List[Tuple[str, str]],
    color: str,
    infinitive: str = "",
    enable_audiofrench: bool = False,
    tense_key: str = "",
    stems: Optional[Dict[str, str]] = None,
) -> str:
    """Colorize tense forms with intelligent black union rules."""
    if len(forms_with_ipa) < 6:
        return ""

    # Extract clean forms for analysis
    clean_forms = []
    for form_text, ipa in forms_with_ipa:
        clean_form = clean_form_text(form_text)
        clean_forms.append(clean_form)

    # Get linguistic stem for Rule 1
    stem = get_linguistic_stem(infinitive) if infinitive else ""

    # Apply black union rules (Rule 2: shared prefix)
    shared_prefix = apply_black_union_rules(clean_forms)

    # Format as 6x2 table: person | form | IPA
    rows = []
    guide_attr = (
        f" href='{html.escape(PRONUNCIATION_GUIDE_URL, quote=True)}' "
        f"target='_blank' rel='noopener noreferrer' "
        f"title='Guide de prononciation (IPA)'"
    )
    for i in range(6):
        form_text, ipa = forms_with_ipa[i]

        # Clean form text (remove pronoun)
        display_form = clean_form_text(form_text)

        # Colorize with Rule 1 (stem) and Rule 2 (shared prefix)
        expected_variants = (
            expected_regular_variants(infinitive, tense_key, i, stems=stems)
            if tense_key
            else []
        )
        irregular_mask = best_expected_mask(display_form, expected_variants)
        highlight_color = None
        if color == COLORS["red"]:
            highlight_color = COLORS["red_hi"]
        elif color == COLORS["blue"]:
            highlight_color = COLORS["blue_hi"]
        elif color == COLORS["green"]:
            highlight_color = COLORS["green_hi"]
        elif color == COLORS["purple"]:
            highlight_color = COLORS["purple_hi"]

        colored_form = colorize_form_with_black_union(
            display_form,
            shared_prefix,
            stem,
            color,
            irregular_mask=irregular_mask,
            highlight_color=highlight_color,
        )
        if enable_audiofrench and infinitive:
            url = audiofrench_url(infinitive, form_text)
            colored_form = (
                f"<a class='audiofrench-link' href='{html.escape(url, quote=True)}' "
                f"data-audio-url='{html.escape(url, quote=True)}' role='button' tabindex='0' "
                f"target='_blank' rel='noopener noreferrer' title='Écouter (AudioFrench)'>"
                f"{colored_form}</a>"
            )

        # Extract IPA ending
        ipa_ending = extract_ipa_ending(ipa, form_text)
        ipa_display = (
            f"<a class='ipa-link'{guide_attr} style='color:{COLORS['salmon']};font-style:italic'>[{ipa_ending}]</a>"
            if ipa_ending
            else ""
        )

        rows.append(f"<td>{colored_form}</td><td>{ipa_display}</td>")

    # Create 6x2 HTML table
    table_html = (
        """<table class='tense-table'>
    <tr>"""
        + "</tr><tr>".join(rows)
        + """</tr>
</table>"""
    )

    return table_html


def process_verb_entry(entry: Dict) -> Optional[Dict]:
    """Process a single verb entry from the JSON data."""
    word = entry.get("word", "")
    pos = entry.get("pos", "")
    lang_code = entry.get("lang_code", "")

    # Only process French verbs
    if pos != "verb" or lang_code != "fr":
        return None

    # Only process our test verbs
    if word not in TEST_VERBS:
        return None

    forms = entry.get("forms", [])
    sounds = entry.get("sounds", [])

    # Extract infinitive with IPA below
    infinitive = format_infinitive_with_ipa(word, forms, sounds)

    # Extract participles stacked with IPA and intelligent coloring
    participles = format_participles_with_ipa(forms, word)

    # Extract tenses - 6 forms each
    present_forms = extract_tense_forms(forms, ["indicative", "present"])
    imparfait_forms = extract_tense_forms(forms, ["indicative", "imperfect"])
    passe_simple_forms = extract_tense_forms(
        forms, ["indicative", "past"], ["multiword-construction", "anterior"]
    )
    futur_simple_forms = extract_tense_forms(forms, ["indicative", "future"])

    stems = derive_stems(word, present_forms)

    # Format tenses with intelligent coloring
    present = format_tense_intelligent(
        present_forms,
        COLORS["red"],
        word,
        enable_audiofrench=True,
        tense_key="present",
        stems=stems,
    )
    imparfait = format_tense_intelligent(
        imparfait_forms,
        COLORS["blue"],
        word,
        enable_audiofrench=True,
        tense_key="imparfait",
        stems=stems,
    )
    passe_simple = format_tense_intelligent(
        passe_simple_forms,
        COLORS["green"],
        word,
        enable_audiofrench=False,
        tense_key="passe_simple",
        stems=stems,
    )
    futur_simple = format_tense_intelligent(
        futur_simple_forms,
        COLORS["purple"],
        word,
        enable_audiofrench=True,
        tense_key="futur",
        stems=stems,
    )

    irregularity = compute_irregularity_marker(
        word,
        present_forms,
        imparfait_forms,
        passe_simple_forms,
        futur_simple_forms,
        stems,
    )

    return {
        "verb": word,
        "infinitive": infinitive,
        "participles": participles,
        "present": present,
        "imparfait": imparfait,
        "passe_simple": passe_simple,
        "futur_simple": futur_simple,
        "irregularity": irregularity,
    }


def main():
    """Main function to extract and process verb data."""
    input_file = "fr-extract.jsonl.gz"
    output_file = "french_conjugations.html"

    print(f"Processing {input_file}...")

    results = []
    processed_count = 0

    try:
        with gzip.open(input_file, "rt", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    entry = json.loads(line.strip())
                    verb_data = process_verb_entry(entry)

                    if verb_data:
                        results.append(verb_data)
                        print(f"Found: {verb_data['verb']}")
                        processed_count += 1

                        # Stop if we've found all test verbs
                        if processed_count >= len(TEST_VERBS):
                            break

                except json.JSONDecodeError as e:
                    print(f"JSON decode error at line {line_num}: {e}")
                    continue
                except Exception as e:
                    print(f"Error processing line {line_num}: {e}")
                    continue

    except FileNotFoundError:
        print(f"Error: {input_file} not found!")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Write to HTML with pretty formatting
    if results:
        print(f"\nWriting {len(results)} verbs to {output_file}")

        html_content = f"""<!DOCTYPE html>
		<html>
		<head>
		    <meta charset="utf-8">
		    <title>Conjugaison des verbes français</title>
	    <style>
	        body {{ font-family: Arial, sans-serif; margin: 20px; font-size: 18px; }}
	        table {{ border-collapse: collapse; width: 100%; }}
	        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; vertical-align: top; }}
	        th {{ background-color: #f2f2f2; font-weight: bold; }}
		        .verb {{ font-weight: bold; font-size: 20px; }}
		        .irregularity {{ font-size: 20px; display: block; margin-top: 5px; }}
		        .wiktionary-link {{ font-size: 12px; font-weight: normal; }}
		        .speaker {{ margin-left: 6px; font-weight: normal; }}
		        .clickable-audio {{ cursor: pointer; user-select: none; }}
		        .clickable-audio:hover {{ text-decoration: underline; }}
		        .speaker.clickable-audio:hover {{ text-decoration: none; }}
		        .ipa-link {{ text-decoration: none; }}
		        .ipa-link:hover {{ text-decoration: underline; }}
	        .audiofrench-link {{ text-decoration: none; color: inherit; cursor: pointer; }}
	        .audiofrench-link:hover {{ text-decoration: underline; }}
	        .tense-table td:nth-child(2) {{ font-kerning: none; font-feature-settings: "kern" 0; }}
	        .tense-table {{ font-size: 14px; border-collapse: collapse; }}
	        .tense-table td {{ padding: 3px 6px; border: none; text-align: left; }}
	        .tense-table td:first-child {{ width: 35%; }}
	        .tense-table td:last-child {{ width: 65%; font-style: italic; }}
	        .participles {{ text-align: center; font-size: 16px; }}
		    </style>
	    <script>
        (function () {{
            let currentAudio = null;
            function playUrl(url) {{
                if (!url) return;
                try {{
                    if (currentAudio) currentAudio.pause();
                    currentAudio = new Audio(url);
                    currentAudio.play();
                }} catch (e) {{
                    console.warn("Audio playback failed:", e);
                }}
            }}
            document.addEventListener("click", function (e) {{
                const el = e.target.closest("[data-audio-url]");
                if (!el) return;
                e.preventDefault();
                playUrl(el.dataset.audioUrl);
            }});
            document.addEventListener("keydown", function (e) {{
                if (e.key !== "Enter" && e.key !== " ") return;
                const el = document.activeElement;
                if (!el || !el.dataset || !el.dataset.audioUrl) return;
                e.preventDefault();
                playUrl(el.dataset.audioUrl);
            }});
        }})();
    </script>
	</head>
	<body>
	    <h1>Conjugaison des verbes français</h1>
	    <p><a href="{PRONUNCIATION_GUIDE_URL}" target="_blank" rel="noopener noreferrer">Guide de prononciation (IPA)</a></p>
	    <p><a href="{LINGOLIA_TENSES_URL}" target="_blank" rel="noopener noreferrer">Les temps de l’indicatif – La conjugaison française</a></p>
	    <p><strong>Légende :</strong> 🟢 Régulier | 🔴 Très irrégulier | 🟡 Irrégularité moyenne | 🟠 Radical irrégulier / changement de radical<br><small>Astuce : cliquez sur 🔊 (ou sur l'IPA sous l'infinitif) pour écouter. Cliquez sur l'IPA dans les tableaux pour ouvrir le guide. Cliquez sur une forme conjuguée (présent / imparfait / futur) pour écouter via <a href="{AUDIOFRENCH_VERB_INDEX_URL}" target="_blank" rel="noopener noreferrer">AudioFrench.com</a>.</small></p>
	    <table>
	        <thead>
	            <tr>
                <th>Verbe / Infinitif</th>
                <th>Participes<br><small>(présent / passé)</small></th>
                <th>Présent</th>
                <th>Imparfait</th>
                <th>Passé simple</th>
                <th>Futur simple</th>
            </tr>
        </thead>
        <tbody>"""

        for result in results:
            marker = result["irregularity"] or "🟢"
            hint = IRREGULARITY_HINTS_FR.get(marker, "")
            hint_attr = f" title='{html.escape(hint, quote=True)}'" if hint else ""
            html_content += f"""
            <tr>
                <td class="verb">{result["infinitive"]}<br><span class="irregularity"{hint_attr}>{marker}</span></td>
                <td class="participles">{result["participles"]}</td>
                <td class="tense-table">{result["present"]}</td>
                <td class="tense-table">{result["imparfait"]}</td>
                <td class="tense-table">{result["passe_simple"]}</td>
                <td class="tense-table">{result["futur_simple"]}</td>
            </tr>"""

        html_content += """
        </tbody>
    </table>
</body>
</html>"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        print("Done! HTML table created with proper black union coloring.")
        print(f"Open {output_file} in your browser to see formatted table.")
    else:
        print("No verb data found!")


if __name__ == "__main__":
    main()
