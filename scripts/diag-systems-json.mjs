// Zapíše počty systémů/osnov/čar pro všechny stránky do JSON (pro diff verzí).
// node scripts/diag-systems-json.mjs <pdf> <out.json> [maxStran]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, out, maxStr] = process.argv;
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const last = Math.min(doc.numPages, Number(maxStr || doc.numPages));
const PPT = 5, MAX_PX = 12e6;
const rows = [];
for (let n = 1; n <= last; n++) {
  const page = await doc.getPage(n);
  const base = page.getViewport({ scale: 1 });
  let scale = PPT;
  if (base.width * base.height * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (base.width * base.height));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx, viewport: vp }).promise;
  const d = detectPageSystems(cv, cv.width / base.width, {});
  rows.push({ page: n, staves: d.staves,
    systems: (d.systems || []).map((s) => ({ st: s.stavesFound, exp: s.stavesExpected,
      bars: s.bars, ok: s.ok, lines: s.lines.map((v) => Math.round(v)) })) });
  if (n % 10 === 0) console.error('… ' + n);
}
fs.writeFileSync(out, JSON.stringify(rows));
console.log('ok ' + out + ' pages=' + rows.length);
