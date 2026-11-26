#!/usr/bin/env python3
"""Screenshoty nových vizuálů: puntík ve sloupci, spojka, lišta skupiny, hláška."""
import asyncio
import base64
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
APP = os.environ.get("NOTY_APP") or m.APP_URL
OUT = os.environ.get("OUT_DIR", "/tmp")


async def rect(h, sel):
    return await h.ev(
        "(() => { const e = document.querySelector(%s); if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left, y: r.top, w: r.width, h: r.height }; })()" % __import__("json").dumps(sel))


async def shot(h, box, name, pad=10, scale=2):
    r = await h.cdp("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": True,
        "clip": {"x": max(0, box["x"] - pad), "y": max(0, box["y"] - pad),
                 "width": box["w"] + 2 * pad, "height": box["h"] + 2 * pad, "scale": scale},
    })
    p = os.path.join(OUT, name)
    open(p, "wb").write(base64.b64decode(r["data"]))
    print("shot", p)


async def main():
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','gesture')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        await h.ev("localStorage.setItem('topbarHidden','0')")
        annot = await h.ev("(() => { const e=document.querySelector(\".tb-btn[title^='Anotace']\"); const r=e.getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2}; })()")
        await h.touch("touchStart", [(annot["x"], annot["y"], 12)])
        await asyncio.sleep(0.45)
        col = await rect(h, ".gm-col")
        # prst 4. kolečko (Text), ať je vidět spojka
        await h.touch("touchMove", [(col["x"] + 200, col["y"] + 5 + 23 + 4 * 50, 12)])
        await asyncio.sleep(0.25)
        await shot(h, {"x": col["x"] - 60, "y": col["y"] - 10, "w": col["w"] + 160, "h": col["h"] + 20}, "gm-track.png")
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.5)
        st = await h.ev("!!document.querySelector('.pie-svg')")
        if st:
            hub = await h.ev("(() => { const c=document.querySelector('.pie-check-bg'); const x=+c.getAttribute('cx'), y=+c.getAttribute('cy'); return {x,y}; })()")
            await h.finger_tap(hub["x"], hub["y"])
            await asyncio.sleep(0.5)
        ph = await rect(h, ".place-hint")
        if ph:
            await shot(h, ph, "place-hint.png", pad=16)
        # skupinová lišta
        nav = await h.ev("(() => { const e=document.querySelector(\".tb-btn[data-gm-group='navig']\"); const r=e.getBoundingClientRect(); return {x:r.left+r.width/2, y:r.top+r.height/2}; })()")
        await h.touch("touchStart", [(nav["x"], nav["y"], 12)])
        await asyncio.sleep(0.4)
        col2 = await rect(h, ".gm-col")
        await shot(h, {"x": col2["x"] - 60, "y": col2["y"] - 10, "w": col2["w"] + 160, "h": col2["h"] + 20}, "gm-group.png")
        await h.touch("touchEnd", [])


asyncio.run(main())
