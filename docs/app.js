const PRONUNCIATION_GUIDE_URL =
  "https://fr.wiktionary.org/wiki/Annexe:Prononciation/fran%C3%A7ais";
const WIKTIONARY_CONJ_BASE =
  "https://fr.wiktionary.org/wiki/Conjugaison:fran%C3%A7ais/";
const AUDIOFRENCH_BASE = "http://www.audiofrench.com/verbs/sounds";

const IRR_HINTS = {
  "🔴": "Très irrégulier",
  "🟡": "Irrégularité moyenne",
  "🟠": "Radical irrégulier / changement de radical",
  "🟢": "Régulier",
};

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#x27;");
}

function normalizeFrench(text) {
  return text
    .toLowerCase()
    .replaceAll("œ", "oe")
    .replaceAll("’", "'")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function verbGroup(inf) {
  if (inf.endsWith("er")) return "er";
  if (inf.endsWith("ir")) return "ir";
  if (inf.endsWith("re")) return "re";
  return "other";
}

function linguisticStem(inf) {
  for (const ending of ["er", "ir", "re"]) {
    if (inf.endsWith(ending)) return inf.slice(0, -ending.length);
  }
  return inf;
}

function applyBlackUnionRules(forms) {
  if (!forms.length) return "";
  let shared = forms[0];
  for (const form of forms.slice(1)) {
    let tmp = "";
    for (let i = 0; i < Math.min(shared.length, form.length); i++) {
      if (shared[i].toLowerCase() === form[i].toLowerCase()) tmp += shared[i];
      else break;
    }
    shared = tmp;
    if (!shared) break;
  }
  return shared;
}

function markStemLetters(form, stem) {
  const isBlack = new Array(form.length).fill(false);
  let lastIdx = -1;
  const lower = form.toLowerCase();
  for (const ch of stem.toLowerCase()) {
    const idx = lower.indexOf(ch, lastIdx + 1);
    if (idx === -1) break;
    isBlack[idx] = true;
    lastIdx = idx;
  }
  return isBlack;
}

function mergeSharedPrefix(isBlack, form, sharedPrefix) {
  for (let i = 0; i < sharedPrefix.length; i++) {
    if (i < form.length && form[i].toLowerCase() === sharedPrefix[i].toLowerCase()) {
      isBlack[i] = true;
    } else {
      break;
    }
  }
}

function editMask(actual, expected) {
  const a = actual;
  const b = expected;
  const n = a.length;
  const m = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  const bt = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(null));

  for (let i = 1; i <= m; i++) {
    dp[i][0] = i;
    bt[i][0] = "del";
  }
  for (let j = 1; j <= n; j++) {
    dp[0][j] = j;
    bt[0][j] = "ins";
  }

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      const cost = b[i - 1] === a[j - 1] ? 0 : 1;
      const del = dp[i - 1][j] + 1;
      const ins = dp[i][j - 1] + 1;
      const rep = dp[i - 1][j - 1] + cost;
      let best = rep;
      let op = cost === 0 ? "eq" : "rep";
      if (ins < best) {
        best = ins;
        op = "ins";
      }
      if (del < best) {
        best = del;
        op = "del";
      }
      dp[i][j] = best;
      bt[i][j] = op;
    }
  }

  const mask = new Array(n).fill(false);
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    const op = bt[i][j];
    if (op === "eq") {
      i--;
      j--;
    } else if (op === "rep") {
      mask[j - 1] = true;
      i--;
      j--;
    } else if (op === "ins") {
      mask[j - 1] = true;
      j--;
    } else if (op === "del") {
      i--;
    } else {
      break;
    }
  }

  return { score: dp[m][n], mask };
}

function cerGerVariants(form, inf, ending) {
  const variants = [form];
  const lower = inf.toLowerCase();
  const first = ending ? ending[0] : "";
  if (lower.endsWith("cer") && ["a", "â", "o"].includes(first)) {
    variants.push(form.replace(/c(?=[aâo])/g, "ç"));
  }
  if (lower.endsWith("ger") && ["a", "â", "o"].includes(first)) {
    variants.push(form.replace(/g(?=[aâo])/g, "ge"));
  }
  return [...new Set(variants)];
}

function yToIVariants(stem, optional) {
  if (!stem.includes("y")) return [stem];
  const idx = stem.lastIndexOf("y");
  if (idx === -1) return [stem];
  const changed = stem.slice(0, idx) + "i" + stem.slice(idx + 1);
  return optional ? [stem, changed] : [changed];
}

function yerStemVariants(stem, inf, tenseKey, personIndex) {
  if (tenseKey !== "present") return [stem];
  const silentE = new Set([0, 1, 2, 5]);
  if (!silentE.has(personIndex)) return [stem];
  const lower = inf.toLowerCase();
  if (lower.endsWith("oyer") || lower.endsWith("uyer")) return yToIVariants(stem, false);
  if (lower.endsWith("ayer")) return yToIVariants(stem, true);
  return [stem];
}

function eToEGrave(stem) {
  const idx = stem.lastIndexOf("e");
  if (idx === -1) return stem;
  return stem.slice(0, idx) + "è" + stem.slice(idx + 1);
}

function eAcuteToEGrave(stem) {
  const idx = stem.lastIndexOf("é");
  if (idx === -1) return stem;
  return stem.slice(0, idx) + "è" + stem.slice(idx + 1);
}

function eerStemVariants(stem, inf, tenseKey, personIndex) {
  if (tenseKey !== "present") return [stem];
  const silentE = new Set([0, 1, 2, 5]);
  if (!silentE.has(personIndex)) return [stem];

  const lower = inf.toLowerCase();
  const variants = [stem];
  if (/é[^aeiouy]*er$/.test(lower)) variants.push(eAcuteToEGrave(stem));
  else if (/e[^aeiouy]*er$/.test(lower)) variants.push(eToEGrave(stem));
  return [...new Set(variants)];
}

