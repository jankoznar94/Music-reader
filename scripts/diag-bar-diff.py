#!/usr/bin/env python3
"""Sken taktových čar po stránkách: pro každý systém vypíše počet vnitřních čar
a jejich x. Slouží k DIFFU před/po změně barLines.js (nic nemění v datech).

Výstup: jeden řádek na systém:  str <p> top <y> osnov <n> bars <k> lines <x/x/..>
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

PDF = ("/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
       "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
       "doc_1bb2c499f695_Mozart-Davide penitente.pdf")

PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "2,4,6,7,8,10").split(",")]
STEP = float(os.environ.get("NOTY_STEP", "60"))
OUT = os.environ.get("NOTY_OUT", "/tmp/bar-diff.json")

JS = """(async () => {
  const p = window.__barDev;
  const page = %d, py = %f;
  const {width:pw, height:ph} = await p.getPageWidthHeight(p.song, page);
  const bandH = 520;
  const crop = {x:0, y:Math.max(0, Math.min(py - bandH/2, ph - bandH)), w:pw,
                h:Math.min(bandH, ph)};
  const cv = document.createElement('canvas');
  const PPT = 6, dpr = window.devicePixelRatio || 1;
  await p.renderPageRegion(p.song, page, cv, crop, pw*PPT/dpr, crop.h*PPT/dpr);
  const d = p.detectBarlines(cv, cv.width / crop.w, {ypt: py, offsetY: crop.y});
  return JSON.stringify({ok:d.ok, bars:d.bars, staves:d.staves, sysTop:d.sysTop,
    sysBot:d.sysBot, top:d.top, lines:d.lines.map(v=>+v.toFixed(1)),
    opening:d.opening, closing:d.closing, diag:d.diag});
})()"""


async def main():
    rows = []
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for page in PAGES:
            await h.goto(page)
            y = 30.0
            while y < 820:
                r = json.loads(await h.ev(JS % (page, y), await_promise=True))
                if r['ok']:
                    key = (page, round(r['sysTop'] or 0, 1))
                    if not any((row[0], round(row[1], 1)) == key for row in rows):
                        rows.append([page, r['sysTop'], r['sysBot'], r['staves'],
                                     r['bars'], r['lines'], r['opening'], r['closing'],
                                     r.get('diag')])
                y += STEP
            print("str %d hotova, systémů %d" % (page, sum(1 for r in rows if r[0] == page)))
    with open(OUT, "w") as f:
        json.dump(rows, f, indent=0)
    for r in rows:
        d = r[8] or {}
        print("str %d top %.1f osnov %d bars %d lines %s open %s close %s | R %s sp %.2f dens %s tail %s barP %s"
              % (r[0], r[1], r[3], r[4], [round(v) for v in r[5]],
                 None if r[6] is None else round(r[6], 1),
                 None if r[7] is None else round(r[7], 1),
                 d.get('staffRight'), d.get('space') or 0, d.get('closingDens'),
                 d.get('tail'), d.get('barP')))

asyncio.run(main())
