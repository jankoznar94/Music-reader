#!/usr/bin/env python3
"""DIAG: surové skupiny řádků (staff.raw), osnovy, mezery a hranice systémů.

Narozdíl od `diag-bar-page-staves.py` vypíše i `rawGroupsPt` (skupiny řádků PŘED
filtrem 4–8 linek), takže je vidět, která osnova vypadla a proč (kolik linek,
jaká mezera). Stránky z NOTY_PAGES, PDF z NOTY_PDF.
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
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "3").split(",")]


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
                let outW = pw * PPT / dpr, outH = ph * PPT / dpr;
                const MAX_PX = 12e6;                       // STEJNÝ strop jako appka
                const areaPx = outW * outH * dpr * dpr;
                if (areaPx > MAX_PX) { const k = Math.sqrt(MAX_PX / areaPx); outW *= k; outH *= k; }
                await d.renderPageRegion(d.song, d.currentPage.value + 1, cv,
                    {x:0,y:0,w:pw,h:ph}, outW, outH);
                const pxPerPt = cv.width / pw;
                const px = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
                let hsh = 0, inkc = 0;
                for (let i = 0; i < px.length; i += 4) {
                  const g = (px[i]*299 + px[i+1]*587 + px[i+2]*114)/1000;
                  hsh = (hsh + g) % 1000000007; if (g < 160) inkc++;
                }
                const res = m.detectPageSystems(cv, pxPerPt, { krok: d.barStep.value });
                return JSON.stringify({ raw: res.rawGroupsPt, rows: res.rowsPt,
                    canvas: [cv.width, cv.height, +(pxPerPt).toFixed(3), hsh, inkc],
                    staffDbg: res.staffDbg,
                    staves: res.staves, gapBase: res.gapBasePt, gaps: res.gapsPt,
                    sys: res.systems.map(s => ({ top: s.sysTop, bot: s.sysBot,
                        st: s.stavesFound, exp: s.stavesExpected, bars: s.bars,
                        lines: s.lines.map(v => Math.round(v)), ok: s.ok,
                        reason: s.reason || '' })) });
              })()""", await_promise=True)
            data = json.loads(r)
            print("=== str. %d — osnov %d, základ mezer %.1f b  plátno %s"
                  % (pg, data["staves"], data["gapBase"], data.get("canvas")))
            print("  surové skupiny řádků (od-do, počet linek):")
            for g in data["raw"]:
                print("    %7.1f–%7.1f  %d linek" % (g[0], g[1], g[2]))
            print("  osnovy (od-do, linek):", ["%.1f–%.1f/%d" % (a, b, n)
                                                for a, b, n in data["rows"]])
            print("  filtr osnov (od-do, linek, verdikt):")
            for g in data.get("staffDbg") or []:
                if g[3] != "ok":
                    print("    %7.1f–%7.1f  %d linek  → %s" % (g[0], g[1], g[2], g[3]))
                    print("        řádky po opravě:", g[4] if len(g) > 4 else None)
                    print("        řádky před opravou:", g[5] if len(g) > 5 else None)
            print("  mezery (b/ink):", data["gaps"])
            for s in data["sys"]:
                print("  SYSTÉM %s–%s osnov %s/%s čar %s ok=%s %s"
                      % (round(s["top"]) if s["top"] else None,
                         round(s["bot"]) if s["bot"] else None,
                         s["st"], s["exp"], s["bars"], s["ok"], s["reason"]))
                print("     čáry:", s["lines"])
            import sys as _s
            _s.stdout.flush()


asyncio.run(main())
