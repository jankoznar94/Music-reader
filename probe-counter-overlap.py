#!/usr/bin/env python3
"""Je překryv počítadla stránek na mobilu způsobený PŘÍRŮSTKEM tlačítka rotace?
Změří stav s rotací i bez ní (tlačítko dočasně schováme) — bez tohoto srovnání
se nedá poznat, zda jde o novou vadu, nebo o stav, který tam byl už dřív.
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check

MEASURE = r"""
(() => {
  const cnt = document.querySelector('.tb-page-center');
  const cr = cnt.getBoundingClientRect();
  const hits = [];
  document.querySelectorAll('.tb-btn').forEach(b => {
    const r = b.getBoundingClientRect();
    if (!(r.right <= cr.left || r.left >= cr.right)) {
      hits.push({ t: (b.title||'').slice(0,20), x:+r.left.toFixed(1), r:+r.right.toFixed(1) });
    }
  });
  return { winW: window.innerWidth, counter: [+cr.left.toFixed(1), +cr.right.toFixed(1)],
           overlaps: hits };
})()
"""


async def run():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pages=6)
        await h.set_tablet(390, 844, 2)
        await asyncio.sleep(1.2)
        with_rot = await h.ev(MEASURE)
        print("  S tlačítkem rotace:  ", json.dumps(with_rot))
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Rotace stránky'); b.style.display='none';"
                   " return true; })()")
        await asyncio.sleep(0.6)
        without = await h.ev(MEASURE)
        print("  Bez tlačítka rotace:", json.dumps(without))
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Rotace stránky'); b.style.display='';"
                   " return true; })()")
        ok("PŘED přidáním rotace se počítadlo NEPŘEKRÝVALO",
           not without["overlaps"], json.dumps(without["overlaps"]))
        # Regrese z přidání tlačítka rotace: na 390 px se pravá skupina roztáhla
        # pod počítadlo stránek (naměřeno 216,6 vs 217,7 = klepnutí na počítadlo
        # trefilo Anotaci). Po zúžení v @media (max-width: 430px) musí být volno.
        ok("S rotací se počítadlo NEPŘEKRÝVÁ (regrese opravena)",
           not with_rot["overlaps"], json.dumps(with_rot["overlaps"]))
        gap = (with_rot["overlaps"][0]["x"] if with_rot["overlaps"] else None)
        print(f"  počítadlo {with_rot['counter']} — mezera vpravo "
              f"{gap if gap else 'OK (žádný překryv)'}")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
