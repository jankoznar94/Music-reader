#!/usr/bin/env python3
"""Diagnostika dočíslování stránek 5 a 6 (Mozart): vypíše systémy, čáry,
podpory kandidátů a důvody selhání. Jen čte, nic neukládá."""
import asyncio
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.environ.get("NOTY_PDF", os.path.expanduser(
    "~/.hermes/profiles/cfsb-agent/cache/documents/doc_1bb2c499f695_Mozart-Davide penitente.pdf"))
PAGES = [int(p) for p in os.environ.get("NOTY_PAGES", "5,6").split(",")]

JS_DUMP = r"""(async () => {
  const d = window.__barDev;
  const page = d.currentPage.value;
  const s = await d.layerScale(page);
  let pw = 595, ph = 842;
  try { const q = await d.getPageWidthHeight(d.song, page + 1); pw = q.width; ph = q.height; } catch (e) {}
  const PPT = 5, dpr = window.devicePixelRatio || 1;
  let outW = pw * PPT / dpr, outH = ph * PPT / dpr;
  const MAX_PX = 12e6, area = outW * outH * dpr * dpr;
  if (area > MAX_PX) { const k = Math.sqrt(MAX_PX / area); outW *= k; outH *= k; }
  const cv = document.createElement('canvas');
  await d.renderPageRegion(d.song, page + 1, cv, {x:0,y:0,w:pw,h:ph}, outW, outH);
  const pxPerPt = cv.width / pw;
  const dpg = d.detectPageSystems(cv, pxPerPt, { krok: Number(d.barStep.value) || 1 });
  const idx = (d.annotations.value.items || [])
     .filter(it => it && it.barNum && it.page === page && it.y != null)
     .map(it => ({n: it.text, x: Math.round(it.x), yPdf: Math.round(it.y / s)}));
  return JSON.stringify({
    page, pxPerPt, staves: dpg.staves, reason: dpg.reason,
    rowsPt: dpg.rowsPt, rawGroupsPt: dpg.rawGroupsPt, gapBasePt: dpg.gapBasePt,
    gapsPt: dpg.gapsPt,
    systems: (dpg.systems || []).map(q => ({
      ok: q.ok, reason: q.reason, spanOk: q.spanOk,
      top: q.sysTop, bot: q.sysBot, staves: q.stavesFound, exp: q.stavesExpected,
      bars: q.bars, lines: q.lines, opening: q.opening, closing: q.closing,
      cands: q.cands, diag: q.diag, staffLeft: q.staffLeftPt,
    })),
    idx,
  });
})()"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for p in PAGES:
            await h.goto(p)
            await asyncio.sleep(0.4)
            r = json.loads(await h.ev(JS_DUMP, await_promise=True))
            print(json.dumps({"page": p}, ensure_ascii=False))
            print(json.dumps(r, ensure_ascii=False, indent=1))

asyncio.run(main())
