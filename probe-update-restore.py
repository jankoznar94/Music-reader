#!/usr/bin/env python3
"""Návrat na stejnou stránku po aktualizaci appky (Jan, 27. 11. 2026).

Chyba: po ťuknutí na „Aktualizovat“ se prohlížeč vrátil vždy na 1. stránku.
Příčina: `noty.lastPos` se při startu přepsal první vykreslenou stránkou dřív,
než se stihla obnovit pozice (mount mění `currentPage`, visí na něm ukládání).
Oprava: pozice se zamrazí při ťuknutí na Aktualizovat (`noty.updatePos`) a při
startu se čte snímek z prvního okamžiku mountu; značka se maže až skutečným
listováním, takže ani druhý start těsně po aktualizaci nespadne na jedničku.

Ověřuje:
  1. běžné otevření = 1. stránka,
  2. aktualizace z 5. stránky → po restartu 5. stránka,
  3. druhý start těsně po ní → pořád 5. stránka,
  4. listování uživatele značku smaže → další start = 1. stránka,
  5. RACE: se skrytou 1. stránkou mount mění `currentPage` (0 → 1) — návrat
     musí i tak trefit uloženou stránku, ne jedničku.
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness, Check, make_pdf = m.Harness, m.Check, m.make_pdf

APP = os.environ.get("APP_URL", "http://localhost:5173/")

APPLY_UPDATE = ("import('/src/update.js').then(mod => mod.applyUpdate().then(() => 'ok')"
                ".catch(e => 'err ' + e))")


async def boot(h):
    """Po reloadu otevři skladbu v knihovně (test prochazí vždy stejnou)."""
    await h.wait_for("!!document.querySelector('.tb-page') || !!document.querySelector('.song-name')",
                     timeout=60, label="app after boot")
    if not await h.ev("!!document.querySelector('.tb-page')"):
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=20, label="songs")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=60, label="viewer")
    await h.wait_for("!document.querySelector('.viewer-loading')", timeout=60, label="render")
    await asyncio.sleep(1.2)


async def main():
    ok = Check()
    async with Harness(APP) as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(make_pdf(6), pages=6, reset=True)
        await boot(h)

        ok("běžné otevření = 1. stránka", (await h.page_text()).startswith("1 /"), await h.page_text())

        # --- aktualizace z 5. stránky ---
        await h.goto(5)
        await asyncio.sleep(0.8)
        ok("před aktualizací jsme na 5. stránce", (await h.page_text()).startswith("5 /"),
           await h.page_text())
        ok("lastPos odpovídá", json.loads(await h.ev("localStorage.getItem('noty.lastPos')"))["page"] == 4,
           await h.ev("localStorage.getItem('noty.lastPos')"))

        print("applyUpdate:", await h.ev(APPLY_UPDATE, await_promise=True))
        await asyncio.sleep(6)
        await boot(h)
        ok("po aktualizaci se vrací na 5. stránku", (await h.page_text()).startswith("5 /"),
           await h.page_text())
        ok("updatePos zůstává pro případ dalšího startu",
           bool(await h.ev("localStorage.getItem('noty.updatePos')")), "")

        # --- druhý start těsně po aktualizaci ---
        await h.ev("location.reload()")
        await asyncio.sleep(5)
        await boot(h)
        ok("druhý start těsně po aktualizaci zůstává na 5. stránce",
           (await h.page_text()).startswith("5 /"), await h.page_text())

        # --- listování uživatele značku smaže ---
        await h.goto(2)
        await asyncio.sleep(0.8)
        ok("listování uživatele značku smazalo",
           not await h.ev("localStorage.getItem('noty.updatePos')")
           and not await h.ev("localStorage.getItem('noty.restoreAfterUpdate')"),
           await h.ev("localStorage.getItem('noty.updatePos')"))
        await h.ev("location.reload()")
        await asyncio.sleep(5)
        await boot(h)
        ok("po listování se další start otevírá na 1. stránce",
           (await h.page_text()).startswith("1 /"), await h.page_text())

        # --- RACE: skrytá 1. stránka → mount mění currentPage (0 → 1) ---
        song = await h.ev("""new Promise((res) => { const q = indexedDB.open('noty-app');
          q.onsuccess = () => { const t = q.result.transaction('songs', 'readonly').objectStore('songs').getAll();
          t.onsuccess = () => res(t.result[0].id); }; })""", await_promise=True)
        await h.ev("""((id) => new Promise((res) => { const q = indexedDB.open('noty-app');
          q.onsuccess = () => { const db = q.result; const g = db.transaction('songs').objectStore('songs').get(id);
          g.onsuccess = () => { const s = g.result; s.hiddenPages = [0];
            const t = db.transaction('songs', 'readwrite'); t.objectStore('songs').put(s);
            t.oncomplete = () => res(true); }; }; }))(%s)""" % json.dumps(song), await_promise=True)
        await h.ev("location.reload()")
        await asyncio.sleep(5)
        await boot(h)
        ok("se skrytou 1. stránkou startuje prohlížeč na 1. viditelné stránce",
           (await h.page_text()).startswith("1 /"), await h.page_text())

        await h.goto(4)
        await asyncio.sleep(0.8)
        before = await h.page_text()
        print("applyUpdate (race):", await h.ev(APPLY_UPDATE, await_promise=True))
        await asyncio.sleep(6)
        await boot(h)
        after = await h.page_text()
        ok("RACE: návrat trefí uloženou stránku, ne jedničku", after == before, f"{before} -> {after}")

        errs = await h.ev("(window.__errs||[]).length")
        ok("žádné chyby v konzoli", errs in (0, None), str(errs))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
