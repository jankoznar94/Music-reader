#!/usr/bin/env python3
"""Může se v ANOTAČNÍM režimu listovat? (Jan, Oct 2026)

Otázka Jana: „Zkontroluj, jestli je opravdu možné listovat dílem i během
zapnutého Anotačního režimu.“

Kód tvrdí ANO (`onTouchEnd`: klepnutí/swipe, které ZAČALO v okrajovém pruhu,
listuje i v anotaci) — ale anotační panel (`min-width: 220px`, `left: 16px`)
sedí PŘESNĚ v levém okrajovém pruhu (`edgeWidth()` ≈ 70 px). Zóna pro listování
je tedy na levé straně zakrytá ovládacím panelem: klepnutí tam trefí
`isControlTarget()` a NElístuje.

Sonda měří STAV (geometrii i reálné přepnutí stránky), ne kód:
  1. jak široký je okrajový pruh a kde leží anotační panel (překryv v px)
  2. co je pod prstem v levém okrajovém pruhu (elementFromPoint)
  3. klepnutí prstem v levém okrajovém pruhu v anotaci → změní se stránka?
  4. totéž vpravo (panel tam není) → změní se stránka?
  5. swipe z levého okraje v anotaci → změní se stránka?
  6. SWIPE — jediná cesta, kterou panel neblokuje (swipe je v onTouchEnd)
  7. kontrola: totéž v režimu čtení (panel tam není)
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

GEO = r"""
(() => {
  const v = document.querySelector('.viewer').getBoundingClientRect();
  const panel = document.querySelector('.annot-panel');
  const pr = panel ? panel.getBoundingClientRect() : null;
  const cs = getComputedStyle(document.querySelector('.viewer'));
  const edgeW = parseFloat(cs.getPropertyValue('--edge-w')) || null;
  const bar = document.querySelector('.top-bar').getBoundingClientRect();
  return {
    viewer: {left: v.left, width: v.width, top: v.top, height: v.height},
    barBottom: bar.bottom,
    edgeVar: edgeW,
    hintLeft: (() => {
      const el = document.querySelector('.edge-hint.left');
      if (!el) return 'missing';
      const c = getComputedStyle(el);
      return c.display + '/' + c.visibility + '/op' + c.opacity;
    })(),
    panel: pr ? {left: pr.left, right: pr.right, top: pr.top, bottom: pr.bottom,
                 w: pr.width, h: pr.height} : null,
  };
})()
"""

UNDER = r"""
((x, y) => {
  const cls = (el) => el ? (el.className && el.className.baseVal !== undefined
      ? el.className.baseVal : String(el.className)) : null;
  const el = document.elementFromPoint(x, y);
  if (!el) return null;
  const p = el.closest ? el.closest('button, .annot-panel, .annot-layer, .top-bar') : null;
  return {tag: el.tagName, cls: cls(el), control: cls(p)};
})(%s, %s)
"""

PAGE = "document.querySelector('.tb-page').textContent.trim()"


async def run():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pages=6)

        # --- režim čtení (kontrola) ------------------------------------
        g = await h.geo()
        y_free = g["barBottom"] + 300
        left_x = g["viewer"]["left"] + 25
        right_x = g["viewer"]["left"] + g["viewer"]["width"] - 25
        print("VIEWER", json.dumps(g["viewer"]), "barBottom", round(g["barBottom"], 1))

        await h.goto(3)
        before = await h.page_text()
        await h.finger_tap(left_x, y_free)
        ok("čtení: klepnutí v levém okraji listuje", await h.page_text() != before,
           f"{before} -> {await h.page_text()}")

        # --- anotační režim ---------------------------------------------
        await h.annot_toggle()
        await h.goto(3)
        a = await h.geo()
        edge = a["edgeVar"]
        print("EDGE VAR", edge)
        print("PANEL", json.dumps(a["panel"]))
        print("HINT LEFT", a["hintLeft"])

        # 1. překryv panelu a levého okrajového pruhu
        if a["panel"]:
            band_right = a["viewer"]["left"] + edge
            overlap = max(0.0, min(a["panel"]["right"], band_right) - max(a["panel"]["left"],
                                                                      a["viewer"]["left"]))
            ok("levý okrajový pruh NENÍ zakrytý anotačním panelem",
               overlap < 1.0,
               f"pruh do x={band_right:.0f}, panel {a['panel']['left']:.0f}–"
               f"{a['panel']['right']:.0f} → překryv {overlap:.0f} px")

        # 2. co je pod prstem v levém okrajovém pruhu
        u = await h.ev(UNDER % (left_x, y_free))
        print("POD PRSTEM vlevo:", json.dumps(u))
        ok("v levém okrajovém pruhu je vrstva stránky (ne ovládací panel)",
           bool(u) and (u["control"] or "") .find("annot-layer") >= 0, json.dumps(u))

        # 3. klepnutí prstem v levém okraji v anotaci
        before = await h.page_text()
        await h.finger_tap(left_x, y_free)
        ok("anotace: klepnutí v levém okraji listuje", await h.page_text() != before,
           f"{before} -> {await h.page_text()}")

        # 4. klepnutí prstem v pravém okraji v anotaci
        before = await h.page_text()
        await h.finger_tap(right_x, y_free)
        ok("anotace: klepnutí v pravém okraji listuje", await h.page_text() != before,
           f"{before} -> {await h.page_text()}")

        # 5. swipe z levého okraje v anotaci
        before = await h.page_text()
        await h.finger_swipe(left_x, y_free, left_x + 150, y_free)
        ok("anotace: swipe z levého okraje listuje", await h.page_text() != before,
           f"{before} -> {await h.page_text()}")

        # 6. swipe z pravého okraje v anotaci (panel tam nezasahuje)
        before = await h.page_text()
        await h.finger_swipe(right_x, y_free, right_x - 150, y_free)
        ok("anotace: swipe z pravého okraje listuje", await h.page_text() != before,
           f"{before} -> {await h.page_text()}")

        # 7. klepnutí na STŘED v anotaci nesmí listovat (kreslí pero)
        before = await h.page_text()
        await h.finger_tap(a["viewer"]["left"] + a["viewer"]["width"] / 2, y_free)
        ok("anotace: klepnutí uprostřed NElístuje", await h.page_text() == before,
           before)

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
