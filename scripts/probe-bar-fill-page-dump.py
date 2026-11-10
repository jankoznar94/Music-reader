#!/usr/bin/env python3
"""Dočíslování CELÉ STRÁNKY — výpis, co appka na stránce našla.

Pro každou stránku z NOTY_PAGES (default 2,4,7,15) zavolá fillPageAt a vypíše
systémy, čísla v náhledu a čas. Slouží k diffu staré a nové verze detekce:
zajímá nás hlavně to, jestli se nějaký systém neobjeví dvakrát (čísla se
opakují) a kolik čísel každý systém dostal.
"""
import asyncio
import importlib.util
import json
import os
import sys
import time

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
PAGES = [int(x) for x in os.environ.get("NOTY_PAGES", "2,4,7,15").split(",")]


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            await h.goto(pg)
            t0 = time.time()
            r = await h.ev("""(async () => { const d=window.__barDev;
                d.barFillPreview.value = null;
                await d.fillPageAt({x:300, y:400});
                const p = d.barFillPreview.value;
                const dbg = (window.__barPickDbg || []).slice(-2);
                if (!p) return JSON.stringify({none:true, toast:d.toast.value, dbg});
                const sys = {};
                for (const it of p.items) {
                  const y = Math.round(it.y1 + 10);
                  (sys[y] = sys[y] || []).push(it.text);
                }
                return JSON.stringify({ systems: p.systems, bars: p.bars,
                  start: p.start, withFirst: p.withFirst, fromIndex: p.fromIndex,
                  resync: p.resync, mismatch: p.mismatch, toast: d.toast.value, dbg,
                  rows: Object.entries(sys).map(([y, t]) => [Number(y), t.join(' ')]) });
              })()""", await_promise=True)
            dt = time.time() - t0
            data = json.loads(r) if r else None
            print("=== str. %d (%.1f s)" % (pg, dt))
            if not data or data.get("none"):
                print("  náhled není")
                if data:
                    print("  toast:", data.get("toast"))
                    print("  dbg:", json.dumps(data.get("dbg"), ensure_ascii=False)[:1200])
            else:
                print("  systémů: %s | čísel: %s | rozsah %s–%s | dopočteno prvních: %s"
                      % (data["systems"], data["bars"], data["start"],
                         (data["start"] + data["bars"] - 1) if data["bars"] else "?",
                         data["withFirst"]))
                for y, t in data["rows"]:
                    print("   y=%s: %s" % (y, t))
            await h.ev("window.__barDev.barFillPreview.value = null; 1")
            sys.stdout.flush()

asyncio.run(main())
