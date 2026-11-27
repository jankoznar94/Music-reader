#!/usr/bin/env python3
"""Univerzální zavírací křížek: zavře okno, a když žádné není, ukončí anotaci."""
import asyncio
import base64
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
VW, VH = (int(x) for x in os.environ.get("NOTY_VIEWPORT", "800x1280").split("x"))


async def shot(h, path):
    s = await h.cdp("Page.captureScreenshot", {"format": "png"})
    open(path, "wb").write(base64.b64decode(s["data"]))


async def rect(h, sel, idx=0):
    return await h.ev(
        "(() => { const e = document.querySelectorAll(%s)[%d]; if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2,"
        " l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; })()"
        % (json.dumps(sel), idx))


async def st(h):
    return await h.ev("(() => { const el = document.querySelector('.viewer');"
                      " const c = el && el.__vueParentComponent; const s = c && c.setupState;"
                      " return { annot: !!(s && s.annotMode), zoom: !!(s && s.zoomPanelOpen),"
                      " barnum: !!(s && s.barnumMode), barHidden: !!(s && s.barHidden) } })()")


async def close_menu(h):
    items = await h.ev("document.querySelectorAll('.gm-item').length")
    if items:
        await h.ev("(() => { const s = document.querySelector('.gm-catch');"
                   " if (s) s.dispatchEvent(new PointerEvent('pointerup', {bubbles:true}));"
                   " document.body.dispatchEvent(new PointerEvent('pointerup', {bubbles:true})); return 1 })()")
        await asyncio.sleep(0.4)


