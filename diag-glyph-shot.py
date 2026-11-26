#!/usr/bin/env python3
"""Rychlý pohled na lištu a koláč dynamiky — uloží dva výřezy jako PNG.

Používá se při ladění ořezu glyfů (Jan: „dynamika je na středu, ale oříznutá").
"""
import asyncio
import base64
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
APP = os.environ.get("NOTY_APP") or m.APP_URL

OUT = os.environ.get("OUT_DIR", "/tmp")


async def rect(h, sel, idx=0):
    return await h.ev(
        "(() => { const e = document.querySelectorAll(%s)[%d]; if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2,"
        "          left: r.left, right: r.right, top: r.top, bottom: r.bottom,"
        "          w: r.width, h: r.height }; })()" % (json.dumps(sel), idx))


async def shot(h, box, name, pad=24):
    x = max(0, box["left"] - pad)
    y = max(0, box["top"] - pad)
    cw = min(2000, box["w"] + 2 * pad)
    ch = min(2000, box["h"] + 2 * pad)
    r = await h.cdp("Page.captureScreenshot", {
        "format": "png",
        "captureBeyondViewport": True,
        "clip": {"x": x, "y": y, "width": cw, "height": ch, "scale": 3},
    })
    p = os.path.join(OUT, name)
    with open(p, "wb") as f:
        f.write(base64.b64decode(r["data"]))
    print("shot", p, round(cw), round(ch))


async def main():
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode', 'gesture')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        fonts = await h.ev("(() => ({ check: document.fonts.check('16px NotyDyn'),"
                           " list: [...document.fonts].map(f => f.family + ':' + f.status) }))()")
        print("fonts", fonts)
        btn = await rect(h, ".tb-btn[title^='Anotace']")
        await h.touch("touchStart", [(btn["x"], btn["y"], 12)])
        await asyncio.sleep(0.35)
        col = await rect(h, ".gm-col")
        print("col", {k: round(v, 1) for k, v in col.items()})
        print("btn.left", round(btn["left"], 1))
        await shot(h, col, "glyf-lista.png")
        # dynamika (index 5)
        i5 = await rect(h, ".gm-item", 5)
        await h.touch("touchMove", [(col["right"] + 140, i5["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.7)
        pie = await rect(h, ".pie-svg")
        await shot(h, pie, "glyf-kolac-dynamika.png", pad=0)
        # zkusit i Značky (index 6)
        btn = await rect(h, ".tb-btn[title^='Anotace']")
        await h.touch("touchStart", [(btn["x"], btn["y"], 12)])
        await asyncio.sleep(0.35)
        col = await rect(h, ".gm-col")
        i6 = await rect(h, ".gm-item", 6)
        await h.touch("touchMove", [(col["right"] + 140, i6["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.7)
        await shot(h, await rect(h, ".pie-svg"), "glyf-kolac-znacky.png", pad=0)


asyncio.run(main())
