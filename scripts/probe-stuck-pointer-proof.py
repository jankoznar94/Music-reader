#!/usr/bin/env python3
"""DŮKAZ DÍRY: nedokončený tah perem nechá `_activePointerId` viset a listování
je mrtvé, dokud se nestiskne anotační tlačítko.

Mechanizmus (z kódu):
  * `_activePointerId` se nastaví v onLayerDown (tah začal na .annot-layer)
  * uvolní se JEN v onLayerUp — a ten je navěšený pouze na .annot-layer
  * `.annot-layer:not(.active) { pointer-events: none }` → když anotační režim
    vypne (nebo se vrstva schová), vrstva `pointerup` NEDOSTANE
  * `blockedNav()` pak vrací true navždy → onTouchStart/onTouchMove/onTouchEnd
    i onTap se hned vrátí → listování prstem je mrtvé

Sonda to zopakuje přesně takto: rozešle `pointerdown` na vrstvu (tah začne),
ale `pointerup` NEPOŠLE. Pak změří, jestli listování jde.

POZOR: sonda je záměrně „destruktivní" — po prvním měření už se stav nezhojí
(leda vypnutím/zapnutím anotačního režimu), což je přesně to, co chceme ukázat.

    scripts/run-probe-fresh.sh scripts/probe-stuck-pointer-proof.py
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


async def page(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    l, r = t.split("/")
    return int(l.split(" ")[0].strip()), int(r.strip().split(" ")[0])


async def try_nav(h, label, attempts=3):
    """Zkusí otočit stránku oběma směry, několikrát."""
    results = []
    for i in range(attempts):
        cur, tot = await page(h)
        for d in ([1, -1] if cur < tot else [-1, 1]):
            g = await h.ev(GEO)
            y = g["top"] + g["height"] * 0.5
            if d > 0:
                x0, x1 = g["left"] + g["width"] - 18, g["left"] + g["width"] * 0.55
            else:
                x0, x1 = g["left"] + 18, g["left"] + g["width"] * 0.45
            await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
            await asyncio.sleep(1.0)
            got = (await page(h))[0]
            results.append((cur, got))
            if got != cur:
                print("  %-42s OK   %s->%s" % (label, cur, got))
                return True
        await asyncio.sleep(0.6)
    cur = (await page(h))[0]
    print("  %-42s **FAIL** (stuck na %s, %d pokusů)" % (label, cur, attempts))
    return False


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

        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)

        await try_nav(h, "1) BASELINE (čistý stav)")
        print("     stav:", json.dumps(await dbg(h), ensure_ascii=False))

        # ---- ROZBITÍ: pointerdown na vrstvu bez pointerup -----------------
        print("\n--- simulace NEDOKONČENÉHO tahu perem (jen pointerdown) ---")
        g = await h.ev(GEO)
        px = g["left"] + g["width"] * 0.5
        py = g["top"] + g["height"] * 0.35
        res = await h.ev(
            "(() => { const svg = document.querySelector('.annot-layer');"
            " if (!svg) return 'no-layer';"
            " const o = { bubbles:true, cancelable:true, pointerId: 4242,"
            "             pointerType:'pen', isPrimary:true, pressure:0.5,"
            "             clientX: %s, clientY: %s };"
            " svg.dispatchEvent(new PointerEvent('pointerdown', o));"
            " return 'pointerdown odeslán'; })()" % (int(px), int(py)))
        print("  ", res)
        await asyncio.sleep(0.4)
        d = await dbg(h)
        print("     stav po nedokončeném tahu:", json.dumps(d, ensure_ascii=False))
        assert d and d["activePointerId"] == 4242, "pointer se nenastavil — simulace selhala"

        # ---- DŮKAZ: listování je mrtvé --------------------------------
        print("\n--- teď se snaž listovat (jako Jan na tabletu) ---")
        await asyncio.sleep(1.0)   # ať vyprší 800ms pen-guard, ať to není o čase
        await try_nav(h, "2) listování po nedokončeném tahu")

        print("\n--- stisk anotačního tlačítka (vypnout + zapnout režim) ---")
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.8)
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.8)
        print("     stav:", json.dumps(await dbg(h), ensure_ascii=False))
        await try_nav(h, "3) listování po vypnutí+zapnutí režimu")

        # ---- DŮKAZ 2: totéž, ale pointerup PŘIJDE na vrstvu --------------
        print("\n--- kontrola: KDYŽ pointerup dorazí, vše je v pořádku ---")
        await h.ev(
            "(() => { const svg = document.querySelector('.annot-layer');"
            " const o = { bubbles:true, cancelable:true, pointerId: 4243,"
            "             pointerType:'pen', isPrimary:true, pressure:0.5,"
            "             clientX: %s, clientY: %s };"
            " svg.dispatchEvent(new PointerEvent('pointerdown', o));"
            " svg.dispatchEvent(new PointerEvent('pointerup', o));"
            " return true; })()" % (int(px), int(py)))
        await asyncio.sleep(1.0)
        print("     stav:", json.dumps(await dbg(h), ensure_ascii=False))
        await try_nav(h, "4) listování po korektním tahu")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
