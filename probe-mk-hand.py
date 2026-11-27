#!/usr/bin/env python3
"""Značka (mk, okno Značky) se dá uchopit nástrojem Ruka — posunout i přepsat.

Jan (21. 11. 2026): „existující Značky by měly jít uchopit s přemístit/upravit
nástrojem ruka atd.“

Ověřuje stav, ne kód:
  1. značka vytvořená v okně Značek se mimo Ruku nekreslí (je jen index)
  2. po přepnutí na Ruku se kreslí a je v pageItems → jde chytit
  3. ťuk na ni ji označí a rám výběru sedí na skutečný otisk písmen (<text> bbox)
  4. pás úprav se jmenuje „Značka", nemá Velikost ani přepínač rámečku
  5. tažení prstem posune právě ji (delta odpovídá pohybu prstu) a uloží se
  6. přepsání textu v dialogu nezmění velikost značky (S/M/L patří skladbě)
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check
_mod.CDP_HTTP = os.environ.get("NOTY_CDP", _mod.CDP_HTTP)

APP = os.environ.get("APP_URL") or os.environ.get("NOTY_APP")

MK_ITEM = r"""(() => {
  const d = window.__barDev;
  const it = d.annotations.value.items.find(x => x && x.mk);
  return it ? { id: it.id, page: it.page, x: it.x, y: it.y, text: it.text,
                size: it.size, color: it.color, border: !!it.border } : null;
})()"""

MK_DOM = r"""(() => {
  const d = window.__barDev;
  const it = d.annotations.value.items.find(x => x && x.mk);
  if (!it) return null;
  const g = document.querySelector('g[data-id="' + it.id + '"]');
  if (!g) return null;
  const t = g.querySelector('text');
  if (!t) return null;
  const r = t.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2,
           w: r.width, h: r.height, text: t.textContent };
})()"""

EDIT_BAR = r"""(() => {
  const b = document.querySelector('.edit-bar');
  if (!b) return null;
  return { type: (b.querySelector('.eb-type') || {}).textContent || '',
           btns: [...b.querySelectorAll('.eb-btn')].map(x => (x.title || x.textContent || '').trim()),
           hasSize: !!b.querySelector('.eb-size'),
           text: b.textContent.replace(/\s+/g, ' ').trim() };
})()"""

SEL_RECT = r"""(() => {
  const g = document.querySelector('.annot-selected');
  if (!g) return null;
  const r = g.querySelector('rect');
  if (!r) return null;
  const b = r.getBoundingClientRect();
  return { x: b.left, y: b.top, w: b.width, h: b.height };
})()"""


async def main():
    ok = Check()
    async with (Harness(url=APP) if APP else Harness()) as h:
        await h.open()
        await h.open_song(reset=True)
        await h.annot_toggle()

        # --- 1) vytvořit značku skutečnou cestou okna Značky ------------------
        await h.click(".tb-mark")
        await asyncio.sleep(0.5)
        await h.click(".marks-panel .jp-btn.primary")   # „Přidat značku“
        await asyncio.sleep(0.5)
        pt = await h.free_point(0.45, 0.8)
        ok("v notách je místo pro ťuk", bool(pt), str(pt))
        await h.finger_tap(pt["x"], pt["y"])
        await asyncio.sleep(0.5)
        has_input = await h.ev("!!document.querySelector('.marks-new .jp-input')")
        ok("po ťuku se otevře pole pro popis značky", has_input is True)
        await h.set_value(".marks-new .jp-input", "B")
        await h.click(".marks-new .jp-btn.primary")      # Uložit
        await asyncio.sleep(0.8)
        mk = await h.ev(MK_ITEM)
        ok("značka je uložená jako anotace s mk", bool(mk), str(mk))
        if not mk:
            return ok.report()

        # --- 2) mimo Ruku je jen index (nekreslí se) -------------------------
        await h.click(".tb-mark")                        # zavřít okno Značek
        await asyncio.sleep(0.5)
        hidden = await h.ev(MK_DOM)
        ok("mimo Ruku / okno Značek se značka nekreslí", hidden is None, str(hidden))

        # --- 3) Ruka ji pustí do vrstvy --------------------------------------
        # Značky se v notách kreslí jen když jsou „zobrazené“, s otevřeným oknem
        # Značek, nebo u právě upravované značky (Jan, 27. 11. 2026 — dřív se
        # v Ruce kreslily VŠECHNY a zůstávaly viset v notách napořád).
        await h.ev("(() => { window.__barDev.mkPanelOpen.value = true; return 1 })()")
        await asyncio.sleep(0.5)
        dom = await h.ev(MK_DOM)
        ok("s otevřeným oknem Značek se značka vykreslí", bool(dom), str(dom))
        if not dom:
            return ok.report()
        ok("v DOM je skutečně „B“", dom["text"] == "B", str(dom["text"]))

        # --- 4) ťuk ji označí, rám sedí na otisk -----------------------------
        await h.pen_tap(dom["x"], dom["y"])
        await asyncio.sleep(0.5)
        sel = await h.ev(SEL_RECT)
        ok("ťuk na značku ji označí", sel is not None, str(sel))
        if sel:
            # rám se kreslí bez paddingu (selectedBox) → musí sedět na <text> ± 3 px
            dx = abs((sel["x"] + sel["w"] / 2) - dom["x"])
            dy = abs((sel["y"] + sel["h"] / 2) - dom["y"])
            ok("střed rámu sedí na střed značky", dx < 4 and dy < 4,
               "dx=%.1f dy=%.1f sel=%s dom=%s" % (dx, dy, sel, dom))

        bar = await h.ev(EDIT_BAR)
        ok("pás úprav se jmenuje „Značka“", bar and bar["type"].strip() == "Značka", str(bar))
        ok("pás úprav nenabízí Velikost", bar and not bar["hasSize"], str(bar and bar["text"]))
        ok("pás úprav nemá přepínač rámečku",
           bar and not any("rámeček" in b.lower() for b in bar["btns"]), str(bar and bar["btns"]))

        # --- 5) tažení prstem značkou hýbe -----------------------------------
        p0 = await h.ev(MK_ITEM)
        await h.touch("touchStart", [(dom["x"], dom["y"], 12)])
        for i in range(1, 7):
            await h.touch("touchMove", [(dom["x"] + 8 * i, dom["y"] + 6 * i, 12)])
            await asyncio.sleep(0.02)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.9)
        p1 = await h.ev(MK_ITEM)
        ok("tažení značkou posune její souřadnice",
           p1 and (p1["x"] > p0["x"] + 5 and p1["y"] > p0["y"] + 5),
           "%s -> %s" % (p0, p1))
        ok("přesun nezměnil text ani velikost",
           p1 and p1["text"] == p0["text"] and p1["size"] == p0["size"], str(p1))

        # --- 6) přepsání textu nesmí přehodit velikost ------------------------
        # Lišta i dialog přijímají klepnutí jen po skutečném POLOŽENÍ prstu
        # (editBarArmed / dialogArmed) — JS `.click()` se záměrně ignoruje.
        pen = await h.ev("(() => { const b=[...document.querySelectorAll('.edit-bar .eb-btn')]"
                         ".find(x=>x.title==='Přepsat text'); if(!b) return null;"
                         " const r=b.getBoundingClientRect();"
                         " return {x:r.left+r.width/2, y:r.top+r.height/2}; })()")
        ok("v pásu je tlačítko Přepsat text", bool(pen), str(pen))
        await h.finger_tap(pen["x"], pen["y"])
        await asyncio.sleep(0.6)
        lbl = await h.ev("(document.querySelector('.text-input-card .ti-label')||{}).textContent")
        ok("dialog přepsání se jmenuje „Značka“", (lbl or '').strip() == "Značka", str(lbl))
        rows = await h.ev("(() => { const c=document.querySelector('.text-input-card');"
                          " return c ? c.textContent.replace(/\\s+/g,' ').trim() : null; })()")
        ok("dialog u značky nenabízí velikost/barvu/rámeček",
           rows is not None and "Velikost" not in rows and "Barva" not in rows
           and "Rámeček" not in rows, str(rows))
        await h.set_value(".text-input-card .ti-input", "C")
        save = await h.ev("(() => { const b=[...document.querySelectorAll('.text-input-card .jp-btn')]"
                          ".find(x=>x.textContent.trim()==='Uložit'); if(!b) return null;"
                          " const r=b.getBoundingClientRect();"
                          " return {x:r.left+r.width/2, y:r.top+r.height/2}; })()")
        await h.finger_tap(save["x"], save["y"])
        await asyncio.sleep(0.9)
        p2 = await h.ev(MK_ITEM)
        ok("text se přepsal na „C“", p2 and p2["text"] == "C", str(p2))
        ok("velikost značky zůstala", p2 and p2["size"] == p0["size"],
           "%s -> %s" % (p0 and p0["size"], p2 and p2["size"]))
        ok("značka si drží svou barvu", p2 and p2["color"] == p0["color"], str(p2))

        # --- 7) okno Značek: klepnutí na značku ji vybere BEZ přepínání Ruky --
        # (Jan, 21. 11. 2026: „abych nemusel klikat Ruku a pak na značku“)
        await h.ev("(() => { const b=[...document.querySelectorAll('.annot-panel .ap-tool')]"
                   ".find(x=>(x.title||'').startsWith('Tužka')); if(b) b.click(); })()")
        await asyncio.sleep(0.4)
        await h.click(".tb-mark")
        await asyncio.sleep(0.6)
        dom2 = await h.ev(MK_DOM)
        ok("značka je vidět i s otevřeným oknem Značek", bool(dom2), str(dom2))
        await h.pen_tap(dom2["x"], dom2["y"])
        await asyncio.sleep(0.6)
        st = await h.ev("(() => { const d = window.__barDev;"
                        " const on = [...document.querySelectorAll('.annot-panel .ap-tool.on')]"
                        "   .map(x => (x.title || '').trim());"
                        " return { editing: d.editingId.value, panel: d.mkPanelOpen.value, tools: on }; })()")
        ok("ťuk na značku ji v okně Značek rovnou označí",
           st and st["editing"] == p2["id"], str(st))
        ok("nástroj se sám přepnul na Ruku",
           st and any(t.startswith("Upravit") for t in st["tools"]), str(st and st["tools"]))
        ok("okno Značek se zavřelo", st and st["panel"] is False, str(st and st["panel"]))
        bar2 = await h.ev(EDIT_BAR)
        ok("pás úprav ukazuje Značku", bar2 and bar2["type"] == "Značka", str(bar2))

        # --- 8) listování krajem displeje nesmí okno Značek zablokovat ------
        await h.ev("(() => window.__barDev.openMarks())()")
        await asyncio.sleep(0.6)
        pg0 = await h.page_text()
        geo = await h.geo()
        await h.finger_tap(geo["left"] + geo["w"] - 20, geo["top"] + geo["h"] * 0.6)
        await asyncio.sleep(0.9)
        pg1 = await h.page_text()
        ok("s otevřeným oknem Značek jde krajem displeje listovat", pg0 != pg1,
           "%s -> %s" % (pg0, pg1))

        # --- 9) přesun přežije reload ---------------------------------------
        await h.open()
        await h.open_song(pdf=None, pages=6, reset=False)
        await asyncio.sleep(1.0)
        p3 = await h.ev(MK_ITEM)
        ok("přesun i přepsání přežily reload",
           p3 and abs(p3["x"] - p2["x"]) < 1.5 and abs(p3["y"] - p2["y"]) < 1.5
           and p3["text"] == "C", "%s -> %s" % (p2, p3))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
