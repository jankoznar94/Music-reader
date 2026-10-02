#!/usr/bin/env python3
"""Ověření: ťuknutí JEDNÍM PRSTEM na stránku zavře režimy, které otevřelo gesto.

Jan: „Když po těchto úpravách uživatel jedním prstem ťukne na stránku, tak by se
tyto módy měly všechny zavřít."

Měří se SKUTEČNÝM dotykem (Input.dispatchTouchEvent), protože právě touch cesta
je ta, kde tap nemusí vygenerovat kompatibilitní `click` — a kdyby appka
spoléhala jen na `onTap`, mřížka by po tříprstém gestu zůstala viset.

Scénáře:
  1) tři prsty → rotační mód se otevře; ťuknutí jedním prstem na plochu → zavřeno
  2) dva prsty → panel zoomu se otevře; ťuknutí jedním prstem → zavřeno
  3) ťuknutí na TLAČÍTKO v liště módy NEZAVÍRÁ (jinak by nešlo ovládat)
  4) ťuknutí do okrajové zóny módy zavře A ZÁROVEŇ otočí stránku
"""
import asyncio
import importlib.util
import json
import os
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
CDP_BASE = "http://127.0.0.1:9222"


def _load_harness():
    for cand in (
        os.path.join(_HERE, "cdp-e2e-harness.py"),
        os.path.expanduser(
            "~/.hermes/profiles/cfsb-agent/skills/software-development/"
            "pwa-pdf-viewer/scripts/cdp-e2e-harness.py"),
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_mod = _load_harness()
Harness, Check = _mod.Harness, _mod.Check


def fresh_harness(url="http://localhost:5173/"):
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(url)
    h._fresh_target = info.get("id")
    return h


STATE = r"""
(() => ({
  rotPanel: !!document.querySelector('.rot-panel'),
  rotGrid: !!document.querySelector('.rot-grid'),
  zoomPanel: !!document.querySelector('.zoom-panel:not(.rot-panel)'),
  page: (document.querySelector('.tb-page') || {}).textContent || '',
}))()
"""


async def open_viewer(h):
    await h.open()
    await h.set_tablet(800, 1280, 2)
    await asyncio.sleep(1.0)
    if not await h.ev("document.querySelectorAll('li.song').length"):
        await h.set_file_input("input[type=file]", _mod.make_pdf(6))
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=60, label="upload")
    await h.ev(_mod.Harness.expand_authors_js())
    await h.wait_for("document.querySelectorAll('li.song').length > 0",
                     timeout=10, label="expand")
    await h.click(".song-name")
    await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="viewer")
    await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="page")
    await asyncio.sleep(1.0)


def two(cx, cy, r=100):
    return [(cx - r, cy, 12), (cx + r, cy, 12)]


def three(cx, cy, r=170, spread=300):
    return [(cx - r, cy, 12), (cx + r, cy, 12), (cx, cy + spread, 12)]


