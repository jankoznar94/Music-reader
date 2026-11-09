// src/barLines.js — TAKTOVÉ ČÁRY v pásu systému (pro „Dočíslovat systém“)
//
// PROČ TAKHLE: na skenech (Mozart, Carus) čáry NEKRESLÍ přes celý systém —
// mezi osnovami je mezera, takže „svislý tah přes celý pás“ neexistuje a
// detekce, která ho vyžadovala, nenašla nic (naměřeno: 3–4 nálezy, samé svorky).
// Fungující postup (ověřeno na str. 4, systém 24–26 → čáry na 75,6 / 265,9 /
// 421,7 bodu, tj. přesně tři takty):
//   1. najdi LINKY OSNOV (řádky s dlouhým vodorovným tahem) a seskup je do osnov,
//   2. v KAŽDÉ osnově hledej sloupce vyplněné po celé její výšce = taktová čára,
//   3. čára platí, když ji vidí aspoň polovina osnov (shoda do 1,5 bodu),
//   4. zahodit levý okraj (svorku) — čáry začínají až za ním.
// Počet taktů = počet nalezených čar (každá čára = začátek taktu, poslední
// takt jde do konce systému). Ten se pak ověří proti „Kroku“.

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

/**
 * Najde taktové čáry v pásu stránky (canvas = pruh přes celou šířku).
 * @param {HTMLCanvasElement} cv
 * @param {number} pxPerPt pixely canvasu na PDF bod
 * @returns {{lines:number[], bars:number, staves:number, staffLines:number}}
 *          `lines` = x-ové souřadnice čar v BODECH PDF (bez svorky), vzestupně
 */
export function detectBarlines(cv, pxPerPt) {
  const w = cv.width, h = cv.height;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const hist = new Uint32Array(256);
  for (let i = 0, p = 0; p < w * h; p++, i += 4) {
    hist[Math.round((d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000)]++;
  }
  const thr = otsu(hist, w * h);
  const mask = new Uint8Array(w * h);
  for (let i = 0, p = 0; p < w * h; p++, i += 4) {
    mask[p] = ((d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000) < thr ? 1 : 0;
  }

  // 1) linky osnov = řádky s dlouhým vodorovným tahem
  const centres = [];
  let runStart = -1;
  for (let y = 0; y <= h; y++) {
    let ink = 0;
    if (y < h) {
      const off = y * w;
      for (let x = 0; x < w; x++) ink += mask[off + x];
    }
    const isLine = y < h && ink / w > 0.45;
    if (isLine && runStart < 0) runStart = y;
    if (!isLine && runStart >= 0) {
      centres.push(Math.round((runStart + y - 1) / 2));
      runStart = -1;
    }
  }
  if (centres.length < 5) return { lines: [], bars: 0, staves: 0, staffLines: centres.length };

  // 2) osnovy = skupiny linek blíž než ~8 bodů
  const gapMax = Math.max(20, Math.round(pxPerPt * 8));
  const staves = [];
  let cur = [centres[0]];
  for (let i = 1; i < centres.length; i++) {
    if (centres[i] - cur[cur.length - 1] < gapMax) cur.push(centres[i]);
    else { staves.push(cur); cur = [centres[i]]; }
  }
  staves.push(cur);
  const realStaves = staves.filter(s => s.length >= 3);

  // 3) v každé osnově sloupce vyplněné po celé výšce = taktová čára
  const hits = [];
  const maxW = Math.round(pxPerPt * 1.6);
  for (const st of realStaves) {
    const yTop = Math.max(0, st[0] - 2), yBot = Math.min(h, st[st.length - 1] + 3);
    const bh = Math.max(1, yBot - yTop);
    const cols = [];
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = yTop; y < yBot; y++) ink += mask[y * w + x];
      if (ink / bh >= 0.85) cols.push(x);
    }
    const xs = [];
    let i = 0;
    while (i < cols.length) {
      let j = i;
      while (j + 1 < cols.length && cols[j + 1] - cols[j] <= 2) j++;
      if (cols[j] - cols[i] + 1 <= maxW) xs.push((cols[i] + cols[j]) / 2);
      i = j + 1;
    }
    hits.push(xs);
  }

  // 4) čára platí, když ji vidí aspoň polovina osnov
  const all = hits.flat().sort((a, b) => a - b);
  const merged = [];
  const tol = pxPerPt * 1.5;
  for (const x of all) {
    const last = merged[merged.length - 1];
    if (last && x - last[last.length - 1] <= tol) last.push(x);
    else merged.push([x]);
  }
  const need = Math.max(2, Math.floor(realStaves.length / 2));
  let lines = merged.filter(g => g.length >= need)
    .map(g => g.reduce((s, v) => s + v, 0) / g.length / pxPerPt);
  // 5) levý okraj (svorka, začátek osnovy) není taktová čára
  lines = lines.filter(x => x >= 55).sort((a, b) => a - b);
  // 6) dvě čáry blíž než 6 bodů nejsou dva takty: bývá to začátek osnovy
  //    a první taktová čára hned za ním (naměřeno 70,6 a 75,7) — necháme tu
  //    druhou, ta je skutečná čára začátku taktu.
  const kept = [];
  for (let i = 0; i < lines.length; i++) {
    if (i + 1 < lines.length && lines[i + 1] - lines[i] < 6) continue;
    if (kept.length && lines[i] - kept[kept.length - 1] < 6) { kept[kept.length - 1] = lines[i]; continue; }
    kept.push(lines[i]);
  }
  lines = kept;
  return { lines, bars: lines.length, staves: realStaves.length, staffLines: centres.length };
}
