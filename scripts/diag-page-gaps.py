#!/usr/bin/env python3
"""Vypíše, jak detekce stránky seskupila osnovy do systémů: řádky osnov,
mezery mezi nimi (velikost, inkoust, spojnice) a výsledné systémy."""
import asyncio
import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.environ.get("NOTY_PDF", "")
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "6").split(",")]

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
  const pxPerPt = cv.width / pw;
  const r = d.detectPageSystems(cv, pxPerPt, {krok: 1, numXs: []});
  return JSON.stringify({ pxPerPt, rows: r.rowsPt, gaps: r.gapsPt,
    base: r.gapBasePt, tall: r.tallCols,
    sys: (r.systems||[]).map(s => [Math.round(s.sysTop), Math.round(s.sysBot),
      s.stavesFound, s.stavesExpected, s.bars, s.ok, s.spanOk, s.lines]) });
})
"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            await h.goto(pg)
            res = json.loads(await h.ev("(" + JS + ")()", await_promise=True))
            print(f"=== str. {pg}  px/b {res['pxPerPt']:.3f}  base {res['base']} b")
            print("osnovy (top, bot, linek):")
            for r0 in res["rows"]:
                print("   ", r0)
            print("mezery (velikost b, ink, spojnice, x spojnic):")
            for g0 in res["gaps"]:
                print("   ", g0)
            print("sloupce přes 25% výšky:", res["tall"][:8])
            print("systémy:")
            for s in res["sys"]:
                print("   ", s)


asyncio.run(main())
