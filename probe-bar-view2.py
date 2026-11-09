#!/usr/bin/env python3
"""Lupa ve VŠECH zobrazeních: výchozí / zoom / ořez (rám) / rám+zoom.

Klíčové: referenční px vrstvy mají vždy šířku REF_W (760 pro stránku 595,2 b),
takže obrazový bod se počítá `vb[0] + px * REF_W / pageW` — NE z `vb[2]`
(s vb[2] se s rámem klepne mimo a vypadá to, že lupa nefunguje).
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

PAGE_W = 595.2
REF_W = 760.0
def to_screen(px, py):
    return ("""(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=%f/%f;
  const g=svg.getScreenCTM();
  const p=new DOMPoint(vb[0]+%f*s, vb[1]+%f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y,vb:vb}); })()""" % (REF_W, PAGE_W, px, py))


async def ensure_pick(h):
    """Panel čísel + lupa zapnutá (kliky na jiná tlačítka režim vypnou)."""
    if not await h.ev("!!document.querySelector('.bn-pick.on')"):
        if not await h.ev("!!document.querySelector('.barnum-panel')"):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
                .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.6)
        if not await h.ev("!!document.querySelector('.barnum-panel')"):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
                .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.6)
        await h.ev("(() => { const b=document.querySelector('.bn-pick'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.4)


async def vb(h):
    return await h.ev("document.querySelector('.annot-layer').getAttribute('viewBox')")


async def tap(h, px, py, label):
    await ensure_pick(h)
    v = await vb(h)
    pt = json.loads(await h.ev(to_screen(px, py)))
    n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
    await h.finger_tap(pt["x"], pt["y"], r=9)
    await asyncio.sleep(2.4)
    dbg = json.loads(await h.ev("JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
    rec = [d for d in dbg if d and d.get("ocr")]
    o = rec[-1]["ocr"] if rec else {}
    toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''")
    ok = "OK" if o.get("digits") == "9" else "CHYBA"
    print("%-10s vb=%-44s → pdf=%s shluk=%s číslice=%s jistota=%s | %s %s"
          % (label, (v or "")[:44], o.get("pdf"), o.get("cluster"), o.get("digits"),
             o.get("confidence"), ok, (toast or "").strip()[:45]))


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        X, Y = 67.1, 515.2     # vytištěná devítka (PDF body)
        await tap(h, X, Y, "výchozí")

        # zoom 3× nahoru (panel zoomu)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
        for _ in range(3):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
                .find(x => x.title === 'Přiblížit'); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.3)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
        await tap(h, X, Y, "zoom")

        # zpět na 100 %, pak rám (panel preferencí)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
            .find(x => x.title === 'Zpět na 100 % (fit na šířku)'); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.5)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.5)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Vycentrovat a preference')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.0)
        await tap(h, X, Y, "rám")

        # rám + zoom
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        for _ in range(2):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
                .find(x => x.title === 'Přiblížit'); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.3)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
        await tap(h, X, Y, "rám+zoom")


asyncio.run(main())