function elerEterStemVariants(stem, inf, tenseKey, personIndex) {
  if (tenseKey !== "present") return [stem];
  const silentE = new Set([0, 1, 2, 5]);
  if (!silentE.has(personIndex)) return [stem];
  const lower = inf.toLowerCase();
  if (!(lower.endsWith("eler") || lower.endsWith("eter"))) return [stem];

  const variants = [stem, eToEGrave(stem)];
  if (lower.endsWith("eler") && stem.endsWith("el")) {
    const doubled = stem.slice(0, -1) + "ll";
    variants.push(doubled, eToEGrave(doubled));
  }
  if (lower.endsWith("eter") && stem.endsWith("et")) {
    const doubled = stem.slice(0, -1) + "tt";
    variants.push(doubled, eToEGrave(doubled));
  }
  return [...new Set(variants)];
}

function regularEnding(inf, tenseKey, personIndex) {
  const group = verbGroup(inf);
  if (tenseKey === "present") {
    if (group === "er") return ["e", "es", "e", "ons", "ez", "ent"][personIndex];
    if (group === "ir") return ["is", "is", "it", "issons", "issez", "issent"][personIndex];
    if (group === "re") return ["s", "s", "", "ons", "ez", "ent"][personIndex];
    return "";
  }
  if (tenseKey === "imparfait") return ["ais", "ais", "ait", "ions", "iez", "aient"][personIndex];
  if (tenseKey === "futur") return ["ai", "as", "a", "ons", "ez", "ont"][personIndex];
  if (tenseKey === "passe_simple") {
    if (group === "er") return ["ai", "as", "a", "âmes", "âtes", "èrent"][personIndex];
    if (group === "ir" || group === "re") return ["is", "is", "it", "îmes", "îtes", "irent"][personIndex];
  }
  return "";
}

function expectedBaseForm(inf, tenseKey, personIndex, stems) {
  const group = verbGroup(inf);
  const stem = group === "other" ? inf : inf.slice(0, -2);

  if (tenseKey === "present") {
    const ending = regularEnding(inf, tenseKey, personIndex);
    return stem + ending;
  }
  if (tenseKey === "imparfait") {
    const ending = regularEnding(inf, tenseKey, personIndex);
    let base = stem;
    if (stems && stems.imparfaitStem) base = stems.imparfaitStem;
    else if (group === "ir") base = stem + "iss";
    return base + ending;
  }
  if (tenseKey === "futur") {
    const ending = regularEnding(inf, tenseKey, personIndex);
    const base = group === "re" ? inf.slice(0, -1) : inf;
    return base + ending;
  }
  if (tenseKey === "passe_simple") {
    const ending = regularEnding(inf, tenseKey, personIndex);
    return stem + ending;
  }
  return "";
}

function expectedRegularVariants(inf, tenseKey, personIndex, stems) {
  const group = verbGroup(inf);
  const base = expectedBaseForm(inf, tenseKey, personIndex, stems);
  if (!base) return [];

  const ending = regularEnding(inf, tenseKey, personIndex);
  let variants = [base];
  variants = variants.flatMap((f) => cerGerVariants(f, inf, ending));

  if (tenseKey === "present" && group !== "other") {
    const stem = inf.slice(0, -2);
    const end = regularEnding(inf, "present", personIndex);
    const expanded = [];
    for (const st1 of yerStemVariants(stem, inf, tenseKey, personIndex)) {
      for (const st2 of eerStemVariants(st1, inf, tenseKey, personIndex)) {
        for (const st3 of elerEterStemVariants(st2, inf, tenseKey, personIndex)) {
          expanded.push(st3 + end);
        }
      }
    }
    variants.push(...expanded);
  }

  return [...new Set(variants)].filter(Boolean);
}

function bestExpectedMask(actual, expectedVariants) {
  if (!expectedVariants.length) return null;
  let best = null;
  let bestScore = Infinity;
  for (const exp of expectedVariants) {
    const { score, mask } = editMask(actual, exp);
    if (score < bestScore) {
      bestScore = score;
      best = mask;
      if (bestScore === 0) break;
    }
  }
  return best;
}

function colorizeForm(form, sharedPrefix, stem, classes, irregularMask) {
  const isBlack = markStemLetters(form, stem);
  mergeSharedPrefix(isBlack, form, sharedPrefix);

  let out = "";
  let mode = null; // black | normal | hi

  function open(modeName) {
    if (modeName === "black") out += `<span class="c-black">`;
    if (modeName === "normal") out += `<span class="${classes.normal}">`;
    if (modeName === "hi") out += `<span class="${classes.hi}">`;
  }
  function close() {
    out += "</span>";
  }

  for (let i = 0; i < form.length; i++) {
    const nextMode = isBlack[i]
      ? "black"
      : Boolean(irregularMask && irregularMask[i])
      ? "hi"
      : "normal";
    if (mode !== nextMode) {
      if (mode) close();
      mode = nextMode;
      open(mode);
    }
    out += escapeHtml(form[i]);
  }

  if (mode) close();
  return out;
}

function extractIpaEnding(ipa) {
  if (!ipa) return "";
  let s = ipa.replace(/^\[/, "").replace(/\]$/, "");
  s = s.replace(/^\\+/, "").replace(/\\+$/, "");
  if (s.includes(" ")) return s.split(" ", 2)[1];
  const idx = s.indexOf("‿");
  if (idx !== -1) return s.slice(idx);
  if (s.length > 2) return s.slice(-2);
  return s;
}

