#!/usr/bin/env python3
"""Animovaný režim ovládání (listopad 2026) — lišta vlevo + kruhový výběr.

Průběh, který se ověřuje:
  1. nastavení v knihovně (ozubené kolo) má přepínač a uloží režim
  2. výchozí režim je TLAČÍTKOVÝ
  3. podržení ✏️ → duch tlačítka odletí a lišta se otevře VLEVO u okraje
  4. svislý tah vybírá nástroj i s prstem MIMO lištu (rozhoduje jen y)
  5. puštění nástroj vybere a otevře KOLÁČ voleb uprostřed stránky
  6. tahem do kruhu se označí výseč, puštění volbu potvrdí
  7. nástroj bez voleb (Ruka) koláč neotevře
  8. klik mimo koláč ho jen zavře
  9. krátké ťuknutí na ✏️ dál přepíná anotační režim
 10. tlačítkový režim má starý plovoucí panel a žádné gesto
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
        "  ghost: !!document.querySelector('.gm-ghost'),"
        "  items: document.querySelectorAll('.gm-item').length,"
        "  active: [...document.querySelectorAll('.gm-item')].findIndex(e => e.classList.contains('active')),"
        "  pie: !!document.querySelector('.pie-svg'),"
        "  sectors: document.querySelectorAll('.pie-sec').length,"
        "  hover: [...document.querySelectorAll('.pie-sec')].findIndex(e => e.classList.contains('hover')),"
        "  vw: innerWidth, vh: innerHeight,"
        "}))()")


async def long_press(h, btn, hold=0.32):
    await h.touch("touchStart", [(btn["x"], btn["y"], 12)])
    await asyncio.sleep(hold)


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
        await h.ev("([...document.querySelectorAll('.set-seg button')].find(b => b.textContent.trim() === 'Animovaný')).click()")
        await asyncio.sleep(0.25)
        mode = await h.ev("localStorage.getItem('noty.controlMode')")
        ok("volba Animovaný se uložila", mode == "gesture", mode)
        await h.ev("document.querySelector('.set-close').click()")
        await asyncio.sleep(0.2)
        # horní lišta je po startu schovaná — pro test ji rovnou odškrteneme
        await h.ev("localStorage.setItem('topbarHidden', '0')")

        # --- 2) Skladba ------------------------------------------------------
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        st = await state(h)
        ok("čtečka běží v animovaném režimu", st["mode"] == "gesture", st["mode"])
        btn = await rect(h, ".tb-btn[title^='Anotace']")
        ok("tlačítko ✏️ existuje", btn is not None, btn)

        # --- 3) Podržení: duch + lišta VLEVO u okraje ------------------------
        await long_press(h, btn)
        st = await state(h)
        ok("podržení otevřelo lištu (.gm-col)", st["menu"], st)
        ok("duch tlačítka je vidět", st["ghost"], st)
        ok("lišta má 9 koleček", st["items"] == 9, st["items"])
        col = await rect(h, ".gm-col")
        ok("lišta je u LEVÉHO okraje (ne pod tlačítkem)", col["left"] <= 12, col["left"])
        ok("lišta začíná POD hlavní lištou", col["top"] >= 50, col["top"])
        ok("lišta nepřekáží prstu u tlačítka", abs(col["left"] - btn["x"]) > 100,
           {"colLeft": col["left"], "btnX": btn["x"]})

        # --- 4) Svislý tah i MIMO lištu -------------------------------------
        item2 = await rect(h, ".gm-item", 2)   # Guma
        await h.touch("touchMove", [(col["right"] + 140, item2["y"], 12)])
        await asyncio.sleep(0.25)
        st = await state(h)
        ok("prst vpravo MIMO lištu vybere podle svislé polohy", st["active"] == 2, st["active"])

        # --- 5) Puštění na notách → koláč -----------------------------------
        item4 = await rect(h, ".gm-item", 4)   # Noty
        await h.touch("touchMove", [(col["right"] + 140, item4["y"], 12)])
        await asyncio.sleep(0.25)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.8)
        st = await state(h)
        ok("lišta se zavřela", not st["menu"], st)
        ok("nástroj se vybral (Noty)", st["tool"] == "note", st["tool"])
        ok("otevřel se KOLÁČ voleb", st["pie"], st)
        ok("koláč má 12 výsečí (5 not + 5 pomlk + 2 obloučky)", st["sectors"] == 12, st["sectors"])

        # --- 6) Kruhový tah na výseč + potvrzení ----------------------------
        geo = await h.ev(
            "(() => { const hole=document.querySelector('.pie-hole');"
            " const r=document.querySelector('.pie-ring');"
            " return { cx: +hole.getAttribute('cx'), cy: +hole.getAttribute('cy'),"
            "          r0: +hole.getAttribute('r'), r: +r.getAttribute('r') }; })()")
        ok("koláč má střed na středu displeje",
           abs(geo["cx"] - st["vw"] / 2) < 2 and abs(geo["cy"] - st["vh"] / 2) < 2, geo)

        step = 2 * math.pi / 12
        ang = -math.pi / 2 + (3 + 0.5) * step          # 4. výseč (osminová nota)
        rr = (geo["r0"] + geo["r"]) / 2
        px = geo["cx"] + math.cos(ang) * rr
        py = geo["cy"] + math.sin(ang) * rr
        await h.touch("touchStart", [(geo["cx"], geo["cy"] + 10, 12)])
        await h.touch("touchMove", [(px, py, 12)])
        await asyncio.sleep(0.25)
        st = await state(h)
        ok("tahem do kruhu se označila 4. výseč", st["hover"] == 3, st["hover"])
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.5)
        st = await state(h)
        ok("puštění potvrdilo volbu a koláč zmizel", not st["pie"], st)
        ok("nástroj zůstal Noty", st["tool"] == "note", st["tool"])

        # --- 7) Nástroj bez voleb (Ruka) koláč neotevře ---------------------
        await long_press(h, btn)
        item7 = await rect(h, ".gm-item", 7)
        await h.touch("touchMove", [(col["right"] + 140, item7["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.8)
        st = await state(h)
        ok("Ruka se vybrala", st["tool"] == "edit", st["tool"])
        ok("Ruka koláč neotevírá", not st["pie"], st)

        # --- 8) Koláč: klik mimo jen zavře ----------------------------------
        await long_press(h, btn)
        i4 = await rect(h, ".gm-item", 4)
        await h.touch("touchMove", [(col["right"] + 140, i4["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.8)
        ok("koláč je otevřený před klikem mimo", bool((await state(h))["pie"]))
        await h.finger_tap(20, 1200)
        await asyncio.sleep(0.4)
        st = await state(h)
        ok("klik mimo koláč ho zavřel", not st["pie"], st)
        ok("nástroj zůstal Noty", st["tool"] == "note", st["tool"])

        # --- 9) Krátké ťuknutí přepíná anotaci -------------------------------
        before = (await state(h))["annot"]
        await h.finger_tap(btn["x"], btn["y"])
        st = await state(h)
        ok("krátké ťuknutí přepnulo anotaci (ne nabídku)",
           st["annot"] != before and not st["menu"], {"before": before, "annot": st["annot"]})

        # --- 10) Tlačítkový režim -------------------------------------------
        await h.ev("localStorage.setItem('noty.controlMode', 'button')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        await h.finger_tap(btn["x"], btn["y"])
        st = await state(h)
        ok("tlačítkový režim ukáže plovoucí panel", st["panel"], st)
        ok("tlačítkový režim gesto neotevírá", not st["menu"] and not st["pie"], st)

    ok.report()


asyncio.run(main())
