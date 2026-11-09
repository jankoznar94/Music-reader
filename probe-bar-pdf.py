#!/usr/bin/env python3
"""E2E: čísla taktů PŘEČTENÁ Z PDF (textová vrstva) + skok na ně.

Používá reálné noty (LilyPond PDF): /tmp/noty-2p.pdf
  strana 1: čísla 6, 11, 16   |   strana 2: číslo 17

Ověřuje:
  * index se naplní bez jediné ruční anotace (hint „Známých taktů: 4 … z PDF 4")
  * skok na 17 → strana 2
  * skok na 14 (mezi 11 a 16) → nejbližší 16 → strana 1
  * skok na 6 → strana 1
"""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

PDF = "/tmp/noty-2p.pdf"


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


async def page_no(h):
    return (await h.ev("document.querySelector('.tb-page').textContent")).strip()


async def open_dialog(h):
    await h.ev("document.querySelector('.tb-page').click()")
    await h.wait_for("!!document.querySelector('.pg-bar-go')", timeout=8, label="dialog")
    # počkej, až doběhne čtení textové vrstvy
    for _ in range(60):
        if not await h.ev("""[...document.querySelectorAll('.page-go .pg-hint')]
                .some(e => e.textContent.includes('Načítám čísla taktů'))"""):
            break
        await asyncio.sleep(0.25)


async def hint(h):
    return await h.ev("""[...document.querySelectorAll('.page-go .pg-hint')].map(e => e.textContent.trim()).join(' | ')""")


async def jump(h, n):
    await open_dialog(h)
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
        await h.set_tablet()
        await h.set_file_input("input[type=file]", PDF)
        await h.wait_for("document.querySelectorAll('.author-group').length > 0", timeout=60, label="PDF")
        await h.ev(h.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=10, label="knihovna")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="prohlížeč")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="stránka")
        await asyncio.sleep(1.0)

        await open_dialog(h)
        text = await hint(h)
        print("hint:", text)
        if "z PDF 4" not in text:
            fails.append("index z PDF není 4 čísla (%s)" % text)
        await h.ev("[...document.querySelectorAll('.pg-btn')].find(b => b.textContent.trim() === 'Zavřít').click()")
        await asyncio.sleep(0.4)

        r = await jump(h, 17)
        print("skok na 17:", r)
        if r[0] != "2 / 2":
            fails.append("takt 17 neměl skočit na stranu 2 (%s)" % r[0])
        r = await jump(h, 14)
        print("skok na 14 (mezi 11 a 16):", r)
        if r[0] != "1 / 2" or "nejbližší známý 16" not in r[1]:
            fails.append("takt 14 neměl skončit na 16 (%s | %s)" % (r[0], r[1]))
        r = await jump(h, 6)
        print("skok na 6:", r)
        # na stránce 1 už stojíme → hláška „Už jsi na taktu 6“ je správně
        if "Takt 6" not in r[1] and "taktu 6" not in r[1]:
            fails.append("takt 6 nebyl nalezen přesně (%s)" % r[1])

        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