function extractIpaFull(ipa) {
  if (!ipa) return "";
  let s = ipa.replace(/^\[/, "").replace(/\]$/, "");
  s = s.replace(/^\\+/, "").replace(/\\+$/, "");
  return s.trim();
}

function makeAudioFrenchUrl(infinitive, personIndex, form) {
  const slug = normalizeFrench(infinitive);
  const vowels = new Set(
    Array.from("aeiouyàâäéèêëîïôöùûüœh")
  );

  let pronoun = ["je", "tu", "il", "nous", "vous", "ils"][personIndex] || "je";
  let filename = "";

  if (pronoun === "je" && form && vowels.has(normalizeFrench(form)[0])) {
    filename = `j'${form}`;
  } else {
    filename = `${pronoun}_${form}`;
  }

  const pathPart = encodeURIComponent(normalizeFrench(filename)).replaceAll("%27", "'"); // keep apostrophe readable
  return `${AUDIOFRENCH_BASE}/${encodeURIComponent(slug)}/${pathPart}.mp3`;
}

function wikiConjUrl(inf) {
  return WIKTIONARY_CONJ_BASE + encodeURIComponent(inf);
}

function buildInfinitiveCell(v) {
  const word = escapeHtml(v.w);
  const alt = v.alt
    ? ` <span class="alt-badge" title="Formes alternatives : voir le Wiktionnaire">var.</span>`
    : "";
  const wiki = `<a class="wiktionary-link" href="${wikiConjUrl(v.w)}" target="_blank" rel="noopener noreferrer">Wiktionnaire</a>${alt}`;

  const speaker =
    v.audio && v.audio.length
      ? `<span class="speaker clickable-audio" data-audio-url="${escapeHtml(v.audio)}" role="button" tabindex="0" title="Écouter la prononciation" aria-label="Écouter">🔊</span>`
      : "";

  const wordSpan =
    v.audio && v.audio.length
      ? `<span class="inf-word clickable-audio" data-audio-url="${escapeHtml(
          v.audio
        )}" role="button" tabindex="0" title="Écouter la prononciation">${word}</span>`
      : `<span class="inf-word">${word}</span>`;

  const ipa =
    v.ipa && v.ipa.length
      ? `<span class="lemma-ipa clickable-audio" data-audio-url="${escapeHtml(v.audio || "")}" role="button" tabindex="0" title="Écouter la prononciation">\\${escapeHtml(
          v.ipa
        )}\\</span>`
      : "";

  const marker = v.irr && v.irr.length ? v.irr : "🟢";
  const hint = IRR_HINTS[marker] || "";
  const hintAttr = hint ? ` title="${escapeHtml(hint)}"` : "";
  const irr = `<span class="irregularity"${hintAttr}>${escapeHtml(marker)}</span>`;

  return `<td class="verb">
    <div class="cell-label">Infinitif</div>
    <div class="inf-row">
      <div class="inf-left cell-scroll">
        <div class="inf-wordline">${wordSpan}${speaker}</div>
        <div class="inf-ipaline">${ipa}</div>
      </div>
      <div class="inf-right">
        <div class="inf-marker">${irr}</div>
        <div class="inf-links">${wiki}</div>
      </div>
    </div>
  </td>`;
}

function buildParticiplesCell(v) {
  const pres = v.part?.pres?.f || "";
  const past = v.part?.past?.f || "";
  const presIpa = v.part?.pres?.ipa || "";
  const pastIpa = v.part?.past?.ipa || "";
  const stem = linguisticStem(v.w);
  const forms = [pres, past].filter(Boolean);
  const shared = applyBlackUnionRules(forms);

  const classes = { normal: "c-red", hi: "c-red-hi" };

  function colored(form) {
    return colorizeForm(form, shared, stem, classes, null);
  }

  const presIpaFull = extractIpaFull(presIpa);
  const pastIpaFull = extractIpaFull(pastIpa);

  const p = pres
    ? `<div class="part-formline"><span class="part-form" style="font-weight:700">${colored(
        pres
      )}</span></div>${
        presIpaFull
          ? `<div class="part-ipaline"><a class="ipa-link part-ipa" href="${PRONUNCIATION_GUIDE_URL}" target="_blank" rel="noopener noreferrer" title="Guide de prononciation (IPA)">\\${escapeHtml(
              presIpaFull
            )}\\</a></div>`
          : ""
      }`
    : "";

  const q = past
    ? `<div class="part-formline"><span class="part-form" style="font-weight:700">${colored(
        past
      )}</span></div>${
        pastIpaFull
          ? `<div class="part-ipaline"><a class="ipa-link part-ipa" href="${PRONUNCIATION_GUIDE_URL}" target="_blank" rel="noopener noreferrer" title="Guide de prononciation (IPA)">\\${escapeHtml(
              pastIpaFull
            )}\\</a></div>`
          : ""
      }`
    : "";

  return `<td class="participles">
    <div class="cell-label">Participes</div>
    <div class="cell-scroll">
      <div class="part-grid">
        <div class="part-item">${p}</div>
        <div class="part-item">${q}</div>
      </div>
    </div>
  </td>`;
}

function tenseClasses(tenseKey) {
  if (tenseKey === "pr") return { normal: "c-red", hi: "c-red-hi" };
  if (tenseKey === "imp") return { normal: "c-teal", hi: "c-teal-hi" };
  if (tenseKey === "ps") return { normal: "c-green", hi: "c-green-hi" };
  return { normal: "c-blue", hi: "c-blue-hi" }; // fut
}

