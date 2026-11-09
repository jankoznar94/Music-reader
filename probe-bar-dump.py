#!/usr/bin/env python3
"""Ground truth: vyrenderuje stránky Mozarta ve vysokém rozlišení a uloží PNG.

PNG se pak analyzuje v Pythonu (analyze.py) nezávisle na JS detekci.
"""
import asyncio
import base64
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = ("/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
       "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
       "doc_1bb2c499f695_Mozart-Davide penitente.pdf")
PAGES = [int(x) for x in (sys.argv[1:] or ["2", "4", "8"])]
OUT = "/tmp/barscan"


async def main():
    os.makedirs(OUT, exist_ok=True)
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            b64 = await h.ev("""(async () => {
                const d = window.__barDev;
                const p = %d;   // 0-based pro renderPageRegion
                const wh = await d.getPageWidthHeight(d.song.value || d.song, p + 1);
                const cv = document.createElement('canvas');
                await d.renderPageRegion(d.song.value || d.song, p + 1, cv,
                    {x:0, y:0, w: wh.width, h: wh.height}, wh.width * 4, wh.height * 4);
                return cv.toDataURL('image/png').split(',')[1];
            })()""" % (pg - 1), await_promise=True)
            raw = base64.b64decode(b64)
            path = os.path.join(OUT, "p%d.png" % pg)
            open(path, "wb").write(raw)
            print(path, len(raw), "B")
            # rozměry + měřítko
            info = await h.ev("""(async () => {
                const d = window.__barDev;
                const p = %d;
                const wh = await d.getPageWidthHeight(d.song.value || d.song, p + 1);
                const s = await d.layerScale(p);
                return JSON.stringify({w: wh.width, h: wh.height, layer: s});
            })()""" % (pg - 1), await_promise=True)
            print("  geometrie:", info)


asyncio.run(main())
