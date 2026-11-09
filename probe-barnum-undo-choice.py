#!/usr/bin/env python3
"""Panel čísel: ZPĚT (undo) a VOLBA ze dvou čísel.

Ověřuje:
1) tlačítko .bn-undo odebere poslední vložené číslo a vrátí počítadlo,
2) při nejednoznačném čtení se v panelu objeví tlačítka s OBĚMA čísly a
   klepnutí na jedno z nich vloží index s tímto číslem.
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

BARS = """(async () => { const q=indexedDB.open('noty-app');
  const db=await new Promise(r=>{q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});
  const rows=await new Promise(r=>{const t=db.transaction('annotations','readonly')
    .objectStore('annotations').getAll(); t.onsuccess=()=>r(t.result||[]); t.onerror=()=>r([]);});
  db.close(); const o=[]; for(const row of rows) for(const it of (row.items||[]))
    if(it.barNum) o.push({t:String(it.text), h:!!it.hidden, p:it.page}); return JSON.stringify(o); })()"""

# najdi komponentu Prohlizec a její setupState (dev build ji vystavuje)
FIND_STATE = """(() => { const app=document.querySelector('#app').__vue_app__;
  if(!app) return 'no app';
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


async def open_panel(h):
    if not await h.ev("!!document.querySelector('.barnum-panel')"):
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    res = []
    async with h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.open_song(pdf=PDF)
        await open_panel(h)
        await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
            ins[0].value='7'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
            ins[1].value='1'; ins[1].dispatchEvent(new Event('change',{bubbles:true}));
            return true; })()""")
        await asyncio.sleep(0.3)
        before = json.loads(await h.ev(BARS, await_promise=True))
        # 1) jedno číslo dovnitř prstu (mimo panel)
        await h.finger_tap(600, 700, r=10)
        await asyncio.sleep(1.2)
        mid = json.loads(await h.ev(BARS, await_promise=True))
        added = [b for b in mid if b not in before]
        print("po ťuknutí: přibylo %s, Další = %s"
              % ([b["t"] for b in added],
                 await h.ev("document.querySelectorAll('.bn-input')[0].value")))
        res.append(("vložení", len(added) == 1))

        # 2) ZPĚT
        has_undo = await h.ev("!!document.querySelector('.bn-undo')")
        dis = await h.ev("!!(document.querySelector('.bn-undo')||{}).disabled")
        await h.ev("(() => { const b=document.querySelector('.bn-undo'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.8)
        after = json.loads(await h.ev(BARS, await_promise=True))
        back = [b for b in after if b not in before]
        nxt = await h.ev("document.querySelectorAll('.bn-input')[0].value")
        toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''")
        print("zpět: tlačítko %s, disabled před klikem %s, zbylo %s, Další = %s | %s"
              % (has_undo, dis, [b["t"] for b in back], nxt, toast.strip()[:60]))
        res.append(("undo", has_undo and not back and str(nxt) == "7"))

        # 3) volba ze dvou čísel — nastavíme stav přímo (dev build)
        st = await h.ev(FIND_STATE)
        print("stav komponenty:", st)
        if st == "found":
            await h.ev("""(() => { const s=window.__pz;
                s.barPickChoice = { nums:['15','153'], page:0, x:600, y:700 };
                return true; })()""")
            await asyncio.sleep(0.4)
            btns = json.loads(await h.ev("""JSON.stringify([...document.querySelectorAll('.bn-choice-btn')]
                .map(b => b.textContent.trim()))"""))
            print("tlačítka nabídky:", btns)
            # klepni na DRUHÉ (153) skutečným dotykem
            pt = json.loads(await h.ev("""(() => { const b=[...document.querySelectorAll('.bn-choice-btn')]
                [1]; if(!b) return 'null'; const r=b.getBoundingClientRect();
                return JSON.stringify({x:r.left+r.width/2, y:r.top+r.height/2}); })()"""))
            await h.finger_tap(pt["x"], pt["y"], r=10)
            await asyncio.sleep(1.0)
            fin = json.loads(await h.ev(BARS, await_promise=True))
            newb = [b for b in fin if b not in before]
            left = await h.ev("document.querySelectorAll('.bn-choice-btn').length")
            print("po výběru 153: nové indexy %s, tlačítek zbylo %s"
                  % ([b["t"] for b in newb], left))
            res.append(("volba", btns == ["15", "153"]
                        and any(b["t"] == "153" and b["h"] for b in newb) and left == 0))
        else:
            res.append(("volba", False))

    print("\nsouhrn: %d/%d" % (sum(1 for _, ok in res if ok), len(res)))


asyncio.run(main())
