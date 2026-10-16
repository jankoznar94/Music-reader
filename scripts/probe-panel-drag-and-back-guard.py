#!/usr/bin/env python3
"""Sonda: přetahování panelů + obrana proti systémovému gestu zpět (Oct 2026)

Jan:
  1) „Při pokusu o listování na další nebo předchozí stránku se teď stává, že
     appka vyskočí do seznamu skladeb."
  2) „Přidáme možnost Drag And drop ke všem dropdown oknům v menu."

Ověřuje:
  A) panel se dá odtáhnout úchytem (a tah NElístuje stránkami),
  B) posun se pamatuje po reloadu, klepnutí na úchyt vrátí panel na výchozí místo,
  C) dotyk v notách spolkne navigaci zpět (prohlížeč/OS gesto), ale tlačítko
     Zpět v liště projde vždy — i bezprostředně po dotyku,
  D) bez dotyku (odpočatý stav) zpět z not opravdu odejde (žádná regrese).

Použití:  NOTY_CDP=http://127.0.0.1:9225 python3 scripts/probe-panel-drag-and-back-guard.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9225")


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
Harness, Check, make_pdf = _m.Harness, _m.Check, _m.make_pdf


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def mouse(h, kind, x, y, buttons=1):
    await h.cdp("Input.dispatchMouseEvent",
                {"type": kind, "x": x, "y": y, "button": "left",
                 "buttons": buttons, "clickCount": 1, "pointerType": "mouse"})


async def drag(h, x0, y0, dx, dy, steps=6):
    await mouse(h, "mousePressed", x0, y0)
    for i in range(1, steps + 1):
        await mouse(h, "mouseMoved", x0 + dx * i / steps, y0 + dy * i / steps)
        await asyncio.sleep(0.02)
    await mouse(h, "mouseReleased", x0 + dx, y0 + dy, buttons=0)
    await asyncio.sleep(0.4)


PANEL_RECT = ("(() => { const p = document.querySelector(%s);"
              " if (!p) return null; const r = p.getBoundingClientRect();"
              " return { x: Math.round(r.left), y: Math.round(r.top),"
              " w: Math.round(r.width), h: Math.round(r.height) }; })()")

ZOOM_BTN = ("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
            ".find(x => (x.title || '').startsWith('Zvětšení')); if (b) b.click();"
            " return !!b; })()")


async def open_zoom_panel(h):
    await h.ev(ZOOM_BTN)
    await asyncio.sleep(0.4)


async def grip_center(h):
    return await h.ev(
        "(() => { const g = document.querySelector('.zoom-panel .panel-grip');"
        " if (!g) return null; const r = g.getBoundingClientRect();"
        " return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()")


async def main():
    ok = Check()
    async with await fresh_harness() as h:
        await h.open()
        await h.open_song(pages=8)

        # ---------- A) přetahování panelu ----------------------------------
        await open_zoom_panel(h)
        before = await h.ev(PANEL_RECT % "'.zoom-panel'")
        page0 = await h.page_text()
        g = await grip_center(h)
        ok("úchyt zoom panelu existuje", bool(g), str(g))
        if not g:
            return ok.report()

        await drag(h, g["x"], g["y"], -140, 120)
        after = await h.ev(PANEL_RECT % "'.zoom-panel'")
        ok("panel se posunul tažením úchytu",
           abs((after["x"] - before["x"]) + 140) < 6 and abs((after["y"] - before["y"]) - 120) < 6,
           f"{before} -> {after}")
        ok("tažení úchytu NElístuje stránkami", page0 == await h.page_text(), await h.page_text())
        stored = await h.ev("localStorage.getItem('noty-panel-pos')")
        ok("posun je uložený", "zoom" in (stored or ""), stored)

        # ---------- B) pamatuje se + klepnutí vrátí -------------------------
        await h.cdp("Page.reload", {"ignoreCache": False})
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="reload")
        await asyncio.sleep(1.2)
        await open_zoom_panel(h)
        after_reload = await h.ev(PANEL_RECT % "'.zoom-panel'")
        ok("po reloadu je panel tam, kam ho uživatel odtáhl",
           abs(after_reload["x"] - after["x"]) < 6 and abs(after_reload["y"] - after["y"]) < 6,
           f"{after} -> {after_reload}")

        g2 = await grip_center(h)
        await mouse(h, "mousePressed", g2["x"], g2["y"])
        await mouse(h, "mouseReleased", g2["x"], g2["y"], buttons=0)
        await asyncio.sleep(0.4)
        back_home = await h.ev(PANEL_RECT % "'.zoom-panel'")
        ok("klepnutí na úchyt vrátí panel na výchozí místo",
           abs(back_home["x"] - before["x"]) < 6 and abs(back_home["y"] - before["y"]) < 6,
           f"výchozí {before} -> {back_home}")
        await h.ev(ZOOM_BTN)   # panel zavřít
        await asyncio.sleep(0.3)

        # ---------- C) dotyk spolkne zpět, tlačítko Zpět ne ------------------
        geo = await h.geo()
        y = geo["barBottom"] + 200
        reader_url = (await h.ev("location.pathname")) or ""
        await h.finger_tap(geo["left"] + 22, y)   # dotyk prstem = ozbrojení okna
        await h.ev("history.back()")
        await asyncio.sleep(1.2)
        snap = await h.ev("JSON.stringify({path: location.pathname,"
                          " viewer: !!document.querySelector('.viewer'),"
                          " library: !!document.querySelector('.library')})")
        snap = json.loads(snap)
        ok("po dotyku gesto zpět NEVYSKOČÍ z not",
           snap["viewer"] and not snap["library"] and snap["path"] == reader_url, json.dumps(snap))

        # tlačítko Zpět v liště = úmysl, musí projít i hned po dotyku
        await h.finger_tap(geo["left"] + 22, y)
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '') === 'Zpět'); b && b.click(); return !!b; })()")
        await asyncio.sleep(1.2)
        snap = json.loads(await h.ev("JSON.stringify({path: location.pathname,"
                                     " viewer: !!document.querySelector('.viewer'),"
                                     " library: !!document.querySelector('.library')})"))
        ok("tlačítko Zpět projde i hned po dotyku", snap["library"] and not snap["viewer"],
           json.dumps(snap))

        # ---------- D) odpočatý stav: zpět z not opravdu odejde -------------
        await h.ev(_m.Harness.expand_authors_js())
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="znovu otevřít")
        await asyncio.sleep(1.5)
        await h.ev("history.back()")
        await asyncio.sleep(1.2)
        snap = json.loads(await h.ev("JSON.stringify({path: location.pathname,"
                                     " viewer: !!document.querySelector('.viewer'),"
                                     " library: !!document.querySelector('.library')})"))
        ok("bez předchozího dotyku zpět z not odejde do knihovny",
           snap["library"] and not snap["viewer"], json.dumps(snap))

    return ok.report()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (ConnectionRefusedError, OSError) as exc:
        raise SystemExit(f"Chrome na {CDP} neodpovídá ({exc})")
