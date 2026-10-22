#!/usr/bin/env python3
"""Zvýrazňovač jako uchopitelný objekt: dá se v režimu Ruka chytit a posunout?

1. nakreslí zvýraznění 3 klepnutími perem
2. přepne nástroj Upravit (ruka)
3. chytne pero DOPROSTŘED pásu a táhne
4. měří, jestli se objevil výběrový rámeček a jestli se čtyřúhelník posunul
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

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

HL_INFO = """(() => {
  const p = document.querySelector('.annot-layer path.hl');
  if (!p) return {found: false};
  return {found: true, d: p.getAttribute('d')};
})()"""


async def main():
    ok = Check()
    pdf = m.make_pdf(4)
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        free = await h.free_point()
        print("free point:", free)
        x, y = free["x"], free["y"]

        print("tool highlighter:", await h.ev(TOOL_JS % json.dumps("Zvýraznění")))
        await asyncio.sleep(0.3)
        await h.pen_tap(x - 70, y + 14)
        await h.pen_tap(x - 70, y - 14)
        await h.pen_tap(x + 70, y)
        await asyncio.sleep(0.5)

        info0 = json.loads(await h.ev("JSON.stringify(%s)" % HL_INFO))
        ok("zvýraznění vzniklo", info0.get("found") is True, str(info0)[:120])
        if not info0.get("found"):
            return ok.report()

        print("tool edit:", await h.ev(TOOL_JS % json.dumps("Upravit")))
        await asyncio.sleep(0.4)

        # klepnutí doprostřed pásu → má se objevit výběrový rámeček
        await h.pen_tap(x, y)
        await asyncio.sleep(0.5)
        sel = await h.ev("!!document.querySelector('.annot-selected')")
        ok("klepnutí na pás zvýraznění ho vybere", sel is True, f"selected={sel}")

        # tažení
        await h.pen_down(x, y)
        for i in range(1, 11):
            await h.pen_move(x + 6 * i, y + 3 * i)
            await asyncio.sleep(0.02)
        await h.pen_up(x + 60, y + 30)
        await asyncio.sleep(0.8)

        info1 = json.loads(await h.ev("JSON.stringify(%s)" % HL_INFO))
        ok("čtyřúhelník se posunul", info1.get("d") != info0.get("d"),
           f"{str(info0.get('d'))[:40]} -> {str(info1.get('d'))[:40]}")

        # a přežije to i překreslení stránky (uloženo, ne jen v paměti)
        await h.goto(2)
        await asyncio.sleep(0.6)
        await h.goto(1)
        await asyncio.sleep(0.8)
        info2 = json.loads(await h.ev("JSON.stringify(%s)" % HL_INFO))
        ok("posun zůstal po otočení stránky", info2.get("d") == info1.get("d"),
           f"{str(info2.get('d'))[:40]}")

        await h.ev("(() => { const a = window.__navdbg && window.__navdbg();"
                   " return a ? JSON.stringify(a) : 'none'; })()")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
