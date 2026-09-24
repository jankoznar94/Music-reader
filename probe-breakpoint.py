#!/usr/bin/env python3
"""Kde přesně nastavit breakpoint pro počítadlo v toku?
Pro každou šířku vypíše skutečné pozice levé skupiny, počítadla a pravé skupiny
a kolik zbývá místa, když je počítadlo absolutní na středu."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness = _mod.Harness

M = r"""
(() => {
  const g = s => { const e=document.querySelector(s); if(!e) return null;
    const r=e.getBoundingClientRect();
    return {x:+r.left.toFixed(1), r:+r.right.toFixed(1), w:+r.width.toFixed(1)}; };
  const cnt = document.querySelector('.tb-page-center');
  const cr = cnt.getBoundingClientRect();
  const cs = getComputedStyle(cnt);
  return { winW: window.innerWidth, left: g('.tb-side.left'), right: g('.tb-side.right'),
           counter: { x:+cr.left.toFixed(1), r:+cr.right.toFixed(1), w:+cr.width.toFixed(1) },
           pos: cs.position,
           freeFromCounter: cs.position === 'absolute'
              ? +(Math.min(cr.left - (g('.tb-side.left')||{r:0}).r,
                           (g('.tb-side.right')||{x:0}).x - cr.right)).toFixed(1)
              : null };
})()
"""


async def run():
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.0)
        await h.open_song(pages=6)
        print(f"{'šířka':>7} │ {'levá':>16} │ {'počítadlo':>16} │ {'pravá':>16} │ pos      │ volno")
        for w in (1100, 1000, 900, 860, 820, 800, 760, 700, 660, 640, 620, 560, 480, 430, 390, 360):
            await h.set_tablet(w, 1000, 2)
            await asyncio.sleep(0.7)
            m = await h.ev(M)
            f = lambda d: f"{d['x']:>6}..{d['r']:<6}" if d else "        -     "
            print(f"{m['winW']:>7} │ {f(m['left'])} │ {f(m['counter'])} │ {f(m['right'])} │ "
                  f"{m['pos']:<8} │ {m['freeFromCounter']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
