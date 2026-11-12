#!/usr/bin/env python3
"""Označený prvek se hýbe odkudkoli; prosté ťuknutí označení zruší.

Jan (Nov 2026): „po označení prvku chci, aby se dalo s prvkem hýbat, ať
uživatel hýbe prstem kdekoliv… označení se zruší po jednoduchém tapnutí,
nebo vypnutím anotačního módu.“

Ověřuje se stav, ne kód:
  1. ťuk na tah v režimu Ruka prvek OZNAČÍ
  2. stisk 60+ px VEDLE prvku a tažení prvkem hýbe (delta odpovídá pohybu)
  3. přesun je v historii (Zpět ho vrátí)
  4. prosté ťuknutí vedle (bez pohybu) označení ZRUŠÍ a prvek neposune
  5. vypnutí anotačního módu označení taky zruší
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

APP = os.environ.get("APP_URL") or os.environ.get("NOTY_APP")

FIRST = r"""(() => {
  const d = window.__barDev;
  const it = d.annotations.value.items[d.annotations.value.items.length - 1];
  if (!it || !it.points) return null;
  return { x: it.points[0].x, y: it.points[0].y, n: it.points.length };
})()"""

EDITING = "(() => window.__barDev.editingId.value)()"


async def pick_tool(h, title_prefix):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll('.annot-panel .ap-tool')]"
        ".find(x=>(x.title||'').startsWith(%s)); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title_prefix))


async def safe_point(h, half=90):
    return await h.ev(
        "(() => { const p=document.querySelector('.annot-panel');"
        " const pr = p ? p.getBoundingClientRect().right : 0;"
        " const v = document.querySelector('.viewer').getBoundingClientRect();"
        " const lo = Math.max(v.left + %d + 10, pr + %d + 10);"
        " const hi = v.right - %d - 10;"
        " for (let frac = 0.45; frac <= 0.85; frac += 0.05) { const y = v.top + v.height*frac;"
        "   for (let x = lo; x <= hi; x += 10) {"
        "     const el = document.elementFromPoint(x, y);"
        "     if (el && el.classList && el.classList.contains('annot-layer'))"
        "       return {x, y}; } }"
        " return null; })()" % (half, half, half))


async def main():
    ok = Check()
    async with (Harness(url=APP) if APP else Harness()) as h:
        await h.open()
        await h.open_song(reset=True)
        await h.annot_toggle()

        # tah tužkou jako cíl přesunu
        await pick_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        pt = await safe_point(h)
        await h.pen_stroke(pt["x"] - 40, pt["y"], pt["x"] + 40, pt["y"])
        await asyncio.sleep(0.3)
        p0 = await h.ev(FIRST)
        ok("tah vznikl", p0 and p0["n"] > 2, str(p0))

        # --- 1) označení ťukem ---------------------------------------------
        await pick_tool(h, "Upravit")
        await asyncio.sleep(0.3)
        await h.pen_tap(pt["x"], pt["y"])
        await asyncio.sleep(0.3)
        ok("ťuk na tah ho označí", await h.ev(EDITING) is not None, str(await h.ev(EDITING)))

        # --- 2) tah VEDLE prvku hýbe prvkem ---------------------------------
        away = {"x": pt["x"] + 80, "y": pt["y"] + 90}
        await h.pen_down(away["x"], away["y"])
        for i in range(1, 6):
            await h.pen_move(away["x"] + 6 * i, away["y"] + 4 * i)
            await asyncio.sleep(0.02)
        await h.pen_up(away["x"] + 30, away["y"] + 20)
        await asyncio.sleep(0.5)
        p1 = await h.ev(FIRST)
        ok("tah VEDLE prvku s ním hýbe", p1 and (p1["x"] > p0["x"] + 3 and p1["y"] > p0["y"] + 3),
           f'{p0} -> {p1}')

        # --- 3) přesun je v historii ---------------------------------------
        before = await h.ev(EDITING)
        box = await h.ev(
            "(() => { const b=[...document.querySelectorAll('.annot-panel .ap-tool')]"
            ".find(x=>(x.title||'')==='Zpět'); const r=b.getBoundingClientRect();"
            " return {x:r.left+r.width/2, y:r.top+r.height/2}; })()")
        await h.finger_tap(box["x"], box["y"])
        await asyncio.sleep(0.5)
        p2 = await h.ev(FIRST)
        ok("Zpět vrátí přesun", p2 and abs(p2["x"] - p0["x"]) < 1.5 and abs(p2["y"] - p0["y"]) < 1.5,
           f'{p1} -> {p2}')
        ok("označení po Zpět zůstává", await h.ev(EDITING) == before, str(await h.ev(EDITING)))

        # --- 4) prosté ťuknutí vedle označení zruší --------------------------
        tapat = {"x": pt["x"] + 140, "y": pt["y"] + 150}
        await h.pen_tap(tapat["x"], tapat["y"])
        await asyncio.sleep(0.4)
        p3 = await h.ev(FIRST)
        ok("ťuknutí vedle označení ZRUŠÍ", await h.ev(EDITING) is None, str(await h.ev(EDITING)))
        ok("ťuknutí vedle prvkem neposune",
           p3 and abs(p3["x"] - p0["x"]) < 1.5 and abs(p3["y"] - p0["y"]) < 1.5, f'{p0} -> {p3}')

        # --- 5) vypnutí anotačního módu -------------------------------------
        await h.pen_tap(pt["x"], pt["y"])
        await asyncio.sleep(0.3)
        ok("znovu označeno", await h.ev(EDITING) is not None)
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        ok("vypnutí anotací označení zruší", await h.ev(EDITING) is None, str(await h.ev(EDITING)))

        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
