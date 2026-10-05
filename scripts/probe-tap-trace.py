#!/usr/bin/env python3
"""Proč TAP na okraj v anotačním režimu nedojde k listování?

Instrumentuje .viewer: v capture fázi touchendu si přečte `_touchStart`
(než ho appka vymaže) a zaznamená, co dorazilo. Tím se pozná, jestli selhává
`_touchStart` (null / bez `edge`), `inEdgeZone`, nebo `isControlTarget`.

    scripts/run-probe-fresh.sh scripts/probe-tap-trace.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
ANNOT = "Anotace / listování"
DBG = "JSON.stringify(window.__navdbg ? window.__navdbg() : null)"

TRACE = r"""
(() => {
  window.__t = [];
  const v = document.querySelector('.viewer');
  const log = (tag, extra) => window.__t.push({ tag, extra, page: (document.querySelector('.tb-page')||{}).textContent });
  v.addEventListener('touchstart', e => {
    const t = e.touches[0] || {};
    log('viewer.touchstart', { x: t.clientX, y: t.clientY, rx: t.radiusX, ry: t.radiusY,
      target: e.target.tagName + '.' + (typeof e.target.className === 'string' ? e.target.className : '') });
  }, true);
  v.addEventListener('touchend', e => {
    // capture → běží PŘED obsluhou appky, takže _touchStart ještě žije
    const s = window.__navdbg ? window.__navdbg().touchStart : null;
    const t = (e.changedTouches && e.changedTouches[0]) || {};
    log('viewer.touchend(before)', { touchStart: s, ex: t.clientX, ey: t.clientY,
      rx: t.radiusX, ry: t.radiusY, nTouches: e.touches.length });
  }, true);
  v.addEventListener('click', e => log('viewer.click', { target: e.target.tagName }), true);
  const s = document.querySelector('.annot-layer');
  if (s) {
    s.addEventListener('pointerdown', e => log('layer.pointerdown', { pt: e.pointerType, id: e.pointerId }), true);
    s.addEventListener('pointerup', e => log('layer.pointerup', { pt: e.pointerType, id: e.pointerId }), true);
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


async def page(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    return t.split("/")[0].split(" ")[0].strip()


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
        await h.open_song(pages=10, reset=False)
        await h.set_tablet()
        await asyncio.sleep(0.5)

        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)
        await h.ev(TRACE)

        g = await h.ev(GEO)
        x_right = g["left"] + g["width"] - 20
        y_mid = g["top"] + g["height"] * 0.5
        x_left = g["left"] + 20

        print("viewer šířka:", await h.ev("document.querySelector('.viewer').clientWidth"))
        print("--edge-w:", await h.ev("getComputedStyle(document.querySelector('.viewer')).getPropertyValue('--edge-w')"))
        print("tap vpravo na x=%d, y=%d" % (x_right, y_mid))

        before = await page(h)
        await h.ev("window.__t = []")
        await h.finger_tap(x_right, y_mid, r=12)
        await asyncio.sleep(1.2)
        after = await page(h)
        print("\nstránka: %s -> %s  (%s)" % (before, after, "OTOČILO" if before != after else "NE"))
        print("  volani:", await h.ev("JSON.stringify(window.__navcalls)"))
        print("  dbg:", await h.ev(DBG))
        print("\n--- trace ---")
        for ev in (await h.ev("JSON.stringify(window.__t)")):
            pass
        for ev in json.loads(await h.ev("JSON.stringify(window.__t)")):
            print("  ", json.dumps(ev, ensure_ascii=False))

        print("\n--- totéž pro levý okraj (x=%d) ---" % x_left)
        before = await page(h)
        await h.ev("window.__t = []")
        await h.finger_tap(x_left, y_mid, r=12)
        await asyncio.sleep(1.2)
        after = await page(h)
        print("stránka: %s -> %s  (%s)" % (before, after, "OTOČILO" if before != after else "NE"))
        for ev in json.loads(await h.ev("JSON.stringify(window.__t)")):
            print("  ", json.dumps(ev, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
