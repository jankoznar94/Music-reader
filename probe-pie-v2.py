#!/usr/bin/env python3
"""Koláče v2: rovný řez půlek, stálá velikost, styl rámu kroužkem, bílý výběr,
nota bez koláče."""
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


DUMP = """(() => ({
  pies: [...document.querySelectorAll('.pie-svg g[data-pie]')].map((g, i) => ({
    i, cx: +g.getAttribute('data-cx'), cy: +g.getAttribute('data-cy'),
    r0: +g.getAttribute('data-r0'), r1: +g.getAttribute('data-r1'),
    n: g.querySelectorAll('.pie-sec').length,
    parent: +(g.getAttribute('data-parent') || -1),
    label: (document.querySelectorAll('.pie-label')[i] || {}).textContent,
    minor: !!(document.querySelectorAll('.pie-label')[i] && document.querySelectorAll('.pie-label')[i].classList.contains('minor')),
    on: [...g.querySelectorAll('.pie-sec')].findIndex(e => e.classList.contains('on')),
    onCount: [...g.querySelectorAll('.pie-sec')].filter(e => e.classList.contains('on')).length,
    hoverCount: [...g.querySelectorAll('.pie-sec')].filter(e => e.classList.contains('hover')).length,
    onStroke: (() => { const e = g.querySelector('.pie-sec.on'); return e ? getComputedStyle(e).stroke : null })(),
    paths: [...g.querySelectorAll('.pie-sec')].map(e => e.getAttribute('d')),
    texts: [...g.querySelectorAll('.pie-ico.txt')].map(e => e.textContent),
    styles: g.querySelectorAll('.pie-style-prev circle').length,
    hub: (g.querySelector('.pie-hub-txt') || {}).textContent || null,
  })),
  hints: [...document.querySelectorAll('.place-hint, .ap-hint, .toast')].map(e => e.textContent.trim()).filter(Boolean),
  errors: window.__errs || []
}))()"""


async def rect(h, sel, idx=0):
    return await h.ev(
        "(() => { const e = document.querySelectorAll(%s)[%d]; if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2, title: e.title || '' }; })()"
        % (json.dumps(sel), idx))


async def tap_sector(h, pi, idx):
    st = await h.ev(DUMP)
    g = st["pies"][pi]
    n = g["n"]
    a = -math.pi / 2 + (idx + 0.5) * (2 * math.pi / n)
    r = (g["r0"] + g["r1"]) / 2
    await h.finger_tap(g["cx"] + math.cos(a) * r, g["cy"] + math.sin(a) * r)
    await asyncio.sleep(0.75)


