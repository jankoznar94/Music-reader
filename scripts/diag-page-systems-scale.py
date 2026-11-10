#!/usr/bin/env python3
"""Citlivost detectPageSystems na měřítku + vliv vytištěných indexů (numXs).

Pro vybrané stránky Cherubiniho vykreslí stránku při několika PPT a vypíše,
kolik systémů/osnov detekce vrátí; pak totéž s numXs (jako když jsou v DB
čísla z lupy / předchozího číslování).
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

PDF = os.environ.get(
    "NOTY_PDF",
    "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
    "doc_74931c6a3260_IMSLP26826-PMLP59513-Cherubini-RequiemCmVSptrs.pdf")
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "1,5").split(",")]
PPTS = [float(x) for x in os.environ.get("NOTY_PPTS", "3.5,4,4.5,5,5.5,6").split(",")]
NUMS = json.loads(os.environ.get("NOTY_NUMS", "null"))

JS = """
(async (args) => {
  const d = window.__barDev;
  const page = d.currentPage.value;
  let pw = 595, ph = 842;
  try { const g = await d.getPageWidthHeight(d.song, page + 1);
        if (g && g.width > 0) { pw = g.width; ph = g.height; } } catch (e) {}
  const out = [];
  for (const ppt of args.ppts) {
    let outW = pw * ppt / window.devicePixelRatio, outH = ph * ppt / window.devicePixelRatio;
    const MAX_PX = 12e6;
    const areaPx = outW * outH * window.devicePixelRatio * window.devicePixelRatio;
    if (areaPx > MAX_PX) { const k = Math.sqrt(MAX_PX / areaPx); outW *= k; outH *= k; }
    const cv = document.createElement('canvas');
    await d.renderPageRegion(d.song, page + 1, cv, {x:0,y:0,w:pw,h:ph}, outW, outH);
    const pxPerPt = cv.width / pw;
    const r = d.detectPageSystems(cv, pxPerPt, {krok: 1, numXs: args.nums || []});
    out.push({ ppt, pxPerPt: +pxPerPt.toFixed(3), w: cv.width, h: cv.height,
      staves: r.staves ?? null, reason: r.reason ?? null,
      sys: (r.systems||[]).map(s => [Math.round(s.sysTop), Math.round(s.sysBot),
        s.stavesFound, s.stavesExpected, s.bars, s.ok, s.spanOk,
        (s.lines||[]).map(v=>Math.round(v))]) });
  }
  return JSON.stringify(out);
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
            print(f"=== str. {pg}")
            res = await h.ev("(" + JS + ")(" + json.dumps({"ppts": PPTS, "nums": NUMS}) + ")",
                             await_promise=True)
            for row in json.loads(res):
                syss = " | ".join(
                    f"y{a}-{b} osn{c}/{d} bars{e}{'' if f else ' FAIL'}"
                    f"{'' if g else ' spanKO'} lines={h2}"
                    for a, b, c, d, e, f, g, h2 in row["sys"])
                print(f"  ppt {row['ppt']}: {row['w']}x{row['h']} "
                      f"px/b {row['pxPerPt']} staves {row['staves']} "
                      f"reason {row['reason']} → {syss}")


asyncio.run(main())
