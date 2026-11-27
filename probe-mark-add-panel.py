#!/usr/bin/env python3
"""Přidání značky: okno Značek při výběru místa zmizí a po vložení se vrátí.

Jan (27. 11. 2026): „Když kliknu na Přidat značku, mělo by zmizet okno se
značkami, protože překáží. Po vložení se může zase zobrazit.“

Ověřuje:
  1. otevřené okno Značek → „Přidat značku“ okno SCHOVÁ (jinak se přes noty
     nedá trefit), pick režim běží a je vidět zavírací ✕,
  2. ťuknutí do not okno Vrátí i s polem pro text (jinak by nebylo kam napsat),
  3. Uložit značku zapíše a okno zůstane otevřené,
  4. zrušení přes ✕ okno taky vrátí (nezůstane schované napořád).
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

CLICK_BY_TEXT = """(() => {
  const el = [...document.querySelectorAll(%s)].find(x => x.textContent.trim() === %s);
  if (!el) return false;
  el.click();
  return true;
})()"""


async def click_text(h, sel, text):
    return await h.ev(CLICK_BY_TEXT % (json.dumps(sel), json.dumps(text)))


async def boot(h):
    """Po reloadu se dostat zpátky do prohlížeče stejné skladby."""
    await h.wait_for("!!document.querySelector('.tb-page') || !!document.querySelector('.song-name')",
                     timeout=60, label="app after boot")
    if not await h.ev("!!document.querySelector('.tb-page')"):
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=20, label="songs")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=60, label="viewer")
    await h.wait_for("!document.querySelector('.viewer-loading')", timeout=60, label="render")
    await asyncio.sleep(1.0)


async def main():
    ok = Check()
    async with Harness(APP) as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pages=6, reset=True)     # čistá DB — žádné značky z minula
        # Lišta musí být VIDĚT, jinak nemá co mizet (výchozí stav má horní lištu
        # schovanou a test by prošel i s rozbitým skrýváním).
        await h.ev("localStorage.setItem('topbarHidden', '0')")
        await h.ev("location.reload()")
        await asyncio.sleep(4)
        await boot(h)
        ok("horní lišta je na začátku vidět",
           not await h.ev("document.querySelector('.top-bar').classList.contains('hidden')"), "")

        await h.ev("window.__barDev.openMarks()")
        await h.wait_for("!!document.querySelector('.marks-panel')", timeout=10, label="marks panel")
        ok("okno Značek je otevřené", True)

        # 1) Přidat značku → okno zmizí
        ok("tlačítko Přidat značku existuje", await click_text(h, ".marks-panel .jp-btn", "Přidat značku"))
        await asyncio.sleep(0.6)
        st = await h.ev("""(() => JSON.stringify({
          panel: !!document.querySelector('.marks-panel'),
          pick: !!(window.__barDev && window.__barDev.mkInsertAt),
          close: !!document.querySelector('.overlay-close'),
          bar: document.querySelector('.top-bar').classList.contains('hidden'),
          strip: !!document.querySelector('.bottom-strip'),
          toast: (document.querySelector('.viewer-toast') || {}).textContent || '',
        }))()""")
        st = json.loads(st)
        ok("okno Značek po ťuknutí na Přidat značku zmizí", not st["panel"], str(st))
        ok("horní lišta při vkládání zmizí", st["bar"], f"hidden={st['bar']}")
        ok("spodní lišta (záložky/značky) zmizí taky", not st["strip"], str(st["strip"]))
        ok("je vidět zavírací ✕ (vkládání jde zrušit)", st["close"], str(st["close"]))
        ok("hláška vyzývá k ťuknutí do not", "notách" in st["toast"].lower(), st["toast"])

        # 2) ťuknutí do not → okno se vrátí s polem pro text
        pt = await h.free_point()
        ok("našlo se místo v notách pro ťuknutí", bool(pt), str(pt))
        await h.finger_tap(pt["x"], pt["y"])
        await asyncio.sleep(0.8)
        st2 = json.loads(await h.ev("""(() => JSON.stringify({
          panel: !!document.querySelector('.marks-panel'),
          input: !!document.querySelector('.marks-new input'),
          focused: document.activeElement === document.querySelector('.marks-new input'),
          bar: document.querySelector('.top-bar').classList.contains('hidden'),
          at: !!(window.__barDev && window.__barDev.mkInsertAt && window.__barDev.mkInsertAt.value),
        }))()"""))
        ok("po ťuknutí do not se okno vrátí", st2["panel"], str(st2))
        ok("po ťuknutí do not se vrátí i horní lišta", not st2["bar"], f"hidden={st2['bar']}")
        ok("je v něm pole pro text i tlačítko Uložit", st2["input"], str(st2))
        ok("příprava vložení drží místo", st2["at"], str(st2))

        # 3) Uložit → značka existuje a okno zůstává
        await h.set_value(".marks-new input", "K")
        await asyncio.sleep(0.2)
        ok("tlačítko Uložit existuje", await click_text(h, ".marks-new .jp-btn", "Uložit"))
        await asyncio.sleep(1.0)
        st3 = json.loads(await h.ev("""(() => JSON.stringify({
          panel: !!document.querySelector('.marks-panel'),
          marks: window.__barDev.marks.value.map(x => x.text),
          list: [...document.querySelectorAll('.marks-panel .mk-label')].map(x => x.textContent.trim()),
        }))()"""))
        ok("značka se uložila", st3["marks"] == ["K"], str(st3["marks"]))
        ok("po uložení okno zůstává otevřené", st3["panel"], str(st3))

        # 4) zrušení přes ✕ okno vrátí
        ok("znovu Přidat značku", await click_text(h, ".marks-panel .jp-btn", "Přidat značku"))
        await asyncio.sleep(0.6)
        ok("okno zase zmizelo", not await h.ev("!!document.querySelector('.marks-panel')"), "")
        await h.click(".overlay-close")
        await asyncio.sleep(0.6)
        st4 = json.loads(await h.ev("""(() => JSON.stringify({
          panel: !!document.querySelector('.marks-panel'),
          pickRow: !!document.querySelector('.marks-new input'),
          close: !!document.querySelector('.overlay-close'),
        }))()"""))
        ok("zrušení přes ✕ okno vrátí", st4["panel"], str(st4))
        ok("rozpracované vkládání je zrušené", not st4["pickRow"], str(st4))

        # 5) stejné pravidlo pro vkládání skoku (umisťování tlačítka)
        await h.ev("window.__barDev.openMarks()")   # zavřít okno Značek
        await asyncio.sleep(0.5)
        await h.ev("window.__barDev.startJumpPlace()")
        await asyncio.sleep(0.6)
        ok("při umisťování skoku zmizí horní lišta",
           await h.ev("document.querySelector('.top-bar').classList.contains('hidden')"), "")
        await h.ev("window.__barDev.startJumpPlace()")   # zrušit
        await asyncio.sleep(0.6)
        ok("po zrušení umisťování se lišta vrátí",
           not await h.ev("document.querySelector('.top-bar').classList.contains('hidden')"), "")

        errs = await h.ev("(window.__errs || []).length")
        ok("žádné chyby v konzoli", errs in (0, None), str(errs))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
