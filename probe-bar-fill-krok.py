#!/usr/bin/env python3
"""Citlivost dočíslování na KROK: co udělá, když uživatel zadá jiný počet
taktů, než systém skutečně má (Jan: „dočíslování nefunguje“).

Pro každý případ zkusí Krok = správně, +1, −1 a vypíše, co appka udělá:
kolik čar našla, zda vložila čísla a jaká.
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
# (strana, pdf x, pdf y, skutečný počet taktů)
CASES = [(2, 300, 355, 4), (4, 300, 400, 3), (8, 300, 400, 3)]

PAGE_BARS = """(async () => { const q=indexedDB.open('noty-app');
  const db=await new Promise(r=>{q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});
  const rows=await new Promise(r=>{const t=db.transaction('annotations','readonly')
    .objectStore('annotations').getAll(); t.onsuccess=()=>r(t.result||[]); t.onerror=()=>r([]);});
  db.close(); const o=[]; for(const row of rows) for(const it of (row.items||[]))
    if(it.barNum && it.page===%d) o.push(Number(it.text)); return JSON.stringify(o.sort((a,b)=>a-b)); })()"""


async def one(h, page, px, py, krok, first):
    # Panel se po vložení zavírá / překresluje — otevřít a ověřit PŘED každým pokusem.
    if not await h.ev("!!document.querySelector('.barnum-panel')"):
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
    await h.wait_for("document.querySelectorAll('.bn-input').length >= 2",
                     timeout=8, label="bn-input")
    await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
        ins[0].value='%d'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
        ins[1].value='%d'; ins[1].dispatchEvent(new Event('change',{bubbles:true}));
        return 1; })()""" % (first, krok))
    await asyncio.sleep(0.3)
    vb = [float(v) for v in (await h.ev(
        "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
    s = REF_W / 595.2
    pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
        const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
        return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + px * s, vb[1] + py * s)))
    await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
    await asyncio.sleep(0.3)
    await h.finger_tap(pt["x"], pt["y"], r=11)
    await asyncio.sleep(2.5)
    toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''")
    dbg = json.loads(await h.ev("JSON.stringify((window.__barPickDbg||[]).filter(d=>d&&d.fill).slice(-1))"))
    got = await h.ev(PAGE_BARS % page)
    if isinstance(got, str):
        got = json.loads(got)
    got = got or []
    d = (dbg[0]["fill"] if dbg else {})
    return dict(toast=toast.strip(), bars=d.get("bars"), ok=d.get("ok"),
                lines=d.get("lines"), inDB=got)


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for (page, px, py, real) in CASES:
            await h.goto(page)
            for krok in (real, real + 1, real - 1):
                r = await one(h, page, px, py, krok, 1)
                print("str %d  Krok %d (skutečnost %d): ok=%s bars=%s vDB=%s | %s"
                      % (page, krok, real, r["ok"], r["bars"], r["inDB"], r["toast"][:110]))
            print()


asyncio.run(main())
