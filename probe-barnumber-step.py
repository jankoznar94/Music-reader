#!/usr/bin/env python3
"""E2E: čísla taktů — KROK (o kolik počítadlo roste) a OZNAČENÍ OBDÉLNÍKEM.

Ověřuje:
  * panel má pole „Krok“, výchozí 1, jde přepsat a přežije reload
  * klepnutí (bez tažení) položí číslo tam, kam se kleplo
  * tažení obdélníku vloží číslo do LEVÉHO HORNÍHO ROHU obdélníku (nad něj)
  * s krokem 4 jdou čísla 1, 5, 9… a „+“ u dalšího čísla skočí o krok
  * náhled obdélníku je vidět během tažení a po puštění zmizí
"""
import asyncio
import base64
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


BAR_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Čísla taktů'))")
# čísla taktů = anotace s třídou, filtry na fantomové měřicí <text> na (0,0)
TEXTS = """[...document.querySelectorAll('.annot-layer text')]
    .map(t => { const r = t.getBoundingClientRect();
      return {txt: t.textContent, x: +t.getAttribute('x'), y: +t.getAttribute('y'),
              left: Math.round(r.left), right: Math.round(r.right), bottom: Math.round(r.bottom)}; })
    .filter(t => t.x !== 0 || t.y !== 0)"""


async def texts(h):
    return await h.ev(TEXTS)


async def bar_step(h):
    return await h.ev("(document.querySelector('.ap-bar-step')||{}).value")


async def bar_next(h):
    return await h.ev("(document.querySelector('.ap-bar-next:not(.ap-bar-step)')||{}).value")


async def set_input(h, sel, val):
    await h.set_value(sel, str(val))
    await h.ev("document.querySelector('%s').dispatchEvent(new Event('change', {bubbles:true}))" % sel)


async def finger_drag(h, x0, y0, x1, y1, steps=8):
    """Tažení obdélníku PRSTEM (pointerType touch) — bez pera, bez palmu."""
    await h.cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x0, "y": y0,
                                             "button": "left", "clickCount": 1, "pointerType": "touch"})
    for i in range(1, steps + 1):
        await h.cdp("Input.dispatchMouseEvent", {"type": "mouseMoved",
                                                 "x": x0 + (x1 - x0) * i / steps,
                                                 "y": y0 + (y1 - y0) * i / steps,
                                                 "button": "left", "buttons": 1, "pointerType": "touch"})
        await asyncio.sleep(0.02)
    await h.cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x1, "y": y1,
                                             "button": "left", "clickCount": 1, "pointerType": "touch"})
    await asyncio.sleep(0.45)


