#!/usr/bin/env python3
"""Skoky v číslování stránek (vynechané stránky sólistů) — Jan, Oct 2026.

Jan: „Často se stává, že máme noty, kde jsou vynechány stránky sólistů. Jsou tam
tedy skoky v číslech. Appka ale logicky nebere tyhle skoky v potaz. Po prvním
skoku už tedy čísla stránek na papíře a v počítadle v appce nesedí. … Přidali
možnost na libovolných stránkách změnit počítadlo, od dané stránky by se
posunulo.“

Sonda jede na SKUTEČNÉM dev serveru a měří, co uživatel vidí (počítadlo, pás
miniatur, skok na zadané číslo, OBSAH canvasu). Scénář:

  1. 6stránková skladba: počítadlo „1 / 6“
  2. na 6. stránce se řekne „tato stránka má číslo 11“ → skok +5
     → počítadlo „11 / 11“, miniatury 1,2,3,4,5,11, canvas dál kreslí TUTÉŽ stránku
  3. stránky PŘED skokem se nemění (3. stránka hlásí „3“ a kreslí sebe)
  4. zadání čísla 11 v dialogu Přejít na stránku skončí na POSLEDNÍ stránce PDF
     (ne na 11. listu, který neexistuje)
  5. druhý skok: na 4. stránce „má číslo 7“ (+3) → čísluje se 1,2,3,7,8,14
     a skoky se sčítají (kumulativně)
  6. seznam skoků v dialogu ukazuje OBA skoky
  7. skoky se ukládají na skladbu (přežijí reload)
  8. „Zrušit“ u jednoho skoku vrátí číslování za ním

    scripts/run-probe-fresh.sh scripts/probe-number-jumps.py
    # a proti živému webu (smí se spustit i s otevřeným přihlášením, data jsou lokální):
    NOTY_APP=https://harlequin-music-reader.web.app/ scripts/run-probe-fresh.sh scripts/probe-number-jumps.py

⚠️ Na živém webu NEEXISTUJE `__navdbg` (jen DEV build) — proto sonda ověřuje
KTERÁ stránka je vykreslená otiskem pixelů canvasu, ne indexem do PDF.
"""
import asyncio
import importlib.util
import json
import os

_CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
# Volitelně proti ŽIVÉMU webu. Bez odregistrování starého service workeru by
# sonda měřila STAROU verzi appky (vzor v references/harness-traps.md).
LIVE = os.environ.get("NOTY_APP")


