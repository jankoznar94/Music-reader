#!/usr/bin/env python3
"""Koláče: rovnoměrné rozložení hlavních + hierarchie vedlejších (vějíř + spojka).

Ověřuje v reálném prohlížeči:
  1. TŘI hlavní koláče (text bez rámečku) jsou stejně velké a stejně daleko
     od fajfky jako při dvou — žádné lepení na střed.
  2. Po „Rámeček: ano“ přibudou DVĚ vedlejší koláče: jsou menší, sedí u svého
     rodiče (blíž k němu než k fajfce) a vedou k nim spojky.
  3. Zvýrazňovač: „Volně“ odemkne Šířku, „Obdélník“ Výšku — vždy jako
     vedlejší koláč rodiče „Způsob“.
  4. Popisky jsou čitelné (plná barva, dost velké) — kontrola computed stylu.
"""
import asyncio
import base64
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
VW, VH = (int(x) for x in os.environ.get("NOTY_VIEWPORT", "800x1280").split("x"))


async def shot(h, path):
    s = await h.cdp("Page.captureScreenshot", {"format": "png"})
    open(path, "wb").write(base64.b64decode(s["data"]))


async def rect(h, sel, idx=0):
    return await h.ev(
        "(() => { const e = document.querySelectorAll(%s)[%d]; if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2, w: r.width }; })()"
        % (json.dumps(sel), idx))


DUMP = """(() => ({
  center: (() => { const svg = document.querySelector('.pie-svg'); 
    return svg ? [+svg.viewBox.baseVal.width/2, +svg.viewBox.baseVal.height/2] : null })(),
  pies: [...document.querySelectorAll('.pie-svg g[data-pie]')].map((g, i) => ({
    i, cx: +g.getAttribute('data-cx'), cy: +g.getAttribute('data-cy'),
    r0: +g.getAttribute('data-r0'), r1: +g.getAttribute('data-r1'),
    key: '', n: g.querySelectorAll('.pie-sec').length,
    parent: +(g.getAttribute('data-parent') || -1),
    label: (document.querySelectorAll('.pie-label')[i] || {}).textContent,
    minor: !!(document.querySelectorAll('.pie-label')[i] || {}).classList
              && document.querySelectorAll('.pie-label')[i].classList.contains('minor'),
    on: [...g.querySelectorAll('.pie-sec')].findIndex(e => e.classList.contains('on')),
    texts: [...g.querySelectorAll('.pie-ico.txt')].map(e => e.textContent),
    hub: (g.querySelector('.pie-hub-txt') || {}).textContent || null,
    labelColor: (document.querySelectorAll('.pie-label')[i] ? getComputedStyle(document.querySelectorAll('.pie-label')[i]).fill : null),
    labelSize: (document.querySelectorAll('.pie-label')[i] ? getComputedStyle(document.querySelectorAll('.pie-label')[i]).fontSize : null),
  })),
  links: document.querySelectorAll('.pie-link').length,
  errors: window.__errs || []
}))()"""


async def tap_sector(h, pi, idx):
    g = (await h.ev(DUMP))["pies"][pi]
    n = g["n"]
    a = -math.pi / 2 + (idx + 0.5) * (2 * math.pi / n)
    r = (g["r0"] + g["r1"]) / 2
    await h.finger_tap(g["cx"] + math.cos(a) * r, g["cy"] + math.sin(a) * r)
    await asyncio.sleep(0.7)


