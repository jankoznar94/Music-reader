#!/usr/bin/env python3
"""LUPA s RÁMEM + ZOOMEM na tabletu — Jan: „s ořezem vůbec nenachází čísla“."""
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
CASES = [(2, 67.1, 515.2, 9), (6, 74.2, 345.2, 47), (6, 75.8, 662.9, 52),
         (8, 70.8, 271.2, 78)]

TO_SCREEN = """(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=%f/595.2; const g=svg.getScreenCTM();
  const p=new DOMPoint(%f*s, %f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y}); })()"""


async def click_tb(h, title):
    return await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('%s')); if (b) b.click(); return !!b; })()""" % title)


async def ensure_tool(h, page):
    if await h.ev("document.querySelector('.tb-page') && document.querySelector('.tb-page').textContent.trim()") != "%d / 80" % page:
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


async def run(h, REF_W, label, zoom_clicks, enable_frame=True):
    # rám
    if enable_frame:
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.4)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.4)
    if zoom_clicks:
        await click_tb(h, 'Zvětšení a posun')
        await asyncio.sleep(0.6)
        for _ in range(zoom_clicks):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
                .find(x => x.title === 'Přiblížit'); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.35)
        await click_tb(h, 'Zvětšení a posun')
        await asyncio.sleep(0.5)
    ok = 0
    for page, px, py, truth in CASES:
        await ensure_tool(h, page)
        vb = [float(v) for v in (await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
        pt = json.loads(await h.ev(TO_SCREEN % (REF_W, px, py)))
        hit = await h.ev("""(() => { const el=document.elementFromPoint(%f,%f);
            return el ? String(el.className && el.className.baseVal !== undefined ?
            el.className.baseVal : el.className) : 'null'; })()""" % (pt["x"], pt["y"]))
        n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
        await h.finger_tap(pt["x"], pt["y"], r=10)
        t0 = 0
        while t0 < 25:
            dbg = json.loads(await h.ev(
                "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
            if any(isinstance(d, dict) and "ocr" in d for d in dbg):
                break
            await asyncio.sleep(0.2)
            t0 += 1
        dbg = json.loads(await h.ev(
            "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
        ocr = next((d["ocr"] for d in dbg if isinstance(d, dict) and "ocr" in d), {})
        good = str(ocr.get("digits")) == str(truth)
        ok += good
        print("  %-10s str.%d pravda %-3s přečteno %-4s jistota %-3s pdf %s pod %s %s"
              % (label, page, truth, ocr.get("digits"), ocr.get("confidence"),
                 ocr.get("pdf"), hit, "OK" if good else "CHYBA"))
    return ok


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2.625)
        await h.open_song(pdf=PDF)
        REF_W = float((await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()[2])
        print("refW:", REF_W)
        a = await run(h, REF_W, "rám", 0)
        b = await run(h, REF_W, "rám+zoom2", 2, enable_frame=False)
        print("\nsouhrn: rám %d/4, rám+zoom %d/4" % (a, b))


asyncio.run(main())
