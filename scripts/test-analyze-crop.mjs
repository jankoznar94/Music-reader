// Rychlý test analyzátoru bez prohlížeče: syntetická stránka s osnovami
// a textem před nimi. Ověří, že šířku rámečku určují osnovy.
import { analyzeContent } from '../src/contentBounds.js';

const W = 560, H = 792;
const gray = new Uint8Array(W * H).fill(255);

const set = (x, y) => { if (x >= 0 && x < W && y >= 0 && y < H) gray[y * W + x] = 0; };

// osnovy: x 57..503, 11 systémů
for (let s = 0; s < 11; s++) {
  const y0 = 113 + s * 55;
  for (let i = 0; i < 5; i++) {
    for (let x = 57; x <= 503; x++) set(x, y0 + i * 4);
  }
}
// text „piano forte“ vlevo před osnovou
for (let y = 280; y < 292; y++) for (let x = 6; x < 50; x++) set(x, y);
// hluboká nota dole
for (let y = 735; y < 742; y++) for (let x = 280; x < 288; x++) set(x, y);

const res = analyzeContent(gray, W, H);
console.log(JSON.stringify(res, null, 1));
const c = res.crop;
console.log('crop x0..x1 v px:', (c.x * W).toFixed(1), ((c.x + c.w) * W).toFixed(1));
console.log('crop y0..y1 v px:', (c.y * H).toFixed(1), ((c.y + c.h) * H).toFixed(1));
