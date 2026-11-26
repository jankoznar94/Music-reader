#!/usr/bin/env python3
"""Animovaný režim ovládání (listopad 2026) — nabídka tahem z tlačítka ✏️.

Ověřuje STAV v reálném prohlížeči:
  1. nastavení v knihovně (ozubené kolo) má přepínač a uloží režim
  2. výchozí režim je TLAČÍTKOVÝ (nic se nemění pod rukama)
  3. podržení ✏️ otevře svislou nabídku (.gm-col) s kolečky
  4. podmenu (.gm-sub) je NAPRAVO od sloupce a hlavní nabídka se ztlumí
  5. tahem na jiné kolečko se označení přepne a podmenu se vymění
  6. tahem na volbu podmenu + puštěním se nastaví nástroj (nota) i předvolba
  7. plovoucí panel anotací je v animovaném režimu schovaný
  8. krátké ťuknutí na ✏️ dál přepíná anotační režim (ne nabídku)
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

APP = os.environ.get("NOTY_APP") or os.environ.get("APP_URL") or m.APP_URL


async def rect(h, sel, idx=0):
    return await h.ev(
        "(() => { const e = document.querySelectorAll(%s)[%d]; if (!e) return null;"
        " const r = e.getBoundingClientRect();"
        " return { x: r.left + r.width/2, y: r.top + r.height/2,"
        "          left: r.left, right: r.right, top: r.top, bottom: r.bottom,"
        "          w: r.width, h: r.height }; })()" % (json.dumps(sel), idx))


async def state(h):
    return await h.ev(
        "(() => ({"
        "  tool: window.__barDev ? window.__barDev.tool.value : null,"
        "  mode: window.__barDev ? window.__barDev.controlMode.value : null,"
        "  annot: !!document.querySelector('.annot-layer.active'),"
        "  panel: !!document.querySelector('.annot-panel'),"
        "  menu: !!document.querySelector('.gm-root'),"
        "  sub: !!document.querySelector('.gm-sub'),"
        "  items: document.querySelectorAll('.gm-item').length,"
        "  opts: document.querySelectorAll('.gm-opt').length,"
        "  active: [...document.querySelectorAll('.gm-item')].findIndex(e => e.classList.contains('active')),"
        "  dimmed: document.querySelectorAll('.gm-item.dim').length,"
        "  sel: !!document.querySelector('.gm-item .gm-circle.sel'),"
        "  optOn: [...document.querySelectorAll('.gm-opt')].findIndex(e => e.classList.contains('on')),"
        "}))()")


async def long_press_to(h, cx, cy, path, hold=0.32):
    """Prst: podržení v místě, pak pohyb po bodech `path`, pak puštění."""
    await h.touch("touchStart", [(cx, cy, 12)])
    await asyncio.sleep(hold)
    for (x, y) in path:
        await h.touch("touchMove", [(x, y, 12)])
        await asyncio.sleep(0.12)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.45)


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()

        # --- 1) Knihovna: ozubené kolo a výchozí režim ------------------------
        st = await h.ev("(() => ({ gear: !!document.querySelector('.gear-btn'),"
                        " mode: localStorage.getItem('noty.controlMode') }))()")
        ok("knihovna má tlačítko ozubeného kola", st["gear"], st)
        ok("výchozí režim je tlačítkový (klíč chybí)", st["mode"] is None, st["mode"])

        await h.ev("document.querySelector('.gear-btn').click()")
        await asyncio.sleep(0.35)
        ok("nastavení se otevřelo (.set-card)", bool(await h.ev("!!document.querySelector('.set-card')")))
        labels = await h.ev("([...document.querySelectorAll('.set-seg button')].map(b => b.textContent.trim()))")
        ok("nastavení nabízí Tlačítkový i Animovaný", labels == ["Tlačítkový", "Animovaný"], labels)
        on = await h.ev("(document.querySelector('.set-seg button.on') || {}).textContent")
        ok("předvybraný je Tlačítkový", (on or "").strip() == "Tlačítkový", on)
        # přepni na animovaný a zkontroluj uložení
        await h.ev("([...document.querySelectorAll('.set-seg button')].find(b => b.textContent.trim() === 'Animovaný')).click()")
        await asyncio.sleep(0.25)
        mode = await h.ev("localStorage.getItem('noty.controlMode')")
        ok("volba Animovaný se uložila", mode == "gesture", mode)
        await h.ev("document.querySelector('.set-close').click()")
        await asyncio.sleep(0.2)
        # horní lišta je po startu schovaná (tap na střed ji ukáže) — pro test
        # ji rovnou odškrteneme, jinak je tlačítko ✏️ mimo obraz
        await h.ev("localStorage.setItem('topbarHidden', '0')")

        # --- 2) Otevři skladbu (nový profil, DB nemazat) ---------------------
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        st = await state(h)
        ok("čtečka běží v animovaném režimu", st["mode"] == "gesture", st["mode"])

        btn = await rect(h, ".tb-btn[title^='Anotace']")
        ok("tlačítko ✏️ existuje", btn is not None, btn)

        # --- 3) Podržení otevře nabídku --------------------------------------
        await h.touch("touchStart", [(btn["x"], btn["y"], 12)])
        await asyncio.sleep(0.36)
        st = await state(h)
        ok("podržení otevřelo nabídku (.gm-root)", st["menu"], st)
        ok("nabídka má 9 koleček nástrojů", st["items"] == 9, st["items"])
        ok("podmenu se otevřelo k tužce", st["sub"], st["sub"])
        ok("vybraná tužka je barevná (výchozí nástroj)", st["sel"], st)
        ok("hlavní nabídka se ztlumila (8 z 9)", st["dimmed"] == 8, st["dimmed"])

        col = await rect(h, ".gm-col")
        sub = await rect(h, ".gm-sub")
        ok("podmenu je NAPRAVO od sloupce", bool(col and sub) and sub["left"] >= col["right"] - 1,
           {"colRight": col and col["right"], "subLeft": sub and sub["left"]})
        ok("podmenu se vejde na displej", bool(sub) and sub["right"] <= 800, {"right": sub and sub["right"]})

        # --- 4) Tahem na jiné kolečko se přepne označení i podmenu -----------
        item4 = await rect(h, ".gm-item", 4)   # Noty
        await h.touch("touchMove", [(item4["x"], item4["y"], 12)])
        await asyncio.sleep(0.3)
        st = await state(h)
        ok("tah označil 5. kolečko (Noty)", st["active"] == 4, st["active"])
        ok("podmenu se vyměnilo na noty (12 voleb)", st["opts"] == 12, st["opts"])
        ok("ztlumených je pořád 8", st["dimmed"] == 8, st["dimmed"])
        ok("vybraný nástroj zůstává barevný i se ztlumenou nabídkou", st["sel"], st)

        # --- 5) Volba podmenu + puštění -------------------------------------
        opt = await rect(h, ".gm-opt", 3)      # osminová nota
        await h.touch("touchMove", [(opt["x"], opt["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.5)
        st = await state(h)
        ok("puštění nastavilo nástroj Noty", st["tool"] == "note", st["tool"])
        ok("nabídka zmizela", not st["menu"], st)
        ok("v animovaném režimu je plovoucí panel schovaný", not st["panel"], st)

        # --- 6) Krátké ťuknutí dál přepíná anotaci ---------------------------
        await h.finger_tap(btn["x"], btn["y"])
        st = await state(h)
        ok("krátké ťuknutí vypnulo anotaci (ne nabídku)", (not st["annot"]) and (not st["menu"]),
           {"annot": st["annot"], "menu": st["menu"]})

        # --- 7) Zpět na tlačítkový režim: panel zase funguje ----------------
        await h.ev("localStorage.setItem('noty.controlMode', 'button')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        await h.finger_tap(btn["x"], btn["y"])
        st = await state(h)
        ok("tlačítkový režim ukáže plovoucí panel", st["panel"], st)
        ok("tlačítkový režim nabídku tahem neotevírá", not st["menu"], st)

    ok.report()


asyncio.run(main())
