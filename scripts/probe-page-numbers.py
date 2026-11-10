#!/usr/bin/env python3
"""Dočíslování celé stránky: co appka vloží (náhled) na zadané stránce.

Používá se k ověření čísel, když nemáme Janovy anotace: vypíše systémy,
jejich hranice, počet osnov, čáry a čísla, která by se vložila.
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
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "20").split(",")]

JS = """
(async () => {
  const d = window.__barDev;
  await d.fillPageAt({x: 10, y: 10});
  const pv = d.barFillPreview.value;
  const dbg = window.__barPickDbg || {};
  return JSON.stringify({
    systems: pv ? pv.systems : null,
    items: pv ? pv.items.map(i => [i.text, Math.round(i.x), Math.round(i.y)]) : null,
    start: pv ? pv.start : null,
    fromIndex: pv ? pv.fromIndex : null,
    withFirst: pv ? pv.withFirst : null,
    resync: pv ? pv.resync : null,
    scan: dbg.pageFillScan || null,
    fill: dbg.pageFill || null,
    diag: d.barPickDiag ? d.barPickDiag.value : null,
    toast: d.toast ? d.toast.value : null,
  });
})()
"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            await h.goto(pg)
            res = await h.ev("(" + JS + ")", await_promise=True)
            d = json.loads(res) if res else {}
            print("=== str.", pg)
            print("  systémy:", d.get("systems"), "items:", len(d.get("items") or []))
            if d.get("items"):
                print("  čísla:", [i[0] for i in d["items"]])
            print("  fromIndex/withFirst/resync:", d.get("fromIndex"),
                  d.get("withFirst"), d.get("resync"))
            print("  fill:", d.get("fill"))
            print("  diag:", d.get("diag"), "| toast:", d.get("toast"))


asyncio.run(main())
