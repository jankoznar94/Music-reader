// src/barLines.js — TAKTOVÉ ČÁRY v systému (pro „Dočíslovat systém")
//
// PROČ TAKHLE (naměřeno na reálném skenu Mozart/Carus, listopad 2026):
//  - Původní verze hledala linky osnov jako řádky s > 45 % inkoustu a používala
//    Otsuův práh celého pásu. Na skutečném skenu jsou linky šedé a rozpadají se:
//    práh 168 dá podíl 0,46–0,64, takže se našlo 7 řádků místo 10 a ze dvou osnov
//    jedna → `need = max(2, …)` už nikdy nic nepustilo. Odtud „Taktové čáry jsem
//    nenašel“ na každé klepnutí.
//  - Pás 240 b často obsahuje DVĚ systémy; míchání jejich čar dá nesmyslný počet.
//  - Rozdělit systémy podle mezery mezi osnovami nejde (uvnitř 38–45 b, mezi
//    systémy 42 b) — jediné spolehlivé kritérium je SHODA TAKTOVÝCH ČAR.
//  - Počet čar se NESMÍ hádat: uživatel zadává „Krok“ = počet taktů systému.
//
// CO BYLO ŠPATNĚ (Jan, listopad 2026) a jak je to teď:
//  1) „Počítá i první taktovou čáru na začátku systému, takže odhaduje o jednoho
//     kandidáta víc.“ → Dřív se úvodní čára vyhazovala jen hackem `x < 55 b`
//     (vzdálenost od okraje STRÁNKY). U sazby s větším levým okrajem je úvodní
//     čára dál než 55 b a počítala se. Teď se měří okraj SYSTÉMU: nejmenší x,
//     kde začíná linka osnov (`staffLeft`), a vše, co leží na něm nebo kousek
//     za ním, je úvodní čára (i s tlustou svorkou) — vrací se jen VNITŘNÍ čáry.
//  2) „První takt v systému už číslo má, takže ani ten by se neměl počítat.“
//     → Čísla se proto vkládají až od DRUHÉHO taktu: systém o `krok` taktech má
//     `krok − 1` vnitřních čar a tolik čísel (první takt si nechá vytištěné číslo).
//  3) „Jako čáry bere i nožičky not.“ → Sloupec se počítal jako čára, když měl
//     ≥ 92 % inkoustu ve VÝŠCE OSNOVY. Nožička akordu tuhle podmínku splní (je
//     stejně vysoká jako osnova) a u sboru se nožičky hlasů navíc kryjí ve
//     svislici, takže projdou i hlasováním. Naměřeno na skenu (mezera 3,42 b):
//       taktová čára  tah 14,7–15,0 b, přesah NAD i POD osnovou 0,3–0,7 b
//       nožička       tah 12,0–13,7 b, přesah aspoň na jedné straně ZÁPORNÝ
//     Čára teď musí: (a) být plná v KAŽDÉ osnově systému, (b) přesáhnout oba
//     konce osnovy, (c) nemít na konci tahu široký vodorovný útvar (hlavičku
//     noty nebo trámec) — to je geometrie, ne práh na štěstí.
//     Minimální výška tahu = výška celého systému (všechny osnovy + mezery).

/** Otsuův práh z histogramu šedi. */
function otsu(hist, total) {
  let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let sumB = 0, wB = 0, best = -1, thr = 127;
  for (let t = 0; t < 256; t++) {
    wB += hist[t];
    if (!wB) continue;
    const wF = total - wB;
    if (!wF) break;
    sumB += t * hist[t];
    const mB = sumB / wB, mF = (sum - sumB) / wF;
    const v = wB * wF * (mB - mF) * (mB - mF);
    if (v > best) { best = v; thr = t; }
  }
  return thr;
}

/** Délka nejdelšího souvislého tahu v řádku masky. */
function longestRun(mask, off, w) {
  let best = 0, run = 0;
  for (let x = 0; x < w; x++) {
    if (mask[off + x]) { run++; if (run > best) best = run; }
    else run = 0;
  }
  return best;
}

/** Šířka vodorovného tahu v řádku `y`, který obsahuje sloupec `x` (v px). */
function hRunAt(mask, w, x, y) {
  if (!mask[y * w + x]) return 0;
  let a = x, b = x;
  while (a > 0 && mask[y * w + a - 1]) a--;
  while (b < w - 1 && mask[y * w + b + 1]) b++;
  return b - a + 1;
}

