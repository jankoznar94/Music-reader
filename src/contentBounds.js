// src/contentBounds.js
// Detekce obsahu na stránce not (ořez okrajů + vycentrování) a osnov.
//
// Vstup: šedotónová nebo RGBA data stránky z canvasu, libovolné rozlišení.
// Výstup: obdélník obsahu v POMĚRECH stránky (0..1) + sklon + osnovy.
//
// Postup:
//   1) Otsu práh → maska inkoustu.
//   2) Odhad sklonu: hledá se úhel, při kterém jsou linky osnov nejostřejší
//      (maximum součtu čtverců řádkového průmětu).
//   3) Dlouhé řádky/sloupce = linky. Linka, která NENÍ součástí pětičky osnov
//      a leží při okraji stránky, je naskenovaná hrana / čára pera → vymaže se
//      z masky, takže se do obsahu nepočítá.
//   4) Zbytek: bloková mapa 4×4 px. Blok je obsah, jen když má inkoust aspoň
//      ve 2 řádcích a 2 sloupcích (to samo zabije 1px čáry) a má souseda
//      v řádku bloků (to zabije smítka a prach).

const BLOCK = 4;
const MIN_INK = 3;
const MIN_ROWS = 2;
const MIN_COLS = 2;

function otsu(gray) {
  const hist = new Uint32Array(256);
  for (let i = 0; i < gray.length; i++) hist[gray[i]]++;
  const total = gray.length;
  let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let wB = 0, sumB = 0, best = -1, thr = 128;
  for (let t = 0; t < 256; t++) {
    wB += hist[t];
    if (!wB) continue;
    const wF = total - wB;
    if (!wF) break;
    sumB += t * hist[t];
    const mB = sumB / wB;
    const mF = (sum - sumB) / wF;
    const v = wB * wF * (mB - mF) * (mB - mF);
    if (v > best) { best = v; thr = t; }
  }
  return thr;
}

function grayOf(rgba, w, h) {
  const gray = new Uint8Array(w * h);
  if (rgba.length === w * h) { gray.set(rgba); return gray; }
  for (let i = 0, p = 0; i < gray.length; i++, p += 4) {
    gray[i] = (rgba[p] * 299 + rgba[p + 1] * 587 + rgba[p + 2] * 114) / 1000;
  }
  return gray;
}

// Průmět do řádků s vyrovnáním sklonu (shear). Vrací histogram délek linek.
function rowProjection(ink, w, h, slope) {
  const rows = new Uint32Array(h + 2);
  for (let y = 0; y < h; y++) {
    const base = y * w;
    for (let x = 0; x < w; x++) {
      if (!ink[base + x]) continue;
      const yy = (y + slope * (x - w / 2)) | 0;
      if (yy >= 0 && yy < h) rows[yy]++;
    }
  }
  return rows;
}

function columnProjection(ink, w, h, slope) {
  const cols = new Uint32Array(w + 2);
  for (let y = 0; y < h; y++) {
    const base = y * w;
    for (let x = 0; x < w; x++) {
      if (!ink[base + x]) continue;
      const xx = (x - slope * (y - h / 2)) | 0;
      if (xx >= 0 && xx < w) cols[xx]++;
    }
  }
  return cols;
}

// Odhad sklonu: maximum součtu čtverců řádkového průmětu = nejostřejší linky.
function estimateSkew(ink, w, h, maxDeg = 3) {
  const maxSlope = Math.tan((maxDeg * Math.PI) / 180);
  const step = 0.0012;
  let bestSlope = 0, bestScore = -1;
  for (let slope = -maxSlope; slope <= maxSlope + 1e-9; slope += step) {
    const rows = rowProjection(ink, w, h, slope);
    let score = 0;
    for (let y = 0; y < h; y++) score += rows[y] * rows[y];
    if (score > bestScore) { bestScore = score; bestSlope = slope; }
  }
  return bestSlope;
}

// Najde špičky (dlouhé vodorovné linky) v průmětu a seskupí je do osnov.
function findLinePeaks(proj, minLen) {
  const peaks = [];
  for (let y = 1; y < proj.length - 1; y++) {
    if (proj[y] < minLen || proj[y] < proj[y - 1] || proj[y] < proj[y + 1]) continue;
    const last = peaks[peaks.length - 1];
    if (last && y - last.y <= 2) {
      if (proj[y] > last.v) { last.y = y; last.v = proj[y]; }
    } else peaks.push({ y, v: proj[y] });
  }
  return peaks;
}

