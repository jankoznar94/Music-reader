#!/usr/bin/env python3
"""Ověření, že gesta dělají to, co mají (počet prstů rozhoduje).

Jan (Sep 2026): „Zoom a přesun pozice bude pomocí gesta dvěma prsty, rotace
bude pomocí gesta třema prsty." — tohle NAHRAZUJE starý model, kdy jedno
dvouprsté gesto dělalo obojí a režim se hádal z poměru pohybu.

Co se ověřuje (stav, ne kód):
  1. tlačítko rotace v liště existuje a nese aktuální úhel
  2. mřížka (.rot-grid) je vidět JEN s otevřenou nabídkou rotace
  3. DVĚMA prsty: zoom se změní, posun se změní, rotace se NEZMĚNÍ
  4. TŘEMI prsty: rotace se změní, zoom a posun se NEZMĚNÍ (rigidní rotace)
  5. zoom a rotace se navzájem vylučují (otevření jednoho zavře druhé)
  6. tři prsty fungují i BEZ otevřené nabídky (režim neurčuje nabídka, ale počet prstů)
"""
import asyncio
import importlib.util
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check

READ_STATE = r"""
(() => {
  const stage = document.querySelector('.stage');
  const rotor = document.querySelector('.rotor');
  const ms = new DOMMatrix(getComputedStyle(stage).transform);
  const mr = new DOMMatrix(getComputedStyle(rotor).transform);
  const tb = [...document.querySelectorAll('.tb-btn')].find(b => (b.title||'') === 'Rotace stránky');
  return {
    zoomFit: +Math.hypot(ms.a, ms.b).toFixed(4),
    panX: +ms.e.toFixed(2),
    panY: +ms.f.toFixed(2),
    deg: +(Math.atan2(mr.b, mr.a) * 180 / Math.PI).toFixed(2),
    grid: !!document.querySelector('.rot-grid'),
    rotBtn: !!tb,
    rotBtnText: tb ? tb.textContent.trim() : null,
  };
})()
"""


async def panel_open(h, title):
    """Otevři nabídku klikem na její tlačítko v horní liště (reálný klik myší
    na skutečný prvek — panel se ovládá stejně jako to dělá uživatel)."""
    n = await h.ev(
        "(() => { const b=[...document.querySelectorAll('.tb-btn')]"
        ".find(x=>(x.title||'')===%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title))
    await asyncio.sleep(0.5)
    return n == 1


async def panel_close_all(h):
    await h.ev("(() => { document.querySelectorAll('.tb-btn.on').forEach(b=>b.click()); return true; })()")
    await asyncio.sleep(0.4)


async def rot_gesture(h, deg=40, radius=150):
    """TŘI prsty po KRUŽNICI (rozptyly konstantní) → čistá rotace, žádný zoom.
    Dvěma prsty by to zoomovalo — režim určuje počet prstů, ne pohyb.
    Tři prsty rozložené po 120°: rotace celé trojice o `deg`."""
    g = await h.geo()
    cx = g["left"] + g["w"] / 2
    cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

    def pts(a0):
        return [(cx + radius * math.cos(a0 + k * 2 * math.pi / 3),
                 cy + radius * math.sin(a0 + k * 2 * math.pi / 3), 12) for k in range(3)]

    await h.touch("touchStart", pts(0.0))
    steps = 40
    for i in range(1, steps + 1):
        await h.touch("touchMove", pts(math.radians(deg * i / steps)))
        await asyncio.sleep(0.015)
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.6)


async def pinch_gesture(h, factor=1.35, move=60):
    """DVA prsty od sebe (zoom) + posun středu → zoom a změna pozice.
    Rotace se u dvou prstů dělat NESMÍ (ta patří třem prstům)."""
    g = await h.geo()
    cx = g["left"] + g["w"] / 2
    cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2
    r0 = 100
    await h.touch("touchStart", [(cx - r0, cy, 12), (cx + r0, cy, 12)])
    for i in range(1, 11):
        t = i / 10
        r = r0 * (1 + (factor - 1) * t)
        dx = move * t
        dy = (move * 0.5) * t
        await h.touch("touchMove", [(cx - r + dx, cy + dy, 12), (cx + r + dx, cy + dy, 12)])
        await asyncio.sleep(0.02)
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.2)


