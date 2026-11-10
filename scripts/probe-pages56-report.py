#!/usr/bin/env python3
"""Reprodukce Janova hlášení: dočíslování stránky 5 a 6 se skrytými indexy
(vytištěná čísla) a dočíslování jednotlivých systémů. Nic neukládá."""
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

# stránka -> [(vytištěné číslo, x, y v bodech PDF)]  (x = kde stojí vytištěné
# číslo, tj. nad první taktovou čarou systému — tak to ukládá lupa)
INDEXES = {
    5: [(30, 33, 42), (33, 33, 296), (37, 30, 547)],
    6: [(42, 68, 42), (47, 68, 344), (52, 71, 662)],
}
# kliknutí do systému (bod PDF) pro dočíslování jednoho systému
CLICKS = {
    5: [(300, 110), (300, 240), (300, 400), (300, 660)],
    6: [(300, 180), (300, 480), (300, 730)],
}


async def set_indexes(h, page):
    s = await h.ev("(async () => window.__barDev.layerScale(window.__barDev.currentPage.value))()",
                   await_promise=True)
    s = float(s)
    items = ",".join(
        "{id:'idx%d',page:%d,tool:'text',barNum:true,hidden:true,text:'%d',size:16,"
        "color:'#000000',opacity:1,border:false,x:%f,y:%f}" % (i, page - 1, n, x * s, y * s)
        for i, (n, x, y) in enumerate(INDEXES[page]))
    await h.ev("""(() => { const it = window.__barDev.annotations.value.items;
        for (let i = it.length - 1; i >= 0; i--) if (it[i].barNum) it.splice(i, 1);
        for (const o of [%s]) it.push(o);
        return it.length; })()""" % items)
    return s


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for page in (5, 6):
            await h.goto(page)
            s = await set_indexes(h, page)
            r = await h.ev("""(async () => { const d = window.__barDev;
                await d.fillPageAt({x:300*%f, y:400*%f});
                const p = d.barFillPreview.value; if (!p) return 'null';
                return JSON.stringify({pageMode: !!p.pageMode, systems: p.systems,
                  fromIndex: p.fromIndex, withFirst: p.withFirst, resync: p.resync,
                  items: p.items.map(i => [i.text, Math.round(i.x / %f), Math.round(i.y / %f)])}); })()"""
                         % (s, s, s, s), await_promise=True)
            print("PAGE %d pageMode: %s" % (page, r))
            await h.ev("window.__barDev.barFillPreview.value = null; 1")
            d = json.loads(await h.ev("(() => JSON.stringify(window.__barDev.__dbg || {}))()") or "{}")
            for (cx, cy) in CLICKS[page]:
                r = await h.ev("""(async () => { const d = window.__barDev;
                    await d.fillSystemAt({x:%f*%f, y:%f*%f});
                    const p = d.barFillPreview.value; if (!p) return 'null';
                    return JSON.stringify({first: p.first, firstSrc: p.firstSrc,
                      start: p.start, bars: p.bars, seen: p.seen, mismatch: p.mismatch,
                      items: p.items.map(i => [i.text, Math.round(i.x / %f)])}); })()"""
                                 % (cx, s, cy, s, s), await_promise=True)
                print("  sys click %d,%d -> %s" % (cx, cy, r))
                dbg = await h.ev("JSON.stringify(window.__barPickDbg || null)")
                print("     dbg:", dbg)
                await h.ev("window.__barDev.barFillPreview.value = null; 1")

asyncio.run(main())
