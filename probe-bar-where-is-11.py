#!/usr/bin/env python3
"""Kde appka hledá číslo 11: klepne na SKUTEČNÉ místo čísla (x≈37) a na místo,
které jí vychází z přepočtu (x≈127). Podle přečteného čísla je jasné, který
přepočet je správný.
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


async def click_tb(h, title):
    return await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('%s')); if (b) b.click(); return !!b; })()""" % title)


async def lupa_on(h):
    if not await h.ev("!!document.querySelector('.annot-panel')"):
        await h.annot_toggle()
    await h.ev("""(() => { const b=[...document.querySelectorAll('.ap-tool')]
        .find(x=>(x.title||'').startsWith('Čísla taktů')); if(b) b.click(); return !!b; })()""")
    await h.wait_for("!!document.querySelector('.bn-pick')", timeout=8, label="barnum panel")
    if not await h.ev("!!document.querySelector('.bn-pick.on')"):
        await h.ev("(() => { const b=document.querySelector('.bn-pick'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.3)
    await h.ev("""(() => { const b=document.querySelector('.ap-collapse');
        if (b && b.title === 'Sbalit') { b.click(); return true; } return false; })()""")
    await asyncio.sleep(0.4)


async def tap(h, x, y, label):
    n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
    await h.finger_tap(x, y, r=10)
    for _ in range(150):
        dbg = json.loads(await h.ev(
            "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
        if any(isinstance(d, dict) and ("ocr" in d or "miss" in d) for d in dbg):
            break
        await asyncio.sleep(0.2)
    dbg = json.loads(await h.ev(
        "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
    ocr = next((d["ocr"] for d in dbg if isinstance(d, dict) and "ocr" in d), {})
    lay = next((d for d in dbg if isinstance(d, dict) and "page" in d and "px" in d), {})
    diag = await h.ev("(document.querySelector('.bn-diag')||{}).textContent||''")
    if os.environ.get("DUMP"):
        print("   dbg:", json.dumps(dbg, ensure_ascii=False)[:700])
    print("%-14s obraz %4d,%4d → vrstva %s,%s → pdf %s | čtení %s (jistota %s) %s"
          % (label, x, y, lay.get("px"), lay.get("py"), ocr.get("pdf"),
             ocr.get("digits"), ocr.get("confidence"),
             "OK" if str(ocr.get("digits")) == "11" else "—"))
    return ocr


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(pdf=PDF)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.5)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.4)
        await h.goto(16)
        await asyncio.sleep(1.2)
        await lupa_on(h)
        # skutečná poloha čísla na obrazovce (z výřezu: x≈37, y≈829)
        await tap(h, 37, 768, "skutečné číslo")
        await tap(h, 127, 768, "o 90 px vpravo")
        await tap(h, 60, 768, "kousek vedle")
        await tap(h, 40, 780, "pod číslem")


asyncio.run(main())
