#!/usr/bin/env python3
"""DOČÍSLOVÁNÍ SYSTÉMU: klepnutím do systému doplní čísla podle taktových čar.
Test na str. 4 (systém 24–27, tj. Krok = 3): po akci musí v DB přibýt 24, 25, 26
a počítadlo se posunout na 27.

Spouštěj: scripts/run-probe-fresh.sh probe-bar-fill.py
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


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(4)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); b.click(); return true; })()""")
        await h.wait_for("!!document.querySelector('.barnum-panel')", timeout=8, label="panel")
        print("panel:", await h.ev("(document.querySelector('.barnum-panel')||{}).innerText"))
        # počítadlo: první takt 24, krok (taktů v systému) 3
        await h.ev("""(() => {
            const ins = [...document.querySelectorAll('.bn-input')];
            if (ins.length < 2) return 'málo polí: ' + ins.length;
            ins[0].value = '24'; ins[0].dispatchEvent(new Event('change', {bubbles: true}));
            ins[1].value = '3';  ins[1].dispatchEvent(new Event('change', {bubbles: true}));
            return ins.map(i => i.value).join('/'); })()""")
        await asyncio.sleep(0.3)
        vb = [float(v) for v in (await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
        s = vb[2] / 595.2
        # klepnutí doprostřed druhého systému (čísla 24–26): pdf (300, 400)
        pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
            const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
            return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + 300 * s, vb[1] + 400 * s)))
        await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.4)
        print("armed:", await h.ev("!!document.querySelector('.bn-fill.on')"))
        await h.finger_tap(pt["x"], pt["y"], r=11)
        await asyncio.sleep(3)
        print("toast:", await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''"))
        dbg = json.loads(await h.ev("JSON.stringify((window.__barPickDbg||[]).filter(d=>d&&d.fill))"))
        print("detekce:", json.dumps(dbg, ensure_ascii=False)[:400])
        items = json.loads(await h.ev("""(async () => { const q=indexedDB.open('noty-app');
          const db=await new Promise(r=>{q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});
          const rows=await new Promise(r=>{const t=db.transaction('annotations','readonly')
            .objectStore('annotations').getAll(); t.onsuccess=()=>r(t.result||[]); t.onerror=()=>r([]);});
          db.close(); const o=[]; for(const row of rows) for(const it of (row.items||[]))
            if(it.barNum) o.push({text:it.text,page:it.page,x:it.x,y:it.y}); return JSON.stringify(o); })()""",
                             await_promise=True))
        print("barNum v DB:", items)
        print("Další v panelu:", await h.ev(
            "(() => { const i=document.querySelector('.bn-input'); return i ? i.value : '?'; })()"))


asyncio.run(main())