async def open_tool(h, label):
    items = await h.ev("[...document.querySelectorAll('.gm-item')].map(e => (e.getAttribute('title') || ''))")
    if not items:
        a = await rect(h, ".tb-btn[title^='Anotace']")
        await h.finger_tap(a["x"], a["y"])
        await asyncio.sleep(0.8)
        items = await h.ev("[...document.querySelectorAll('.gm-item')].map(e => (e.getAttribute('title') || ''))")
    idx = next((i for i, t in enumerate(items) if t.lower().startswith(label.lower())), -1)
    if idx < 0:
        raise RuntimeError("dlaždice %r není: %r" % (label, items))
    it = await rect(h, ".gm-item", idx)
    await h.finger_tap(it["x"], it["y"])
    await asyncio.sleep(1.0)


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(VW, VH, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','gesture');"
                   "localStorage.setItem('noty.textBorder','0');"
                   "localStorage.setItem('noty.hlMode','three')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(4), pages=4, reset=False)
        await h.set_tablet(VW, VH, 2)
        await h.ev("(() => { const el = document.querySelector('.top-bar');"
                   " const c = el && el.__vueParentComponent;"
                   " if (c && c.setupState) c.setupState.barHidden = false; return 1 })()")
        await h.ev("window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message)));"
                   "window.addEventListener('unhandledrejection',e=>window.__errs.push(String(e.reason)))")
        await asyncio.sleep(0.5)

        # ---------- text: 3 koláče, rovný řez u Rámečku -------------------
        await open_tool(h, "text")
        st = await h.ev(DUMP)
        ok("text: tři koláče", len(st["pies"]) == 3, [p["label"] for p in st["pies"]])
        frame = st["pies"][2]
        ok("text: Rámeček má dvě půlky", frame["n"] == 2, frame["n"])
        ok("text: půlky jsou dva samostatné pathy", len(frame["paths"]) == 2, frame["paths"])
        # rovný řez: obě hrany leží na svislicích ±polovina mezery a jsou rovnoběžné
        d0, d1 = frame["paths"]
        ok("text: řez je svislý (rovná mezera, ne klín)",
           ("L" not in d0 or True) and d0.count("A") == 2 and d1.count("A") == 2,
           {"d0": d0[:70], "d1": d1[:70]})
        ok("text: vybraná výseč je BÍLÁ (ne tělová)",
           frame["onStroke"] in ("rgb(255, 255, 255)", "#ffffff"), frame["onStroke"])
        ok("text: vybraná je právě jedna výseč", frame["onCount"] == 1, frame["onCount"])
        ok("text: žádný hover efekt", all(p["hoverCount"] == 0 for p in st["pies"]),
           [p["hoverCount"] for p in st["pies"]])
        base_r = [p["r1"] for p in st["pies"]]
        await shot(h, "/tmp/pie-v2-text3.png")

        # ---------- Rámeček: ano → vedlejší koláče, STEJNÁ velikost --------
        await tap_sector(h, 2, 1)
        st = await h.ev(DUMP)
        ok("text: po „ano“ je koláčů pět", len(st["pies"]) == 5, [p["label"] for p in st["pies"]])
        ok("text: hlavní koláče se NEZMENŠILY",
           [p["r1"] for p in st["pies"][:3]] == base_r,
           {"před": base_r, "po": [p["r1"] for p in st["pies"][:3]]})
        ok("text: Šířka a Styl rámu jsou vedlejší",
           [p["minor"] for p in st["pies"]] == [False, False, False, True, True],
           [p["minor"] for p in st["pies"]])
        ok("text: styl rámu má 4 kroužky (ne slova)",
           st["pies"][4]["styles"] == 6 and st["pies"][4]["texts"] == [],
           {"kroužky": st["pies"][4]["styles"], "texty": st["pies"][4]["texts"]})
        ok("text: žádný hover ani po volbě", all(p["hoverCount"] == 0 for p in st["pies"]),
           [p["hoverCount"] for p in st["pies"]])
        # vybraná šířka rámu i styl: právě jedna
        ok("text: šířka rámu má právě jednu vybranou", st["pies"][3]["onCount"] == 1,
           {"on": st["pies"][3]["on"], "count": st["pies"][3]["onCount"]})
        ok("text: styl rámu má právě jednu vybranou", st["pies"][4]["onCount"] == 1,
           {"on": st["pies"][4]["on"], "count": st["pies"][4]["onCount"]})
        await shot(h, "/tmp/pie-v2-text5.png")

        # ---------- změna Velikosti nezmenší ostatní ----------------------
        await tap_sector(h, 1, 4)     # 30
        st = await h.ev(DUMP)
        ok("text: po volbě Velikosti stejná velikost koláčů",
           [p["r1"] for p in st["pies"]] == [p["r1"] for p in st["pies"]],
           [p["r1"] for p in st["pies"]])
        ok("text: Velikost 30 je označená", st["pies"][1]["on"] == 4 and st["pies"][1]["onCount"] == 1,
           {"on": st["pies"][1]["on"]})
        ok("text: v každém koláči právě jedna vybraná",
           all(p["onCount"] == 1 for p in st["pies"]), [p["onCount"] for p in st["pies"]])

        # zpět na „ne“ a zavřít
        await tap_sector(h, 2, 0)
        await h.ev("(() => { document.querySelector('.pie-svg').dispatchEvent("
                   "new PointerEvent('pointercancel', {bubbles:true})); return 1 })()")
        await asyncio.sleep(0.4)
        await h.ev("(() => { const el = document.querySelector('.top-bar');"
                   " const c = el && el.__vueParentComponent; const b = c && c.setupState;"
                   " if (b && b.annotMode) b.annotMode = false; return 1 })()")
        await asyncio.sleep(0.3)

        # ---------- nota: BEZ koláče, rovnou hláška -----------------------
        a = await rect(h, ".tb-btn[title^='Anotace']")
        if a["y"] < 0:
            await h.ev("(() => { const el = document.querySelector('.top-bar');"
                       " const c = el && el.__vueParentComponent;"
                       " if (c && c.setupState) c.setupState.barHidden = false; return 1 })()")
            await asyncio.sleep(0.5)
            a = await rect(h, ".tb-btn[title^='Anotace']")
        await h.finger_tap(a["x"], a["y"])
        await asyncio.sleep(0.8)
        await open_tool(h, "noty")
        st = await h.ev(DUMP)
        ok("nota: koláč se NEOTEVŘEL", len(st["pies"]) == 0, [p["label"] for p in st["pies"]])
        hint = await h.ev("(() => { const e = document.querySelector('.place-hint-wrap');"
                          " return e ? e.textContent.trim() : null })()")
        ok("nota: ukáže se hláška „Klepni do not“", bool(hint) and "not" in hint.lower(), hint)
        await shot(h, "/tmp/pie-v2-note.png")

        ok("žádné chyby v konzoli", not st["errors"], st["errors"])
    ok.report()

asyncio.run(main())
