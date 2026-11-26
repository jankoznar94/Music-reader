#!/usr/bin/env python3
"""Svislé lišty skupin + puntík/spojka + hláška „vyber místo“ (listopad 2026).

Ověřuje v reálném prohlížeči:
  1. lišta nástrojů má puntík ve sloupci pod tlačítkem a spojku k vybranému kolečku
  2. puntík sleduje prst a spojka míří na kolečko, které je právě vybrané
  3. skupina „Záložky, značky, skoky, čísla taktů“ se rozbalí dotekem (4 kolečka)
  4. puštění bez pohybu nechá lištu otevřenou; klepnutí na kolečko otevře okno
  5. skupina „Zobrazení“ (zvětšení, rotace, vycentrování) otevře okno zoomu
  6. dotyk mimo lištu ji zavře a nic nenakreslí
  7. po fajfce v koláči se objeví hláška „vyber místo“ a klepnutím do not zmizí
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
        " return { x: r.left + r.width/2, y: r.top + r.height/2,"
        "          left: r.left, right: r.right, top: r.top, bottom: r.bottom,"
        "          w: r.width, h: r.height }; })()" % (json.dumps(sel), idx))


async def gm_state(h):
    return await h.ev(
        "(() => ({ open: !!document.querySelector('.gm-root'),"
        "  mode: document.querySelector('.gm-root.panel') ? 'panel' : 'tools',"
        "  items: [...document.querySelectorAll('.gm-item')].map(i => (i.title || '')),"
        "  active: [...document.querySelectorAll('.gm-item')].findIndex(e => e.classList.contains('active')),"
        "  col: (() => { const c = document.querySelector('.gm-col'); if (!c) return null;"
        "    const r = c.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom }; })(),"
        "  band: (() => { const b = document.querySelector('.gm-track-band'); if (!b) return null;"
        "    const r = b.getBoundingClientRect(); return { l: r.left, r: r.right, t: r.top, b: r.bottom }; })(),"
        "  dot: (() => { const d = document.querySelector('.gm-track-dot'); if (!d) return null;"
        "    return { cx: +d.getAttribute('cx'), cy: +d.getAttribute('cy') }; })(),"
        "  link: (() => { const l = document.querySelector('.gm-track-link'); if (!l) return null;"
        "    return { x1: +l.getAttribute('x1'), y1: +l.getAttribute('y1'),"
        "             x2: +l.getAttribute('x2'), y2: +l.getAttribute('y2') }; })(),"
        "  marks: !!document.querySelector('.marks-panel'),"
        "  zoom: !!document.querySelector('.zoom-panel'),"
        "  pie: !!document.querySelector('.pie-svg'),"
        "  hint: (document.querySelector('.place-hint') || {}).textContent || ''"
        "}))()")


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await h.ev("localStorage.setItem('noty.controlMode','gesture')")
        await h.ev("sessionStorage.clear()")
        await h.open()
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        await h.ev("localStorage.setItem('topbarHidden','0')")

        annot = await rect(h, ".tb-btn[title^='Anotace']")
        # --- 1) lišta nástrojů: puntík + spojka ------------------------------
        await h.touch("touchStart", [(annot["x"], annot["y"], 12)])
        await asyncio.sleep(0.4)
        st = await gm_state(h)
        ok("lišta nástrojů se otevřela", st["open"] and len(st["items"]) == 9, st["items"])
        ok("ve sloupci pod tlačítkem je pruh (oblast pro puntík)",
           bool(st["band"]) and abs(st["band"]["l"] + st["band"]["r"]) / 2 == 0 or bool(st["band"]), st["band"])
        ok("pruh stojí pod tlačítkem ✏️",
           bool(st["band"]) and st["band"]["l"] <= annot["x"] <= st["band"]["r"], {"band": st["band"], "annot_x": annot["x"]})
        ok("puntík i spojka existují", bool(st["dot"]) and bool(st["link"]), {"dot": st["dot"], "link": st["link"]})

        col = st["col"]
        # prst do poloviny lišty (mimo ni, napravo) → puntík se posune
        y_mid = (col["t"] + col["b"]) / 2
        await h.touch("touchMove", [(col["r"] + 140, y_mid, 12)])
        await asyncio.sleep(0.2)
        st2 = await gm_state(h)
        ok("puntík sleduje svislou polohu prstu",
           abs(st2["dot"]["cy"] - y_mid) < 6, {"dot_y": st2["dot"]["cy"], "finger": y_mid})
        ok("puntík sedí ve sloupci tlačítka (x)",
           abs(st2["dot"]["cx"] - annot["x"]) < 2, {"dot_x": st2["dot"]["cx"], "annot_x": annot["x"]})
        ok("spojka vede z puntíku k vybranému kolečku",
           bool(st2["link"]) and abs(st2["link"]["y1"] - st2["dot"]["cy"]) < 1
           and st2["link"]["x2"] < st2["dot"]["cx"], st2["link"])
        ok("vybrané kolečko odpovídá poloze prstu",
           st2["active"] == round((y_mid - (col["t"] + 28)) / 50), st2["active"])
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.5)
        ok("po puštění se lišta zavřela", not (await gm_state(h))["open"])
        # Puštění na „Textu“ otevřelo koláč voleb — ten musí pryč, jinak jeho
        # scrim leží přes hlavní lištu a skupinové tlačítko nepustí dotyk dál.
        st = await gm_state(h)
        if st["pie"]:
            hub = await rect(h, ".pie-check-bg")
            await h.finger_tap(hub["x"], hub["y"])
            await asyncio.sleep(0.45)

        # --- 2) skupina Záložky / značky / skoky / čísla ----------------------
        nav = await rect(h, ".tb-btn[data-gm-group='navig']")
        ok("tlačítko skupiny orientace existuje", nav is not None, nav)
        await h.touch("touchStart", [(nav["x"], nav["y"], 12)])
        await asyncio.sleep(0.35)
        st = await gm_state(h)
        ok("skupina se rozbalila dotekem", st["open"] and st["mode"] == "panel", st["mode"])
        ok("skupina má 4 položky",
           st["items"] == ["Záložky", "Značky", "Skoky", "Čísla taktů"], st["items"])
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.3)
        ok("puštění bez pohybu nechá lištu otevřenou", (await gm_state(h))["open"])

        # klepnutí na kolečko Značky → panel značek
        item = await rect(h, ".gm-item", 1)
        await h.finger_tap(item["x"], item["y"])
        await asyncio.sleep(0.5)
        st = await gm_state(h)
        ok("klepnutí na Značky otevřelo jejich okno", st["marks"], st)
        ok("lišta se při volbě zavřela", not st["open"], st)

        # --- 3) skupina Zobrazení --------------------------------------------
        await h.ev("(() => { const b = document.querySelector('.marks-panel .mk-close, .marks-panel .panel-close'); if (b) b.click(); return true; })()")
        await asyncio.sleep(0.3)
        view = await rect(h, ".tb-btn[data-gm-group='view']")
        ok("tlačítko skupiny zobrazení existuje", view is not None, view)
        await h.touch("touchStart", [(view["x"], view["y"], 12)])
        await asyncio.sleep(0.35)
        st = await gm_state(h)
        ok("skupina zobrazení má 3 položky",
           st["items"] == ["Zvětšení", "Rotace", "Vycentrovat"], st["items"])
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.3)
        z = await rect(h, ".gm-item", 0)
        await h.finger_tap(z["x"], z["y"])
        await asyncio.sleep(0.5)
        st = await gm_state(h)
        ok("klepnutí na Zvětšení otevřelo okno zoomu", st["zoom"], st)
        ok("lišta zobrazení se zavřela", not st["open"], st)

        # --- 4) dotyk mimo lištu ji zavře a nic nenakreslí -------------------
        await h.ev("(() => { const b = document.querySelector('.zoom-panel .panel-close, .zoom-panel .zp-close'); if (b) b.click(); return true; })()")
        await asyncio.sleep(0.3)
        await h.touch("touchStart", [(nav["x"], nav["y"], 12)])
        await asyncio.sleep(0.35)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.3)
        before = await h.ev("window.__barDev.annotations.value.items.length")
        await h.finger_tap(400, 900)
        await asyncio.sleep(0.4)
        st = await gm_state(h)
        after = await h.ev("window.__barDev.annotations.value.items.length")
        ok("dotyk mimo lištu ji zavře", not st["open"], st)
        ok("dotyk mimo lištu nic nenakreslí", before == after, {"before": before, "after": after})

        # --- 5) hláška „vyber místo“ ----------------------------------------
        await h.touch("touchStart", [(annot["x"], annot["y"], 12)])
        await asyncio.sleep(0.4)
        col = (await gm_state(h))["col"]
        i3 = await rect(h, ".gm-item", 3)     # Text
        await h.touch("touchMove", [(col["r"] + 140, i3["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        st = await gm_state(h)
        ok("text: koláč voleb se otevřel", st["pie"], st)
        hub = await rect(h, ".pie-check-bg")
        await h.finger_tap(hub["x"], hub["y"])
        await asyncio.sleep(0.45)
        st = await gm_state(h)
        ok("po fajfce se ukáže hláška o výběru místa",
           "místo" in st["hint"].lower(), st["hint"])
        await h.finger_tap(400, 900)
        await asyncio.sleep(0.45)
        ok("klepnutí do not hlášku schová", not (await gm_state(h))["hint"])
        # uklidit dialog, pokud se otevřel
        await h.ev("(() => { const b = document.querySelector('.text-input-card .btn-ok, .text-input-card .btn-done'); if (b) b.click(); return true; })()")

    ok.report()


asyncio.run(main())
