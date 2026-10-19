// Dávková kontrola ořezu na všech stránkách reálné skladby.
// Pro každou stránku ověří: ok, staff nalezeny, výřez není prázdný,
// a že výřez neobsahuje prázdný pruh nahoře větší než ~3 % výšky stránky.
import { analyzeContent } from '../src/contentBounds.js';
import fs from 'fs';
import path from 'path';

const dir = process.argv[2] || '/tmp/ejraw';
const W = 560, H = 792;
const files = fs.readdirSync(dir).filter(f => f.endsWith('.raw')).sort();
let bad = [];
for (const f of files) {
  const gray = new Uint8Array(fs.readFileSync(path.join(dir, f)));
  if (gray.length !== W * H) { console.log(f, 'BAD SIZE', gray.length); continue; }
  const r = analyzeContent(gray, W, H);
  const x0 = Math.round(r.crop.x * W), y0 = Math.round(r.crop.y * H);
  const x1 = Math.round((r.crop.x + r.crop.w) * W), y1 = Math.round((r.crop.y + r.crop.h) * H);
  // první inkoustový řádek UVNITŘ výřezu (hrubý práh)
  const thr = 210;
  let inkTop = -1;
  for (let y = Math.max(0, y0); y < Math.min(H, y1); y++) {
    let has = false;
    for (let x = Math.max(0, x0); x < Math.min(W, x1); x++) if (gray[y * W + x] < thr) { has = true; break; }
    if (has) { inkTop = y; break; }
  }
  const topBlank = inkTop >= 0 ? inkTop - Math.max(0, y0) : -1;
  const flags = [];
  if (!r.ok) flags.push('NOT_OK');
  if (!(r.staff.groups >= 2)) flags.push('NO_STAVES');
  if (topBlank < 0) flags.push('EMPTY_CROP');
  else if (topBlank > H * 0.03) flags.push('TOP_BLANK=' + topBlank);
  const sp = r.staff.spacing || 0;
  const sx0 = r.staff.x0 == null ? -1 : r.staff.x0;
  // řez do tahu na okraji: první/poslední sloupec výřezu není prázdný
  const colInk = (xc) => {
    let n = 0;
    for (let y = Math.max(0, y0); y < Math.min(H, y1); y++) if (gray[y * W + xc] < thr) n++;
    return n;
  };
  const edgeL = colInk(Math.max(0, x0)), edgeR = colInk(Math.min(W - 1, x1 - 1));
  if (edgeL > 2) flags.push('EDGE_INK_L=' + edgeL);
  if (edgeR > 2) flags.push('EDGE_INK_R=' + edgeR);
  const line = `${f} crop x=${r.crop.x.toFixed(3)} y=${r.crop.y.toFixed(3)} w=${r.crop.w.toFixed(3)} h=${r.crop.h.toFixed(3)} `
    + `staff=${r.staff.groups} sp=${sp.toFixed(4)} x0=${sx0.toFixed(3)} topBlank=${topBlank} ${flags.join(' ')}`;
  console.log(line);
  if (flags.length) bad.push(f);
}
console.log('---');
console.log(bad.length ? 'FLAGGED: ' + bad.join(', ') : 'ALL OK (' + files.length + ' pages)');
