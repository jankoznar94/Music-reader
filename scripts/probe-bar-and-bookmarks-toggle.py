#!/usr/bin/env python3
"""Spodní lišta záložek se schová a ukáže STEJNĚ jako horní lišta.

1. otevře skladbu, přidá záložku → lišta záložek je vidět
2. tap na STŘED not → zmizí horní lišta I lišta záložek
3. tap na STŘED znovu → obě se vrátí
4. se schovanou lištou jde záložka pořád použít? (lišta je pryč, takže ne —
   hlavní je, že se stav drží i po překreslení stránky)
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

STATE = """(() => {
  const bar = document.querySelector('.top-bar');
  const strip = document.querySelector('.bookmark-strip');
  return JSON.stringify({
    barHidden: !!(bar && bar.classList.contains('hidden')),
    strip: !!strip,
    stripBtns: strip ? strip.querySelectorAll('.bookmark-btn').length : 0,
    barBottom: bar ? Math.round(bar.getBoundingClientRect().bottom) : null,
  });
})()"""


async def st(h):
    return json.loads(await h.ev(STATE))


async def main():
    ok = Check()
    pdf = m.make_pdf(6)
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf)
        await asyncio.sleep(0.8)
        # Střed plátna: klepnutí na střed not přepíná lištu (okraje listují).
        c = json.loads(await h.ev(
            "(() => { const r=document.querySelector('.viewer').getBoundingClientRect();"
            " return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2}); })()"))
        x, y = c["x"], c["y"]

        s = await st(h)
        print("start:", s)
        # lišta musí být vidět, jinak by se záložka neměla kam vykreslit
        if s["barHidden"]:
            await h.finger_tap(x, y)
            await asyncio.sleep(0.5)
            s = await st(h)
        ok("horní lišta je vidět", s["barHidden"] is False, str(s))

        # přidat záložku přes panel záložek
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Přidat záložku')); b.click(); return 1; })()")
        await h.wait_for("!!document.querySelector('.jump-panel .jp-input')", 10, "panel záložky")
        await h.set_value(".jump-panel .jp-input", "Coda")
        await h.ev("document.querySelector('.jump-panel .jp-btn.primary').click()")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", 10, "lišta záložek")
        s = await st(h)
        ok("lišta záložek je vidět s lištou", s["strip"] is True and s["stripBtns"] == 1, str(s))

        # tap na střed → schovat obojí
        await h.finger_tap(x, y)
        await asyncio.sleep(0.5)
        s = await st(h)
        ok("tap na střed schová horní lištu", s["barHidden"] is True, str(s))
        ok("tap na střed schová i lištu záložek", s["strip"] is False, str(s))
        ok("záložka zůstala uložená (jen lišta je pryč)", s["stripBtns"] == 0, str(s))

        # tap na střed → vrátit obojí
        await h.finger_tap(x, y)
        await asyncio.sleep(0.5)
        s = await st(h)
        ok("druhý tap vrátí horní lištu", s["barHidden"] is False, str(s))
        ok("druhý tap vrátí i lištu záložek", s["strip"] is True and s["stripBtns"] == 1, str(s))

        # stav se pamatuje i po přechodu na jinou stránku
        await h.finger_tap(x, y)
        await asyncio.sleep(0.4)
        await h.goto(2)
        await asyncio.sleep(0.6)
        s = await st(h)
        ok("schovaná lišta zůstane schovaná i po listování", s["strip"] is False, str(s))
        await h.finger_tap(x, y)
        await asyncio.sleep(0.5)
        s = await st(h)
        ok("po návratu lišty je záložka zpátky", s["strip"] is True and s["stripBtns"] == 1, str(s))

        # v anotačním režimu se lišta vždy ukáže (kvůli východu z režimu)
        await h.finger_tap(x, y)          # schovat
        await asyncio.sleep(0.4)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        s = await st(h)
        ok("vstup do anotace lišty vrátí", s["barHidden"] is False and s["strip"] is True, str(s))
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
