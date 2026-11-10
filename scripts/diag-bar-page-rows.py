#!/usr/bin/env python3
"""DIAG: profil řádků stránky (podíl inkoustu + nejdelší vodorovný tah).

Proč: osnovy se hledají podle řádků s dlouhým tahem. Když na celostránkovém
renderu některé osnovy chybí, je potřeba vidět NAMĚŘENÉ hodnoty těch řádků,
ne hádat prahy. NOTY_Y0/NOTY_Y1 = rozsah v bodech PDF (default 380–620).
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
    "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
    "doc_1bb2c499f695_Mozart-Davide penitente.pdf")
PAGE = int(os.environ.get("NOTY_PAGE", "2"))
Y0 = float(os.environ.get("NOTY_Y0", "380"))
Y1 = float(os.environ.get("NOTY_Y1", "620"))
PPT = float(os.environ.get("NOTY_PPT", "5"))


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(PAGE)
        r = await h.ev("""(async () => {
            const d = window.__barDev;
            const pw = (await d.getPageWidthHeight(d.song, d.currentPage.value + 1)).width;
            const ph = (await d.getPageWidthHeight(d.song, d.currentPage.value + 1)).height;
            const cv = document.createElement('canvas');
            const THR = %f, PPT = %f, dpr = window.devicePixelRatio || 1;
            await d.renderPageRegion(d.song, d.currentPage.value + 1, cv,
                {x:0,y:0,w:pw,h:ph}, pw*PPT/dpr, ph*PPT/dpr);
            const w = cv.width, hgt = cv.height;
            const px = w / pw;
            const data = cv.getContext('2d', {willReadFrequently:true})
                           .getImageData(0,0,w,hgt).data;
            const y0 = Math.round(%f * px), y1 = Math.round(%f * px);
            const out = [];
            for (let y = y0; y < y1; y++) {
              let ink = 0, run = 0, best = 0;
              const off = y * w;
              for (let x = 0; x < w; x++) {
                const i = (off + x) * 4;
                const v = (data[i]*299 + data[i+1]*587 + data[i+2]*114)/1000;
                if (v < THR) { ink++; run++; if (run > best) best = run; }
                else run = 0;
              }
              out.push([+(y/px).toFixed(2), +(ink/w).toFixed(3), +(best/w).toFixed(3)]);
            }
            return JSON.stringify({w, hgt, px, rows: out});
        })()""" % (float(os.environ.get("NOTY_THR","200")), PPT, Y0, Y1), await_promise=True)
        d = json.loads(r)
        print("plátno %s×%s (%.2f px/b), řádky s tahem ≥ 0.25 nebo ink ≥ 0.12:"
              % (d["w"], d["hgt"], d["px"]))
        prev = None
        for y, frac, run in d["rows"]:
            if frac < 0.12 and run < 0.25:
                continue
            gap = "" if prev is None else " +%.1f" % (y - prev)
            print("  y=%7.2f  ink=%.3f  tah=%.3f%s" % (y, frac, run, gap))
            prev = y

asyncio.run(main())
