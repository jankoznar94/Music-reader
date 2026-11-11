// Co udělalo doplňování ZTRACENÝCH čar (diag.hole) a jací kandidáti existují.
// node scripts/diag-holes.mjs <pdf> <strana> [strana…]
// Strany jsou 1-based (PDF 44 = tištěná 43).
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, ...pages] = process.argv;
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const PPT = 5, MAX_PX = 12e6;

for (const p of pages.map(Number)) {
  const page = await doc.getPage(p);
  const base = page.getViewport({ scale: 1 });
  let scale = PPT;
  if (base.width * base.height * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (base.width * base.height));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx, viewport: vp }).promise;
  const d = detectPageSystems(cv, cv.width / base.width, {});
  console.log(`== PDF ${p}: systémů ${(d.systems || []).length}`);
  (d.systems || []).forEach((s, k) => {
    console.log(`  sys${k + 1} bars=${s.bars} lines=${JSON.stringify((s.lines || []).map(v => +v.toFixed(1)))}`
      + ` open=${s.opening == null ? null : +(s.opening / (cv.width / base.width)).toFixed(1)}`
      + ` close=${s.closing == null ? null : +(s.closing / (cv.width / base.width)).toFixed(1)}`);
    console.log(`    cands=${JSON.stringify(s.cands)}`);
    console.log(`    hole=${JSON.stringify(s.diag && s.diag.hole)}`);
    console.log(`    weak=${JSON.stringify(s.diag && s.diag.weak)}`);
  });
}
