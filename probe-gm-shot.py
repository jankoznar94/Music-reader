#!/usr/bin/env python3
"""Screenshot animované nabídky — tablet (800) i telefon (390)."""
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
            # Úzká lišta se posouvá — tlačítko ✏️ může být mimo záběr. Posuň
            # lištu tak, aby bylo vidět (uživatel to dělá prstem taky).
            await h.ev(
                '(() => { const b = document.querySelector(".tb-btn[title^=\'Anotace\']");'
                ' const bar = document.querySelector(".top-bar");'
                ' if (b && bar) { const br = b.getBoundingClientRect().left;'
                ' bar.scrollLeft = Math.max(0, bar.scrollLeft + br - 32); }'
                ' return true; })()')
            await asyncio.sleep(0.3)
            if tag == "phone":
                # Úzká lišta: počítadlo stránek je absolutně na středu a v tomto
                # posunu leží NAD tlačítkem ✏️ (preexistující překryv lišty).
                # Pro screenshot nabídky ho dočasně schováme, ať se dá ťuknout.
                await h.ev('(() => { const s=document.createElement("style");'
                           ' s.textContent=".tb-page-center{display:none!important}";'
                           ' document.head.appendChild(s); return true; })()')
                await asyncio.sleep(0.2)
            btn = await rect(h, ".tb-btn[title^='Anotace']")
            print(tag, "btn", btn)
            await h.touch("touchStart", [(btn["x"], btn["y"], 12)])
            await asyncio.sleep(0.4)
            dbg = await h.ev("(() => ({ menu: !!document.querySelector('.gm-root'), n: document.querySelectorAll('.gm-item').length,"
                             " mode: window.__barDev && window.__barDev.controlMode.value,"
                             " hit: (document.elementFromPoint(%s, %s)||{}).className }))()"
                             % (btn["x"], btn["y"]))
            print(tag, "dbg", dbg)
            item = await rect(h, ".gm-item", 5)   # Dynamika
            if item is None:
                await h.touch("touchEnd", [])
                await asyncio.sleep(0.4)
                continue
            await h.touch("touchMove", [(item["x"], item["y"], 12)])
            await asyncio.sleep(0.35)
            info = await h.ev(
                "(() => { const s=document.querySelector('.gm-sub'); const c=document.querySelector('.gm-col');"
                " const sr=s.getBoundingClientRect(), cr=c.getBoundingClientRect();"
                " return { vw: innerWidth, col:[cr.left,cr.right], sub:[sr.left,sr.right,sr.top,sr.bottom] }; })()")
            print(tag, info)
            await shot(h, "/tmp/gm-%s.png" % tag)
            await h.touch("touchEnd", [])
            await asyncio.sleep(0.4)


asyncio.run(main())
