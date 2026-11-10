#!/usr/bin/env python3
"""Uloží plátno stránky (stejné jako pro Dočíslování) do PNG pro offline rozbor."""
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
    "doc_74931c6a3260_IMSLP26826-PMLP59513-Cherubini-RequiemCmVSptrs.pdf")
PAGE = int(os.environ.get("NOTY_PAGE", "1"))
OUT = os.environ.get("NOTY_OUT", "/tmp/page-dump.png")

JS = """
(async () => {
  const d = window.__barDev;
  const page = d.currentPage.value;
  let pw = 595, ph = 842;
  try { const g = await d.getPageWidthHeight(d.song, page + 1);
        if (g && g.width > 0) { pw = g.width; ph = g.height; } } catch (e) {}
  const PPT = 5;
  let outW = pw * PPT / window.devicePixelRatio, outH = ph * PPT / window.devicePixelRatio;
  const MAX_PX = 12e6;
  const areaPx = outW * outH * window.devicePixelRatio * window.devicePixelRatio;
  if (areaPx > MAX_PX) { const k = Math.sqrt(MAX_PX / areaPx); outW *= k; outH *= k; }
  const cv = document.createElement('canvas');
  await d.renderPageRegion(d.song, page + 1, cv, {x:0,y:0,w:pw,h:ph}, outW, outH);
  return JSON.stringify({ data: cv.toDataURL('image/png'), w: cv.width, h: cv.height,
                          pxPerPt: cv.width / pw, pw, ph });
})
"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=PDF)
        await h.goto(PAGE)
        res = json.loads(await h.ev("(" + JS + ")()", await_promise=True))
        raw = base64.b64decode(res["data"].split(",", 1)[1])
        open(OUT, "wb").write(raw)
        print(json.dumps({k: res[k] for k in ("w", "h", "pxPerPt", "pw", "ph")}), OUT)


asyncio.run(main())
