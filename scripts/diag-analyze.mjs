// Diagnostika analyzátoru na reálné stránce: vypíše osnovy, okraje a ostrůvky
// inkoustu vlevo/vpravo od osnov (proč se značky hlasů nepřibraly).
import { analyzeContent } from '../src/contentBounds.js';
import fs from 'fs';

const arg = process.argv[2] || '5';
const W = 560, H = 792;
const file = arg.includes('/') ? arg : `/tmp/g${arg}.raw`;
const gray = new Uint8Array(fs.readFileSync(file));

const res = analyzeContent(gray, W, H);
console.log('crop:', JSON.stringify(res.crop));
console.log('staff:', JSON.stringify(res.staff));

// znovu spočítat masku stejně jako analyzátor (hrubě) a vypsat sloupce
const ink = new Uint8Array(W * H);
for (let i = 0; i < gray.length; i++) if (gray[i] < 160) ink[i] = 1;
const colHasInk = (x) => { for (let y = 0; y < H; y++) if (ink[y * W + x]) return true; return false; };
const hx0 = Math.round(res.staff.x0 * W);
const runs = [];
let start = -1, last = -1;
for (let x = Math.max(0, hx0 - 30); x < hx0; x++) {
  if (colHasInk(x)) { if (start < 0) start = x; last = x; }
  else if (start >= 0 && x - last > 3) { runs.push([start, last]); start = -1; }
}
if (start >= 0) runs.push([start, last]);
console.log('hx0 =', hx0, 'ostrůvky vlevo:', JSON.stringify(runs));

// komponenty v levém okně
const near = Math.round(W * 0.05);
const x0w = Math.max(0, hx0 - near);
const seen = new Uint8Array(W * H);
const comps = [];
for (let y = 0; y < H; y++) for (let x = x0w; x < hx0; x++) {
  const i = y * W + x;
  if (!ink[i] || seen[i]) continue;
  const stack = [i]; seen[i] = 1;
  let minX = x, maxX = x, minY = y, maxY = y, n = 0;
  while (stack.length) {
    const j = stack.pop(); n++;
    const jx = j % W, jy = (j / W) | 0;
    if (jx < minX) minX = jx; if (jx > maxX) maxX = jx;
    if (jy < minY) minY = jy; if (jy > maxY) maxY = jy;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const nx = jx + dx, ny = jy + dy;
      if (nx < x0w || nx >= hx0 || ny < 0 || ny >= H) continue;
      const k = ny * W + nx;
      if (ink[k] && !seen[k]) { seen[k] = 1; stack.push(k); }
    }
  }
  comps.push({ x: minX, w: maxX - minX + 1, y: minY, h: maxY - minY + 1, n });
}
comps.sort((a, b) => a.x - b.x);
console.log('komponenty:', JSON.stringify(comps.slice(0, 12)));
