// --- MIGRACE VZHLEDU (jednorázová, verzovaná) --------------------------------
// PRAVIDLO (Jan, Oct 2026): „Nesmí se žádná naše aktualizace takhle radikálně
// projevit automaticky." Nová verze NESMÍ změnit, jak vypadají existující noty
// — ani měřítko, ani pozici, ani ořez. Když vývoj změní výchozí vzhled, musí
// tahle migrace u STARÝCH dat vrátit přesně ten vzhled, který uživatel znal,
// a nový vzhled nechat jen jako volbu (tlačítko), ne jako nový default.
//
// Rev 2 (ořez/rám): ukázalo se, že příznak `frame` na skladbách a v uložených
// zobrazeních zůstal z vývoje zapnutý, takže se skladby začaly otevírat
// OŘÍZNUTÉ a ZVĚTŠENÉ („noty, které měl dřív v pohodě, jsou najednou jinak
// a ještě oříznuté“). Migrace příznak jednou vypne; ořez si každý zapne sám
// tlačítkem Rám u konkrétní skladby. Zoom/posun/rotace se NEMAŽOU — ty patří
// uživateli. (Uložené zobrazení vzniklé s rámem má zoom 1 a pan 0, protože
// `applyPageView()` je s rámem vynuluje, takže vypnutí rámu ho neposune.)
//
// Jak přidat další změnu vzhledu: zvyš PRESENTATION_REV a přidej do
// `runMigrations()` krok, který stará data převede na PŘEDCHOZÍ vzhled.
// Nikdy neměň výchozí vzhled „jen tak" — vždycky přes migraci s revizí.

import {
  dbGetAllSongs, dbSaveSong,
  dbGetAllPageViews, dbSavePageView,
  dbGetSongView, dbSaveSongView,
} from './db.js';

export const PRESENTATION_REV = 2;
const REV_KEY = 'noty.presentationRev';

function readRev() {
  try { return Number(localStorage.getItem(REV_KEY)) || 0; } catch (e) { return 0; }
}
function writeRev(rev) {
  try { localStorage.setItem(REV_KEY, String(rev)); } catch (e) { /* privátní režim */ }
}

// Rev 2: vypnout ořez (rám) všude, kde ho zapsal vývoj — na skladbě,
// na uloženém zobrazení skladby i na uložených zobrazeních stránek.
async function rev2FrameOff() {
  let changed = 0;
  const songs = await dbGetAllSongs();
  for (const s of songs) {
    if (!s || !s.id) continue;
    if (s.frame) { await dbSaveSong({ ...s, frame: 0 }); changed++; }
    const pvs = await dbGetAllPageViews(s.id);
    for (const pv of pvs) {
      if (!pv || !pv.frame) continue;
      await dbSavePageView({ ...pv, frame: 0 });
      changed++;
    }
    const sv = await dbGetSongView(s.id);
    if (sv && sv.frame) { await dbSaveSongView({ ...sv, frame: 0 }); changed++; }
  }
  return changed;
}

// Spustí všechny kroky, které ještě neproběhly. Volá se jednou při startu appky,
// PŘED mountem, aby se žádná skladba neotevřela ve starém (novém) vzhledu.
export async function runPresentationMigrations() {
  const rev = readRev();
  if (rev >= PRESENTATION_REV) return { rev, changed: 0 };
  let changed = 0;
  if (rev < 2) {
    try { changed += await rev2FrameOff(); }
    catch (e) { console.warn('[vzhled] migrace rev2 selhala', e); }
  }
  writeRev(PRESENTATION_REV);
  if (changed) console.info('[vzhled] vrácen původní vzhled u ' + changed + ' záznamů');
  return { rev: PRESENTATION_REV, changed };
}
