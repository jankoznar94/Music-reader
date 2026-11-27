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
        # lišta se po open_song schová → vrátit přes stav Vue komponenty
        await h.ev("(() => { const el = document.querySelector('.top-bar');"
                   " const c = el && el.__vueParentComponent;"
                   " if (c && c.setupState) c.setupState.barHidden = false; return 1 })()")
        await asyncio.sleep(0.4)

        annot = await rect(h, ".tb-btn[title^='Anotace']")
        # --- 1) lišta nástrojů: puntík + spojka ------------------------------
        await h.touch("touchStart", [(annot["x"], annot["y"], 12)])
        await asyncio.sleep(0.4)
        st = await gm_state(h)
        ok("lišta nástrojů se otevřela", st["open"] and len(st["items"]) == 10, st["items"])
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

        # --- 6) ŤUKNUTÍ na ✏️ = stejná nabídka, jen bez pruhu a pod tlačítkem ---
        # Uklidit: vypnout anotaci (jinak ťuknutí jen vypíná režim).
        await h.ev("window.__barDev.annotMode.value = false")
        await asyncio.sleep(0.25)
        await h.finger_tap(annot["x"], annot["y"])
        await asyncio.sleep(0.5)
        st = await gm_state(h)
        ok("ťuknutí na ✏️ otevře nabídku nástrojů", st["open"] and len(st["items"]) == 10, st["items"])
        ok("lišta stojí PŘÍMO POD tlačítkem (ne vlevo)",
           bool(st["col"]) and abs((st["col"]["l"] + st["col"]["r"]) / 2 - annot["x"]) < 3,
           {"col": st["col"], "btn_x": annot["x"]})
        ok("u ťuknutí není pruh pro prst ani puntík",
           st["band"] is None and st["dot"] is None, {"band": st["band"], "dot": st["dot"]})
        ok("anotace se ťuknutím zapnula",
           await h.ev("!!document.querySelector('.annot-layer.active')"))
        i4 = await rect(h, ".gm-item", 4)     # Noty
        await h.finger_tap(i4["x"], i4["y"])
        await asyncio.sleep(0.55)
        st = await gm_state(h)
        ok("klepnutí na kolečko vybralo nástroj",
           (await h.ev("window.__barDev.tool.value")) == "note", await h.ev("window.__barDev.tool.value"))
        ok("nota koláč NEOTEVÍRÁ (rovnou hláška)",
           not st["pie"] and "not" in (st["hint"] or "").lower(), {"pie": st["pie"], "hint": st["hint"]})

        # --- 7) nabídka po ťuknutí se zavře dotykem mimo ----------------------
        await h.ev("window.__barDev.annotMode.value = false")
        await asyncio.sleep(0.2)
        await h.finger_tap(annot["x"], annot["y"])
        await asyncio.sleep(0.45)
        ok("nabídka je otevřená", (await gm_state(h))["open"])
        await h.finger_tap(400, 900)
        await asyncio.sleep(0.35)
        st = await gm_state(h)
        ok("dotyk mimo nabídku ji zavře", not st["open"], st)

        # --- 8) Druhé ťuknutí nabídku zavře a tlačítko přestane svítit ---------
        await h.ev("window.__barDev.annotMode.value = false")
        await asyncio.sleep(0.2)
        await h.finger_tap(annot["x"], annot["y"])
        await asyncio.sleep(0.45)
        lit = await h.ev("(() => { const e = document.querySelector(\".tb-btn[title^='Anotace']\");"
                         " return { menu: !!document.querySelector('.gm-root'), lit: e.classList.contains('on') }; })()")
        ok("první ťuknutí: nabídka otevřená a tlačítko svítí", lit["menu"] and lit["lit"], lit)
        await h.finger_tap(annot["x"], annot["y"])
        await asyncio.sleep(0.5)
        lit2 = await h.ev("(() => { const e = document.querySelector(\".tb-btn[title^='Anotace']\");"
                          " return { menu: !!document.querySelector('.gm-root'), lit: e.classList.contains('on'),"
                          "          annot: window.__barDev.annotMode.value }; })()")
        ok("druhé ťuknutí: nabídka zmizí", not lit2["menu"], lit2)
        ok("druhé ťuknutí: tlačítko přestane svítit", not lit2["lit"], lit2)
        ok("druhé ťuknutí: anotační režim se vypne", lit2["annot"] is False, lit2)

        # --- 9) ✕ v liště ukončí anotační režim ------------------------------
        await h.finger_tap(annot["x"], annot["y"])
        await asyncio.sleep(0.45)
        last = await h.ev("(() => { const a = document.querySelectorAll('.gm-item');"
                          " const e = a[a.length - 1]; const r = e.getBoundingClientRect();"
                          " return { x: r.left + r.width / 2, y: r.top + r.height / 2, title: e.title }; })()")
        ok("poslední kolečko lišty je Konec anotace", last["title"] == "Konec anotace", last)
        await h.finger_tap(last["x"], last["y"])
        await asyncio.sleep(0.45)
        st = await h.ev("(() => ({ annot: window.__barDev.annotMode.value,"
                        " menu: !!document.querySelector('.gm-root'),"
                        " lit: document.querySelector(\".tb-btn[title^='Anotace']\").classList.contains('on') }))()")
        ok("✕ vypne anotační režim", st["annot"] is False, st)
        ok("✕ zavře lištu i zhasne tlačítko", (not st["menu"]) and (not st["lit"]), st)

        # --- 10) Barevný koláč: celá výseč má barvu, střed taky --------------
        await h.finger_tap(annot["x"], annot["y"])
        await asyncio.sleep(0.45)
        i0 = await rect(h, ".gm-item", 0)      # Tužka
        await h.finger_tap(i0["x"], i0["y"])
        await asyncio.sleep(0.6)
        cols = await h.ev("(() => ([...document.querySelectorAll('.pie-sec.col')].map(e => ({\n"
                          "  fill: e.style.fill, w: e.getAttribute('stroke-width') }))))()")
        ok("barevné výseče jsou vyplněné BARVOU (ne malé kroužky)",
           bool(cols) and all(c["fill"] for c in cols), cols[:4])
        dots = await h.ev("document.querySelectorAll('.pie-dot').length")
        ok("v barevných výsečích nejsou žádné malé kroužky", dots == 0, dots)
        hub = await h.ev("(() => { const g = document.querySelector('g[data-pie=\"0\"]');"
                         " const c = [...g.querySelectorAll('circle')].find(x => x.getAttribute('fill') && x.getAttribute('fill') !== 'none');"
                         " const bg = g.querySelector('.pie-hub-bg');"
                         " return c ? { r: +c.getAttribute('r'), bgR: +bg.getAttribute('r'), fill: c.getAttribute('fill') } : null; })()")
        ok("střed koláče je CELÝ ve vybrané barvě",
           bool(hub) and hub["r"] >= hub["bgR"] - 8, hub)
        hub_px = await h.ev("(() => { const l = document.querySelector('.pie-check-bg'); const r = l.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()")
        await h.finger_tap(hub_px["x"], hub_px["y"])
        await asyncio.sleep(0.5)

        # --- 11) Hláška u tužky je uprostřed a velká --------------------------
        hint = await h.ev("(() => { const e = document.querySelector('.place-hint'); if (!e) return null;"
                          " const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);"
                          " return { text: e.textContent, cy: r.top + r.height / 2, fs: parseFloat(cs.fontSize),"
                          "          scrim: !!document.querySelector('.place-hint-scrim') }; })()")
        ok("hláška se ukáže i u tužky", bool(hint) and "not" in hint["text"].lower(), hint)
        ok("hláška je UPROSTŘED obrazovky", bool(hint) and abs(hint["cy"] - 640) < 6, hint and hint["cy"])
        ok("hláška je velká (≥ 18 px)", bool(hint) and hint["fs"] >= 18, hint and hint["fs"])
        ok("hláška má lehké ztmavení", bool(hint) and hint["scrim"], hint)
        await h.finger_tap(400, 1000)
        await asyncio.sleep(0.4)

    ok.report()


asyncio.run(main())
