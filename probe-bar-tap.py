#!/usr/bin/env python3
"""E2E: bodové vkládání čísla taktu — číslo NAD ťuknutým bodem.

Jan (Nov 2026): „U tohoto číslování uživatel bodově ťukne (prstem nebo perem) na
levý horní roh systému a číslo se umístí nad něj. Horizontálně zarovno s bodem,
vertikálně několik pixelů nad bod.“

Ověřuje:
  * ťuknutí vloží číslo, jehož LEVÝ OKRAJ je na x bodu (zarovno)
  * spodní okraj čísla (účaří) je pár px NAD bodem
  * ťuknutí s drobným chvěním (pár px) se pořád bere jako ťuknutí, ne obdélník
  * prstem i perem
"""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

TAP_GAP = 6


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


BAR_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Čísla taktů'))")


async def texts(h):
    return await h.ev("""[...document.querySelectorAll('.annot-layer text')]
        .filter(t => +t.getAttribute('x') !== 0 || +t.getAttribute('y') !== 0)
        .map(t => { const r = t.getBoundingClientRect();
          return {txt: t.textContent, x: +t.getAttribute('x'), y: +t.getAttribute('y'),
                  left: Math.round(r.left), right: Math.round(r.right),
                  top: Math.round(r.top), bottom: Math.round(r.bottom)}; })""")


async def finger_tap(h, x, y):
    await h.cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y,
                                             "button": "left", "clickCount": 1, "pointerType": "touch"})
    await asyncio.sleep(0.05)
    await h.cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y,
                                             "button": "left", "clickCount": 1, "pointerType": "touch"})
    await asyncio.sleep(0.45)


async def main():
    fails = []
    async with m.Harness() as h:
        await h.cdp("Storage.clearDataForOrigin", {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open()
        await h.ev("(() => { localStorage.clear(); navigator.serviceWorker && navigator.serviceWorker"
                   ".getRegistrations().then(rs => rs.forEach(r => r.unregister())); return true; })()")
        await h.open_song(pages=3)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        t = await h.ev(BAR_TOOL)
        await h.pen_tap(t["x"], t["y"])
        await asyncio.sleep(0.5)

        # 1) ťuknutí perem
        await h.pen_tap(520, 900)
        a = await texts(h)
        print("pero — ťuknutí (520,900):", a)
        if not a:
            fails.append("pero: číslo se nevložilo")
        else:
            n = a[0]
            if abs(n["left"] - 520) > 3:
                fails.append("pero: číslo není zarovno s bodem (left=%s, bod=520)" % n["left"])
            if not (884 <= n["bottom"] <= 898):
                fails.append("pero: číslo není pár px nad bodem (bottom=%s, bod=900)" % n["bottom"])

        # 2) ťuknutí prstem
        await finger_tap(h, 600, 1000)
        a = await texts(h)
        n = a[-1] if a else None
        print("prst — ťuknutí (600,1000):", n)
        if not n or n["txt"] != "2":
            fails.append("prst: číslo se nevložilo (%s)" % (n and n["txt"]))
        else:
            if abs(n["left"] - 600) > 3:
                fails.append("prst: číslo není zarovno s bodem (left=%s)" % n["left"])
            if not (984 <= n["bottom"] <= 998):
                fails.append("prst: číslo není pár px nad bodem (bottom=%s)" % n["bottom"])

        # 3) ťuknutí s chvěním (12 px) = pořád ťuknutí → číslo NAD bodem
        await h.pen_down(660, 1060)
        await h.pen_move(668, 1066)
        await h.pen_up(668, 1066)
        await asyncio.sleep(0.45)
        a = await texts(h)
        n = a[-1] if a else None
        print("chvění (660,1060)→(668,1066):", n)
        if not n or n["txt"] != "3":
            fails.append("chvění: číslo se nevložilo")
        elif not (1058 <= n["bottom"] <= 1072):
            # kotví se k místu P UŠTĚNÍ (668,1066), číslo visí pár px nad ním
            fails.append("chvění: číslo nevisí nad bodem, spadlo do obdélníku (bottom=%s)" % n["bottom"])

        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
