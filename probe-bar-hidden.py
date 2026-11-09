#!/usr/bin/env python3
"""E2E: přepínač VIDITELNÁ / SKRYTÁ čísla taktů.

Pro noty, kde jsou čísla taktů už VYTISKNUTÁ: čísla se vloží, ale v notách
nejsou vidět (nezdvojují se) a slouží jen ke skoku na takt. Přepínač je kdykoli
zase zobrazí (a schová) — platí pro VŠECHNA vložená čísla, ne jen pro nová.

Ověřuje:
  * přepínač existuje, hlásí stav a přepíná se
  * ve stavu „skrytá“ nejsou čísla v notách vidět, ale jsou v indexu (skok jde)
  * přepnutí na „viditelná“ je zobrazí VŠECHNA (i ta vložená dřív)
  * přepnutí zpět je zase schová
  * volba se pamatuje v localStorage
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
TOGGLE = center("document.querySelector('.bar-hidden')")


async def vis(h):
    return await h.ev("""[...document.querySelectorAll('.annot-layer text')]
        .filter(t => +t.getAttribute('x') !== 0 || +t.getAttribute('y') !== 0)
        .map(t => t.textContent)""")


async def label(h):
    return (await h.ev("document.querySelector('.bar-hidden').textContent")).strip()


async def jump(h, n):
    await h.ev("document.querySelector('.tb-page').click()")
    await h.wait_for("!!document.querySelector('.pg-bar-go')", timeout=8, label="dialog")
    for _ in range(80):
        if not await h.ev("""[...document.querySelectorAll('.page-go .pg-hint')]
                .some(e => e.textContent.includes('Načítám čísla taktů'))"""):
            break
        await asyncio.sleep(0.25)
    await h.set_value(".pg-bar-go", str(n))
    btn = await h.ev(center("[...document.querySelectorAll('.pg-btn')].find(b => b.textContent.trim() === 'Takt')"))
    await h.pen_tap(btn["x"], btn["y"])
    await asyncio.sleep(1.2)
    return await h.ev("(document.querySelector('.viewer-toast')||{}).textContent || ''")


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
        t = await h.ev(BAR_TOOL)
        await h.pen_tap(t["x"], t["y"])
        await asyncio.sleep(0.5)
        print("výchozí stav:", await label(h))
        if await label(h) != "Čísla: viditelná":
            fails.append("výchozí stav není 'viditelná'")

        # přepni na skrytá a vlož tři čísla obdélníkem
        tg = await h.ev(TOGGLE)
        await h.pen_tap(tg["x"], tg["y"])
        await asyncio.sleep(0.4)
        print("po přepnutí:", await label(h))
        if await label(h) != "Čísla: skrytá":
            fails.append("přepínač nepřešel do 'skrytá'")
        for y in (880, 980, 1080):
            await h.pen_down(470, y)
            await h.pen_move(600, y + 25)
            await h.pen_up(600, y + 25)
            await asyncio.sleep(0.35)
        cnt = await h.ev("window.__navdbg().annotCount")
        v = await vis(h)
        print("anotací:", cnt, "| vidět v notách:", v)
        if cnt != 3:
            fails.append("nevložila se 3 čísla (je %s)" % cnt)
        if v:
            fails.append("skrytá čísla jsou v notách vidět: %s" % v)

        toast = await jump(h, 2)
        print("skok na takt 2 (skryté číslo):", toast)
        if "Takt 2" not in toast and "taktu 2" not in toast:
            fails.append("skok podle skrytého čísla nefunguje (%s)" % toast)

        # zpět na viditelná → všechna tři se objeví
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        t = await h.ev(BAR_TOOL)
        if t:
            await h.pen_tap(t["x"], t["y"])
            await asyncio.sleep(0.4)
        tg = await h.ev(TOGGLE)
        if not tg:
            fails.append("panel s přepínačem není otevřený")
        else:
            await h.pen_tap(tg["x"], tg["y"])
            await asyncio.sleep(0.5)
            print("po přepnutí zpět:", await label(h), "| vidět:", await vis(h))
            if await label(h) != "Čísla: viditelná":
                fails.append("nepřepnul zpět na viditelná")
            if len(await vis(h)) != 3:
                fails.append("po přepnutí na viditelná nejsou vidět všechna čísla (%s)" % await vis(h))

            # a zase schovat
            await h.pen_tap(tg["x"], tg["y"])
            await asyncio.sleep(0.5)
            if await vis(h):
                fails.append("po opětovném skrytí jsou čísla pořád vidět")
            print("po opětovném skrytí vidět:", await vis(h))

        saved = await h.ev("localStorage.getItem('noty.barHidden')")
        print("localStorage noty.barHidden:", saved)
        if saved != "1":
            fails.append("volba se nepamatuje")

        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