async def drag(h, x0, y0, x1, y1, steps=8):
    await h.pen_down(x0, y0)
    for i in range(1, steps + 1):
        await h.pen_move(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        await asyncio.sleep(0.02)
    preview = await h.ev("!!document.querySelector('.annot-layer rect[stroke-dasharray=\"6 4\"]')")
    await h.pen_up(x1, y1)
    await asyncio.sleep(0.45)
    still = await h.ev("!!document.querySelector('.annot-layer rect[stroke-dasharray=\"6 4\"]')")
    return preview, still


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
        panel = await h.ev("""(() => { const r = document.querySelector('.annot-panel').getBoundingClientRect();
            return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; })()""")
        print("panel (l,t,w,h):", panel)
        print("krok:", await bar_step(h), "| další:", await bar_next(h))
        if await bar_step(h) != "1":
            fails.append("výchozí krok není 1")

        # 1) klepnutí bez tažení → číslo v místě klepnutí
        await h.pen_tap(560, 880)
        await asyncio.sleep(0.4)
        a = await texts(h)
        print("po klepnutí:", a)
        if len(a) != 1 or abs(a[0]["left"] - 560) > 12:
            fails.append("klepnutí nevložilo číslo do místa klepnutí")

        # 2) obdélník (tažení zleva odshora doprava dolů)
        prev, still = await drag(h, 470, 940, 700, 1010)
        a = await texts(h)
        print("náhled během tažení:", prev, "| po puštění zůstal:", still)
        print("po obdélníku:", a)
        if not prev:
            fails.append("během tažení není vidět obdélník")
        if still:
            fails.append("obdélník zůstal viset po puštění")
        if len(a) != 2:
            fails.append("obdélník nevložil druhé číslo")
        else:
            n2 = a[1]
            if abs(n2["left"] - 470) > 12:
                fails.append("číslo nesedí na levý okraj obdélníku (left=%s)" % n2["left"])
            if not (n2["bottom"] <= 942):
                fails.append("číslo není NAD obdélníkem (bottom=%s)" % n2["bottom"])
            if n2["txt"] != "2":
                fails.append("druhé číslo není 2 (je %s)" % n2["txt"])

        # 3) krok 4: „+“ u dalšího čísla skočí o krok, obdélník vloží další
        await set_input(h, ".ap-bar-step", 4)
        await asyncio.sleep(0.25)
        print("krok nastaven:", await bar_step(h), "| další:", await bar_next(h))
        plus = await h.ev(center("[...document.querySelectorAll('.ap-size')].find(e => e.title === 'Další číslo')"))
        await h.pen_tap(plus["x"], plus["y"])
        await asyncio.sleep(0.3)
        if await bar_next(h) != "7":
            fails.append("„+“ nerespektuje krok (další=%s, čekáno 3+4=7)" % await bar_next(h))
        await drag(h, 470, 1040, 760, 1090)
        a = await texts(h)
        print("po obdélníku s krokem 4:", a)
        print("další po vložení:", await bar_next(h))
        if len(a) != 3 or a[2]["txt"] != "7":
            fails.append("s krokem 4 nevložilo číslo 7 (je %s)" % (a[2]["txt"] if len(a) > 2 else None))
        if await bar_next(h) != "11":
            fails.append("po vložení se další nezvýšilo o krok (další=%s, čekáno 11)" % await bar_next(h))

        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        open("/tmp/barnumber-step-shot.png", "wb").write(base64.b64decode(shot["data"]))

        saved = await h.ev("({step: localStorage.getItem('noty.barStep'), next: localStorage.getItem('noty.barNext')})")
        print("localStorage:", saved)
        if saved["step"] != "4":
            fails.append("krok se nepamatuje")

        await h.cdp("Page.reload")
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(2.0)
        # Po reloadu zůstává route prohlížeče — stačí znovu zapnout anotace.
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="prohlížeč")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="stránka")
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        t = await h.ev(BAR_TOOL)
        await h.pen_tap(t["x"], t["y"])
        await asyncio.sleep(0.5)
        print("po reloadu krok:", await bar_step(h))
        if await bar_step(h) != "4":
            fails.append("krok nepřežil reload")

        # 4) obdélník PRSTEM — musí projít i při zapnutém „Jen pero“
        # (anotace už běží z kontroly po reloadu, proto se needituje znovu)
        if not await h.ev("!!document.querySelector('.ap-tool')"):
            await h.annot_toggle()
            await asyncio.sleep(0.5)
        t = await h.ev(BAR_TOOL)
        if t:
            await h.pen_tap(t["x"], t["y"])
            await asyncio.sleep(0.4)
        before = len(await texts(h))
        await finger_drag(h, 470, 1000, 700, 1050)
        a = await texts(h)
        print("po obdélníku prstem:", len(a) - before, "nové číslo:", a[-1] if a else None)
        if len(a) != before + 1:
            fails.append("obdélník prstem nevložil číslo (přidáno %d)" % (len(a) - before))
        elif abs(a[-1]["left"] - 470) > 12:
            fails.append("obdélník prstem nesedí na levý okraj (left=%s)" % a[-1]["left"])

        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
