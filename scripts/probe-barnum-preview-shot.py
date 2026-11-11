#!/usr/bin/env python3
"""Snímek smrsknutého okna číslování při náhledu celé stránky (pro kontrolu okem)."""
import asyncio
import base64
import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.environ.get(
    "NOTY_PDF",
    "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
    "doc_1bb2c499f695_Mozart-Davide penitente.pdf")
OUT = os.environ.get("NOTY_OUT", "/tmp/barnum-preview-compact.png")


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5199/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        for _ in range(5):
            st = json.loads(await h.ev("""(() => { const d=window.__barDev;
                return JSON.stringify({b:d.barnumMode.value, panel: !!document.querySelector('.barnum-panel')}); })()"""))
            if st["b"] and st["panel"]:
                break
            await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                       ".find(x => (x.title||'').startsWith('Číslování')); if (b) b.click(); })()")
            await asyncio.sleep(0.5)
        await asyncio.sleep(0.3)
        await h.ev("(() => { const b=document.querySelector('.bn-page'); if (b) b.click(); })()")
        for _ in range(80):
            if await h.ev("window.__barDev && window.__barDev.barFillPreview.value ? '1' : ''"):
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.6)
        rect = json.loads(await h.ev("""(() => { const p=document.querySelector('.barnum-panel');
            const r=p.getBoundingClientRect();
            return JSON.stringify([r.left, r.top, r.width, r.height]); })()"""))
        # výřez s okolím, ať je vidět, že panel nekryje noty
        x, y, w, hh = rect
        clip = {"x": max(0, x - 40), "y": max(0, y - 20),
                "width": min(w + 80, 800 - max(0, x - 40)),
                "height": hh + 120, "scale": 2}
        shot = await h.cdp("Page.captureScreenshot", {"clip": clip, "captureBeyondViewport": False})
        data = base64.b64decode(shot["data"])
        with open(OUT, "wb") as f:
            f.write(data)
        print("panel rect:", rect)
        print("snímek:", OUT, len(data), "B")


asyncio.run(main())
