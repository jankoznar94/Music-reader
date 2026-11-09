#!/usr/bin/env python3
"""LUPA klepnutá PEREM (ne prstem). Jan (Nov 2026): „když klepnu prstem, funguje
to; když perem, tak ne — jistota 0, shluk 0“.

Pero posílá pointerType='pen'; sonda to ověří na stejném místě jako prst
(str. 2, vytištěná devítka, bod 67,1 / 515,2) a vypíše, co dorazilo do
pickPrintedBarNumber (souřadnice vrstvy, přepočet do PDF bodů, statistika).
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


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        await h.annot_toggle()
        await h.ev("""(() => { const b=[...document.querySelectorAll('.ap-tool')]
            .find(x=>(x.title||'').startsWith('Čísla taktů')); if(b) b.click(); return !!b; })()""")
        await h.wait_for("!!document.querySelector('.bn-pick')", timeout=8)
        await h.ev("document.querySelector('.bn-pick').click()")
        await h.ev("""(() => { const b=document.querySelector('.ap-collapse');
            if (b && b.title === 'Sbalit') { b.click(); return true; } return false; })()""")
        await asyncio.sleep(0.6)
        vb = [float(v) for v in (await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
        s = REF_W / 595.2
        pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
            const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
            return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + 67.1 * s, vb[1] + 515.2 * s)))
        print("cíl na obrazovce:", {k: round(v) for k, v in pt.items()})
        print("element v místě:", await h.ev(
            "(() => { const e=document.elementFromPoint(%f,%f); return e ? (e.className.baseVal!==undefined?e.className.baseVal:e.className) : 'none'; })()"
            % (pt["x"], pt["y"])))

        for kind in ("pen", "finger"):
            n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
            if kind == "pen":
                await h.pen_down(pt["x"], pt["y"])
                await asyncio.sleep(0.05)
                await h.pen_up(pt["x"], pt["y"])
            else:
                await h.finger_tap(pt["x"], pt["y"], r=11)
            await asyncio.sleep(3)
            dbg = json.loads(await h.ev(
                "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
            toast = await h.ev(
                "(document.querySelector('.viewer-toast')||{}).textContent || ''")
            print("---", kind, "| toast:", toast)
            print("   dbg:", json.dumps(dbg, ensure_ascii=False)[:700])


asyncio.run(main())
