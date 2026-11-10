#!/usr/bin/env python3
"""Vykreslí zadaný výřez stránky do PNG (přes pdf.js v aplikaci).
Použití: diag-p7-shot.py <page> <y0pt> <y1pt> <out.png>"""
import asyncio
import base64
import importlib.util
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

JS = """(async () => {
  const p = window.__barDev;
  const page = %d;
  const {width:pw, height:ph} = await p.getPageWidthHeight(p.song, page);
  const crop = {x:0, y:%f, w:pw, h:%f};
  const cv = document.createElement('canvas');
  const PPT = 6, dpr = 1;
  await p.renderPageRegion(p.song, page, cv, crop, crop.w*PPT/dpr, crop.h*PPT/dpr);
  return cv.toDataURL('image/png');
})()"""


async def main():
    page = int(os.environ.get("NOTY_PAGE", "7"))
    y0 = float(os.environ.get("NOTY_Y0", "495"))
    y1 = float(os.environ.get("NOTY_Y1", "645"))
    out = os.environ.get("NOTY_OUT", "/tmp/crop.png")
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(page)
        url = await h.ev(JS % (page, y0, y1 - y0), await_promise=True)
        data = url.split(",", 1)[1]
        with open(out, "wb") as f:
            f.write(base64.b64decode(data))
        print("saved", out, len(data))

asyncio.run(main())
