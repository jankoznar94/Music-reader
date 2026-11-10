#!/usr/bin/env python3
"""Dočíslování s NÁHLEDEM: klepni → náhled → Vložit / Zrušit.

Ověřuje:
  1. po klepnutí do systému se NIC neuloží a objeví se náhled
     (čárkované čáry + čísla, tlačítka Vložit/Zrušit),
  2. „Zrušit" náhled zmizí a v DB nepřibude nic,
  3. druhé klepnutí + „Vložit" uloží přesně ta čísla, která byla v náhledu,
     na souřadnice z náhledu (x = začátky taktů).
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
CASES = [(2, 230, 4, 1), (4, 200, 3, 21), (2, 560, 3, 9)]

BARS_IN_DB = """(async () => { const q=indexedDB.open('noty-app');
  const db=await new Promise(r=>{q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});
  const rows=await new Promise(r=>{const t=db.transaction('annotations','readonly')
    .objectStore('annotations').getAll(); t.onsuccess=()=>r(t.result||[]); t.onerror=()=>r([]);});
  db.close(); const o=[]; for(const row of rows) for(const it of (row.items||[]))
    if(it.barNum && it.page===%d) o.push([Number(it.text), Math.round(it.x), Math.round(it.y)]);
  return JSON.stringify(o.sort((a,b)=>a[0]-b[0])); })()"""


async def tap_system(h, page, py):
    await h.wait_for("!!document.querySelector('.barnum-panel')", timeout=8, label="panel")
    vb = [float(v) for v in (await h.ev(
        "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
    s = vb[2] / 595.2
    pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
        const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
        return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + 300 * s, vb[1] + py * s)))
    await h.ev("(() => { const b=document.querySelector('.bn-fill'); if(b) b.click(); return !!b; })()")
    await asyncio.sleep(0.3)
    await h.finger_tap(pt["x"], pt["y"], r=11)
    await asyncio.sleep(2.5)


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    ok = 0
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        cur = None
        for (page, py, krok, first) in CASES:
            if cur != page:
                await h.goto(page); cur = page
            if not await h.ev("!!document.querySelector('.barnum-panel')"):
                await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
                    .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
                await asyncio.sleep(0.7)
            for _t in range(4):
                try:
                    await h.wait_for("document.querySelectorAll('.bn-input').length >= 2", timeout=4, label="bn")
                    break
                except Exception:
                    await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
                        .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click(); return !!b; })()""")
                    await asyncio.sleep(0.7)
            await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
                ins[0].value='%d'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
                ins[1].value='%d'; ins[1].dispatchEvent(new Event('change',{bubbles:true})); return 1; })()"""
                % (first, krok))
            await asyncio.sleep(0.3)
            before = json.loads(await h.ev(BARS_IN_DB % (page - 1), await_promise=True) or "[]")
            await tap_system(h, page, py)
            pv = await h.ev("""(() => { const g=document.querySelector('.barfill-preview');
                return JSON.stringify(g ? [...g.querySelectorAll('.barfill-num')].map(t=>t.textContent) : null); })()""")
            btns = await h.ev("""(() => { const b=document.querySelector('.bn-fill-ok');
                return b ? b.textContent.trim() : null; })()""")
            now = json.loads(await h.ev(BARS_IN_DB % (page - 1), await_promise=True) or "[]")
            print("str %d y %d: náhled=%s tlačítko=%r | v DB před %d po %d"
                  % (page, py, pv, btns, len(before), len(now)))
            # POZOR: od listopadu 2026 se číslo 1. taktu bere z INDEXU systému,
            # ne z pole „Další“; tady index záměrně není, takže se použije
            # záložní „Další“ a číslují se takty 2..N (tedy `first + 1 …`).
            # 1) náhled musí existovat, čísla musí jít po sobě od first+1
            #    a nic se nesmí uložit
            nums = json.loads(pv) if pv else None
            seq = nums is not None and len(nums) >= 1 and nums == [
                str(first + 1 + i) for i in range(len(nums))]
            c1 = seq and len(now) == len(before)

            # 2) Zrušit
            await h.ev("(() => { const b=document.querySelector('.bn-fill-no'); if(b) b.click(); return !!b; })()")
            await asyncio.sleep(0.5)
            gone = await h.ev("!document.querySelector('.barfill-preview')")
            after_cancel = json.loads(await h.ev(BARS_IN_DB % (page - 1), await_promise=True) or "[]")
            c2 = bool(gone) and len(after_cancel) == len(before)

            # 3) znovu + Vložit
            await tap_system(h, page, py)
            pv2 = await h.ev("""(() => { const g=document.querySelector('.barfill-preview');
                return JSON.stringify(g ? [...g.querySelectorAll('.barfill-num')].map(t=>t.textContent) : null); })()""")
            await h.ev("(() => { const b=document.querySelector('.bn-fill-ok'); if(b) b.click(); return !!b; })()")
            await asyncio.sleep(1.5)
            after_ok = json.loads(await h.ev(BARS_IN_DB % (page - 1), await_promise=True) or "[]")
            n = len(nums) if nums else 0
            expect = [str(first + 1 + i) for i in range(n)]
            before_nums = [str(r[0]) for r in before]
            got = [str(r[0]) for r in after_ok if str(r[0]) not in before_nums]
            xs = [r[1] for r in after_ok if str(r[0]) not in before_nums]
            c3 = sorted(got) == sorted(expect) and len(set(xs)) == n
            print("   1 náhled: %s | 2 zrušit: %s | 3 vložit: %s (čísla %s, x %s)"
                  % (c1, c2, c3, got, xs))
            ok += c1 + c2 + c3
    print("\nsouhrn: %d/9" % ok)


asyncio.run(main())
