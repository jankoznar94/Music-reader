#!/usr/bin/env python3
"""E2E: mazání jednotlivých čísel taktů nástrojem Ruka.

Jan (Nov 2026): „Číslování by mělo být možné nějak smazat, ne hromadně, ale
libovolně zvlášť… mohlo by to reagovat alespoň na nástroj ruka. Po odstranění
to zmizí i z možnosti na daný takt skočit.“

Ověřuje:
  * v režimu Ruka jde číslo taktu ťuknutím vybrat (lišta hlásí „Číslo taktu“)
  * tlačítko 🗑 ho smaže — počet anotací klesne
  * smazaný takt zmizí z indexu skoku (skok na něj hlásí nejbližší známý)
  * funguje i pro SKRYTÁ čísla (ta jsou vidět jen v režimu Ruka)
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
HAND_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Upravit'))")
BAR_HIDDEN = center("document.querySelector('.bar-hidden')")


async def count(h):
    return await h.ev("window.__navdbg().annotCount")


async def texts(h):
    return await h.ev("""[...document.querySelectorAll('.annot-layer text')]
        .filter(t => +t.getAttribute('x') !== 0 || +t.getAttribute('y') !== 0)
        .map(t => { const r = t.getBoundingClientRect();
          return {txt: t.textContent, left: Math.round(r.left), top: Math.round(r.top),
                  cx: Math.round(r.left + r.width/2), cy: Math.round(r.top + r.height/2)}; })""")


async def jump_toast(h, n):
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
    await asyncio.sleep(1.0)
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

        # skrytá čísla (jako u not s vytištěnými čísly) — 3 kusy: 7, 10, 13
        tg = await h.ev(BAR_HIDDEN)
        await h.pen_tap(tg["x"], tg["y"])
        await asyncio.sleep(0.3)
        await h.set_value(".ap-bar-next:not(.ap-bar-step)", "7")
        await h.ev("document.querySelector('.ap-bar-next:not(.ap-bar-step)').dispatchEvent(new Event('change',{bubbles:true}))")
        await h.set_value(".ap-bar-step", "3")
        await h.ev("document.querySelector('.ap-bar-step').dispatchEvent(new Event('change',{bubbles:true}))")
        await asyncio.sleep(0.3)
        for y in (880, 980, 1080):
            await h.pen_tap(520, y)
            await asyncio.sleep(0.35)
        print("anotací po vložení:", await count(h))
        if await count(h) != 3:
            fails.append("nevložila se 3 čísla (%s)" % await count(h))

        # režim Ruka → skrytá čísla se ukážou (anotace už běží, jen přepnout nástroj)
        hand = await h.ev(HAND_TOOL)
        print("tlačítko Ruka:", bool(hand))
        await h.pen_tap(hand["x"], hand["y"])
        await asyncio.sleep(0.5)
        tx = await texts(h)
        print("čísla v režimu Ruka:", tx)
        if len(tx) != 3:
            fails.append("skrytá čísla nejsou v režimu Ruka vidět (%d)" % len(tx))
            print("VÝSLEDEK: PROBLÉM: " + "; ".join(fails))
            return

        # vyber prostřední (10) a smaž
        mid = tx[1]
        await h.pen_tap(mid["cx"], mid["cy"])
        await asyncio.sleep(0.6)
        bar = await h.ev("(document.querySelector('.edit-bar')||{}).innerText || ''")
        print("lišta úprav:", bar.replace("\\n", " | ")[:120])
        if "Číslo taktu" not in bar:
            fails.append("lišta nehlásí 'Číslo taktu' (je: %s)" % bar[:80])
        trash = await h.ev(center("document.querySelector('.edit-bar .eb-btn[title=\"Smazat\"]')"))
        print("tlačítko 🗑:", bool(trash))
        if not trash:
            fails.append("v liště není tlačítko Smazat")
        else:
            await h.pen_tap(trash["x"], trash["y"])
            await asyncio.sleep(0.8)
            print("anotací po smazání:", await count(h))
            if await count(h) != 2:
                fails.append("po smazání nejsou 2 anotace (%s)" % await count(h))

        # smazaný takt 10 už v indexu není → skok hlásí nejbližší známý
        toast = await jump_toast(h, 10)
        print("skok na smazaný takt 10:", toast)
        if "ejbližší známý" not in toast:
            fails.append("smazaný takt zůstal v indexu (toast: %s)" % toast)

        # ťuknutí kousek VEDLE čísla (8 px) ho v režimu Ruka pořád vybere
        # (dialog stránky anotace vypnul → znovu zapnout a zvolit Ruku)
        if not await h.ev("!!document.querySelector('.ap-tool')"):
            await h.annot_toggle()
            await asyncio.sleep(0.5)
        hand = await h.ev(HAND_TOOL)
        if hand:
            await h.pen_tap(hand["x"], hand["y"])
            await asyncio.sleep(0.45)
        tx = await texts(h)
        one = tx[0]
        await h.pen_tap(one["cx"] + 8, one["cy"] + 6)
        await asyncio.sleep(0.5)
        sel = await h.ev("(document.querySelector('.edit-bar')||{}).innerText || ''")
        print("výběr ťuknutím vedle čísla:", "Číslo taktu" in sel)
        if "Číslo taktu" not in sel:
            fails.append("ťuknutí 8 px vedle čísla ho nevybere")

        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
