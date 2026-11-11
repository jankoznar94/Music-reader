// Přečte VYTIŠTĚNÁ čísla taktů z výřezů PNG (tesseract.js offline, whitelist číslic).
// Slouží k ověření pravdy o počtu taktů ve systému, když je sken 1bitový a
// vision na drobných číslicích selhává (čte „201“ jako „011“).
//
// Použití: node scripts/diag-ocr-bar-numbers.mjs /tmp/num_p44_s1.png /tmp/num_p46_s2.png …
// Volitelně NOTY_PSM (default 7) a NOTY_SCALE (předzvětšení, default 2).
import { createWorker } from 'tesseract.js';

const files = process.argv.slice(2);
if (!files.length) {
  console.error('použití: node scripts/diag-ocr-bar-numbers.mjs <png> [png…]');
  process.exit(2);
}
const psm = process.env.NOTY_PSM || '7';

const worker = await createWorker('eng', 1, {
  langPath: 'public/ocr',
  corePath: 'public/ocr/tesseract-core-lstm.wasm.js',
  cacheMethod: 'none',
  logger: () => {},
});
await worker.setParameters({
  tessedit_char_whitelist: '0123456789',
  tessedit_pageseg_mode: psm,
});

for (const f of files) {
  const { data } = await worker.recognize(f);
  const txt = (data.text || '').replace(/\s+/g, '');
  console.log(`${f}  ->  "${txt}"  (jistota ${Math.round(data.confidence)})`);
}
await worker.terminate();
