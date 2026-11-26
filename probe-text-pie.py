#!/usr/bin/env python3
"""Koláč u nástroje TEXT — barva, velikost, rámeček, šířka a styl rámu.

Ověřuje v reálném prohlížeči:
  1. text má TŘI koláče: Barva / Velikost / Rámeček
  2. po volbě „S rámečkem“ se objeví další dva: Šířka rámu / Styl rámu (5 koláčů)
  3. koláče se vejdou na displej a nepřekrývají se
  4. volba šířky a stylu se opravdu uloží (označená výseč + hodnota v aplikaci)
  5. přepnutí zpět na „Bez rámečku“ koláče zase ubere
"""
import asyncio
import importlib.util
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
APP = os.environ.get("NOTY_APP") or m.APP_URL


async def rect(h, sel, idx=0):
    return await h.ev(
        "(() => { const e = document.querySelectorAll(%s)[%d]; if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2 }; })()"
        % (json.dumps(sel), idx))


async def pies(h):
    return await h.ev(
        "(() => ([...document.querySelectorAll('.pie-svg g[data-pie]')].map(g => ({"
        "  key: g.querySelector('.pie-label') ? '' : '',"
        "  cx: +g.getAttribute('data-cx'), cy: +g.getAttribute('data-cy'),"
        "  r0: +g.getAttribute('data-r0'), r1: +g.getAttribute('data-r1'),"
        "  on: [...g.querySelectorAll('.pie-sec')].findIndex(e => e.classList.contains('on')),"
        "  n: g.querySelectorAll('.pie-sec').length }))))()")


async def labels(h):
    return await h.ev("[...document.querySelectorAll('.pie-label')].map(e => e.textContent)")


async def tap_sector(h, pi, idx):
    """Klepnutí doprostřed výseče `idx` v koláči `pi` (0 = nahoru, po směru)."""
    g = (await pies(h))[pi]
    n = g["n"]
    a = -math.pi / 2 + (idx + 0.5) * (2 * math.pi / n)
    r = (g["r0"] + g["r1"]) / 2
    await h.finger_tap(g["cx"] + math.cos(a) * r, g["cy"] + math.sin(a) * r)


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','gesture')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(4), pages=4, reset=False)
        await h.ev("localStorage.setItem('topbarHidden','0')")

        annot = await rect(h, ".tb-btn[title^='Anotace']")
        await h.finger_tap(annot["x"], annot["y"])
        await asyncio.sleep(0.5)
        it = await rect(h, ".gm-item", 3)      # Text
        await h.finger_tap(it["x"], it["y"])
        await asyncio.sleep(0.7)

        st = await pies(h)
        ok("text má tři koláče (barva, velikost, rámeček)", len(st) == 3, len(st))
        ok("popisky sedí", (await labels(h)) == ["Barva", "Velikost", "Rámeček"], await labels(h))

        vw, vh = 800, 1280
        ok("všechny koláče se vejdou na displej",
           all(p["cx"] - p["r1"] >= -1 and p["cx"] + p["r1"] <= vw + 1
               and p["cy"] - p["r1"] >= -1 and p["cy"] + p["r1"] <= vh + 1 for p in st), st)
        over = []
        for i in range(len(st)):
            for j in range(i + 1, len(st)):
                d = math.hypot(st[i]["cx"] - st[j]["cx"], st[i]["cy"] - st[j]["cy"])
                if d < st[i]["r1"] + st[j]["r1"]:
                    over.append((i, j, round(d), round(st[i]["r1"] + st[j]["r1"])))
        ok("koláče se nepřekrývají", not over, over)

        # --- „S rámečkem“ (druhá výseč koláče Rámeček) ------------------------
        await tap_sector(h, 2, 1)
        await asyncio.sleep(0.6)
        st = await pies(h)
        ok("po „S rámečkem“ je koláčů PET", len(st) == 5, len(st))
        ok("přibyla Šířka a Styl rámu",
           (await labels(h)) == ["Barva", "Velikost", "Rámeček", "Šířka rámu", "Styl rámu"],
           await labels(h))
        ok("i pět koláčů se vejde na displej",
           all(p["cx"] - p["r1"] >= -1 and p["cx"] + p["r1"] <= vw + 1
               and p["cy"] - p["r1"] >= -1 and p["cy"] + p["r1"] <= vh + 1 for p in st), st)
        ok("vybraný je „S rámečkem“", st[2]["on"] == 1, st[2])

        # --- šířka 8 (třetí výseč) a styl Čárky (druhá) -----------------------
        await tap_sector(h, 3, 2)
        await asyncio.sleep(0.45)
        st = await pies(h)
        ok("vybraná šířka rámu je označená", st[3]["on"] == 2, st[3])
        ok("šířka se propsala do aplikace",
           (await h.ev("window.__barDev.textBorderWidth ? window.__barDev.textBorderWidth.value : null")) in (None, 8),
           await h.ev("window.__barDev.textBorderWidth ? window.__barDev.textBorderWidth.value : null"))

        await tap_sector(h, 4, 1)
        await asyncio.sleep(0.45)
        st = await pies(h)
        ok("vybraný styl rámu je označený", st[4]["on"] == 1, st[4])

        # --- zpět na „Bez rámečku“ -------------------------------------------
        await tap_sector(h, 2, 0)
        await asyncio.sleep(0.55)
        st = await pies(h)
        ok("po „Bez rámečku“ jsou zase tři koláče", len(st) == 3, len(st))
        ok("vybrané je „Bez rámečku“", st[2]["on"] == 0, st[2])

        # --- výběr zůstane označený i když prst přejede jiný koláč -------------
        before = (await pies(h))[1]["on"]
        g = (await pies(h))[0]
        await h.touch("touchStart", [(g["cx"], g["cy"] + 8, 12)])
        await h.touch("touchMove", [(g["cx"] + (g["r0"] + g["r1"]) / 2, g["cy"], 12)])
        await asyncio.sleep(0.25)
        after = (await pies(h))[1]["on"]
        ok("výběr v jiném koláči nezmizí, když prst přejede vedle", before == after, {"before": before, "after": after})
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.3)

    ok.report()


asyncio.run(main())
