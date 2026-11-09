#!/usr/bin/env python3
"""Co lupa skutečně přečetla: vypíše VŠECHNA čtení (`reads`) a nabídku (`choice`).

Slouží k ověření, že se kandidáti pro tlačítka sbírají i z reálného OCR a že
úspěšné čtení nabídku nedělá (nevyskočí tlačítka, když je jasno).
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
CASES = [(8, 69.0, 46.8, 75), (4, 79.5, 294.6, 24), (6, 75.8, 662.9, 52), (2, 67.1, 515.2, 9)]
REF_W = 760.0

TO_SCREEN = """(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=%f/595.2; const g=svg.getScreenCTM();
  const p=new DOMPoint(%f + %f*s, %f + %f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y}); })()"""


async def ensure_lupa(h, page):
    cur = await h.ev("document.querySelector('.tb-page') && document.querySelector('.tb-page').textContent.trim()")
    if str(cur).split(" / ")[0].strip() != str(page):
        await h.goto(page)
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


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for page, px, py, truth in CASES:
            await ensure_lupa(h, page)
            vb = [float(v) for v in (await h.ev(
                "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
            pt = json.loads(await h.ev(TO_SCREEN % (REF_W, vb[0], px, vb[1], py)))
            n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
            await h.finger_tap(pt["x"], pt["y"], r=10)
            for _ in range(120):
                dbg = json.loads(await h.ev(
                    "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
                if any(isinstance(d, dict) and "ocr" in d for d in dbg):
                    break
                await asyncio.sleep(0.2)
            ocr = next((d["ocr"] for d in dbg if isinstance(d, dict) and "ocr" in d), {})
            ch = await h.ev("document.querySelectorAll('.bn-choice-btn').length")
            print("str.%d pravda %-3s → %-4s | čtení: %s | nabídka %s | tlačítek %s"
                  % (page, truth, ocr.get("digits"),
                     [(r["d"], r["c"]) for r in (ocr.get("reads") or [])],
                     ocr.get("choice"), ch))


asyncio.run(main())
