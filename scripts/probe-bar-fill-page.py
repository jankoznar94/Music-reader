#!/usr/bin/env python3
"""Dočíslování CELÉ STRÁNKY: klepne se do 1. systému str. 2 s indexem 5 a ověří,
že appka očísluje všechny systémy stránky popořadě (a naváže na další).

Kontroluje: počet systémů, čísla v náhledu, čas výpočtu, a že první takt
systému bez indexu se taky očísluje.
"""
import asyncio
import importlib.util
import json
import os
import time

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = ("/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
       "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
       "doc_1bb2c499f695_Mozart-Davide penitente.pdf")


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        # index: číslo 5 nad prvním systémem (y ~264 - 12)
        s = await h.ev("""(async () => { const d=window.__barDev;
            return JSON.stringify(await d.layerScale(d.currentPage.value)); })()""",
            await_promise=True)
        s = json.loads(s)
        await h.ev("""(async () => { const d=window.__barDev;
            const it=d.annotations.value.items;
            for (let i=it.length-1;i>=0;i--) if (it[i].barNum) it.splice(i,1);
            it.push({ id:'idx', page:d.currentPage.value, tool:'text', barNum:true,
                      hidden:true, text:'5', size:16, color:'#000000', opacity:1,
                      border:false, x:70*%f, y:252*%f });
            return 1; })()""" % (s, s), await_promise=True)
        t0 = time.time()
        r = await h.ev("""(async () => { const d=window.__barDev;
            await d.fillPageAt({x:300*%f, y:400*%f});
            const p=d.barFillPreview.value;
            return JSON.stringify(p ? {bars:p.bars, start:p.start, systems:p.systems,
              withFirst:p.withFirst, fromIndex:p.fromIndex,
              nums:p.items.map(i=>i.text)} : null); })()""" % (s, s), await_promise=True)
        dt = time.time() - t0
        print("výpočet %.1f s" % dt)
        p = json.loads(r) if r else None
        print("náhled:", p)
        if p:
            print("systémů:", p["systems"], "| čísel:", p["bars"], "| rozsah:",
                  p["nums"][0], "–", p["nums"][-1],
                  "| dopočteno prvních taktů:", p["withFirst"])
        # další stránka navazuje
        await h.goto(3)
        r2 = await h.ev("""(async () => { const d=window.__barDev;
            await d.fillPageAt({x:300*%f, y:300*%f});
            const p=d.barFillPreview.value;
            return JSON.stringify(p ? {first:p.items[0].text, bars:p.bars,
              systems:p.systems} : null); })()""" % (s, s), await_promise=True)
        print("str. 3 navazuje:", r2)
        # úklid: náhled zrušit
        await h.ev("window.__barDev.barFillPreview.value = null; 1")

asyncio.run(main())