function groupStaves(peaks, h) {
  // Pětička linek se stejným rozestupem (tolerance 45 %).
  const groups = [];
  const staffRows = new Uint8Array(h + 2);
  let spacingSum = 0, spacingN = 0;
  for (let i = 0; i + 4 < peaks.length; i++) {
    const d = [];
    for (let k = 1; k < 5; k++) d.push(peaks[i + k].y - peaks[i + k - 1].y);
    const mean = d.reduce((a, b) => a + b, 0) / 4;
    if (mean < 2 || mean > h * 0.03) continue;
    const dev = Math.max(...d.map(x => Math.abs(x - mean))) / mean;
    if (dev > 0.45) continue;
    groups.push({ y: peaks[i].y, spacing: mean });
    spacingSum += mean; spacingN++;
    const y0 = peaks[i].y - Math.ceil(mean), y1 = peaks[i + 4].y + Math.ceil(mean);
    for (let y = Math.max(0, y0); y <= Math.min(h, y1); y++) staffRows[y] = 1;
    i += 3; // další pětička začíná až za touhle
  }
  return { groups, staffRows, spacing: spacingN ? spacingSum / spacingN : 0 };
}

/**
 * @param {Uint8ClampedArray|Uint8Array} rgba RGBA nebo šedotón
 * @returns {{crop:{x,y,w,h}, angle:number, staff:{spacing,groups}, ok:boolean, ink:number}}
 */