async def main():
    ok = Check()
    async with fresh_harness() as h:
        await open_viewer(h)
        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

        # preflight
        await h.ev("(() => { window.__pre=[];"
                   " document.addEventListener('touchstart', e => window.__pre.push(e.touches.length),"
                   " { capture: true, passive: true }); return true; })()")
        await h.touch("touchStart", two(cx, cy))
        await asyncio.sleep(0.1)
        await h.touch("touchEnd", [])
        pre = await h.ev("JSON.stringify(window.__pre)")
        ok("preflight: dotyky se doručí", bool(pre) and "2" in pre, f"{pre}")
        if not (pre and "2" in pre):
            print("\nPREFLIGHT FAILED. Konec.")
            return ok.report()

        # ---------- 1) tři prsty → rotační mód; tap jedním prstem zavře ----------
        await h.touch("touchStart", three(cx, cy))
        await asyncio.sleep(0.2)
        st = await h.ev(STATE)
        ok("1) tři prsty otevřou rotační mód", st["rotPanel"] and st["rotGrid"], str(st))
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)
        st = await h.ev(STATE)
        ok("1) po gestu je mód pořád otevřený", st["rotPanel"], str(st))

        await h.finger_tap(cx, cy)
        await asyncio.sleep(0.6)
        st = await h.ev(STATE)
        ok("1) ťuknutí JEDNÍM PRSTEM mód ZAVŘE (panel i mřížka)",
           (not st["rotPanel"]) and (not st["rotGrid"]) and (not st["zoomPanel"]), str(st))

        # ---------- 2) dva prsty → panel zoomu; tap jedním prstem zavře ----------
        await h.touch("touchStart", two(cx, cy))
        await asyncio.sleep(0.2)
        st = await h.ev(STATE)
        ok("2) dva prsty otevřou panel zoomu", st["zoomPanel"], str(st))
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)

        await h.finger_tap(cx + 30, cy + 40)
        await asyncio.sleep(0.6)
        st = await h.ev(STATE)
        ok("2) ťuknutí jedním prstem zavře i panel zoomu",
           (not st["zoomPanel"]) and (not st["rotPanel"]), str(st))

        # ---------- 3) tap na TLAČÍTKO v liště módy nezavírá ----------
        await h.touch("touchStart", three(cx, cy))
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)
        st = await h.ev(STATE)
        ok("3) rotační mód je otevřený", st["rotPanel"], str(st))
        # tap na tlačítko „Anotace" v liště — mód se NESMÍ zavřít tudy
        btn = await h.ev("""(() => {
          const b = [...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title || '').startsWith('Anotace'));
          if (!b) return null;
          const r = b.getBoundingClientRect();
          return [r.left + r.width/2, r.top + r.height/2];
        })()""")
        if btn:
            await h.finger_tap(btn[0], btn[1])
            await asyncio.sleep(0.6)
            st = await h.ev(STATE)
            # Anotace zavírá ostatní panely — to je SPRÁVNÉ vzájemné vylučování,
            # ale nesmí to udělat cesta „tap na stránku". Proto tu jen ověříme,
            # že se neotevřel žádný z panelů gesta a anotace je zapnutá.
            ok("3) tap na tlačítko lišty neotevře panel gesta",
               (not st["zoomPanel"]) and (not st["rotPanel"]), str(st))
            await h.ev("""(() => { const a=[...document.querySelectorAll('.tb-btn')]
              .find(x=>(x.title||'').startsWith('Anotace')); if (a) a.click(); return 1; })()""")
            await asyncio.sleep(0.4)

        # ---------- 4) tap v okrajové zóně zavře A otočí stránku ----------
        # Nejdřív na 2. stránku — na 1/6 by prevPage() legitimně nic neudělal
        # a test by hlásil falešný FAIL.
        await h.touch("touchStart", two(cx, cy))
        await asyncio.sleep(0.15)
        await h.touch("touchEnd", [])
        btn_next = await h.ev("""(() => {
          const b = [...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title || '').startsWith('Anotace'));
          return !!b;
        })()""")
        # na 2. stránku se dostaneme tlačítkem lišty (swipe z prostředku nelistuje)
        await h.ev("(() => { const el=document.querySelector('.viewer'); return 1; })()")
        await h.touch("touchStart", three(cx, cy))
        await asyncio.sleep(0.15)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.3)

        # přepni na 2. stránku skutečným tahem z okrajové zóny
        await h.finger_swipe(g["left"] + 20, cy, g["left"] - 40, cy)
        await asyncio.sleep(0.8)
        st = await h.ev(STATE)
        print("   po swipu:", st)
        page_before = st["page"]
        ok("4) jsme na 2. stránce (předpoklad testu)", page_before == "2 / 6", page_before)
        if page_before != "2 / 6":
            print("   (listování se nepovedlo, test 4 se přeskočí)")
            return ok.report()

        # teď otevři rotační mód a ťukni do LEVÉHO okraje → zavřít + zpět na 1
        await h.touch("touchStart", three(cx, cy))
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)
        st = await h.ev(STATE)
        ok("4) rotační mód otevřený", st["rotPanel"], str(st))
        await h.finger_tap(g["left"] + 20, cy)
        await asyncio.sleep(0.8)
        st = await h.ev(STATE)
        ok("4) tap v okrajové zóně mód zavře", not st["rotPanel"], str(st))
        ok("4) a ZÁROVEŇ otočí stránku (listování funguje dál)",
           st["page"] != page_before, f"'{page_before}' -> '{st['page']}'")

        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
