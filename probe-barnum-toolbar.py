#!/usr/bin/env python3
"""Tlačítko ČÍSLOVÁNÍ v hlavní liště: otevře JEN malý panel čísel (velký
anotační panel zůstane zavřený) a lupa v něm funguje. Navíc ověří, že
tlačítko pro centrování je stejně velké jako tlačítko anotace.

Jan (Nov 2026): „číslování bychom měli dát úplně mimo anotační menu — bude mít
svoje vlastní tlačítko na hlavní liště“ a „tlačítko pro menu pro centrování je
menší než tlačítko pro anotační mód“.

Spouštěj: scripts/run-probe-fresh.sh probe-barnum-toolbar.py
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

OK = []
BAD = []


def check(cond, label, extra=""):
    (OK if cond else BAD).append(label)
    print(("OK   " if cond else "CHYBA") + " " + label + ((" — " + str(extra)) if extra else ""))


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)

        # 1) tlačítko číslování je v liště a má glyf „1"
        has = await h.ev("""(() => [...document.querySelectorAll('.tb-btn')]
            .some(b => (b.title||'').startsWith('Číslování taktů')))()""")
        check(has, "tlačítko Číslování taktů je v hlavní liště")

        # 2) velikosti: anotace vs. centrování (preference)
        sizes = json.loads(await h.ev("""(() => {
            const a = [...document.querySelectorAll('.tb-btn')].find(b => (b.title||'').startsWith('Anotace'));
            const c = [...document.querySelectorAll('.tb-btn')].find(b => (b.title||'').startsWith('Vycentrovat'));
            const r = e => e ? {w: Math.round(e.getBoundingClientRect().width), h: Math.round(e.getBoundingClientRect().height)} : null;
            return JSON.stringify({annot: r(a), center: r(c)}); })()"""))
        check(sizes["annot"] and sizes["center"] and sizes["annot"] == sizes["center"],
              "centrování je stejně velké jako anotace", sizes)

        # 3) klepnutí na tlačítko otevře JEN malý panel
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); b.click(); return true; })()""")
        await h.wait_for("!!document.querySelector('.barnum-panel')", timeout=8, label="barnum panel")
        state = json.loads(await h.ev(
            "JSON.stringify({barnum: !!document.querySelector('.barnum-panel'),"
            " annot: !!document.querySelector('.annot-panel'),"
            " on: [...document.querySelectorAll('.tb-btn')].some(b => (b.title||'').startsWith('Číslování') && b.classList.contains('on'))})"))
        check(state["barnum"], "panel čísel se otevřel")
        check(not state["annot"], "velký anotační panel zůstal zavřený")
        check(state["on"], "tlačítko svítí (aktivní režim)")

        # 4) lupa v tomto režimu funguje
        await h.ev("(() => { const b=document.querySelector('.bn-pick'); if(b) b.click(); return !!b; })()")
        await asyncio.sleep(0.3)
        vb = [float(v) for v in (await h.ev(
            "document.querySelector('.annot-layer').getAttribute('viewBox')")).split()]
        s = vb[2] / 595.2
        pt = json.loads(await h.ev("""(() => { const svg=document.querySelector('.annot-layer');
            const g=svg.getScreenCTM(); const p=new DOMPoint(%f,%f).matrixTransform(g);
            return JSON.stringify({x:p.x,y:p.y}); })()""" % (vb[0] + 67.1 * s, vb[1] + 515.2 * s)))
        n0 = int(await h.ev("JSON.stringify((window.__barPickDbg||[]).length)"))
        await h.cdp("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [
            {"x": pt["x"], "y": pt["y"], "id": 0, "radiusX": 11, "radiusY": 11, "force": 1.0}]})
        await asyncio.sleep(0.05)
        await h.cdp("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        await asyncio.sleep(3)
        got = json.loads(await h.ev("JSON.stringify((window.__barPickDbg||[]).slice(%d))" % n0))
        digits = next((d["ocr"]["digits"] for d in got if isinstance(d, dict) and "ocr" in d), "")
        check(str(digits) == "9", "lupa v režimu číslování přečte 9", digits)

        # 5) vypnutí tlačítkem
        await h.ev("""(() => { const b=[...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title||'').startsWith('Číslování taktů')); b.click(); return true; })()""")
        await asyncio.sleep(0.5)
        check(not await h.ev("!!document.querySelector('.barnum-panel')"), "po vypnutí panel zmizí")

        print("SOUHRN: %d OK, %d chyb" % (len(OK), len(BAD)))


asyncio.run(main())
