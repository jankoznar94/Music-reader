#!/usr/bin/env python3
"""Pro každý systém stránky vypíše staffLeft, opening a vnitřní čáry (body PDF)."""
import asyncio
import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.environ["NOTY_PDF"]
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "20").split(",")]

JS = """
(async () => {
  const d = window.__barDev;
  const page = d.currentPage.value;
  let pw = 595, ph = 842;
  const g = await d.getPageWidthHeight(d.song, page + 1);
  if (g && g.width > 0) { pw = g.width; ph = g.height; }
  const PPT = 5, dpr = window.devicePixelRatio || 1;
  let outW = pw * PPT / dpr, outH = ph * PPT / dpr;
  const MAX_PX = 12e6, area = outW * outH * dpr * dpr;
  if (area > MAX_PX) { const k = Math.sqrt(MAX_PX / area); outW *= k; outH *= k; }
  const cv = document.createElement('canvas');
  await d.renderPageRegion(d.song, page + 1, cv, {x:0,y:0,w:pw,h:ph}, outW, outH);
  const pxPerPt = cv.width / pw;
  const r = d.detectPageSystems(cv, pxPerPt, {krok: 1, numXs: []});
  return JSON.stringify((r.systems || []).map(s => ({
    top: Math.round(s.sysTop), bot: Math.round(s.sysBot),
    staves: s.stavesFound, left: +(s.staffLeftPt || 0).toFixed(1),
    open: s.openingPt == null ? null : +s.openingPt.toFixed(1),
    lines: (s.lines || []).map(v => Math.round(v)),
    right: s.diag ? +s.diag.staffRight : null,
    space: +(s.spacePt || 0).toFixed(2),
  })));
})()
"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            await h.goto(pg)
            res = await h.ev("(" + JS + ")", await_promise=True)
            print("=== str.", pg)
            for s in json.loads(res):
                print("  y%d-%d osn%d left=%.1f open=%s right=%s space=%.2f lines=%s"
                      % (s["top"], s["bot"], s["staves"], s["left"], s["open"],
                         s["right"], s["space"], s["lines"]))


asyncio.run(main())
