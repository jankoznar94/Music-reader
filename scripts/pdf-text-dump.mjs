// Vytáhne textovou vrstvu stránky (čísla taktů mají souřadnice v bodech PDF).
// Použití: node scripts/pdf-text-dump.mjs <pdf> <page> [minY] [maxY]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import fs from 'node:fs';

const [, , file, pageStr, minY, maxY] = process.argv;
const page = Number(pageStr || 9);
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data, useSystemFonts: true }).promise;
const p = await doc.getPage(page);
const vp = p.getViewport({ scale: 1 });
const tc = await p.getTextContent();
let n = 0;
for (const it of tc.items) {
  if (!it.str || !it.str.trim()) continue;
  const y = vp.height - it.transform[5];
  if (minY && y < Number(minY)) continue;
  if (maxY && y > Number(maxY)) continue;
  n++;
  if (n <= 80) console.log(JSON.stringify({ s: it.str, x: +it.transform[4].toFixed(1), y: +y.toFixed(1) }));
}
console.log('celkem textů:', n, 'strana', vp.width.toFixed(1), 'x', vp.height.toFixed(1));