def norm180(x):
    y = (x + 180) % 360 - 180
    return 180 if y == -180 else y


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.0)
        await h.open_song(pages=6)
        await asyncio.sleep(1.0)

        # ---------- 1) tlačítko rotace + mřížka jen u rotace ----------
        s = await h.ev(READ_STATE)
        ok("tlačítko ROTACE je v liště", s["rotBtn"], json.dumps(s)[:120])
        ok("tlačítko nese aktuální úhel (0°)", s["rotBtnText"] == "0°", str(s["rotBtnText"]))
        ok("mřížka se ve výchozím stavu nezobrazuje", not s["grid"], f"grid={s['grid']}")

        ok("nabídka ZOOMU se otevřela", await panel_open(h, "Zvětšení a posun"))
        s = await h.ev(READ_STATE)
        ok("u ZOOMU se mřížka NEzobrazuje", not s["grid"], f"grid={s['grid']}")

        ok("nabídka ROTACE se otevřela", await panel_open(h, "Rotace stránky"))
        s = await h.ev(READ_STATE)
        ok("u ROTACE se mřížka zobrazuje", s["grid"], f"grid={s['grid']}")
        ok("otevřením ROTACE se ZOOM zavřel (vylučují se)",
           not (await h.ev("!!document.querySelector('.zoom-panel:not(.rot-panel)')")),
           "zoom panel")

        # ---------- 2) DVĚMA prsty = zoom + posun (rotace se nesmí hnout) ----------
        await panel_close_all(h)
        await asyncio.sleep(0.4)
        before = await h.ev(READ_STATE)
        await pinch_gesture(h, factor=1.35, move=70)
        after = await h.ev(READ_STATE)
        print(f"  2 PRSTY: {json.dumps(before)} -> {json.dumps(after)}")
        ok("2 prsty: měřítko se ZVĚTŠILO", after["zoomFit"] > before["zoomFit"] + 0.05,
           f"{before['zoomFit']} -> {after['zoomFit']}")
        ok("2 prsty: posun se pohnul",
           abs(after["panX"] - before["panX"]) > 5 or abs(after["panY"] - before["panY"]) > 5,
           f"pan {before['panX']},{before['panY']} -> {after['panX']},{after['panY']}")
        ok("2 prsty: úhel se NEPOHNL",
           abs(norm180(after["deg"] - before["deg"])) < 1.5,
           f"{before['deg']}° -> {after['deg']}°")

        # ---------- 3) TŘEMI prsty = rotace (zoom/posun se nesmí hnout) ----------
        before = await h.ev(READ_STATE)
        await rot_gesture(h, deg=40)
        after = await h.ev(READ_STATE)
        print(f"  3 PRSTY: {json.dumps(before)} -> {json.dumps(after)}")
        turned = norm180(after["deg"] - before["deg"])
        ok("3 prsty: gesto otočilo stránku (~40°)", abs(turned - 40) < 8, f"Δ {turned:.1f}°")
        ok("3 prsty: měřítko se NEPOHNL O (rigidní rotace)",
           abs(after["zoomFit"] - before["zoomFit"]) < 0.01,
           f"{before['zoomFit']} -> {after['zoomFit']}")
        ok("3 prsty: posun se NEPOHNL",
           abs(after["panX"] - before["panX"]) < 1 and abs(after["panY"] - before["panY"]) < 1,
           f"pan {before['panX']},{before['panY']} -> {after['panX']},{after['panY']}")
        ok("3 prsty: tlačítko v liště hlásí nový úhel",
           (await h.ev(READ_STATE))["rotBtnText"] not in ("0°", None),
           str((await h.ev(READ_STATE))["rotBtnText"]))

        # ---------- 4) tři prsty fungují i BEZ otevřené nabídky ----------
        await panel_close_all(h)
        await asyncio.sleep(0.4)
        s = await h.ev(READ_STATE)
        ok("se zavřenými nabídkami mřížka zmizela", not s["grid"], f"grid={s['grid']}")
        ok("se zavřenými nabídkami není otevřený žádný panel ZOOM/ROTACE",
           not (await h.ev("!!document.querySelector('.zoom-panel')")), "panel")
        before = await h.ev(READ_STATE)
        await rot_gesture(h, deg=35)
        after = await h.ev(READ_STATE)
        turned = norm180(after["deg"] - before["deg"])
        ok("BEZ nabídky: tři prsty rotují i nadále (režim = počet prstů, ne nabídka)",
           abs(turned - 35) < 8, f"Δ {turned:.1f}°")

        # ---------- 5) vylučování nabídek zoom/rotace ----------
        ok("nabídka ZOOMU se otevřela", await panel_open(h, "Zvětšení a posun"))
        ok("nabídka ROTACE se otevřela", await panel_open(h, "Rotace stránky"))
        s = await h.ev(READ_STATE)
        ok("u ROTACE se mřížka zobrazuje", s["grid"], f"grid={s['grid']}")
        ok("otevřením ROTACE se ZOOM zavřel (vylučují se)",
           not (await h.ev("!!document.querySelector('.zoom-panel:not(.rot-panel)')")),
           "zoom panel")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
