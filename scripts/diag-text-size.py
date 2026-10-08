#!/usr/bin/env python3
"""Diagnostika: jakou velikost má aktivní text PO „Uložit“ a po vyčištění dialogu.

Sonda `probe-text-size-before-insert.py` selhala na tom, že dialog otevřený pro
další text ukazoval 20 místo očekávaných 22. Tenhle skript vypíše každý krok,
aby se dalo určit, KDE se hodnota ztratí (uložení vs. obnovení při dalším otevření).

    NOTY_CDP=http://127.0.0.1:9242 python3 scripts/diag-text-size.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


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


async def point_of(h, sel):
    return await h.ev("""(() => {
      const sel = %s;
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const x0 = Math.max(0, Math.floor(r.left - 4)), x1 = Math.min(innerWidth - 1, Math.ceil(r.right + 4));
      const y0 = Math.max(0, Math.floor(r.top - 4)), y1 = Math.min(innerHeight - 1, Math.ceil(r.bottom + 4));
      for (let y = y0; y <= y1; y += 2) for (let x = x0; x <= x1; x += 2) {
        const hit = document.elementFromPoint(x, y);
        if (hit && (hit === el || (hit.closest && hit.closest(sel) === el))) return [x + 0.5, y + 0.5];
      }
      return null;
    })()""" % json.dumps(sel))


async def tap_el(h, sel):
    pt = await point_of(h, sel)
    if not pt:
        print(f"   !! prvek {sel} nenalezen")
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(0.06)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.5)
    return True


async def snap(h, label):
    raw = await h.ev("""(() => JSON.stringify({
      overlay: !!document.querySelector('.text-input-overlay'),
      val: (document.querySelector('.ti-size-val') || {}).textContent || null,
      input: (document.querySelector('.ti-input') || {}).value || null,
      active: !!document.querySelector('.annot-layer > g > circle'),
      ls: (() => { try { return localStorage.getItem('noty.textSize'); } catch (e) { return 'ERR'; } })(),
      navdbg: window.__navdbg ? { editingAnnotationId: window.__navdbg().editingAnnotationId } : null,
      draftDbg: window.__textSizeDbg ? window.__textSizeDbg() : null,
    }))()""")
    print(f"{label}: {raw}")
    return json.loads(raw)


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        # čistý štít: vymaž pamatovanou velikost
        await h.ev("(() => { try { localStorage.removeItem('noty.textSize'); } catch(e){} return 1; })()")
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Text')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)

        p = await h.ev("""(() => {
          const svg = document.querySelector('.annot-layer');
          const v = svg.getBoundingClientRect();
          for (const fy of [0.30, 0.38, 0.46]) for (const fx of [0.62, 0.54, 0.46]) {
            const x = v.left + v.width * fx, y = v.top + v.height * fy;
            if (document.elementFromPoint(x, y) === svg) return {x, y};
          }
          return null;
        })()""")
        print("bod:", p)
        await h.pen_tap(p["x"], p["y"])
        await asyncio.sleep(0.9)
        await snap(h, "1) po otevření dialogu      ")

        await tap_el(h, ".ti-size-btn:last-of-type")
        await snap(h, "2) po jednom +               ")

        await h.set_value(".ti-input", "diagnostika")
        await tap_el(h, ".jp-btn.primary")
        await asyncio.sleep(1.2)
        await snap(h, "3) po Uložit                 ")

        print("   --- a teď jen zavři/přepni nástroj a zpátky na Text ---")
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Tužka')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        await snap(h, "4) po přepnutí na Tužku      ")
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Text')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        await snap(h, "5) zpět na Text              ")

        # nové místo — jiné souřadnice, ať se netrefí do hotové anotace
        p2 = await h.ev("""(() => {
          const svg = document.querySelector('.annot-layer');
          const v = svg.getBoundingClientRect();
          for (const fy of [0.50, 0.58, 0.66]) for (const fx of [0.60, 0.52, 0.44]) {
            const x = v.left + v.width * fx, y = v.top + v.height * fy;
            if (document.elementFromPoint(x, y) === svg) return {x, y};
          }
          return null;
        })()""")
        print("bod 2:", p2)
        await h.pen_tap(p2["x"], p2["y"])
        await asyncio.sleep(0.9)
        await snap(h, "6) nový dialog (má být 22?)  ")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
