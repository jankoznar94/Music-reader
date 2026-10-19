// Test detekce obsahu nad reálnými stránkami uloženými jako surová šedotónová data.
import fs from 'node:fs';
import { analyzeContent } from '../src/contentBounds.js';

const dir = '/tmp/bounds-test';
const idx = JSON.parse(fs.readFileSync(`${dir}/index.json`, 'utf8'));
for (const f of idx) {
  const gray = new Uint8Array(fs.readFileSync(`${dir}/${f.name}.gray`));
  const t0 = performance.now();
  const r = analyzeContent(gray, f.w, f.h);
  const ms = (performance.now() - t0).toFixed(1);
  const c = r.crop;
  const m = (v) => (v * 100).toFixed(1).padStart(5);
  console.log(
    `${f.name.padEnd(22)} T${m(c.y)} B${m(1 - c.y - c.h)} L${m(c.x)} R${m(1 - c.x - c.w)}` +
    `  staff ${(r.staff.spacing * 100).toFixed(1)}%/${r.staff.groups}` +
    `  skew ${r.angle.toFixed(2)}°  ${ms} ms`
  );
}
