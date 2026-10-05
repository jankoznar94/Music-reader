#!/usr/bin/env python3
"""Cílená kontrola: neRozbil @pointerleave/@pointercancel na .stage kreslení perem?

Po opravě (resetGestureState + @pointerleave na .stage) musí pero pořád
NORMÁLNĚ kreslit: pointerdown → pointermove → pointerup na .annot-layer.
Sonda proto kreslí a čte stav PŘED, BĚHEM a PO tahu.

    scripts/run-probe-fresh.sh scripts/probe-pen-still-draws.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
ANNOT = "Anotace / listování"
DBG = "JSON.stringify(window.__navdbg ? window.__navdbg() : null)"
COUNT = "document.querySelectorAll('.annot-layer > g').length"


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
        await h.open_song(pages=6, reset=False)

        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "panel")
        await asyncio.sleep(0.6)

        # ověř, že vrstva je aktivní (pointer-events: auto) — bez toho pero nekreslí
        layer = await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " if (!s) return null;"
            " const r = s.getBoundingClientRect();"
            " return { cls: s.getAttribute('class'), pe: getComputedStyle(s).pointerEvents,"
            "          w: +r.width.toFixed(0), h: +r.height.toFixed(0) }; })()")
        print("vrstva:", json.dumps(layer, ensure_ascii=False))
        c("vrstva je aktivní (pointer-events: auto)", layer and layer["pe"] == "auto",
          str(layer and layer["pe"]))

        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => x.getAttribute('title') === 'Tužka'); if (b) b.click(); return true; })()")
        await asyncio.sleep(0.4)

        before = await h.ev(COUNT)
        g = await h.ev(GEO)
        cx = g["left"] + g["width"] * 0.5
        cy = g["top"] + g["height"] * 0.3
        print("cíl tahu:", cx, cy, "| počet anotací před:", before)

        # POZOR: CDP `Input.dispatchMouseEvent{pointerType:'pen'}` v headless
        # Chromu 149 DORUČÍ jen pointerover/enter/move/up — `pointerdown` NEPŘIJDE,
        # takže pero „nekreslí" i na NEDOTČENÉM kódu. Ověřeno spuštěním sondy
        # před i po změně (stejný výsledek) → není to regrese appky, je to past
        # harnessu. Proto tah stavíme syntetickými PointerEventy: ověřeno, že
        # anotaci opravdu vytvoří, a to na původním i upraveném kódu.
        await h.ev("window.__nd = { pid: 9001 }")
        await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " const o = { bubbles:true, cancelable:true, pointerId:9001,"
            "             pointerType:'pen', isPrimary:true, pressure:0.5, buttons:1,"
            "             clientX:%d, clientY:%d };"
            " s.dispatchEvent(new PointerEvent('pointerdown', o)); return true; })()"
            % (int(cx - 50), int(cy)))
        await asyncio.sleep(0.3)
        mid = await dbg(h)
        print("BĚHEM tahu (po pointerdown):", json.dumps(mid, ensure_ascii=False))
        c("BĚHEM tahu drží _activePointerId", mid and mid["activePointerId"] == 9001,
          str(mid and mid["activePointerId"]))

        for i in range(1, 6):
            await h.ev(
                "(() => { const s = document.querySelector('.annot-layer');"
                " s.dispatchEvent(new PointerEvent('pointermove',"
                "  { bubbles:true, cancelable:true, pointerId:9001, pointerType:'pen',"
                "    isPrimary:true, pressure:0.5, buttons:1, clientX:%d, clientY:%d }));"
                " return true; })()" % (int(cx - 50 + i * 20), int(cy + i * 3)))
            await asyncio.sleep(0.06)
        await h.ev(
            "(() => { const s = document.querySelector('.annot-layer');"
            " s.dispatchEvent(new PointerEvent('pointerup',"
            "  { bubbles:true, cancelable:true, pointerId:9001, pointerType:'pen',"
            "    isPrimary:true, pressure:0, buttons:0, clientX:%d, clientY:%d }));"
            " return true; })()" % (int(cx + 50), int(cy + 15)))
        await asyncio.sleep(1.0)

        after = await h.ev(COUNT)
        d = await dbg(h)
        print("PO tahu:", json.dumps(d, ensure_ascii=False), "| počet anotací:", after)
        c("pero NAKRESLILO anotaci", after > before, "%s -> %s" % (before, after))
        c("_activePointerId je po tahu uvolněný", d and d["activePointerId"] is None,
          str(d and d["activePointerId"]))
        c("blocked je false", d and d["blocked"] is False, str(d and d["blocked"]))

        # a ještě: prst po tahu listuje
        t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
        cur = int(t.split("/")[0].split(" ")[0].strip())
        g = await h.ev(GEO)
        y = g["top"] + g["height"] * 0.5
        await h.finger_swipe(g["left"] + g["width"] - 18, y, g["left"] + g["width"] * 0.55, y,
                             r=12, steps=10)
        await asyncio.sleep(1.2)
        t2 = await h.ev("document.querySelector('.tb-page').textContent.trim()")
        cur2 = int(t2.split("/")[0].split(" ")[0].strip())
        c("prst po tahu listuje", cur2 != cur, "%s -> %s" % (cur, cur2))

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
