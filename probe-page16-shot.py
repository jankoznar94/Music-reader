#!/usr/bin/env python3
"""Screenshot str. 16 s rámem + vyznačené body, kde si appka myslí, že je číslo 11.

Kreslí do screenshotu dva křížky:
  A) x ze SVG přepočtu (p − cropBox)/s … tam, kde lupa hledá dnes
  B) x z „plátnového“ přepočtu (cropPt + podíl šířky bitmapy)
Porovnáním se skutečnou polohou vytištěné 11 poznáme, který je správně.
"""
import asyncio
import base64
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


async def click_tb(h, title):
    return await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('%s')); if (b) b.click(); return !!b; })()""" % title)


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(pdf=PDF)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.5)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.4)
        await h.goto(16)
        await asyncio.sleep(1.2)
        # schovej panely a lišty, ať je vidět jen stránka
        await h.ev("(() => { document.querySelectorAll('.barnum-panel,.annot-panel').forEach(e=>e.style.display='none'); return true; })()")
        info = json.loads(await h.ev("""JSON.stringify((() => {
            const cv=document.querySelector('canvas.pdf-canvas');
            const r=cv.getBoundingClientRect();
            const svg=document.querySelector('.annot-layer');
            const g=svg.getScreenCTM();
            const p=(x,y)=>{ const q=new DOMPoint(x,y).matrixTransform(g); return [q.x,q.y]; };
            return { rect:[r.left,r.top,r.width,r.height],
                     vb: svg.getAttribute('viewBox'),
                     y528: p(0, 0) }; })())"""))
        print("canvas rect:", info["rect"], "viewBox:", info["vb"])
        # souřadnice na obrazovce pro pdf y=528: vezmeme z CTM (stejné pro obě cesty v y)
        ys = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
            const g=svg.getScreenCTM(); const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
            const s=760/595.2; const q=new DOMPoint(vb[0]+72.6*s, vb[1]+528*s).matrixTransform(g);
            return JSON.stringify({x:q.x,y:q.y}); })()"""))
        clip = {"x": 0, "y": max(0, ys["y"] - 90), "width": 420, "height": 150, "scale": 3}
        shot = await h.cdp("Page.captureScreenshot", {"format": "png", "clip": clip})
        with open("/tmp/page16-crop-11.png", "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("screenshot:", "/tmp/page16-crop-11.png", "clip:", clip)
        print("bod ze SVG přepočtu (kde lupa hledá):", ys)
        print("levý okraj plátna:", info["rect"][0])


asyncio.run(main())
