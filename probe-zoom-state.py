#!/usr/bin/env python3
"""Rychlá diagnostika ovládání zoomu a rámu (aby sonda viewmodes neselhala naslepo)."""
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


async def snap(h, label):
    s = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
        const st=document.querySelector('.stage');
        return JSON.stringify({ vb: svg.getAttribute('viewBox'),
          stage: st ? getComputedStyle(st).transform : '',
          zoomTxt: (document.querySelector('.tb-btn.zoom-btn')||{}).textContent.trim(),
          zoomPanel: !!document.querySelector('.zoom-panel'),
          prefsPanel: !!document.querySelector('.prefs-panel'),
          zbtns: [...document.querySelectorAll('.zp-btn')].map(b=>b.title).slice(0,14) }); })()"""))
    print(label, json.dumps(s, ensure_ascii=False))
    return s


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        await snap(h, "start:")
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.8)
        await snap(h, "po otevření zoom panelu:")
        n = await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
            .find(x => x.title === 'Přiblížit'); if (!b) return 'není'; b.click(); b.click(); return 'kliknuto'; })()""")
        print("zoom klik:", n)
        await asyncio.sleep(0.8)
        await snap(h, "po zoomu:")
        f = await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (!b) return 'není'; b.click(); return 'kliknuto'; })()""")
        print("rám klik:", f)
        await asyncio.sleep(1.5)
        await snap(h, "po rámu:")


asyncio.run(main())
