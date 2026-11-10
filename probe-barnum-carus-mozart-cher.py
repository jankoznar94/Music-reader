#!/usr/bin/env python3
"""Dočíslování na DVOU reálných skenech (Mozart Davide penitente, Cherubini Requiem).

Pro každou stránku z NOTY_PAGES:
  1) `fillPageAt` — co appka našla (systémy, osnovy, čísla, toast, diagnostika),
  2) `fillSystemAt` — jeden systém s INDEXEM nasazeným nad první taktovou čáru,
     aby se ověřilo, že se číslo 1. taktu bere z indexu a ne z pole Další.

Index se seeduje přímo do `annotations` (barNum) — stejný tvar, jaký ukládá lupa.
PDF se bere z NOTY_PDF, stránky z NOTY_PAGES (1-based, jak je vidí uživatel).
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
IDX = json.loads(os.environ.get("NOTY_IDX", "[]"))   # [[page, cislo, x_b, y_b], ...]
SYS_TAP = json.loads(os.environ.get("NOTY_SYS", "{}"))  # {"3": [x_b, y_b]}


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for pg in PAGES:
            await h.goto(pg)
            r = await h.ev("""(async () => { const d = window.__barDev;
                d.barFillPreview.value = null;
                await d.fillPageAt({x:300, y:400});
                const scan = (window.__barPickDbg || []).filter(x => x.pageFillScan).slice(-1)[0];
                const fill = (window.__barPickDbg || []).filter(x => x.pageFill).slice(-1)[0];
                const p = d.barFillPreview.value;
                const out = {scan: scan ? scan.pageFillScan : null,
                             fill: fill ? fill.pageFill : null,
                             toast: d.toast.value, diag: null};
                if (!p) return JSON.stringify(out);
                const rows = {};
                for (const it of p.items) {
                  const y = Math.round(it.y1 + 10);
                  (rows[y] = rows[y] || []).push(it.text);
                }
                out.preview = {systems: p.systems, bars: p.bars, start: p.start,
                  withFirst: p.withFirst, fromIndex: p.fromIndex,
                  resync: p.resync, mismatch: p.mismatch};
                out.rows = Object.entries(rows).map(([y, t]) => [Number(y), t.join(" ")]);
                return JSON.stringify(out);
              })()""", await_promise=True)
            data = json.loads(r)
            print("=== %s str. %d" % (os.path.basename(PDF)[:22], pg))
            print("  toast:", data.get("toast"))
            sc = data.get("scan") or {}
            print("  scan: osnov %s | %s" % (sc.get("staves"), sc.get("reason") or ""))
            for s in sc.get("sys") or []:
                print("    sys top=%s bot=%s osnov %s/%s čar %s ok=%s span=%s open=%s close=%s"
                      % (s["top"], s["bot"], s["staves"], s["exp"], s["bars"],
                         s["ok"], s["span"], s["open"], s["close"]))
                print("       čáry:", s["lines"])
            if data.get("preview"):
                print("  NÁHLED:", json.dumps(data["preview"], ensure_ascii=False))
                for y, t in data.get("rows") or []:
                    print("    y=%s: %s" % (y, t))
            await h.ev("window.__barDev.barFillPreview.value = null; 1")

        if IDX:
            for page, n, xb, yb in IDX:
                await h.goto(page)
                r = await h.ev("""(async () => { const d = window.__barDev;
                    const s = await d.layerScale(d.currentPage.value);
                    d.annotations.value.items.push({ id: crypto.randomUUID(),
                      page: d.currentPage.value, tool: 'text', barNum: true,
                      text: %d, size: 12, color: '#000', opacity: 1, border: false,
                      x: Math.round(%f * s), y: Math.round(%f * s) });
                    return 1;
                  })()""" % (n, xb, yb), await_promise=True)
                print("  index %d na str. %d nasazen" % (n, page))

        REFILL = [int(x) for x in os.environ.get("NOTY_REFILL", "").split(",") if x.strip()]
        for page in REFILL:
            await h.goto(page)
            r = await h.ev("""(async () => { const d = window.__barDev;
                d.barFillPreview.value = null;
                await d.fillPageAt({x:300, y:400});
                const p = d.barFillPreview.value;
                if (!p) return JSON.stringify({none:true, toast:d.toast.value});
                const rows = {};
                for (const it of p.items) {
                  const y = Math.round(it.y1 + 10);
                  (rows[y] = rows[y] || []).push(it.text);
                }
                return JSON.stringify({toast:d.toast.value, systems:p.systems,
                  withFirst:p.withFirst, fromIndex:p.fromIndex,
                  rows:Object.entries(rows).map(([y,t]) => [Number(y), t.join(" ")])});
              })()""", await_promise=True)
            print("=== REFILL str. %d" % page)
            print(" ", r)

        if SYS_TAP:
            for page, (xb, yb) in [(int(k), v) for k, v in SYS_TAP.items()]:
                await h.goto(page)
                r = await h.ev("""(async () => { const d = window.__barDev;
                    const s = await d.layerScale(d.currentPage.value);
                    d.barFillPreview.value = null;
                    await d.fillSystemAt({x: %f * s, y: %f * s});
                    const p = d.barFillPreview.value;
                    const dbg = (window.__barPickDbg || []).slice(-1)[0];
                    if (!p) return JSON.stringify({none: true, toast: d.toast.value, dbg});
                    return JSON.stringify({ toast: d.toast.value, dbg,
                      first: p.first, firstSrc: p.firstSrc, start: p.start,
                      bars: p.bars, nums: p.items.map(i => i.text) });
                  })()""" % (xb, yb), await_promise=True)
                print("=== %s str. %d — JEDEN SYSTÉM (klepnutí %.0f,%.0f b)" %
                      (os.path.basename(PDF)[:22], page, xb, yb))
                print(" ", r)
                await h.ev("window.__barDev.barFillPreview.value = null; 1")


asyncio.run(main())
