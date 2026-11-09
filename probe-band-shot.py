#!/usr/bin/env python3
"""Screenshot pásu se systémem (str. 16, rám) pro PIXELOVÉ měření polohy čísla."""
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

PDF = ("/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
       "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
       "doc_1bb2c499f695_Mozart-Davide penitente.pdf")


async def click_tb(h, title):
    return await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('%s')); if (b) b.click(); return !!b; })()""" % title)


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 1)
        await h.open_song(pdf=PDF)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.5)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.4)
        await h.goto(16)
        await asyncio.sleep(1.5)
        await h.ev("(() => { document.querySelectorAll('.barnum-panel,.annot-panel,.top-bar,.bookmark-strip,.edge').forEach(e=>{ if(e) e.style.visibility='hidden'; }); return true; })()")
        await asyncio.sleep(0.3)
        geo = json.loads(await h.ev("""JSON.stringify((() => {
            const cv=document.querySelector('canvas.pdf-canvas');
            const r=cv.getBoundingClientRect();
            const svg=document.querySelector('.annot-layer');
            const g=svg.getScreenCTM();
            const f=(x,y)=>{const q=new DOMPoint(x,y).matrixTransform(g);return [q.x,q.y];};
            const vb=svg.getAttribute('viewBox').split(/\\s+/).map(Number);
            return { rect:[r.left,r.top,r.width,r.height], vb,
                     pdf73_528: f(73*760/595.2, 528*760/595.2),
                     pdf73_570: f(73*760/595.2, 570*760/595.2) }; })())"""))
        print("canvas:", geo["rect"], "viewBox:", geo["vb"])
        print("kde leží pdf(73,528) na obrazovce:", geo["pdf73_528"])
        print("kde leží pdf(73,570) na obrazovce:", geo["pdf73_570"])
        clip = {"x": 0, "y": 780, "width": 300, "height": 90, "scale": 4}
        shot = await h.cdp("Page.captureScreenshot", {"format": "png", "clip": clip})
        with open("/tmp/pas-system.png", "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("screenshot: /tmp/pas-system.png clip:", clip)


asyncio.run(main())
