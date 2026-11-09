#!/usr/bin/env python3
"""Uloží VYKRESLENÉ plátno (str. 16, rám) pro offline srovnání s PDF."""
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
        await h.set_tablet(800, 1280, 1)
        await h.open_song(pdf=PDF)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.5)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.4)
        await h.goto(16)
        await asyncio.sleep(1.5)
        info = json.loads(await h.ev("""(() => {
            const app=document.querySelector('#app').__vue_app__;
            const seen=new Set(); const q=[app._instance]; let st=null;
            while(q.length){ const c=q.shift(); if(!c||seen.has(c)) continue; seen.add(c);
              if(c.setupState && 'barPickChoice' in c.setupState){ st=c.setupState; break; }
              if(c.subTree){ const ss=[c.subTree]; while(ss.length){ const v=ss.pop();
                if(!v) continue; if(v.component) q.push(v.component);
                if(v.children){ if(Array.isArray(v.children)) ss.push(...v.children);
                  else if(typeof v.children==='object') ss.push(v.children); } } } }
            const cv=document.querySelector('canvas.pdf-canvas');
            return JSON.stringify({ url: cv.toDataURL('image/png'), w: cv.width, h: cv.height,
                     cssW: cv.getBoundingClientRect().width,
                     pr: st && st._pageRender, cb: st && st.cropBox }); })()"""))
        data = info["url"].split(",", 1)[1]
        with open("/tmp/canvas-crop.png", "wb") as f:
            f.write(base64.b64decode(data))
        print("canvas:", info["w"], "x", info["h"], "cssW", info["cssW"])
        print("_pageRender:", json.dumps(info["pr"]))
        print("cropBox:", json.dumps(info["cb"]))
        print("saved: /tmp/canvas-crop.png")


asyncio.run(main())
