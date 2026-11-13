// Náhled stránek PDF do PNG (bez prohlížeče) — pro kontrolu not očima.
// Použití: node pdf-preview.mjs <pdf> <outdir> [strana…]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';
import path from 'node:path';

const [, , file, outdir, ...rest] = process.argv;
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data }).promise;
console.log('pages:', doc.numPages);
const pages = rest.length ? rest.map(Number) : [1];
fs.mkdirSync(outdir, { recursive: true });
for (const n of pages) {
  const page = await doc.getPage(n);
  const base = page.getViewport({ scale: 1 });
  const scale = Math.min(2.2, Math.sqrt(12e6 / (base.width * base.height)));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx, viewport: vp }).promise;
  const out = path.join(outdir, `p${n}.png`);
  fs.writeFileSync(out, cv.toBuffer('image/png'));
  console.log(out, cv.width, 'x', cv.height, 'pt', base.width.toFixed(1), base.height.toFixed(1));
}
