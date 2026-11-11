// Přehled systémů na zadaných stránkách: čáry, mezery jako násobky mediánu,
// podezření na chybějící (2x mezera) nebo falešnou čáru.
// node scripts/diag-sys-report.mjs <pdf> <strana,strana,...>
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import { createCanvas } from '@napi-rs/canvas';
import fs from 'node:fs';

globalThis.document = { createElement: () => createCanvas(1, 1) };
globalThis.window = globalThis;
globalThis.requestAnimationFrame = (fn) => setTimeout(() => fn(Date.now()), 0);
const { detectPageSystems } = await import('../src/barLines.js');

const [, , file, pagesStr] = process.argv;
const pages = pagesStr.split(',').map(Number);
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const PPT = 5, MAX_PX = 12e6;

for (const n of pages) {
  const page = await doc.getPage(n);
  const base = page.getViewport({ scale: 1 });
  let scale = PPT;
  if (base.width * base.height * scale * scale > MAX_PX) scale = Math.sqrt(MAX_PX / (base.width * base.height));
  const vp = page.getViewport({ scale });
  const cv = createCanvas(Math.round(vp.width), Math.round(vp.height));
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
  await page.render({ canvasContext: ctx, viewport: vp }).promise;
  const pxPerPt = cv.width / base.width;
  const d = detectPageSystems(cv, pxPerPt, {});
  console.log(`== PDF ${n}: osnov ${d.staves}, systémů ${d.systems.length}`);
  d.systems.forEach((s, k) => {
    const seq = [];
    if (s.opening != null) seq.push(['open', +(s.opening / pxPerPt).toFixed(1)]);
    for (const x of s.lines) seq.push(['bar', +x.toFixed(1)]);
    if (s.closing != null) seq.push(['close', +(s.closing / pxPerPt).toFixed(1)]);
    const xs = seq.map(q => q[1]);
    const gaps = xs.slice(1).map((v, i) => +(v - xs[i]).toFixed(1));
    const med = gaps.length ? gaps.slice().sort((a, b) => a - b)[Math.floor((gaps.length - 1) / 2)] : 0;
    const ratios = gaps.map(g => med ? +(g / med).toFixed(2) : 0);
    const suspect = ratios.filter(r => r > 1.6).length;
    console.log(`  sys${k + 1} st=${s.stavesFound}/${s.stavesExpected} ok=${s.ok} span=${s.spanOk} bars=${s.bars}`
      + ` top=${+(s.sysTop / pxPerPt).toFixed(1)} bot=${+(s.sysBot / pxPerPt).toFixed(1)}`
      + ` xs=${JSON.stringify(xs)} gaps=${JSON.stringify(gaps)} med=${med} ratio=${JSON.stringify(ratios)}`
      + (suspect ? '  <<< SKOK' : ''));
  });
}
