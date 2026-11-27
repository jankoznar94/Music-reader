#!/usr/bin/env python3
"""Počítadlo stránek je vidět i se schovanou lištou — malé, nahoře uprostřed."""
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
VW, VH = (int(x) for x in os.environ.get("NOTY_VIEWPORT", "800x1280").split("x"))


async def shot(h, path):
    s = await h.cdp("Page.captureScreenshot", {"format": "png"})
    open(path, "wb").write(base64.b64decode(s["data"]))


async def rect(h, sel):
    return await h.ev(
        "(() => { const e = document.querySelector(%s); if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2,"
        " l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height,"
        " text: (e.textContent || '').trim() }; })()" % json.dumps(sel))


async def set_bar(h, hidden):
    await h.ev("(() => { const el = document.querySelector('.top-bar');"
               " const c = el && el.__vueParentComponent;"
               " if (c && c.setupState) c.setupState.barHidden = %s; return 1 })()"
               % ("true" if hidden else "false"))
    await asyncio.sleep(0.5)


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(VW, VH, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','button')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(4), pages=4, reset=False)
        await h.set_tablet(VW, VH, 2)
        await asyncio.sleep(0.4)

        # lišta schovaná (čtecí režim)
        await set_bar(h, True)
        f = await rect(h, ".tb-page-float")
        ok("se schovanou lištou je počítadlo vidět", f is not None, f)
        ok("počítadlo je nahoře", f and f["t"] < 40, f)
        ok("počítadlo je vodorovně uprostřed",
           f and abs((f["l"] + f["r"]) / 2 - VW / 2) < 2, f)
        ok("počítadlo je malé (výška ≤ 24 px)", f and f["h"] <= 24, f)
        ok("počítadlo ukazuje stránku „1 / 4“",
           f and f["text"].replace(" ", "") == "1/4", f["text"] if f else None)
        await shot(h, "/tmp/page-float.png")

        # ťuknutí otevře zadání stránky
        if f:
            await h.finger_tap(f["x"], f["y"])
            await asyncio.sleep(0.7)
            pg = await h.ev("!!document.querySelector('.page-go')")
            ok("ťuknutí na počítadlo otevře zadání stránky", bool(pg), pg)
            await h.ev("(() => { const el = document.querySelector('.page-go-backdrop');"
                       " if (el) el.click(); return 1 })()")
            await asyncio.sleep(0.4)

        # s lištou počítadlo v liště a plovoucí zmizí
        await set_bar(h, False)
        ok("s lištou plovoucí počítadlo zmizí", await rect(h, ".tb-page-float") is None, None)

        ok("žádné chyby v konzoli", not await h.ev("window.__errs || []"), None)
    ok.report()

asyncio.run(main())
