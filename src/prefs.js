// src/prefs.js — malé úložiště voleb, které mají přežít VYPNUTÍ appky.
//
// Proč samostatně: `libraryState.js` drží jen stav „na cestě" (vrátit se
// z prohlížeče tam, kde uživatel byl) a po startu se záměrně nuluje. Volby
// zobrazení (seskupení podle skladatelů, řazení…) ale uživatel nechce
// přepínat po každém zapnutí (Jan, listopad 2026), takže patří do
// localStorage — a to na jedno místo, aby přibývání dalších voleb
// neznamenalo další klíč a další try/catch.
const KEY = 'noty.prefs';

/** Všechny uložené volby (objekt). Nikdy nevyhodí — privátní režim = {} */
export function loadPrefs() {
  try {
    const raw = localStorage.getItem(KEY);
    const o = raw ? JSON.parse(raw) : null;
    return o && typeof o === 'object' ? o : {};
  } catch (e) {
    return {};
  }
}

/** Uloží jednu volbu a ostatní nechá být. */
export function savePref(name, value) {
  try {
    const all = loadPrefs();
    all[name] = value;
    localStorage.setItem(KEY, JSON.stringify(all));
  } catch (e) { /* privátní režim — volba prostě nepřežije */ }
}

/** Přečte volbu; když chybí (nebo je mimo povolené hodnoty), vrátí `fallback`. */
export function readPref(name, fallback, allowed) {
  const all = loadPrefs();
  const v = all[name];
  if (v === undefined || v === null) return fallback;
  // Jiný typ než výchozí hodnota = poškozený/starý zápis → výchozí stav.
  if (typeof v !== typeof fallback) return fallback;
  if (allowed && !allowed.includes(v)) return fallback;
  return v;
}
