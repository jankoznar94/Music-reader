#!/usr/bin/env python3
"""Dočíslování stránky s vícetaktovými pomlkami (Skyrim choir part).

Ověřuje, že po pomlce číslování skočí o N taktů (Jan, Nov 2026):
  str. 2: 26,27,28,29(pomlka 6) → 35,42,43,44,45,46 → 47,48,49,50(pomlka 6),56,57 → 58…
Sonda čte NÁHLED dočíslování (barFillPreview), nic neukládá.
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
APP = os.environ.get("APP_URL") or os.environ.get("NOTY_APP")
PDF = os.environ.get("NOTY_PDF", "/tmp/skyrim-choir.pdf")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

# Náhled: čísla po systémech (seskupená podle y).
PREVIEW = """(() => {
  const d = window.__barDev;
  const pv = d && d.barFillPreview && d.barFillPreview.value;
  if (!pv) return JSON.stringify({ ok: false });
  const byY = new Map();
  for (const it of pv.items) {
    const y = Math.round(Number(it.y) / 12);
    if (!byY.has(y)) byY.set(y, []);
    byY.get(y).push({ n: Number(it.text), x: Number(it.x) });
  }
  const sys = [...byY.entries()].sort((a, b) => a[0] - b[0])
    .map(([, arr]) => arr.sort((a, b) => a.x - b.x).map(o => o.n));
  return JSON.stringify({ ok: true, sys, count: pv.items.length });
})()"""


async def fill(h, page_idx):
    await h.ev("(() => { window.__barDev.currentPage.value = " + str(page_idx) + "; return 1; })()")
    await asyncio.sleep(0.6)
    await h.ev("window.__barDev.fillPageAt()", await_promise=True)
    await asyncio.sleep(0.4)
    st = await h.ev(PREVIEW)
    return json.loads(st)


async def main():
    ok = Check()
    async with (Harness(url=APP) if APP else Harness()) as h:
        await h.open()
        await h.open_song(PDF, reset=True)
        await asyncio.sleep(1.0)

        v = await fill(h, 1)          # str. 2 (index 1)
        print("str. 2:", v)
        if not v.get("ok"):
            ok("náhled dočíslování vznikl", False, "barFillPreview je prázdný")
            return ok.report()
        # Skladba je v appce neočíslovaná → čísla začínají od 1; rozhoduje POSUN
        # mezi systémy (pomlky), ne absolutní hodnota. Vytištěné noty mají
        # 26/35/47/58, takže posun = 26 − první spočítané číslo.
        firsts = [s[0] for s in v["sys"]]
        off = 26 - firsts[0]
        shifted = [[n + off for n in sys] for sys in v["sys"]]
        ok("str. 2: první čísla systémů 26 / 35 / 47 / 58",
           [x[0] for x in shifted][:4] == [26, 35, 47, 58], str(shifted))
        ok("str. 2: 2. systém skočí za pomlkou 7 (35 → 42)",
           shifted[1][:2] == [35, 42], str(shifted[1]))
        ok("str. 2: 3. systém 47,48,49,50 a pak 56 (pomlka 6)",
           shifted[2] == [47, 48, 49, 50, 56, 57], str(shifted[2]))
        await h.ev("window.__barDev.barFillPreview.value = null")

        v = await fill(h, 19)         # str. 20
        print("str. 20:", v)
        await h.ev("window.__barDev.barFillPreview.value = null")

        v = await fill(h, 27)         # str. 28 (pomlky 7,8,6)
        print("str. 28:", v)
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
