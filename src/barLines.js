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

/** Šedá maska (inkoust = 1) + práh.
 *  ⚠️ Práh se počítá po PÁSECH (64 px), ne jeden pro celý obrázek: sken je
 *  na stránce nestejně osvětlený a jeden globální Otsu na celé stránce
 *  ztratil světlé osnovy v dolní polovině (naměřeno str. 2: 10 osnov místo 15,
 *  chyběly právě ty ve spodní části) — a ztracená osnova rozbije hranice
 *  systému. V pásu (jeden systém) je pásová hodnota skoro totéž co globální,
 *  takže se chování `detectBarlines` nemění. Práh pro LINKY OSNOV je navíc
 *  výš než Otsu (Otsu + 35, max 235) — linky jsou na skenu šedé a při nízkém
 *  prahu se rozpadají (naměřeno 0,46–0,64 místo > 0,85). */
function buildMask(cv) {
  const w = cv.width, h = cv.height;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;
  const gray = new Uint8Array(w * h);
  for (let i = 0, p = 0; p < w * h; p++, i += 4) {
    gray[p] = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
  }
  const BLOCK = 64;
  const mask = new Uint8Array(w * h);
  // DRUHÁ maska — jen VELMI tmavý inkoust sazby (tahy, závorky), ne šum skenu.
  // Slouží k jedinému účelu: rozhodnout, jestli mezi dvěma osnovami něco
  // PROCHÁZÍ (závorka systému, taktová čára přes mezeru) — viz `gapConn`.
  // Šedé skeny mají v mezerách stíny a vazbu, které `mask` (Otsu + 35) bere
  // jako inkoust, takže se podle ní hranice systému poznat nedá.
  const dark = new Uint8Array(w * h);
  // Počty inkoustu ve sloupcích — slouží k poznání sloupců přes celý obraz
  // (vazba, stín u okraje skenu). Ty se nesmí počítat jako „linka osnovy“.

  let thrGlobal = 0;
  for (let y0 = 0; y0 < h; y0 += BLOCK) {
    const y1 = Math.min(h, y0 + BLOCK);
    const hist = new Uint32Array(256);
    for (let y = y0; y < y1; y++) {
      const off = y * w;
      for (let x = 0; x < w; x++) hist[gray[off + x] | 0]++;
    }
    const thr = Math.min(235, otsu(hist, (y1 - y0) * w) + 35);
    // Práh pro „tmavý inkoust“: pod Otsuem, aby šum papíru a stíny vypadly
    // (naměřeno: závorka systému má < 100, skenový stín u okraje 150–200).
    const dthr = Math.max(70, Math.min(150, thr - 45));
    if (!thrGlobal) thrGlobal = thr;
    for (let y = y0; y < y1; y++) {
      const off = y * w;
      for (let x = 0; x < w; x++) {
        const g = gray[off + x];
        if (g < thr) mask[off + x] = 1;
        if (g < dthr) dark[off + x] = 1;
      }
    }
  }
  const colInk = new Uint32Array(w);
  const darkColInk = new Uint32Array(w);
  for (let y = 0; y < h; y++) {
    const off = y * w;
    for (let x = 0; x < w; x++) {
      if (mask[off + x]) colInk[x]++;
      if (dark[off + x]) darkColInk[x]++;
    }
  }
  return { w, h, mask, dark, darkColInk, thr: thrGlobal, colInk };
}

/** Vytáhne ze skupiny řádků PRAVIDELNOU OSNOVU. Na horším skenu (nižší
 *  rozlišení, text písně, dynamika) se k pěti linkám přidá šestý až osmý řádek
 *  a skupina pak neprojde testem rovnoměrnosti → osnova ZMIZNE a systém se
 *  rozpadne (naměřeno Mozart str. 7 při 4,9 px/bod: osnovy na 443–466 a
 *  721–747 vypadly a stránka se očíslovala jako 5 systémů místo 4).
 *  Řešení: najdi nejdelší řetěz řádků s krokem = medián mezery (< 8 b) a ten
 *  ber jako osnovu. Text/dynamika stojí mimo krok, takže do řetězu nesedne. */
function repairStaff(g, pxPerPt, sp) {
  if (g.length <= 5) return g;
  const step = sp > 0 ? sp : 4 * pxPerPt;
  let best = [];
  for (let s = 0; s < g.length; s++) {
    const o = g[s];
    const pts = [o];
    for (let k = 1; k < 6; k++) {
      const want = o + k * step;
      let hit = null, bd = Infinity;
      for (const v of g) {
        const d = Math.abs(v - want);
        if (d < bd) { bd = d; hit = v; }
      }
      if (hit == null || bd > 0.45 * step) break;
      pts.push(hit);
    }
    // Řetěz musí být ROVNOMĚRNÝ, jinak je to náhodná posloupnost řádků
    // (naměřeno Mozart str. 3: „osnova“ 307,7/311,6/313,4/319,8/321,6/324,9
    // s mezerami 3,9/1,8/6,4/1,8/3,3 — rozhodně to není pět linek osnovy).
    const cg = [];
    for (let i = 1; i < pts.length; i++) cg.push(pts[i] - pts[i - 1]);
    const mn = Math.min(...cg), mx = Math.max(...cg);
    const regular = cg.length ? mx <= 1.5 * mn : false;
    if (regular && pts.length > best.length) best = pts;
  }
  return best.length >= 4 ? best : g;
}

/** Osnovy = skupiny 4–6 ROVNOMĚRNÝCH řádků s dlouhým vodorovným tahem.
 *  Nerovnoměrné skupiny (text písně, podtržení, obloučky) se zahazují — dřív
 *  z nich vznikaly falešné „osnovy“ a z těch nesmyslný počet osnov
 *  (naměřeno `staves: 9`). Tahle funkce je JEDINÉ místo, kde se osnovy hledají,
 *  aby se stránka a jeden systém nemohly rozejít. */
