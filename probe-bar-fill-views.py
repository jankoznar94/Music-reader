#!/usr/bin/env python3
"""DOČÍSLOVÁNÍ s RÁMEM a se ZOOMEM — režim, ve kterém to Janovi hlásilo 0 čar.

Příčina byla v `layerScale`: měřítko se počítalo z cropBox.w (šířka výřezu),
takže s rámem bylo 1,101 místo 1,277 a klepnutí se přepočetlo o desítky bodů
vedle → pás mimo systém → 0 čar. Tady se to ověřuje na dvou systémech.
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
PAGE_W = 595.2
REF_W = 760.0

PAGE_BARS = """(async () => { const q=indexedDB.open('noty-app');
  const db=await new Promise(r=>{q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});
  const rows=await new Promise(r=>{const t=db.transaction('annotations','readonly')
    .objectStore('annotations').getAll(); t.onsuccess=()=>r(t.result||[]); t.onerror=()=>r([]);});
  db.close(); const o=[]; for(const row of rows) for(const it of (row.items||[]))
    if(it.barNum && it.page===%d) o.push(Number(it.text)); return JSON.stringify(o); })()"""


def to_screen(px, py):
    return ("""(() => { const svg=document.querySelector('.annot-layer');
  const vb=(svg.getAttribute('viewBox')||'0 0 1 1').split(/\\s+/).map(Number);
  const s=%f/%f; const g=svg.getScreenCTM();
  const p=new DOMPoint(%f*s, %f*s).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y}); })()""" % (REF_W, PAGE_W, px, py))


async def open_panel(h):
    if not await h.ev("!!document.querySelector('.barnum-panel')"):
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        if not await h.ev("!!document.querySelector('.barnum-panel')"):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
                .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.6)


async def case(h, label, page, px, py, krok, first, expect):
    if await h.ev("document.querySelector('.tb-page') && document.querySelector('.tb-page').textContent.trim()") != "%d / 80" % page:
        await h.goto(page)
    await open_panel(h)
    await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
        if (ins.length < 2) return 'málo polí';
        ins[0].value='%d'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
        ins[1].value='%d'; ins[1].dispatchEvent(new Event('change',{bubbles:true}));
        return 'ok'; })()""" % (first, krok))
    await asyncio.sleep(0.3)
    before = json.loads(await h.ev(PAGE_BARS % (page - 1), await_promise=True))
    pt = json.loads(await h.ev(to_screen(px, py)))
    if not await h.ev("!!document.querySelector('.bn-fill.on')"):
        await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.3)
    n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
    await h.finger_tap(pt["x"], pt["y"], r=10)
    await asyncio.sleep(2.5)
    dbg = json.loads(await h.ev(
        "JSON.stringify((window.__barPickDbg||[]).slice(%d).filter(d=>d&&d.fill))" % n0))
    det = dbg[-1]["fill"] if dbg else {}
    after = json.loads(await h.ev(PAGE_BARS % (page - 1), await_promise=True))
    new = sorted(set(n for n in after if n not in before))
    good = new == sorted(expect)
    toast = await h.ev("(document.querySelector('.viewer-toast')||{}).textContent||''")
    print("%-12s str %d y %-4d Krok %d: čar %s, osnov %s, ok %s | nová %s | %s | %s"
          % (label, page, py, krok, det.get("lines"), det.get("staves"), det.get("ok"),
             new, "OK" if good else "CHYBA", (toast or "").strip()[:50]))
    return good


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    res = []
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        # 1) výchozí
        res.append(await case(h, "výchozí", 4, 300, 400, 3, 24, [24, 25, 26]))

        # 2) rám
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Vycentrovat a preference')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.7)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn.prefs-icon')]
            .find(x => (x.title||'').startsWith('Oříznout okraje')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(1.2)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Vycentrovat a preference')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.5)
        res.append(await case(h, "rám", 4, 300, 200, 3, 21, [21, 22, 23]))

        # 3) rám + zoom
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        for _ in range(2):
            await h.ev("""(() => { const b=[...document.querySelectorAll('.zp-btn')]
                .find(x => x.title === 'Přiblížit'); if (b) b.click(); return !!b; })()""")
            await asyncio.sleep(0.3)
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Zvětšení a posun')); if (b) b.click(); return !!b; })()""")
        await asyncio.sleep(0.6)
        res.append(await case(h, "rám+zoom", 2, 300, 355, 4, 9, [9, 10, 11, 12]))

    print("\nsouhrn: %d/%d" % (sum(1 for r in res if r), len(res)))


asyncio.run(main())