def _load_harness():
    for cand in (
        os.path.expanduser("~/noty-app/cdp-e2e-harness.py"),
        "/home/martin_fabian/noty-app/cdp-e2e-harness.py",
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_m = _load_harness()
_m.CDP_HTTP = _CDP
Check = _m.Check

# Otisk viditelného canvasu (FNV-1a přes pixely) — spolehlivě řekne, KTERÁ
# stránka je vykreslená, i když počítadlo hlásí totéž číslo v obou případech.
HASH_JS = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas');
  if (!c || !c.width || !c.height) return 0;
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let h = 2166136261;
  for (let i = 0; i < d.length; i += 971) { h ^= d[i]; h = (h * 16777619) >>> 0; }
  return h;
})()
"""


async def settled_hash(h, timeout=6.0, poll=0.15):
    """Otisk canvasu po ustálení (render je asynchronní); prázdný canvas = 0."""
    seq, last, stable, waited = [], 0, 0, 0.0
    while waited < timeout:
        v = await h.ev(HASH_JS)
        if v:
            seq.append(v)
            if v == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = v
        await asyncio.sleep(poll)
        waited += poll
    return last


async def counter(h):
    return await h.ev("document.querySelector('.tb-page').textContent.trim()")


async def thumbs(h):
    """Čísla v pásu miniatur (co uživatel vidí pod dlaždicemi)."""
    await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
               ".find(x => (x.title || '').includes('Slider')); if (b) b.click(); })()")
    await asyncio.sleep(1.3)
    nums = await h.ev("[...document.querySelectorAll('.thumb-num')]"
                      ".map(e => e.textContent.trim()).join(',')")
    await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
               ".find(x => (x.title || '').includes('Slider')); if (b) b.click(); })()")
    await asyncio.sleep(0.4)
    return nums


async def close_dialog(h):
    await h.ev("(() => { const b = [...document.querySelectorAll('.pg-btn')]"
               ".find(x => (x.textContent || '').trim() === 'Zavřít'); if (b) b.click(); })()")
    await asyncio.sleep(0.4)


async def open_page_dialog(h):
    await h.click(".tb-page")
    await h.wait_for("!!document.querySelector('.pg-input')", timeout=6, label="page dialog")


async def set_number_here(h, value):
    """Pole „Tato stránka má číslo“ = DRUHÉ .pg-offset-input v dialogu."""
    await open_page_dialog(h)
    n_inputs = await h.ev("document.querySelectorAll('.pg-offset-input').length")
    await h.ev("""(() => { const els = document.querySelectorAll('.pg-offset-input');
        const el = els[els.length - 1];
        el.value = %s; el.dispatchEvent(new Event('input', { bubbles: true }));
        return el.value; })()""" % json.dumps(str(value)))
    clicked = await h.ev("""(() => { const b = [...document.querySelectorAll('.pg-offset .pg-btn')]
        .find(x => (x.textContent || '').trim() === 'Nastavit odsud');
        if (!b) return false; b.click(); return true; })()""")
    await asyncio.sleep(0.9)
    await close_dialog(h)
    return n_inputs, clicked


async def jump_rows(h):
    """Řádky seznamu skoků v dialogu (co je vidět)."""
    await open_page_dialog(h)
    rows = await h.ev("[...document.querySelectorAll('.pg-jumps .jp-item')]"
                      ".map(e => e.textContent.replace(/\\s+/g, ' ').trim())")
    return rows


async def song_jumps(h):
    """Skoky uložené na PRÁVĚ OTEVŘENÉ skladbě (id je v URL) — čteme z IDB.
    POZOR: ne getAll()[0] — v DB může být víc skladeb a pořadí klíčů je
    náhodné, takže by sonda četla jinou skladbu a hlásila falešný FAIL."""
    expr = """
    new Promise((resolve) => {
      const id = location.pathname.split('/').pop();
      const q = indexedDB.open('noty-app');
      q.onsuccess = () => {
        const r = q.result.transaction('songs', 'readonly').objectStore('songs').get(id);
        r.onsuccess = () => resolve(JSON.stringify(r.result ? (r.result.numberJumps || null) : null));
        r.onerror = () => resolve('r.onerror');
      };
      q.onerror = () => resolve('q.onerror');
    })
    """
    raw = await h.ev(expr, await_promise=True)
    return json.loads(raw) if raw else None


async def main():
    ok = Check()
    h = _m.Harness(url=LIVE) if LIVE else _m.Harness()
    if LIVE:
        print("   cíl:", LIVE)
    async with h:
        await h.open()
        if LIVE:
            # Na živém webu sundat service worker i cache — jinak by sonda měřila
            # starou verzi z precache.
            await h.ev("(async () => { const rs = await navigator.serviceWorker.getRegistrations();"
                       " for (const r of rs) await r.unregister();"
                       " for (const k of await caches.keys()) await caches.delete(k);"
                       " return true; })()", await_promise=True)
            await asyncio.sleep(1.0)
            await h.open()
        await h.open_song(pdf=_m.make_pdf(6))

        c = await counter(h)
        ok("1) počítadlo na začátku hlásí „1 / 6“", c.startswith("1 / 6"), c)

        # otisky stránek, které budeme potřebovat jako referenci
        await h.goto(3)
        fp3 = await settled_hash(h)
        c3 = await counter(h)
        await h.goto(6)
        fp6 = await settled_hash(h)
        ok("2) otisky stránek se liší (měření obsahu canvasu funguje)",
           bool(fp3) and bool(fp6) and fp3 != fp6, f"str.3={fp3} str.6={fp6}")

        # --- 1) skok na 6. stránce: má číslo 11 ---
        n_inputs, clicked = await set_number_here(h, 11)
        ok("3) dialog má ZADÁVACÍ řádek pro skok v číslování", clicked and n_inputs == 2,
           f"polí={n_inputs} klik={clicked}")
        c = await counter(h)
        ok("4) 6. stránka se hlásí jako 11 a počítadlo je „11 / 11“",
           c.startswith("11 / 11"), c)
        fp_now = await settled_hash(h)
        ok("4b) přitom se pořád kreslí TA SAMÁ stránka (skok nic nepřesunul)",
           fp_now == fp6, f"čekáno {fp6}, canvas {fp_now}")
        t = await thumbs(h)
        ok("5) miniatury číslují 1,2,3,4,5,11 (díra po vynechaných stránkách)",
           t == "1,2,3,4,5,11", str(t))

        # --- 2) stránky před skokem se nesmí změnit ---
        await h.goto(3)
        c = await counter(h)
        ok("6) 3. stránka hlásí dál „3“ (skok působí od své stránky dál) a kreslí sebe",
           c.startswith("3 / 11") and (await settled_hash(h)) == fp3, c)

        # --- 3) zadání čísla 11 musí skončit na POSLEDNÍ stránce PDF ---
        await h.goto(11)
        c = await counter(h)
        ok("7) zadání čísla 11 skončí na poslední stránce PDF (canvas = str. 6)",
           c.startswith("11 / 11") and (await settled_hash(h)) == fp6, c)

        # --- 4) druhý skok: 4. stránka má číslo 7 (+3), skoky se sčítají ---
        await h.goto(4)
        fp4 = await settled_hash(h)
        _, clicked = await set_number_here(h, 7)
        ok("8) druhý skok se nastavil", clicked, json.dumps(clicked))
        c = await counter(h)
        ok("9) 4. stránka se hlásí jako 7 a součet je „7 / 14“", c.startswith("7 / 14"), c)
        fp_now = await settled_hash(h)
        ok("9b) a pořád se kreslí 4. stránka", fp_now == fp4, f"čekáno {fp4}, canvas {fp_now}")
        t = await thumbs(h)
        ok("10) miniatury sčítají oba skoky: 1,2,3,7,8,14",
           t == "1,2,3,7,8,14", str(t))

        # --- 5) seznam skoků v dialogu ---
        rows = await jump_rows(h)
        ok("11) dialog vypisuje oba skoky (+3 od 4., +5 od 6. stránky)",
           len(rows) == 2 and "+3" in rows[0] and "+5" in rows[1], json.dumps(rows))
        await close_dialog(h)

        # --- 6) uložení na skladbu ---
        saved = await song_jumps(h)
        ok("12) skoky se uložily na skladbu (indexy do PDF, ne pořadí)",
           saved == [{"page": 3, "delta": 3}, {"page": 5, "delta": 5}], json.dumps(saved))

        # --- 7) přežije reload ---
        await h.cdp("Page.reload", {"ignoreCache": False})
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="viewer po reloadu")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="stránka")
        await asyncio.sleep(1.2)
        # POZOR: zadává se číslo, které uživatel VIDÍ — číslo 4 v tomhle číslování
        # neexistuje (je v díře), takže se chodí na „7“.
        await h.goto(7)
        c = await counter(h)
        ok("13) po reloadu číslování drží (stránka s číslem 7, „7 / 14“)",
           c.startswith("7 / 14") and (await settled_hash(h)) == fp4, c)

        # --- 8) zrušení jednoho skoku ---
        rows = await jump_rows(h)
        removed = await h.ev("""(() => { const rows = [...document.querySelectorAll('.pg-jumps .jp-item')];
            const row = rows.find(r => /\\+3/.test(r.textContent));
            if (!row) return false;
            const b = row.querySelector('.jp-btn'); if (!b) return false;
            b.click(); return true; })()""")
        await asyncio.sleep(0.9)
        await close_dialog(h)
        c = await counter(h)
        ok("14) po zrušení skoku +3 se tatáž stránka hlásí „4“ a součet „4 / 11“",
           removed and c.startswith("4 / 11") and (await settled_hash(h)) == fp4,
           f"zrušeno={removed} počítadlo={c}")
        t = await thumbs(h)
        ok("15) miniatury zpět na 1,2,3,4,5,11", t == "1,2,3,4,5,11", str(t))
        saved = await song_jumps(h)
        ok("16) v datech zůstal jen druhý skok",
           saved == [{"page": 5, "delta": 5}], json.dumps(saved))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
