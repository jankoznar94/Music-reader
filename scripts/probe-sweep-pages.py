#!/usr/bin/env python3
"""Přejede VŠECHNY stránky nahraného PDF a vypíše, kde detekce selže
(systém bez čar / uříznutý). Jen čte."""
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
FROM = int(os.environ.get("NOTY_FROM", "1"))
TO = int(os.environ.get("NOTY_TO", "0"))

JS = r"""(async () => {
  const d = window.__barDev, page = d.currentPage.value;
  let pw = 595, ph = 842;
  try { const q = await d.getPageWidthHeight(d.song, page + 1); pw = q.width; ph = q.height; } catch (e) {}
  const PPT = 5, dpr = window.devicePixelRatio || 1;
  let outW = pw * PPT / dpr, outH = ph * PPT / dpr;
  const MAX_PX = 12e6, area = outW * outH * dpr * dpr;
  if (area > MAX_PX) { const k = Math.sqrt(MAX_PX / area); outW *= k; outH *= k; }
  const cv = document.createElement('canvas');
  await d.renderPageRegion(d.song, page + 1, cv, {x:0,y:0,w:pw,h:ph}, outW, outH);
  const pxPerPt = cv.width / pw;
  const g = d.detectPageSystems(cv, pxPerPt, { krok: 1 });
  return JSON.stringify({
    staves: g.staves, reason: g.reason || null,
    sys: (g.systems || []).map(q => [Math.round(q.sysTop), Math.round(q.sysBot),
      q.stavesFound, q.stavesExpected, q.bars, q.spanOk, q.ok]),
  });
})()"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        total = int(await h.ev("window.__barDev.song.pageCount || 0") or 0)
        last = TO or total
        bad = []
        for p in range(FROM, last + 1):
            await h.goto(p)
            await asyncio.sleep(0.15)
            d = json.loads(await h.ev(JS, await_promise=True))
            issues = []
            if d.get("reason"):
                issues.append("DŮVOD: " + d["reason"])
            for s in d["sys"]:
                if not s[5] or not s[6]:
                    issues.append("systém y%d-%d %d/%d osnov span=%s ok=%s"
                                  % (s[0], s[1], s[2], s[3], s[5], s[6]))
            mark = "OK " if not issues else "!! "
            print("%sstr.%2d osnov %2d systémů %d %s" %
                  (mark, p, d["staves"], len(d["sys"]), "; ".join(issues)))
            if issues:
                bad.append(p)
        print("hotovo, problémové stránky:", bad)

asyncio.run(main())
