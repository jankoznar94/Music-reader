#!/usr/bin/env python3
"""Přesná reprodukce Janova klepnutí: p (106,735) na str. 16 s rámem.

Volá interní `pickPrintedBarNumber` s POSUNUTÝM p (jak ho Janovi vrátila
`toLayerCoords`) a správnou obrazovkovou polohou. Lupa se to musí sama poznat
podle obrazu (kandidát „plátno“) a přečíst 11.
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

FIND_STATE = """(() => { const app=document.querySelector('#app').__vue_app__;
  const seen=new Set(); const q=[app._instance];
  while(q.length){ const c=q.shift(); if(!c||seen.has(c)) continue; seen.add(c);
    const s=c.setupState;
    if(s && 'barPickChoice' in s) { window.__pz = s; return typeof s.pickPrintedBarNumber; }
    if(c.subTree) { const st=[c.subTree]; while(st.length){ const v=st.pop();
      if(!v) continue; if(v.component) q.push(v.component);
      if(v.children) { if(Array.isArray(v.children)) st.push(...v.children);
        else if(typeof v.children==='object') st.push(v.children); } } }
  }
  return 'not found'; })()"""

TO_SCREEN = """(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=%f/595.2; const g=svg.getScreenCTM();
  const p=new DOMPoint(%f*s, %f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y}); })()"""


async def click_tb(h, title):
    return await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
        .find(x => (x.title||'').startsWith('%s')); if (b) b.click(); return !!b; })()""" % title)


async def lupa_on(h):
    if not await h.ev("!!document.querySelector('.annot-panel')"):
        await h.annot_toggle()
    await h.ev("""(() => { const b=[...document.querySelectorAll('.ap-tool')]
        .find(x=>(x.title||'').startsWith('Čísla taktů')); if(b) b.click(); return !!b; })()""")
    await h.wait_for("!!document.querySelector('.bn-pick')", timeout=8, label="barnum panel")
    if not await h.ev("!!document.querySelector('.bn-pick.on')"):
        await h.ev("(() => { const b=document.querySelector('.bn-pick'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.3)


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2.625)
        await h.open_song(pdf=PDF)
        REF_W = float((await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()[2])
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.5)
        await click_tb(h, 'Vycentrovat a preference')
        await asyncio.sleep(0.4)
        await h.goto(16)
        await asyncio.sleep(1.0)
        await lupa_on(h)
        print("setupState.pickPrintedBarNumber:", await h.ev(FIND_STATE))
        vb = [float(v) for v in (await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
        # správná obrazovková poloha čísla 11 (pdf 72.6 / 528)
        pt = json.loads(await h.ev(TO_SCREEN % (REF_W, vb[0], 72.6, vb[1], 528.0)))
        print("správná obrazovka čísla 11:", pt)
        info = json.loads(await h.ev("""JSON.stringify((() => {
            const s=window.__pz, cv=document.querySelector('canvas.pdf-canvas');
            const r=cv.getBoundingClientRect();
            const svg=document.querySelector('.annot-layer');
            const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
            return { rect:[r.left,r.top,r.width,r.height], vb, cb: s.cropBox ? s.cropBox.value : s.cropBox,
                     pr: s._pageRender, cssW: s.cssW, cssH: s.cssH, rot: s.rot,
                     layerScale: s.layerScale }; })())"""))
        print("geometrie:", json.dumps(info, ensure_ascii=False)[:600])
        n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
        # Janovo posunuté p (106,735) + správná obrazovka
        await h.ev("""(() => { const s=window.__pz;
            s.pickPrintedBarNumber({x:106, y:735}, 'touch',
              {clientX:%f, clientY:%f});
            return true; })()""" % (pt["x"], pt["y"]))
        await asyncio.sleep(4.0)
        dbg = json.loads(await h.ev(
            "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
        ocr = next((d["ocr"] for d in dbg if isinstance(d, dict) and "ocr" in d), {})
        cand = next((d["mapCandidates"] for d in dbg if isinstance(d, dict) and "mapCandidates" in d), None)
        diag = await h.ev("(document.querySelector('.bn-diag')||{}).textContent||''")
        print("kandidáti přepočtu:", cand)
        print("přečteno:", ocr.get("digits"), "jistota", ocr.get("confidence"),
              "| map:", ocr.get("map"), "| pdf:", ocr.get("pdf"))
        print("diag:", diag.strip()[:170])
        print("\nVÝSLEDEK:", "OK" if str(ocr.get("digits")) == "11" else "CHYBA")


asyncio.run(main())
