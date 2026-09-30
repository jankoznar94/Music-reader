#!/usr/bin/env python3
"""Ověření opravy: klepej VŽDY na bod, kde stránka sama hlásí danou dlaždici
(elementFromPoint) — ne na souřadnici spočítanou z getBoundingClientRect.

Tím se obejde jakákoli neshoda měření souřadnic a testuje se skutečná smlouva:
„klepnu na dlaždici, kterou vidím → vloží se ta dlaždice".

Scénáře:
  1. umístění dynamiky perem samo nic nevloží, dialog zůstane otevřený (5x)
  2. volba dlaždic mp, fff, pp po sobě → přesně tyto glyfy
  3. volba prstem
  4. Zrušit nic nevloží
"""
import asyncio
import importlib.util
import json

_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", "/home/martin_fabian/noty-app/cdp-e2e-harness.py")
_h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h)
Harness, Check, make_pdf = _h.Harness, _h.Check, _h.make_pdf

KEY = {"mp": 0xE52C, "fff": 0xE530, "pp": 0xE52B, "sf": 0xE524}


async def state(h):
    return await h.ev(
        "(() => ({ open: !!document.querySelector('.text-input-overlay'),"
        " glyphs: [...document.querySelectorAll('.annot-layer text')]"
        "   .map(t => t.textContent.codePointAt(0)) }))()")


async def point_of(h, key, sel=".dyn-btn"):
    """Najdi bod, kde elementFromPoint vrací právě dlaždici `key` (nebo prvek `sel`)."""
    return await h.ev("""(() => {
      const want = %s, sel = %s;
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      for (let y = Math.ceil(r.top); y < r.bottom; y += 3) {
        for (let x = Math.ceil(r.left); x < r.right; x += 3) {
          const el = document.elementFromPoint(x, y);
          if (!el) continue;
          const hit = sel === '.dyn-btn'
            ? (el.closest ? el.closest('.dyn-btn') : null)
            : (el.closest ? el.closest(sel) : null);
          if (sel === '.dyn-btn') { if (hit && hit.title === want) return [x + 0.5, y + 0.5]; }
          else if (hit) return [x + 0.5, y + 0.5];
        }
      }
      return null;
    })()""" % (json.dumps(key), json.dumps(sel)))


async def dismiss(h):
    """Zavři dialog SKUTEČNÝM dotykem na Zrušit (programový click guard blokuje)."""
    if not await h.ev("!!document.querySelector('.text-input-overlay')"):
        return True
    pt = await point_of(h, "", ".jp-btn")
    if not pt:
        return False
    await h.pen_tap(pt[0], pt[1])
    await asyncio.sleep(0.5)
    return not await h.ev("!!document.querySelector('.text-input-overlay')")


async def open_dialog(h):
    """Najdi volnou plochu not a umísti tam dynamiku perem."""
    for _ in range(8):
        p = await h.free_point()
        if not p:
            continue
        await h.pen_stroke(p["x"], p["y"], p["x"] + 2, p["y"] + 2)
        await asyncio.sleep(0.7)
        if await h.ev("!!document.querySelector('.text-input-overlay')"):
            return p
    return None


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Dynamika')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)

        # 1) pět umístění: nic se nesmí vložit samo
        auto = []
        for i in range(5):
            before = await state(h)
            p = await open_dialog(h)
            if not p:
                ok(f"umístění #{i+1}: dialog se otevřel", False, "nepodařilo se otevřít")
                continue
            after = await state(h)
            new = [g for g in after["glyphs"] if g not in before["glyphs"]]
            auto += new
            ok(f"umístění #{i+1}: dialog se otevřel a sám nic nevložil",
               after["open"] and not new,
               f"open={after['open']} nové={['U+%04X' % g for g in new]}")
            closed = await dismiss(h)
            if not closed:
                ok(f"umístění #{i+1}: dialog se dá zavřít dotykem na Zrušit", False,
                   "zůstal otevřený")
            await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                       ".find(x => (x.title || '').startsWith('Dynamika')); if (b) b.click(); })()")
            await asyncio.sleep(0.3)
        ok("umístění perem samo nikdy nevloží dynamiku", auto == [],
           f"samovolně {['U+%04X' % g for g in auto]}")

        # 2) volby dlaždic perem
        for key in ("mp", "fff", "pp"):
            p = await open_dialog(h)
            if not p:
                ok(f"dialog pro volbu {key}", False, "neotevřel se")
                continue
            st = await state(h)
            pt = await point_of(h, key)
            if not pt:
                ok(f"dlaždice {key} je na stránce dosažitelná", False, "bod nenalezen")
                continue
            await h.pen_tap(pt[0], pt[1])
            await asyncio.sleep(0.6)
            st2 = await state(h)
            new = [g for g in st2["glyphs"] if g not in st["glyphs"]]
            ok(f"volba '{key}' vloží U+{KEY[key]:04X}", new == [KEY[key]],
               f"vloženo {['U+%04X' % g for g in new]}")

        # 3) volba prstem
        p = await open_dialog(h)
        if p:
            st = await state(h)
            pt = await point_of(h, "sf")
            if pt:
                await h.finger_tap(pt[0], pt[1])
                await asyncio.sleep(0.6)
                st2 = await state(h)
                new = [g for g in st2["glyphs"] if g not in st["glyphs"]]
                ok("volba prstem 'sf' vloží U+E524", new == [0xE524],
                   f"vloženo {['U+%04X' % g for g in new]}")

        # 4) Zrušit
        p = await open_dialog(h)
        if p:
            st = await state(h)
            closed = await dismiss(h)
            st2 = await state(h)
            ok("Zrušit dotykem nic nevloží a dialog zmizí",
               closed and (not st2["open"]) and st2["glyphs"] == st["glyphs"],
               f"open={st2['open']}")

    return ok.report()


asyncio.run(main())
