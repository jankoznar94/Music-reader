// src/barLines.js — TAKTOVÉ ČÁRY v systému (pro „Dočíslovat systém")
//
// HISTORIE CHYB (ať se nevrací):
//  1) Práh na linky osnov z celého pásu → na šedém skenu se linky rozpadaly.
//     Teď: Otsu + 35, práh max 235.
//  2) Úvodní taktová čára se vyhazovala hackem `x < 55 b` (od okraje STRÁNKY),
//     takže u sazby s větším levým okrajem prošla a čísla se posunula o 1.
//     Teď se měří okraj SYSTÉMU (první inkoust na lince osnov).
//  3) „Čára“ = sloupec plný ve výšce osnovy → bralo i nožičky not (akord je
//     stejně vysoký jako osnova a u sboru se nožičky hlasů kryjí).
//  4) Podmínka „čára přesahuje osnovu nad i pod“ — na skenu Carus je přesah
//     0,0 b, takže neprošla ANI JEDNA čára (`overshoot: 0` v diagnostice).
//  5) Seskupování osnov do systému se slévalo přes dva systémy (`staves: 9`
//     místo 6) a pak se hledaly čáry, které neexistují.
//
// SOUČASNÝ PŘÍSTUP (listopad 2026) — nic z toho nepotřebuje:
//  * Bere se JEDINÁ osnova, do které uživatel klepl. Seskupování do systému
//    odpadá, takže se nemůže splést počet osnov.
//  * Kandidáti = svislé tahy v té osnově (taktové čáry, nožičky, občas klíč).
//  * Rozhoduje PRAVIDELNOST: takty jdou za sebou v pravidelném kroku, kdežto
//    nožičky stojí uvnitř taktů na náhodných místech. Hledá se proto nejdelší
//    řetěz kandidátů se stejnou vzdáleností (kotva + k × P) na obě strany.
//    Nožička do řetězu nesedne, protože rozestupy by přestaly vycházet.
//  * Úvodní ani koncová čára takt nezačínají (stojí na okrajích osnovy) —
//    obojí se vyhodí. Čísla jdou na takty 2..N, protože 1. takt systému má
//    číslo vytištěné (Jan, listopad 2026).
//  * „Krok“ je jen KONTROLA, ne vstup pro výpočet: appka takty spočítá sama
//    a když se to s Krokem rozchází, řekne to. (Jan: „já nevěděl, že má vliv,
//    co zadám do Další a Krok“ — nemá.)

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
 * Nejdelsi řetěz bodů s pravidelným krokem — takhle se oddělí taktové čáry od
 * nožiček: nožičky stojí uvnitř taktů, takže rozestupy rozhodí, kdežto skutečné
 * čáry drží krok. Krok P se hledá HLASOVÁNÍM přes všechny dvojice kandidátů
 * (ne z mezer mezi sousedy — jedna nožička mezi dvěma čarami mezeru rozpůlí),
 * pak se od každé kotvy zkouší řetěz na obě strany.
 */
function barChain(xs, spacePx) {
  const n = xs.length;
  if (n < 2) return xs.slice();
  const diffs = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) diffs.push(xs[j] - xs[i]);
  // Tolerance MUSÍ být těsná: volnější (1,2 mezery) brala jako čárty i nožičky
  // trámcované skupiny (naměřeno: 245,2 místo 249,9) a klíč (69,5).
  const tolOf = (P) => Math.max(1.5, Math.min(0.05 * P, 0.6 * spacePx));
  const minP = 6 * spacePx;                 // takt je širší než 6 mezer
  let bestP = 0, bestScore = 0;
  for (const P of diffs) {
    if (P < minP) continue;
    let sc = 0;
    for (const d of diffs) {
      if (d < P * 0.94) continue;
      const k = Math.round(d / P);
      if (k >= 1 && Math.abs(d - k * P) <= tolOf(P)) sc += 1 / k;
    }
    if (sc > bestScore) { bestScore = sc; bestP = P; }
  }
  if (!bestP) return [];
  const tol = tolOf(bestP);
  let best = [];
  for (const a of xs) {
    const pts = [a];
    for (let i = 1; i <= 64; i++) {
      const want = a + i * bestP;
      const hit = xs.find(v => Math.abs(v - want) <= tol);
      if (hit == null) break;
      pts.push(hit);
    }
    for (let i = 1; i <= 64; i++) {
      const want = a - i * bestP;
      const hit = xs.find(v => Math.abs(v - want) <= tol);
      if (hit == null) break;
      pts.unshift(hit);
    }
    if (pts.length > best.length) best = pts;
  }
  return best;
}