function staffGroups(mask, w, h, pxPerPt) {
  const longest = (off) => longestRun(mask, off, w);
  // ⚠️ Řádek linky osnovy se na vybledlém skenu nedetekuje, když je linka
  // PŘERUŠENÁ (naměřeno Cherubini str. 9: podíl inkoustu 0,24–0,39 a nejdelší
  // tah jen 21–25 % šířky, takže obě původní podmínky selhaly a z celého
  // systému zbyly 2 osnovy). Druhá, mírnější podmínka bere řádky s dlouhým
  // tahem (>= 16 % šířky) i při menším podílu inkoustu — text písně ani
  // trámce takhle dlouhý SOUVISLÝ tah nemají, takže falešné linky nepřidá.
  const rowFrac = new Float32Array(h);
  const rowLong = new Float32Array(h);
  const blobStaffs = [];
  for (let y = 0; y < h; y++) {
    const off = y * w;
    let ink = 0;
    for (let x = 0; x < w; x++) ink += mask[off + x];
    rowFrac[y] = ink / w;
    rowLong[y] = longest(off) / w;
  }
  const centres = [];
  let runStart = -1;
  for (let y = 0; y <= h; y++) {
    let on = false;
    if (y < h) {
      on = rowFrac[y] >= 0.30 || rowLong[y] >= 0.45
        || (rowLong[y] >= 0.16 && rowFrac[y] >= 0.15);
    }
    if (on && runStart < 0) runStart = y;
    if (!on && runStart >= 0) {
      const bh = (y - runStart) / pxPerPt;      // výška pásu v bodech
      // ⚠️ HUSTÝ KLAVÍRNÍ DOPROVOD: celá osnova je jeden tmavý pás (noty,
      // trámce a linky splývají), takže se z jejích pěti linek stane JEDNO
      // centrum a osnova zmizí (naměřeno Cherubini tištěná str. 9: ze šesti
      // osnov systému se našly čtyři). Pás vysoký jako osnova (10–22 b) se
      // proto bere jako CELÁ osnova — vyrobí se pět pseudo-linek, aby na něj
      // seděly okraje, spojnice i měření čar.
      if (bh >= 10 && bh <= 22) {
        const top = runStart, bot = y - 1;
        blobStaffs.push([top, Math.round(top + (bot - top) * 0.25), Math.round((top + bot) / 2),
                         Math.round(top + (bot - top) * 0.75), bot]);
      } else {
        centres.push(Math.round((runStart + y - 1) / 2));
      }
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
  // ⚠️ Linka osnovy se na skenu občas detekuje DVAKRÁT (dvojitý tah / přerušená
  // linka) a z osnovy se pak stane „skupina o 8–9 linkách“, kterou filtr 4–8
  // zahodí → osnova ZMIZÍ a rozpadne se hranice systému (naměřeno str. 2:
  // 5 osnov ztraceno a systémům chyběl kus). Slijeme proto centra blíž než
  // 0,55 typické mezery mezi linkami — ta se MĚŘÍ z dat, ne z pxPerPt.
  // ⚠️ Do měření meziprostoru NESMÍ vstoupit zdvojené linky samotné: na
  // vybledlém skenu (Mozart str. 3) dá každá linka dva řádky 1,5 b od sebe,
  // takže medián VŠECH mezer vyjde 1,5 b, `mergeSep` 0,9 b a zdvojení se
  // neslijí → osnova má 9–10 „linek“ a rozpadne se na dvě. Proto se berou jen
  // mezery, které odpovídají skutečnému rozestupu linek osnovy (2,5–6 b).
  const ds = [];
  for (let i = 1; i < cs.length; i++) {
    const d = cs[i] - cs[i - 1];
    if (d >= 2.5 * pxPerPt && d <= 6 * pxPerPt) ds.push(d);
  }
  ds.sort((a, b) => a - b);
  const lineSpace = ds.length ? ds[Math.floor(ds.length / 2)] : 3.8 * pxPerPt;
  const mergeSep = Math.max(2, 0.45 * lineSpace);
  const cs2 = [];
  for (const c of cs) {
    if (cs2.length && c - cs2[cs2.length - 1] <= mergeSep) {
      cs2[cs2.length - 1] = Math.round((cs2[cs2.length - 1] + c) / 2);
    } else cs2.push(c);
  }
  const groups = [];
  let cur = [];
  for (const c of cs2) {
    if (cur.length && c - cur[cur.length - 1] < gapMax) cur.push(c);
    else { if (cur.length) groups.push(cur); cur = [c]; }
  }
  if (cur.length) groups.push(cur);
  // Skupina delší než 6 linek = dvě osnovy slepené (na skenu mezi ně občas
  // spadne řádek textu nebo trylek). Rozdělí se v NEJVĚTŠÍ mezeře, takže
  // z jedné „osnovy“ o 7 linkách vzniknou dvě — jinak z ní vyjde systém
  // s nesmyslným počtem osnov a hranice systému se posunou.
  const splitBig = (g) => {
    if (g.length <= 6) return [g];
    const gaps = [];
    for (let i = 1; i < g.length; i++) gaps.push(g[i] - g[i - 1]);
    const med = gaps.slice().sort((a, b) => a - b)[Math.floor(gaps.length / 2)];
    let cut = 0, cutAt = -1;
    for (let i = 0; i < gaps.length; i++) {
      if (gaps[i] > med * 1.5 && gaps[i] > cut) { cut = gaps[i]; cutAt = i; }
    }
    if (cutAt < 0) return [g];
    return splitBig(g.slice(0, cutAt + 1)).concat(splitBig(g.slice(cutAt + 1)));
  };
  const groupsSplit = [];
  const preOf = new Map();
  for (const g of groups) {
    const rp = repairStaff(g, pxPerPt, lineSpace);
    for (const part of splitBig(rp)) { preOf.set(part, g); groupsSplit.push(part); }
  }
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
  const dbg = [];
  const real = groupsSplit.filter((g) => {
    const why = (r) => {
      dbg.push([+(g[0] / pxPerPt).toFixed(1), +(g[g.length - 1] / pxPerPt).toFixed(1),
                g.length, r, g.map((v) => +(v / pxPerPt).toFixed(1)),
                (preOf.get(g) || []).map((v) => +(v / pxPerPt).toFixed(1))]);
      return r === 'ok';
    };
    if (g.length < 4 || g.length > 8) return why('linek ' + g.length);
    const gaps = [];
    for (let i = 1; i < g.length; i++) gaps.push(g[i] - g[i - 1]);
    gaps.sort((a, b) => a - b);
    const med = gaps[Math.floor(gaps.length / 2)];
    if (med < 2) return why('krok ' + med.toFixed(1));
    let same = 0;
    for (const gp of gaps) if (gp >= 0.7 * med && gp <= 1.4 * med) same++;
    if (same < g.length - 3) return why('nepravidelné ' + same + '/' + gaps.length);
    // Čtyřlinková „osnova“ je skoro vždy řádek TEXTU (patička, tiráž), který
    // má linky nestejně daleko. Skutečná osnova se 4 linkami (sken ztratil
    // jednu) drží rozestup těsně, takže se pozná podle rovnoměrnosti.
    // ⚠️ Sken ale umí poslední linku posunout o pár desetin bodu (naměřeno
    // Mozart str. 17: mezery 6,3 / 6,4 / 4,4 b = 22 px vs. mez 0,7 × 31,5 =
    // 22,05 px) — pravidlo `same < 3` pak zahodí SKUTEČNOU osnovu a systém
    // ztratí jednu osnovu. Rozhoduje proto POMĚR mezer, ne absolutní mez.
    if (g.length === 4) {
      const mn = gaps[0], mx = gaps[gaps.length - 1];
      if (same < 3 && !(mn > 0 && mx <= 1.75 * mn)) return why('4 linky nepravidelné');
    }
    // ⚠️ Rozestup linek jedné osnovy je ~4 b. Skupina s rozestupem 20+ b není
    // osnova, ale SLEPENÉ CELÉ OSNOVY: v hustém klavírním doprovodu je celá
    // osnova jeden tmavý pás, takže se z jejích pěti linek stane jedno
    // „centrum“ a z pěti osnov jedna falešná „osnova“ o pěti linkách
    // (naměřeno Cherubini tištěná str. 9: ze 6 osnov zbyly 4). Zahodit.
    if (med > 9 * pxPerPt) return why('krok ' + (med / pxPerPt).toFixed(1) + ' b');
    if (vStrokes(g) < 2) return why('bez svislic');
    return why('ok');
  });
  // Osnovy z hustých pásů (viz `blobStaffs`) se přidají mezi „normální“ osnovy;
  // projít musí stejným testem svislic (text žádné nemá).
  for (const b of blobStaffs) {
    const yT = b[0], yB = b[b.length - 1], bh = Math.max(1, yB - yT);
    let n = 0, run = 0;
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let yy = yT; yy <= yB; yy++) ink += mask[yy * w + x];
      if (ink / bh >= 0.9) { run++; } else { if (run >= 1) n++; run = 0; }
    }
    if (run) n++;
    if (n >= 2) real.push(b);
  }
  real.sort((a, b) => a[0] - b[0]);
  // DVA ÚLOMKY JEDNÉ OSNOVY. Když se z osnovy ztratí linka (sken) nebo ji
  // `repairStaff` uřízne, vzniknou dvě „osnovy“ 3–5 b od sebe a systém pak
  // dostane o osnovu víc (naměřeno Mozart str. 3: 453,2–463,8 + 468,5–476,7).
  // Mezera mezi DVĚMA osnovami je vždy větší (naměřeno 13–33 b), takže se
  // úlomky smí spojit, jen když jsou blíž než 6 b.
  const mergedReal = [];
  for (const g of real) {
    const prev = mergedReal[mergedReal.length - 1];
    if (prev && g[0] - prev[prev.length - 1] < 6 * pxPerPt) {
      prev.push(...g);
      prev.sort((a, b) => a - b);
    } else mergedReal.push(g.slice());
  }
  return { real: mergedReal, lines: cs.length, dbg,
           raw: groups.map((g) => [g[0], g[g.length - 1], g.length]) };
}

