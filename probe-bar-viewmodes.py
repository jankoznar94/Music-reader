#!/usr/bin/env python3
"""LUPA + DOČÍSLOVÁNÍ ve VŠECH zobrazeních: default, zoom, ořez (rám).

Jan (Nov 2026): „lupa funguje jen bez zoomu/ořezu; jakmile to není ve výchozí
podobě, nefunguje“ a „Dočíslování: nalezeno 0 čar, pokaždé“.

Sonda klepne na totéž vytištěné číslo (str. 2, bod 67,1 / 515,2 = devítka)
v různých režimech a vypíše, co si appka myslí, že uživatel zmáčkl:
`pdf` = přepočet klepnutí do bodů PDF, `shluk` = kolik shluků číslic našla.
Když se `pdf` rozjede od 67,1 / 515,2, je chyba v souřadnicích, ne v OCR.
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

TO_SCREEN = """(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=vb[2]/595.2;
  const g=svg.getScreenCTM();
  const p=new DOMPoint(%f*s, %f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y,vb:vb,s:s}); })()"""


async def state(h):
    return json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
        const st=document.querySelector('.stage');
        const cs=st ? getComputedStyle(st) : null;
        return JSON.stringify({ vb: (svg.getAttribute('viewBox')||''),
          stage: cs ? cs.transform : '', stageW: st ? st.style.width : '',
          zoomBtn: (document.querySelector('.tb-btn.zoom-btn')||{}).textContent }); })()"""))


async def tap(h, px, py, label):
    before = await state(h)
    pt = json.loads(await h.ev(TO_SCREEN % (px, py)))
    n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
    await h.finger_tap(pt["x"], pt["y"], r=9)
    await asyncio.sleep(2.2)
    dbg = json.loads(await h.ev(
        "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
    rec = [d for d in dbg if d and d.get("ocr")]
    o = rec[-1]["ocr"] if rec else {}
    toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''")
    print("%-22s vb=%-22s obraz=(%4.0f,%4.0f) → pdf=%s shluk=%s jistota=%s | %s"
          % (label, before["vb"], pt["x"], pt["y"], o.get("pdf"), o.get("cluster"),
             o.get("confidence"), (toast or "").strip()[:60]))
    return o, pt


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); b.click(); return true; })()""")
        await asyncio.sleep(0.8)
        if not await h.ev("!!document.querySelector('.bn-pick.on')"):
            await h.ev("(() => { const b=document.querySelector('.bn-pick'); if(b) b.click(); return !!b; })()")
            await asyncio.sleep(0.4)

        X, Y = 67.1, 515.2     # vytištěná devítka na str. 2 (PDF body)
        await tap(h, X, Y, "1) výchozí")

        # zoom 200 %
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if(b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        for _ in range(3):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
                .find(x => x.title === 'Přiblížit'); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.35)
        await asyncio.sleep(0.6)
        # po zoomu nemusí být cíl na obrazovce — centrujeme, ať je vidět
        await h.ev("""(() => { const v=document.querySelector('.viewer'); if (v) v.scrollTo(0, v.scrollHeight*0.55); return true; })()""")
        await asyncio.sleep(0.5)
        await tap(h, X, Y, "2) zoom 200 %")

        # zpět na 100 % a rám (rám je v panelu preferencí, ne v zoomu)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
            .find(x => x.title === 'Zpět na 100 % (fit na šířku)'); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Vycentrovat a preference')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
        print("  rám tlačítko:", await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (!b) return 'není'; b.click(); return 'kliknuto'; })()"""))
        await asyncio.sleep(1.0)
        await tap(h, X, Y, "3) ořez (rám)")

        # rám + zoom
        for _ in range(2):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
                .find(x => x.title === 'Přiblížit'); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.35)
        await asyncio.sleep(0.5)
        await tap(h, X, Y, "4) rám + zoom")

        # DOČÍSLOVÁNÍ v režimu, který má Jan: čísla 9–12 na str. 2
        print("\n--- Dočíslování (str. 2, Krok 4, další 9) ---")
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
            .find(x => x.title === 'Zpět na 100 % (fit na šířku)'); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.5)
        print("stav:", json.dumps(await state(h), ensure_ascii=False))
        await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
            ins[0].value='9'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
            ins[1].value='4'; ins[1].dispatchEvent(new Event('change',{bubbles:true}));
            return true; })()""")
        if not await h.ev("!!document.querySelector('.bn-fill.on')"):
            await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.3)
        before = await state(h)
        pt = json.loads(await h.ev(TO_SCREEN % (300, 355)))
        n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
        await h.finger_tap(pt["x"], pt["y"], r=10)
        await asyncio.sleep(3)
        dbg = json.loads(await h.ev(
            "JSON.stringify((window.__barPickDbg||[]).slice(%d).filter(d=>d&&d.fill))" % n0))
        print("vb:", before["vb"], "| fill:", json.dumps(dbg[-1]["fill"], ensure_ascii=False) if dbg else "—")
        print("toast:", await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''"))


asyncio.run(main())
