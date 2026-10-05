#!/usr/bin/env python3
"""Tap na okraj v anotačním režimu NElístuje? (Jan, Oct 2026)

Jan: „Stále nefunguje tap na přesun na další a předchozí stránku. Anotační
režim to zkrátka nějak vypíná."

POZADÍ KÓDU — tap jde JINUDY než swipe:
  onTap()      → `if (annotMode.value) return;`         ← tap v anotaci se ZAHODÍ
  onTouchEnd() → `if (wasAnot && st.edge && inEdgeZone(t.clientX)) annotEdgeTap(...)`
  annotEdgeTap → `if (isControlTarget(target)) return;` ← anotační PANEL leží v levém kraji

Sonda měří tap na kraj: vlevo (kde sedí anotační panel) i vpravo, v anotaci
i mimo ni, a vypíše, co cestu zablokovalo.

    scripts/run-probe-fresh.sh scripts/probe-edge-tap-nav.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
ANNOT = "Anotace / listování"
DBG = "JSON.stringify(window.__navdbg ? window.__navdbg() : null)"


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

GEO = ("(() => { const r = document.querySelector('.stage.backdrop').getBoundingClientRect();"
       " return { left: r.left, top: r.top, width: r.width, height: r.height }; })()")

# Co leží na daném bodě? (odhalí, jestli tap trefí panel/vrstvu/plátno)
HIT = r"""
(() => {
  const els = document.elementsFromPoint(%d, %d).slice(0, 4);
  return els.map(e => (e.className && typeof e.className === 'string'
      ? e.tagName + '.' + e.className.split(' ').join('.')
      : e.tagName));
})()
"""


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def page(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    l, r = t.split("/")
    return int(l.split(" ")[0].strip()), int(r.strip().split(" ")[0])


async def dbg(h):
    raw = await h.ev(DBG)
    return json.loads(raw) if raw else None


async def tap(h, x, y, label=""):
    before = (await page(h))[0]
    await h.finger_tap(x, y, r=12)
    await asyncio.sleep(1.1)
    after = (await page(h))[0]
    return before, after


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
        await h.open_song(pages=10, reset=False)
        await h.set_tablet()
        await asyncio.sleep(0.5)

        g = await h.ev(GEO)
        y_mid = g["top"] + g["height"] * 0.5
        x_left = g["left"] + 20
        x_right = g["left"] + g["width"] - 20
        print("geometrie: vlevo x=%d, vpravo x=%d, y=%d" % (x_left, x_right, y_mid))

        print("\n--- co leží na okrajích (bez anotace) ---")
        print("  vlevo :", await h.ev(HIT % (int(x_left), int(y_mid))))
        print("  vpravo:", await h.ev(HIT % (int(x_right), int(y_mid))))

        # --- 1) MIMO anotační režim -------------------------------------
        print("\n--- 1) MIMO anotační režim ---")
        b, a = await tap(h, x_right, y_mid)
        c("1) tap vpravo přepne vpřed (čtení)", a != b, "%s->%s" % (b, a))
        b, a = await tap(h, x_right, y_mid)
        c("1) tap vpravo podruhé", a != b, "%s->%s" % (b, a))
        b, a = await tap(h, x_left, y_mid)
        c("1) tap vlevo přepne zpět (čtení)", a != b, "%s->%s" % (b, a))

        # --- 2) V anotačním režimu --------------------------------------
        print("\n--- 2) zapnout anotační režim ---")
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)

        print("  co leží na okrajích S panelem:")
        print("    vlevo :", await h.ev(HIT % (int(x_left), int(y_mid))))
        print("    vpravo:", await h.ev(HIT % (int(x_right), int(y_mid))))
        print("  __navdbg:", json.dumps(await dbg(h), ensure_ascii=False))

        b, a = await tap(h, x_right, y_mid)
        c("2) TAP VPRAVO v anotaci → další stránka", a != b, "%s->%s" % (b, a))
        b, a = await tap(h, x_right, y_mid)
        c("2) TAP VPRAVO v anotaci podruhé", a != b, "%s->%s" % (b, a))
        b, a = await tap(h, x_left, y_mid)
        c("2) TAP VLEVO v anotaci → předchozí", a != b, "%s->%s" % (b, a))

        # --- 3) tap na kraj pod anotačním panelem (nižší y) -------------
        print("\n--- 3) tap vlevo POD panelem (panel končí ~y=472) ---")
        y_low = g["top"] + g["height"] * 0.8
        print("    co tam leží:", await h.ev(HIT % (int(x_left), int(y_low))))
        b, a = await tap(h, x_left, y_low)
        c("3) tap vlevo pod panelem → předchozí", a != b, "%s->%s" % (b, a))

        # --- 4) swipe pro srovnání (fungoval) ---------------------------
        print("\n--- 4) swipe pro srovnání ---")
        cur = (await page(h))[0]
        await h.finger_swipe(x_right, y_mid, g["left"] + g["width"] * 0.55, y_mid, r=12, steps=10)
        await asyncio.sleep(1.1)
        c("4) SWIPE vpravo v anotaci funguje", (await page(h))[0] != cur,
          "%s->%s" % (cur, (await page(h))[0]))

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
