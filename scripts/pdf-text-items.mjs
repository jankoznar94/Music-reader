// Textová vrstva stránky: co je v PDF jako text (porovnávací pravda k obrázkové detekci).
// Použití: node scripts/pdf-text-items.mjs <pdf> <strana> [strana…]
import { getDocument } from 'pdfjs-dist/legacy/build/pdf.mjs';
import fs from 'node:fs';

const [, , file, ...rest] = process.argv;
const data = new Uint8Array(fs.readFileSync(file));
const doc = await getDocument({ data }).promise;
for (const n of rest.map(Number)) {
  const page = await doc.getPage(n);
  const tc = await page.getTextContent();
  const items = tc.items
    .filter(i => i.str && i.str.trim())
    .map(i => ({
      s: i.str.trim(),
      x: +i.transform[4].toFixed(1),
      y: +(842 - i.transform[5]).toFixed(1),
      h: +Math.hypot(i.transform[2], i.transform[3]).toFixed(1),
    }));
  console.log(JSON.stringify({ page: n, items }, null, 0));
}