def check_layout(ok, name, st):
    c = st["center"]
    major = [p for p in st["pies"] if not p["minor"]]
    minor = [p for p in st["pies"] if p["minor"]]
    vw, vh = VW, VH
    ok("%s: vše na displeji" % name,
       all(p["cx"] - p["r1"] >= 0 and p["cx"] + p["r1"] <= vw
           and p["cy"] - p["r1"] >= 0 and p["cy"] + p["r1"] <= vh for p in st["pies"]),
       [(p["i"], round(p["cx"] - p["r1"]), round(p["cx"] + p["r1"]),
         round(p["cy"] - p["r1"]), round(p["cy"] + p["r1"])) for p in st["pies"]])
    over = []
    for i in range(len(st["pies"])):
        for j in range(i + 1, len(st["pies"])):
            a, b = st["pies"][i], st["pies"][j]
            d = math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])
            related = a["parent"] == b["i"] or b["parent"] == a["i"]
            if d < a["r1"] + b["r1"] + (14 if related else 6):
                over.append((a["label"], b["label"], round(d), round(a["r1"] + b["r1"])))
    ok("%s: koláče se nepřekrývají" % name, not over, over)
    if len(major) > 1:
        dists = [round(math.hypot(p["cx"] - c[0], p["cy"] - c[1])) for p in major]
        radii = [round(p["r1"]) for p in major]
        ok("%s: hlavní koláče stejně daleko od fajfky" % name,
           max(dists) - min(dists) <= 2, dists)
        ok("%s: hlavní koláče stejně velké" % name, max(radii) - min(radii) <= 2, radii)
        ok("%s: hlavní koláče nejsou namačkané u fajfky" % name,
           min(dists) >= 40 + max(radii) * 0.9, {"vzdalenost": dists, "r": radii})
    if minor:
        ok("%s: vedlejší jsou menší než hlavní" % name,
           max(p["r1"] for p in minor) < min(p["r1"] for p in major),
           {"minor": [p["r1"] for p in minor], "major": [p["r1"] for p in major]})
        ok("%s: ke každému vedlejšímu vede spojka" % name,
           st["links"] == len(minor), {"links": st["links"], "minor": len(minor)})
        # Vedlejší musí být blíž svému rodiči (Rámeček / Způsob) než fajfce.
        par = min(major, key=lambda p: min(
            math.hypot(p["cx"] - q["cx"], p["cy"] - q["cy"]) for q in minor))
        for q in minor:
            dPar = math.hypot(q["cx"] - par["cx"], q["cy"] - par["cy"])
            dHub = math.hypot(q["cx"] - c[0], q["cy"] - c[1])
            ok("%s: „%s“ sedí u svého hlavního koláče" % (name, q["label"]),
               dPar < dHub, {"kRodiči": round(dPar), "kFajfce": round(dHub)})


