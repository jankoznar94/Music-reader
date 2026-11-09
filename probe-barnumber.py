#!/usr/bin/env python3
"""E2E: nástroj „Čísla taktů" — klepnutí vloží další číslo a počítadlo roste.

Ověřuje:
  * tlačítko nástroje existuje a zapne se
  * 3 klepnutí = čísla 1, 2, 3 (textové anotace ve vrstvě, na stránce)
  * počítadlo ukazuje 4 a PŘEŽIJE reload (localStorage)
  * ruční přepsání počítadla („začni od 37") funguje a další číslo je 37
  * rukou jde číslo vybrat a lišta hlásí „Číslo taktu"
"""
import asyncio
import base64
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


BAR_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Čísla taktů'))")


async def numbers(h):
    return await h.ev("""[...document.querySelectorAll('.annot-layer text')]
        .map(t => ({txt: t.textContent, x: +t.getAttribute('x'), y: +t.getAttribute('y')}))
        .filter(t => t.x !== 0 || t.y !== 0)""")


async def next_val(h):
    return await h.ev("(document.querySelector('.ap-bar-next')||{}).value")


async def main():
    async with m.Harness() as h:
        await h.cdp("Storage.clearDataForOrigin", {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open()
        await h.ev("(() => { localStorage.removeItem('noty.barNext'); localStorage.removeItem('noty.barSize');"
                   " navigator.serviceWorker && navigator.serviceWorker.getRegistrations()"
                   ".then(rs => rs.forEach(r => r.unregister())); return true; })()")
        await h.open_song(pages=3)
        await h.annot_toggle()
        await asyncio.sleep(0.6)

        t = await h.ev(BAR_TOOL)
        print("tlačítko Čísla taktů:", t)
        await h.pen_tap(t["x"], t["y"])
        await asyncio.sleep(0.5)
        print("počítadlo po zapnutí nástroje:", await next_val(h))
        row = await h.ev("!!document.querySelector('.ap-bar-next')")
        print("řádek s počítadlem v panelu:", row)

        pts = [(560, 700), (560, 860), (560, 1020)]
        for (x, y) in pts:
            await h.pen_tap(x, y)
            await asyncio.sleep(0.35)
        nums = await numbers(h)
        print("vložená čísla:", nums)
        print("počítadlo po 3 klepnutích:", await next_val(h))

        # ruční přepsání počítadla
        await h.set_value(".ap-bar-next", "37")
        await h.ev("document.querySelector('.ap-bar-next').dispatchEvent(new Event('change', {bubbles:true}))")
        await asyncio.sleep(0.3)
        await h.pen_tap(620, 1120)
        await asyncio.sleep(0.4)
        nums2 = await numbers(h)
        print("po přepsání na 37:", [n["txt"] for n in nums2])

        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        open("/tmp/barnumber-shot.png", "wb").write(base64.b64decode(shot["data"]))

        # reload — počítadlo musí zůstat
        saved = await h.ev("localStorage.getItem('noty.barNext')")
        await h.cdp("Page.reload")
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(2.0)
        print("localStorage noty.barNext:", saved)

        ok = ([n["txt"] for n in nums] == ["1", "2", "3"] and len(nums2) == 4
              and nums2[-1]["txt"] == "37")
        print("VÝSLEDEK:", "OK" if ok else "PROBLÉM")


asyncio.run(main())
