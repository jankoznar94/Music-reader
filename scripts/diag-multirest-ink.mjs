// Kalibrace: kolik inkoustu mají taktové sloupce (pomlka vs běžný takt).
// Použití: node scripts/diag-multirest-ink.mjs <pdf> <strana> [strana…]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);
const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, ...rest] = process.argv;
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data }).promise;
const PPT = Number(process.env.NOTY_PPT || 5), MAX_PX = 12e6;

function ink(ctx, pxPerPt, ba, sys, sp) {
  const x0 = Math.round(ba.x0 * pxPerPt), x1 = Math.round(ba.x1 * pxPerPt);
  const y0 = Math.round((sys.top + 0.6 * sp) * pxPerPt);
  const y1 = Math.round((sys.bot - 0.6 * sp) * pxPerPt);
  const w = Math.max(1, x1 - x0), h = Math.max(1, y1 - y0);
  const d = ctx.getImageData(x0, y0, w, h).data;
  let n = 0;
  for (let i = 0; i < d.length; i += 4) {
    if ((d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000 < 170) n++;
  }
  return n / (w * h);
}

for (const n of rest.map(Number)) {
  const page = await doc.getPage(n);
  const base = page.getViewport({ scale: 1 });
  const pw = base.width, ph = base.height;
  let scale = PPT;
  if (pw * ph * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (pw * ph));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx2 = cv.getContext('2d');
  ctx2.fillStyle = '#fff';
  ctx2.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx2, viewport: vp }).promise;
  const pxPerPt = cv.width / pw;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const d = detectPageSystems(cv, pxPerPt, {});
  console.log('page', n);
  for (const s of d.systems || []) {
    if (!s.ok) continue;
    const sp = s.spacePt || 4;
    const firstX = Number.isFinite(s.openingPt) ? s.openingPt : s.staffLeftPt + 2 * sp;
    const closeX = Number.isFinite(s.closingPt) ? s.closingPt
      : (Number.isFinite(s.staffRightPt) ? s.staffRightPt : s.lines[s.lines.length - 1] + 100);
    const bx = [firstX, ...s.lines, closeX];
    const vals = [];
    for (let i = 0; i + 1 < bx.length; i++) {
      vals.push(+ink(ctx, pxPerPt, { x0: bx[i], x1: bx[i + 1] },
                     { top: s.sysTop, bot: s.sysBot }, sp).toFixed(4));
    }
    console.log('  y=', Math.round(s.sysTop), 'sp=', sp.toFixed(2), 'sloupce:', vals.join(' '));
  }
}
