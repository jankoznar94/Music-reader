#!/usr/bin/env python3
"""Hledám REGRESI: po opravě listování v anotačním režimu nefunguje vůbec.

Jan (po nasazení): „Teď listování nefunguje při anotačním režimu vůbec.
Už od začátku."

Hypotézy:
  H1) `resetGestureState()` v `gotoPage` maže `_touchStart` a `_pinch` — swipe
      ale stránku otočí, takže je to až následek, ne příčina.
  H2) `@pointerleave` na `.stage` volá `onLayerUp`, a ten dělá víc než úklid:
      u nástroje text/dynamika/značka otevře dialog (`pending`) apod.
  H3) **Sticky `:hover` na reálném tabletu.** `_staleGuard()` uvolní pointer jen
      když `svg.matches(':hover')` je FALSE. Na tabletu je po dotyku `:hover`
      na vrstvě TRVALE pravdivý → pointer se neuvolní nikdy → listování mrtvé.
      Harness doteď `:hover` nikdy nenastavil, takže to nemohl odhalit.

Sonda testuje listování v anotačním režimu:
  A) čistý stav
  B) po dotyku na střed (simulace reálného dotyku na plátno)
  C) se zapnutým `Emulation.setEmulatedMedia(hover)` — jako dotykové zařízení
  D) po tahu perem prstem (bez pointerup — past, kterou oprava řeší)

    scripts/run-probe-fresh.sh scripts/probe-nav-regression.py
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


async def try_nav(h):
    for _ in range(2):
        cur, tot = await page(h)
        d = 1 if cur < tot else -1
        g = await h.ev(GEO)
        y = g["top"] + g["height"] * 0.5
        if d > 0:
            x0, x1 = g["left"] + g["width"] - 18, g["left"] + g["width"] * 0.55
        else:
            x0, x1 = g["left"] + 18, g["left"] + g["width"] * 0.45
        await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
        await asyncio.sleep(1.0)
        if (await page(h))[0] != cur:
            return True, "%s->%s" % (cur, (await page(h))[0])
        await asyncio.sleep(0.8)
    return False, "stuck %s" % ((await page(h))[0])


async def hover_state(h):
    return await h.ev(
        "(() => { const s = document.querySelector('.annot-layer');"
        " return s ? { hover: s.matches(':hover'), cls: s.getAttribute('class') } : null; })()")


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
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)

        print("hover stav (headless default):", await hover_state(h))
        ok, det = await try_nav(h)
        c("A) čistý stav", ok, det)

        # --- B) dotyk na střed (jako reálný prst na plátno) --------------
        print("\n--- B) dotyk na střed plátna ---")
        g = await h.ev(GEO)
        await h.finger_tap(g["left"] + g["width"] * 0.5, g["top"] + g["height"] * 0.45, r=12)
        await asyncio.sleep(0.6)
        print("   stav:", json.dumps(await dbg(h), ensure_ascii=False))
        print("   hover:", await hover_state(h))
        ok, det = await try_nav(h)
        c("B) po dotyku na střed se dál listuje", ok, det)

        # --- C) EMULACE DOTYKOVÉHO ZAŘÍZENÍ (hover: hover, pointer: coarse)
        print("\n--- C) emulace tabletu (Emulation.setEmulatedMedia hover) ---")
        await h.cdp("Emulation.setEmulatedMedia", {
            "features": [{"name": "hover", "value": "hover"},
                         {"name": "pointer", "value": "coarse"}]})
        await asyncio.sleep(0.5)
        print("   hover:", await hover_state(h))
        ok, det = await try_nav(h)
        c("C) s emulovaným honevrem se listuje", ok, det)

        # --- D) tah, který nedostane pointerup (past, kterou oprava řeší) --
        print("\n--- D) nedokončený tah (bez pointerup) ---")
        g = await h.ev(GEO)
        px = int(g["left"] + g["width"] * 0.5)
        py = int(g["top"] + g["height"] * 0.35)
        await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " s.dispatchEvent(new PointerEvent('pointerdown',"
            "  { bubbles:true, cancelable:true, pointerId:7777, pointerType:'pen',"
            "    isPrimary:true, pressure:0.5, buttons:1, clientX:%d, clientY:%d }));"
            " return true; })()" % (px, py))
        await asyncio.sleep(0.4)
        d = await dbg(h)
        print("   hned po pointerdown:", json.dumps(d, ensure_ascii=False))
        print("   hover:", await hover_state(h))
        await asyncio.sleep(1.0)
        d2 = await dbg(h)
        print("   po 1 s (guard?):", json.dumps(d2, ensure_ascii=False))
        await asyncio.sleep(2.0)
        d3 = await dbg(h)
        print("   po 3 s:", json.dumps(d3, ensure_ascii=False))
        ok, det = await try_nav(h)
        c("D) po nedokončeném tahu se listuje", ok, det)

        # --- E) hover NA vrstvě (jako když tam leží prst) -----------------
        print("\n--- E) rucně nastavený :hover na vrstvě ---")
        forced = await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " if (!s) return 'no';"
            " try { s.dispatchEvent(new PointerEvent('pointerover',"
            "  { bubbles:true, pointerId:8888, pointerType:'touch', isPrimary:true,"
            "    clientX:100, clientY:100 })); } catch(e) {}"
            " return s.matches(':hover'); })()")
        print("   hover po pointerover:", forced)
        await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " s.dispatchEvent(new PointerEvent('pointerdown',"
            "  { bubbles:true, cancelable:true, pointerId:8889, pointerType:'touch',"
            "    isPrimary:true, pressure:0.5, buttons:1, clientX:%d, clientY:%d }));"
            " return true; })()" % (px, py))
        await asyncio.sleep(2.5)
        d = await dbg(h)
        print("   stav po 2,5 s s hoverem:", json.dumps(d, ensure_ascii=False))
        print("   hover:", await hover_state(h))
        ok, det = await try_nav(h)
        c("E) s :hover na vrstvě se listuje (H3)", ok, det)

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
