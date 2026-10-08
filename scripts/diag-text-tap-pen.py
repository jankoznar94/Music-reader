#!/usr/bin/env python3
"""DIAGNOSTIKA: pero klepne na plátno → má se otevřít dialog textu.

Jan: „Doteky prstem i perem jsou občas nestabilní.“ V probe-touch-all.py vychází
sekce D (pero klepne → dialog textu) na 1/12, zatímco všechno ostatní je 12/12.
Dvě možná vysvětlení, která se musí ROZLIŠIT (jinak se ladí neexistující chyba):

  (a) APLIKACE: pero se po prvním tahu „zasekne“ (visí `_activePointerId`) a další
      klepnutí spadnou do větve „blok: jiný tah“ — pak je to skutečná chyba.
  (b) TEST: dialog se po prvním úspěchu NEZAVŘE (má pojistku `dialogArmed`),
      zůstane přes celou obrazovku, `free_xy` nenajde volné místo a sonda to
      počítá jako „neotevřelo se“ — pak je chyba v sondě.

Sonda po každém pokusu vypíše, KTERÁ VĚTEV se uplatnila (`window.__navdbg`), jestli
dialog zůstal otevřený a proč selhalo zavření.

    NOTY_CDP=http://127.0.0.1:9226 python3 scripts/diag-text-tap-pen.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
N = int(os.environ.get("NOTY_N", "8"))


def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("hh", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = CDP
Harness = _m.Harness

JS_PEN_TAP = """([x, y]) => {
  const l = document.querySelector('.annot-layer'); if (!l) return 'no-layer';
  const mk = (t, p) => new PointerEvent(t, { bubbles: true, cancelable: true,
    pointerId: 9101, pointerType: 'pen', isPrimary: true, pressure: p,
    buttons: p ? 1 : 0, clientX: x, clientY: y });
  l.dispatchEvent(mk('pointerdown', 0.5)); l.dispatchEvent(mk('pointerup', 0));
  return 'sent';
}"""

JS_PEN_STROKE = """([x0, y0, x1, y1]) => {
  const l = document.querySelector('.annot-layer'); if (!l) return 'no-layer';
  const mk = (t, x, y, p) => new PointerEvent(t, { bubbles: true, cancelable: true,
    pointerId: 9102, pointerType: 'pen', isPrimary: true, pressure: p,
    buttons: p ? 1 : 0, clientX: x, clientY: y });
  l.dispatchEvent(mk('pointerdown', x0, y0, 0.5));
  for (let i = 1; i <= 8; i++)
    l.dispatchEvent(mk('pointermove', x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * i / 8, 0.5));
  l.dispatchEvent(mk('pointerup', x1, y1, 0));
  return 'sent';
}"""


async def ev_args(h, js, args):
    return await h.ev("(%s)(%s)" % (js, json.dumps(args)))


async def annot_on(h):
    return await h.ev("""(() => { const b = [...document.querySelectorAll('.tb-btn')]
      .find(x => (x.title || '').startsWith('Anotace'));
      return b ? b.classList.contains('on') : null; })()""")


async def panel_open(h):
    return await h.ev("!!document.querySelector('.ap-collapse')")


async def set_panel(h, want):
    for _ in range(4):
        if await panel_open(h) == bool(want):
            return True
        await h.ev("""(() => { const b = document.querySelector('.ap-collapse');
          if (b) b.click(); return true; })()""")
        await asyncio.sleep(0.5)
    return False


async def pick_tool(h, prefix):
    for _ in range(3):
        if await annot_on(h):
            break
        await h.ev("""(() => { const b = [...document.querySelectorAll('.tb-btn')]
          .find(x => (x.title || '').startsWith('Anotace')); if (b) b.click(); })()""")
        await asyncio.sleep(0.5)
    await set_panel(h, True)
    for _ in range(5):
        if await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
          .find(x => (x.title || '').startsWith(%s)); return !!b; })()""" % json.dumps(prefix)):
            break
        await asyncio.sleep(0.4)
    r = await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
      .find(x => (x.title || '').startsWith(%s));
      if (!b) return 'missing'; b.click(); return 'ok'; })()""" % json.dumps(prefix))
    await asyncio.sleep(0.5)
    return r == "ok"


async def free_xy(h):
    raw = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y, d) => boxes.some(r => r.width > 0 &&
        x > r.left - d && x < r.right + d && y > r.top - d && y < r.bottom + d);
      for (const d of [30.0, 20.0, 12.0]) {
        for (let y = v.top + 40; y < v.bottom - 40; y += 14)
          for (let x = v.left + 24; x < v.right - 24; x += 14) {
            if (document.elementFromPoint(x, y) !== svg) continue;
            if (near(x, y, d)) continue;
            return {x, y};
          }
      }
      return null; })()""")
    return (raw["x"], raw["y"]) if raw else None


