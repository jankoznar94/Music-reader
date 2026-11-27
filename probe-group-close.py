#!/usr/bin/env python3
"""Tlačítko skupiny na hlavní liště: druhé ťuknutí zavře VŠE (Jan, 27. 11. 2026).

Původní chyba: otevřel se zoom z nabídky skupiny „Zobrazení“, tlačítko zůstalo
zvýrazněné, ale další ťuknutí na něj otevřelo nabídku ZNOVU místo zavření —
zavřít se dalo až třetím ťuknutím.

Ověřuje pro obě skupiny (Zobrazení i Orientace v notách):
  * 1. ťuknutí = nabídka, tlačítko svítí,
  * volba v nabídce = okno otevřené, nabídka zavřená, tlačítko pořád svítí
    (okno skupiny je otevřené),
  * 2. ťuknutí na tlačítko = okno I nabídka zavřené, tlačítko nesvítí,
  * 3. ťuknutí = nabídka zase otevře (tlačítko je použitelné, nezůstane mrtvé).
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

BTN = """(() => {
  const b = [...document.querySelectorAll('.tb-btn')].find(x => (x.title || '').startsWith(%s));
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2, on: b.classList.contains('on') };
})()"""

STATE = """(() => JSON.stringify({
  gm: !!document.querySelector('.gm-col'),
  zoom: !!document.querySelector('[data-panel="zoom"]'),
  rot: !!document.querySelector('[data-panel="rot"]'),
  prefs: !!document.querySelector('[data-panel="prefs"]'),
  marks: !!document.querySelector('.marks-panel'),
  bookmark: !!document.querySelector('.bookmark-panel'),
  btnView: [...document.querySelectorAll('.tb-btn')].filter(x => (x.title || '').startsWith('Zobrazení'))
    .map(x => x.classList.contains('on')),
  btnNav: [...document.querySelectorAll('.tb-btn')].filter(x => (x.title || '').startsWith('Záložky, značky'))
    .map(x => x.classList.contains('on')),
}))()"""

ITEM = """(() => {
  const el = [...document.querySelectorAll('.gm-item')].find(x => x.title === %s);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
})()"""


async def tap(h, pt):
    await h.finger_tap(pt["x"], pt["y"])


async def run_group(h, ok, title, item_title, panel_key, label):
    b = await h.ev(BTN % json.dumps(title))
    ok(f"[{label}] tlačítko je na liště", bool(b), str(b))
    if not b:
        return
    await tap(h, b)
    st = json.loads(await h.ev(STATE))
    ok(f"[{label}] 1. ťuknutí otevře nabídku a tlačítko svítí",
       st["gm"] and b["on"] is False or st["gm"], str(st))

    it = await h.ev(ITEM % json.dumps(item_title))
    ok(f"[{label}] v nabídce je „{item_title}“", bool(it), str(it))
    if not it:
        return
    await tap(h, it)
    st = json.loads(await h.ev(STATE))
    b2 = await h.ev(BTN % json.dumps(title))
    ok(f"[{label}] volba otevře okno a zavře nabídku", st[panel_key] and not st["gm"], str(st))
    ok(f"[{label}] tlačítko u otevřeného okna svítí", bool(b2 and b2["on"]), str(b2))

    await tap(h, b2)
    st = json.loads(await h.ev(STATE))
    b3 = await h.ev(BTN % json.dumps(title))
    ok(f"[{label}] 2. ťuknutí zavře okno I nabídku", not st[panel_key] and not st["gm"], str(st))
    ok(f"[{label}] tlačítko po zavření nesvítí", bool(b3 and not b3["on"]), str(b3))

    await tap(h, b3)
    st = json.loads(await h.ev(STATE))
    ok(f"[{label}] 3. ťuknutí nabídku znovu otevře (tlačítko není mrtvé)", st["gm"], str(st))
    # ukliď: ťuknutí na stejné tlačítko nabídku zavře
    b4 = await h.ev(BTN % json.dumps(title))
    await tap(h, b4)
    st = json.loads(await h.ev(STATE))
    ok(f"[{label}] úklid: nabídka zavřená", not st["gm"], str(st))


async def main():
    ok = Check()
    async with Harness(APP) as h:
        await h.open()
        await h.set_tablet()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", label="songs")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="viewer")
        await asyncio.sleep(1.2)

        await run_group(h, ok, "Zobrazení", "Zvětšení", "zoom", "Zobrazení / Zvětšení")
        await run_group(h, ok, "Zobrazení", "Rotace", "rot", "Zobrazení / Rotace")
        await run_group(h, ok, "Záložky, značky", "Značky", "marks", "Orientace / Značky")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