async def pick_group(h, btn_title, item_word):
    """Otevře skupinu v hlavní liště a vybere v ní položku podle slova."""
    last = None
    for attempt in range(3):
        await close_menu(h)
        await asyncio.sleep(0.35)
        b = await rect(h, ".tb-btn[title^='%s']" % btn_title)
        await h.finger_tap(b["x"], b["y"])
        await asyncio.sleep(0.75)
        items = await h.ev("[...document.querySelectorAll('.gm-item')].map(e => e.getAttribute('title') || '')")
        idx = next((i for i, t in enumerate(items) if item_word.lower() in t.lower()), -1)
        if idx >= 0:
            it = await rect(h, ".gm-item", idx)
            await h.finger_tap(it["x"], it["y"])
            await asyncio.sleep(0.9)
            return
        last = items
    raise RuntimeError("položka %r není v %r: %r" % (item_word, btn_title, last))


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(VW, VH, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','button')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(4), pages=4, reset=False)
        await h.set_tablet(VW, VH, 2)
        await h.ev("(() => { const el = document.querySelector('.top-bar');"
                   " const c = el && el.__vueParentComponent;"
                   " if (c && c.setupState) c.setupState.barHidden = false; return 1 })()")
        await asyncio.sleep(0.5)

        ok("bez okna křížek není", await rect(h, ".overlay-close") is None, None)

        # --- 0) skupina Zobrazení: nesmí rozsvítit anotaci a jde zavřít ----
        await close_menu(h)
        zbtn = await rect(h, ".tb-btn[data-gm-group='view']")
        await h.finger_tap(zbtn["x"], zbtn["y"])
        await asyncio.sleep(0.7)
        menu_items = await h.ev("document.querySelectorAll('.gm-item').length")
        ok("skupina Zobrazení se otevřela", menu_items > 0, menu_items)
        annot_on = await h.ev("document.querySelector('.tb-btn[title^=\"Anotace\"]').classList.contains('on')")
        ok("tlačítko Anotace se NEROZSVÍTÍ kvůli nabídce", not annot_on, annot_on)
        ok("křížek je i u nabídky skupiny", await rect(h, ".overlay-close") is not None, None)
        # druhé ťuknutí na totéž tlačítko nabídku zavře
        await h.finger_tap(zbtn["x"], zbtn["y"])
        await asyncio.sleep(0.7)
        ok("druhé ťuknutí na Zobrazení nabídku zavřelo",
           await h.ev("document.querySelectorAll('.gm-item').length") == 0, None)
        # a křížek ji taky zavře
        await h.finger_tap(zbtn["x"], zbtn["y"])
        await asyncio.sleep(0.7)
        ok("nabídka se otevřela podruhé", await h.ev("document.querySelectorAll('.gm-item').length") > 0, None)
        btnM = await rect(h, ".overlay-close")
        if btnM:
            await h.finger_tap(btnM["x"], btnM["y"])
            await asyncio.sleep(0.6)
            ok("křížek zavřel nabídku skupiny",
               await h.ev("document.querySelectorAll('.gm-item').length") == 0, None)
        await shot(h, "/tmp/close-menu.png")

        # --- 1b) druhé ťuknutí na skupinu zavře i okna skupiny --------------
        await pick_group(h, "Zobrazení", "Zvětšení")
        s = await st(h)
        ok("okno Zvětšení je zase otevřené", s["zoom"], s)
        await h.finger_tap(zbtn["x"], zbtn["y"])       # 1. ťuk: otevře nabídku
        await asyncio.sleep(0.7)
        ok("nabídka skupiny se otevřela", await h.ev("document.querySelectorAll('.gm-item').length") > 0, None)
        await h.finger_tap(zbtn["x"], zbtn["y"])       # 2. ťuk: zavře nabídku I okno
        await asyncio.sleep(0.8)
        s = await st(h)
        ok("druhé ťuknutí zavřelo nabídku", await h.ev("document.querySelectorAll('.gm-item').length") == 0, None)
        ok("druhé ťuknutí zavřelo i okno Zvětšení (ne jen lištu)", not s["zoom"], s)
        ok("po zavření zmizel i křížek", await rect(h, ".overlay-close") is None, None)

        # --- 1) okno Zvětšení: křížek ho zavře ----------------------------
        await pick_group(h, "Zobrazení", "Zvětšení")
        s = await st(h)
        ok("okno Zvětšení je otevřené", s["zoom"], s)
        btn = await rect(h, ".overlay-close")
        ok("křížek je u otevřeného okna", btn is not None, btn)
        ok("křížek je vodorovně UPROSTŘED",
           btn and abs((btn["l"] + btn["r"]) / 2 - VW / 2) < 2, btn)
        nav_r = await h.ev("(() => { const b=[...document.querySelectorAll('.annot-nav-btn')];"
                           " return b.map(e => { const r = e.getBoundingClientRect();"
                           " return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)] }) })()")
        clashing = btn and any(not (btn["r"] < n[0] or btn["l"] > n[2] or btn["b"] < n[1] or btn["t"] > n[3]) for n in nav_r)
        ok("křížek nepřekrývá šipky listování", not clashing, {"krizek": btn, "sipky": nav_r})
        ok("křížek má dotykovou plochu ≥ 44 px", btn and btn["w"] >= 44 and btn["h"] >= 44, btn)
        if btn:
            await h.finger_tap(btn["x"], btn["y"])
            await asyncio.sleep(0.6)
            s = await st(h)
            ok("křížek zavřel okno Zvětšení", not s["zoom"], s)
            ok("křížek po zavření zmizel", await rect(h, ".overlay-close") is None, None)

        # --- 2) okno čísel taktů -----------------------------------------
        await pick_group(h, "Záložky", "Čísla taktů")
        s = await st(h)
        ok("okno čísel taktů se otevřelo", s["barnum"], s)
        btn2 = await rect(h, ".overlay-close")
        ok("křížek je i u čísel taktů", btn2 is not None, btn2)
        if btn2:
            await h.finger_tap(btn2["x"], btn2["y"])
            await asyncio.sleep(0.6)
            s = await st(h)
            ok("křížek zavřel čísla taktů", not s["barnum"], s)

        # --- 3) anotační režim -------------------------------------------
        a = await rect(h, ".tb-btn[title^='Anotace']")
        await h.finger_tap(a["x"], a["y"])
        await asyncio.sleep(0.8)
        s = await st(h)
        ok("anotace běží", s["annot"], s)
        btnA = await rect(h, ".overlay-close")
        ok("v anotaci je křížek vidět", btnA is not None, btnA)
        nav = await h.ev("(() => { const els=[...document.querySelectorAll('.annot-nav-btn')];"
                         " return els.map(e => { const r = e.getBoundingClientRect();"
                         " return [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)] }) })()")
        ok("šipky listování jsou v anotaci vykreslené", len(nav) == 2, nav)
        overlap = btnA and any(not (btnA["r"] < n[0] or btnA["l"] > n[2] or btnA["b"] < n[1] or btnA["t"] > n[3]) for n in nav)
        ok("křížek nepřekrývá stránkování", not overlap, {"krizek": btnA, "navigace": nav})
        await shot(h, "/tmp/close-annot.png")
        if btnA:
            await h.finger_tap(btnA["x"], btnA["y"])
            await asyncio.sleep(0.7)
            s = await st(h)
            ok("křížek ukončil anotační režim", not s["annot"], s)
            ok("křížek po ukončení zmizel", await rect(h, ".overlay-close") is None, None)
            ok("lišta je vidět", not s["barHidden"], s)
        await shot(h, "/tmp/close-none.png")

    ok.report()

asyncio.run(main())
