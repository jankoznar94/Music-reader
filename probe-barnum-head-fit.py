#!/usr/bin/env python3
"""Vizuální kontrola panelu čísel: vejde se hlavička (název + 5 tlačítek)?

Změří šířky a udělá screenshot panelu + zkusí přepínač skrytá/viditelná.
"""
import asyncio
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


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(pdf=PDF)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.0)
        info = json.loads(await h.ev("""JSON.stringify((() => {
            const p=document.querySelector('.barnum-panel');
            const hd=p.querySelector('.bn-head');
            const bs=[...hd.children].map(e => ({c:e.className|0, t:e.tagName,
              w:Math.round(e.getBoundingClientRect().width),
              l:Math.round(e.getBoundingClientRect().left)}));
            return { panel:[Math.round(p.getBoundingClientRect().width)], head:[hd.clientWidth, hd.scrollWidth],
                     kids: bs, r:p.getBoundingClientRect() }; })())"""))
        print("panel:", info["panel"], "hlavička client/scroll:", info["head"])
        for k in info["kids"]:
            print("   ", k)
        r = info["r"]
        shot = await h.cdp("Page.captureScreenshot", {"format": "png",
                          "clip": {"x": r["x"], "y": r["y"], "width": r["width"], "height": r["height"], "scale": 2}})
        import base64
        path = "/tmp/barnum-panel.png"
        with open(path, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("screenshot:", path)


asyncio.run(main())
