#!/usr/bin/env python3
"""Citlivost detekce na rozlišení renderu: pro každé PPT (px na bod) vypíše
systémy stránky 5 a 6 — počet osnov a nalezené čáry. Odhalí, které čáry
vyskakují/mizí podle rozlišení (na tabletu je jiné dpr než v harnessu)."""
import asyncio
import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.path.expanduser(
    "~/.hermes/profiles/cfsb-agent/cache/documents/doc_1bb2c499f695_Mozart-Davide penitente.pdf")

JS = r"""(async () => {
  const d = window.__barDev, page = d.currentPage.value;
  let pw = 595, ph = 842;
  try { const q = await d.getPageWidthHeight(d.song, page + 1); pw = q.width; ph = q.height; } catch (e) {}
  const out = [];
  for (const PPT of [3, 4, 5, 6, 7, 8]) {
    const cv = document.createElement('canvas');
    await d.renderPageRegion(d.song, page + 1, cv, {x:0,y:0,w:pw,h:ph}, pw*PPT, ph*PPT);
    const pxPerPt = cv.width / pw;
    const dpg = d.detectPageSystems(cv, pxPerPt, { krok: 1 });
    out.push({PPT, staves: dpg.staves, sys: (dpg.systems||[]).map(q => ({
      top: Math.round(q.sysTop), bot: Math.round(q.sysBot), st: q.stavesFound, exp: q.stavesExpected,
      ok: q.ok, span: q.spanOk, bars: q.bars,
      lines: q.lines.map(v => Math.round(v)), open: q.opening == null ? null : Math.round(q.opening/pxPerPt),
      close: q.closing == null ? null : Math.round(q.closing/pxPerPt)}))});
  }
  return JSON.stringify(out);
})()"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for page in (5, 6):
            await h.goto(page)
            await asyncio.sleep(0.3)
            r = json.loads(await h.ev(JS, await_promise=True))
            print("PAGE", page)
            for row in r:
                print("  PPT", row["PPT"], "staves", row["staves"])
                for s in row["sys"]:
                    print("    top %3d bot %3d st %d/%d ok %s span %s bars %d lines %s open %s close %s"
                          % (s["top"], s["bot"], s["st"], s["exp"], s["ok"], s["span"], s["bars"],
                             s["lines"], s["open"], s["close"]))

asyncio.run(main())
