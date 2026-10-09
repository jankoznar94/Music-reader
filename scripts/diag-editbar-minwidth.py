#!/usr/bin/env python3
"""Diagnostika: jak široká musí lišta úprav být, aby se řádky nezlomily.

Na ŽIVÉ liště (žádný klon) nastaví šířku na řadu hodnot a po každé změně
odečte: kolik řádků má hlavní řádek a kolik řádek rámu (počet různých `top`
u dětí) a kde skončí koš. Odpoví na otázku „kolik px potřebuje řádek rámu".

Použití: bash scripts/run-probe-fresh.sh scripts/diag-editbar-minwidth.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


def _load_harness():
    for cand in (
        os.path.expanduser("~/noty-app/cdp-e2e-harness.py"),
        "/home/martin_fabian/noty-app/cdp-e2e-harness.py",
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness = _m.Harness
COLLAPSE = ".ap-collapse"

SWEEP_JS = """(async () => {
  const bar = document.querySelector('.edit-bar');
  if (!bar) return JSON.stringify({bar: false});
  const rows = [...bar.children];
  const info = (w) => ({
    w: Math.round(w),
    rows: rows.map(r => {
      const kids = [...r.children].map(k => Math.round(k.getBoundingClientRect().top));
      const q = r.getBoundingClientRect();
      return {h: Math.round(q.height), lines: new Set(kids).size,
              need: Math.round([...r.children].reduce((a, k) => a + k.getBoundingClientRect().width, 0))};
    }),
  });
  const out = [info(bar.getBoundingClientRect().width)];
  for (const w of [420, 480, 560, 640, 720, 800]) {
    bar.style.width = w + 'px';
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    out.push(info(bar.getBoundingClientRect().width));
  }
  bar.style.width = '';
  await new Promise(r => requestAnimationFrame(r));
  out.push(info(bar.getBoundingClientRect().width));
  return JSON.stringify(out);
})()"""


async def tap(h, sel, hold_ms=70):
    pt = await h.ev("""(() => {
      const sel = %s; const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top) + 1; y <= Math.ceil(r.bottom) - 1; y += 2)
        for (let x = Math.floor(r.left) + 1; x <= Math.ceil(r.right) - 1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(sel) === el))) return [x + 0.5, y + 0.5];
        }
      return null; })()""" % json.dumps(sel))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.5)
    return True


async def panel(h, want):
    if await h.ev("!!document.querySelector(%s[title=%s])" % (json.dumps(COLLAPSE), json.dumps(want))):
        await tap(h, COLLAPSE)


async def free_xy(h):
    return await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const r = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y) => boxes.some(q => q.width > 0 &&
        x > q.left - 26 && x < q.right + 26 && y > q.top - 22 && y < q.bottom + 22);
      for (const fy of [0.34, 0.42, 0.50, 0.58, 0.26]) for (const fx of [0.60, 0.52, 0.44, 0.68, 0.36]) {
        const x = r.left + r.width * fx, y = r.top + r.height * fy;
        if (document.elementFromPoint(x, y) === svg && !near(x, y)) return {x, y};
      } return null; })()""")


async def build(h, w, hh, dsf):
    await h.set_tablet(w, hh, dsf)
    await h.annot_toggle()
    await panel(h, "Sbalit")
    p = await free_xy(h)
    await panel(h, "Rozbalit")
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.getAttribute('title') || '').startsWith('Text'));"
               " if (b) b.click(); return !!b; })()")
    await asyncio.sleep(0.35)
    await panel(h, "Sbalit")
    await h.pen_tap(p["x"], p["y"])
    await asyncio.sleep(0.8)
    await h.set_value(".ti-input", "Andante")
    await tap(h, ".text-input-overlay .jp-btn.primary")
    await asyncio.sleep(1.0)
    await panel(h, "Rozbalit")
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.getAttribute('title') || '').startsWith('Upravit'));"
               " if (b) b.click(); return !!b; })()")
    await asyncio.sleep(0.35)
    await panel(h, "Sbalit")
    await h.pen_tap(p["x"], p["y"])
    await asyncio.sleep(0.9)
    # rámeček zapnout
    if not await h.ev("""(() => { const b = document.querySelector(".edit-bar .eb-btn[title*='ráme']");
      return !!(b && b.classList.contains('on')); })()"""):
        await tap(h, ".edit-bar .eb-btn[title*='ráme']")


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await build(h, 800, 1280, 2)
        print("=== tablet 800: sweep šířky lišty ===")
        for row in json.loads(await h.ev(SWEEP_JS, await_promise=True)):
            print(f"  šířka {row['w']:4}  " + "  ".join(
                f"řádek{i}: v={r['h']} řádků={r['lines']} dětí spolu {r['need']}px"
                for i, r in enumerate(row["rows"])))
        print("\n=== tablet 800: skutečná šířka a rozměry stránky ===")
        print(await h.ev("""(() => {
          const v = document.querySelector('.viewer');
          return JSON.stringify({innerW: innerWidth, viewerW: Math.round(v.getBoundingClientRect().width),
            barRect: Math.round(document.querySelector('.edit-bar').getBoundingClientRect().width)}); })()"""))


if __name__ == "__main__":
    asyncio.run(main())