/**
 * Najde VNITŘNÍ taktové čáry systému (čáry, které začínají 2. a další takt).
 *
 * @param {HTMLCanvasElement} cv pás přes celou šířku (240–260 bodů vysoký)
 * @param {number} pxPerPt pixely canvasu na PDF bod
 * @param {{krok:number, ypt:number, offsetY?:number}} opt `krok` = počet taktů
 *        systému (zadává uživatel), `ypt` = y klepnutí v bodech PDF (rozhoduje,
 *        který systém se bere)
 * @returns {{lines:number[], bars:number, krok:number, staves:number, top:number,
 *            ok:boolean, reason?:string, opening?:number|null, mode?:string}}
 *          `lines` = x-ové souřadnice začátků taktů 2..krok v BODECH PDF (první
 *          takt se nečísluje, má vytištěné číslo), `top` = horní linka systému
 *          v bodech PDF (číslo taktu patří nad ni)
 */
export function detectBarlines(cv, pxPerPt, opt = {}) {
  const w = cv.width, h = cv.height;
  const krok = Math.max(1, Math.min(64, Math.round(opt.krok || 1)));
  const ypt = Number.isFinite(opt.ypt) ? opt.ypt : null;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const hist = new Uint32Array(256);
  const gray = new Uint8Array(w * h);
  for (let i = 0, p = 0; p < w * h; p++, i += 4) {
    const v = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
    gray[p] = v;
    hist[v | 0]++;
  }
  // Práh pro LINKY OSNOV výš než Otsu celého pásu — linky jsou na skenu šedé
  // a při nízkém prahu se rozpadají (naměřeno 0,46–0,64 místo > 0,85).
  const thr = Math.min(235, otsu(hist, w * h) + 35);
  const mask = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) mask[p] = gray[p] < thr ? 1 : 0;

  // 1) linky osnov = řádky s dlouhým vodorovným tahem
  const centres = [];
  let runStart = -1;
  for (let y = 0; y <= h; y++) {
    let on = false;
    if (y < h) {
      const off = y * w;
      let ink = 0;
      for (let x = 0; x < w; x++) ink += mask[off + x];
      const frac = ink / w;
      on = frac >= 0.30 || longestRun(mask, off, w) / w >= 0.45;
    }
    if (on && runStart < 0) runStart = y;
    if (!on && runStart >= 0) {
      centres.push(Math.round((runStart + y - 1) / 2));
      runStart = -1;
    }
  }
  // slít tlusté linky
  const minSep = Math.max(2, Math.round(pxPerPt * 0.8));
  const cs = [];
  for (const c of centres) {
    if (cs.length && c - cs[cs.length - 1] <= minSep) cs[cs.length - 1] = Math.round((cs[cs.length - 1] + c) / 2);
    else cs.push(c);
  }
  const gapMax = Math.max(12, Math.round(pxPerPt * 8));
  const staves = [];
  let cur = [];
  for (const c of cs) {
    if (cur.length && c - cur[cur.length - 1] < gapMax) cur.push(c);
    else { if (cur.length) staves.push(cur); cur = [c]; }
  }
  if (cur.length) staves.push(cur);
  const real = staves.filter(s => s.length >= 4);
  if (!real.length) {
    return { lines: [], bars: 0, krok, staves: 0, top: 0, ok: false,
             reason: 'nenašel jsem linky osnov (' + cs.length + ' linek)' };
  }

  // 2) Hrubé svislice v každé osnově — sloupec plný po celé výšce osnovy.
  //    Slouží JEN k seskupení osnov do systému (shoda čar mezi osnovami),
  //    ne k rozhodnutí „tohle je taktová čára“.
  const maxW = Math.max(2, Math.round(pxPerPt * 2.6));
  const per = real.map((s) => {
    const yTop = s[0], yBot = s[s.length - 1];
    const bh = Math.max(1, yBot - yTop);
    const cols = [];
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = yTop; y <= yBot; y++) ink += mask[y * w + x];
      if (ink / bh >= 0.90) cols.push(x);
    }
    const xs = [];
    let i = 0;
    while (i < cols.length) {
      let j = i;
      while (j + 1 < cols.length && cols[j + 1] - cols[j] <= 2) j++;
      if (cols[j] - cols[i] + 1 <= maxW) xs.push((cols[i] + cols[j]) / 2 / pxPerPt);
      i = j + 1;
    }
    return { y0: s[0] / pxPerPt, y1: s[s.length - 1] / pxPerPt, py0: s[0], py1: s[s.length - 1], cols: xs, src: s };
  });

  // 3) systém = osnovy u klepnutí, které jsou souvislé a mají shodné čáry
  const dist = (o) => (o.y0 <= ypt && ypt <= o.y1)
    ? 0 : Math.min(Math.abs(ypt - o.y0), Math.abs(ypt - o.y1));
  let start = 0;
  if (ypt != null) {
    let bd = Infinity;
    per.forEach((o, i) => { const dd = dist(o); if (dd < bd) { bd = dd; start = i; } });
  }
  const same = (a, b) => {
    let hit = 0;
    for (const x of a) if (b.some(y => Math.abs(x - y) <= 1.5)) hit++;
    return hit >= 2;
  };
  const group = [start];
  // MEZERA UVNITŘ SYSTÉMU vs MEZI SYSTÉMY (naměřeno na skutečné sazbě):
  // uvnitř systému 20–29 b, mezi systémy 52 b. Pevných 55 b (dřív) proto
  // slilo dva systémy do jednoho a detekce pak nenašla ani jednu čáru — čáry
  // dvou systémů totiž nemají nic společného. Mez se bere z mediánu mezer
  // na stránce, ne z konstanty: uvnitř je jich většina, takže medián = mezera
  // uvnitř systému a 1,75× mediánu už mezi systémy neprojde.
  const gapsPt = [];
  for (let i = 1; i < per.length; i++) gapsPt.push(per[i].y0 - per[i - 1].y1);
  gapsPt.sort((a, b) => a - b);
  const medGap = gapsPt.length ? gapsPt[Math.floor(gapsPt.length / 2)] : 30;
  const GAP_PT = Math.max(26, Math.min(55, 1.75 * medGap));
  for (let i = start + 1; i < per.length; i++) {
    const prev = per[group[group.length - 1]];
    if (per[i].y0 - prev.y1 > GAP_PT || !same(per[i].cols, per[start].cols)) break;
    group.push(i);
  }
  for (let i = start - 1; i >= 0; i--) {
    const prev = per[group[0]];
    if (prev.y0 - per[i].y1 > GAP_PT || !same(per[i].cols, per[start].cols)) break;
    group.unshift(i);
  }

  // 4) GEOMETRIE: co je taktová čára a co nožička
  const st = group.map(i => ({ y0: per[i].py0, y1: per[i].py1 }));
  const heights = st.map(s => Math.max(1, s.y1 - s.y0));
  const spacePx = Math.max(2, Math.round(heights[0] / 4));   // mezera osnovy v px
  const gTop = Math.min(...st.map(s => s.y0));
  const gBot = Math.max(...st.map(s => s.y1));
  // Každá osnova má vlastní okno o mezeru širší — na skenu je taktová čára
  // kreslená ZVLÁŠŤ pro každou osnovu, takže mezi osnovami je mezera a hledat
  // jeden souvislý tah přes celý systém nemá smysl.
  const segs = st.map((s, i) => {
    const sp = Math.max(2, Math.round(heights[i] / 4));
    return { y0: s.y0, y1: s.y1, h: heights[i], sp,
             w0: Math.max(0, Math.floor(s.y0 - 1.5 * sp)),
             w1: Math.min(h - 1, Math.ceil(s.y1 + 1.5 * sp)) };
  });
  // řádky linek osnov — v nich se šířka tahu NESMÍ měřit (linka jde přes stránku)
  const isStaffRow = new Uint8Array(h);
  for (const c of cs) {
    for (let y = Math.max(0, c - 2); y <= Math.min(h - 1, c + 2); y++) isStaffRow[y] = 1;
  }

  // Levý okraj systému = první inkoust na horní (a dolní) lince kterékoliv osnovy.
  // Úvodní taktová čára stojí právě tady — a ta se nepočítá (takt 1 má číslo).
  let staffLeft = w;
  for (const s of st) {
    for (const yy of [Math.round(s.y0), Math.round(s.y1)]) {
      for (let x = 0; x < w; x++) {
        if (mask[yy * w + x]) { if (x < staffLeft) staffLeft = x; break; }
      }
    }
  }
  if (staffLeft >= w) staffLeft = 0;
  const openSkip = staffLeft + 0.6 * spacePx;      // px

  const blobWpx = 0.85 * spacePx;                  // hlava noty / trámec
  const cols = [];
  for (let x = 0; x < w; x++) {
    let full = true, blob = false, runMax = 0;
    let overTop = -999, overBot = -999;
    for (let i = 0; i < segs.length; i++) {
      const sg = segs[i];
      let runS = -1, best = 0, bestS = 0, ink = 0;
      for (let y = sg.w0; y <= sg.w1; y++) {
        if (mask[y * w + x]) {
          if (runS < 0) runS = y;
          const len = y - runS + 1;
          if (len > best) { best = len; bestS = runS; }
          if (y >= sg.y0 && y <= sg.y1) ink++;
        } else runS = -1;
      }
      // (a) sloupec musí být plný v KAŽDÉ osnově systému — nožička je jen v jedné
      if (ink / sg.h < 0.85) { full = false; break; }
      if (i === 0) overTop = (sg.y0 - bestS) / pxPerPt;
      if (i === segs.length - 1) overBot = (bestS + best - sg.y1) / pxPerPt;
      if (best > runMax) runMax = best;
      // (c) široký vodorovný útvar na konci tahu = hlava noty / trámec → nožička
      const step = Math.max(1, Math.round(sg.sp / 4));
      for (let k = 0; k <= step * 3 && !blob; k++) {
        const ys = [bestS + k, bestS + best - 1 - k];
        for (const y of ys) {
          if (y < 0 || y >= h || isStaffRow[y]) continue;
          if (hRunAt(mask, w, x, y) >= blobWpx) { blob = true; break; }
        }
      }
      if (blob) break;
    }
    if (!full) continue;
    // (b) přesah nad PRVNÍ a pod POSLEDNÍ osnovou systému (u nožičky chybí)
    cols.push({ x, overTop, overBot, run: runMax / pxPerPt, blob });
  }
  // slít sousední sloupce jedné čáry (tlustá čára = 2–4 px)
  const merged = [];
  for (const c of cols) {
    const last = merged[merged.length - 1];
    if (last && c.x - last.x <= Math.max(2, Math.round(pxPerPt * 1.0))) {
      if (c.run > last.run) merged[merged.length - 1] = c;
      continue;
    }
    merged.push(c);
  }
  // úvodní čára (na okraji systému) — vyhodit, takt 1 má vytištěné číslo
  let opening = null;
  const rest = [];
  for (const c of merged) {
    if (opening == null && c.x <= openSkip) { opening = c.x / pxPerPt; continue; }
    rest.push(c);
  }
  const want = krok - 1;                     // vnitřní čáry = takty 2..krok
  const toPt = (c) => c.x / pxPerPt;
  const candsOf = (arr) => arr.map(c => [+toPt(c).toFixed(1), c.run, c.overTop.toFixed(2), c.overBot.toFixed(2), c.blob ? 1 : 0]);
  // Přísně: přesah na OBOU koncích. Když to nestačí (některá vydání mají čáry
  // zarovnané přesně s osnovou), zkusí se totéž bez požadavku na přesah —
  // hlava noty na konci tahu pořád platí jako důkaz nožičky.
  const dbg = { group: st.map(s => [+(s.y0 / pxPerPt).toFixed(1), +(s.y1 / pxPerPt).toFixed(1)]),
                staffLeft: +(staffLeft / pxPerPt).toFixed(1), space: +(spacePx / pxPerPt).toFixed(2),
                all: real.map(g => [+(g[0] / pxPerPt).toFixed(1), +(g[g.length - 1] / pxPerPt).toFixed(1), g.length]) };
  const strict = rest.filter(c => !c.blob && c.overTop > 0 && c.overBot > 0);
  const loose = rest.filter(c => !c.blob);
  const mode = strict.length >= want ? 'přesah' : (loose.length >= want ? 'bez přesahu' : 'málo');
  // Špatné číslo je horší než žádné (Jan) — radši chyba s počtem než posun.
  const pick = (mode === 'přesah' ? strict : loose).slice(0, Math.max(0, want));
  const lines = pick.map(toPt);
  const top = (Number.isFinite(opt.offsetY) ? opt.offsetY : 0) + per[group[0]].y0;

  const diag = { thr, staves: group.length, cols: cols.length, merged: merged.length,
                 opening: opening == null ? null : +opening.toFixed(1), mode,
                 overshoot: rest.filter(c => c.overTop > 0 && c.overBot > 0).length };
  if (want < 1) {
    return { lines: [], bars: 0, krok, staves: group.length, top, ok: false, opening,
             reason: 'systém o jednom taktu — první takt už číslo má, není co dočíslovat',
             diag, dbg, cands: candsOf(merged) };
  }
  if (lines.length < want) {
    return { lines, bars: lines.length, krok, staves: group.length, top, ok: false, opening,
             reason: 'našel jsem jen ' + lines.length + ' z ' + want + ' vnitřních čar',
             diag, dbg, cands: candsOf(merged) };
  }
  return { lines, bars: lines.length, krok, staves: group.length, top, ok: true, thr,
           opening, diag, mode, dbg, cands: candsOf(merged) };
}
