#!/usr/bin/env python3
"""DIAG: co detectPageSystems na stránce vidí — osnovy, mezery, hranice systémů."""
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
    "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
    "doc_1bb2c499f695_Mozart-Davide penitente.pdf")
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "2").split(",")]


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            await h.goto(pg)
            r = await h.ev("""(async () => {
                const d = window.__barDev;
                const m = await import('/src/barLines.js');
                const dim = await d.getPageWidthHeight(d.song, d.currentPage.value + 1);
                const pw = dim.width, ph = dim.height;
                const cv = document.createElement('canvas');
                const PPT = 5, dpr = window.devicePixelRatio || 1;
                await d.renderPageRegion(d.song, d.currentPage.value + 1, cv,
                    {x:0,y:0,w:pw,h:ph}, pw*PPT/dpr, ph*PPT/dpr);
                const pxPerPt = cv.width / pw;
                const res = m.detectPageSystems(cv, pxPerPt, { krok: d.barStep.value });
                return JSON.stringify({ w: cv.width, h: cv.height, pxPerPt,
                    staves: res.staves, gapBasePt: res.gapBasePt,
                    rows: res.rowsPt, gaps: res.gapsPt,
                    sys: res.systems.map(s => ({ ok: s.ok, span: s.spanOk,
                        top: s.sysTop, bot: s.sysBot, staves: s.stavesFound,
                        exp: s.stavesExpected, bars: s.bars, reason: s.reason,
                        lines: s.lines.map(v => Math.round(v)),
                        open: s.openingPt == null ? null : Math.round(s.openingPt * 10) / 10,
                        left: s.dbg ? s.dbg.staffLeft : null,
                        right: s.dbg ? s.dbg.staffRight : null })) });
            })()""", await_promise=True)
            data = json.loads(r)
            print("=== str. %d  plátno %s×%s (%.2f px/b)" % (pg, data["w"], data["h"], data["pxPerPt"]))
            print("osnov: %s | základ mezer: %s b" % (data["staves"], data["gapBasePt"]))
            for i, row in enumerate(data["rows"]):
                print("  osnova %2d: %6.1f–%6.1f (%d linek)" % (i, row[0], row[1], row[2]))
            print("mezery:", " ".join("%s/%s" % (g[0], g[1]) for g in data["gaps"]))
            for s in data["sys"]:
                print("  SYSTÉM top=%s bot=%s osnov %s/%s čar %s ok=%s span=%s | okraj %s..%s | open %s %s"
                      % (round(s["top"]) if s["top"] else None,
                         round(s["bot"]) if s["bot"] else None,
                         s["staves"], s["exp"], s["bars"], s["ok"], s["span"],
                         (s.get("left")), (s.get("right")), s["open"], s.get("reason") or ""))
                print("     čáry:", s["lines"])

asyncio.run(main())
