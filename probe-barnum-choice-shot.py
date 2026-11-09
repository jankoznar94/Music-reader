#!/usr/bin/env python3
"""Screenshot panelu s NABÍDKOU dvou čísel (15 / 153) pro vizuální kontrolu."""
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

FIND_STATE = """(() => { const app=document.querySelector('#app').__vue_app__;
  const seen=new Set(); const q=[app._instance];
  while(q.length){ const c=q.shift(); if(!c||seen.has(c)) continue; seen.add(c);
    const s=c.setupState;
    if(s && 'barPickChoice' in s) { window.__pz = s; return 'found'; }
    if(c.subTree) { const st=[c.subTree]; while(st.length){ const v=st.pop();
      if(!v) continue; if(v.component) q.push(v.component);
      if(v.children) { if(Array.isArray(v.children)) st.push(...v.children);
        else if(typeof v.children==='object') st.push(v.children); } } }
  }
  return 'not found'; })()"""


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(pdf=PDF)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.9)
        print(await h.ev(FIND_STATE))
        await h.ev("""(() => { window.__pz.barPickChoice =
            { nums:['15','153'], page:0, x:600, y:700 }; return true; })()""")
        await asyncio.sleep(0.5)
        r = json.loads(await h.ev("""JSON.stringify((() => { const p=document.querySelector('.barnum-panel');
            const b=p.getBoundingClientRect(); return {x:b.x,y:b.y,width:b.width,height:b.height}; })())"""))
        shot = await h.cdp("Page.captureScreenshot", {"format": "png",
                          "clip": {**r, "scale": 2}})
        with open("/tmp/barnum-choice.png", "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("screenshot: /tmp/barnum-choice.png")


asyncio.run(main())
