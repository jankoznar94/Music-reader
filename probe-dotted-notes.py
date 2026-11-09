#!/usr/bin/env python3
"""E2E: tečkované rytmy — vloží čtvrtku, půlku a pomlku S TEČKOU přes reálné UI.

Ověřuje, co uživatel opravdu uvidí:
  * v dialogu je přepínač „Tečkovaný rytmus"
  * dlaždice noty vloží notu a k ní se vykreslí KRUH (tečka)
  * tečka sedí VEDLE hlavičky a ve stejné výšce (geometrie z DOM)
  * bez přepínače se kruh nevykreslí
  * screenshot pro vizuální kontrolu
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

OUT = "/tmp/dotted-shot.png"


def center(sel_js):
    return ("(() => { const b = %s; if (!b) return null;"
            " const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2),"
            " title: b.title || b.textContent.trim()}; })()" % sel_js)


async def insert_note(h, x, y, tile_title, dotted=True):
    # nástroj Nota
    pt = await h.ev(center("[...document.querySelectorAll('.ap-tool')].find(e => e.querySelector('.nota-ico'))"))
    await h.pen_tap(pt["x"], pt["y"])
    await asyncio.sleep(0.4)
    await h.pen_tap(x, y)
    await h.wait_for("!!document.querySelector('.text-input-card')", timeout=10, label="dialog noty")
    if dotted:
        tg = await h.ev(center("[...document.querySelectorAll('.ti-row .ti-toggle')]"
                              ".find(e => (e.textContent || '').includes('Tečkovaný'))"))
        if not tg:
            raise RuntimeError("přepínač Tečkovaný rytmus v dialogu není")
        await h.pen_tap(tg["x"], tg["y"])
        await asyncio.sleep(0.3)
        label = await h.ev("(document.querySelector('.text-input-card .ti-note')||{}).textContent || ''")
        print("   popisek v dialogu:", (label or "").strip())
    tile = await h.ev(center("[...document.querySelectorAll('.dyn-btn')].find(e => e.title === %s)"
                             % json.dumps(tile_title)))
    if not tile:
        raise RuntimeError("dlaždice %r nenalezena" % tile_title)
    await h.pen_tap(tile["x"], tile["y"])
    await asyncio.sleep(0.7)


async def dump(h):
    return await h.ev("""(() => {
      const layer = document.querySelector('.annot-layer');
      if (!layer) return {texts: [], circles: []};
      const texts = [...layer.querySelectorAll('text')].map(t => ({
        x: +t.getAttribute('x'), y: +t.getAttribute('y'), size: +t.getAttribute('font-size'),
        ch: t.textContent.codePointAt(0) ? t.textContent.codePointAt(0).toString(16) : null
      }));
      const circles = [...layer.querySelectorAll('circle')].map(c => ({
        cx: +c.getAttribute('cx'), cy: +c.getAttribute('cy'), r: +c.getAttribute('r')
      }));
      return {texts, circles};
    })()""")


async def main():
    async with m.Harness() as h:
        await h.cdp("Storage.clearDataForOrigin", {
            "origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open()
        await h.ev("(() => { navigator.serviceWorker && navigator.serviceWorker.getRegistrations()"
                   ".then(rs => rs.forEach(r => r.unregister())); return true; })()")
        await h.open_song(pages=3)
        await h.annot_toggle()
        await asyncio.sleep(0.6)

        pts = [(560, 640), (560, 820), (560, 1000)]
        tests = [("čtvrťová nota", True), ("půlová nota", True), ("pomlka půlová", True)]
        for (title, dotted), (x, y) in zip(tests, pts):
            print("vkládám:", title, "tečka:", dotted)
            await insert_note(h, x, y, title, dotted)

        # kontrola: jedna nota BEZ tečky
        print("vkládám: čtvrťová nota BEZ tečky")
        await insert_note(h, 620, 1120, "čtvrťová nota", dotted=False)

        data = await dump(h)
        print("\nSVG text (x, y, size, kód):")
        for t in data["texts"]:
            print("   ", t)
        print("SVG kruhy (tečky):")
        for c in data["circles"]:
            print("   ", c)

        # geometrie: tečka musí být vpravo od noty a v podobné výšce
        ok = True
        for c in data["circles"]:
            near = [t for t in data["texts"] if abs(t["y"] - c["cy"]) < t["size"] * 0.8
                    and 0 < c["cx"] - t["x"] < t["size"]]
            if not near:
                print("   !! tečka nesedí k žádné notě:", c)
                ok = False
        if len(data["circles"]) != 3:
            print("   !! očekávány 3 tečky, nalezeno:", len(data["circles"]))
            ok = False

        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open(OUT, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("\nscreenshot:", OUT)
        print("VÝSLEDEK:", "OK" if ok else "PROBLÉM")


asyncio.run(main())
