#!/usr/bin/env python3
"""Zátěžová sonda se STAVOVÝM OKNEM: která anotační akce nechá viset
`_activePointerId` (a tím zabije listování)?

Používá dočasný hook `window.__navdbg()` z Prohlizec.vue.

Klíčové: `_activePointerId` se uvolňuje JEN z pointerup/pointercancel na
`.annot-layer`. Ta má `pointer-events: none`, kdykoli není anotační režim
zapnutý — dotyk proto vrstvu mine a pointer zůstane viset navždy.

    scripts/run-probe-fresh.sh scripts/probe-navdbg-stress.py
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


async def swipe(h):
    g = await h.ev(GEO)
    y = g["top"] + g["height"] * 0.5
    cur, tot = await page(h)
    if cur < tot:
        x0, x1 = g["left"] + g["width"] - 18, g["left"] + g["width"] * 0.55
    else:
        x0, x1 = g["left"] + 18, g["left"] + g["width"] * 0.45
    await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
    await asyncio.sleep(1.0)
    return cur, (await page(h))[0]


async def tool(h, title):
    return await h.ev(
        "(() => { const b = [...document.querySelectorAll('.ap-tool')]"
        ".find(x => x.getAttribute('title') === %s); if (!b) return 'missing';"
        " b.click(); return 'ok'; })()" % json.dumps(title))


async def centre(h, fx=0.5, fy=0.4):
    g = await h.ev(GEO)
    return (g["left"] + g["width"] * fx, g["top"] + g["height"] * fy)


async def report(h, label, before=None):
    d = await dbg(h)
    b, a = await swipe(h)
    print("  %-30s nav: %s->%s  | %s" % (
        label, b, a, json.dumps(d, ensure_ascii=False) if d else "NO HOOK"))
    return b != a, d


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

        print("hook:", await dbg(h))
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)
        await report(h, "baseline (anotace zapnuta)")

        # 1) tah perem
        await tool(h, "Tužka")
        x, y = await centre(h, 0.5, 0.35)
        await h.pen_stroke(x - 40, y, x + 40, y, steps=8)
        await asyncio.sleep(1.0)
        await report(h, "po tahu perem")

        # 2) guma (jiná cesta v onLayerUp)
        await tool(h, "Guma (maže anotace, přes které přejede)")
        x, y = await centre(h, 0.5, 0.3)
        await h.pen_stroke(x - 40, y, x + 40, y, steps=8)
        await asyncio.sleep(1.0)
        await report(h, "po gumě")

        # 3) značka s dialogem
        await tool(h, "Značky pro výšky not (béčko, odrážka, křížek, ozdoby...)")
        x, y = await centre(h, 0.5, 0.45)
        await h.pen_tap(x, y)
        await asyncio.sleep(0.9)
        print("  dialog:", await h.ev("!!document.querySelector('.text-input-overlay')"))
        d = await dbg(h)
        print("  stav s OTEVŘENÝM dialogem:", json.dumps(d, ensure_ascii=False))
        await h.ev("(() => { const b = [...document.querySelectorAll('.ti-actions .jp-btn')]"
                   ".find(x => x.textContent.trim() === 'Uložit');"
                   " const ov = document.querySelector('.text-input-overlay');"
                   " if (ov) { const r = ov.getBoundingClientRect();"
                   "  ov.dispatchEvent(new PointerEvent('pointerdown',"
                   "   { bubbles:true, cancelable:true, pointerId:777, pointerType:'touch',"
                   "     clientX: r.left+5, clientY: r.top+5 })); }"
                   " if (b) b.click(); return true; })()")
        await asyncio.sleep(1.0)
        await report(h, "po značce (dialog Uložit)")

        # 4) NÁVRAT: klepni pero na místo značky nástrojem Ruka → výběr → dialog znovu
        await tool(h, "Upravit / přesunout text či dynamiku")
        await h.pen_tap(x, y)
        await asyncio.sleep(0.8)
        await report(h, "po výběru prvku (ruka)")

        # 5) KILL: vypni anotační režim uprostřed tahu perem
        print("\n--- KILL TEST: vypnutí anotačního režimu uprostřed tahu ---")
        await tool(h, "Tužka")
        g = await h.ev(GEO)
        px = g["left"] + g["width"] * 0.5
        py = g["top"] + g["height"] * 0.3
        await h.pen_down(px, py)
        await h.pen_move(px + 30, py + 10)
        await asyncio.sleep(0.3)
        d = await dbg(h)
        print("  uprostřed tahu:", json.dumps(d, ensure_ascii=False))
        # vypni režim (jako by uživatel stiskl ✏️ / přešel jinam)
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.6)
        await h.pen_up(px + 30, py + 10)
        await asyncio.sleep(1.2)
        d = await dbg(h)
        print("  po vypnutí režimu uprostřed tahu:", json.dumps(d, ensure_ascii=False))
        b, a = await swipe(h)
        print("  listování po tom:", b, "->", a)

        # 6) totéž s TŘEMI prsty (OS na tabletu bere PrintScreen)
        print("\n--- KILL TEST 2: tříprsté gesto (OS) ---")
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.6)
        g = await h.ev(GEO)
        cx = g["left"] + g["width"] * 0.5
        cy = g["top"] + g["height"] * 0.45
        await h.touch("touchStart", [(cx - 60, cy), (cx + 60, cy), (cx, cy + 60)])
        await h.touch("touchMove", [(cx - 40, cy - 30), (cx + 40, cy + 20), (cx, cy + 80)])
        await asyncio.sleep(0.3)
        d = await dbg(h)
        print("  během rotace:", json.dumps(d, ensure_ascii=False))
        await h.touch("touchEnd", [])
        await asyncio.sleep(1.2)
        await report(h, "po rotaci 3 prsty")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
