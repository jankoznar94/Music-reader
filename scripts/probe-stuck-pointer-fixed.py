#!/usr/bin/env python3
"""Ověření OPRAVY: nedokončený tah perem už nesmí zabít listování.

Opakuje scénář ze scripts/probe-stuck-pointer-proof.py (který PŘED opravou
prokázal, že `_activePointerId` zůstal viset a listování bylo mrtvé natrvalo)
a navíc přidává další cesty, kterými pointer dřív mohl zmizet:

  A) pointerdown na vrstvu bez pointerup  → úklid přes _staleGuard v blockedNav
  B) pointerdown + vypnutí anotačního režimu (vrstva ztratí pointer-events)
  C) pointerdown + odchod pera z .stage (pointerleave)
  D) pointerdown + simulovaná ztráta viditelnosti karty (visibilitychange)

Po každé musí listování po chvíli (než vyprší 800 ms pen-guard) zase jít.

    scripts/run-probe-fresh.sh scripts/probe-stuck-pointer-fixed.py
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


async def try_nav(h, attempts=3):
    for _ in range(attempts):
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
            if got != cur:
                return True, "%s->%s" % (cur, got)
        await asyncio.sleep(0.6)
    return False, "stuck na %s" % ((await page(h))[0])


async def stuck_pointer(h, pid):
    """Pošle pointerdown na vrstvu a NIC dalšího."""
    g = await h.ev(GEO)
    px = int(g["left"] + g["width"] * 0.5)
    py = int(g["top"] + g["height"] * 0.35)
    return await h.ev(
        "(() => { const svg = document.querySelector('.annot-layer');"
        " if (!svg) return 'no-layer';"
        " svg.dispatchEvent(new PointerEvent('pointerdown',"
        "  { bubbles:true, cancelable:true, pointerId:%d, pointerType:'pen',"
        "    isPrimary:true, pressure:0.5, clientX:%d, clientY:%d }));"
        " return 'sent'; })()" % (pid, px, py))


async def ensure_annot(h, on=True):
    have = await h.ev("!!document.querySelector('.annot-panel')")
    if have != on:
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.8)


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
        await ensure_annot(h, True)
        await asyncio.sleep(0.6)

        ok, det = await try_nav(h)
        c("BASELINE listování", ok, det)

        # --- A) pointerdown bez pointerup --------------------------------
        print("\n--- A) pointerdown bez pointerup ---")
        await stuck_pointer(h, 5001)
        await asyncio.sleep(0.4)
        d = await dbg(h)
        print("   hned po pointerdown:", json.dumps(d, ensure_ascii=False))
        c("A) pointer se nastavil (simulace platí)", d["activePointerId"] == 5001, str(d["activePointerId"]))
        await asyncio.sleep(1.0)
        ok, det = await try_nav(h)
        c("A) listování se po chvíli rozjede (PO OPRAVĚ)", ok, det)

        # --- B) pointerdown + vypnutí režimu ----------------------------
        print("\n--- B) pointerdown, pak vypnutí anotačního režimu ---")
        await ensure_annot(h, True)
        await stuck_pointer(h, 5002)
        await asyncio.sleep(0.3)
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.6)
        d = await dbg(h)
        print("   po vypnutí režimu:", json.dumps(d, ensure_ascii=False))
        c("B) pointer je uvolněný (resetGestureState na annotMode)", d["activePointerId"] is None, str(d["activePointerId"]))
        ok, det = await try_nav(h)
        c("B) listování jde", ok, det)

        # --- C) pointerdown + pointerleave ze .stage --------------------
        print("\n--- C) pero opustí .stage (pointerleave) ---")
        await ensure_annot(h, True)
        await stuck_pointer(h, 5003)
        await asyncio.sleep(0.3)
        # pointerleave s odlišnými souřadnicemi (pero odjelo mimo stage)
        await h.ev(
            "(() => { const st = document.querySelector('.stage.backdrop');"
            " st.dispatchEvent(new PointerEvent('pointerleave',"
            "  { bubbles:false, pointerId:5003, pointerType:'pen', isPrimary:true,"
            "    clientX:-50, clientY:-50 })); return true; })()")
        await asyncio.sleep(0.8)
        d = await dbg(h)
        print("   po pointerleave:", json.dumps(d, ensure_ascii=False))
        c("C) pointer uvolněný", d["activePointerId"] is None, str(d["activePointerId"]))
        ok, det = await try_nav(h)
        c("C) listování jde", ok, det)

        # --- D) pointerdown + ztráta viditelnosti ----------------------
        print("\n--- D) simulace spánku karty (visibilitychange) ---")
        await ensure_annot(h, True)
        await stuck_pointer(h, 5004)
        await asyncio.sleep(0.3)
        # POZOR: `Page.setWebLifecycleState frozen` v headless Chromu zamrazí
        # renderer tak, že už neodpovídá na Input.dispatchTouchEvent (sonda pak
        # visí až do timeoutu). Stačí vyvolat samotnou událost — obsluha v appce
        # volá resetGestureState() bezpodmínečně, takže se tím testuje přesně to
        # zapojení, o které jde.
        await h.ev("(() => { document.dispatchEvent(new Event('visibilitychange')); return true; })()")
        await asyncio.sleep(0.8)
        d = await dbg(h)
        print("   po visibilitychange:", json.dumps(d, ensure_ascii=False))
        c("D) pointer uvolněný", d["activePointerId"] is None, str(d["activePointerId"]))
        ok, det = await try_nav(h)
        c("D) listování jde", ok, det)

        # --- E) regrese: kreslení perem pořád funguje -------------------
        print("\n--- E) regrese: pero pořád kreslí, prst pořád listuje ---")
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => x.getAttribute('title') === 'Tužka'); if (b) b.click(); return true; })()")
        before = await h.ev("document.querySelectorAll('.annot-layer > g').length")
        g = await h.ev(GEO)
        cx = g["left"] + g["width"] * 0.5
        cy = g["top"] + g["height"] * 0.3
        # CDP pero v headless Chromu nedoručí pointerdown → tah stavíme synteticky
        # (viz scripts/probe-pen-diag.py; stejné chování na původním i novém kódu).
        await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " const mk = (t, x, y, p) => new PointerEvent(t,"
            "  { bubbles:true, cancelable:true, pointerId:9101, pointerType:'pen',"
            "    isPrimary:true, pressure:p, buttons:p ? 1 : 0, clientX:x, clientY:y });"
            " s.dispatchEvent(mk('pointerdown', %d, %d, 0.5));"
            " for (let i = 1; i <= 6; i++) s.dispatchEvent(mk('pointermove', %d + i * 16, %d + i * 3, 0.5));"
            " s.dispatchEvent(mk('pointerup', %d, %d, 0));"
            " return true; })()"
            % (int(cx - 50), int(cy), int(cx - 50), int(cy), int(cx + 50), int(cy + 18)))
        await asyncio.sleep(1.2)
        after = await h.ev("document.querySelectorAll('.annot-layer > g').length")
        c("E) pero nakreslilo anotaci", after > before, "%s -> %s" % (before, after))
        ok, det = await try_nav(h)
        c("E) prst po tahu dál listuje", ok, det)

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
