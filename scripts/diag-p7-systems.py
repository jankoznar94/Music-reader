#!/usr/bin/env python3
"""Diagnostika: co detectBarlines vidí na str. 7 (třetí systém) a kolik taktů
hlásí na známých stránkách. Čistě čte, nic nemění."""
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

# Přesný pás jako v aplikaci (520 b, klepnutí doprostřed).
BAND_JS = """(async () => {
  const p = window.__barDev;
  const page = %d, py = %f;
  const {width:pw, height:ph} = await p.getPageWidthHeight(p.song, page);
  const bandH = 520;
  const crop = {x:0, y:Math.max(0, Math.min(py - bandH/2, ph - bandH)), w:pw,
                h:Math.min(bandH, ph)};
  const cv = document.createElement('canvas');
  const PPT = 6, dpr = window.devicePixelRatio || 1;
  await p.renderPageRegion(p.song, page, cv, crop, pw*PPT/dpr, crop.h*PPT/dpr);
  const pxPerPt = cv.width / crop.w;
  const d = p.detectBarlines(cv, pxPerPt, {ypt: py, offsetY: crop.y});
  return JSON.stringify({page, crop, pxPerPt, w:cv.width, h:cv.height,
    lines:d.lines.map(v=>+v.toFixed(1)), bars:d.bars, ok:d.ok, top:d.top,
    staves:d.staves, diag:d.diag, dbg:d.dbg, cands:d.cands,
    opening:d.opening, closing:d.closing, sysTop:d.sysTop, sysBot:d.sysBot,
    staffLeft:d.dbg&&d.dbg.staffLeft, staffRight:d.dbg&&d.dbg.staffRight});
})()"""

# Kolik svislých sloupců a s jakým pokrytím má KAŽDÁ osnova v pásu (bez filtru).
COLS_JS = """(async () => {
  const p = window.__barDev;
  const page = %d, py = %f;
  const {width:pw, height:ph} = await p.getPageWidthHeight(p.song, page);
  const bandH = %d;
  const crop = {x:0, y:Math.max(0, Math.min(py - bandH/2, ph - bandH)), w:pw,
                h:Math.min(bandH, ph)};
  const cv = document.createElement('canvas');
  const PPT = 6, dpr = window.devicePixelRatio || 1;
  await p.renderPageRegion(p.song, page, cv, crop, pw*PPT/dpr, crop.h*PPT/dpr);
  const pxPerPt = cv.width / crop.w;
  const d = p.detectBarlines(cv, pxPerPt, {ypt: py, offsetY: crop.y});
  const dbg = d.dbg || {};
  const out = {crop, pxPerPt, staffs: dbg.all, staff: dbg.staff};
  return JSON.stringify(out);
})()"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(7)
        # Nejdřív najdi, kde na str. 7 jsou systémy: skenuj klepnutím po 25 b.
        found = []
        y = 30.0
        while y < 800:
            r = await h.ev(BAND_JS % (7, y), await_promise=True)
            r = json.loads(r)
            sig = (r['staves'], r.get('sysTop'), r.get('sysBot'))
            if not found or found[-1][1:] != sig:
                found.append([y, r['staves'], r.get('sysTop'), r.get('sysBot'),
                              r['bars'], [round(v) for v in r['lines']], r.get('ok')])
            y += 25
        print("=== str. 7: sken systémů (klepnutí y → stavy ===")
        for f in found:
            print(f)
        print()
        # Detail třetího systému
        sys3 = [f for f in found if f[0] >= 0]
        for f in found:
            r = json.loads(await h.ev(BAND_JS % (7, f[0]), await_promise=True))
            print("--- tap y %.0f | systém %.1f–%.1f | osnov %d | ok=%s bars=%d"
                  % (f[0], r.get('sysTop') or 0, r.get('sysBot') or 0, r['staves'],
                     r['ok'], r['bars']))
            print("    lines:", [round(v) for v in r['lines']])
            print("    cands:", r['cands'])
            print("    staff:", r['staffLeft'], "→", r['staffRight'],
                  "| diag:", r['diag'])
            print("    dbg.all:", (r['dbg'] or {}).get('all'),
                  "need:", (r['dbg'] or {}).get('need'))
            print()
    # Poznámka: klepnutím se nemění žádný stav, jde jen o čtení.

asyncio.run(main())
