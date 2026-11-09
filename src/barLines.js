// src/barLines.js — TAKTOVÉ ČÁRY v systému (pro „Dočíslovat systém“)
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
//    Vybírá se proto právě `krok` kandidátů s nejvíc hlasy (kolik osnov je vidí)
//    zleva; skutečnou čáru vidí všechny osnovy, nožičku noty jedna nebo dvě.
//    Čísla se vkládají na začátky taktů zleva, koncová čára systému se nepoužívá.

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

/**
 * Najde taktové čáry v pásu stránky.
 * @param {HTMLCanvasElement} cv pás přes celou šířku (240–260 bodů vysoký)
 * @param {number} pxPerPt pixely canvasu na PDF bod
 * @param {{krok:number, ypt:number}} opt `krok` = počet taktů systému (uživatel),
 *        `ypt` = y klepnutí v bodech PDF (rozhoduje, který systém se bere)
 * @returns {{lines:number[], bars:number, staves:number, top:number,
 *            ok:boolean, reason?:string}}
 *          `lines` = x-ové souřadnice začátků taktů v BODECH PDF, `top` = horní
 *          linka systému v bodech PDF (číslo taktu patří nad ni)
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
    return { lines: [], bars: 0, staves: 0, top: 0, ok: false,
             reason: 'nenašel jsem linky osnov (' + cs.length + ' linek)' };
  }

  // 2) taktoví kandidáti v každé osnově (sloupec vyplněný po celé výšce osnovy)
  const maxW = Math.max(2, Math.round(pxPerPt * 1.3));
  const per = real.map((s) => {
    const yTop = s[0], yBot = s[s.length - 1];
    const bh = Math.max(1, yBot - yTop);
    const cols = [];
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = yTop; y <= yBot; y++) ink += mask[y * w + x];
      if (ink / bh >= 0.92) cols.push(x);
    }
    const xs = [];
    let i = 0;
    while (i < cols.length) {
      let j = i;
      while (j + 1 < cols.length && cols[j + 1] - cols[j] <= 2) j++;
      if (cols[j] - cols[i] + 1 <= maxW) xs.push((cols[i] + cols[j]) / 2 / pxPerPt);
      i = j + 1;
    }
    return { y0: s[0] / pxPerPt, y1: s[s.length - 1] / pxPerPt, cols: xs };
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
  const GAP_PT = 55;
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

  // 4) hlasy kandidátů = kolik osnov systému danou svislici vidí
  const all = [];
  for (const i of group) for (const x of per[i].cols) all.push(x);
  all.sort((a, b) => a - b);
  const groups = [];
  for (const x of all) {
    const g = groups[groups.length - 1];
    if (g && x - g[g.length - 1] <= 1.5) g.push(x); else groups.push([x]);
  }
  const need = Math.max(1, Math.ceil(0.5 * group.length));
  const cand = [];
  for (const g of groups) {
    const x = g.reduce((s, v) => s + v, 0) / g.length;
    if (x < 55) continue;                             // svorka / okraj stránky
    let votes = 0;
    for (const i of group) if (per[i].cols.some(y => Math.abs(x - y) <= 2)) votes++;
    if (votes >= need) cand.push({ x, votes });
  }
  cand.sort((a, b) => a.x - b.x);
  // slít dvě čáry blíž než 6 b (začátek osnovy + první taktová čára)
  const merged = [];
  for (const c of cand) {
    const last = merged[merged.length - 1];
    if (last && c.x - last.x < 6) { if (c.votes > last.votes) merged[merged.length - 1] = c; continue; }
    merged.push(c);
  }
  // Výběr čar: bereme PRVNÍ `krok` skutečných čar ZLEVA.
  //
  // PROČ ne skóre (dřív): skóre = hlasy − odchylka rozestupů zvýhodňovalo
  // rovnoměrné rozestupy, takže u systému, kde je první takt širší, zahodilo
  // DRUHOU čáru a jako čtvrtou vzalo KONCOVOU. Čísla pak seděla na špatných
  // místech (naměřeno: 65/259/361/464/566 → vybráno 65/361/464/566). Čísla
  // taktu jdou vždy zleva doprava, takže stačí vzít prvních `krok` čar.
  //
  // `need` = kolik osnov čáru musí vidět: polovina zaokrouhlená nahoru, ale
  // aspoň 2 — u jednoosnového pásu by jinak prošlo každé smetí.
  const needV = Math.max(2, Math.ceil(0.6 * group.length));
  const cands = merged.filter(c => c.votes >= needV).sort((a, b) => a.x - b.x);
  const lines = cands.slice(0, krok).map(c => c.x);
  const top = (Number.isFinite(opt.offsetY) ? opt.offsetY : 0) + per[group[0]].y0;
  const dump = cands.map(c => [Math.round(c.x * 10) / 10, c.votes]);
  if (lines.length < krok) {
    return { lines, bars: lines.length, staves: group.length, top, ok: false,
             reason: 'našel jsem jen ' + lines.length + ' z ' + krok + ' čar',
             diag: { thr, osnovy: group.length, kandidátů: merged.length },
             cands: dump, need };
  }
  return { lines, bars: lines.length, staves: group.length, top, ok: true, thr,
           cands: dump, need };
}
