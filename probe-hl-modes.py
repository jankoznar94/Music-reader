#!/usr/bin/env python3
"""Zvýrazňovač: tři způsoby (3 body / Obdélník / Volně) + select tloušťky 1–50.

Co se ověřuje (stav v DOM a v uložených anotacích, ne kód):
  1. v panelu je u zvýrazňovače řádek tří způsobů a výchozí je „3 body“
  2. select tloušťky má 50 voleb 1–50 px a změna se projeví na novém tahu
  3. obdélník: dva body + Výška = 40 px → čtyřúhelník, jehož výška na OBRAZOVCE
     je 40 px (ne 40 jednotek vrstvy) a šířka = vzdálenost obou bodů
  4. volně: tah perem → anotace s points + free, žádné poly; kreslí se jako tah
  5. tři body pořád fungují (regrese původního chování)
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

PANEL = r"""(() => {
  const modes = [...document.querySelectorAll('.annot-panel .ap-mode')].map(b => b.textContent.trim());
  const on = [...document.querySelectorAll('.annot-panel .ap-mode.on')].map(b => b.textContent.trim());
  const sel = document.querySelector('.annot-panel .ap-select');
  const opts = sel ? [...sel.options].map(o => o.value) : [];
  const num = document.querySelector('.annot-panel .ap-num');
  return { modes, on, optCount: opts.length, first: opts[0], last: opts[opts.length-1],
           num: num ? num.value : null };
})()"""

LAST = r"""(() => {
  const d = window.__barDev;
  const items = d.annotations.value.items;
  if (!items.length) return { count: 0 };
  const it = items[items.length - 1];
  const svg = document.querySelector('.annot-layer');
  const ctm = svg.getScreenCTM();
  const sc = (it.poly || []).map(q => {
    const p = new DOMPoint(q.x, q.y).matrixTransform(ctm);
    return { x: p.x, y: p.y };
  });
  const dist = (p, q) => Math.hypot(q.x - p.x, q.y - p.y);
  const sides = sc.length === 4 ? [0,1,2,3].map(i => Math.round(dist(sc[i], sc[(i+1)%4]))) : [];
  const tilt = sc.length === 4
    ? +(Math.atan2(sc[1].y - sc[0].y, sc[1].x - sc[0].x) * 180 / Math.PI).toFixed(2) : null;
  const cx = sc.length ? sc.reduce((s,p)=>s+p.x,0)/sc.length : null;
  const cy = sc.length ? sc.reduce((s,p)=>s+p.y,0)/sc.length : null;
  return {
    count: items.length, tool: it.tool, free: !!it.free,
    polyLen: (it.poly || []).length, points: (it.points || []).length,
    width: it.width, sides, tilt,
    cx: cx == null ? null : Math.round(cx), cy: cy == null ? null : Math.round(cy),
  };
})()"""

COUNT = "(() => window.__barDev.annotations.value.items.length)()"


async def safe_point(h, half=90):
    """Bod na vrstvě, který je od plovoucího panelu anotací dál než `half` px —
    jinak tah začne/ skončí na panelu a appka (správně) nic nenakreslí."""
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
        "       return {x, y, panelRight: pr}; } }"
        " return null; })()" % (half, half, half))


async def pick_tool(h, title):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll('.annot-panel .ap-tool')]"
        ".find(x=>(x.title||'')===%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title))


async def pick_mode(h, label):
    return await h.ev(
        "(() => { const b=[...document.querySelectorAll('.annot-panel .ap-mode')]"
        ".find(x=>x.textContent.trim()===%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(label))


async def set_height(h, px):
    return await h.ev(
        "(() => { const i=document.querySelector('.annot-panel .ap-num'); if(!i) return 0;"
        " i.value=%d; i.dispatchEvent(new Event('input',{bubbles:true}));"
        " i.dispatchEvent(new Event('change',{bubbles:true})); return 1; })()" % px)


async def set_size(h, px):
    return await h.ev(
        "(() => { const s=document.querySelector('.annot-panel .ap-select'); if(!s) return 0;"
        " s.value=String(%d); s.dispatchEvent(new Event('change',{bubbles:true})); return 1; })()" % px)


async def main():
    ok = Check()
    async with (Harness(url=APP) if APP else Harness()) as h:
        await h.open()                 # reset_db by jinak běžel nad about:blank
        # Vynuluj zapamatovaný způsob, aby „výchozí je 3 body“ platilo pro čistý
        # stav (způsob se záměrně pamatuje mezi otevřeními).
        await h.ev("localStorage.removeItem('noty.hlMode'); localStorage.removeItem('noty.hlRectHeight')")
        await h.cdp("Page.reload")
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(1.0)
        await h.open_song(reset=False)
        await h.annot_toggle()
        ok("panel anotací otevřený", await h.ev("!!document.querySelector('.annot-panel')"))

        await pick_tool(h, "Zvýraznění")
        await asyncio.sleep(0.4)
        p = await h.ev(PANEL)
        ok("tři způsoby v panelu", p["modes"] == ["3 body", "Obdélník", "Volně"], str(p["modes"]))
        ok("výchozí způsob = 3 body", p["on"] == ["3 body"], str(p["on"]))
        # Select tloušťky visí u tužky (u zvýrazňovače jen ve volném režimu).
        await pick_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        p = await h.ev(PANEL)
        ok("select tloušťky 1–50", p["optCount"] == 50 and p["first"] == "1" and p["last"] == "50",
           f'{p["optCount"]} voleb, {p["first"]}..{p["last"]}')
        await pick_tool(h, "Zvýraznění")
        await asyncio.sleep(0.3)

        # --- 2) tloušťka se propíše do nového tahu (tužka) --------------------
        await pick_tool(h, "Tužka")
        await set_size(h, 7)
        await asyncio.sleep(0.2)
        pt = await safe_point(h)
        await h.pen_stroke(pt["x"] - 40, pt["y"], pt["x"] + 40, pt["y"])
        last = await h.ev(LAST)
        ok("tužka kreslí zvolenou tloušťkou 7 px", last.get("width") == 7, str(last))

        # --- 3) obdélník ze dvou bodů + výška --------------------------------
        await pick_tool(h, "Zvýraznění")
        await asyncio.sleep(0.3)
        ok("způsob Obdélník lze vybrat", await pick_mode(h, "Obdélník") == 1)
        await asyncio.sleep(0.2)
        ok("pole Výška se ukáže", await set_height(h, 40) == 1)
        await asyncio.sleep(0.2)
        before = await h.ev(COUNT)
        pt = await safe_point(h)
        x1, y1 = pt["x"] - 70, pt["y"]
        x2, y2 = pt["x"] + 70, pt["y"] + 4     # mírně jiné y → pás se centruje
        await h.pen_tap(x1, y1)
        await h.pen_tap(x2, y2)
        await asyncio.sleep(0.4)
        rect = await h.ev(LAST)
        ok("obdélník: vznikla JEDNA anotace", rect.get("count") == before + 1, str(rect))
        ok("obdélník: čtyřúhelník zvýrazňovače", rect.get("tool") == "highlighter"
           and rect.get("polyLen") == 4, str(rect))
        sides = sorted(rect.get("sides") or [])
        ok("obdélník: strany 140 a 40 px (kolmá výška)",
           len(sides) == 4 and abs(sides[0] - 40) <= 1.5 and abs(sides[1] - 40) <= 1.5
           and abs(sides[2] - 140) <= 2 and abs(sides[3] - 140) <= 2, str(sides))
        # body byly o 4 px výš níž → pás MUSÍ být nakloněný, ne vodorovný
        ok("obdélník: pás jde z kopce podle bodů (~1,6°)",
           abs((rect.get("tilt") or 0) - 1.64) <= 1.0, str(rect.get("tilt")))
        ok("obdélník: střed pásu = střed obou bodů",
           abs((rect.get("cx") or 0) - (x1 + x2) / 2) <= 1.5
           and abs((rect.get("cy") or 0) - (y1 + y2) / 2) <= 1.5,
           str((rect.get("cx"), rect.get("cy"))))

        # --- 4) volné kreslení ------------------------------------------------
        ok("způsob Volně lze vybrat", await pick_mode(h, "Volně") == 1)
        await asyncio.sleep(0.2)
        ok("způsob se pamatuje (localStorage)",
           await h.ev("localStorage.getItem('noty.hlMode')") == "free")
        before = await h.ev(COUNT)
        pt = await safe_point(h)
        await h.pen_stroke(pt["x"] - 50, pt["y"] - 20, pt["x"] + 50, pt["y"] + 20, steps=14)
        free = await h.ev(LAST)
        ok("volně: vznikla anotace tahu", free.get("count") == before + 1, str(free))
        ok("volně: tah (free, points, žádné poly)",
           free.get("free") is True and (free.get("points") or 0) > 2 and free.get("polyLen") == 0,
           str(free))
        ok("volně: kreslí se jako tah s multiply",
           await h.ev("!!document.querySelector('.annot-layer path.hl[stroke]')"))

        # --- 5) regrese: tři body --------------------------------------------
        await pick_mode(h, "3 body")
        await asyncio.sleep(0.2)
        before = await h.ev(COUNT)
        pt = await safe_point(h)
        await h.pen_tap(pt["x"] - 60, pt["y"] - 10)
        await h.pen_tap(pt["x"] - 60, pt["y"] + 10)
        await h.pen_tap(pt["x"] + 60, pt["y"])
        await asyncio.sleep(0.4)
        three = await h.ev(LAST)
        ok("tři body: vznikla anotace", three.get("count") == before + 1, str(three))
        ok("tři body: čtyřúhelník", three.get("polyLen") == 4, str(three))
        s3 = sorted(three.get("sides") or [])
        ok("tři body: vodorovný pás 120 × 20 px",
           len(s3) == 4 and abs(s3[0] - 20) <= 1.5 and abs(s3[1] - 20) <= 1.5
           and abs(s3[2] - 120) <= 2 and abs(s3[3] - 120) <= 2, str(s3))

        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
