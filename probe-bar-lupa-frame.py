#!/usr/bin/env python3
"""LUPA se ZAPNUTÝM RÁMEM (ořez okrajů) — Jan: „s ořezem vůbec nenachází čísla“.

Souřadnice případů jsou v BODECH PDF; klepnutí se do vrstvy převádí měřítkem
CELÉ stránky (refW / šířka v bodech), ne cropBox.w — jinak test měří špatný bod.
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
PAGE_W = 595.2
REF_W = 760.0

CASES = [
    (2, 67.1, 515.2, 9),
    (2, 68.7, 249.6, 5),
    (6, 73.7, 43.8, 42),
    (6, 74.2, 345.2, 47),
    (6, 75.8, 662.9, 52),
    (8, 69.0, 46.8, 75),
    (8, 70.8, 271.2, 78),
]

TO_SCREEN = """(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=%f/%f; const g=svg.getScreenCTM();
  const p=new DOMPoint(%f*s, %f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y}); })()"""


async def enable_frame(h):
    await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('Vycentrovat a preference')); if (b) b.click(); return !!b; })()""")
    await asyncio.sleep(0.7)
    await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
        .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
    await asyncio.sleep(1.2)
    await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('Vycentrovat a preference')); if (b) b.click(); return !!b; })()""")
    await asyncio.sleep(0.5)


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


async def tap_case(h, page, px, py):
    await ensure_tool(h, page)
    vb = [float(v) for v in (await h.ev(
        "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
    pt = json.loads(await h.ev(TO_SCREEN % (REF_W, PAGE_W, px, py)))
    n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
    await h.finger_tap(pt["x"], pt["y"], r=10)
    t0 = time.time()
    while time.time() - t0 < 25:
        dbg = json.loads(await h.ev(
            "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
        if any(isinstance(d, dict) and "ocr" in d for d in dbg):
            break
        await asyncio.sleep(0.15)
    dbg = json.loads(await h.ev(
        "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
    ocr = next((d["ocr"] for d in dbg if isinstance(d, dict) and "ocr" in d), {})
    diag = await h.ev("(document.querySelector('.bn-diag')||{}).textContent||''")
    return {"vb": vb, "digits": ocr.get("digits"), "conf": ocr.get("confidence"),
            "cluster": ocr.get("cluster"), "pdf": ocr.get("pdf"),
            "stats": ocr.get("stats"), "diag": diag}


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await enable_frame(h)
        print("viewBox s rámem:", await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')"))
        ok = 0
        for page, px, py, truth in CASES:
            r = await tap_case(h, page, px, py)
            good = str(r["digits"]) == str(truth)
            ok += good
            print("str.%d pravda %-3s přečteno %-4s jistota %-3s shluk %s pdf %s %s"
                  % (page, truth, r["digits"], r["conf"], r["cluster"], r["pdf"],
                     "OK" if good else "CHYBA"))
            print("   ", (r["diag"] or "").strip()[:160])
        print("\nsouhrn s rámem: %d/%d" % (ok, len(CASES)))


asyncio.run(main())
