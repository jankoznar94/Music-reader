#!/usr/bin/env python3
"""Ověření CHOVÁNÍ na ŽIVÉM webu (harlequin-music-reader.web.app).

Proč zvlášť: na minifikovaném buildu NEEXISTUJE `devtoolsRawSetupState`, takže se
stav musí číst z DOM (transformace, texty, přítomnost prvků) — což je stejně
správnější úroveň (to, co uživatel vidí).

Ověřuje tři nové věci:
  1. odebrání stránky (počítadlo, tlačítka v panelu, ✕ na miniaturách)
  2. zoom pod 100 %
  3. gesta: 2 prsty zoom+posun, 3 prsty rotace
"""
import asyncio
import importlib.util
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check, make_pdf = _mod.Harness, _mod.Check, _mod.make_pdf

LIVE = "https://harlequin-music-reader.web.app/"

STATE = r"""
(() => {
  const stage = document.querySelector('.stage');
  const rotor = document.querySelector('.rotor');
  const ms = stage ? new DOMMatrix(getComputedStyle(stage).transform) : null;
  const mr = rotor ? new DOMMatrix(getComputedStyle(rotor).transform) : null;
  const ind = document.querySelector('.tb-page-center');
  return {
    counter: ind ? ind.textContent.replace(/\s+/g, ' ').trim() : null,
    zoomFit: ms ? +Math.hypot(ms.a, ms.b).toFixed(4) : null,
    panX: ms ? +ms.e.toFixed(2) : null,
    panY: ms ? +ms.f.toFixed(2) : null,
    deg: mr ? +(Math.atan2(mr.b, mr.a) * 180 / Math.PI).toFixed(2) : null,
    thumbX: document.querySelectorAll('.thumb-x').length,
    pagesBtn: !!document.querySelector('.tb-btn[title="Odebrat stránky"]'),
  };
})()
"""


def shown(c):
    try:
        return int(str(c).split("/")[1].split("(")[0].strip())
    except Exception:
        return -1


async def tap_tb(h, title):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll('.tb-btn')]"
        ".find(x=>(x.title||'')===%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title))


async def click_zp(h, title):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
        ".find(x=>(x.title||'')===%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title))


async def pinch(h, factor=1.35, move=0):
    g = await h.geo()
    cx = g["left"] + g["w"] / 2
    cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2
    r0 = 100
    await h.touch("touchStart", [(cx - r0, cy, 12), (cx + r0, cy, 12)])
    for i in range(1, 11):
        t = i / 10
        r = r0 * (1 + (factor - 1) * t)
        await h.touch("touchMove", [(cx - r + move * t, cy, 12), (cx + r + move * t, cy, 12)])
        await asyncio.sleep(0.02)
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.2)


async def rotate3(h, deg=40, radius=150):
    g = await h.geo()
    cx = g["left"] + g["w"] / 2
    cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

    def pts(a0):
        return [(cx + radius * math.cos(a0 + k * 2 * math.pi / 3),
                 cy + radius * math.sin(a0 + k * 2 * math.pi / 3), 12) for k in range(3)]

    await h.touch("touchStart", pts(0.0))
    for i in range(1, 41):
        await h.touch("touchMove", pts(math.radians(deg * i / 40)))
        await asyncio.sleep(0.015)
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.6)


