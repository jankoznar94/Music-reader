#!/usr/bin/env python3
"""E2E: SKOK NA TAKT — index z čísel taktů a přesun na stránku.

Ověřuje:
  * bez čísel taktů dialog hlásí „žádná čísla taktů"
  * přesné číslo taktu → stránka, kde číslo je
  * neexistující číslo → NEJBLIŽŠÍ známý (i při shodné vzdálenosti bere nižší)
  * toast řekne, co se stalo (přesný vs. nejbližší)
  * hledá se jen v části skladby mezi záložkami (mimo ni se najde i vzdálenější)
"""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


BAR_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Čísla taktů'))")



SEED_BM = r"""
((songId) => new Promise((resolve) => {
  const items = [{ id: 'bm-a', page: 0, label: 'A' }, { id: 'bm-b', page: 1, label: 'B' }];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('bookmarks', 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items, manualOrder: true });
    tx.oncomplete = () => resolve(true);
  };
}))(__SONG__)
"""
SONG_ID = """
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('songs', 'readonly').objectStore('songs').getAll();
    r.onsuccess = () => resolve(r.result.length ? r.result[0].id : null);
  };
})
"""

async def page_no(h):
    return (await h.ev("document.querySelector('.tb-page').textContent")).strip()


async def set_next(h, n):
    await h.set_value(".ap-bar-next:not(.ap-bar-step)", str(n))
    await h.ev("document.querySelector('.ap-bar-next:not(.ap-bar-step)').dispatchEvent(new Event('change',{bubbles:true}))")
    await asyncio.sleep(0.2)


async def prep(h):
    """Zapni anotace a znovu zvol nástroj Čísla taktů (dialog/goto je vypne)."""
    if not await h.ev("!!document.querySelector('.ap-tool')"):
        await h.annot_toggle()
        await asyncio.sleep(0.5)
    t = await h.ev(BAR_TOOL)
    if not t:
        return None
    await h.pen_tap(t["x"], t["y"])
    await asyncio.sleep(0.4)
    return t


async def place(h):
    pt = await h.free_point()
    await h.pen_tap(pt["x"], pt["y"])
    await asyncio.sleep(0.35)


async def jump(h, n):
    """Otevři dialog stránky, zadej takt, potvrď; vrať (stránka, toast)."""
    await h.ev("document.querySelector('.tb-page').click()")
    await h.wait_for("!!document.querySelector('.pg-bar-go')", timeout=8, label="dialog")
    await h.set_value(".pg-bar-go", str(n))
    btn = await h.ev(center("[...document.querySelectorAll('.pg-btn')].find(b => b.textContent.trim() === 'Takt')"))
    await h.pen_tap(btn["x"], btn["y"])
    await asyncio.sleep(1.2)
    return [await page_no(h), await h.ev("(document.querySelector('.viewer-toast')||{}).textContent || ''")]


async def main():
    fails = []
    async with m.Harness() as h:
        await h.cdp("Storage.clearDataForOrigin", {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open()
        await h.ev("(() => { localStorage.clear(); navigator.serviceWorker && navigator.serviceWorker"
                   ".getRegistrations().then(rs => rs.forEach(r => r.unregister())); return true; })()")
        await h.open_song(pages=3)
        await h.annot_toggle()
        await asyncio.sleep(0.6)

        # dialog před očíslováním
        await h.ev("document.querySelector('.tb-page').click()")
        await h.wait_for("!!document.querySelector('.pg-bar-go')", timeout=8, label="dialog")
        hint = await h.ev("""[...document.querySelectorAll('.page-go .pg-hint')].map(e => e.textContent).join(' | ')""")
        await h.ev("document.querySelector('.pg-btn') && [...document.querySelectorAll('.pg-btn')].find(b => b.textContent.trim() === 'Zavřít').click()")
        await asyncio.sleep(0.3)
        print("hint bez čísel:", hint)
        if "Zatím žádná čísla taktů" not in hint:
            fails.append("chybí hláška o chybějících číslech")

        # dialog zavřel anotační režim → znovu ho zapni
        await h.annot_toggle()
        await asyncio.sleep(0.5)
        t = await h.ev(BAR_TOOL)
        await h.pen_tap(t["x"], t["y"])
        await asyncio.sleep(0.4)

        # stránka 1: takty 1, 2
        await place(h)
        await place(h)
        # stránka 2: takt 10
        await h.goto(2)
        await asyncio.sleep(0.6)
        await prep(h)
        await set_next(h, 10)
        await place(h)
        # stránka 3: takt 20
        await h.goto(3)
        await asyncio.sleep(0.6)
        await prep(h)
        await set_next(h, 20)
        await place(h)

        idx = await h.ev("window.__navdbg ? 1 : 1")
        print("index v UI:", await h.ev("""(() => { const p = document.querySelector('.pg-bar-go');
            return !!p; })()"""))
        # přesuny
        print("přesun na 10:", await jump(h, 10))
        if (await page_no(h)) != "2 / 3":
            fails.append("takt 10 neskočil na stránku 2 (je %s)" % await page_no(h))
        print("přesun na 20:", await jump(h, 20))
        if (await page_no(h)) != "3 / 3":
            fails.append("takt 20 neskočil na stránku 3")
        print("přesun na 15 (mezi 10 a 20):", await jump(h, 15))
        if (await page_no(h)) != "2 / 3":
            fails.append("takt 15 neměl skočit na nejbližší nižší (10)")
        print("přesun na 4 (mezi 3 a 10):", await jump(h, 4))
        print("stránka po 4:", await page_no(h))

        # --- rozsah na část skladby (záložky) -------------------------------
        # Záložky: A = str. 1, B = str. 2–3. Stojíme na str. 3 (část B).
        # Takt 2 leží v části A → NESMÍ se tam skočit; nejbližší v části B je 10.
        sid = await h.ev(SONG_ID, await_promise=True)
        await h.ev(SEED_BM.replace("__SONG__", __import__("json").dumps(sid)), await_promise=True)
        await h.cdp("Page.reload")
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(2.0)
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="prohlížeč")
        await h.goto(3)
        await asyncio.sleep(0.8)
        r = await jump(h, 2)
        print("s částí B, skok na takt 2 (leží v části A):", r)
        if r[0] != "2 / 3":
            fails.append("skok na takt 2 utekl do jiné části (stránka %s)" % r[0])
        if "nejbližší známý 10" not in r[1]:
            fails.append("u skoku mimo část chybí hláška o nejbližším známém (%s)" % r[1])
        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