function buildTenseCell(v, tenseKey) {
  const forms = v.t?.[tenseKey] || [];
  if (forms.length < 6) return `<td class="tense-cell"></td>`;
  const words = forms.map((x) => x.f);
  const shared = applyBlackUnionRules(words);
  const stem = linguisticStem(v.w);

  const stems = {};
  const nous = v.t?.pr?.[3]?.f || "";
  if (nous.endsWith("ons")) stems.imparfaitStem = nous.slice(0, -3);

  const tenseMap = { pr: "present", imp: "imparfait", ps: "passe_simple", fut: "futur" };
  const tk = tenseMap[tenseKey] || "";
  const ending = (idx) => regularEnding(v.w, tk, idx);

  const classes = tenseClasses(tenseKey);

  const rows = [];
  const gridItems = [];
  for (let i = 0; i < 6; i++) {
    const form = words[i] || "";
    const expectedVariants = expectedRegularVariants(v.w, tk, i, stems);
    const irregularMask = bestExpectedMask(form, expectedVariants);
    let colored = colorizeForm(form, shared, stem, classes, irregularMask);

    const pron = ["je", "tu", "il/elle/on/iel", "nous", "vous", "ils/elles/iels"][i] || "";

    if (tenseKey !== "ps") {
      const url = makeAudioFrenchUrl(v.w, i, form);
      colored = `<a class="audiofrench-link" href="${escapeHtml(
        url
      )}" data-audio-url="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="Écouter (AudioFrench)">${colored}</a>`;
    }

    const ipaEnding = extractIpaEnding(forms[i].ipa || "");
    const ipa = ipaEnding
      ? `<a class="ipa-link" href="${PRONUNCIATION_GUIDE_URL}" target="_blank" rel="noopener noreferrer" title="Guide de prononciation (IPA)">[${escapeHtml(
          ipaEnding
        )}]</a>`
      : "";

    rows.push(
      `<td class="tense-row-col"><div class="tense-row"><span class="tense-form-inline">${colored}</span>${
        ipa ? `<span class="tense-ipa-inline">${ipa}</span>` : ""
      }</div></td>`
    );

    const boxAudioAttr =
      tenseKey !== "ps"
        ? ` data-audio-url="${escapeHtml(makeAudioFrenchUrl(v.w, i, form))}" title="Écouter (AudioFrench)"`
        : "";

    const formAttr = ` data-form="${escapeHtml(form)}"`;
    gridItems.push(
      `<div class="tense-item" tabindex="-1"${boxAudioAttr}${formAttr}>
        <div class="tense-pron">${escapeHtml(pron)}</div>
        <div class="tense-form">${colored}</div>
        <div class="tense-ipa">${ipa}</div>
      </div>`
    );
  }

  const table = `<div class="tense-scroll"><table class="tense-table"><tr>${rows.join(
    "</tr><tr>"
  )}</tr></table></div>`;
  const grid = `<div class="tense-grid">${gridItems.join("")}</div>`;
  const label =
    tenseKey === "pr"
      ? "Présent"
      : tenseKey === "imp"
      ? "Imparfait"
      : tenseKey === "ps"
      ? "Passé simple"
      : "Futur simple";
  return `<td class="tense-cell"><div class="cell-label">${label}</div>${table}${grid}</td>`;
}

function buildRow(v) {
  const cells = [
    buildInfinitiveCell(v),
    buildParticiplesCell(v),
    buildTenseCell(v, "pr"),
    buildTenseCell(v, "imp"),
    buildTenseCell(v, "ps"),
    buildTenseCell(v, "fut"),
  ];
  return `<tr data-word="${escapeHtml(v.w)}" tabindex="-1">${cells.join("")}</tr>`;
}

function suggest(words, query, limit = 10) {
  const q = normalizeFrench(query.trim());
  if (!q) return [];
  const starts = [];
  const includes = [];

  for (const w of words) {
    const n = normalizeFrench(w);
    if (n.startsWith(q)) starts.push(w);
    else if (n.includes(q)) includes.push(w);
    if (starts.length >= limit) break;
  }

  const out = starts.length >= limit ? starts.slice(0, limit) : starts.concat(includes).slice(0, limit);
  return out;
}

function setupAudioClickHandler() {
  let currentAudio = null;
  function playUrl(url) {
    if (!url) return;
    try {
      if (currentAudio) currentAudio.pause();
      currentAudio = new Audio(url);
      currentAudio.play();
    } catch (e) {
      console.warn("Audio playback failed:", e);
    }
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("a.ipa-link")) return;
    const el = e.target.closest("[data-audio-url]");
    if (!el) return;
    e.preventDefault();
    playUrl(el.dataset.audioUrl);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const el = document.activeElement;
    if (!el || !el.dataset || !el.dataset.audioUrl) return;
    e.preventDefault();
    playUrl(el.dataset.audioUrl);
  });
}

function adjustMobileParticiplesLayout() {
  const portrait = window.matchMedia("(max-width: 700px) and (orientation: portrait)");
  function run() {
    for (const cell of document.querySelectorAll("td.participles")) {
      cell.dataset.ipaBelow = "";
      if (!portrait.matches) continue;
      const items = cell.querySelectorAll(".part-item");
      let overflow = false;
      for (const item of items) {
        if (item.scrollWidth > item.clientWidth + 1) {
          overflow = true;
          break;
        }
      }
      if (overflow) cell.dataset.ipaBelow = "1";
    }
  }

  if (!adjustMobileParticiplesLayout._setup) {
    adjustMobileParticiplesLayout._setup = true;
    window.addEventListener("resize", () => {
      window.clearTimeout(adjustMobileParticiplesLayout._t);
      adjustMobileParticiplesLayout._t = window.setTimeout(run, 60);
    });
    portrait.addEventListener?.("change", run);
  }

  run();
}

