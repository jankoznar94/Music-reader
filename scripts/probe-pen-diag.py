#!/usr/bin/env python3
"""Izolace: proč pero po opravě nezačne kreslit?

Sonda nasadí na .annot-layer počítadla událostí a zkusí dva způsoby tahu:
  1) CDP Input.dispatchMouseEvent s pointerType='pen'  (cesta harnessu)
  2) syntetický PointerEvent('pointerdown')            (cesta, která fungovala)
Pak porovná, které události dorazí a co udělá onLayerDown.

    scripts/run-probe-fresh.sh scripts/probe-pen-diag.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
ANNOT = "Anotace / listování"
DBG = "JSON.stringify(window.__navdbg ? window.__navdbg() : null)"

TAP = r"""
(() => {
  window.__ev = [];
  const s = document.querySelector('.annot-layer');
  const st = document.querySelector('.stage.backdrop');
  for (const t of ['pointerdown','pointermove','pointerup','pointercancel','pointerleave','pointerenter','pointerover']) {
    s.addEventListener(t, e => window.__ev.push(['layer', t, e.pointerType, e.pointerId]), true);
    st.addEventListener(t, e => window.__ev.push(['stage', t, e.pointerType, e.pointerId]), true);
  }
  return true;
})()
"""


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

GEO = ("(() => { const r = document.querySelector('.stage.backdrop').getBoundingClientRect();"
       " return { left: r.left, top: r.top, width: r.width, height: r.height }; })()")


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def dbg(h):
    raw = await h.ev(DBG)
    return json.loads(raw) if raw else None


async def events(h):
    return await h.ev("JSON.stringify(window.__ev || [])")


async def main():
    h = await fresh_harness()
    async with h:
        await h.open()
        try:
            await h.ev("indexedDB.deleteDatabase('noty-app')")
        except Exception:
            pass
        await asyncio.sleep(0.6)
        await h.open()
        await h.open_song(pages=6, reset=False)

        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => x.getAttribute('title') === 'Tužka'); if (b) b.click(); return true; })()")
        await asyncio.sleep(0.4)

        g = await h.ev(GEO)
        cx = g["left"] + g["width"] * 0.5
        cy = g["top"] + g["height"] * 0.3

        # ---------- 1) CDP pero (cesta harnessu) ----------
        print("=== 1) CDP Input.dispatchMouseEvent pointerType=pen ===")
        await h.ev(TAP)
        await h.pen_down(cx - 40, cy)
        await h.pen_move(cx, cy + 5)
        await h.pen_up(cx + 40, cy + 10)
        await asyncio.sleep(0.6)
        print("  události:", await events(h))
        print("  stav:", json.dumps(await dbg(h), ensure_ascii=False))
        print("  anotací:", await h.ev("document.querySelectorAll('.annot-layer > g').length"))

        # ---------- 2) syntetický PointerEvent ----------
        print("\n=== 2) syntetický PointerEvent (bubbling) ===")
        await h.ev(TAP)
        await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " const o = { bubbles:true, cancelable:true, pointerId: 9001,"
            "             pointerType:'pen', isPrimary:true, pressure:0.5, buttons:1,"
            "             clientX:%d, clientY:%d };"
            " s.dispatchEvent(new PointerEvent('pointerdown', o));"
            " s.dispatchEvent(new PointerEvent('pointermove',"
            "   Object.assign({}, o, { clientX:%d, clientY:%d })));"
            " s.dispatchEvent(new PointerEvent('pointerup',"
            "   Object.assign({}, o, { clientX:%d, clientY:%d })));"
            " return true; })()" % (int(cx - 40), int(cy), int(cx), int(cy + 5), int(cx + 40), int(cy + 10)))
        await asyncio.sleep(0.8)
        print("  události:", await events(h))
        print("  stav:", json.dumps(await dbg(h), ensure_ascii=False))
        print("  anotací:", await h.ev("document.querySelectorAll('.annot-layer > g').length"))

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
