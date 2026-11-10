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
//  6) Pravý okraj osnov se bral jako MAXIMUM inkoustu na linkách — jediná
//     zatoulaná značka (trylek přes linku, str. 7: o 13 b) pak odsunula okraj a
//     koncová taktová čára přestala být „blízko okraje“ → systém dostal o takt
//     navíc. Teď MEDIÁN konců linek.
//  7) Nožička dlouhého akordu (tři noty nad sebou, jedna nožička) prošla testem
//     „je ve víc osnovách“ — ve sboru jsou akordy hlasů svisle zarovnané
//     (str. 7, 3. systém: falešné čáry 100 a 139 b s podporou 2 ze 3). Teď se
//     u neúplné podpory navíc vyžaduje průchod MEZEROU mezi osnovami — tam
//     taktová čára systému prochází, nožička ne.
//  8) Koncová čára se poznávala podle vzdálenosti od konce linek — v této sazbě
//     ale linky přetahují ~45 b za koncovou čáru do okraje (str. 9/1. a 2.
//     systém, str. 13/2. a 3., str. 7/2.–4.), takže zůstala mezi vnitřními a
//     systém dostal o takt navíc. Teď rozhoduje OBSAH: za koncovou čarou je
//     prázdno (0–1 % inkoustu), za vnitřní čarou hudba (12–34 %). Měří se se
//     vynechanými linkami osnov a vynechanými sloupci přes celou stránku.
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
  const offY = Number.isFinite(opt.offsetY) ? opt.offsetY : 0;
  // ⚠️ Klepnutí (`ypt`) je v bodech PDF CELÉ STRÁNKY, ale řádky osnov se měří
  // v PÁSU (crop), takže se musí odečíst `offsetY`. Dřív se neodečítalo a výběr
  // osnovy u klepnutí padal o systém vedle (naměřeno: klepnutí na klavír 470 b
  // vybralo systém pod ním).
  const ypt = Number.isFinite(opt.ypt) ? opt.ypt - offY : null;
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
  // Tolerance: na vybledlém skenu se jedna linka osnovy detekuje DVAKRÁT nebo
  // se přidá řádek textu písně (naměřeno str. 7: 393,5…410,3 = 6 řádků), takže
  // se připouštějí až 3 nepravidelné mezery. Text se pak pozná podle toho, že
  // v něm NENÍ svislá čára přes celou výšku (skutečná osnova má aspoň 2).
  const vStrokes = (g) => {
    const yT = g[0], yB = g[g.length - 1], bh = Math.max(1, yB - yT);
    let n = 0, run = 0;
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = yT; y <= yB; y++) ink += mask[y * w + x];
      if (ink / bh >= 0.9) { run++; }
      else { if (run >= 1) n++; run = 0; }
    }
    if (run) n++;
    return n;
  };
  const real = groups.filter((g) => {
    if (g.length < 4 || g.length > 8) return false;
    const gaps = [];
    for (let i = 1; i < g.length; i++) gaps.push(g[i] - g[i - 1]);
    gaps.sort((a, b) => a - b);
    const med = gaps[Math.floor(gaps.length / 2)];
    if (med < 2) return false;
    let same = 0;
    for (const gp of gaps) if (gp >= 0.7 * med && gp <= 1.4 * med) same++;
    if (same < g.length - 3) return false;
    return vStrokes(g) >= 2;
  });
  if (!real.length) {
    return { lines: [], bars: 0, krok, staves: 0, top: 0, ok: false,
             reason: 'nenašel jsem linky osnov (' + cs.length + ' linek)' };
  }

  // 2) SYSTÉM kolem klepnutí = sousední osnovy, mezi kterými PROCHÁZÍ taktová
  //    čára mezerou. Dřív se brala jen JEDNA osnova (ta u klepnutí), takže u
  //    sboru + klavíru se čísla tiskla nad klavírní osnovu doprostřed systému
  //    (Jan, listopad 2026). Sousedství se pozná podle inkoustu ve svislém
  //    sloupci v mezeře — praporek/klíč tam neprochází, taktová čára ano.
  //    Okraje osnovy se z testu vyhazují (závorka systému a koncová čára
  //    vypadají jako spojnice i mezi dvěma systémy).
  const dists = real.map((g) => {
    const y0 = g[0] / pxPerPt, y1 = g[g.length - 1] / pxPerPt;
    const dd = (ypt != null && y0 <= ypt && ypt <= y1)
      ? 0 : (ypt == null ? 0 : Math.min(Math.abs(ypt - y0), Math.abs(ypt - y1)));
    return { g, y0, y1, dd };
  });
  let nearIdx = 0;
  for (let i = 1; i < dists.length; i++) if (dists[i].dd < dists[nearIdx].dd) nearIdx = i;
  const near = dists[nearIdx];
  const rows = near.g;
  const yTop = rows[0], yBot = rows[rows.length - 1];
  const staffH = Math.max(2, yBot - yTop);
  const spacePx = Math.max(2, staffH / 4);

  // Okraje osnovy (první a poslední inkoust na horní lince) — kvůli testu spojení.
  const staffEdges = (g) => {
    const yr = Math.round(g[0]) * w;
    let a = -1, b = -1;
    for (let x = 0; x < w; x++) if (mask[yr + x]) { if (a < 0) a = x; b = x; }
    return [a < 0 ? 0 : a, b < 0 ? w - 1 : b];
  };
  // Kolik svislých sloupců v mezeře mezi dvěma osnovami je plných (taktová čára).
  const gapInk = (up, lo) => {
    const y0 = up[up.length - 1] + 2, y1 = lo[0] - 2;
    if (y1 <= y0) return 0;
    const [L, R] = staffEdges(up);
    const sp = Math.max(2, (up[up.length - 1] - up[0]) / 4);
    const x0 = Math.max(0, Math.round(L + 2 * sp));
    const x1 = Math.min(w - 1, Math.round(R - 2 * sp));
    const need = y1 - y0 + 1;
    let cols = 0;
    for (let x = x0; x <= x1; x++) {
      let ink = 0;
      for (let y = y0; y <= y1; y++) ink += mask[y * w + x];
      if (ink / need >= 0.9) cols++;
    }
    return cols;
  };
  const gapList = [];
  for (let i = 0; i + 1 < real.length; i++) {
    gapList.push({ gap: real[i + 1][0] - real[i][real[i].length - 1], ink: gapInk(real[i], real[i + 1]) });
  }
  // SYSTÉM = souvislý pás osnov. Rozhoduje MEZERA + SPOJNICE:
  //  * mezera větší než 1,5 × NEJMENŠÍ typická mezera (25. percentil) a BEZ
  //    spojnice = hranice systému; na skenu Carus jsou uvnitř systému mezery
  //    18–38 b, mezi systémy 37–45 b, takže samotná velikost nestačí a rozhoduje
  //    spojnice (závorka / taktová čára přes mezeru),
  //  * extrémní mezera (> 3 × typická) je hranice vždy — tam spojnice nepatří.
  // ⚠️ Základ se bere z 25. percentilu, ne z mediánu: v pásu, kde je jen jeden
  // systém, převažují velké mezery sbor→klavír a medián je nad hranicí systému
  // (naměřeno: 11 osnov slitých do jednoho systému na str. 8).
  const gapSorted = gapList.map((q) => q.gap).sort((a, b) => a - b);
  const gapBase = gapSorted.length ? gapSorted[Math.floor((gapSorted.length - 1) * 0.25)] : 0;
  const boundary = (q) => gapBase > 0
    && (q.gap > 3 * gapBase || (q.gap > 1.5 * gapBase && q.ink < 1));
  const conn = gapList.map((q) => !boundary(q));
  let sysA = nearIdx, sysB = nearIdx;
  while (sysA > 0 && conn[sysA - 1]) sysA--;
  while (sysB < real.length - 1 && conn[sysB]) sysB++;
  const sysTopPx = real[sysA][0];
  const sysBotPx = real[sysB][real[sysB].length - 1];
  const top = offY + sysTopPx / pxPerPt;
  const sysCount = sysB - sysA + 1;

  // 3) svislé tahy v KAŽDÉ osnově systému (taktové čáry + nožičky + občas klíč)
  // Prahová hodnota pokrytí se zkouší od přísné k volnější: při 0,80 procházely
  // nožičky tlustých akordů (naměřeno 10–22 „čar“ v osnově, skutečné 4–6), takže
  // se s nimi pak míchaly i skutečné čáry. Na 0,95 zůstanou jen svislice přes
  // celou osnovu — a ty se napříč systémem shodují.
  const maxW = Math.max(2, Math.round(0.9 * spacePx));      // čára je tenká
  const staffColsAt = (cov) => {
    const res = [];
    for (let i = sysA; i <= sysB; i++) {
      const g = real[i];
      const yT = g[0], yB = g[g.length - 1], bh = Math.max(1, yB - yT);
      const cols = [];
      for (let x = 0; x < w; x++) {
        let ink = 0;
        for (let y = yT; y <= yB; y++) ink += mask[y * w + x];
        if (ink / bh >= cov) cols.push(x);
      }
      const out = [];
      let k = 0;
      while (k < cols.length) {
        let j = k;
        while (j + 1 < cols.length && cols[j + 1] - cols[j] <= 2) j++;
        if (cols[j] - cols[k] + 1 <= maxW) out.push((cols[k] + cols[j]) / 2);
        k = j + 1;
      }
      res.push({ i, out });
    }
    return res;
  };

  // 3b) TAKTOVÁ ČÁRA JE VE VŠECH OSNOVÁCH SYSTÉMU na stejném x, kdežto nožička
  // noty nebo klíč jen v jedné. Dřív se hlasovalo „aspoň jeden soused“, takže
  // prošly dvě ze čtyř čar a občas i nožička (Jan, listopad 2026).
  // ⚠️ Toleranci shlukování drž na 1,2 mezery: sken je mírně křivý a táž čára
  // vychází v různých osnovách až o 4 b jinde (naměřeno na str. 10: 70 vs 74 b).
  // Při 0,6 mezery se čára rozdělila na dva shluky s půlkovou podporou a zmizela.
  const xTol = Math.max(2, 1.2 * spacePx);
  // Podpora: toleruje JEDNU osnovu, kde sken čáru ztratil (jinak vypadávaly
  // skutečné čáry — Jan: „ignoruje poslední takt“), ale ne dvě (to už je nožička
  // v husté klavírní osnově: naměřeno 4/6 na str. 4).
  const need = sysCount >= 2 ? Math.max(2, sysCount - 1) : 1;
  // 3c) NOŽIČKA AKORDU NAPŘÍČ OSNOVAMI. Ve sborech jsou akordy jednotlivých
  // hlasů svisle zarovnané, takže dlouhá nožička tří not nad sebou projde
  // „v tolika osnovách“ jako taktová čára a systém pak dostane o takt víc
  // (naměřeno str. 7, 3. systém: falešné čáry na 100 a 139 b se podporou 2 ze 3).
  // Rozdíl: skutečná taktová čára SYSTÉMU prochází i MEZEROU mezi osnovami,
  // nožička zůstane uvnitř své osnovy. Když je podpora plná (čára ve všech
  // osnovách), mezera se nevyžaduje — sken ji občas ztratí.
  const gapCols = [];
  for (let i = sysA; i < sysB; i++) {
    const y0 = real[i][real[i].length - 1] + 2, y1 = real[i + 1][0] - 2;
    if (y1 <= y0) continue;
    const needRows = y1 - y0 + 1;
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = y0; y <= y1; y++) ink += mask[y * w + x];
      if (ink / needRows >= 0.9) gapCols.push(x);
    }
  }
  const crossesGap = (x) => gapCols.some(g => Math.abs(g - x) <= xTol);
  const clusterize = (staffCols) => {
    const all = [];
    for (const sc of staffCols) for (const x of sc.out) all.push({ x, i: sc.i });
    all.sort((a, b) => a.x - b.x);
    const clusters = [];
    for (const p of all) {
      const c = clusters[clusters.length - 1];
      if (c) {
        const mean = c.xs.reduce((n, q) => n + q.x, 0) / c.xs.length;
        if (Math.abs(p.x - mean) <= xTol) { c.xs.push(p); continue; }
      }
      clusters.push({ xs: [p] });
    }
    const candsX = [];
    for (const c of clusters) {
      const support = new Set(c.xs.map(p => p.i)).size;
      const x = c.xs.reduce((n, p) => n + p.x, 0) / c.xs.length;
      if (support >= need && (support >= sysCount || sysCount < 2 || crossesGap(x))) candsX.push(x);
    }
    return { clusters, candsX, all };
  };
  let staffCols = staffColsAt(0.95);
  let cl = clusterize(staffCols);
  let covUsed = 0.95;
  if (cl.candsX.length < 2) {
    // slabý/šedý sken: zkusit volnější práh, ať se systém nevyhodnotí jako prázdný
    covUsed = 0.85;
    staffCols = staffColsAt(covUsed);
    cl = clusterize(staffCols);
  }
  const { clusters, candsX, all } = cl;

  // 4) okraje systému. Bere se první a poslední inkoust na linkách VŠECH osnov
  // systému, ale sloupce protínající celou stránku se ignorují — na kraji skenu
  // je svislá linka (vazba), která by okraj posunula o desítky bodů doleva.
  const colInk = new Uint32Array(w);
  for (let y = 0; y < h; y++) {
    const off = y * w;
    for (let x = 0; x < w; x++) if (mask[off + x]) colInk[x]++;
  }
  const isArtifact = (x) => colInk[x] > 0.5 * h || x < 0.02 * w;
  // ⚠️ Okraj se bere jako MEDIÁN konců linek, ne jako maximum: na str. 7 táhne
  // pravý okraj o 13 b doprava jediná zatoulaná značka (trylek přes linku),
  // a pak už koncová taktová čára nevypadá „blízko okraje“ → zůstane mezi
  // vnitřními a systém dostane o takt navíc.
  const medOf = (arr) => {
    if (!arr.length) return 0;
    const s = arr.slice().sort((a, b) => a - b);
    return s[Math.floor((s.length - 1) / 2)];
  };
  const leftEnds = [], rightEnds = [];
  for (let i = sysA; i <= sysB; i++) {
    for (const yy of real[i]) {
      const yr = Math.round(yy) * w;
      for (let x = 0; x < w; x++) if (mask[yr + x] && !isArtifact(x)) { leftEnds.push(x); break; }
      for (let x = w - 1; x >= 0; x--) if (mask[yr + x] && !isArtifact(x)) { rightEnds.push(x); break; }
    }
  }
  let staffLeft = medOf(leftEnds);
  let staffRight = medOf(rightEnds);
  if (!rightEnds.length || staffLeft > staffRight) { staffLeft = 0; staffRight = w - 1; }

  const medGap = (arr) => {
    const d = [];
    for (let i = 1; i < arr.length; i++) d.push(arr[i] - arr[i - 1]);
    d.sort((a, b) => a - b);
    return d.length ? d[Math.floor(d.length / 2)] : 0;
  };
  let rest = candsX.slice().sort((a, b) => a - b)
    .filter(x => x > staffLeft + 0.6 * spacePx);
  let holeDbg = null;   // diagnostika doplněných čar (jen pro panel/sondu)
  // 4b) ZTRACENÁ ČÁRA UPROSTŘED SYSTÉMU. Na vybledlém skenu se jedna čára
  // nedetekuje (v jedné osnově má krytí jen 76 %, práh je 95 %), a protože
  // zbylé čáry drží krok, systém dostane o takt MÍŇ — číslo pak přeskočí
  // (naměřeno str. 15/3. systém: čára na 159 b chybí a takt 58 se nevyčíslí).
  // Pozná se to podle DVOJNÁSOBNÉ mezery: takty jsou stejně široké, takže
  // mezera ~2× delší než medián = chybí právě jedna čára. Doplní se kandidát
  // z volnějšího prahu (72 %) nejblíž očekávané poloze, a jen když ho vidí
  // aspoň polovina osnov systému (nožička ne).
  if (rest.length >= 1 && rest.length <= 40) {
    // Do mezer se počítá i LEVÝ OKRAJ systému — chybějící čára často stojí
    // hned za úvodní čarou (ta se z kandidátů vyhodí, takže by mezera nevznikla).
    const seq = [staffLeft].concat(rest);
    const P0 = medGap(seq);
    const holes = [];
    for (let i = 1; i < seq.length; i++) {
      const g = seq[i] - seq[i - 1];
      if (!(P0 > 0) || g <= 1.7 * P0) continue;
      // Mezera musí být SKORO PŘESNĚ k-násobkem kroku — jinak jsou takty
      // nestejně široké a dopočítávat se nic nemá (naměřeno str. 9/3. systém:
      // mezera 1,8× kroku, ale na 2× chybí 20 %, a doplněná „čára“ byla nožička).
      const kk = Math.round(g / P0);
      if (kk < 2 || kk > 6 || Math.abs(g - kk * P0) > 0.25 * P0) continue;
      holes.push([seq[i - 1], seq[i], g]);
    }
    if (holes.length) {
      const loose = new Map();
      for (const sc of staffColsAt(0.72)) for (const x of sc.out) {
        const hit = [...loose.keys()].find(k => Math.abs(k - x) <= xTol);
        if (hit == null) loose.set(x, new Set([sc.i]));
        else loose.get(hit).add(sc.i);
      }
      const supAt = (x) => {
        let s = 0;
        for (const [k, sup] of loose) if (Math.abs(k - x) <= xTol) s = Math.max(s, sup.size);
        return s;
      };
      // Práh podpory se bere z TOHO, co v systému už uznané čáry mají — když
      // systém detekce slepí z víc osnov (naměřeno str. 67: osnov 11), nemůže
      // se chtít plná podpora.
      const refSups = rest.map(supAt).filter(v => v > 0);
      const refMax = refSups.length ? Math.max(...refSups) : sysCount;
      // Doplní se jen čára, kterou vidí skoro tolik osnov jako tu nejsilnější
      // uznanou (nožička zarovnaných akordů má o osnovu méně — str. 9/3. systém).
      const minSup = Math.min(6, Math.max(2, Math.ceil(0.9 * refMax)));
      const wantSup = minSup;
      const add = [];
      for (const [a, b, g] of holes) {
        const k = Math.round(g / P0);
        if (k < 2 || k > 6) continue;
        const step = g / k;
        for (let j = 1; j < k; j++) {
          const want = a + j * step;
          let best = null;
          for (const [x, sup] of loose) {
            if (sup.size < wantSup) continue;
            if (Math.abs(x - want) > 0.45 * step) continue;
            if (!best || Math.abs(x - want) < Math.abs(best - want)) best = x;
          }
          if (best != null) add.push(best);
        }
      }
      if (add.length) rest = rest.concat(add).sort((x, y) => x - y);
      holeDbg = { holes: holes.map(h => [Math.round(h[0] / pxPerPt), Math.round(h[1] / pxPerPt),
                                          Math.round(h[2] / pxPerPt)]),
                  loose: loose.size, minSup, refSups: refSups.slice().sort((a, b) => a - b),
                  add: add.map(v => +(v / pxPerPt).toFixed(1)) };
    }
  }
  // Úvodní čára systému se nečísluje. Je to první kandidát za okrajem, ale jen
  // když stojí blíž než 0,75 šířky taktu — jinak je to skutečná vnitřní čára
  // a úvodní se nedetekovala (naměřeno: str. 6 — závorka v 14 b, úvodní čára
  // v 68 b, takty 94 b; str. 4 — úvodní hned u okraje).
  let opening = null;
  if (rest.length === 1) opening = rest.pop();
  else if (rest.length >= 2) {
    const P = medGap(rest);
    if (P > 0 && rest[0] - staffLeft < 0.75 * P) opening = rest.shift();
  }
  // Koncová čára stojí na konci not — ale LINKY OSNOV v této sazbě přetahují
  // ~45 b do pravého okraje, takže vzdálenost od okraje nic neříká (dřív se
  // podle ní koncová čára hledala a na str. 9/1. a 2. systém a str. 13/3.
  // systém zůstala mezi vnitřními → systém dostal o takt navíc).
  // Rozhoduje OBSAH: za skutečnou vnitřní čarou je hudba (12–16 % inkoustu),
  // za koncovou čarou už jen prázdné linky (1–2 %). Linky osnov se při měření
  // vynechávají, jinak by „prázdno“ nikdy nevyšlo.
  const staffRowSkip = new Set();
  for (let i = sysA; i <= sysB; i++) {
    for (const yy of real[i]) {
      const r = Math.round(yy);
      for (let d = -2; d <= 2; d++) staffRowSkip.add(r + d);
    }
  }
  const musicDensity = (xa, xb) => {
    const x0 = Math.max(0, Math.round(xa)), x1 = Math.min(w - 1, Math.round(xb));
    if (x1 <= x0) return 0;
    const y0 = Math.round(real[sysA][0]);
    const y1 = Math.round(real[sysB][real[sysB].length - 1]);
    let ink = 0, n = 0;
    for (let y = y0; y <= y1; y++) {
      if (staffRowSkip.has(y)) continue;
      const off = y * w;
      for (let x = x0; x <= x1; x++) {
        // Sloupce přes celou stránku (vazba, stín u okraje skenu) se nepočítají
        // — jinak „prázdný“ okraj vyjde jako plný inkoustu.
        if (isArtifact(x)) continue;
        ink += mask[off + x];
        n++;
      }
    }
    return n ? ink / n : 0;
  };
  let closing = null;
  while (rest.length && rest[rest.length - 1] > staffRight - 2.5 * spacePx) closing = rest.pop();
  // …a když linky přetahují, rozhodne prázdno za poslední čarou. Pojistka:
  // zahazuje se jen KRÁTKÝ chvost (do 0,6 šířky taktu) — koncová čára v této
  // sazbě stojí ~45 b před koncem linek, kdežto skutečný poslední takt je
  // široký jako ostatní, takže se nezahodí.
  const barP = medGap(rest);
  const tailShort = () => {
    const t = staffRight - rest[rest.length - 1];
    return barP > 0 ? t < 0.6 * barP : t < 8 * spacePx;
  };
  while (rest.length && tailShort()
         && musicDensity(rest[rest.length - 1] + spacePx, staffRight) < 0.05) {
    closing = rest.pop();
  }

  // 5) VNITŘNÍ ČÁRY = všichni kandidáti, které vidí celý systém. Řetěz
  // pravidelnosti se používá JEN u jedoosnového systému (tam podpora nic
  // nefiltruje) — jinak zahazoval skutečné čáry, protože takty v sazbě nejsou
  // stejně široké (naměřeno str. 6: čáry 198/292/391/485, řetěz vzal jen dvě).
  let inner = rest;
  if (sysCount === 1) {
    const ch = barChain(inner, spacePx);
    if (ch.length >= 2) inner = ch;
  }
  const chain = inner;
  const linesPt = chain.map(x => x / pxPerPt);
  const bars = linesPt.length;                    // čísel = takty 2..N
  const dbg = {
    staff: [+near.y0.toFixed(1), +near.y1.toFixed(1)], space: +(spacePx / pxPerPt).toFixed(2),
    staffLeft: +(staffLeft / pxPerPt).toFixed(1), staffRight: +(staffRight / pxPerPt).toFixed(1),
    system: [+(real[sysA][0] / pxPerPt).toFixed(1), +(real[sysB][real[sysB].length - 1] / pxPerPt).toFixed(1)],
    sysCount, need, staffs: sysCount,
    all: real.map(g => [+(g[0] / pxPerPt).toFixed(1), +(g[g.length - 1] / pxPerPt).toFixed(1), g.length]),
  };
  const diag = { thr, osnov: real.length, system: sysCount, strokes: all.length,
                 cov: covUsed, cands: candsX.length, chain: chain.length, krok,
                 staffRight: +(staffRight / pxPerPt).toFixed(1),
                 space: +(spacePx / pxPerPt).toFixed(2),
                 closingDens: rest.length
                   ? +(musicDensity(rest[rest.length - 1] + spacePx, staffRight)).toFixed(3) : null,
                 tail: rest.length ? +(staffRight - rest[rest.length - 1]).toFixed(1) : null,
                 barP: +barP.toFixed(1), hole: holeDbg };
  const cands = clusters.map(c => [+(c.xs.reduce((n, p) => n + p.x, 0) / c.xs.length / pxPerPt).toFixed(1),
                                   new Set(c.xs.map(p => p.i)).size]);

  if (!chain.length) {
    return { lines: [], bars: 0, krok, staves: sysCount, top, ok: false, opening, closing,
             sysTop: offY + real[sysA][0] / pxPerPt, sysBot: offY + real[sysB][real[sysB].length - 1] / pxPerPt,
             spacePt: spacePx / pxPerPt,
             reason: 'v tomhle systému jsem nenašel pravidelný sled taktových čar',
             diag, dbg, cands };
  }
  // „Krok“ je jen kontrola: appka takty spočítá sama a případný rozdíl ukáže.
  const krokBars = krok >= 2 ? krok - 1 : null;
  return { lines: linesPt, bars, krok, krokBars, staves: sysCount, top, ok: true, thr,
           sysTop: offY + real[sysA][0] / pxPerPt, sysBot: offY + real[sysB][real[sysB].length - 1] / pxPerPt,
           spacePt: spacePx / pxPerPt,
           opening, closing, diag, dbg, mode: 'systém', cands,
           openingPt: opening == null ? null : offY * 0 + opening / pxPerPt,
           staffLeftPt: staffLeft / pxPerPt };
}
