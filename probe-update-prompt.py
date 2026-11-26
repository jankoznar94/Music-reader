#!/usr/bin/env python3
"""Okno „Nová verze aplikace je k dispozici“ (UpdatePrompt.vue).

Ověřuje v reálném prohlížeči:
  1. po startu appky okno NENÍ vidět (nic k dispozici)
  2. jakmile update.js ohlásí novou verzi, okno vyskočí — i nad otevřenou skladbou
  3. okno neblokuje kreslení pod sebou (root má pointer-events: none)
  4. „Později“ okno zavře a pro tutéž verzi se už neukáže
  5. jiná (novější) verze okno ukáže znovu
  6. tlačítko „Aktualizovat hned“ existuje a je nad textem
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
APP = os.environ.get("NOTY_APP") or m.APP_URL


async def rect(h, sel):
    return await h.ev(
        "(() => { const e = document.querySelector(%s); if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2, left: r.left, right: r.right,"
        "          top: r.top, bottom: r.bottom, w: r.width, h: r.height }; })()" % json.dumps(sel))


async def state(h):
    return await h.ev(
        "(() => ({ box: !!document.querySelector('.up-box'),"
        "  title: (document.querySelector('.up-title') || {}).textContent || '',"
        "  btns: [...document.querySelectorAll('.up-btn')].map(b => b.textContent.trim()),"
        "  pe: document.querySelector('.up-root') ? getComputedStyle(document.querySelector('.up-root')).pointerEvents : null,"
        "  dismissed: sessionStorage.getItem('noty-update-dismissed'),"
        "  hash: window.__updateState }))()")


async def force(h, value, hash=None):
    await h.ev("window.__setUpdateAvailable(%s, %s)" % (json.dumps(value), json.dumps(hash)))
    await asyncio.sleep(0.2)


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.ev("sessionStorage.clear()")
        await h.open()
        await h.open_song(pdf=m.make_pdf(4), pages=4, reset=False)

        st = await state(h)
        ok("po startu okno není vidět", not st["box"], st)

        # --- 1) nová verze → okno -------------------------------------------
        await force(h, True, "assets/index-TEST1.js")
        st = await state(h)
        ok("nová verze → okno vyskočí", st["box"], st)
        ok("okno má nadpis o nové verzi", "nová verze" in st["title"].lower(), st["title"])
        ok("okno má dvě tlačítka", st["btns"] == ["Aktualizovat hned", "Později"], st["btns"])
        ok("okno neblokuje okolí (pointer-events: none)", st["pe"] == "none", st["pe"])
        box = await rect(h, ".up-box")
        ok("okno je nahoře uprostřed displeje",
           bool(box) and abs(box["x"] - 400) < 3 and box["top"] < 200, box)

        # --- 2) „Později“ ---------------------------------------------------
        later = await rect(h, ".up-btn:not(.primary)")
        await h.finger_tap(later["x"], later["y"])
        await asyncio.sleep(0.3)
        st = await state(h)
        ok("Později okno zavře", not st["box"], st)
        ok("Později si verzi zapamatuje", st["dismissed"] == "assets/index-TEST1.js", st["dismissed"])

        await force(h, True, "assets/index-TEST1.js")
        ok("tatáž verze se už neukáže", not (await state(h))["box"])

        # --- 3) novější verze → znovu ---------------------------------------
        await force(h, True, "assets/index-TEST2.js")
        ok("novější verze okno ukáže znovu", (await state(h))["box"])

        # --- 4) tlačítko pro aktualizaci je nad „Později“ -------------------
        upd = await rect(h, ".up-btn.primary")
        later = await rect(h, ".up-btn:not(.primary)")
        ok("Aktualizovat hned je první (nad Později)",
           bool(upd and later) and upd["top"] < later["top"], {"upd": upd and upd["top"], "later": later and later["top"]})

        # --- 5) okno se ukáže i nad knihovnou -------------------------------
        await force(h, False)
        await h.goto_library() if hasattr(h, "goto_library") else None
        await force(h, True, "assets/index-TEST3.js")
        ok("okno funguje i mimo prohlížeč skladby", (await state(h))["box"])

    ok.report()


asyncio.run(main())
