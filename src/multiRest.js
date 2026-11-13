/**
 * Vícetaktové pomlky (multi-measure rests) — Jan, listopad 2026.
 *
 * V notách se objevuje „ekonomický“ takt: prázdný takt, nad kterým stojí velké
 * tučné číslo N, které říká, přes kolik taktů je pomlka roztažená. Příklad
 * z reálného partu (Skyrim, str. 2): před pomlkou je takt 28, pomlka začíná
 * taktem 29 s číslem 6 (tj. 29–34), takže další takt má číslo 35 — a přesně
 * tak to mají v sobě vytištěné noty (35 stojí na začátku dalšího systému).
 *
 * Dočíslování dřív počítalo každý TAKTOVÝ SLOUPEC jako jeden takt, takže po
 * pomlce byla všechna čísla nižší o N−1 a stránka se musela srovnávat podle
 * vytištěného čísla (a když tam žádné nebylo, byla čísla špatně úplně).
 *
 * DŮLEŽITÉ: sama velikost čísla NESTAČÍ. V některých vydáních jsou vytištěná
 * čísla taktů velká (naměřeno 14 b, Skyrim str. 28) a bez dalšího vodítka by
 * se z nich staly „pomlky“ a číslování by ujelo o desítky. Proto se velké
 * číslo pomlky pozná RELATIVNĚ: musí být nejméně 1,35× vyšší než obvyklé
 * vytištěné číslo taktu na téže stránce (pomlka 18,9 b vs. takt 9,4–12 b;
 * na str. 28 je všechno 14 b → nic se za pomlku neprohlásí).
 *
 * A POZOR: v některých partech nejsou počty taktů pomlky v textové vrstvě
 * vůbec (kreslí se hudebním fontem — Skyrim str. 28). Tam se pomlka
 * nerozpozná a číslování se chová jako dřív (jeden sloupec = jeden takt);
 * srovnání podle vytištěného čísla na začátku dalšího systému to spraví.
 * Skeny textovou vrstvu nemají — tam funkce vrátí prázdno.
 */

// Od kolika násobků osnovové mezery je číslo „velké číslo pomlky“.
export const MULTIREST_MIN_H = 2.8;
// Jak vysoko nad horní osnovou číslo pomlky stojí (v násobcích mezery):
// naměřeno 4,5–6× nahoru (účaří), proto velkorysý pás.
export const MULTIREST_ABOVE = 7.0;
// Prázdný takt = podíl inkoustu menší než tenhle zlomek mediánu běžných taktů.
export const MULTIREST_EMPTY_RATIO = 0.45;
// Velké číslo pomlky musí být aspoň takhle vyšší než obvyklé číslo taktu.
export const MULTIREST_REL_H = 1.35;

/** Nejmenší rozumná výška vytištěného čísla = „jak vysoká je tu číslice taktu“.
 *  (Medián nejde použít — na stránce s mnoha pomlkami převáží právě velká
 *  čísla pomlk a práh by vylezl nad ně a nenašlo by se nic.) */
function baseHeight(printed, sp) {
  const hs = printed.map((p) => p.h).filter((v) => v >= 0.8 * sp).sort((a, b) => a - b);
  return hs.length ? hs[0] : 0;
}

/** Podíl tmavých pixelů ve sloupci taktu mezi horní a dolní osnovou (mimo linky). */
function inkFraction(ctx, pxPerPt, bar, sys, sp) {
  const x0 = Math.round(Math.min(bar.x0, bar.x1) * pxPerPt);
  const x1 = Math.round(Math.max(bar.x0, bar.x1) * pxPerPt);
  const y0 = Math.round((sys.top + 0.6 * sp) * pxPerPt);
  const y1 = Math.round((sys.bot - 0.6 * sp) * pxPerPt);
  const w = Math.max(1, x1 - x0);
  const h = Math.max(1, y1 - y0);
  if (x1 <= x0 || y1 <= y0) return 1;
  let d;
  try { d = ctx.getImageData(x0, y0, w, h).data; } catch (e) { return 1; }
  let ink = 0;
  for (let i = 0; i < d.length; i += 4) {
    if ((d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000 < 170) ink++;
  }
  return ink / (w * h);
}

/**
 * Najde taktové sloupce systému, které jsou vícetaktovou pomlkou.
 *
 * @param {HTMLCanvasElement|OffscreenCanvas} cv stránka vykreslená v pxPerPt (dpr 1!)
 * @param {number} pxPerPt pixely na bod PDF
 * @param {{top:number,bot:number}} sys horní/dolní linka systému v bodech PDF (y od shora)
 * @param {Array<{x0:number,x1:number}>} bars sloupce taktů v bodech PDF, zleva doprava
 * @param {{sp:number,printed:Array<{n:number,x:number,yTop:number,w:number,h:number}>}} opt
 *        sp = osnovová mezera v bodech, printed = čísla z textové vrstvy stránky
 *        (`readPageTextNumbers()` — x/yTop v bodech PDF, y od shora)
 * @returns {Array<{i:number,count:number,src:string}>} i = index sloupce v `bars`
 */
export function detectMultiRests(cv, pxPerPt, sys, bars, opt = {}) {
  const sp = opt.sp > 0 ? opt.sp : 4;
  const printed = opt.printed || [];
  if (!printed.length || !bars.length || !cv) return [];
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  // Základ pro Relativní práh se bere z čísel TOHOTO systému (na stránce může
  // být jiná sazba i jiná velikost čísel než v jiném systému).
  const sysPrinted = printed.filter((p) => p && p.yTop >= sys.top - MULTIREST_ABOVE * sp
    && p.yTop <= sys.bot);
  const baseH = baseHeight(sysPrinted, sp);
  const bigH = Math.max(MULTIREST_MIN_H * sp, MULTIREST_REL_H * baseH);
  const above = MULTIREST_ABOVE * sp;
  const out = [];
  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    const lo = Math.min(b.x0, b.x1) - 2;
    const hi = Math.max(b.x0, b.x1) + 2;
    const cand = printed.filter((p) => {
      if (!p || !(p.h >= bigH)) return false;            // malé číslo = číslo taktu
      const cx = p.x + (p.w || 0) / 2;                   // číslo stojí NAD sloupcem
      if (cx < lo || cx > hi) return false;
      const top = p.yTop - p.h;                          // horní hrana čísla
      // číslo pomlky stojí NAD horní osnovou (ne uvnitř ní)
      return top >= sys.top - above && p.yTop <= sys.top + 0.5 * sp;
    });
    if (!cand.length) continue;
    // Číslo se opakuje nad každou osnovou systému — platí ta nejčastější hodnota.
    const votes = new Map();
    for (const c of cand) votes.set(c.n, (votes.get(c.n) || 0) + 1);
    let n = 0, best = 0;
    for (const [v, k] of votes) if (k > best) { best = k; n = v; }
    if (!(n >= 2 && n <= 999)) continue;                 // „pomlka“ o 1 taktu nemá smysl
    out.push({ i, count: n, src: 'pdf' });
  }
  return out;
}