async def main():
    ok = Check()
    pdf = make_pdf(6)
    async with Harness() as h:
        h.url = LIVE          # ŽIVÝ web, ne dev server
        # ⚠️ PAST: prohlížeč měl z dřívějška nainstalovaný STARÝ service worker
        # z produkce → stránky se servírovaly z jeho cache a sonda viděla staré
        # chování (žádné nové tlačítko), i když je na webu nový build. Před
        # měřením proto odregistrovat všechny SW a smazat CacheStorage.
        await h.cdp("Page.navigate", {"url": LIVE})
        await asyncio.sleep(2.0)
        cleared = await h.ev(
            "(() => (async () => {"
            " const rs = await navigator.serviceWorker.getRegistrations();"
            " for (const r of rs) await r.unregister();"
            " const keys = await caches.keys();"
            " for (const k of keys) await caches.delete(k);"
            " return { sw: rs.length, caches: keys.length }; })())()", await_promise=True)
        print("  [cleanup] odregistrováno:", json.dumps(cleared))
        await h.open()
        await asyncio.sleep(1.5)
        still = await h.ev("(async () => (await navigator.serviceWorker.getRegistrations()).length)()",
                           await_promise=True)
        print("  [cleanup] SW po reloadu:", still)
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.5)
        # ⚠️ IndexedDB si pamatuje stav z MINULÉHO běhu (což je správně — trvalost
        # funguje), ale test potřebuje čistý začátek, jinak první kontrola vidí
        # „1 / 5 (z 6)“ a hlásí falešný FAIL.
        await h.ev("indexedDB.deleteDatabase('noty-app')")
        await asyncio.sleep(1.0)
        await h.open()
        await asyncio.sleep(1.5)
        # na živém webu je prázdná IndexedDB → nahrát fixture přes skutečný input
        await h.set_file_input("input[type=file]", pdf)
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=60, label="upload")
        await h.ev(h.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=15)
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40)
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40)
        await asyncio.sleep(1.5)

        s = STATE
        st = await h.ev(s)
        ok("LIVE: tlačítko „Odebrat stránky“ je v liště", st["pagesBtn"], json.dumps(st)[:120])
        ok("LIVE: počítadlo 1 / 6", shown(st["counter"]) == 6, st["counter"])

        # --- odebrání stránky ---
        await tap_tb(h, "Odebrat stránky")
        await asyncio.sleep(0.5)
        clicked = await click_zp(h, "Odebrat tuto stránku ze skladby")
        await asyncio.sleep(1.2)
        st = await h.ev(s)
        ok("LIVE: odebrání stránky funguje (5 zobrazených)", clicked == 1 and shown(st["counter"]) == 5, st["counter"])
        ok("LIVE: počítadlo hlásí původní počet (z 6)", "z 6" in (st["counter"] or ""), st["counter"])

        # --- ✕ na miniaturách ---
        await tap_tb(h, "Slider stránek")
        await asyncio.sleep(1.5)
        st = await h.ev(s)
        ok("LIVE: ✕ na miniaturách je v pásu (5×)", st["thumbX"] == 5, f"thumbX={st['thumbX']}")
        await tap_tb(h, "Slider stránek")
        await asyncio.sleep(0.4)

        # --- vrácení (panel odebírání se otevřením pásu zavřel → otevřít znovu) ---
        await tap_tb(h, "Odebrat stránky")
        await asyncio.sleep(0.5)
        ret = await click_zp(h, "Vrátit odebrané stránky")
        await asyncio.sleep(1.0)
        st = await h.ev(s)
        ok("LIVE: vrácení všech → 6 zobrazených", ret == 1 and shown(st["counter"]) == 6, st["counter"])

        # --- zoom pod 100 % ---
        await tap_tb(h, "Zvětšení a posun")
        await asyncio.sleep(0.4)
        for _ in range(4):
            await click_zp(h, "Oddálit po 10 %")
            await asyncio.sleep(0.25)
        st = await h.ev(s)
        ok("LIVE: zoom jde pod 100 % (60 %)", abs(st["zoomFit"] - 0.60) < 0.03, str(st["zoomFit"]))
        for _ in range(8):
            await click_zp(h, "Oddálit po 10 %")
            await asyncio.sleep(0.2)
        st = await h.ev(s)
        ok("LIVE: minimum zoomu je 25 %", abs(st["zoomFit"] - 0.25) < 0.03, str(st["zoomFit"]))
        await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
                   ".find(x=>x.textContent.trim()==='100 %'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(0.5)
        st = await h.ev(s)
        ok("LIVE: tlačítko 100 % vrátí fit", abs(st["zoomFit"] - 1.0) < 0.03, str(st["zoomFit"]))

        # --- gesta ---
        await pinch(h, factor=1.4, move=60)
        st = await h.ev(s)
        ok("LIVE: 2 prsty zoomují", st["zoomFit"] > 1.05, str(st["zoomFit"]))
        ok("LIVE: 2 prsty posouvají", abs(st["panX"]) > 5, str(st["panX"]))
        ok("LIVE: 2 prsty NErotují", abs(st["deg"]) < 0.01, str(st["deg"]))
        z0, px0, py0 = st["zoomFit"], st["panX"], st["panY"]

        await rotate3(h, deg=40)
        st = await h.ev(s)
        ok("LIVE: 3 prsty rotují (~40°)", abs(abs(st["deg"]) - 40) < 7, str(st["deg"]))
        ok("LIVE: 3 prsty nemění zoom (rigidní)", abs(st["zoomFit"] - z0) < 0.02, f"{z0} -> {st['zoomFit']}")
        ok("LIVE: 3 prsty nemění posun", abs(st["panX"] - px0) < 1 and abs(st["panY"] - py0) < 1,
           f"{px0},{py0} -> {st['panX']},{st['panY']}")

    ok.report()


if __name__ == "__main__":
    asyncio.run(main())
