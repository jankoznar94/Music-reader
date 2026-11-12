#!/usr/bin/env python3
"""Panel anotací: minimum ovládání podle nástroje + noty pod jedním tlačítkem
a Zpět, které zabere na PRVNÍ ťuknutí.

Co se ověřuje (stav v DOM, ne kód):
  1. Styl se ukazuje jen podle nástroje: tužka barvy+tloušťka+krytí,
     zvýrazňovač (3 body) jen barvy, zvýrazňovač (volně) barvy+tloušťka,
     guma jen tloušťka, text jen barvy, ruka NIC
  2. sekce „Značky“ v panelu není; notové nástroje jsou pod tlačítkem s ikonou
     noty a řádek se rozbalí až po kliknutí
  3. „Jen pero“ je ve výchozím stavu VYPNUTÉ
  4. Zpět po nakreslení zabere na první ťuknutí (pero i prst)
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

APP = os.environ.get("APP_URL") or os.environ.get("NOTY_APP")

STATE = r"""(() => {
  const p = document.querySelector('.annot-panel');
  if (!p) return null;
  const cats = [...p.querySelectorAll('.ap-cat-label')].map(x => x.textContent.trim());
  const sel = p.querySelector('.ap-select');
  return {
    cats,
    colors: p.querySelectorAll('.ap-color').length,
    size: !!sel,
    opacity: !!p.querySelector('.ap-opacity'),
    notaRow: !!p.querySelector('.ap-nota-row'),
    notaBtn: !!p.querySelector('.ap-tool.nota-tool'),
    penOnlyOn: !!p.querySelector('.ap-tool.pen-only.on'),
  };
})()"""

COUNT = "(() => window.__barDev.annotations.value.items.length)()"


async def pick_tool(h, title_prefix):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll('.annot-panel .ap-tool')]"
        ".find(x=>(x.title||'').startsWith(%s)); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title_prefix))


async def click_sel(h, sel):
    return await h.ev(
        "(() => { const b=document.querySelector(%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(sel))


async def safe_point(h, half=90):
    return await h.ev(
        "(() => { const p=document.querySelector('.annot-panel');"
        " const pr = p ? p.getBoundingClientRect().right : 0;"
        " const v = document.querySelector('.viewer').getBoundingClientRect();"
        " const lo = Math.max(v.left + %d + 10, pr + %d + 10);"
        " const hi = v.right - %d - 10;"
        " for (let frac = 0.45; frac <= 0.85; frac += 0.05) { const y = v.top + v.height*frac;"
        "   for (let x = lo; x <= hi; x += 10) {"
        "     const el = document.elementFromPoint(x, y);"
        "     if (el && el.classList && el.classList.contains('annot-layer'))"
        "       return {x, y}; } }"
        " return null; })()" % (half, half, half))


async def main():
    ok = Check()
    async with (Harness(url=APP) if APP else Harness()) as h:
        await h.open()
        await h.open_song(reset=True)     # čistá DB = první použití
        await h.annot_toggle()

        s = await h.ev(STATE)
        ok("panel otevřený a notové tlačítko existuje", s and s["notaBtn"] is True, str(s))
        ok("sekce „Značky“ z panelu zmizela", s and "Značky" not in s["cats"], str(s and s["cats"]))
        ok("řádek notových nástrojů je schovaný", s and s["notaRow"] is False, str(s))
        ok("„Jen pero“ je výchozí VYPNUTO", s and s["penOnlyOn"] is False, str(s))

        # --- 1) Styl podle nástroje -----------------------------------------
        await pick_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        s = await h.ev(STATE)
        ok("tužka: barvy + tloušťka + krytí",
           s["colors"] > 0 and s["size"] and s["opacity"], str(s))

        await pick_tool(h, "Zvýraznění")
        await asyncio.sleep(0.3)
        await h.ev("(() => { const b=[...document.querySelectorAll('.ap-mode')].find(x=>x.textContent.trim()==='3 body'); b.click(); return 1; })()")
        await asyncio.sleep(0.2)
        s = await h.ev(STATE)
        ok("zvýrazňovač 3 body: jen barvy",
           s["colors"] > 0 and not s["size"] and not s["opacity"], str(s))
        await h.ev("(() => { const b=[...document.querySelectorAll('.ap-mode')].find(x=>x.textContent.trim()==='Volně'); b.click(); return 1; })()")
        await asyncio.sleep(0.2)
        s = await h.ev(STATE)
        ok("zvýrazňovač volně: barvy + tloušťka, bez krytí",
           s["colors"] > 0 and s["size"] and not s["opacity"], str(s))

        await pick_tool(h, "Guma")
        await asyncio.sleep(0.3)
        s = await h.ev(STATE)
        ok("guma: jen tloušťka", s["colors"] == 0 and s["size"] and not s["opacity"], str(s))

        await pick_tool(h, "Text")
        await asyncio.sleep(0.3)
        s = await h.ev(STATE)
        ok("text: jen barvy", s["colors"] > 0 and not s["size"] and not s["opacity"], str(s))

        await pick_tool(h, "Upravit")
        await asyncio.sleep(0.3)
        s = await h.ev(STATE)
        ok("ruka: NIC (žádný Styl)", s["colors"] == 0 and not s["size"] and not s["opacity"], str(s))

        # --- 2) notové nástroje pod tlačítkem --------------------------------
        ok("klik na tlačítko not rozbalí řádek", await click_sel(h, ".ap-tool.nota-tool") == 1)
        await asyncio.sleep(0.3)
        s = await h.ev(STATE)
        ok("řádek notových nástrojů je vidět", s["notaRow"] is True, str(s))
        n = await h.ev("(() => document.querySelectorAll('.ap-nota-row .ap-tool').length)()")
        ok("v řádku je 5 notových nástrojů", n == 5, str(n))

        await pick_tool(h, "Dynamika")
        await asyncio.sleep(0.3)
        s = await h.ev(STATE)
        ok("notový nástroj: žádný Styl (ani krytí, ani tloušťka, ani barvy)",
           s["colors"] == 0 and not s["size"] and not s["opacity"], str(s))
        ok("notový nástroj drží řádek otevřený", s["notaRow"] is True, str(s))
        # zavření skupiny nesmí nechat vybraný nástroj, který není vidět
        await click_sel(h, ".ap-tool.nota-tool")
        await asyncio.sleep(0.3)
        t = await h.ev("window.__barDev ? 'dev' : 'prod'")
        tool = await h.ev("(() => { const b=document.querySelector('.ap-tool.on'); return b ? (b.title||'') : document.querySelector('.annot-panel .ap-tool.on').title; })()")
        ok("zavřením skupiny se z notového nástroje odchází", "Dynamika" not in (tool or ""), str(tool))

        # --- 4) Zpět na první ťuknutí ---------------------------------------
        await pick_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        pt = await safe_point(h)
        await h.pen_stroke(pt["x"] - 40, pt["y"], pt["x"] + 40, pt["y"])
        await asyncio.sleep(0.3)
        ok("tah vznikl", await h.ev(COUNT) == 1, str(await h.ev(COUNT)))
        box = await h.ev(
            "(() => { const b=[...document.querySelectorAll('.annot-panel .ap-tool')]"
            ".find(x=>(x.title||'')==='Zpět'); const r=b.getBoundingClientRect();"
            " return {x:r.left+r.width/2, y:r.top+r.height/2, dis:b.disabled}; })()")
        ok("Zpět je aktivní (enabled)", box["dis"] is False, str(box))
        await h.pen_tap(box["x"], box["y"])
        await asyncio.sleep(0.4)
        c1 = await h.ev(COUNT)
        ok("Zpět perem zabere na PRVNÍ ťuknutí", c1 == 0, f"po 1. ťuku: {c1}")
        # a tentýž test prstem
        pt = await safe_point(h)
        await h.pen_stroke(pt["x"] - 40, pt["y"], pt["x"] + 40, pt["y"])
        await asyncio.sleep(0.3)
        await h.finger_tap(box["x"], box["y"])
        await asyncio.sleep(0.4)
        c2 = await h.ev(COUNT)
        ok("Zpět prstem zabere na PRVNÍ ťuknutí", c2 == 0, f"po 1. ťuku: {c2}")

        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
