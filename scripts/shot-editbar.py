#!/usr/bin/env python3
"""Vyfotí lištu úprav na tabletu 800 — vizuální kontrola po opravě šířky.

Použití: bash scripts/run-probe-fresh.sh scripts/shot-editbar.py
"""
import asyncio
import base64
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
OUT = os.environ.get("NOTY_SHOT", os.path.expanduser("~/noty-app/editbar-fix-800.png"))


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
    await asyncio.sleep(0.6)
    return True


async def collapse(h):
    if await h.ev("!!document.querySelector(%s[title='Sbalit'])" % json.dumps(COLLAPSE)):
        await tap(h, COLLAPSE)


async def open_panel(h):
    if await h.ev("!!document.querySelector(%s[title='Rozbalit'])" % json.dumps(COLLAPSE)):
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


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet(800, 1280, 2)
        await h.annot_toggle()
        await collapse(h)

        p = await free_xy(h)
        await open_panel(h)
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.getAttribute('title') || '').startsWith('Text'));"
                   " if (b) b.click(); return !!b; })()")
        await asyncio.sleep(0.35)
        await collapse(h)
        await h.pen_tap(p["x"], p["y"])
        await asyncio.sleep(0.8)
        await h.set_value(".ti-input", "Andante")
        await tap(h, ".text-input-overlay .jp-btn.primary")
        await asyncio.sleep(1.0)

        # vybrat rukou
        await open_panel(h)
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.getAttribute('title') || '').startsWith('Upravit'));"
                   " if (b) b.click(); return !!b; })()")
        await asyncio.sleep(0.35)
        await collapse(h)
        await h.pen_tap(p["x"], p["y"])
        await asyncio.sleep(0.9)

        # rámeček ZAPNOUT (nejširší stav lišty)
        if not await h.ev("""(() => { const b = document.querySelector(".edit-bar .eb-btn[title*='ráme']");
          return !!(b && b.classList.contains('on')); })()"""):
            await tap(h, ".edit-bar .eb-btn[title*='ráme']")

        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open(OUT, "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        st = json.loads(await h.ev("""(() => { const b = document.querySelector('.edit-bar');
          const r = b.getBoundingClientRect(); const cs = getComputedStyle(b);
          const inner = r.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth);
          const t = b.querySelector(".eb-btn[title='Smazat']").getBoundingClientRect();
          const el = document.elementFromPoint(t.left + t.width/2, t.top + t.height/2);
          return JSON.stringify({bar: [Math.round(r.left), Math.round(r.right)], rows: b.children.length,
            innerRight: Math.round(inner), trashRight: Math.round(t.right),
            trashOnScreen: t.right <= window.innerWidth,
            trashClickable: !!(el && el.closest && el.closest(".eb-btn[title='Smazat']") ===
              b.querySelector(".eb-btn[title='Smazat']"))}); })()"""))
        print("snímek:", OUT)
        print("stav lišty:", json.dumps(st, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
