#!/usr/bin/env python3
"""SONDA: okno „Vkládání not“ — dvousloupcové okno s náhledem vpravo.

Ověřuje (Jan, Nov 2026):
  * pomlka NEMÁ řádek „Linky“ (ani „Poloha“)
  * náhled je vpravo v boxu s čárkovaným rámem, přes celou pravou část okna
  * měřítko náhledu je STEJNÉ pro všechny hodnoty (celá vs čtvrťová hlavička)
  * tečka je menší než dřív (kruh, ne font)
  * dole už není malým písmem název noty
  * screenshot okna i řady nástrojů pro vizuální kontrolu

Spouštěj:  scripts/run-probe-fresh.sh probe-note-dialog.py
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
Harness = m.Harness
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
m.APP_URL = os.environ.get("NOTY_APP", m.APP_URL)

OUT_DLG = "/tmp/note-dialog.png"
OUT_TILES = "/tmp/note-tiles.png"


def center(js):
    return ("(() => { const b = %s; if (!b) return null;"
            " const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2),"
            " title: b.title || (b.textContent||'').trim()}; })()" % js)


async def shot(h, path, clip=None):
    kw = {"format": "png"}
    if clip:
        kw["clip"] = {"x": clip["x"], "y": clip["y"], "width": clip["w"],
                      "height": clip["h"], "scale": 2}
    r = await h.cdp("Page.captureScreenshot", kw)
    open(path, "wb").write(base64.b64decode(r["data"]))
    print("   screenshot →", path)


async def rect(h, sel):
    return await h.ev("(() => { const e = document.querySelector(%s); if (!e) return null;"
                      " const r = e.getBoundingClientRect();"
                      " return {x: r.left, y: r.top, w: r.width, h: r.height}; })()" % json.dumps(sel))


async def pick(h, title):
    t = await h.ev(center("[...document.querySelectorAll('.text-input-card .dyn-btn')]"
                          ".find(e => e.title === %s)" % json.dumps(title)))
    if not t:
        raise RuntimeError("dlaždice %r nenalezena" % title)
    await h.pen_tap(t["x"], t["y"])
    await asyncio.sleep(0.5)


async def preview_info(h):
    return await h.ev("""(() => {
      const svg = document.querySelector('.ti-note-prev .nota-nahled');
      if (!svg) return null;
      const vb = svg.getAttribute('viewBox').split(/\\s+/).map(Number);
      const t = svg.querySelector('text');
      const c = svg.querySelector('circle');
      const box = svg.getBoundingClientRect();
      return {
        vb, w: box.width, h: box.height,
        px_per_em: box.height / vb[3] * Number(t.getAttribute('font-size')),
        font_size: Number(t.getAttribute('font-size')),
        dot_r: c ? Number(c.getAttribute('r')) : null,
        dot_r_em: c ? Number(c.getAttribute('r')) / Number(t.getAttribute('font-size')) : null,
        fill: getComputedStyle(t).fill, stroke: getComputedStyle(t).stroke,
      };
    })()""")


async def main():
    async with Harness() as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=m.make_pdf(6))
        await h.annot_toggle()
        await asyncio.sleep(0.8)

        # rozbalit řádek notových nástrojů
        g = await h.ev(center("document.querySelector('.ap-tool.nota-tool')"))
        await h.pen_tap(g["x"], g["y"])
        await asyncio.sleep(0.5)
        await shot(h, OUT_TILES, await rect(h, ".annot-panel"))

        # nástroj Vkládání not
        nt = await h.ev(center("[...document.querySelectorAll('.ap-tool')]"
                               ".find(e => (e.title||'').startsWith('Vkládání not'))"))
        if not nt:
            raise RuntimeError("tlačítko Vkládání not nenalezeno")
        await h.pen_tap(nt["x"], nt["y"])
        await asyncio.sleep(0.4)
        p = await h.free_point(0.55, 0.8)
        await h.pen_tap(p["x"], p["y"])
        await h.wait_for("!!document.querySelector('.ti-note-body')", timeout=10, label="dialog noty")
        await asyncio.sleep(0.6)

        card = await rect(h, ".text-input-card")
        prev = await rect(h, ".ti-note-prev")
        print("okno:", card, "\nnáhled:", prev)
        body = await h.ev("(() => { const b = document.querySelector('.ti-note-body');"
                          " const r = b.getBoundingClientRect();"
                          " const l = b.querySelector('.ti-note-left').getBoundingClientRect();"
                          " return {w: r.width, left: l.width, right: r.width - l.width}; })()")
        print("sloupce:", body)

        await pick(h, "čtvrťová nota")
        a = await preview_info(h)
        await pick(h, "celá nota")
        b = await preview_info(h)
        print("čtvrťová:", a)
        print("celá    :", b)

        # pomlka → žádné Linky
        await pick(h, "pomlka čtvrťová")
        rest = await h.ev("(() => { const c = document.querySelector('.text-input-card');"
                          " return { linky: [...c.querySelectorAll('.ti-size-label')].some(e => e.textContent.trim() === 'Linky'),"
                          "   poloha: [...c.querySelectorAll('.ti-size-label')].some(e => e.textContent.trim() === 'Poloha'),"
                          "   nazev: [...c.querySelectorAll('.ti-note')].map(e => e.textContent.trim()) }; })()")
        print("pomlka:", rest)

        # tečka
        await pick(h, "čtvrťová nota")
        tg = await h.ev(center("[...document.querySelectorAll('.text-input-card .ti-toggle')]"
                               ".find(e => (e.textContent||'').includes('Tečkovaný'))"))
        await h.pen_tap(tg["x"], tg["y"])
        await asyncio.sleep(0.4)
        c = await preview_info(h)
        print("s tečkou:", c)
        await shot(h, OUT_DLG, card)

        # kontrola tvrzení
        ok = True
        if rest["linky"] or rest["poloha"]:
            print("FAIL: pomlka má Linky/Polohu"); ok = False
        if rest["nazev"]:
            print("FAIL: dole je pořád název noty:", rest["nazev"]); ok = False
        if not a or not b:
            print("FAIL: náhled chybí"); ok = False
        else:
            if abs(a["px_per_em"] - b["px_per_em"]) > 0.5:
                print("FAIL: měřítko náhledu se mezi hodnotami liší"); ok = False
            if b["h"] < 100:  # celá nota nemá být obrovská ani titěrná
                print("FAIL: náhled celé noty je moc malý"); ok = False
        if not c or not c["dot_r_em"]:
            print("FAIL: tečka v náhledu chybí"); ok = False
        elif c["dot_r_em"] > 0.08:
            print("FAIL: tečka je pořád velká (r = %.3f em)" % c["dot_r_em"]); ok = False
        print("VÝSLEDEK:", "OK" if ok else "CHYBY")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