/** Levý a pravý konec OSNOVY: sloupec, kde je nakreslená VĚTŠINA linek osnovy
 *  (4 z 5 — sken občas jednu ztratí). Slouží pro okraje a pro měření hustoty;
 *  úvodní čára systému se z něj NEODVOZUJE (okraj může být posunutý textem
 *  nebo závorkou na kraji sazby — naměřeno str. 2/1. systém: 15 b místo 136 b).
 */
function staffSpan(g, mask, w) {
  const need = Math.max(2, g.length - 1);
  let first = -1, last = -1;
  for (let x = 0; x < w; x++) {
    let c = 0;
    for (const yy of g) if (mask[Math.round(yy) * w + x]) c++;
    if (c >= need) { if (first < 0) first = x; last = x; }
  }
  return [first < 0 ? 0 : first, last < 0 ? w - 1 : last];
}

/** Kolik svislých sloupců v mezeře mezi dvěma osnovami je plných (spojnice). */
function gapInk(up, lo, mask, w, colInk, h) {
  const y0 = up[up.length - 1] + 2, y1 = lo[0] - 2;
  if (y1 <= y0) return 0;
  const [L, R] = staffSpan(up, mask, w);
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
}

/** Hustota inkoustu v mezeře mezi dvěma osnovami (podíl tmavých pixelů).
 *  Rozhoduje u mezery, která je velká jako hranice systému, ale leží UVNITŘ
 *  systému: mezi sborem a klavírem je text písně a dynamika (naměřeno 8–17 %
 *  inkoustu), kdežto mezi dvěma systémy je prázdno (2–5 %). Prahy velikosti
 *  to nerozliší — naměřeno Mozart str. 5: mezera sbor→klavír 34,7 b, skutečná
 *  hranice systému 37,2 b (rozdíl 2,5 b). */
function gapDensity(up, lo, mask, w, h, colInk) {
  const y0 = up[up.length - 1] + 2, y1 = lo[0] - 2;
  if (y1 <= y0) return 0;
  const [L, R] = staffSpan(up, mask, w);
  const sp = Math.max(2, (up[up.length - 1] - up[0]) / 4);
  const x0 = Math.max(0, Math.round(L + sp));
  const x1 = Math.min(w - 1, Math.round(R - sp));
  if (x1 <= x0) return 0;
  let ink = 0, n = 0;
  for (let y = y0; y <= y1; y++) {
    const off = y * w;
    for (let x = x0; x <= x1; x++) {
      // sloupce přes celou stránku (vazba, stín) se nepočítají
      if (colInk[x] > 0.5 * h) continue;
      ink += mask[off + x];
      n++;
    }
  }
  return n ? ink / n : 0;
}

/** Kolik SLOUPCŮ prochází mezerou mezi dvěma osnovami v masce TMAVÉHO inkoustu.
 *  To je jediné spolehlivé vodítko, jestli dvě osnovy patří do JEDNOHO systému:
 *  závorka systému (a taktové čáry vedené přes mezeru) jsou černé a procházejí
 *  celou mezerou, kdežto mezi DVĚMA systémy je prázdno. Šedé skeny mají v
 *  mezerách stíny, vazbu a linku u okraje — ty `mask` (Otsu + 35) bere jako
 *  inkoust, takže podle ní se hranice systému poznat nedala (naměřeno Mozart
 *  str. 17: hranice systému „s inkoustem 19 a 27 sloupců“).
 *  Sloupce přes celou stránku (stín/vazba) se vynechávají — jinak by „prázdno“
 *  bylo plné inkoustu. */
function gapConn(up, lo, dark, artCol, w, xLo, xHi, outX, deepFrom) {
  const y0 = up[up.length - 1] + 2, y1 = lo[0] - 2;
  if (y1 <= y0) return 0;
  const need = y1 - y0 + 1;
  const a = Math.max(0, Math.round(Number.isFinite(xLo) ? xLo : 0));
  const b = Math.min(w - 1, Math.round(Number.isFinite(xHi) ? xHi : w - 1));
  let n = 0, deep = 0;
  for (let x = a; x <= b; x++) {
    if (artCol[x]) continue;                     // stín/vazba přes celou stránku
    let ink = 0;
    for (let y = y0; y <= y1; y++) ink += dark[y * w + x];
    if (ink / need >= 0.8) {
      n++;
      // „Hluboké" sloupce = dál od levého okraje osnov. Levá závorka systému
      // prochází KAŽDOU mezerou (i mezi systémy), takže se do spojnice
      // nepočítá; taktové čáry uvnitř sazby ano.
      if (Number.isFinite(deepFrom) && x >= deepFrom) deep++;
      if (outX && outX.length < 12) outX.push(x);
    }
  }
  if (outX) outX.deep = deep;
  return n;
}

/** Sloupce, které jsou tmavé I V OKRAJÍCH stránky (nad prvním a pod posledním
 *  systémem) = skenový stín, vazba, okraj předlohy. Závorka systému tam NENÍ
 *  (existuje jen uvnitř systému), takže tohle je bezpečné vodítko, jak artefakt
 *  odlišit od skutečné spojnice — na rozdíl od „sloupec tmavý přes celou
 *  stránku“ (závorky všech systémů leží ve stejném x a jejich inkoust se
 *  nasčítá, naměřeno Cherubini str. 3: 0,71 výšky stránky). */
function artifactCols(real, dark, w, h) {
  const art = new Uint8Array(w);
  const firstTop = real[0][0];
  const lastBot = real[real.length - 1][real[real.length - 1].length - 1];
  const m = Math.max(6, Math.round(0.01 * h));
  const rows = [];
  for (let y = 0; y < h; y++) {
    if (y < firstTop - m || y > lastBot + m) rows.push(y);
  }
  if (rows.length < 8) return art;
  const need = Math.ceil(0.5 * rows.length);
  for (let x = 0; x < w; x++) {
    let c = 0;
    for (const y of rows) { if (dark[y * w + x]) { c++; if (c >= need) { art[x] = 1; break; } } }
  }
  return art;
}

/** Rozdělí osnovy do SYSTÉMŮ. Jedno místo pravdy pro celou stránku i pro
 *  klepnutí do jednoho systému — dřív si to každé volání počítalo samo z jiného
 *  výřezu, takže pásky vycházely jinak a jeden systém se očísloval dvakrát.
 *  SYSTÉM = souvislý pás osnov. Rozhoduje MEZERA + SPOJNICE:
 *  * mezera větší než 1,5 × NEJMENŠÍ typická mezera (25. percentil) a BEZ
 *    spojnice = hranice systému; na skenu Carus jsou uvnitř systému mezery
 *    18–38 b, mezi systémy 37–45 b, takže samotná velikost nestačí a rozhoduje
 *    spojnice (závorka / taktová čára přes mezeru),
 *  * mezera > 1,4 × typická, kterou NEPROCHÁZÍ ani jeden tmavý sloupec, je
 *    hranice taky — tohle zachrání sazbu, kde je v mezerách text/dynamika a
 *    staré pravidlo `ink < 1` je odmítlo (naměřeno Mozart str. 17: hranice
 *    48,4 b s „inkoustem“ 19).
 *  * extrémní mezera (> 3 × typická) je hranice vždy — tam spojnice nepatří.
 *  ⚠️ Základ se bere z 25. percentilu, ne z mediánu: v pásu, kde je jen jeden
 *  systém, převažují velké mezery sbor→klavír a medián je nad hranicí systému
 *  (naměřeno: 11 osnov slitých do jednoho systému na str. 8). */