function adjustMobileTenseGridLayout() {
  const portrait = window.matchMedia("(max-width: 700px) and (orientation: portrait)");
  function run() {
    for (const grid of document.querySelectorAll(".tense-grid")) {
      delete grid.dataset.layout;
      if (!portrait.matches) continue;
      let force2 = false;

      const gridRect = grid.getBoundingClientRect();
      for (const item of grid.querySelectorAll(".tense-item")) {
        const itemRect = item.getBoundingClientRect();
        if (itemRect.right > gridRect.right + 0.5) {
          force2 = true;
          break;
        }
        if (item.scrollWidth > item.clientWidth + 1) {
          force2 = true;
          break;
        }
        const form = item.querySelector(".tense-form");
        if (!form) continue;
        const over = form.scrollWidth > form.clientWidth + 1;
        if (over) {
          force2 = true;
          break;
        }
      }
      if (force2) grid.dataset.layout = "2x3";
    }
  }

  if (!adjustMobileTenseGridLayout._setup) {
    adjustMobileTenseGridLayout._setup = true;
    window.addEventListener("resize", () => {
      window.clearTimeout(adjustMobileTenseGridLayout._t);
      adjustMobileTenseGridLayout._t = window.setTimeout(run, 60);
    });
    portrait.addEventListener?.("change", run);
  }
  run();
}

function adjustDesktopTenseIpaLayout() {
  const portrait = window.matchMedia("(max-width: 700px) and (orientation: portrait)");
  function run() {
    for (const cell of document.querySelectorAll("td.tense-cell")) {
      cell.dataset.ipaBelow = "";
      if (portrait.matches) continue;
      const scroller = cell.querySelector(".tense-scroll");
      if (!scroller) continue;
      if (scroller.scrollWidth > scroller.clientWidth + 1) {
        cell.dataset.ipaBelow = "1";
      }
    }
  }

  if (!adjustDesktopTenseIpaLayout._setup) {
    adjustDesktopTenseIpaLayout._setup = true;
    window.addEventListener("resize", () => {
      window.clearTimeout(adjustDesktopTenseIpaLayout._t);
      adjustDesktopTenseIpaLayout._t = window.setTimeout(run, 60);
    });
  }
  run();
}

function cryptoRandomInt(maxExclusive) {
  if (maxExclusive <= 0) return 0;
  const buf = new Uint32Array(1);
  crypto.getRandomValues(buf);
  return buf[0] % maxExclusive;
}

function collectAllForms(v) {
  const out = [];
  const add = (s) => {
    if (s && typeof s === "string") out.push(s);
  };
  add(v.w);
  add(v.part?.pres?.f);
  add(v.part?.past?.f);
  for (const key of ["pr", "imp", "ps", "fut"]) {
    for (const x of v.t?.[key] || []) add(x.f);
  }
  return out;
}

function computeSuggestions(entries, query, limit = 10) {
  const q = normalizeFrench(query.trim());
  if (!q) return [];

  const suggestions = [];
  const seen = new Set();

  // 1) Exact match (infinitive or any form)
  for (const e of entries) {
    if (e.norm === q) {
      suggestions.push({ w: e.w, note: "infinitif" });
      seen.add(e.w);
      break;
    }
  }
  if (suggestions.length < limit) {
    for (const e of entries) {
      if (seen.has(e.w)) continue;
      const idx = e.formsNorm.findIndex((f) => f === q);
      if (idx !== -1) {
        suggestions.push({ w: e.w, note: `forme : ${e.forms[idx]}`, form: e.forms[idx] });
        seen.add(e.w);
        if (suggestions.length >= limit) return suggestions;
      }
    }
  }

  // 2) Prefix on infinitive
  for (const e of entries) {
    if (seen.has(e.w)) continue;
    if (e.norm.startsWith(q)) {
      suggestions.push({ w: e.w, note: "infinitif" });
      seen.add(e.w);
      if (suggestions.length >= limit) return suggestions;
    }
  }

  // 3) Contains on infinitive
  for (const e of entries) {
    if (seen.has(e.w)) continue;
    if (e.norm.includes(q)) {
      suggestions.push({ w: e.w, note: "infinitif" });
      seen.add(e.w);
      if (suggestions.length >= limit) return suggestions;
    }
  }

  // 4) Contains on conjugated forms
  for (const e of entries) {
    if (seen.has(e.w)) continue;
    if (!e.formsBlob.includes(q)) continue;
    let example = "";
    for (let i = 0; i < e.formsNorm.length; i++) {
      if (e.formsNorm[i].includes(q)) {
        example = e.forms[i];
        break;
      }
    }
    suggestions.push({ w: e.w, note: example ? `forme : ${example}` : "forme conjuguée", form: example || "" });
    seen.add(e.w);
    if (suggestions.length >= limit) return suggestions;
  }

  return suggestions;
}