async def open_tool(h, label):
    for attempt in range(3):
        items = await h.ev("[...document.querySelectorAll('.gm-item')].map(e => e.getAttribute('title') || '')")
        if not items:
            annot = await rect(h, ".tb-btn[title^='Anotace']")
            await h.finger_tap(annot["x"], annot["y"])
            await asyncio.sleep(0.7)
            continue
        idx = next((i for i, t in enumerate(items) if t.lower().startswith(label.lower())), -1)
        if idx < 0:
            raise RuntimeError("dlaždice %r není v nabídce: %r" % (label, items))
        it = await rect(h, ".gm-item", idx)
        await h.finger_tap(it["x"], it["y"])
        await asyncio.sleep(0.9)
        return
    raise RuntimeError("nepodařilo se otevřít nabídku nástrojů")


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(VW, VH, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','gesture');"
                   "localStorage.setItem('noty.textBorder','0');"
                   "localStorage.setItem('noty.hlMode','three');"
                   "localStorage.setItem('noty.hlRectHeight','30')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(4), pages=4, reset=False)
        # open_song si nastavuje vlastní (tabletový) viewport — náš musí být AŽ po něm
        await h.set_tablet(VW, VH, 2)
        await h.ev("localStorage.setItem('topbarHidden','0')")
        await h.ev("window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message)));"
                   "window.addEventListener('unhandledrejection',e=>window.__errs.push(String(e.reason)))")

        # --- text: tři hlavní koláče -----------------------------------------
        await open_tool(h, "text")
        st = await h.ev(DUMP)
        ok("text: tři koláče", len(st["pies"]) == 3, [p["label"] for p in st["pies"]])
        ok("text: popisky", [p["label"] for p in st["pies"]] == ["Barva", "Velikost", "Rámeček"],
           [p["label"] for p in st["pies"]])
        check_layout(ok, "text/3", st)
        text_col = await h.ev("getComputedStyle(document.documentElement).getPropertyValue('--text').trim()")
        # hex → rgb(), aby šlo srovnat s computed fill
        hx = text_col.lstrip('#')
        want = "rgb(%d, %d, %d)" % (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))
        ok("text: popisek je plná barva textu (ne tlumená)",
           all(p["labelColor"] == want for p in st["pies"]),
           {"cile": want, "popisky": [p["labelColor"] for p in st["pies"]]})
        ok("text: popisek je dost velký (≥ 12 px)",
           all(float((p["labelSize"] or "0px")[:-2]) >= 12 for p in st["pies"]),
           [p["labelSize"] for p in st["pies"]])
        await shot(h, "/tmp/pie-3.png")

        # --- „Rámeček: ano“ → dva vedlejší --------------------------------
        await tap_sector(h, 2, 1)
        st = await h.ev(DUMP)
        ok("text: po „ano“ je koláčů pět", len(st["pies"]) == 5, [p["label"] for p in st["pies"]])
        ok("text: Šířka a Styl rámu jsou VEDLEJŠÍ",
           [p["minor"] for p in st["pies"]] == [False, False, False, True, True],
           [p["minor"] for p in st["pies"]])
        check_layout(ok, "text/5", st)
        await shot(h, "/tmp/pie-5.png")

        # zpět na „ne“ → vedlejší zmizí
        await tap_sector(h, 2, 0)
        st = await h.ev(DUMP)
        ok("text: po „ne“ jsou zase tři koláče", len(st["pies"]) == 3,
           [p["label"] for p in st["pies"]])
        await h.ev("(() => { const svg = document.querySelector('.pie-svg');"
                   " svg.dispatchEvent(new PointerEvent('pointercancel', {bubbles:true})); return 1 })()")
        await asyncio.sleep(0.4)

        # --- zvýrazňovač: Volně → Šířka, Obdélník → Výška ------------------
        await open_tool(h, "zvýraz")
        st = await h.ev(DUMP)
        ok("zvýrazňovač: dva hlavní koláče", len(st["pies"]) == 2, [p["label"] for p in st["pies"]])
        check_layout(ok, "zvýraz/2", st)
        await shot(h, "/tmp/pie-hl-2.png")

        mode_i = [p["label"] for p in st["pies"]].index("Způsob")
        await tap_sector(h, mode_i, 2)          # Volně
        st = await h.ev(DUMP)
        ok("zvýrazňovač: „Volně“ přidá Šířku jako vedlejší",
           [p["label"] for p in st["pies"]] == ["Barva", "Způsob", "Šířka"],
           [p["label"] for p in st["pies"]])
        ok("zvýrazňovač: Šířka je vedlejší", st["pies"][2]["minor"] if len(st["pies"]) > 2 else None, st["pies"])
        check_layout(ok, "zvýraz/free", st)
        await shot(h, "/tmp/pie-hl-free.png")

        await tap_sector(h, mode_i, 1)          # Obdélník
        st = await h.ev(DUMP)
        ok("zvýrazňovač: „Obdélník“ přidá Výšku jako vedlejší",
           [p["label"] for p in st["pies"]] == ["Barva", "Způsob", "Výška"],
           [p["label"] for p in st["pies"]])
        check_layout(ok, "zvýraz/rect", st)
        await shot(h, "/tmp/pie-hl-rect.png")

        # --- volba ve vedlejším koláči se opravdu propíše do aplikace -------
        st = await h.ev(DUMP)
        lab = [p["label"] for p in st["pies"]]
        vi = lab.index("Výška")
        hi = st["pies"][vi]["texts"].index("40")
        await tap_sector(h, vi, hi)
        st = await h.ev(DUMP)
        ok("zvýrazňovač: volba Výšky 40 se uloží",
           await h.ev("localStorage.getItem('noty.hlRectHeight')") == "40",
           await h.ev("localStorage.getItem('noty.hlRectHeight')"))
        ok("zvýrazňovač: Výška 40 je označená a ve středu",
           st["pies"][vi]["on"] == hi and st["pies"][vi]["hub"] == "40",
           {"on": st["pies"][vi]["on"], "hub": st["pies"][vi]["hub"]})
        ok("zvýrazňovač: koláč po volbě zůstal otevřený", len(st["pies"]) == 3,
           [p["label"] for p in st["pies"]])

        ok("žádné chyby v konzoli", not (st["errors"]), st["errors"])

    ok.report()


asyncio.run(main())
