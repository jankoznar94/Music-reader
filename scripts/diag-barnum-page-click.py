#!/usr/bin/env python3
"""DIAG: proč klik na .bn-page nezapne dočíslování stránky a proč nejde ťuknout
do vrstvy. Vypíše stav panelu, vrstvy a elementFromPoint v mřížce."""
import asyncio
import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.environ.get(
    "NOTY_PDF",
    "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
    "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
    "doc_1bb2c499f695_Mozart-Davide penitente.pdf")


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title||'').startsWith('Číslování')); if (b) b.click(); })()")
        await asyncio.sleep(0.7)
        print(await h.ev("""(() => { const p=document.querySelector('.barnum-panel');
            const lay=document.querySelector('.annot-layer');
            const r=lay?lay.getBoundingClientRect():null;
            return JSON.stringify({
              panel: !!p, pageBtn: !!document.querySelector('.bn-page'),
              layer: !!lay, pe: lay ? getComputedStyle(lay).pointerEvents : null,
              rect: r ? [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)] : null,
              armed: !!document.querySelector('.bn-page.on'),
              vw: innerWidth, vh: innerHeight }); })()"""))
        print(await h.ev("""(() => { const b=document.querySelector('.bn-page');
            if (!b) return 'no button';
            const r=b.getBoundingClientRect();
            const at=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2);
            b.click();
            return JSON.stringify({ rect:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],
              hitAt: at ? at.className : null }); })()"""))
        await asyncio.sleep(0.4)
        print("po kliku armed:", await h.ev("!!document.querySelector('.bn-page.on')"),
              "| toast:", await h.ev("window.__barDev ? window.__barDev.toast.value : '?'"))
        print(await h.ev("""(() => {
            const lay=document.querySelector('.annot-layer');
            const r=lay.getBoundingClientRect();
            const out=[];
            for (const fx of [0.3,0.5,0.7]) for (const fy of [0.4,0.6,0.9]) {
              const x=r.left+r.width*fx, y=r.top+r.height*fy;
              const el=document.elementFromPoint(x,y);
              out.push([Math.round(x),Math.round(y), el?el.className:'null']);
            }
            return JSON.stringify(out); })()"""))

asyncio.run(main())
