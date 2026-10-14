#!/usr/bin/env python3
"""Skoky v číslování stránek (vynechané stránky sólistů) — Jan, Oct 2026.

Jan: „Často se stává, že máme noty, kde jsou vynechány stránky sólistů. Jsou tam
tedy skoky v číslech. Appka ale logicky nebere tyhle skoky v potaz. Po prvním
skoku už tedy čísla stránek na papíře a v počítadle v appce nesedí. … Přidali
možnost na libovolných stránkách změnit počítadlo, od dané stránky by se
posunulo.“

Sonda jede na SKUTEČNÉM dev serveru a měří, co uživatel vidí (počítadlo, pás
miniatur, skok na zadané číslo). Scénář:

  1. 6stránková skladba: počítadlo „1 / 6“
  2. na 6. stránce se řekne „tato stránka má číslo 11“ → skok +5
     → počítadlo „11 / 11“, miniatury 1,2,3,4,5,11
  3. stránky PŘED skokem se nemění (3. stránka hlásí „3“)
  4. zadání čísla 11 v dialogu Přejít na stránku skončí na POSLEDNÍ stránce PDF
     (ne na 11. listu, který neexistuje)
  5. druhý skok: na 4. stránce „má číslo 7“ (+3) → čísluje se 1,2,3,7,8,14
     a skoky se sčítají (kumulativně)
  6. seznam skoků v dialogu ukazuje OBA skoky
  7. skoky se ukládají na skladbu (přežijí reload)
  8. „Zrušit“ u jednoho skoku vrátí číslování za ním

    scripts/run-probe-fresh.sh scripts/probe-number-jumps.py
"""
import asyncio
import importlib.util
import json
import os

_CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


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
Harness, Check = _m.Harness, _m.Check


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


async def pdf_page(h):
    """Aktuální stránka jako index do PDF (__navdbg existuje jen v DEV buildu)."""
    raw = await h.ev("JSON.stringify(window.__navdbg ? {page: window.__navdbg().page} : null)")
    return (json.loads(raw) or {}).get("page") if raw else None


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
        r.onsuccess = () => resolve(JSON.stringify(r.result ? (r.result.numberJumps || null) : 'NENALEZENA'));
        r.onerror = () => resolve('r.onerror');
      };
      q.onerror = () => resolve('q.onerror');
    })
    """
    raw = await h.ev(expr, await_promise=True)
    return json.loads(raw) if raw else None


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))

        c = await counter(h)
        ok("1) počítadlo na začátku hlásí „1 / 6“", c.startswith("1 / 6"), c)

        # --- 1) skok na 6. stránce: má číslo 11 ---
        await h.goto(6)
        ok("2) jsme na 6. stránce PDF", (await pdf_page(h)) == 5, f"page={await pdf_page(h)}")
        n_inputs, clicked = await set_number_here(h, 11)
        ok("2b) dialog má ZADÁVACÍ řádek pro skok v číslování", clicked and n_inputs == 2,
           f"polí={n_inputs} klik={clicked}")
        c = await counter(h)
        ok("3) 6. stránka se hlásí jako 11 a počítadlo je „11 / 11“",
           c.startswith("11 / 11"), c)
        t = await thumbs(h)
        ok("4) miniatury číslují 1,2,3,4,5,11 (díra po vynechaných stránkách)",
           t == "1,2,3,4,5,11", str(t))

        # --- 2) stránky před skokem se nesmí změnit ---
        await h.goto(3)
        c = await counter(h)
        ok("5) 3. stránka hlásí dál „3“ (skok působí od své stránky dál)",
           c.startswith("3 / 11"), c)

        # --- 3) zadání čísla 11 musí skončit na POSLEDNÍ stránce PDF ---
        await h.goto(11)
        c = await counter(h)
        pg = await pdf_page(h)
        ok("6) zadání čísla 11 skončí na poslední stránce PDF (index 5) a hlásí „11 / 11“",
           c.startswith("11 / 11") and pg == 5, f"počítadlo={c} page={pg}")

        # --- 4) druhý skok: 4. stránka má číslo 7 (+3), skoky se sčítají ---
        await h.goto(4)
        _, clicked = await set_number_here(h, 7)
        ok("7) druhý skok se nastavil", clicked, json.dumps(clicked))
        c = await counter(h)
        ok("8) 4. stránka se hlásí jako 7 a součet je „7 / 14“", c.startswith("7 / 14"), c)
        t = await thumbs(h)
        ok("9) miniatury sčítají oba skoky: 1,2,3,7,8,14",
           t == "1,2,3,7,8,14", str(t))

        # --- 5) seznam skoků v dialogu ---
        rows = await jump_rows(h)
        ok("10) dialog vypisuje oba skoky (+3 od 4., +5 od 6. stránky)",
           len(rows) == 2 and "+3" in rows[0] and "+5" in rows[1], json.dumps(rows))
        await close_dialog(h)

        # --- 6) uložení na skladbu ---
        saved = await song_jumps(h)
        ok("11) skoky se uložily na skladbu (indexy do PDF)",
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
        ok("12) po reloadu číslování drží (stránka s číslem 7, „7 / 14“)",
           c.startswith("7 / 14"), c)

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
        ok("13) po zrušení skoku +3 se tatáž stránka hlásí „4“ a součet „4 / 11“",
           removed and c.startswith("4 / 11"), f"zrušeno={removed} počítadlo={c}")
        t = await thumbs(h)
        ok("14) miniatury zpět na 1,2,3,4,5,11", t == "1,2,3,4,5,11", str(t))
        saved = await song_jumps(h)
        ok("15) v datech zůstal jen druhý skok",
           saved == [{"page": 5, "delta": 5}], json.dumps(saved))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