/**
 * Najde VNITŘNÍ taktové čáry systému (čáry, které začínají 2. a další takt).
 *
 * @param {HTMLCanvasElement} cv pás přes celou šířku (240–420 bodů vysoký)
 * @param {number} pxPerPt pixely canvasu na PDF bod
 * @param {{krok?:number, ypt?:number, offsetY?:number}} opt `krok` = počet taktů
 *        systému (jen kontrola, ne vstup výpočtu), `ypt` = y klepnutí v bodech PDF
 * @returns {{lines:number[], bars:number, krok:number, top:number, ok:boolean,
 *            reason?:string, opening?:number|null, closing?:number|null}}
 *          `lines` = x-ové souřadnice začátků taktů 2..N v BODECH PDF,
 *          `top` = horní linka osnovy v bodech PDF (číslo patří nad ni)
 */
export function detectBarlines(cv, pxPerPt, opt = {}) {
  const w = cv.width, h = cv.height;
  const krok = Math.max(0, Math.min(64, Math.round(opt.krok || 0)));
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
  const groups = [];
  let cur = [];
  for (const c of cs) {
    if (cur.length && c - cur[cur.length - 1] < gapMax) cur.push(c);
    else { if (cur.length) groups.push(cur); cur = [c]; }
  }
  if (cur.length) groups.push(cur);
  // Osnova = 4–6 ROVNOMĚRNÝCH linek. Nerovnoměrné skupiny (řádky textu,
  // podtržení, obloučky) se zahazují — dřív z nich vznikaly falešné „osnovy“
  // a z těch pak nesmyslný počet osnov (naměřeno `staves: 9`).
  const real = groups.filter((g) => {
    if (g.length < 4) return false;
    const gaps = [];
    for (let i = 1; i < g.length; i++) gaps.push(g[i] - g[i - 1]);
    gaps.sort((a, b) => a - b);
    const med = gaps[Math.floor(gaps.length / 2)];
    if (med < 2) return false;
    let same = 0;
    for (const gp of gaps) if (gp >= 0.7 * med && gp <= 1.4 * med) same++;
    return same >= g.length - 2;
  });
  if (!real.length) {
    return { lines: [], bars: 0, krok, staves: 0, top: 0, ok: false,
             reason: 'nenašel jsem linky osnov (' + cs.length + ' linek)' };
  }

  // 2) OSNOVA U KLEPNUTÍ — jediná, žádné seskupování do systému
  const dists = real.map((g) => {
    const y0 = g[0] / pxPerPt, y1 = g[g.length - 1] / pxPerPt;
    const dd = (ypt != null && y0 <= ypt && ypt <= y1)
      ? 0 : (ypt == null ? 0 : Math.min(Math.abs(ypt - y0), Math.abs(ypt - y1)));
    return { g, y0, y1, dd };
  });
  let near = dists[0];
  for (const it of dists) if (it.dd < near.dd) near = it;
  const rows = near.g;
  const yTop = rows[0], yBot = rows[rows.length - 1];
  const staffH = Math.max(2, yBot - yTop);
  const spacePx = Math.max(2, staffH / 4);
  const top = (Number.isFinite(opt.offsetY) ? opt.offsetY : 0) + near.y0;

  // 3) svislé tahy v této osnově (taktové čáry + nožičky + občas klíč)
  const maxW = Math.max(2, Math.round(0.9 * spacePx));      // čára je tenká
  const win0 = Math.max(0, Math.floor(yTop - 0.6 * spacePx));
  const win1 = Math.min(h - 1, Math.ceil(yBot + 0.6 * spacePx));
  const strokes = [];
  {
    const cols = [];
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = yTop; y <= yBot; y++) ink += mask[y * w + x];
      if (ink / staffH >= 0.80) cols.push(x);
    }
    let i = 0;
    while (i < cols.length) {
      let j = i;
      while (j + 1 < cols.length && cols[j + 1] - cols[j] <= 2) j++;
      if (cols[j] - cols[i] + 1 <= maxW) {
        const cx = (cols[i] + cols[j]) / 2;
        // přesah tahu nad/pod osnovou jen do diagnostiky (rozhodovat NESMÍ —
        // na skenu Carus je 0,0 a dřív kvůli tomu neprošla žádná čára)
        let runS = -1, best = 0, bestS = 0;
        for (let y = win0; y <= win1; y++) {
          if (mask[y * w + Math.round(cx)]) {
            if (runS < 0) runS = y;
            const len = y - runS + 1;
            if (len > best) { best = len; bestS = runS; }
          } else runS = -1;
        }
        strokes.push({ x: cx, overTop: (yTop - bestS) / pxPerPt,
                       overBot: (bestS + best - yBot) / pxPerPt, run: best / pxPerPt });
      }
      i = j + 1;
    }
  }

  // 4) okraje osnovy — úvodní ani koncová čára takt nezačínají
  const lineRow = (yy) => {
    const yr = Math.round(yy) * w;
    let a = -1, b = -1;
    for (let x = 0; x < w; x++) if (mask[yr + x]) { if (a < 0) a = x; b = x; }
    return [a, b];
  };
  const [leftA, leftB] = lineRow(yTop);
  const staffLeft = leftA < 0 ? 0 : leftA;
  const staffRight = leftB < 0 ? w - 1 : leftB;

  const xsAll = strokes.map(s => s.x);
  const inner = xsAll.filter(x => x > staffLeft + 0.6 * spacePx && x < staffRight - 0.8 * spacePx);
  const opening = xsAll.find(x => x <= staffLeft + 0.6 * spacePx);
  const closing = xsAll.find(x => x >= staffRight - 0.8 * spacePx);

  // 5) pravidelný řetěz = taktové čáry (nožičky na něj nesednou)
  let chain = barChain(inner, spacePx);
  // 5b) HLASY SOUSEDNÍCH OSNOV: taktová čára je ve všech osnovách systému na
  // stejném x, kdežto klíč nebo oblouček jen v jedné. Řetěz se proto pročistí —
  // na skenu Carus jinak prošel klíč jako „první taktová čára“ (naměřeno: 71
  // místo správných 132). Hlasy se počítají jen z osnov blízkých té kliknuté,
  // aby se nemíchal sousední systém.
  const staffCols = real.map((g) => {
    const yT = g[0], yB = g[g.length - 1], bh = Math.max(1, yB - yT);
    const out = [];
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = yT; y <= yB; y++) ink += mask[y * w + x];
      if (ink / bh >= 0.80) out.push(x);
    }
    return { g, out };
  });
  const nearIdx = real.indexOf(near.g);
  const neighbours = staffCols
    .map((sc, i) => ({ i, sc }))
    .filter(({ i, sc }) => i !== nearIdx && Math.abs(sc.g[0] - yTop) < 12 * spacePx)
    .map(({ sc }) => sc.out);
  const votes = (x) => neighbours.reduce((n, cols) =>
    n + (cols.some(v => Math.abs(v - x) <= 0.8 * spacePx) ? 1 : 0), 0);
  if (neighbours.length) {
    const kept = chain.filter(x => votes(x) >= Math.min(1, neighbours.length));
    if (kept.length >= 2) chain = kept;
  }
  // 5c) Klíč stojí hned za úvodní čarou a v každé osnově je na stejném x
  // (proto ho hlasy neodliší). Takt je ale širší: první taktová čára nemůže
  // být blíž než ~0,45 šířky taktu od okraje osnovy — naměřeno na skenu Carus
  // prošel klíč v x=71, správná první čára je 132 (krok 60).
  if (chain.length >= 3) {
    const d = [];
    for (let i = 1; i < chain.length; i++) d.push(chain[i] - chain[i - 1]);
    d.sort((a, b) => a - b);
    const P = d[Math.floor(d.length / 2)];
    if (P > 0) {
      const kept = chain.filter(x => x >= staffLeft + 0.45 * P);
      if (kept.length >= 2) chain = kept;
    }
  }
  const linesPt = chain.map(x => x / pxPerPt);
  const bars = linesPt.length;                    // čísel = takty 2..N
  const dbg = {
    staff: [+near.y0.toFixed(1), +near.y1.toFixed(1)], space: +(spacePx / pxPerPt).toFixed(2),
    staffLeft: +(staffLeft / pxPerPt).toFixed(1), staffRight: +(staffRight / pxPerPt).toFixed(1),
    strokes: strokes.length, inner: inner.length,
    over: strokes.filter(s => s.overTop > 0 && s.overBot > 0).length,
    all: real.map(g => [+(g[0] / pxPerPt).toFixed(1), +(g[g.length - 1] / pxPerPt).toFixed(1), g.length]),
  };
  const diag = { thr, osnov: real.length, strokes: strokes.length, inner: inner.length,
                 chain: chain.length, krok };
  const cands = strokes.map(s => [+(s.x / pxPerPt).toFixed(1), +s.overTop.toFixed(2), +s.overBot.toFixed(2)]);

  if (!chain.length) {
    return { lines: [], bars: 0, krok, staves: real.length, top, ok: false, opening, closing,
             reason: 'v téhle osnově jsem nenašel pravidelný sled taktových čar',
             diag, dbg, cands };
  }
  // „Krok“ je jen kontrola: appka takty spočítá sama a případný rozdíl ukáže.
  const krokBars = krok >= 2 ? krok - 1 : null;
  return { lines: linesPt, bars, krok, krokBars, staves: real.length, top, ok: true, thr,
           opening, closing, diag, dbg, mode: 'mřížka', cands };
}