async function main() {
  setupAudioClickHandler();

  const status = document.getElementById("status");
  const q = document.getElementById("q");
  const searchBtn = document.getElementById("searchBtn");
  const randomBtn = document.getElementById("randomBtn");
  const themeBtn = document.getElementById("themeBtn");
  const randYellowBtn = document.getElementById("randYellow");
  const randOrangeBtn = document.getElementById("randOrange");
  const randRedBtn = document.getElementById("randRed");
  const toTopBtn = document.getElementById("toTop");
  const rows = document.getElementById("rows");
  const suggestionsEl = document.getElementById("suggestions");
  const searchEl = document.querySelector(".search");
  const searchPlaceholder = document.getElementById("searchPlaceholder");
  const legendEl = document.querySelector(".legend");
  const repoLinkEl = document.getElementById("repoLink");
  const issuesLinkEl = document.getElementById("issuesLink");
  const footerMetaEl = document.getElementById("footerMeta");

  // Theme toggle: auto -> light -> dark (must be ready before data loads)
  const themeModes = ["auto", "light", "dark"];
  function getTheme() {
    return localStorage.getItem("theme") || "auto";
  }
  function applyTheme(mode) {
    if (mode === "auto") {
      document.documentElement.removeAttribute("data-theme");
      themeBtn.textContent = "🌓";
      themeBtn.title = "Thème : Auto";
      themeBtn.setAttribute("aria-label", "Thème : Auto");
    } else {
      document.documentElement.setAttribute("data-theme", mode);
      const label = mode === "light" ? "Clair" : "Sombre";
      themeBtn.textContent = mode === "light" ? "☀️" : "🌙";
      themeBtn.title = `Thème : ${label}`;
      themeBtn.setAttribute("aria-label", `Thème : ${label}`);
    }
    localStorage.setItem("theme", mode);
  }
  applyTheme(getTheme());
  themeBtn.addEventListener("click", () => {
    const current = getTheme();
    const idx = themeModes.indexOf(current);
    const next = themeModes[(idx + 1) % themeModes.length];
    applyTheme(next);
  });

  status.textContent = "Chargement des verbes…";

  let manifest = null;
  let data = null;
  try {
    const res = await fetch("./data/manifest.json", { cache: "no-store" });
    if (res.ok) manifest = await res.json();
    if (!manifest) throw new Error("no manifest");
  } catch (e) {
    status.textContent =
      "Données manquantes. Lancez: make build-pages-full (ou build-pages-limit).";
    return;
  }

  const meta = manifest.meta || {};
  const byWord = new Map();
  const entries = [];
  let loadedCount = 0;
  const INITIAL_TOTAL_ROWS = 8; // total rows to show quickly (including avoir/faire)
  const TARGET_TOTAL_ROWS = 10; // cap target total rows after all chunks
  const MAX_ROWS = 200;
  const byIrr = { "🟡": [], "🟠": [], "🔴": [] };

  function addEntry(v) {
    if (!v || !v.w || byWord.has(v.w)) return;
    const irr = v.irr && v.irr.length ? v.irr : "🟢";
    if (byIrr[irr]) byIrr[irr].push(v.w);
    byWord.set(v.w, v);
    const forms = collectAllForms(v);
    const formsNorm = forms.map((x) => normalizeFrench(x));
    entries.push({
      w: v.w,
      norm: normalizeFrench(v.w),
      forms,
      formsNorm,
      formsBlob: formsNorm.join(" "),
    });
    loadedCount++;
  }

  const totalCount = Number(manifest.count || 0);
  status.textContent = `0 / ${totalCount.toLocaleString("fr-FR")} verbes chargés…`;

  // Repo / issues links + footer meta
  const repoUrl = meta.repo_url || "";
  const issuesUrl = meta.issues_url || "";
  if (repoLinkEl) {
    if (repoUrl) {
      repoLinkEl.href = repoUrl;
      repoLinkEl.hidden = false;
    } else {
      repoLinkEl.hidden = true;
    }
  }
  if (issuesLinkEl) {
    if (issuesUrl) {
      issuesLinkEl.href = issuesUrl;
      issuesLinkEl.hidden = false;
    } else {
      issuesLinkEl.hidden = true;
    }
  }

  if (footerMetaEl) {
    const nowYear = new Date().getFullYear();
    const gen = manifest.generated_at ? new Date(manifest.generated_at) : null;
    const genStr = gen && !Number.isNaN(gen.getTime()) ? gen.toLocaleDateString("fr-FR") : "";
    const dumpStr = meta.wiktionary_extract_date || "";
    const startYear = 2026;
    const yearText = nowYear > startYear ? `${startYear}-${nowYear}` : `${startYear}`;
    const lines = [
      "Quel plaisir de construire ce petit outil pour apprendre le français.",
      `© Carlson Büth ${escapeHtml(yearText)}`,
    ];
    if (genStr) lines.push(`Page générée le ${escapeHtml(genStr)}`);
    if (dumpStr) lines.push(`Extraction Wiktionnaire : ${escapeHtml(dumpStr)}`);
    if (repoUrl) {
      lines.push(
        `<a href="${escapeHtml(repoUrl)}" target="_blank" rel="noopener noreferrer">Code source</a>`
      );
    }
    footerMetaEl.innerHTML = lines.map((t) => `<span class="footer-line">${t}</span>`).join("");
  }

  // Sticky search bar state
  const portrait = window.matchMedia("(max-width: 700px) and (orientation: portrait)");
  const setMobileLabels = () => {
    q.placeholder = portrait.matches ? "Rechercher…" : "Rechercher un verbe (infinitif ou forme conjuguée)…";
  };
  setMobileLabels();
  portrait.addEventListener?.("change", setMobileLabels);

  // Floating search bar: appears only once the legend reaches the top.
  let floatingOffTimer = null;
  let floatingLocked = false;
  let floatingState = false;
  const SHOW_AT = 6; // px
  const HIDE_AT = 40; // px (hysteresis to avoid flicker)
  function topOcclusionPx() {
    if (!searchEl) return 0;
    const rect = searchEl.getBoundingClientRect();
    const isFixed = searchEl.classList.contains("floating") && searchEl.classList.contains("show");
    // When fixed, it visually occludes content; when in-flow near top it still occupies space,
    // but we want focused items to land a bit below it.
    return (isFixed ? rect.height + 18 : rect.height + 12) || 0;
  }
  function scrollElementBelowSearch(el) {
    if (!el) return;
    const y = window.scrollY + el.getBoundingClientRect().top;
    const target = Math.max(0, y - topOcclusionPx());
    window.scrollTo({ top: target, behavior: "smooth" });
  }
  function reservedSearchHeight() {
    if (!searchEl) return 0;
    const rect = searchEl.getBoundingClientRect();
    const cs = window.getComputedStyle(searchEl);
    const mt = parseFloat(cs.marginTop) || 0;
    const mb = parseFloat(cs.marginBottom) || 0;
    return Math.ceil(rect.height + mt + mb);
  }
  function setFloating(on) {
    if (!searchEl || !searchPlaceholder) return;
    if (on === floatingState) return;
    floatingState = on;
    if (on) {
      if (floatingOffTimer) {
        window.clearTimeout(floatingOffTimer);
        floatingOffTimer = null;
      }
      if (!searchEl.classList.contains("floating")) {
        searchPlaceholder.style.height = `${reservedSearchHeight()}px`;
        searchEl.classList.add("floating");
        window.requestAnimationFrame(() => searchEl.classList.add("show"));
      } else {
        searchPlaceholder.style.height = `${reservedSearchHeight()}px`;
        searchEl.classList.add("show");
      }
    } else {
      if (!searchEl.classList.contains("floating")) return;
      searchEl.classList.remove("show");
      floatingOffTimer = window.setTimeout(() => {
        searchEl.classList.remove("floating");
        searchPlaceholder.style.height = "0px";
      }, 240);
    }

    if (portrait.matches) {
      if (on) {
        searchBtn.textContent = "🔎";
      } else {
        searchBtn.textContent = "Rechercher";
        randomBtn.style.display = "";
      }
    } else {
      searchBtn.textContent = "Rechercher";
      randomBtn.style.display = "";
    }
  }

  function updateFloating() {
    if (!legendEl) return;
    if (floatingLocked) {
      if (window.scrollY <= 4) floatingLocked = false;
      setFloating(false);
      return;
    }
    const top = legendEl.getBoundingClientRect().top;
    if (!floatingState) setFloating(top <= SHOW_AT);
    else setFloating(!(top > HIDE_AT));
  }
  window.addEventListener("scroll", updateFloating, { passive: true });
  window.addEventListener("resize", updateFloating);
  updateFloating();

  function addRowToTop(word, { focusRow, focusForm } = { focusRow: true, focusForm: "" }) {
    const v = byWord.get(word);
    if (!v) return;
    document.querySelectorAll(`tr[data-word="${CSS.escape(word)}"]`).forEach((el) => el.remove());
    rows.insertAdjacentHTML("afterbegin", buildRow(v));
    enforceMaxRows();
    adjustMobileParticiplesLayout();
    adjustMobileTenseGridLayout();
    adjustDesktopTenseIpaLayout();
    if (focusRow) {
      const row = rows.querySelector(`tr[data-word="${CSS.escape(word)}"]`);
      if (row) {
        row.scrollIntoView({ block: "start", behavior: "smooth" });
        row.focus({ preventScroll: true });
      }
    }
    if (focusForm && portrait.matches) {
      const row = rows.querySelector(`tr[data-word="${CSS.escape(word)}"]`);
      const el = row?.querySelector(`.tense-item[data-form="${CSS.escape(focusForm)}"]`);
      if (el) {
        el.classList.add("picked");
        // Ensure the focused form lands just below the search bar (floating or in-flow).
        scrollElementBelowSearch(el);
        el.focus({ preventScroll: true });
        window.setTimeout(() => el.classList.remove("picked"), 900);
      }
    }
  }

  function addRowToBottom(word) {
    const v = byWord.get(word);
    if (!v) return;
    document.querySelectorAll(`tr[data-word="${CSS.escape(word)}"]`).forEach((el) => el.remove());
    rows.insertAdjacentHTML("beforeend", buildRow(v));
    enforceMaxRows();
    adjustMobileParticiplesLayout();
    adjustMobileTenseGridLayout();
    adjustDesktopTenseIpaLayout();
  }

  function shownWords() {
    return new Set(Array.from(document.querySelectorAll("tr[data-word]")).map((tr) => tr.dataset.word));
  }

  function enforceMaxRows() {
    while (rows.children.length > MAX_ROWS) {
      rows.lastElementChild?.remove();
    }
  }

  function maybeAddRandomRow(sourceWords = null) {
    const shown = shownWords();
    const pool = sourceWords && sourceWords.length ? sourceWords : entries.map((e) => e.w);
    if (!pool.length) return;
    for (let i = 0; i < 30; i++) {
      const w = pool[cryptoRandomInt(pool.length)];
      if (!w || shown.has(w) || !byWord.has(w)) continue;
      addRowToBottom(w);
      return;
    }
  }

  let didInitialSeed = false;
  function seedInitialRows() {
    if (didInitialSeed) return;
    didInitialSeed = true;
    const shown = shownWords();
    for (const w of ["avoir", "faire"]) {
      if (byWord.has(w) && !shown.has(w)) addRowToBottom(w);
    }
    // Add a few random verbs to start with (once).
    while (shownWords().size < INITIAL_TOTAL_ROWS && entries.length) {
      maybeAddRandomRow();
    }
  }

  function pickRandomFromBucket(marker) {
    const bucket = byIrr[marker] || [];
    if (!bucket.length) return;
    const w = bucket[cryptoRandomInt(bucket.length)];
    if (w) pick(w);
  }
  randYellowBtn?.addEventListener("click", () => pickRandomFromBucket("🟡"));
  randOrangeBtn?.addEventListener("click", () => pickRandomFromBucket("🟠"));
  randRedBtn?.addEventListener("click", () => pickRandomFromBucket("🔴"));

  function idleTick() {
    return new Promise((resolve) => {
      if (typeof requestIdleCallback !== "undefined") requestIdleCallback(() => resolve(), { timeout: 120 });
      else setTimeout(resolve, 0);
    });
  }

  async function loadChunk(relPath) {
    if (typeof DecompressionStream === "undefined") throw new Error("DecompressionStream required");
    const res = await fetch(`./data/${relPath}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const stream = res.body.pipeThrough(new DecompressionStream("gzip"));
    const text = await new Response(stream).text();
    return JSON.parse(text);
  }

  const chunks = manifest.chunks || [];
  const plannedAdds = Math.max(0, Math.min(TARGET_TOTAL_ROWS, 50) - INITIAL_TOTAL_ROWS);
  const addSchedule = new Set();
  if (plannedAdds > 0 && chunks.length) {
    for (let i = 1; i <= plannedAdds; i++) {
      addSchedule.add(Math.floor((i * chunks.length) / (plannedAdds + 1)));
    }
  }

  async function loadAllChunks() {
    for (let chunkIndex = 0; chunkIndex < chunks.length; chunkIndex++) {
      const chunk = chunks[chunkIndex];
      try {
        const chunkData = await loadChunk(chunk);
        const verbs = chunkData.verbs || [];
        for (const v of verbs) addEntry(v);
        status.textContent = `${loadedCount.toLocaleString("fr-FR")} / ${totalCount.toLocaleString(
          "fr-FR"
        )} verbes chargés…`;
        seedInitialRows();
        if (didInitialSeed && addSchedule.has(chunkIndex) && shownWords().size < TARGET_TOTAL_ROWS) {
          maybeAddRandomRow(verbs.map((v) => v.w));
        }
        adjustMobileParticiplesLayout();
        adjustMobileTenseGridLayout();
        adjustDesktopTenseIpaLayout();
      } catch (e) {
        console.warn("Chunk load failed:", chunk, e);
      }
      await idleTick();
    }
    status.textContent = `${loadedCount.toLocaleString("fr-FR")} verbes chargés.`;
  }

  // Low-priority progressive load to keep UI responsive (theme toggle etc.).
  loadAllChunks();

  let selectedIndex = -1;
  let currentSuggestions = [];

  function renderSuggestions() {
    if (!currentSuggestions.length) {
      suggestionsEl.classList.remove("visible");
      suggestionsEl.innerHTML = "";
      return;
    }
    suggestionsEl.classList.add("visible");
    suggestionsEl.innerHTML = currentSuggestions
      .map((s, idx) => {
        const selected = idx === selectedIndex;
        const v = byWord.get(s.w);
        const irr = v && v.irr && v.irr.length ? v.irr : "🟢";
        return `<div class="suggestion" role="option" aria-selected="${selected}" data-word="${escapeHtml(
          s.w
        )}" data-idx="${idx}"><span>${escapeHtml(s.w)}</span><small>${escapeHtml(
          `${irr} ${s.note || ""}`.trim()
        )}</small></div>`;
      })
      .join("");

    const selectedEl = suggestionsEl.querySelector('[aria-selected="true"]');
    selectedEl?.scrollIntoView({ block: "nearest" });
  }

  function pick(word, { focusForm } = { focusForm: "" }) {
    const v = byWord.get(word);
    if (!v) return;
    const isFloating = !!searchEl?.classList.contains("floating");
    const isShowing = !!searchEl?.classList.contains("show");
    // At top (non-floating UI), do not auto-scroll/focus.
    addRowToTop(word, { focusRow: isFloating && isShowing, focusForm });
    q.value = "";
    currentSuggestions = [];
    selectedIndex = -1;
    renderSuggestions();
  }

  function updateSuggestions() {
    currentSuggestions = computeSuggestions(entries, q.value, 100);
    selectedIndex = currentSuggestions.length ? 0 : -1;
    renderSuggestions();
  }

  q.addEventListener("input", () => {
    updateSuggestions();
  });

  q.addEventListener("keydown", (e) => {
    if (!currentSuggestions.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, currentSuggestions.length - 1);
      renderSuggestions();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      renderSuggestions();
    } else if (e.key === "Enter") {
      e.preventDefault();
      const s = currentSuggestions[selectedIndex];
      pick(s.w, { focusForm: s.form || "" });
    } else if (e.key === "Escape") {
      currentSuggestions = [];
      selectedIndex = -1;
      renderSuggestions();
    }
  });

  searchBtn.addEventListener("click", () => {
    if (!q.value.trim()) return;
    updateSuggestions();
    if (currentSuggestions.length) pick(currentSuggestions[0].w, { focusForm: currentSuggestions[0].form || "" });
  });

  randomBtn.addEventListener("click", () => {
    const idx = cryptoRandomInt(entries.length);
    pick(entries[idx].w);
  });

  // Back-to-top button
  function updateToTop() {
    const show = window.scrollY > window.innerHeight * 2;
    toTopBtn.classList.toggle("visible", show);
  }
  window.addEventListener("scroll", updateToTop, { passive: true });
  updateToTop();
  toTopBtn.addEventListener("click", () => {
    floatingLocked = true;
    setFloating(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  suggestionsEl.addEventListener("click", (e) => {
    const el = e.target.closest("[data-idx]");
    if (!el) return;
    const idx = Number.parseInt(el.dataset.idx || "", 10);
    const s = Number.isFinite(idx) ? currentSuggestions[idx] : null;
    if (!s) return;
    pick(s.w, { focusForm: s.form || "" });
  });

  document.addEventListener("click", (e) => {
    if (e.target === q || suggestionsEl.contains(e.target)) return;
    currentSuggestions = [];
    selectedIndex = -1;
    renderSuggestions();
  });
}

main();
