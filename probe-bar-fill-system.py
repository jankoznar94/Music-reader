#!/usr/bin/env python3
"""Dočíslování systému: čísla NAD HORNÍ osnovu systému a z INDEXU systému.

Ověřuje dvě věci, které Jan nahlásil (listopad 2026):
  1. klepnutí do SPODNÍ osnovy (klavír) → čísla patří nad NEJHORNĚJŠÍ osnovu
     celého systému, ne nad tu kliknutou,
  2. číslo 1. taktu se bere z UŽ ZADANÉHO čísla v systému (skrytý index),
     ne z pole „Další“ — to se naschvál nastaví na nesmysl.
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

# (strana, pdf y klepnutí (SPODNÍ osnova), index 1. taktu, očekávaná čísla,
#  pdf y horní osnovy systému)
CASES = [
    (2, 470, 5, ["6", "7", "8"], 264.0),
    (2, 630, 9, ["10", "11"], 529.8),
    (4, 520, 24, ["25", "26"], 307.7),
    (6, 300, 42, ["43", "44", "45", "46"], 52.5),
    (10, 740, 4, ["5", "6"], 487.2),
]

# (strana, pdf y klepnutí do SPODNÍ osnovy, očekávaná horní linka systému)
SYSTEMS = [
    (4, 100, 48.3),    # 1. systém, klik do 4. hlasu
    (4, 700, 560.5),   # 3. systém
    (8, 130, 53.7),
    (8, 400, 305.8),
    (8, 700, 566.0),
]


async def panel(h):
    for _ in range(5):
        if await h.ev("document.querySelectorAll('.bn-input').length >= 2"):
            return
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); if (b) b.click();
            const c=document.querySelector('.ap-collapse'); if (!b && c) c.click(); return 1; })()""")
        await asyncio.sleep(0.8)
    await h.wait_for("document.querySelectorAll('.bn-input').length >= 2", timeout=8, label="bn")


async def push_index(h, pdf_y, n):
    # Anotace se po otevření panelu NAČÍTAJÍ Z IndexedDB (async) a přepíšou pole,
    # takže ručně vložený index může zmizet — proto se po vložení ověří a zopakuje.
    js = """(async () => { const d=window.__barDev;
        const s = await d.layerScale(d.currentPage.value);
        const it=d.annotations.value.items;
        for (let i=it.length-1;i>=0;i--) if (it[i].barNum) it.splice(i,1);
        it.push({ id:'idx-'+%d, page:d.currentPage.value, tool:'text', barNum:true,
                  hidden:true, text:'%d', size:16, color:'#000000', opacity:1,
                  border:false, x:70*s, y:%f*s });
        return it.filter(i=>i.barNum).length; })()""" % (n, n, pdf_y)
    for _ in range(6):
        got = await h.ev(js, await_promise=True)
        await asyncio.sleep(0.4)
        alive = await h.ev("window.__barDev.annotations.value.items.filter(i=>i.barNum).length")
        if alive:
            return got
    return 0


