#!/usr/bin/env python3
"""Screenshoty animovaného režimu — duch, lišta vlevo, koláč s prstenci.

Ukládá na tabletu (800) i telefonu (390):
  /tmp/gm-ghost-<tag>.png     let ducha tlačítka
  /tmp/gm-rail-<tag>.png      lišta nástrojů vlevo
  /tmp/gm-pie-<tag>.png       koláč tužky (dva prstence + fajfka)
  /tmp/gm-pie-hover-<tag>.png prst na výseči barvy
"""
import asyncio
import base64
import importlib.util
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
APP = os.environ.get("NOTY_APP") or os.environ.get("APP_URL") or m.APP_URL


async def rect(h, sel, idx=0):
    return await h.ev(
        "(() => { const e = document.querySelectorAll(%s)[%d]; if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2 }; })()"
        % (json.dumps(sel), idx))


async def shot(h, name):
    data = await h.cdp("Page.captureScreenshot", {"format": "png"})
    with open(name, "wb") as f:
        f.write(base64.b64decode(data["data"]))
    print("saved", name)


async def main():
    async with m.Harness(url=APP) as h:
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','gesture')")
        await h.ev("localStorage.setItem('topbarHidden','0')")
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)

        for (w, hh, tag) in [(800, 1280, "tablet"), (390, 844, "phone")]:
            await h.set_tablet(w, hh, 2)
            await asyncio.sleep(0.5)
            if tag == "phone":
                # na úzké liště leží počítadlo stránek NAD tlačítkem ✏️
                await h.ev('(() => { const s=document.createElement("style");'
                           ' s.textContent=".tb-page-center{display:none!important}";'
                           ' document.head.appendChild(s); return true; })()')
                await asyncio.sleep(0.2)
            btn = await rect(h, ".tb-btn[title^='Anotace']")
            await h.touch("touchStart", [(btn["x"], btn["y"], 12)])
            await asyncio.sleep(0.2)
            await shot(h, "/tmp/gm-ghost-%s.png" % tag)
            await asyncio.sleep(0.3)
            item = await rect(h, ".gm-item", 0)   # Tužka (dva prstence)
            await h.touch("touchMove", [(item["x"] + 160, item["y"], 12)])
            await asyncio.sleep(0.2)
            await shot(h, "/tmp/gm-rail-%s.png" % tag)
            await h.touch("touchEnd", [])
            await asyncio.sleep(0.6)
            await shot(h, "/tmp/gm-pie-%s.png" % tag)
            geo = await h.ev(
                "(() => { const hub=document.querySelector('.pie-hub-bg');"
                " const g=document.querySelector('.pie-svg g[data-ring]');"
                " return { cx:+hub.getAttribute('cx'), cy:+hub.getAttribute('cy'),"
                " r0:+g.getAttribute('data-r0'), r1:+g.getAttribute('data-r1') }; })()")
            ang = -math.pi / 2 + 2.5 * (2 * math.pi / 9)
            rr = (geo["r0"] + geo["r1"]) / 2
            await h.touch("touchStart", [(geo["cx"], geo["cy"] + 10, 12)])
            await h.touch("touchMove", [(geo["cx"] + math.cos(ang) * rr,
                                         geo["cy"] + math.sin(ang) * rr, 12)])
            await asyncio.sleep(0.3)
            await shot(h, "/tmp/gm-pie-hover-%s.png" % tag)
            await h.touch("touchEnd", [])
            await asyncio.sleep(0.5)
            # zavřít fajfkou, ať je čistý stav pro další rozměr
            await h.touch("touchStart", [(geo["cx"], geo["cy"], 12)])
            await asyncio.sleep(0.08)
            await h.touch("touchEnd", [])
            await asyncio.sleep(0.4)


asyncio.run(main())