function systemGroups(real, mask, w, colInk, h, dark, darkColInk) {
  const artCol = dark ? artifactCols(real, dark, w, h) : null;
  // Rozsah x, ve kterém se hledají SPOJNICE. Vnější kousek se vynechává:
  // na okrajích skenu je stín a vazba, které procházejí celou stránkou
  // (naměřeno Mozart str. 17: tmavý pruh na x≈565–568 a 9–13 b prochází
  // i mezerami MEZI systémy). Závorku systému to nechá být — ta stojí
  // u levého okraje osnov (Cherubini: x≈16 b), tedy až za touhle hranicí.
  const medOfA = (arr) => { const s = arr.slice().sort((x, y) => x - y); return s[Math.floor((s.length - 1) / 2)]; };
  const lefts = [], rights = [], heights = [];
  for (const g of real) {
    const [L, R] = staffSpan(g, mask, w);
    lefts.push(L); rights.push(R); heights.push(g[g.length - 1] - g[0]);
  }
  const L0 = lefts.length ? medOfA(lefts) : 0;
  const R0 = rights.length ? medOfA(rights) : w - 1;
  const sp0 = Math.max(2, (heights.length ? medOfA(heights) : 16) / 4);
  const xLo = L0 + 0.75 * sp0;
  const xHi = R0 - 3 * sp0;
  const gaps = [];
  // Hranice „hluboko uvnitř" mezery: levá závorka systému stojí u okraje osnov
  // (naměřeno Cherubini: x≈40 b při okraji 36 b), kdežto taktové čáry uvnitř
  // sazby jsou dál. Do spojnice se proto počítají jen sloupce odsud dál.
  const xDeep = L0 + 3 * sp0;
  for (let i = 0; i + 1 < real.length; i++) {
    const connX = [];
    gaps.push({ gap: real[i + 1][0] - real[i][real[i].length - 1],
                ink: gapInk(real[i], real[i + 1], mask, w, colInk, h),
                conn: dark ? gapConn(real[i], real[i + 1], dark, artCol, w, xLo, xHi, connX, xDeep) : null,
                connX, connDeep: connX.deep || 0,
                dens: gapDensity(real[i], real[i + 1], mask, w, h, colInk) });
  }
  const sorted = gaps.map((q) => q.gap).sort((a, b) => a - b);
  const gapBase = sorted.length ? sorted[Math.floor((sorted.length - 1) * 0.25)] : 0;
  // Hranice systému: obrovská mezera, nebo mezera nad 1,5× typickou bez spojnice.
  // ⚠️ ROZHODUJE SPOJNICE, ne velikost mezery. V této sazbě vede sazba
  // taktové čáry SPOJITĚ jen v jedné mezeře každého systému (mezi klavírními
  // osnovami — naměřeno `conn` 11–29, `ink` 9–25), kdežto mezerou MEZI systémy
  // neprochází nic (`conn === 0`). Dřív se `conn === 0` uznávalo jako hranice
  // jen při mezeře > 1,25× základu, takže se dva systémy slily, když byla mezera
  // 1,06× (naměřeno tištěná 14, PDF 15: 20,0 b při základu 18,8 b) a na tištěné
  // 43 (PDF 44) se slily VŠECHNY tři systémy do jednoho o 18 osnovách — a z toho
  // pak vyšel jediný „velký takt“ (naměřeno bars=1).
  // Proto nové pravidlo: SILNÁ spojnice (`conn >= 8`) označuje KONEC systému —
  // mezera hned za ní, kterou už nic neprochází, je hranice. Velikost mezer
  // tohle nerozliší: na str. 41 (PDF 48) je mezera uvnitř systému 24,0 b
  // a skutečná hranice 22,0 b.
  // Hustota inkoustu v mezeře zůstává jen v diagnostice — text písně je i mezi
  // skutečnými systémy (naměřeno Cherubini tištěná str. 5).
  const strongConn = Math.max(8, 0.45 * Math.max(0, ...gaps.map((q) => q.conn || 0)));
  const sizeBoundary = (q, i) => gapBase > 0
    && (q.gap > 3 * gapBase
        // ⚠️ „Prázdná mezera“ musí být prázdná i ve TMAVÉM inkoustu (`conn`).
        // Mezera sbor→klavír je velká (naměřeno 26–28 b = 1,5–1,6× základu)
        // a `ink` je v ní 0 (text písně je jinde), ale prochází jí závorka
        // sazby — `conn` 4. Bez podmínky `conn === 0` se systém rozpůlil na
        // 4 + 2 osnovy a klavír se očísloval jako samostatný systém
        // (naměřeno tištěná 12 = PDF 13, 31, 32, 54, 55).
        // ⚠️ Mezera sbor→klavír je taky „velká a prázdná“ (naměřeno 26–28 b =
        // 1,5–1,6× základu, `ink` 0), ale prochází jí závorka sazby (`conn` 4)
        // a HNED POD NÍ vede spojnice mezi klavírními osnovami (`conn` 11–29).
        // To je podpis klavírní dvojice, ne hranice systému — bez téhle
        // pojistky se systém půlil na 4 + 2 a klavír se čísloval zvlášť
        // (naměřeno tištěná 12 = PDF 13, 31, 32, 55).
        || (q.gap > 1.5 * gapBase && q.ink < 1 && (q.conn === 0
            // Podpis klavírní dvojice: mezera sbor→klavír (conn 4–5), pod ní
            // SILNÁ spojnice mezi klavírními osnovami a teprve pod tou PRÁZDNO
            // (skutečná hranice systému). V Mozartovi je pod velkou mezerou
            // taky silná spojnice, ale pod ní další spojnice, ne prázdno —
            // tam hranice zůstává (jinak se dva systémy slily, naměřeno 6+6→12).
            || !((i + 1 < gaps.length && (gaps[i + 1].conn || 0) >= strongConn)
                 && i + 2 < gaps.length && (gaps[i + 2].conn || 0) === 0)))
        || (q.conn === 0 && q.gap > 1.25 * gapBase)
        || (q.conn === 0 && i > 0 && (gaps[i - 1].conn || 0) >= strongConn));
  const bounds = [];
  let a = 0;
  for (let i = 0; i < real.length; i++) {
    if (i + 1 < real.length && !sizeBoundary(gaps[i], i)) continue;
    bounds.push([a, i]);
    a = i + 1;
  }
  // KLAVÍRNÍ DVOJICE PATŘÍ K SYSTÉMU NAD SEBOU. Sbor + klavír má mezi sebou
  // mezeru bez spojnice, velkou jako hranice systému (naměřeno Mozart str. 5:
  // 34,7 b uvnitř systému vs 37,2 b mezi systémy), takže podle velikosti se to
  // oddělit nedá. Rozhoduje tvar: blok o DVOU osnovách, pod nímž ani nad ním
  // není větší mezera, je klavír systému výš — a klavírní dvojice je v systému
  // vždy jen jedna.
  const merged = [];
  for (let k = 0; k < bounds.length; k++) {
    const [b0, b1] = bounds[k];
    const prev = merged[merged.length - 1];
    const belowCount = b1 - b0 + 1;
    const aboveCount = prev ? prev[1] - prev[0] + 1 : 0;
    // KLAVÍRNÍ DVOJICE se pozná i TÍM, že její vnitřní mezerou procházejí
    // taktové čáry (skenované noty je vedou přes celou dvojici), kdežto mezi
    // systémy neprochází nic. Bez toho se na stránce s jedním vokálním hlasem
    // (Cherubini tištěná 19: systémy 4/4/3/3 osnov) klavír odtrhl, protože
    // horní blok nemá 3 osnovy — z jednoho systému byly dva a jedoosnový
    // „systém" si navíc spletl nožičku půlové noty s taktovou čarou.
    const pairJoin = belowCount === 2 && gaps[b0] && gaps[b0].connDeep >= 3;
    if (prev && belowCount === 2 && (aboveCount >= 3 || pairJoin)) {
      const gap = real[b0][0] - real[prev[1]][real[prev[1]].length - 1];
      const nextGap = k + 1 < bounds.length
        ? real[bounds[k + 1][0]][0] - real[b1][real[b1].length - 1] : Infinity;
      if (gapBase > 0 && gap <= 2.4 * gapBase && gap < 1.15 * nextGap) {
        prev[1] = b1;
        continue;
      }
    }
    merged.push([b0, b1]);
  }
  return { gaps, gapBase, bounds: merged };
}

