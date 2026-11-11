// Diagnostika systémů/taktů po stránkách — BEZ prohlížeče.
// Vykreslí stránku přes pdfjs + @napi-rs/canvas, spustí SKUTEČNÝ
// `detectPageSystems` z src/barLines.js a vypíše, kolik taktů kde vidí.
//
// Použití: node scripts/diag-page-systems-node.mjs <pdf> <strana> [strana…]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, ...pageArgs] = process.argv;
const pages = pageArgs.map(Number);
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;

const PPT = Number(process.env.NOTY_PPT || 5), MAX_PX = 12e6;

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
  const d = detectPageSystems(cv, pxPerPt, {});
  const out = {
    page: pageNum, pw: +pw.toFixed(1), ph: +ph.toFixed(1), pxPerPt: +pxPerPt.toFixed(3),
    ok: d.ok, staves: d.staves, reason: d.reason || null, gapBasePt: d.gapBasePt,
    gapsPt: d.gapsPt,
    rowsPt: d.rowsPt,
    systems: (d.systems || []).map((s) => ({
      a: s.sysA, b: s.sysB, staves: s.staves, expected: s.stavesExpected,
      spanOk: s.spanOk, ok: s.ok, reason: s.reason || null, bars: s.bars,
      lines: (s.lines || []).map((v) => +v.toFixed(1)),
      sysTop: +s.sysTop?.toFixed(1), sysBot: +s.sysBot?.toFixed(1),
      opening: s.opening == null ? null : +(s.opening / pxPerPt).toFixed(1),
      closing: s.closing == null ? null : +(s.closing / pxPerPt).toFixed(1),
      staffLeft: s.staffLeftPt, staffRight: s.diag?.staffRight,
      space: s.diag?.space, cands: s.cands, diag: s.diag,
    })),
  };
  console.log(JSON.stringify(out));
}
