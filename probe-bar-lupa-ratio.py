#!/usr/bin/env python3
"""RÁM + ZÁLOŽNÍ CESTA PŘEPOČTU — reprodukce Janova nálezu ze str. 16.

Jan (řádek z panelu): klepnutí na číslo 11 skončilo na `pdf 14,487`, jistota 0,
shluk 0, komp 3, ink 9,7 %, max 70 b. Podle měření PDF jsou vytištěná čísla na
str. 16 na `x ≈ 67–77`, trojka systému na `y ≈ 525` → rozdíl je přesně cropBox
(odečetl se dvakrát, protože `toLayerCoords()` v záložní cestě vracela souřadnice
RELATIVNÍ k výřezu).

Sonda proto: 1) s rámem normálně (CTM), 2) s rámem a `getScreenCTM()` vynuceně
vracející null (= záložní cesta). Obě musí přečíst 11.
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

# (strana 1-based, pdf x, pdf y, správné číslo) — str. 16 třetí systém = 11
CASES = [(16, 72.6, 528.0, 11)]
PAGE_W = 595.2

TO_SCREEN = """(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=%f/595.2;
  const fn = window.__ctm0 || SVGSVGElement.prototype.getScreenCTM;
  const g = fn.call(svg);
  const p=new DOMPoint(%f + %f*s, %f + %f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y}); })()"""


async def click_tb(h, title):
    return await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('%s')); if (b) b.click(); return !!b; })()""" % title)


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


async def tap(h, REF_W, page, px, py):
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
    diag = await h.ev("(document.querySelector('.bn-diag')||{}).textContent||''")
    return ocr, diag.strip()


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2.625)
        await h.open_song(pdf=PDF)
        REF_W = float((await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()[2])
        # rám
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.5)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.4)
        print("viewBox s rámem:", await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')"))
        ok = 0
        for mode in ("ctm", "ratio"):
            if mode == "ratio":
                # vynutit záložní cestu v toLayerCoords()
                await h.ev("""(() => { window.__ctm0 = SVGSVGElement.prototype.getScreenCTM;
                    SVGSVGElement.prototype.getScreenCTM = function(){ return null; };
                    return true; })()""")
            for page, px, py, truth in CASES:
                await ensure_lupa(h, page)
                ocr, diag = await tap(h, REF_W, page, px, py)
                good = str(ocr.get("digits")) == str(truth)
                ok += good
                print("%-6s str.%d pravda %-3s přečteno %-4s jistota %-3s pdf %s | %s"
                      % (mode, page, truth, ocr.get("digits"), ocr.get("confidence"),
                         ocr.get("pdf"), "OK" if good else "CHYBA"))
                print("       ", diag[:150])
        await h.ev("(() => { SVGSVGElement.prototype.getScreenCTM = window.__ctm0; return true; })()")
        print("\nsouhrn: %d/%d" % (ok, 2 * len(CASES)))


asyncio.run(main())
