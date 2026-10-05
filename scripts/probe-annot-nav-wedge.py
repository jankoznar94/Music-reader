#!/usr/bin/env python3
"""Sonda: zasekne se listování po anotační AKCI? (Jan, Oct 2026)

„Opravdu se občas stane, že při anotačním režimu přestane fungovat listování
stránek. Funguje to, ale prostě po určité době, nebo akci, se to sekne a pak už
listovat nejde. Jen po vypnutí anotačního režimu."

HYPOTÉZA (z čtení Prohlizec.vue):
  blockedNav() vypne listování, dokud je `_activePointerId !== null`.
  `_activePointerId` se nastaví v onLayerDown a uvolní v onLayerUp — ale
  onLayerUp u nástrojů text/dynamika/značka skončí cestou
      it.pending = true; editingAnnotationId.value = it.id; return;
  Zbytek onLayerUp (kde se pointer uvolňuje) se přeskočí. Pointerup TÉHOŽ
  pointeru pak spadne na `if (!activeItem.value) return;` → pointer se
  NIKDY neuvolní. Od té chvíle je listování mrtvé, dokud uživatel nevypne
  anotační režim (watch(annotMode) → endEdit, ale POZOR: endEdit jen
  editingId, pointer taky neuklidí — proto pomůže jen vypnutí režimu, které
  resetuje i `_touchStart` v onTouchStart přes blockedNav? ne…).

  Reálný mechanismus „pomůže jen vypnutí režimu": `_activePointerId` zůstane
  nastavený natrvalo. blockedNav() je pak true navždy a žádný touchstart
  nezačne tah. Vypnutí anotačního režimu pointer NEuklidí — takže pokud
  hypotéza platí, musí zůstat zaseknuté i po vypnutí. Proto sonda měří i to.

Sonda po každé akci zkusí prstem na okraji otočit stránku.

    NOTY_CDP=http://127.0.0.1:9225 python3 scripts/probe-annot-nav-wedge.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9225")


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
Harness, Check = _m.Harness, _m.Check

ANNOT_TITLE = "Anotace / listování"

GEO = r"""
(() => {
  const r = document.querySelector('.stage.backdrop').getBoundingClientRect();
  return { left: r.left, top: r.top, width: r.width, height: r.height };
})()
"""


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def page_num(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    return t.split(" ")[0].split("/")[0].strip()


async def swipe_next(h):
    g = await h.ev(GEO)
    y = g["top"] + g["height"] * 0.5
    x0 = g["left"] + g["width"] - 18
    x1 = g["left"] + g["width"] * 0.55
    before = await page_num(h)
    await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
    await asyncio.sleep(1.3)
    return before, await page_num(h)


async def swipe_prev(h):
    g = await h.ev(GEO)
    y = g["top"] + g["height"] * 0.5
    x0 = g["left"] + 18
    x1 = g["left"] + g["width"] * 0.45
    before = await page_num(h)
    await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
    await asyncio.sleep(1.3)
    return before, await page_num(h)


async def tool_click(h, title):
    return await h.ev(
        "(() => { const b = [...document.querySelectorAll('.ap-tool')]"
        ".find(x => x.getAttribute('title') === %s); if (!b) return 'missing';"
        " b.click(); return 'ok'; })()" % json.dumps(title))


async def centre(h, fx=0.5, fy=0.4):
    g = await h.ev(GEO)
    return (g["left"] + g["width"] * fx, g["top"] + g["height"] * fy)


async def arm_and_click_dialog(h, label):
    """Dialog má @click.capture s `dialogArmed` — bez položení prstu uvnitř
    dialogu se klik zahodí. Namíříme tedy pointerdown na tlačítko a pak klik."""
    return await h.ev(
        "(() => { const b = [...document.querySelectorAll('.ti-actions .jp-btn')]"
        ".find(x => x.textContent.trim() === %s); if (!b) return 'missing';"
        " const r = b.getBoundingClientRect();"
        " const opt = { bubbles: true, cancelable: true, clientX: r.left + r.width/2,"
        "               clientY: r.top + r.height/2, pointerId: 777, pointerType: 'touch' };"
        " document.querySelector('.text-input-overlay')"
        "   .dispatchEvent(new PointerEvent('pointerdown', opt));"
        " b.dispatchEvent(new PointerEvent('pointerdown', opt));"
        " b.click();"
        " return 'clicked:' + b.textContent.trim(); })()" % json.dumps(label))


async def main():
    c = Check()
    h = await fresh_harness()
    async with h:
        await h.open()
        try:
            await h.ev("indexedDB.deleteDatabase('noty-app')")
        except Exception:
            pass
        await asyncio.sleep(0.6)
        await h.open()
        await h.open_song(pages=8, reset=False)

        # --- BASELINE: listování v anotačním režimu -------------------------
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT_TITLE))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "anotační panel")
        await asyncio.sleep(0.6)
        b, a = await swipe_next(h)
        c("BASELINE listování v anotaci", b != a, "%s -> %s" % (b, a))

        # --- A) tah perem (tužka) — pointer se uvolňuje normálně ------------
        await tool_click(h, "Tužka")
        x, y = await centre(h, 0.5, 0.35)
        await h.pen_stroke(x - 40, y, x + 40, y, steps=8)
        await asyncio.sleep(1.2)
        b, a = await swipe_prev(h)
        c("A) po tahu perem se dál listuje", b != a, "%s -> %s" % (b, a))

        # --- B) ZNAČKA: pointer se v onLayerUp NIKDY neuvolní ---------------
        await tool_click(h, "Značky pro výšky not (béčko, odrážka, křížek, ozdoby...)")
        x, y = await centre(h, 0.5, 0.45)
        await h.pen_tap(x, y)
        await asyncio.sleep(1.0)
        has_dialog = await h.ev("!!document.querySelector('.text-input-overlay')")
        c("B) po klepnutí Značkou se otevřel dialog", has_dialog)
        if not has_dialog:
            return c.report()

        # ještě NEpotvrzuj — otestuj, co udělá swipe při otevřeném dialogu
        b, a = await swipe_next(h)
        c("B1) se ZAVŘENÝM dialogem se dál listuje", b != a, "%s -> %s" % (b, a))

        print("  potvrzení dialogu:", await arm_and_click_dialog(h, "Uložit"))
        await asyncio.sleep(1.2)
        c("B) dialog se zavřel", not await h.ev("!!document.querySelector('.text-input-overlay')"))

        b, a = await swipe_prev(h)
        c("B2) PO ZNAČCE se dál listuje", b != a, "%s -> %s" % (b, a))

        # --- C) totéž s TEXTEM (stejná cesta v onLayerUp) -------------------
        await tool_click(h, "Text (klávesnice)")
        x, y = await centre(h, 0.45, 0.6)
        await h.pen_tap(x, y)
        await asyncio.sleep(0.9)
        if await h.ev("!!document.querySelector('.text-input-overlay')"):
            await arm_and_click_dialog(h, "Uložit")
            await asyncio.sleep(1.1)
        b, a = await swipe_next(h)
        c("C) PO TEXTU se dál listuje", b != a, "%s -> %s" % (b, a))

        # --- D) vypnutí anotačního režimu: uklidí se pointer? ---------------
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT_TITLE))
        await asyncio.sleep(0.8)
        c("D) anotační režim vypnut", not await h.ev("!!document.querySelector('.annot-panel')"))
        b, a = await swipe_next(h)
        c("D) po vypnutí režimu se listuje", b != a, "%s -> %s" % (b, a))

        # --- E) znovu zapnout: mělo by fungovat pořád ---------------------
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT_TITLE))
        await asyncio.sleep(0.8)
        b, a = await swipe_prev(h)
        c("E) po opětovném zapnutí režimu se listuje", b != a, "%s -> %s" % (b, a))

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
