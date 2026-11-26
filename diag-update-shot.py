#!/usr/bin/env python3
"""Screenshot okna „Nová verze aplikace je k dispozici“ — vizuální kontrola."""
import asyncio
import base64
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
APP = os.environ.get("NOTY_APP") or m.APP_URL


async def main():
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.wait_for("!!window.__setUpdateAvailable", label="update.js")
        await asyncio.sleep(2.5)   # počkat, až doběhne startovní kontrola verze (jinak ji hned přepíše)
        await h.ev("sessionStorage.removeItem('noty-update-dismissed')")
        await h.ev("window.__setUpdateAvailable(true, 'assets/index-TEST9.js')")
        await asyncio.sleep(0.3)
        box = await h.ev("(() => { const r = document.querySelector('.up-box').getBoundingClientRect();"
                         " return { x: r.left - 20, y: r.top - 20, w: r.width + 40, h: r.height + 40 }; })()")
        r = await h.cdp("Page.captureScreenshot", {
            "format": "png", "captureBeyondViewport": True,
            "clip": {"x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"], "scale": 2},
        })
        p = "/tmp/update-prompt.png"
        open(p, "wb").write(base64.b64decode(r["data"]))
        print("shot", p)


asyncio.run(main())
