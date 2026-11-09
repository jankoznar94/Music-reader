#!/usr/bin/env python3
"""Dočíslování: co appka najde a kam dá čísla (x pozice) — bez DB.

Pro každý bod: nastaví Krok + první číslo, klepne, vypíše `lines` (x čar
v bodech PDF) a toast. Očekávané hodnoty (změřeno nezávisle z obrázku):
  str 2, y 230 (systém 1, 4 takty): 65/259/361/464
  str 2, y 400 (systém 2, 4 takty): 65/259/361/464
  str 2, y 560 (systém 3, 3 takty): 64/247/407
  str 4, y 200/400/600 (3 takty):   75/266/421
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
CASES = [(2, 230, 4), (2, 400, 4), (2, 560, 3),
         (4, 200, 3), (4, 400, 3), (4, 600, 3)]


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        cur = None
        for (page, py, krok) in CASES:
            if cur != page:
                await h.goto(page); cur = page
            if not await h.ev("!!document.querySelector('.barnum-panel')"):
                await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
                    .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
                await asyncio.sleep(0.8)
            for _try in range(4):
                try:
                    await h.wait_for("document.querySelectorAll('.bn-input').length >= 2", timeout=4, label="bn")
                    break
                except Exception:
                    await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]\n                        .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()")
                    await asyncio.sleep(0.6)
            await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
                ins[0].value='1'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
                ins[1].value='%d'; ins[1].dispatchEvent(new Event('change',{bubbles:true})); return 1; })()""" % krok)
            await asyncio.sleep(0.3)
            vb = [float(v) for v in (await h.ev(
                "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
            s = vb[2] / 595.2
            pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
                const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
                return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + 300 * s, vb[1] + py * s)))
            await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
            await asyncio.sleep(0.3)
            await h.finger_tap(pt["x"], pt["y"], r=11)
            await asyncio.sleep(2.5)
            raw = await h.ev("JSON.stringify((window.__barPickDbg||[]).filter(d=>d&&d.fill).slice(-1))")
            d = (json.loads(raw) or [{}])[0].get("fill", {})
            toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''")
            print("str %d y %d Krok %d: ok=%s osnov=%s lines=%s"
                  % (page, py, krok, d.get("ok"), d.get("staves"), d.get("lines")))
            print("    toast:", toast.strip()[:120])


asyncio.run(main())
