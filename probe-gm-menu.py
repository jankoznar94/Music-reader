#!/usr/bin/env python3
"""Animovaný režim ovládání (listopad 2026, 3. kolo) — lišta vlevo, koláč
s prstenci (jeden na parametr) a tlačítko s fajfkou.

Ověřuje STAV v reálném prohlížeči:
  1. nastavení v knihovně (ozubené kolo) a výchozí tlačítkový režim
  2. podržení ✏️ → duch + lišta VLEVO u okraje (ne pod tlačítkem)
  3. notové ikony jsou vycentrované na otisk (nepřetékají z kolečka)
  4. svislý tah vybírá i s prstem mimo lištu
  5. tužka → koláč se DVĚMA prstenci (barva 9 + síla 7), uprostřed fajfka
  6. vybrané hodnoty jsou označené výsečí v obou prstencích
  7. volba v prstenci se uplatní a zůstane označená
  8. fajfka palety zavře
  9. noty → jeden prstenec s 12 výsečemi
 10. Ruka (bez voleb) koláč neotevírá
 11. Zpět / Dopředu jsou na hlavní liště
 12. krátké ťuknutí přepíná anotaci
 13. tlačítkový režim má starý plovoucí panel
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
        "  pies: document.querySelectorAll('.pie-svg g[data-pie]').length,"
        "  sectors: document.querySelectorAll('.pie-sec').length,"
        "  hub: !!document.querySelector('.pie-hub-g'),"
        "  undo: !!document.querySelector('.tb-btn[title^=\"Zpět\"]'),"
        "  redo: !!document.querySelector('.tb-btn[title^=\"Dopředu\"]'),"
        "  vw: innerWidth, vh: innerHeight,"
        "}))()")


async def long_press(h, btn, hold=0.3):
    await h.touch("touchStart", [(btn["x"], btn["y"], 12)])
    await asyncio.sleep(hold)


async def ink_inside(h, sel):
    """Je otisk glyfu (getBBox) CELÝ uvnitř viewBoxu svého malého SVG? Ořez = FAIL."""
    return await h.ev(
        "(() => { const out = [];"
        " document.querySelectorAll(%s).forEach((s, i) => {"
        "  const t = s.querySelector('text'); if (!t) return;"
        "  const vb = (s.getAttribute('viewBox') || '').trim().split(/\\s+/).map(Number);"
        "  if (vb.length !== 4) return;"
        "  const b = t.getBBox();"
        "  out.push({ i, dl: +(b.x - vb[0]).toFixed(3), dr: +((vb[0] + vb[2]) - (b.x + b.width)).toFixed(3),"
        "             dt: +(b.y - vb[1]).toFixed(3), db: +((vb[1] + vb[3]) - (b.y + b.height)).toFixed(3),"
        "             w: +b.width.toFixed(3), h: +b.height.toFixed(3) });"
        " }); return out; })()" % json.dumps(sel))


async def pie_geo(h):
    return await h.ev(
        "(() => { const c=document.querySelector('.pie-check-bg');"
        " const pies=[...document.querySelectorAll('.pie-svg g[data-pie]')].map(g => ({"
        "   cx:+g.getAttribute('data-cx'), cy:+g.getAttribute('data-cy'),"
        "   r0:+g.getAttribute('data-r0'), r1:+g.getAttribute('data-r1'),"
        "   on:[...g.querySelectorAll('.pie-sec')].findIndex(e => e.classList.contains('on')),"
        "   hub: !!g.querySelector('.pie-hub') }));"
        " return { cx:+c.getAttribute('cx'), cy:+c.getAttribute('cy'), r:+c.getAttribute('r'), pies }; })()")


def pt(cx, cy, a, r):
    return (cx + math.cos(a) * r, cy + math.sin(a) * r)


def sector_angle(i, n):
    return -math.pi / 2 + (i + 0.5) * (2 * math.pi / n)


async def main():
    ok = m.Check()
    async with m.Harness(url=APP) as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        # Test předpokládá ČISTÉ úložiště (výchozí tlačítkový režim) — předchozí
        # běh tam nechává 'gesture' a tvrzení o výchozím stavu by padalo.
        await h.ev("localStorage.removeItem('noty.controlMode')")
        await h.open()

        # --- 1) Knihovna -----------------------------------------------------
        st = await h.ev("(() => ({ gear: !!document.querySelector('.gear-btn'),"
                        " mode: localStorage.getItem('noty.controlMode') }))()")
        ok("knihovna má tlačítko ozubeného kola", st["gear"], st)
        ok("výchozí režim je tlačítkový (klíč chybí)", st["mode"] is None, st["mode"])
        await h.ev("document.querySelector('.gear-btn').click()")
        await asyncio.sleep(0.35)
        labels = await h.ev("([...document.querySelectorAll('.set-seg button')].map(b => b.textContent.trim()))")
        ok("nastavení nabízí Tlačítkový i Animovaný", labels == ["Tlačítkový", "Animovaný"], labels)
        on = await h.ev("(document.querySelector('.set-seg button.on') || {}).textContent")
        ok("předvybraný je Tlačítkový", (on or "").strip() == "Tlačítkový", on)
        await h.ev("([...document.querySelectorAll('.set-seg button')].find(b => b.textContent.trim() === 'Animovaný')).click()")
        await asyncio.sleep(0.25)
        ok("volba Animovaný se uložila", (await h.ev("localStorage.getItem('noty.controlMode')")) == "gesture")
        await h.ev("document.querySelector('.set-close').click()")
        await asyncio.sleep(0.2)
        await h.ev("localStorage.setItem('topbarHidden', '0')")

        # --- 2) Skladba ------------------------------------------------------
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        btn = await rect(h, ".tb-btn[title^='Anotace']")
        st = await state(h)
        ok("tlačítko ✏️ existuje", btn is not None, btn)
        ok("Zpět a Dopředu jsou na hlavní liště", st["undo"] and st["redo"], st)

        # --- 3) Podržení: duch + lišta vlevo ---------------------------------
        await long_press(h, btn)
        st = await state(h)
        ok("podržení otevřelo lištu", st["menu"], st)
        ok("duch tlačítka je vidět", st["ghost"], st)
        ok("lišta má 9 koleček", st["items"] == 9, st["items"])
        col = await rect(h, ".gm-col")
        ok("lišta stojí HNED NALEVO od tlačítka ✏️ (ne v rohu)",
           col["left"] > 12 and abs(col["right"] - btn["left"]) <= 2,
           {"col": [round(col["left"], 1), round(col["right"], 1)], "btn": round(btn["left"], 1)})
        ok("lišta začíná POD hlavní lištou", col["top"] >= 50, col["top"])
        gl_in = await ink_inside(h, ".gm-glyph-svg")
        ok("glyfy lišty se vejdou do šířky kolečka (bez ořezu)",
           bool(gl_in) and all(min(g["dl"], g["dr"]) >= -0.5 for g in gl_in), gl_in)

        # --- 4) notová ikona je vycentrovaná na OTISK ------------------------
        circ = await rect(h, ".gm-item .gm-circle", 4)     # Noty
        gl = await rect(h, ".gm-item .gm-glyph-svg", 0)    # první glyf = Noty
        ok("notová ikona se vejde do kolečka",
           bool(circ and gl) and gl["top"] >= circ["top"] - 0.5 and gl["bottom"] <= circ["bottom"] + 0.5,
           {"circ": circ and [circ["top"], circ["bottom"]], "glyph": gl and [gl["top"], gl["bottom"]]})
        ok("notová ikona je na středu kolečka",
           bool(circ and gl) and abs((gl["top"] + gl["bottom"]) / 2 - circ["y"]) < 1.5,
           {"dy": gl and round((gl["top"] + gl["bottom"]) / 2 - circ["y"], 2)})

        # --- 5) Tah mimo lištu + volba tužky --------------------------------
        item2 = await rect(h, ".gm-item", 2)
        await h.touch("touchMove", [(col["right"] + 140, item2["y"], 12)])
        await asyncio.sleep(0.25)
        ok("prst mimo lištu vybere podle svislé polohy", (await state(h))["active"] == 2)

        item0 = await rect(h, ".gm-item", 0)   # Tužka
        await h.touch("touchMove", [(col["right"] + 140, item0["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        st = await state(h)
        ok("lišta se zavřela", not st["menu"], st)
        ok("tužka se vybrala", st["tool"] == "pencil", st["tool"])
        ok("koláč se otevřel", st["pie"], st)
        ok("tužka má DVA SAMOSTATNÉ koláče (barva + síla)", st["pies"] == 2, st["pies"])
        ok("dohromady 16 výsečí (9 barev + 7 sil)", st["sectors"] == 16, st["sectors"])
        ok("uprostřed je tlačítko s fajfkou", st["hub"], st)

        geo = await pie_geo(h)
        ok("fajfka je uprostřed displeje",
           abs(geo["cx"] - st["vw"] / 2) < 2 and abs(geo["cy"] - st["vh"] / 2) < 2, geo)
        ok("koláče jsou od sebe oddělené (každý svůj střed)",
           abs(geo["pies"][0]["cx"] - geo["pies"][1]["cx"]) > 100, geo["pies"])
        ok("každý koláč má ve středu svou vybranou hodnotu",
           all(p["hub"] for p in geo["pies"]), [p["hub"] for p in geo["pies"]])
        ok("vybrané hodnoty jsou označené v obou koláčích",
           all(p["on"] >= 0 for p in geo["pies"]), [p["on"] for p in geo["pies"]])

        # --- 6) Volba barvy v levém koláči ----------------------------------
        p0 = geo["pies"][0]
        x, y = pt(p0["cx"], p0["cy"], sector_angle(2, 9), (p0["r0"] + p0["r1"]) / 2)
        await h.touch("touchStart", [(p0["cx"], p0["cy"] + 8, 12)])
        await h.touch("touchMove", [(x, y, 12)])
        await asyncio.sleep(0.2)
        hov = await h.ev("([...document.querySelectorAll('.pie-sec')].findIndex(e => e.classList.contains('hover')))")
        ok("prst v levém koláči označí 3. barvu", hov == 2, hov)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.35)
        geo2 = await pie_geo(h)
        ok("vybraná barva zůstala označená", geo2["pies"][0]["on"] == 2, geo2["pies"][0])
        ok("koláč zůstal otevřený (další parametr)", (await state(h))["pie"])

        # --- 7) Volba síly v pravém koláči ----------------------------------
        p1 = geo2["pies"][1]
        x, y = pt(p1["cx"], p1["cy"], sector_angle(4, 7), (p1["r0"] + p1["r1"]) / 2)
        await h.touch("touchStart", [(p1["cx"], p1["cy"] + 8, 12)])
        await h.touch("touchMove", [(x, y, 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.35)
        geo3 = await pie_geo(h)
        ok("vybraná síla je označená v pravém koláči", geo3["pies"][1]["on"] == 4, geo3["pies"][1])

        # --- 8) Fajfka zavře palety -----------------------------------------
        await h.touch("touchStart", [(geo3["cx"], geo3["cy"], 12)])
        await asyncio.sleep(0.08)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)
        st = await state(h)
        ok("fajfka zavřela koláče", not st["pie"], st)
        ok("nástroj zůstal tužka", st["tool"] == "pencil", st["tool"])

        # --- 9) Noty: jeden koláč kolem fajfky ------------------------------
        await long_press(h, btn)
        i4 = await rect(h, ".gm-item", 4)
        await h.touch("touchMove", [(col["right"] + 140, i4["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        st = await state(h)
        ok("noty: nástroj vybrán", st["tool"] == "note", st["tool"])
        ok("noty: JEDEN koláč kolem fajfky", st["pies"] == 1, st["pies"])
        ok("noty: 12 výsečí", st["sectors"] == 12, st["sectors"])
        g4 = await pie_geo(h)
        ok("noty: koláč je přesně kolem fajfky",
           abs(g4["pies"][0]["cx"] - g4["cx"]) < 1 and g4["pies"][0]["r0"] > g4["r"], g4)
        ok("noty: koláč nemá zvláštní střed (fajfka ho nahrazuje)", not g4["pies"][0]["hub"], g4["pies"][0])
        p0 = g4["pies"][0]
        x, y = pt(p0["cx"], p0["cy"], sector_angle(3, 12), (p0["r0"] + p0["r1"]) / 2)
        await h.touch("touchStart", [(p0["cx"], p0["cy"] + 8, 12)])
        await h.touch("touchMove", [(x, y, 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.3)
        ok("noty: 4. výseč se označila", (await pie_geo(h))["pies"][0]["on"] == 3)
        await h.touch("touchStart", [(g4["cx"], g4["cy"], 12)])
        await asyncio.sleep(0.08)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)

        # --- 9b) Dynamika: glyfy ve výsečích nesmí být oříznuté ---------------
        await long_press(h, btn)
        i5 = await rect(h, ".gm-item", 5)
        await h.touch("touchMove", [(col["right"] + 140, i5["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        st = await state(h)
        ok("dynamika: nástroj vybrán", st["tool"] == "dynamic", st["tool"])
        ok("dynamika: koláč otevřený", st["pie"], st)
        pin = await ink_inside(h, ".pie-glyph")
        ok("dynamika: otisky ve výsečích se vejdou do šířky (bez ořezu)",
           bool(pin) and all(min(g["dl"], g["dr"]) >= -0.5 for g in pin), pin)
        dgeo = await pie_geo(h)
        ok("dynamika: hned po otevření je zvýrazněná vybraná výseč (mf)",
           dgeo["pies"][0]["on"] == 4, dgeo["pies"][0])
        if pin:
            g = pin[0]
            ok("dynamika: glyf je na středu výseče (rezerva na obou stranách)",
               abs(g["dl"] - g["dr"]) < g["w"] * 0.45 and abs(g["dt"] - g["db"]) < g["h"] * 0.45, g)
        await h.touch("touchStart", [(g4["cx"], g4["cy"], 12)])
        await asyncio.sleep(0.08)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)

        # --- 10) Ruka bez koláče --------------------------------------------
        await long_press(h, btn)
        i7 = await rect(h, ".gm-item", 7)
        await h.touch("touchMove", [(col["right"] + 140, i7["y"], 12)])
        await asyncio.sleep(0.2)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        st = await state(h)
        ok("Ruka se vybrala", st["tool"] == "edit", st["tool"])
        ok("Ruka koláč neotevírá", not st["pie"], st)

        # --- 11) Krátké ťuknutí ---------------------------------------------
        before = (await state(h))["annot"]
        await h.finger_tap(btn["x"], btn["y"])
        st = await state(h)
        ok("krátké ťuknutí přepnulo anotaci", st["annot"] != before and not st["menu"],
           {"before": before, "annot": st["annot"]})

        # --- 12) Tlačítkový režim -------------------------------------------
        await h.ev("localStorage.setItem('noty.controlMode', 'button')")
        await h.open()
        await h.open_song(pdf=m.make_pdf(6), pages=6, reset=False)
        await h.finger_tap(btn["x"], btn["y"])
        st = await state(h)
        ok("tlačítkový režim ukáže plovoucí panel", st["panel"], st)
        ok("Zpět/Dopředu jsou i v tlačítkovém režimu", st["undo"] and st["redo"], st)

    ok.report()


asyncio.run(main())
