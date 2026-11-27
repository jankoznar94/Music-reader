#!/usr/bin/env python3
"""Značky (posuvky #, b, ♮…) se vkládají jako noty: žádný koláč, jen hláška.

Jan (27. 11. 2026): „vkládání hudebních křížků a béček atd. se musí chovat jako
vkládání not — nezobrazí se koláč, ale rovnou hláška o vložení.“

Ověřuje:
  * výběr nástroje „Značky“ v nabídce nástrojů NEOTEVRЕ koláč,
  * místo něj se ukáže hláška „Klepni do not — vyber místo pro značku“,
  * ťuknutí do not otevře dialog se znaky (posuvky, ozdoby…), ze kterého jde
    značka vložit — stejná cesta jako u noty,
  * pro srovnání: „Noty“ se chovají stejně (regrese).
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness, Check = m.Harness, m.Check

APP = os.environ.get("APP_URL", "http://localhost:5173/")

ANNOT_BTN = """(() => {
  const b = [...document.querySelectorAll('.tb-btn')].find(x => (x.title || '').startsWith('Anotace'));
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
})()"""

ITEM = """(() => {
  const el = [...document.querySelectorAll('.gm-item')].find(x => x.title === %s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
})()"""

STATE = """(() => JSON.stringify({
  pie: !!document.querySelector('.pie-svg'),
  hint: (document.querySelector('.place-hint') || {}).textContent || '',
  tool: window.__barDev.tool.value,
  annot: window.__barDev.annotMode.value,
  dialog: !!document.querySelector('.text-input-card'),
  marks: !!document.querySelector('.mark-sec'),
  items: window.__barDev.annotations.value.items.map(i => i.text),
}))()"""


async def press(h, pt, hold=0.06):
    await h.cdp("Input.dispatchMouseEvent",
                {"type": "mousePressed", "x": pt["x"], "y": pt["y"], "button": "left",
                 "clickCount": 1, "pointerType": "mouse"})
    await asyncio.sleep(hold)
    await h.cdp("Input.dispatchMouseEvent",
                {"type": "mouseReleased", "x": pt["x"], "y": pt["y"], "button": "left",
                 "clickCount": 1, "pointerType": "mouse"})
    await asyncio.sleep(0.7)


async def choose_tool(h, label):
    """Podržení ✏️ otevře nabídku nástrojů; ťuknutí na položku ji vybere."""
    btn = await h.ev(ANNOT_BTN)
    await h.cdp("Input.dispatchMouseEvent",
                {"type": "mousePressed", "x": btn["x"], "y": btn["y"], "button": "left",
                 "clickCount": 1, "pointerType": "mouse"})
    await asyncio.sleep(0.7)          # podržení = nabídka nástrojů
    it = await h.ev(ITEM % json.dumps(label))
    if not it:
        await h.cdp("Input.dispatchMouseEvent",
                    {"type": "mouseReleased", "x": btn["x"], "y": btn["y"], "button": "left",
                     "clickCount": 1, "pointerType": "mouse"})
        return False
    await press(h, it)
    await asyncio.sleep(0.6)
    return True


async def main():
    ok = Check()
    async with Harness(APP) as h:
        await h.open()
        # Nabídka nástrojů (s koláčem) existuje jen v animovaném režimu ovládání.
        await h.ev("localStorage.setItem('noty.controlMode','gesture')")
        await h.ev("location.reload()")
        await asyncio.sleep(3)
        await h.set_tablet()
        await h.open_song(pages=6, reset=True)
        await asyncio.sleep(1.0)

        # --- ZNAČKY: žádný koláč, rovnou hláška ---
        ok("nabídka nástrojů jde otevřít", await choose_tool(h, "Značky"))
        st = json.loads(await h.ev(STATE))
        ok("nástroj Značky je vybraný", st["tool"] == "mark", str(st["tool"]))
        ok("koláč se NEZOBRAZÍ", not st["pie"], str(st["pie"]))
        ok("ukáže se hláška „Klepni do not“", "Klepni do not" in st["hint"], st["hint"])

        # ťuknutí do not → dialog se znaky
        pt = await h.free_point()
        ok("našlo se místo v notách", bool(pt), str(pt))
        await h.finger_tap(pt["x"], pt["y"])
        await asyncio.sleep(1.0)
        st2 = json.loads(await h.ev(STATE))
        ok("po ťuknutí do not se otevře dialog", st2["dialog"], str(st2))
        ok("dialog nabízí značky (posuvky, ozdoby…)", st2["marks"], str(st2))
        ok("dialog nemá koláč", not st2["pie"], str(st2))

        # vložení posuvky křížku (#) z dialogu
        ok("v dialogu je dlaždice křížku", await h.ev(
            """(() => { const b = [...document.querySelectorAll('.mark-sec .dyn-btn')]
                 .find(x => (x.title || '').includes('křížek'));
               if (!b) return false; const r = b.getBoundingClientRect();
               return {x: r.left + r.width/2, y: r.top + r.height/2}; })()""") is not False, "")
        tile = await h.ev(
            """(() => { const b = [...document.querySelectorAll('.mark-sec .dyn-btn')]
                 .find(x => (x.title || '').includes('křížek'));
               if (!b) return null; const r = b.getBoundingClientRect();
               return {x: r.left + r.width/2, y: r.top + r.height/2}; })()""")
        await press(h, tile)
        await asyncio.sleep(1.0)
        st3 = json.loads(await h.ev(STATE))
        ok("křížek se vložil do not (text značky = klíč 'k')",
           any((t or "").strip().lower() in ("k", "#", "\ue262") for t in st3["items"]), str(st3["items"]))
        ok("dialog se po vložení zavřel", not st3["dialog"], str(st3))

        # --- NOTY: stejné chování (regrese) ---
        ok("nabídka nástrojů jde otevřít znovu", await choose_tool(h, "Noty"))
        st4 = json.loads(await h.ev(STATE))
        ok("u not se taky neukáže koláč", not st4["pie"], str(st4))
        ok("u not se ukáže hláška o vložení", "Klepni do not" in st4["hint"], st4["hint"])

        errs = await h.ev("(window.__errs || []).length")
        ok("žádné chyby v konzoli", errs in (0, None), str(errs))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
