#!/usr/bin/env python3
"""Screenshot po Dočíslování: čísla musí sedět NAD horní linkou systému,
na začátku každého taktu — ne o pár bodů vedle ani nad jiným systémem."""
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
        await h.goto(4)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); b.click(); return true; })()""")
        await asyncio.sleep(0.8)
        await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
            ins[0].value='24'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
            ins[1].value='3';  ins[1].dispatchEvent(new Event('change',{bubbles:true}));
            return true; })()""")
        vb = [float(v) for v in (await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
        s = REF_W / 595.2
        pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
            const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
            return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + 300 * s, vb[1] + 400 * s)))
        await h.ev("(() => { const b=document.querySelector('.bn-fill'); b.click(); return true; })()")
        await asyncio.sleep(0.3)
        await h.finger_tap(pt["x"], pt["y"], r=11)
        await asyncio.sleep(2.0)
        # POZOR: skrytá čísla se kreslí jen v režimu číslování — panel nechat otevřený
        res = await h.cdp("Page.captureScreenshot", {"format": "png"})
        import base64
        with open("/tmp/lupa/fill-shot.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))
        print("screenshot: /tmp/lupa/fill-shot.png")
        print("čísla:", await h.ev("""(() => JSON.stringify([...document.querySelectorAll('.annot-layer text')]
            .filter(t => (t.textContent||'').match(/^\\d+$/))
            .map(t => ({t: t.textContent, x: t.getAttribute('x'), y: t.getAttribute('y')}))))()"""))


asyncio.run(main())
