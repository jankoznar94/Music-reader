#!/usr/bin/env python3
"""DIAGNOSTIKA detekce taktových čar: co appka v systému VIDÍ.

Pro každý systém na stránkách vypíše všechny kandidáty na taktovou čáru
(x v bodech PDF, kolik osnov je vidí) a kolik osnov systém má.
Krok se schválně nastaví vysoký, aby se vypsali VŠICHNI kandidáti.
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
REF_W = 760.0
# (strana, pdf y) — pokrývá systémy na stránce
POINTS = [(2, 180), (2, 355), (2, 530), (2, 700),
          (4, 200), (4, 400), (4, 600),
          (8, 180), (8, 400), (8, 620)]


async def tap(h, page, py):
    if not await h.ev("!!document.querySelector('.barnum-panel')"):
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
    await h.wait_for("document.querySelectorAll('.bn-input').length >= 2", timeout=8, label="bn")
    await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
        ins[1].value='16'; ins[1].dispatchEvent(new Event('change',{bubbles:true})); return 1; })()""")
    await asyncio.sleep(0.2)
    vb = [float(v) for v in (await h.ev(
        "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
    s = REF_W / 595.2
    pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
        const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
        return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + 300 * s, vb[1] + py * s)))
    await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
    await asyncio.sleep(0.2)
    await h.finger_tap(pt["x"], pt["y"], r=11)
    await asyncio.sleep(2.0)
    dbg = json.loads(await h.ev(
        "JSON.stringify((window.__barPickDbg||[]).filter(d=>d&&d.fill).slice(-1))"))
    return dbg[0]["fill"] if dbg else {}


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        cur = None
        for (page, py) in POINTS:
            if cur != page:
                await h.goto(page)
                cur = page
            d = await tap(h, page, py)
            # po vložení se panel zavírá → uvolnit pro další pokus
            pass
            print("str %d y %d: need %s osnov %s ok %s staves_top %.1f"
                  % (page, py, d.get("need"), d.get("staves"), d.get("ok"), (d.get("top") or 0)))
            print("   kandidáti:", d.get("cands"))
            print()


asyncio.run(main())
