#!/usr/bin/env python3
"""Screenshoty animovaného režimu — duch + lišta vlevo + kruhový výběr.

Ukládá: /tmp/gm-ghost.png (let ducha), /tmp/gm-rail.png (lišta vlevo),
/tmp/gm-pie.png (koláč voleb uprostřed), a totéž na šířce telefonu 390 px.
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
            await asyncio.sleep(0.23)
            await shot(h, "/tmp/gm-ghost-%s.png" % tag)
            await asyncio.sleep(0.35)
            item = await rect(h, ".gm-item", 4)   # Noty
            await h.touch("touchMove", [(item["x"] + 160, item["y"], 12)])
            await asyncio.sleep(0.25)
            await shot(h, "/tmp/gm-rail-%s.png" % tag)
            await h.touch("touchEnd", [])
            await asyncio.sleep(0.8)
            await shot(h, "/tmp/gm-pie-%s.png" % tag)
            # označ výseč prstem (4. výseč) a vyfoť zvýraznění
            geo = await h.ev(
                "(() => { const hole=document.querySelector('.pie-hole');"
                " const r=document.querySelector('.pie-ring');"
                " return { cx:+hole.getAttribute('cx'), cy:+hole.getAttribute('cy'),"
                " r0:+hole.getAttribute('r'), r:+r.getAttribute('r') }; })()")
            import math
            step = 2 * math.pi / 12
            ang = -math.pi / 2 + 3.5 * step
            rr = (geo["r0"] + geo["r"]) / 2
            await h.touch("touchStart", [(geo["cx"], geo["cy"] + 10, 12)])
            await h.touch("touchMove", [(geo["cx"] + math.cos(ang) * rr,
                                         geo["cy"] + math.sin(ang) * rr, 12)])
            await asyncio.sleep(0.3)
            await shot(h, "/tmp/gm-pie-hover-%s.png" % tag)
            await h.touch("touchEnd", [])
            await asyncio.sleep(0.5)


asyncio.run(main())
