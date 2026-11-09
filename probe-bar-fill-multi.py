#!/usr/bin/env python3
"""DOČÍSLOVÁNÍ na VÍC systémech: ověří, že detekce taktových čar sedí na Krok
a čísla se vloží na správné stránky napříč skenem (ne jen jeden systém).

Případy: (strana, x, y v bodech PDF, Krok, první takt, očekávaná čísla)
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

CASES = [
    (2, 300, 355, 4, 9,  [9, 10, 11, 12]),
    (4, 300, 200, 3, 21, [21, 22, 23]),
    (4, 300, 400, 3, 24, [24, 25, 26]),
    (8, 300, 180, 3, 75, [75, 76, 77]),
    (8, 300, 400, 3, 78, [78, 79, 80]),
]

PAGE_BARS = """(async () => { const q=indexedDB.open('noty-app');
  const db=await new Promise(r=>{q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});
  const rows=await new Promise(r=>{const t=db.transaction('annotations','readonly')
    .objectStore('annotations').getAll(); t.onsuccess=()=>r(t.result||[]); t.onerror=()=>r([]);});
  db.close(); const o=[]; for(const row of rows) for(const it of (row.items||[]))
    if(it.barNum && it.page===%d) o.push(Number(it.text)); return JSON.stringify(o); })()"""


async def run_case(h, page, px, py, krok, first, expect):
    if await h.ev("document.querySelector('.tb-page') && document.querySelector('.tb-page').textContent.trim()") != "%d / 80" % page:
        await h.goto(page)
    if not await h.ev("!!document.querySelector('.barnum-panel')"):
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        if not await h.ev("!!document.querySelector('.barnum-panel')"):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
                .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
            await h.wait_for("!!document.querySelector('.barnum-panel')", timeout=10, label="panel")
    await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
        ins[0].value='%d'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
        ins[1].value='%d'; ins[1].dispatchEvent(new Event('change',{bubbles:true}));
        return true; })()""" % (first, krok))
    await asyncio.sleep(0.3)
    before = json.loads(await h.ev(PAGE_BARS % (page - 1), await_promise=True))
    vb = [float(v) for v in (await h.ev(
        "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
    s = vb[2] / 595.2
    pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
        const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
        return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + px * s, vb[1] + py * s)))
    if not await h.ev("!!document.querySelector('.bn-fill.on')"):
        await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.3)
    n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
    await h.finger_tap(pt["x"], pt["y"], r=11)
    await asyncio.sleep(2.5)
    toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''")
    dbg = json.loads(await h.ev(
        "JSON.stringify((window.__barPickDbg||[]).slice(%d).filter(d=>d&&d.fill))" % n0))
    det = dbg[-1]["fill"] if dbg else {}
    after = json.loads(await h.ev(PAGE_BARS % (page - 1), await_promise=True))
    new_nums = [n for n in after if n not in before]
    nxt = await h.ev("(() => { const i=document.querySelector('.bn-input'); return i ? i.value : '?'; })()")
    good = sorted(set(new_nums)) == sorted(expect)
    print("str %-2d y %-4d Krok %d: čáry %s, top %s, ok %s | nová %s | čekáno %s | %s | další %s | %s"
          % (page, py, krok, det.get("lines"), round(det.get("top", 0), 1), det.get("ok"),
             sorted(set(new_nums)), expect, "OK" if good else "CHYBA", nxt,
             (toast or "").strip()[:70]))
    return good


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    results = []
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        for (page, px, py, krok, first, expect) in CASES:
            results.append(await run_case(h, page, px, py, krok, first, expect))
    print("\nsouhrn: %d/%d" % (sum(1 for r in results if r), len(results)))


asyncio.run(main())