/**
 * Najde VŠECHNY systémy stránky naráz. Osnovy i hranice systémů se počítají
 * jednou pro celou stránku (proto se systémy nemůžou sejít dvakrát ani slit dva
 * dohromady), každý systém se pak změří stejným `detectBarlines` jako při
 * klepnutí — jen na vlastním výřezu stránky.
 * @returns {{ok:boolean, systems:Array, staves:number, reason?:string}}
 */
export function detectPageSystems(cv, pxPerPt, opt = {}) {
  const krok = Math.max(0, Math.min(64, Math.round(opt.krok || 0)));
  const { w, h, mask, colInk, dark, darkColInk } = buildMask(cv);
  const staff = staffGroups(mask, w, h, pxPerPt);
  const real = staff.real;
  if (!real.length) {
    return { ok: false, systems: [], staves: 0,
             reason: 'nenašel jsem linky osnov (' + staff.lines + ' linek)' };
  }
  const grp = systemGroups(real, mask, w, colInk, h, dark, darkColInk);
  const topPxOf = (i) => real[i][0];
  const botPxOf = (i) => real[i][real[i].length - 1];
  const systems = [];
  for (let k = 0; k < grp.bounds.length; k++) {
    const [a, b] = grp.bounds[k];
    const topPx = topPxOf(a), botPx = botPxOf(b);
    // Výřez sahá do POLOVINY mezery k sousednímu systému — víc by přitáhlo cizí
    // osnovy a seskupení uvnitř výřezu by je slilo do tohohle systému.
    const prevBot = k > 0 ? botPxOf(grp.bounds[k - 1][1]) : -Infinity;
    const nextTop = k + 1 < grp.bounds.length ? topPxOf(grp.bounds[k + 1][0]) : Infinity;
    const pad = 14 * pxPerPt;
    const y0 = Math.max(0, Math.floor(Math.max(topPx - pad, (prevBot + topPx) / 2)));
    const y1 = Math.min(h, Math.ceil(Math.min(botPx + pad, (botPx + nextTop) / 2)));
    const bh = Math.max(4, y1 - y0);
    const band = document.createElement('canvas');
    band.width = w;
    band.height = bh;
    band.getContext('2d').drawImage(cv, 0, y0, w, bh, 0, 0, w, bh);
    const offY = y0 / pxPerPt;
    const midPt = (topPx + botPx) / 2 / pxPerPt;
    // ⚠️ `ypt` se předává v bodech CELÉ stránky a `detectBarlines` od něj odečte
    // `offsetY` — proto tady NEPŘIČÍTÁME `offY` (dřív se přičetlo a klepnutí
    // uvnitř výřezu padlo mimo něj → vybrala se špatná osnova a z výřezu čtyř
    // taktů vyšlo jedenáct čar).
    const det = detectBarlines(band, pxPerPt, {
      krok, ypt: midPt, offsetY: offY, numXs: opt.numXs,
      staffRows: real.slice(a, b + 1).map((g) => g.map((v) => v - y0)),
      rows: [Math.round(topPx) - y0, Math.round(botPx) - y0],
    });
    // Kontrola, že výřez opravdu obsahuje PRÁVĚ tenhle systém: když se hrany
    // rozejdou, výřez něco uřízl a detekci nesmíme věřit.
    const spanOk = Number.isFinite(det.sysTop) && Number.isFinite(det.sysBot)
      && Math.abs(det.sysTop - topPx / pxPerPt) <= 3
      && Math.abs(det.sysBot - botPx / pxPerPt) <= 3;
    systems.push({ ...det, spanOk, sysA: a, sysB: b, stavesFound: det.staves,
                   stavesExpected: b - a + 1 });
  }
  const inkTop = [];
  for (let x = 0; x < w; x++) if (colInk[x] > 0.25 * h) inkTop.push([Math.round(x / pxPerPt), colInk[x], h]);
  return { ok: systems.some((d) => d.ok), systems, staves: real.length, tallCols: inkTop.slice(0, 12),
           staffDbg: (staff.dbg || []).map((r) => [r[0], r[1], r[2], r[3], r[4], r[5]]),
           rawGroupsPt: staff.raw.map((g) => [+(g[0] / pxPerPt).toFixed(1),
                                             +(g[1] / pxPerPt).toFixed(1), g[2]]),
           gapBasePt: +(grp.gapBase / pxPerPt).toFixed(1),
           gapsPt: grp.gaps.map((q) => [+(q.gap / pxPerPt).toFixed(1), q.ink, q.conn,
                                        (q.connX || []).map(v => +(v / pxPerPt).toFixed(1))]),
           rowsPt: real.map((g) => [+(g[0] / pxPerPt).toFixed(1),
                                   +(g[g.length - 1] / pxPerPt).toFixed(1), g.length]) };
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
  const krok = Math.max(0, Math.min(64, Math.round(opt.krok || 0)));
  const offY = Number.isFinite(opt.offsetY) ? opt.offsetY : 0;
  // ⚠️ Klepnutí (`ypt`) je v bodech PDF CELÉ STRÁNKY, ale řádky osnov se měří
  // v PÁSU (crop), takže se musí odečíst `offsetY`. Dřív se neodečítalo a výběr
  // osnovy u klepnutí padal o systém vedle (naměřeno: klepnutí na klavír 470 b
  // vybralo systém pod ním).
  const ypt = Number.isFinite(opt.ypt) ? opt.ypt - offY : null;
  const { w, h, mask, thr, colInk, dark, darkColInk } = buildMask(cv);

  // 1) linky osnov = řádky s dlouhým vodorovným tahem, seskupené do osnov.
  // ⚠️ Když osnovy už našel `detectPageSystems` pro CELOU stránku, použijí se
  // TY — výřez pásu má jiné prahy (adaptivní Otsu po blocích) a osnovy v něm
  // vycházejí jinak: naměřeno Cherubini tištěná str. 9, kde pás ztratil dvě
  // osnovy, `sysTop` se posunul o 65 b a celý systém se odmítl jako uříznutý.
  const staff = Array.isArray(opt.staffRows) && opt.staffRows.length
    ? { real: opt.staffRows, lines: opt.staffRows.length }
    : staffGroups(mask, w, h, pxPerPt);
  const real = staff.real;
  if (!real.length) {
    return { lines: [], bars: 0, krok, staves: 0, top: 0, ok: false,
             reason: 'nenašel jsem linky osnov (' + staff.lines + ' linek)' };
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

  // Okraje systému a jeho hranice řeší `systemGroups` (jedno místo pravdy pro
  // celou stránku i pro klepnutí) — tady se jen vybere pás, do kterého se kleplo.
  let sysA = nearIdx, sysB = nearIdx;
  // Když volá celou stránku `detectPageSystems`, hranice systému UŽ ZNÁ (počítaly
  // se jednou pro celou stránku) a předává je v `rows` (px pásu). Uvnitř výřezu
  // se nesmí počítat znovu: pás má jiné statistiky mezer, takže si šestiosnový
  // systém sám rozdělil na 4 + 2 a čísla vyšla doprostřed (naměřeno str. 4).
  if (Array.isArray(opt.rows)) {
    const near0 = (y, useTop) => {
      let best = -1, bd = Infinity;
      for (let i = 0; i < real.length; i++) {
        const v = useTop ? real[i][0] : real[i][real[i].length - 1];
        const d = Math.abs(v - y);
        if (d < bd) { bd = d; best = i; }
      }
      return best;
    };
    sysA = near0(opt.rows[0], true);
    sysB = near0(opt.rows[1], false);
    if (sysA < 0) sysA = nearIdx;
    if (sysB < 0 || sysB < sysA) sysB = sysA;
  } else {
    for (const [a, b] of systemGroups(real, mask, w, colInk, h, dark, darkColInk).bounds) {
      if (nearIdx >= a && nearIdx <= b) { sysA = a; sysB = b; break; }
    }
  }
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
  const gapColsPer = [];
  for (let i = sysA; i < sysB; i++) {
    const y0 = real[i][real[i].length - 1] + 2, y1 = real[i + 1][0] - 2;
    if (y1 <= y0) continue;
    const needRows = y1 - y0 + 1;
    const cols = [];
    for (let x = 0; x < w; x++) {
      let ink = 0;
      for (let y = y0; y <= y1; y++) ink += mask[y * w + x];
      if (ink / needRows >= 0.9) cols.push(x);
    }
    gapColsPer.push(cols);
  }
  const crossesGap = (x) => gapColsPer.some(cols => cols.some(g => Math.abs(g - x) <= xTol));
  const gapSupport = (x) => gapColsPer.reduce((n, cols) =>
    n + (cols.some(g => Math.abs(g - x) <= xTol) ? 1 : 0), 0);
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
    const accepted = [];
    for (const c of clusters) {
      const support = new Set(c.xs.map(p => p.i)).size;
      const x = c.xs.reduce((n, p) => n + p.x, 0) / c.xs.length;
      // Tolerance JEDNA osnova nestačí: na vybledlém skenu vypadne čára i ve
      // DVOU osnovách (naměřeno Cherubini 7osnový systém, čára na 160 b měla
      // podporu 5 — systém pak dostal o takt míň a číslo se přeskočilo).
      // Když kandidát navíc prochází MEZEROU mezi osnovami, je to taktová čára
      // systému, ne nožička (nožička zůstává uvnitř své osnovy) — proto se mu
      // povolí podpora o dvě osnovy nižší.
      if (support >= need
          || (support >= Math.max(2, sysCount - 2) && gapSupport(x) >= 1)) {
        accepted.push({ x, support, gs: gapSupport(x) });
      }
    }
    // ⚠️ NOŽIČKY ZAROVNANÝCH AKORDŮ. Když jsou dvě osnovy (klavír, sbor), mají
    // noty obou rukou/hlasů stejný rytmus, takže sloupce nožiček projdou jako
    // „plné ve všech osnovách“ a 4taktový systém dostane 11 čar (naměřeno
    // str. 2: kandidáti 259/266/312/354/418/474/508 se podporou 2). Skutečná
    // taktová čára SYSTÉMU ale prochází MEZEROU mezi osnovami; nožička ne.
    // Mezera se proto vyžaduje, jakmile ji v systému vůbec něco proťalo (jinak
    // by vypadly skutečné čáry na skenu, kde se spojnice ztratila).
    const useGap = sysCount >= 2 && accepted.filter(a => a.gs >= 1).length >= 3;
    const candsX = [];
    for (const a of accepted) {
      // ⚠️ Podpora ve VŠECH osnovách (`support === sysCount`) přebíjí chybějící
      // spojnici. Nožička noty nikdy neprojde šesti osnovami — ta je vždy jen
      // v jedné. Naměřeno tištěná 30 (PDF 31), 1. systém: skutečná čára na
      // 321,7 b má podporu 6/6, ale mezerou neprochází (v této sazbě je čára
      // v mezerách přerušená) → `gs = 0` → čára vypadla a systém dostal
      // o takt MÍŇ (Jan: „ignoruje poslední takt“).
      const passes = (useGap ? a.gs >= 1 : (sysCount < 2 || a.gs >= 1))
        || (sysCount >= 4 && a.support >= sysCount);
      if (passes) candsX.push(a.x);
    }
    return { clusters, candsX, all };
  };
  // Práh krytí 0,90 (dřív 0,95): na vybledlém skenu má skutečná taktová čára
  // v některé osnově 90–94 % (linka je přerušená), takže při 0,95 vypadla
  // a podpora spadla pod `need` — naměřeno Cherubini tištěná str. 14:
  // 3. systém vrátil jedinou čáru. Nožičky se sem nedostanou: ty nemívají
  // 90 % výšky osnovy a navíc musí projít mezerou mezi osnovami.
  // Když i tak nevyjde ani jedna čára, zkusí se 0,85 a 0,78 — jinak systém
  // skončí jako „nenašel pravidelný sled“ a stránka se celá odmítne
  // (naměřeno Cherubini str. 28, 31, 34, 51).
  let staffCols = null, cl = null, covUsed = 0.90;
  for (const cov of [0.90, 0.85, 0.78]) {
    covUsed = cov;
    staffCols = staffColsAt(cov);
    cl = clusterize(staffCols);
    if (cl.candsX.length >= 2) break;
  }
  const { clusters, candsX, all } = cl;

  // 4) okraje systému. Bere se NEJDELŠÍ SOUVISLÝ ÚSEK linky (viz `staffEdges`),
  // ne první/poslední inkoust — na kraji skenu je vazba a stín a ty posunuly
  // levý okraj o desítky bodů doleva (naměřeno „okraj 15 b“ místo 60 b), takže
  // se úvodní čára systému přestala poznávat a číslovalo se o takt víc.
  const medOf = (arr) => {
    if (!arr.length) return 0;
    const s = arr.slice().sort((a, b) => a - b);
    return s[Math.floor((s.length - 1) / 2)];
  };
  const leftEnds = [], rightEnds = [];
  for (let i = sysA; i <= sysB; i++) {
    const [L, R] = staffSpan(real[i], mask, w);
    leftEnds.push(L);
    rightEnds.push(R);
  }
  let staffLeft = medOf(leftEnds);
  let staffRight = medOf(rightEnds);
  if (!rightEnds.length || staffLeft > staffRight) { staffLeft = 0; staffRight = w - 1; }
  // Sloupce protínající celý pás (vazba, stín u okraje skenu) se do hustoty
  // inkoustu nepočítají — jinak „prázdný“ okraj vyjde jako plný inkoustu.
  const isArtifact = (x) => colInk[x] > 0.5 * h || x < 0.02 * w;

  const medGap = (arr) => {
    const d = [];
    for (let i = 1; i < arr.length; i++) d.push(arr[i] - arr[i - 1]);
    d.sort((a, b) => a - b);
    return d.length ? d[Math.floor(d.length / 2)] : 0;
  };
  // Do kandidátů patří i ÚVODNÍ čára systému — v této sazbě stojí přesně na
  // začátku linek (staffLeft), takže filtr „až za okrajem + 0,6 mezery“ ji
  // zahodil a systém dostal o takt MÍŇ (naměřeno str. 2, 2. systém: 3 čáry
  // místo 4). Odebrání úvodní čáry řeší až test níž.
  let rest = candsX.slice().sort((a, b) => a - b)
    .filter(x => x >= staffLeft - pxPerPt);
  let holeDbg = null;   // diagnostika doplněných čar (jen pro panel/sondu)
  let weakDbg = [];     // co doplnila 4d) (slabá čára v dvojmezeře)
  let weakSkipDbg = []; // dvojmezery, které 4d) ZÁMĚRNĚ nedoplnila (široký takt)
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
  // Úvodní čára (první takt) systému se nečísluje — jeho číslo je VYTIŠTĚNÉ.
  // ⚠️ Na začátku systému jsou obvykle DVA plné svislé tahy: hrana/závorka
  // sazby a hned za ní PRVNÍ TAKTOVÁ ČÁRA, nad kterou stojí vytištěné číslo
  // (naměřeno str. 6: závorka 14 b, první čára 68 b, vytištěné „42“ nad 68).
  // Proto se první kandidát bere jako úvodní VŽDY (je to hrana systému) a když
  // je hned za ním druhý blíž než 0,75 šířky taktu, je úvodní i ten (první
  // takt). Podmínka `rest[0] - staffLeft` se tu NEPOUŽÍVÁ: okraj osnovy může
  // být posunutý textem/závorkou (str. 2/1. systém: okraj 15 b, skutečný
  // začátek linek 136 b) a pak se úvodní čára nepoznala a systém dostal
  // o takt navíc (19/21 v regresi). Pojistka proti „úvodní se nedetekovala“:
  // zahodit se smí jen kandidát blíž než 1,5 šířky taktu od okraje.
  let opening = null;
  // 1) Nejpřesnější je VYTIŠTĚNÉ ČÍSLO: stojí nad PRVNÍ taktovou čarou systému
  //    (Jan ho lupou ukládá jako index `barNum`). Kandidát nejblíž jeho x je
  //    úvodní čára; všechno vlevo od něj je hrana/závorka sazby. Bez toho se
  //    u sazby se DVĚMA tahy na začátku (závorka + čára) vybírala závorka
  //    a systém dostal o takt navíc — a podle rozlišení renderu se to
  //    Přepínalo mezi dvěma výsledky (naměřeno Mozart str. 6: na 5 px/bod
  //    začínal systém číslem 53 místo 52).
  if (Array.isArray(opt.numXs) && opt.numXs.length) {
    const topPt = offY + real[sysA][0] / pxPerPt;
    const spPt = spacePx / pxPerPt;
    const inBand = opt.numXs
      .filter(o => o && Number.isFinite(o.x)
        && o.y >= topPt - 6 * spPt && o.y <= topPt + 1.2 * spPt)
      .sort((a, b) => a.x - b.x);
    if (inBand.length) {
      const anchor = inBand[0].x * pxPerPt;
      let best = null, bd = Infinity;
      for (const x of rest) {
        const dd = Math.abs(x - anchor);
        if (dd < bd) { bd = dd; best = x; }
      }
      if (best != null && bd <= 2.5 * spacePx) {
        opening = best;
        rest = rest.filter(x => x > best + 0.5 * spacePx);
      }
    }
  }
  if (opening == null && rest.length === 1) opening = rest.pop();
  else if (opening == null && rest.length >= 2) {
    const P = medGap(rest);
    // ⚠️ Kandidát u OKRAJE osnov (do 0,6 šířky taktu) je úvodní čára vždy.
    // Když u okraje žádný kandidát není, rozhoduje START LINEK: úvodní čára
    // stojí tam, kde začínají vodorovné linky osnov (naměřeno Mozart str. 2/1.
    // systém: `staffLeft` je 15 b = závorka, ale linky začínají na 135,9 b
    // a tam stojí i úvodní čára). Bez toho se buď úvodní čára nechala mezi
    // vnitřními (systém dostal o takt víc), nebo se za úvodní vzala první
    // VNITŘNÍ čára ~1,25 taktu od okraje (Cherubini tištěná 19, 3. a 4.
    // systém: 186 b při okraji 36 b → systém dostal o takt míň).
    const startVotes = (x) => leftEnds.filter(L => Math.abs(x - L) <= 1.2 * spacePx).length;
    const atLineStart = startVotes(rest[0]) >= Math.max(1, Math.ceil(sysCount * 0.5))
      && rest[0] - staffLeft < 1.6 * P;
    if (P > 0 && (rest[0] - staffLeft < 0.6 * P || atLineStart)) {
      opening = rest.shift();
      // ⚠️ Druhou úvodní čáru (závorka + první taktová čára) ber jen tehdy,
      // když po ní v systému zůstanou aspoň DVĚ vnitřní čáry. Na systému
      // s málo detekovanými čarami (Cherubini str. 28: jen 3 kandidáti) se
      // jinak sežraly obě a systém zůstal bez čar → celá stránka se odmítla.
      if (rest.length >= 3 && rest[0] - opening < 0.75 * P) opening = rest.shift();
    }
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
  // ⚠️ Koncová čára je JEDNA (max. dvojitá). Bez počítadla se smyčka „za
  // koncovou čarou je prázdno“ na systému, kde jsou na konci pomlky, zakously
  // do VŠECH kandidátů a systém zůstal bez čar (naměřeno Cherubini str. 28,
  // 31, 34, 51: bars 0 → celá stránka se odmítla).
  let closingPops = 0;
  while (rest.length > 1 && closingPops < 2
         && rest[rest.length - 1] > staffRight - 2.5 * spacePx) {
    closing = rest.pop();
    closingPops++;
  }
  // …a když linky přetahují, rozhodne prázdno za poslední čarou. Pojistka:
  // zahazuje se jen KRÁTKÝ chvost (do 0,6 šířky taktu) — koncová čára v této
  // sazbě stojí ~45 b před koncem linek, kdežto skutečný poslední takt je
  // široký jako ostatní, takže se nezahodí.
  // ⚠️ Tohle kolo se smí pustit JEN když koncová čára ještě není nalezená.
  // Dřív běželo i po něm a sežralo skutečnou VNITŘNÍ čáru: na tištěné 11/3.
  // systému jsou kandidáti 402,5 (vnitřní) i 435,3 (koncová, u okraje linek);
  // první kolo správně vzalo 435,3 jako koncovou, druhé pak přepsalo koncovou
  // na 402,5 → poslední takt zůstal bez čísla (Jan: „ignoruje poslední takt“).
  // Naměřeno stejně na tištěné 12/1. (412,3 vs 435) a 31/3. (396,7 vs 432,4).
  const barP = medGap(rest);
  const tailShort = () => {
    const t = staffRight - rest[rest.length - 1];
    return barP > 0 ? t < 0.6 * barP : t < 8 * spacePx;
  };
  // Hustota se měří v ÚZKÉM okně hned za kandidátem (ne až po pravý okraj
  // linek): za koncovou čarou je prázdno, ale dál k okraji můžou být zatoulané
  // značky a ty dřív „nafoukly“ prázdno na 14–20 % (naměřeno str. 5 a 7), takže
  // se koncová čára nechala mezi vnitřními a systém dostal o takt navíc.
  const afterLast = () => {
    const x = rest[rest.length - 1];
    return musicDensity(x + spacePx, Math.min(staffRight, x + 6 * spacePx));
  };
  while (rest.length > 1 && closing == null && closingPops < 2
         && tailShort() && afterLast() < 0.05) {
    closing = rest.pop();
    closingPops++;
  }

  // 4d) CHYBĚJÍCÍ ČÁRA PODLE SOUSEDNÍCH MEZER (listopad 2026). Aplikuje se až na
  // HOTOVÝ řetěz vnitřních čar (ne na kandidáty: v kandidátech jsou i obloučky
  // a posuvky, takže by pravidlo „2× mezera“ spadlo mezi dvě falešné polohy).
  // Naměřeno 600dpi Cherubini tištěná 43/2.: detekce vidí mezery 51 / 59 / 128 /
  // 69 b; medián SOUSEDŮ té 128 je 59, takže čára chybí. Globální medián tohle
  // mine (128/69 = 1,85 < 1,7× mediánu? ne — ale u 44/3. a 46/1. to padá na
  // toleranci), proto rozhodují sousedé.
  // Doplní se JEN čára, která je ve skenu opravdu vidět: ve VŠECH osnovách
  // systému má ten sloupec inkoust (≥ 0,18 výšky osnovy) a víc než okolní hudba
  // (≥ medián okna + 0,05), ale NENÍ souvislá (≤ 0,85) — plná svislice by se
  // normální detekcí našla sama. Nožička ani slabika takhle ve všech osnovách
  // současně nevystoupí.
  if (rest.length >= 2 && rest.length <= 40) {
    const cohAt = (x) => {
      let mn = 1;
      for (let i = sysA; i <= sysB; i++) {
        const g = real[i];
        const yT = g[0], yB = g[g.length - 1], bh = Math.max(1, yB - yT);
        let ink = 0;
        for (let y = yT; y <= yB; y++) ink += mask[y * w + Math.round(x)];
        mn = Math.min(mn, ink / bh);
      }
      return mn;
    };
    const weakAdd = [];
    // ⚠️ MEZERA MEZI OSNOVAMI ROZHODUJE (listopad 2026). Jan: Cherubini str. 23,
    // 2. systém — takt se 4 dobami je na šířku stejně velký jako následující dva
    // takty (4+4), takže dvojmezera vznikne i bez chybějící čáry; uprostřed stojí
    // zarovnané noty sboru i klavíru a jejich nožičky vypadají jako slabá čára.
    // Skutečná taktová čára prochází MEZEROU mezi osnovami, nožička ne.
    // Doplní se proto, když sloupec mezerou prochází, NEBO když je v mezeře víc
    // hudby než v sousedních taktech (dvě hudby = chybějící čára, ne roztažený takt).
    const gapOk = (x) => gapSupport(x) >= 1;
    for (let i = 0; i + 1 < rest.length; i++) {
      const g = rest[i + 1] - rest[i];
      const nb = [];
      if (i - 1 >= 0) nb.push(rest[i] - rest[i - 1]);
      if (i + 2 < rest.length) nb.push(rest[i + 2] - rest[i + 1]);
      if (!nb.length) continue;          // krajní mezery nemají s čím srovnávat
      const ref = medOf(nb);
      if (!(ref > 0) || g < 1.75 * ref) continue;
      const k = Math.round(g / ref);
      if (k !== 2) continue;             // jen jednoznačná dvojmezera
      const step = g / 2;
      const want = rest[i] + step;
      // ⚠️ HUSTOTA HUDBY ROZLIŠUJE ZTRACENOU ČÁRU OD ŠIROKÉHO TAKTU (listopad 2026).
      // Jan: „takt má 4 doby, ale na šířku je stejně široký jako následující dva
      // takty, které mají každý také 4 doby" → dvojmezera vznikne i tam, kde čára
      // NEchybí, jen je takt roztažený (recitativ, dlouhé noty). V obou případech
      // uprostřed stojí zarovnané noty sboru i klavíru, takže koherence je stejná.
      // Rozdíl je v hustotě: když čára chybí, jsou v mezeře DVĚ hudby (hustota jako
      // v sousedním taktu); když je takt jen široký, je hudba roztažená na dvojnásobnou
      // šířku (hustota zhruba poloviční). Radši číslo chybí, než aby bylo o takt víc.
      const densIn = (xa, xb) => musicDensity(xa + 1.2 * spacePx, xb - 1.2 * spacePx);
      const dGap = densIn(rest[i], rest[i + 1]);
      const dNb = [];
      if (i - 1 >= 0) dNb.push(densIn(rest[i - 1], rest[i]));
      if (i + 2 < rest.length) dNb.push(densIn(rest[i + 1], rest[i + 2]));
      const dRef = dNb.length ? medOf(dNb) : dGap;
      const densRatio = dRef > 0 ? dGap / dRef : 1;

      // okno ±30 % půlmezery: chybějící čára dělí takt na dvě podobné půlky
      const lo = Math.max(0, Math.round(want - 0.3 * step));
      const hi = Math.min(w - 1, Math.round(want + 0.3 * step));
      const vals = [];
      for (let x = lo; x <= hi; x++) { const c = cohAt(x); vals.push(c); }
      if (!vals.length) continue;
      const sorted = vals.slice().sort((p, q) => p - q);
      const base = sorted[Math.floor(sorted.length / 2)];
      let peak = null;
      for (let x = lo; x <= hi; x++) {
        const c = cohAt(x);
        if (!peak || c > peak[1]) peak = [x, c];
      }
      const minCoh = Math.max(0.18, base + 0.05);
      // NESMÍ to být čára, kterou už řetěz má (jinak by vznikla dvě čísla na
      // stejném x — naměřeno Mozart str. 16/1.: koherence 0,70 na 269,7 b, což
      // je už uznaná čára, a systém dostal o takt navíc).
      const onChain = rest.some(x => Math.abs(x - (peak ? peak[0] : -1e9)) <= xTol);
      // HORNÍ MEZ je to, co odliší slabou čáru od SILNÉHO objektu na stejném x.
      // Naměřeno: skutečná slabá čára má po osnovách 0,22–0,35 (600dpi Cherubini
      // str. 44/2. vrchol 0,27), kdežto trámec/nožička zarovnaných akordů 0,61
      // a víc (Mozart str. 16/1. na 270 b). Nad 0,50 se nedoplňuje — radši
      // číslo chybí, než aby bylo o takt víc.
      if (peak && !onChain && peak[1] >= minCoh && peak[1] <= 0.50
          && (gapOk(peak[0]) || densRatio >= 1.05)) {
        weakAdd.push(peak[0]);
        weakAdd.dbg = weakAdd.dbg || [];
        weakAdd.dbg.push([+(peak[0] / pxPerPt).toFixed(1), +peak[1].toFixed(2), +base.toFixed(2),
                          +densRatio.toFixed(2)]);
      } else if (peak && !onChain && peak[1] >= minCoh && peak[1] <= 0.50) {
        // Záznam o tom, co se ZÁMĚRNĚ nedoplnilo (široký takt) — pro diagnostiku.
        weakAdd.skip = weakAdd.skip || [];
        weakAdd.skip.push([+(peak[0] / pxPerPt).toFixed(1), +peak[1].toFixed(2),
                           +densRatio.toFixed(2)]);
      }
    }
    const dbgWeak = weakAdd.dbg || [];
    if (weakAdd.length) rest = rest.concat(weakAdd).sort((x, y) => x - y);
    weakDbg = dbgWeak;
    weakSkipDbg = weakAdd.skip || [];
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
                 barP: +barP.toFixed(1), hole: holeDbg, weak: weakDbg,
                 weakSkip: weakSkipDbg };
  const startsPt = candsX.map(x => +(x / pxPerPt).toFixed(1));
  const cands = clusters.map(c => {
    const mean = c.xs.reduce((n, p) => n + p.x, 0) / c.xs.length;
    return [+(mean / pxPerPt).toFixed(1), new Set(c.xs.map(p => p.i)).size, gapSupport(mean)];
  });

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
           opening, closing, diag, dbg, mode: 'systém', cands, startsPt,
           openingPt: opening == null ? null : offY * 0 + opening / pxPerPt,
           staffLeftPt: staffLeft / pxPerPt };
}