async def tap(h, page, py):
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
    ok = 0
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        cur = None
        for (page, py, idx, expect, sys_top) in CASES:
            if cur != page:
                await h.goto(page); cur = page
            await panel(h)
            # „Další“ naschvál špatně — do výpočtu nesmí vstoupit.
            await h.ev("""(() => { const ins=[...document.querySelectorAll('.bn-input')];
                ins[0].value='42'; ins[0].dispatchEvent(new Event('change',{bubbles:true}));
                ins[1].value='4'; ins[1].dispatchEvent(new Event('change',{bubbles:true})); return 1; })()""")
            await asyncio.sleep(0.3)
            await push_index(h, sys_top - 12, idx)
            await tap(h, page, py)
            pv = await h.ev("""(() => { const p=window.__barDev.barFillPreview.value;
                if(!p) return 'null';
                return JSON.stringify({first:p.first, src:p.firstSrc, start:p.start,
                  bars:p.bars, nums:p.items.map(i=>i.text),
                  ys:p.items.map(i=>i.y), y2s:p.items.map(i=>i.y2)}); })()""")
            if isinstance(pv, dict) or pv == 'null' or pv is None:
                p = None if pv in ('null', None) else pv
            else:
                p = json.loads(pv)
            scale = await h.ev("""(async () => {
                const p=window.__barDev; return JSON.stringify(await p.layerScale(p.currentPage.value)); })()""",
                await_promise=True)
            if isinstance(scale, str):
                scale = json.loads(scale)
            if not p:
                print("str %d y %d: BEZ NÁHLEDU" % (page, py))
                continue
            ys_pdf = [round(y / scale, 1) for y in p["ys"]]
            y2_pdf = [round(y / scale, 1) for y in p["y2s"]]
            nums_ok = (p["nums"] == expect) if expect else (p["nums"] and p["nums"][0] == str(idx + 1))
            # čísla musí být NAD horní osnovou systému (pár bodů nad ní), ne u kliknuté
            y_ok = all(abs(y - (sys_top - 2)) <= 6 for y in ys_pdf)
            src_ok = p["src"] == "index" and p["first"] == idx
            dbg = await h.ev("JSON.stringify((window.__barPickDbg||[]).filter(d=>d&&d.fill).slice(-1)[0]||{})")
            if isinstance(dbg, str): dbg = json.loads(dbg)
            f = (dbg or {}).get('fill', {})
            print("   det: staves=%s ok=%s lines=%s top=%s cands=%s" % (
                f.get('staves'), f.get('ok'),
                [round(v) for v in (f.get('lines') or [])], f.get('top'),
                (f.get('cands') or [])[:14]))
            print("   dbg: %s" % json.dumps((f.get('dbg') or {}).get('all'), ensure_ascii=False))
            pvdbg = await h.ev("JSON.stringify((window.__barPickDbg||[]).filter(d=>d&&d.preview).slice(-1)[0]||{})")
            if isinstance(pvdbg, str): pvdbg = json.loads(pvdbg)
            print("   preview dbg: %s" % (pvdbg or {}).get('preview'))
            idx_dbg = await h.ev("""(async () => {
                const d = window.__barDev;
                return JSON.stringify({
                  page: d.currentPage.value,
                  s: await d.layerScale(d.currentPage.value),
                  items: d.annotations.value.items.filter(i=>i.barNum)
                    .map(i=>({p:i.page, text:i.text, y:Math.round(i.y), x:Math.round(i.x)}))});
                })()""", await_promise=True)
            print("   index: %s" % idx_dbg)
            print("str %d y %d: čísla %s (čekáno %s), y %s (systém %.1f), první=%s/%s, y2 %s"
                  % (page, py, p["nums"], expect, ys_pdf, sys_top, p["first"], p["src"], y2_pdf))
            print("   čísla %s | výška %s | index %s" % (nums_ok, y_ok, src_ok))
            ok += nums_ok + y_ok + src_ok
            # 4) POSLEDNÍ PŘÍPAD: potvrdit „Vložit“ a zkontrolovat SOUŘADNICE v DB.
            if (page, py) == (4, 520):
                await h.ev("(() => { const b=document.querySelector('.bn-fill-ok'); if(b) b.click(); return !!b; })()")
                await asyncio.sleep(1.5)
                db = await h.ev("""(async () => {
                    const q = indexedDB.open('noty-app');
                    const d = await new Promise(r => { q.onsuccess = () => r(q.result); q.onerror = () => r(null); });
                    const rows = await new Promise(r => { const t = d.transaction('annotations','readonly')
                        .objectStore('annotations').getAll(); t.onsuccess = () => r(t.result||[]); t.onerror = () => r([]); });
                    d.close(); const out = [];
                    for (const row of rows) for (const it of (row.items||[]))
                      if (it.barNum && it.page === 3) out.push([Number(it.text), Math.round(it.x), Math.round(it.y)]);
                    return JSON.stringify(out.sort((a,b)=>a[0]-b[0])); })()""", await_promise=True)
                if isinstance(db, str): db = json.loads(db)
                nums_db = [r[0] for r in db]
                # index (24) je tam taky (commit uloží celé pole), ale leží výš;
                # rozhoduje, že doplněná čísla 25, 26 mají STEJNOU výšku nad
                # horní osnovou systému a x roste zleva doprava.
                fill = [r for r in db if r[0] in (25, 26)]
                commit_ok = (nums_db == [24, 25, 26] and len(fill) == 2
                             and len(set(r[2] for r in fill)) == 1
                             and fill[0][1] < fill[1][1]
                             and abs(fill[0][2] / scale - (sys_top - 2)) <= 6)
                print("   DB po Vložit: %s → %s" % (db, commit_ok))
                ok += commit_ok
        # 5) SESKUPENÍ SYSTÉMU na dalších stránkách: klepnutí do SPODNÍ osnovy
        # musí dát horní linku CELÉHO systému (ne té osnovy). Ověřuje se jen
        # `top` z detekce — čísla tu neřešíme.
        for (page, py, want_top) in SYSTEMS:
            if cur != page:
                await h.goto(page); cur = page
            await panel(h)
            await h.ev("""(() => { const it=window.__barDev.annotations.value.items;
                for (let i=it.length-1;i>=0;i--) if (it[i].barNum) it.splice(i,1); return 1; })()""")
            await tap(h, page, py)
            dbg = await h.ev("JSON.stringify((window.__barPickDbg||[]).filter(d=>d&&d.fill).slice(-1)[0]||{})")
            if isinstance(dbg, str): dbg = json.loads(dbg)
            f = (dbg or {}).get('fill', {})
            got = f.get('top')
            good = got is not None and abs(got - want_top) <= 4
            print("systém str %d y %d: top=%s (čekáno %.1f) osnov=%s → %s"
                  % (page, py, None if got is None else round(got, 1), want_top, f.get('staves'), good))
            ok += good
    print("\nsouhrn: %d/%d" % (ok, 3 * len(CASES) + 1 + len(SYSTEMS)))


asyncio.run(main())
