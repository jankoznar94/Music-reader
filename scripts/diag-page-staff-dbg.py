#!/usr/bin/env python3
"""Proč se na stránce ztratí osnovy: výpis staffDbg (verdikty) + surové skupiny řádků.

Používá STEJNÉ plátno jako appka (getPageWidthHeight + MAX_PX strop + dpr).
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
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "1").split(",")]

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
  return JSON.stringify({ pxPerPt, staves: r.staves,
    staff: (r.staffDbg||[]).map(x => x),
    sys: (r.systems||[]).map(s => [Math.round(s.sysTop), Math.round(s.sysBot), s.stavesFound, s.stavesExpected, s.spanOk, s.ok]),
    raw: r.rawStaff || null });
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
            print(f"=== str. {pg}  px/b {res['pxPerPt']:.3f}  osnov {res['staves']}")
            print("  systémy:", res["sys"])
            for row in res["staff"]:
                y0, y1, n, verdict = row[0], row[1], row[2], row[3]
                mark = "" if verdict == "ok" else "  <<<"
                print(f"  osnova y{y0}–{y1} linek {n}: {verdict}{mark}")
                if verdict != "ok":
                    print(f"      linky: {row[4]}")


asyncio.run(main())
