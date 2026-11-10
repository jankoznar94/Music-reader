#!/usr/bin/env python3
"""Proč se liší počet osnov mezi ručním renderem a Dočíslováním stránky?

Na jedné stránce: (1) vyrenderuj plátno ručně a spočítej osnovy, (2) zavolej
fillPageAt a přečti, co vidělo ono, (3) vyrenderuj druhé plátno a porovnej
pixelová data (hash) s prvním. Když se plátna liší, je to render, ne detekce.
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

PDF = os.environ["NOTY_PDF"]
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "7").split(",")]

JS = """(async (doFill) => {
  const d = window.__barDev;
  const m = await import('/src/barLines.js');
  const dim = await d.getPageWidthHeight(d.song, d.currentPage.value + 1);
  const pw = dim.width, ph = dim.height;
  const PPT = 5, dpr = window.devicePixelRatio || 1;
  const mk = async () => {
    const cv = document.createElement('canvas');
    await d.renderPageRegion(d.song, d.currentPage.value + 1, cv,
        {x:0,y:0,w:pw,h:ph}, pw*PPT/dpr, ph*PPT/dpr);
    const px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
    let sum = 0, ink = 0;
    for (let i = 0; i < px.length; i += 4) {
      const g = (px[i]*299 + px[i+1]*587 + px[i+2]*114)/1000;
      sum = (sum + g) % 1000000007; if (g < 160) ink++;
    }
    const res = m.detectPageSystems(cv, cv.width/pw, {});
    return { w: cv.width, h: cv.height, dpr, hash: sum, ink,
             staves: res.staves, systems: res.systems.length };
  };
  const a = await mk();
  let filled = null;
  if (doFill) {
    d.barFillPreview.value = null;
    await d.fillPageAt({x:300, y:400});
    const p = d.barFillPreview.value;
    const sc = (window.__barPickDbg || []).filter(x => x.pageFillScan).slice(-1)[0];
    filled = { toast: d.toast.value, systems: p ? p.systems : null,
               bars: p ? p.bars : null, scanStaves: sc ? sc.pageFillScan.staves : null };
    d.barFillPreview.value = null;
  }
  const b = await mk();
  return JSON.stringify({ a, b, filled });
})"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            await h.goto(pg)
            r = await h.ev(JS + "(true)", await_promise=True)
            print("=== str. %d" % pg)
            print(" ", r)
            import sys
            sys.stdout.flush()


asyncio.run(main())