async def dbg(h):
    r = await h.ev("(() => (window.__navdbg ? window.__navdbg() : null))()")
    return r or {}


async def dialog_open(h):
    return await h.ev("!!document.querySelector('.text-input-overlay')")


async def close_dialog(h, label="Zrušit"):
    """Zavři dialog SKUTEČNÝM dotykem (dialog má pojistku dialogArmed)."""
    r = await h.ev("""(() => { const b = [...document.querySelectorAll('.ti-actions .jp-btn')]
      .find(x => (x.textContent||'').trim() === %s); if (!b) return 'missing';
      const rc = b.getBoundingClientRect();
      const o = { bubbles:true, cancelable:true, pointerId:777, pointerType:'touch',
                  clientX: rc.left + rc.width/2, clientY: rc.top + rc.height/2 };
      const ov = document.querySelector('.text-input-overlay');
      if (ov) { ov.dispatchEvent(new PointerEvent('pointerdown', o));
                ov.dispatchEvent(new MouseEvent('click', o)); }
      b.click(); return 'ok'; })()""" % json.dumps(label))
    await asyncio.sleep(0.5)
    still = await dialog_open(h)
    return r == "ok" and not still


async def main():
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await pick_tool(h, "Text")
        tool_now = await h.ev("""(() => { const b = document.querySelector('.ap-tool.on');
          return b ? b.title : null; })()""")
        print("nastroj pred merenim:", tool_now)
        await set_panel(h, False)
        await asyncio.sleep(0.4)

        for i in range(N):
            d0 = await dbg(h)
            xy = await free_xy(h)
            if not xy:
                print(f"[{i}] free_xy=None | dialog_otevreny={await dialog_open(h)}")
                continue
            await ev_args(h, JS_PEN_TAP, [xy[0], xy[1]])
            await asyncio.sleep(0.8)
            opened = await dialog_open(h)
            d1 = await dbg(h)
            over = await h.ev("""(() => { const e = document.elementFromPoint(%f, %f);
              return e ? (e.className && e.className.baseVal !== undefined
                ? e.className.baseVal : String(e.className || e.tagName)) : null; })()"""
                % (xy[0], xy[1]))
            print(f"[{i}] bod=({xy[0]:.0f},{xy[1]:.0f}) pod_bodem={over} "
                  f"otevreno={opened} | lastUp='{d1.get('lastUp')}' "
                  f"activePtr={d1.get('activePtr', d1.get('activePointerId'))} "
                  f"activeStroke={d1.get('activeStroke')} annot={d1.get('annotCount')}")
            print(f"      pred: lastUp='{d0.get('lastUp')}' "
                  f"activePtr={d0.get('activePointerId')} "
                  f"evLog_tail={d0.get('evLog', [])[-4:]}")
            print(f"      po:   evLog_tail={d1.get('evLog', [])[-5:]}")
            if opened:
                okc = await close_dialog(h, "Zrušit")
                print(f"      zavreni: {'OK' if okc else 'SELHALO'} "
                      f"dialog_po={await dialog_open(h)} "
                      f"activePtr_po={ (await dbg(h)).get('activePointerId') }")

        # Druhá otázka: zůstává pero zaseknuté i po TAHEM (ne klepnutí)?
        print("\n--- pero po tahu, pak klepnutí ---")
        await pick_tool(h, "Tužka")
        tool2 = await h.ev("""(() => { const b = document.querySelector('.ap-tool.on');
          return b ? b.title : null; })()""")
        print("nastroj:", tool2)
        await set_panel(h, False)
        for i in range(3):
            xy = await free_xy(h)
            await ev_args(h, JS_PEN_STROKE, [xy[0], xy[1], xy[0] + 70, xy[1] + 25])
            await asyncio.sleep(0.6)
            d = await dbg(h)
            print(f"[tah {i}] activePtr={d.get('activePointerId')} "
                  f"stroke={d.get('activeStroke')} annot={d.get('annotCount')}")
        await pick_tool(h, "Text")
        await set_panel(h, False)
        xy = await free_xy(h)
        await ev_args(h, JS_PEN_TAP, [xy[0], xy[1]])
        await asyncio.sleep(0.8)
        print("po tahu klepnutí → dialog:", await dialog_open(h),
              (await dbg(h)).get("lastUp"))


if __name__ == "__main__":
    asyncio.run(main())
