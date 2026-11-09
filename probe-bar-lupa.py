#!/usr/bin/env python3
"""LUPA na reálném skenu: měří čas a SPRÁVNOST čtení vytištěných čísel taktů.

Jan (Nov 2026): „po klepnutí se zobrazí hláška o čtení, ale výsledek až při
dalším pokusu“, „hledání trvá hrozně dlouho“, „místo 9 to přečetlo 19“.

Sken: Mozart – Davide penitente (80 stran, bez textové vrstvy).
Souřadnice jsou v BODECH PDF (y od shora), naměřené segmentací obrázků.

Spouštěj: scripts/run-probe-fresh.sh probe-bar-lupa.py
"""
import asyncio
import importlib.util
import json
import os
import time

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = ("/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
       "native-inputs/b6372852962f9d22817e7d1e99486df274129c0907a91924f0da5d2b8c47f722/"
       "doc_1bb2c499f695_Mozart-Davide penitente.pdf")

# (strana, x, y v bodech PDF, správné číslo)
CASES = [
    (2, 67.1, 515.2, 9),
    (2, 68.7, 249.6, 5),
    (6, 73.7, 43.8, 42),
    (6, 74.2, 345.2, 47),
    (6, 75.8, 662.9, 52),
    # klepnutí kousek VEDLE čísla (prst se netrefí přesně) — hledání shluku to má srovnat
    (2, 73.5, 508.0, 9),
    (6, 80.5, 47.0, 42),
    # str. 8 — Jan: „některá čísla to přečíst nechce“ (75, 78, 81)
    (8, 69.0, 46.8, 75),
    (8, 70.8, 271.2, 78),
    (8, 69.6, 493.2, 81),
]

TO_SCREEN = """(() => { const svg=document.querySelector('.annot-layer');
  const g=svg.getScreenCTM();
  const p=new DOMPoint(%f,%f).matrixTransform(g);
  return JSON.stringify({x:p.x,y:p.y}); })()"""


async def ensure_tool(h, page):
    """Otevře stránku a připraví lupu (panel + nástroj Čísla taktů + lupa)."""
    if await h.ev("document.querySelector('.tb-page') && document.querySelector('.tb-page').textContent.trim()") != "%d / 80" % page:
        await h.goto(page)
    if not await h.ev("!!document.querySelector('.annot-panel')"):
        await h.annot_toggle()
    await h.ev("""(() => { const b=[...document.querySelectorAll('.ap-tool')]
        .find(x=>(x.title||'').startsWith('Čísla taktů')); if(b) b.click(); return !!b; })()""")
    await h.wait_for("!!document.querySelector('.bn-pick')", timeout=8, label="barnum panel")
    if not await h.ev("!!document.querySelector('.bn-pick.on')"):
        await h.ev("(() => { const b=document.querySelector('.bn-pick'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.3)
    await h.ev("""(() => { const b=document.querySelector('.ap-collapse');
        if (b && b.title === 'Sbalit') { b.click(); return true; } return false; })()""")
    await asyncio.sleep(0.4)


async def tap_case(h, page, px, py):
    await ensure_tool(h, page)
    vb = [float(v) for v in (await h.ev(
        "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
    s = vb[2] / 595.2
    pt = json.loads(await h.ev(TO_SCREEN % (vb[0] + px * s, vb[1] + py * s)))
    n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
    t0 = time.time()
    await h.cdp("Input.dispatchTouchEvent",
                {"type": "touchStart",
                 "touchPoints": [{"x": pt["x"], "y": pt["y"], "id": 0,
                                  "radiusX": 11, "radiusY": 11, "force": 1.0}]})
    await asyncio.sleep(0.05)
    await h.cdp("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    toast, t_res = None, None
    trail = []
    while time.time() - t0 < 30:
        st = json.loads(await h.ev(
            "JSON.stringify({t:(document.querySelector('.viewer-toast')||{}).textContent||''})"))["t"]
        if st != toast:
            toast = st
            trail.append((round(time.time() - t0, 2), st))
        if t_res is None and any(k in st for k in ("přečteno", "Nalezeno", "nepodařilo", "selhalo")):
            t_res = round(time.time() - t0, 2)
        if t_res is not None and time.time() - t0 > t_res + 0.6:
            break
        await asyncio.sleep(0.1)
    dbg = json.loads(await h.ev(
        "JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
    ocr = next((d["ocr"] for d in dbg if isinstance(d, dict) and "ocr" in d), {})
    return {"trail": trail, "t": t_res, "digits": ocr.get("digits"),
            "conf": ocr.get("confidence"), "render": ocr.get("render"),
            "find": ocr.get("find"), "total": ocr.get("total"),
            "cluster": ocr.get("cluster")}


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        ok = 0
        for page, px, py, truth in CASES:
            r = await tap_case(h, page, px, py)
            good = str(r["digits"]) == str(truth)
            ok += good
            print("str.%d  pravda %-3s  přečteno %-4s  jistota %-3s  shluk %s  "
                  "render %sms find %sms celkem %sms  %s"
                  % (page, truth, r["digits"], r["conf"], r["cluster"],
                     r["render"], r["find"], r["total"], "OK" if good else "CHYBA"))
            print("   toasty:", r["trail"])
        print("SOUHRN: %d/%d správně" % (ok, len(CASES)))
        items = json.loads(await h.ev("""(async () => { const q=indexedDB.open('noty-app');
          const db=await new Promise(r=>{q.onsuccess=()=>r(q.result);q.onerror=()=>r(null);});
          const rows=await new Promise(r=>{const t=db.transaction('annotations','readonly')
            .objectStore('annotations').getAll(); t.onsuccess=()=>r(t.result||[]); t.onerror=()=>r([]);});
          db.close(); const o=[]; for(const row of rows) for(const it of (row.items||[]))
            if(it.barNum) o.push({text:it.text,page:it.page,hidden:it.hidden}); return JSON.stringify(o); })()""",
                             await_promise=True))
        print("barNum v DB:", items)


asyncio.run(main())
