#!/usr/bin/env python3
"""Sonda: přesune se KAŽDÝ panel s úchytem? (zoom, rotace, odebrané stránky,
skoky, záložky, anotace)

Kontroluje u každého panelu:
  * úchyt (⠿) v panelu je,
  * tažením se panel posune a tah NElístuje stránkami,
  * úchyt zůstane na displeji (posun je omezený — jinak by panel zmizel
    i s jedinou cestou zpět),
  * klepnutí na úchyt vrátí panel na výchozí místo.

Panel, jehož úchyt je mimo displej (uložená pozice z dřívějška / jiná
orientace), sonda nejdřív klepnutím vrátí domů — to je zároveň test záchrany
pozic (rescuePanelOffsets).

    NOTY_CDP=http://127.0.0.1:9227 python3 scripts/probe-panel-grips.py [songId]
"""
import asyncio
import importlib.util
import json
import os
import sys
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9227")
SONG = sys.argv[1] if len(sys.argv) > 1 else None


def _load_harness():
    cand = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness, Check = _m.Harness, _m.Check

PANELS = [
    ("zoom", "Zvětšení", ".zoom-panel:not(.rot-panel)"),
    ("rot", "Rotace stránky", ".zoom-panel.rot-panel"),
    ("pages", "Odebrat stránky", ".zoom-panel:not(.rot-panel)"),
    ("jump", "Vytvořit skok", ".jump-panel"),
    ("bookmark", "Přidat záložku", ".jump-panel"),
    ("annot", "Anotace / listování", ".annot-panel"),
]

RECT = ("(() => { const p = document.querySelector(%s); if (!p) return null;"
        " const r = p.getBoundingClientRect();"
        " return { x: Math.round(r.left), y: Math.round(r.top) }; })()")
GRIP = ("(() => { const p = document.querySelector(%s); if (!p) return null;"
        " const g = p.querySelector('.panel-grip'); if (!g) return null;"
        " const r = g.getBoundingClientRect();"
        " return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()")


async def click_btn(h, prefix):
    return await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                      ".find(x => (x.title || '').startsWith(%s)); if (b) b.click();"
                      " return !!b; })()" % json.dumps(prefix))


async def mouse(h, kind, x, y, buttons=1):
    await h.cdp("Input.dispatchMouseEvent",
                {"type": kind, "x": x, "y": y, "button": "left",
                 "buttons": buttons, "clickCount": 1, "pointerType": "mouse"})


async def first_song(h):
    ids = await h.ev(
        "new Promise(res => { const r = indexedDB.open('noty-app');"
        " r.onsuccess = () => { const q = r.result.transaction('songs','readonly')"
        ".objectStore('songs').getAll(); q.onsuccess = () => res(JSON.stringify("
        "q.result.map(s => s.id))); }; })")
    ids = json.loads(ids)
    return ids[0] if ids else None


async def main():
    ok = Check()
    async with Harness(_m.APP_URL) as h:
        await h.set_tablet()
        await h.cdp("Page.navigate", {"url": _m.APP_URL})
        await asyncio.sleep(2.5)
        song = SONG or await first_song(h)
        if not song:
            raise SystemExit("v IndexedDB není žádná skladba — nahraj nejdřív PDF")
        await h.cdp("Page.navigate", {"url": _m.APP_URL + "prohlizec/" + song})
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="čtečka")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="stránka")
        await asyncio.sleep(1.0)
        for name, title, sel in PANELS:
            await click_btn(h, title)
            await asyncio.sleep(0.5)
            # Úklid z předchozího běhu: panel klepnutím na úchyt vrátit domů,
            # aby se "výchozí místo" neměřilo s uloženým posunem.
            gp0 = await h.ev(GRIP % json.dumps(sel))
            if gp0 and gp0["x"] > 2 and gp0["y"] > 2:
                await mouse(h, "mousePressed", gp0["x"], gp0["y"])
                await mouse(h, "mouseReleased", gp0["x"], gp0["y"], buttons=0)
                await asyncio.sleep(0.5)
            before = await h.ev(RECT % json.dumps(sel))
            g = await h.ev(GRIP % json.dumps(sel))
            ok(f"{name}: úchyt v panelu", bool(before) and bool(g),
               f"panel={before} grip={g}")
            if not (before and g):
                await click_btn(h, title)
                await asyncio.sleep(0.3)
                continue
            await mouse(h, "mousePressed", g["x"], g["y"])
            for i in range(1, 6):
                await mouse(h, "mouseMoved", g["x"] - 90 * i / 5, g["y"] + 70 * i / 5)
                await asyncio.sleep(0.02)
            await mouse(h, "mouseReleased", g["x"] - 90, g["y"] + 70, buttons=0)
            await asyncio.sleep(0.4)
            moved = await h.ev(RECT % json.dumps(sel))
            ok(f"{name}: panel se tažením posunul",
               (moved["x"], moved["y"]) != (before["x"], before["y"]),
               f"{before} -> {moved}")
            # Úchyt musí zůstat na displeji — jinak panel zmizí i s cestou zpět.
            g3 = await h.ev(GRIP % json.dumps(sel))
            ok(f"{name}: úchyt zůstal na displeji (posun omezený)",
               bool(g3) and g3["x"] >= 0 and g3["y"] >= 0, str(g3))
            page = await h.page_text()
            g2 = await h.ev(GRIP % json.dumps(sel))
            await mouse(h, "mousePressed", g2["x"], g2["y"])
            await mouse(h, "mouseReleased", g2["x"], g2["y"], buttons=0)
            await asyncio.sleep(0.4)
            home = await h.ev(RECT % json.dumps(sel))
            ok(f"{name}: klepnutí na úchyt vrátí panel zpět",
               abs(home["x"] - before["x"]) < 6 and abs(home["y"] - before["y"]) < 6,
               f"{before} -> {home}")
            ok(f"{name}: tah po úchytu nelistoval", page == await h.page_text(),
               await h.page_text())
            await click_btn(h, title)
            await asyncio.sleep(0.4)
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