export function analyzeContent(rgba, w, h) {
  const gray = grayOf(rgba, w, h);
  const hist = new Uint32Array(256);
  for (let i = 0; i < gray.length; i++) hist[gray[i]]++;
  const otsuThr = otsu(gray);
  // Otsu sám o sobě ztrácí tenké antialiasované linky (na 700 px široké
  // stránce jsou světle šedé) — osnovy se pak rozpadnou. Proto práh táhneme
  // od papíru: vše, co je o víc než 30 % tmavší než papír, je inkoust.
  const pct = (q) => {
    let acc = 0;
    const target = gray.length * q;
    for (let i = 0; i < 256; i++) { acc += hist[i]; if (acc >= target) return i; }
    return 255;
  };
  const paper = pct(0.90);
  const dark = pct(0.02);
  const paperThr = Math.min(235, Math.round(paper - 0.30 * Math.max(1, paper - dark)));
  const thr = Math.max(otsuThr, paperThr);
  const ink = new Uint8Array(w * h);
  let inkCount = 0;
  for (let i = 0; i < gray.length; i++) {
    if (gray[i] < thr) { ink[i] = 1; inkCount++; }
  }
  if (inkCount < w * h * 0.0008) {
    return { crop: { x: 0, y: 0, w: 1, h: 1 }, angle: 0,
             staff: { spacing: 0, groups: 0 }, ok: false, ink: 0 };
  }

  const slope = estimateSkew(ink, w, h);
  const angle = (Math.atan(slope) * 180) / Math.PI;

  // --- Vodorovné linky ---
  const rows = rowProjection(ink, w, h, slope);
  const hPeaks = findLinePeaks(rows, Math.max(20, w * 0.30));
  const staves = groupStaves(hPeaks, h);

  // Naskenovaná hrana / náhodná čára: dlouhý řádek mimo osnovy, u okraje.
  const noiseRow = new Uint8Array(h + 2);
  for (const p of hPeaks) {
    if (staves.staffRows[p.y]) continue;
    if (p.v < w * 0.45) continue;
    if (p.y < h * 0.18 || p.y > h * 0.82) noiseRow[p.y] = 1;
  }
  // --- Svislé linky ---
  const cols = columnProjection(ink, w, h, slope);
  const vPeaks = findLinePeaks(cols, Math.max(20, h * 0.30));
  const noiseCol = new Uint8Array(w + 2);
  for (const p of vPeaks) {
    if (p.v < h * 0.45) continue;
    if (p.x < w * 0.12 || p.x > w * 0.88) noiseCol[p.x] = 1;
  }

  // Vymazat šumové linky z masky (se zohledněním sklonu).
  if (noiseRow.some(v => v) || noiseCol.some(v => v)) {
    for (let y = 0; y < h; y++) {
      const base = y * w;
      for (let x = 0; x < w; x++) {
        if (!ink[base + x]) continue;
        const yy = (y + slope * (x - w / 2)) | 0;
        const xx = (x - slope * (y - h / 2)) | 0;
        if ((yy >= 0 && yy < h && noiseRow[yy]) || (xx >= 0 && xx < w && noiseCol[xx])) {
          ink[base + x] = 0;
        }
      }
    }
  }

  // --- Bloková mapa obsahu ---
  const bw = Math.ceil(w / BLOCK), bh = Math.ceil(h / BLOCK);
  const okBlock = new Uint8Array(bw * bh);
  for (let by = 0; by < bh; by++) {
    for (let bx = 0; bx < bw; bx++) {
      let n = 0, rowsMask = 0, colsMask = 0;
      const y0 = by * BLOCK, x0 = bx * BLOCK;
      for (let y = y0; y < Math.min(y0 + BLOCK, h); y++) {
        const base = y * w;
        for (let x = x0; x < Math.min(x0 + BLOCK, w); x++) {
          if (ink[base + x]) {
            n++; rowsMask |= 1 << (y - y0); colsMask |= 1 << (x - x0);
          }
        }
      }
      if (n < MIN_INK) continue;
      let rc = 0, cc = 0;
      for (let i = 0; i < BLOCK; i++) {
        if (rowsMask & (1 << i)) rc++;
        if (colsMask & (1 << i)) cc++;
      }
      if (rc >= MIN_ROWS && cc >= MIN_COLS) okBlock[by * bw + bx] = 1;
    }
  }
  const solid = new Uint8Array(bw * bh);
  for (let by = 0; by < bh; by++) {
    for (let bx = 0; bx < bw; bx++) {
      if (!okBlock[by * bw + bx]) continue;
      const l = bx > 0 ? okBlock[by * bw + bx - 1] : 0;
      const r = bx < bw - 1 ? okBlock[by * bw + bx + 1] : 0;
      if (l || r) solid[by * bw + bx] = 1;
    }
  }
  const rowCount = new Uint16Array(bh), colCount = new Uint16Array(bw);
  for (let by = 0; by < bh; by++) {
    for (let bx = 0; bx < bw; bx++) if (solid[by * bw + bx]) rowCount[by]++;
  }
  for (let bx = 0; bx < bw; bx++) {
    for (let by = 0; by < bh; by++) if (solid[by * bw + bx]) colCount[bx]++;
  }
  let minBy = bh, maxBy = -1, minBx = bw, maxBx = -1;
  for (let by = 0; by < bh; by++) if (rowCount[by] >= 2) { if (by < minBy) minBy = by; maxBy = by; }
  for (let bx = 0; bx < bw; bx++) if (colCount[bx] >= 2) { if (bx < minBx) minBx = bx; maxBx = bx; }

  const staffOut = { spacing: staves.spacing / h, groups: staves.groups.length };
  if (maxBy < 0 || maxBx < 0) {
    return { crop: { x: 0, y: 0, w: 1, h: 1 }, angle, staff: staffOut, ok: false,
             ink: inkCount / (w * h) };
  }

  // Okraje: nechat malý odstup, ať noty nejsou nalepené na hranu displeje.
  // Bloková mřížka je hrubá (4 px), takže obalovou křivku doladíme přesnými
  // extrémy inkoustu UVNITŘ blokového obalu — jen v místech, kde je inkoustu
  // dost (řádek/sloupec ≥ 2 px), aby kraj nevychýlil osamocený smítko.
  const wx0 = minBx * BLOCK, wx1 = Math.min(w, (maxBx + 1) * BLOCK);
  const wy0 = minBy * BLOCK, wy1 = Math.min(h, (maxBy + 1) * BLOCK);
  const rowMin = Math.max(2, Math.round(w * 0.0015));
  const colMin = Math.max(2, Math.round(h * 0.0015));
  let ex0 = wx0, ex1 = wx1 - 1, ey0 = wy0, ey1 = wy1 - 1;
  for (let x = wx0; x < wx1; x++) {
    let c = 0;
    for (let y = wy0; y < wy1; y++) if (ink[y * w + x]) c++;
    if (c >= colMin) { ex0 = x; break; }
  }
  for (let x = wx1 - 1; x >= wx0; x--) {
    let c = 0;
    for (let y = wy0; y < wy1; y++) if (ink[y * w + x]) c++;
    if (c >= colMin) { ex1 = x; break; }
  }
  for (let y = wy0; y < wy1; y++) {
    let c = 0;
    for (let x = wx0; x < wx1; x++) if (ink[y * w + x]) c++;
    if (c >= rowMin) { ey0 = y; break; }
  }
  for (let y = wy1 - 1; y >= wy0; y--) {
    let c = 0;
    for (let x = wx0; x < wx1; x++) if (ink[y * w + x]) c++;
    if (c >= rowMin) { ey1 = y; break; }
  }

  const padX = 0.012, padY = 0.02;
  const rawX0 = ex0 / w, rawX1 = (ex1 + 1) / w;
  const rawY0 = ey0 / h, rawY1 = (ey1 + 1) / h;
  const cx = (rawX0 + rawX1) / 2, cy = (rawY0 + rawY1) / 2;
  const halfW = Math.max(0.06, (rawX1 - rawX0) / 2 + padX);
  const halfH = Math.max(0.05, (rawY1 - rawY0) / 2 + padY);
  let x0 = cx - halfW, x1 = cx + halfW;
  let y0 = cy - halfH, y1 = cy + halfH;
  // Když výřez přeteče okraj stránky, posunout ho (ne zmenšit) — obsah
  // zůstane uprostřed a jen se dorovná k okraji.
  if (x0 < 0) { x1 -= x0; x0 = 0; }
  if (x1 > 1) { x0 -= (x1 - 1); x1 = 1; }
  if (y0 < 0) { y1 -= y0; y0 = 0; }
  if (y1 > 1) { y0 -= (y1 - 1); y1 = 1; }
  x0 = Math.max(0, x0); y0 = Math.max(0, y0);
  x1 = Math.min(1, x1); y1 = Math.min(1, y1);

  return {
    crop: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 },
    angle,
    staff: staffOut,
    ok: true,
    ink: inkCount / (w * h),
  };
}
