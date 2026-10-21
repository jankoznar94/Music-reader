#!/usr/bin/env python3
"""Režim Ruka: zvýrazňovač jde chytit a posunout PRSTEM, dlaň nic neodtáhne.

Jan (Oct 2026): „aby se i obdélník zvýrazňovače dal uchopit jako objekt a posunout" —
na tabletu to dělá prstem, a „Jen pero" (dlaňová ochrana) dotyk v režimu Ruka
blokoval úplně. Sonda ověřuje:
  1. prst klepne na pás zvýraznění → výběrový rámeček
  2. prst ho táhne → čtyřúhelník se posune a posun zůstane po překreslení
  3. dlaň (poloměr 70) ho nevybere ani neposune
  4. bezprostředně po tahu perem dotyk nechytá (pero právě píše)
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
TOOL_JS = ("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
           ".find(x => (x.title || '').startsWith(%s)); if (b) { b.click(); return 'ok'; }"
           " return 'missing'; })()")
HL_D = """(() => { const p = document.querySelector('.annot-layer path.hl');
  return p ? p.getAttribute('d') : null; })()"""
SEL = "!!document.querySelector('.annot-selected rect')"


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(m.make_pdf(4))
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        free = await h.free_point()
        x, y = free["x"], free["y"]

        await h.ev(TOOL_JS % json.dumps("Zvýraznění"))
        await h.pen_tap(x - 70, y + 14)
        await h.pen_tap(x - 70, y - 14)
        await h.pen_tap(x + 70, y)
        await asyncio.sleep(0.5)
        d0 = await h.ev(HL_D)
        ok("zvýraznění vzniklo", bool(d0), str(d0)[:60])

        await h.ev(TOOL_JS % json.dumps("Upravit"))
        await asyncio.sleep(0.4)

        # 3) dlaň na pás: nesmí vybrat
        await h.palm_tap(x, y)
        ok("dlaň zvýraznění nevybere", (await h.ev(SEL)) is False)

        # 1) prst klepne
        await h.finger_tap(x, y)
        ok("prst zvýraznění vybere", (await h.ev(SEL)) is True)

        # 2) prst táhne
        await h.touch("touchStart", [(x, y, 12)])
        for i in range(1, 13):
            await h.touch("touchMove", [(x + 5 * i, y + 2 * i, 12)])
            await asyncio.sleep(0.02)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.8)
        d1 = await h.ev(HL_D)
        print("evLog:", json.loads(await h.ev("JSON.stringify(window.__navdbg())"))["evLog"][-10:])
        ok("prst zvýraznění posune", d1 != d0, f"{str(d0)[:30]} -> {str(d1)[:30]}")

        await h.goto(2)
        await asyncio.sleep(0.5)
        await h.goto(1)
        await asyncio.sleep(0.8)
        d2 = await h.ev(HL_D)
        ok("posun zůstal po překreslení stránky", d2 == d1, str(d2)[:60])

        # 4) hned po tahu perem dotyk nechytá
        await h.pen_stroke(x - 40, y + 60, x + 40, y + 60)
        await h.finger_tap(x, y)
        ok("těsně po tahu perem prst nechytá (pero píše)", (await h.ev(SEL)) is False)
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
