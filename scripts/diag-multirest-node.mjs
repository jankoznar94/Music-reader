// Diagnostika vícetaktových pomlsek — BEZ prohlížeče.
// Pro každou stránku vypíše, jak by dočíslování očíslovalo takty (včetně
// skoků za pomlkou) a porovná to s vytištěnými čísly v textové vrstvě PDF.
//
// Použití: node scripts/diag-multirest-node.mjs <pdf> [strana…]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const { detectPageSystems } = await import('../src/barLines.js');
const { detectMultiRests } = await import('../src/multiRest.js');

const [, , file, ...pageArgs] = process.argv;
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data }).promise;
const pages = pageArgs.length ? pageArgs.map(Number)
  : Array.from({ length: doc.numPages }, (_, i) => i + 1);
const PPT = Number(process.env.NOTY_PPT || 5), MAX_PX = 12e6;

let bad = 0, sysCount = 0, restsCount = 0, midBad = 0;
for (const pageNum of pages) {
  const page = await doc.getPage(pageNum);
  const base = page.getViewport({ scale: 1 });
  const pw = base.width, ph = base.height;
  let scale = PPT;
  if (pw * ph * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (pw * ph));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx, viewport: vp }).promise;
  const pxPerPt = cv.width / pw;

  // čísla z textové vrstvy (stejné jako readPageTextNumbers v appce)
  const tc = await page.getTextContent().catch(() => null);
  const printed = [];
  for (const it of (tc && tc.items) || []) {
    const t = String(it.str || '').trim();
    if (!/^\d{1,4}\.?$/.test(t)) continue;
    const tr = it.transform || [];
    const size = Math.hypot(tr[2] || 0, tr[3] || 0) || 10;
    printed.push({
      n: parseInt(t, 10), x: tr[4] || 0, yTop: ph - (tr[5] || 0),
      w: Number(it.width) || size * 0.6 * t.length, h: size,
    });
  }

  const d = detectPageSystems(cv, pxPerPt, {});
  const lines = [];
  const restsAll = [];
  let prevLast = null;
  for (const sys of (d.systems || [])) {
    sysCount++;
    if (!sys.ok || !sys.spanOk) { lines.push('  systém přeskočen: ' + (sys.reason || 'uříznutý')); continue; }
    const sp = sys.spacePt || 4;
    const firstX = Number.isFinite(sys.openingPt) ? sys.openingPt
      : (Number.isFinite(sys.staffLeftPt) ? sys.staffLeftPt + 2 * sp : sys.lines[0] - 40);
    const closeX = Number.isFinite(sys.closingPt) ? sys.closingPt
      : (Number.isFinite(sys.staffRightPt) ? sys.staffRightPt : sys.lines[sys.lines.length - 1] + 100);
    const bx = [firstX, ...sys.lines, closeX];
    const bars = [];
    for (let i = 0; i + 1 < bx.length; i++) bars.push({ x0: bx[i], x1: bx[i + 1] });
    const span = bars.map(() => 1);
    // NOTY_NOREST=1 → chování PŘED opravou (jeden sloupec = jeden takt)
    const found = process.env.NOTY_NOREST === '1' ? []
      : detectMultiRests(cv, pxPerPt, { top: sys.sysTop, bot: sys.sysBot }, bars, { sp, printed });
    for (const r of found) span[r.i] = r.count;

    // vytištěné číslo na začátku systému = nezávislá pravda (jako v appce)
    const bandTop = sys.sysTop - 6 * sp, bandBot = sys.sysTop + 1 * sp;
    const hit = printed.filter(p => p.h < 3 * sp && p.yTop >= bandTop && p.yTop <= bandBot)
      .sort((a, b) => a.x - b.x);
    let cur = hit.length ? hit[0].n : (prevLast != null ? prevLast + 1 : 1);
    const nums = [];
    for (let i = 0; i < bars.length; i++) { nums.push(cur); cur += span[i]; }
    prevLast = cur - 1;
    const tag = found.map(r => `pomlka ${nums[r.i]}×${r.count}`).join(', ');
    // KAŽDÉ vytištěné číslo systému (i uprostřed) musí sedět na naše číslo:
    // právě tady se dřív projevilo, že pomlka počítala jako jeden takt.
    const placed = hit.length
      ? [{ x: firstX, n: nums[0] }].concat(sys.lines.map((x, i) => ({ x, n: nums[i + 1] })))
      : sys.lines.map((x, i) => ({ x, n: nums[i] }));
    for (const p2 of printed) {
      if (p2.h >= 3 * sp) continue;                     // velké číslo pomlky
      if (p2.yTop < sys.sysTop - 6 * sp || p2.yTop > sys.sysBot) continue;
      let bestP = null;
      for (const q of placed) {
        const dx = Math.abs(q.x - p2.x);
        if (!bestP || dx < bestP.dx) bestP = { dx, q };
      }
      if (!bestP || bestP.dx > 32) continue;
      if (Math.abs(bestP.q.n - p2.n) > 0.5) {
        midBad++;
        lines.push(`  ! vytištěné ${p2.n} u x=${Math.round(p2.x)} → spočítáno`
          + ` ${Math.round(bestP.q.n)} (rozdíl ${p2.n - Math.round(bestP.q.n)})`);
      }
    }
    if (hit.length && Math.abs(hit[0].n - nums[0]) > 0.5) {
      bad++;
      lines.push(`  ! systém y=${Math.round(sys.sysTop)}: vytištěno ${hit[0].n},`
        + ` spočítáno ${Math.round(nums[0])} — o ${hit[0].n - Math.round(nums[0])} vedle`);
    }
    if (found.length) restsAll.push({ sys: Math.round(sys.sysTop), found: found.length, tag });
    lines.push(`  y=${Math.round(sys.sysTop)} sazba ${JSON.stringify(nums.map(n => +n.toFixed(0)))}`
      + (hit.length ? ` vytištěno ${hit[0].n}` : ' bez vytištěného čísla')
      + (tag ? `  ← ${tag}` : ''));
  }

  restsCount += restsAll.length;
  if (process.env.NOTY_QUIET) continue;
  console.log(`page ${pageNum}  systémů ${(d.systems || []).length}  pomlk ${restsAll.length}`);
  for (const l of lines) console.log(l);

}

console.log(`\nSOUHRN: systémů ${sysCount}, pomlk ${restsCount},`
  + ` rozporů na začátku systému ${bad}, uprostřed systému ${midBad}`);
process.exit(bad || midBad ? 1 : 0);
