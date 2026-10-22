#!/usr/bin/env python3
"""Zvýrazňovač: jde v režimu Ruka změnit rozměr tažením za stranu a otočit?

1. nakreslí zvýraznění 3 klepnutími perem
2. přepne nástroj Upravit (ruka) a pás vybere
3. chytí úchytku PRAVÉ strany a táhne doprava → pravá hrana se posune, levá zůstane
4. chytí úchytku HORNÍ strany a táhne nahoru → horní hrana se posune, dolní zůstane
5. chytí otočné kolečko a otočí → čtyřúhelník už není osový, plocha zůstane
6. zkontroluje, že úprava přežila překreslení stránky a že tažení UPROSTŘED pásu
   pořád posouvá celý pás (úchytky nesmí sebrat celou plochu)
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

TOOL_JS = ("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
           ".find(x => (x.title || '').startsWith(%s)); if (b) { b.click(); return 'ok'; }"
           " return 'missing'; })()")

STATE_JS = """(() => {
  const svg = document.querySelector('.annot-layer');
  const hl = svg && svg.querySelector('path.hl');
  if (!svg || !hl) return JSON.stringify({found: false});
  const m = svg.getScreenCTM();
  const toS = (x, y) => { const p = new DOMPoint(x, y).matrixTransform(m); return {x: p.x, y: p.y}; };
  const pts = (hl.getAttribute('d') || '').replace(/^M/, '').replace(/Z$/, '')
    .split('L').map(s => s.split(',').map(Number))
    .map(([x, y]) => ({x, y}));
  const grips = [...svg.querySelectorAll('.hl-grip')].map(el => {
    if (el.tagName.toLowerCase() === 'rect') {
      const cx = +el.getAttribute('x') + +el.getAttribute('width') / 2;
      const cy = +el.getAttribute('y') + +el.getAttribute('height') / 2;
      return toS(cx, cy);
    }
    return toS(+el.getAttribute('cx'), +el.getAttribute('cy'));
  });
  // směry lokálních os pásu NA OBRAZOVCE (pro tažení po otočené stránce)
  const ux = pts[1].x - pts[0].x, uy = pts[1].y - pts[0].y;
  const vx = pts[3].x - pts[0].x, vy = pts[3].y - pts[0].y;
  const nu = Math.hypot(ux, uy) || 1, nv = Math.hypot(vx, vy) || 1;
  const axes = {
    u: {x: (m.a * ux + m.c * uy) / nu, y: (m.b * ux + m.d * uy) / nu},
    v: {x: (m.a * vx + m.c * vy) / nv, y: (m.b * vx + m.d * vy) / nv},
  };
  return JSON.stringify({found: true, pts, grips, axes,
                         screen: pts.map(p => toS(p.x, p.y)),
                         page: window.__navdbg ? window.__navdbg().page : null,
                         scale: Math.hypot(m.a, m.b)});
})()"""


def bbox(pts):
    xs = [p["x"] for p in pts]
    ys = [p["y"] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def area(pts):
    s = 0.0
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        s += a["x"] * b["y"] - b["x"] * a["y"]
    return abs(s) / 2


async def drag(h, x0, y0, x1, y1, steps=12):
    await h.pen_down(x0, y0)
    for i in range(1, steps + 1):
        await h.pen_move(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        await asyncio.sleep(0.02)
    await h.pen_up(x1, y1)
    await asyncio.sleep(0.6)


async def state(h):
    return json.loads(await h.ev(STATE_JS))


async def main():
    ok = Check()
    pdf = m.make_pdf(4)
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        free = await h.free_point()
        # Pás kreslíme NÍŽ, než je volný bod: otočné kolečko je 46 px NAD pásem
        # a v malém okně headless prohlížeče by jinak zmizelo pod panelem
        # nástrojů (ten sahá do y≈472).
        x, y = free["x"], free["y"] + 80

        print("tool highlighter:", await h.ev(TOOL_JS % json.dumps("Zvýraznění")))
        await asyncio.sleep(0.3)
        await h.pen_tap(x - 75, y + 12)
        await h.pen_tap(x - 75, y - 12)
        await h.pen_tap(x + 75, y)
        await asyncio.sleep(0.5)

        print("tool edit:", await h.ev(TOOL_JS % json.dumps("Upravit")))
        await asyncio.sleep(0.4)
        await h.pen_tap(x, y)
        await asyncio.sleep(0.5)

        s0 = await state(h)
        ok("pás existuje", s0.get("found") is True, str(s0)[:100])
        if not s0.get("found"):
            return ok.report()
        ok("vybraný pás má 5 úchytek (4 strany + kolečko)", len(s0["grips"]) == 5,
           f"grips={len(s0['grips'])}")
        if len(s0["grips"]) != 5:
            return ok.report()

        x1, y1, x2, y2 = bbox(s0["pts"])
        w0, h0 = x2 - x1, y2 - y1
        a0 = area(s0["pts"])
        print(f"start bbox {x1:.1f},{y1:.1f} .. {x2:.1f},{y2:.1f}  ({w0:.1f} x {h0:.1f})")

        # 1) PRAVÁ strana doprava o 60 px obrazovky
        g = s0["grips"][1]
        await drag(h, g["x"], g["y"], g["x"] + 60, g["y"])
        s1 = await state(h)
        bx1, by1, bx2, by2 = bbox(s1["pts"])
        ok("pravá hrana se roztáhla", abs((bx2 - x2) - 60 / s0["scale"]) < 4,
           f"Δright={(bx2 - x2):.1f}px vrstvy, očekáváno {60 / s0['scale']:.1f}")
        ok("levá hrana zůstala na místě", abs(bx1 - x1) < 1.5, f"Δleft={(bx1 - x1):.2f}")
        ok("výška se nezměnila", abs((by2 - by1) - h0) < 1.5, f"Δh={(by2 - by1) - h0:.2f}")

        # 2) HORNÍ strana nahoru o 30 px obrazovky
        g = s1["grips"][0]
        await drag(h, g["x"], g["y"], g["x"], g["y"] - 30)
        s2 = await state(h)
        cx1, cy1, cx2, cy2 = bbox(s2["pts"])
        ok("horní hrana se posunula nahoru", abs((cy1 - by1) + 30 / s0["scale"]) < 4,
           f"Δtop={(cy1 - by1):.1f}px vrstvy, očekáváno {-30 / s0['scale']:.1f}")
        ok("dolní hrana zůstala na místě", abs(cy2 - by2) < 1.5, f"Δbottom={(cy2 - by2):.2f}")
        ok("šířka se nezměnila", abs((cx2 - cx1) - (bx2 - bx1)) < 1.5,
           f"Δw={(cx2 - cx1) - (bx2 - bx1):.2f}")

        # 3) otočné kolečko: otočit o ~40°
        g = s2["grips"][4]
        cxs = (cx1 + cx2) / 2
        cys = (cy1 + cy2) / 2
        # kolečko je nahoře; otočit do strany o úhel kolem středu
        import math
        r = math.hypot(g["x"] - cxs, g["y"] - cys)
        ang0 = math.atan2(g["y"] - cys, g["x"] - cxs)
        ang1 = ang0 + math.radians(40)
        tx, ty = cxs + r * math.cos(ang1), cys + r * math.sin(ang1)
        await drag(h, g["x"], g["y"], tx, ty)
        s3 = await state(h)
        # osový obdélník má vrcholy po dvou na stejných x/y; pootočený ne
        xs3 = sorted(round(p["x"], 1) for p in s3["pts"])
        ys3 = sorted(round(p["y"], 1) for p in s3["pts"])
        axis_aligned = (len(set(xs3)) <= 2 and len(set(ys3)) <= 2)
        ok("kolečko pás otočilo", not axis_aligned, f"x={xs3} y={ys3}")
        a3 = area(s3["pts"])
        ok("otočení nezměnilo plochu", abs(a3 - area(s2["pts"])) / max(a3, 1) < 0.05,
           f"{area(s2['pts']):.1f} -> {a3:.1f}")

        # 4) úchytka musí fungovat i na pootočeném pásu: pravá strana ven
        g = s3["grips"][1]
        await drag(h, g["x"], g["y"], g["x"] + 25, g["y"])
        s4 = await state(h)
        ok("rozměr jde měnit i po otočení", area(s4["pts"]) > a3 + 1,
           f"{a3:.1f} -> {area(s4['pts']):.1f}")

        # 5) UPROSTŘED pásu se pořád posouvá CELÝ pás (úchytky neberou plochu)
        c = {"x": sum(p["x"] for p in s4["pts"]) / 4, "y": sum(p["y"] for p in s4["pts"]) / 4}
        sc = [p for p in s4["screen"]]
        scx = sum(p["x"] for p in sc) / 4
        scy = sum(p["y"] for p in sc) / 4
        d0 = s4["pts"]
        await drag(h, scx, scy, scx + 20, scy + 15)
        s5 = await state(h)
        moved = all(abs(a["x"] - b["x"]) > 0.5 or abs(a["y"] - b["y"]) > 0.5
                    for a, b in zip(d0, s5["pts"]))
        ok("tažení uprostřed posune celý pás", moved,
           f"Δ={[round(s5['pts'][i]['x'] - d0[i]['x'], 1) for i in range(4)]}")

        # 5b) PRSTEM (dotyk, ne pero): dlaňová ochrana nesmí blokovat chycení úchytky
        await asyncio.sleep(1.1)   # ať od posledního tahu perem uplyne PEN_GUARD_MS
        g = s5["grips"][3]          # levá strana
        l0 = s5["pts"]
        await h.finger_swipe(g["x"], g["y"], g["x"] - 30, g["y"], r=12, steps=10)
        await asyncio.sleep(0.5)
        s5b = await state(h)
        ok("prstem jde chytit úchytku a roztáhnout levou stranu",
           area(s5b["pts"]) > area(l0) + 1
           and abs(s5b["pts"][1]["x"] - l0[1]["x"]) < 1.5
           and abs(s5b["pts"][2]["x"] - l0[2]["x"]) < 1.5,
           f"plocha {area(l0):.0f} -> {area(s5b['pts']):.0f}")
        ok("dotyk na úchytce neotočil stránku", s5b.get("page") == 0,
           f"page={s5b.get('page')}")
        s5 = s5b

        # 6) OTOČENÁ STRÁNKA o 90°: úchytky musí sedět na pásu a rozměr fungovat
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Rotace stránky'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(0.5)
        await h.ev("(() => { const b=[...document.querySelectorAll('button')]"
                   ".find(x=>(x.title||'')==='Otočit vlevo o 90°'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(1.5)
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Rotace stránky'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(0.5)
        # Rotace vypne anotační režim (jako každé otevření panelu) — vrátit se
        # do anotace a znovu vzít ruku, jinak vrstva nechytá dotyk.
        if not json.loads(await h.ev("JSON.stringify(window.__navdbg().annotMode)")):
            await h.annot_toggle()
            await asyncio.sleep(0.5)
        if (await h.ev("window.__navdbg().tool")) != "edit":
            await h.ev(TOOL_JS % json.dumps("Upravit"))
            await asyncio.sleep(0.4)
        sR0 = await state(h)
        ok("pás přežil otočení stránky", sR0.get("found") is True, str(sR0)[:80])
        if not sR0.get("found"):
            return ok.report()
        # vybrat pás znovu (rotace ruší výběr). Klepnutí musí trefit PLOCHU pásu;
        # po otočení může střed pásu ležet pod plovoucím panelem, proto zkusíme
        # i jiné body uvnitř čtyřúhelníku.
        sp = sR0["screen"]
        cands = [(sum(p["x"] for p in sp) / 4, sum(p["y"] for p in sp) / 4),
                 ((sp[0]["x"] + sp[2]["x"]) / 2, (sp[0]["y"] + sp[2]["y"]) / 2),
                 ((sp[0]["x"] + sp[1]["x"]) / 2, (sp[0]["y"] + sp[1]["y"]) / 2)]
        sR = sR0
        for cxp, cyp in cands:
            tgt = await h.ev("(() => { const e=document.elementFromPoint(%f,%f);"
                             " return e ? e.tagName+'.'+(e.getAttribute('class')||'') : 'none'; })()"
                             % (cxp, cyp))
            print("   kandidát", round(cxp), round(cyp), "->", tgt)
            if not str(tgt).startswith("svg"):
                continue
            await h.pen_tap(cxp, cyp)
            await asyncio.sleep(0.5)
            sR = await state(h)
            if len(sR["grips"]) == 5:
                break
        ok("po otočení má vybraný pás zase 5 úchytek", len(sR["grips"]) == 5,
           f"grips={len(sR['grips'])}")
        if len(sR["grips"]) == 5:
            g = sR["grips"][1]                 # pravá strana
            u = sR["axes"]["u"]                # její směr NA OBRAZOVCE
            await drag(h, g["x"], g["y"], g["x"] + u["x"] * 30, g["y"] + u["y"] * 30)
            sR1 = await state(h)
            ok("rozměr jde měnit i na otočené stránce",
               area(sR1["pts"]) > area(sR["pts"]) + 1,
               f"plocha {area(sR['pts']):.0f} -> {area(sR1['pts']):.0f}")
            ok("u otočeného pásu zůstala protější strana na místě",
               max(abs(sR1["pts"][0]["x"] - sR["pts"][0]["x"]),
                   abs(sR1["pts"][0]["y"] - sR["pts"][0]["y"]),
                   abs(sR1["pts"][3]["x"] - sR["pts"][3]["x"]),
                   abs(sR1["pts"][3]["y"] - sR["pts"][3]["y"])) < 1.5,
               "levá strana se pohnula")
            s5 = sR1
        # vrátit stránku do svislé polohy
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'')==='Rotace stránky'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(0.4)
        await h.ev("(() => { const b=[...document.querySelectorAll('button')]"
                   ".find(x=>(x.title||'')==='Klepnutím zrušit otočení'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(1.2)

        # 7) přežije překreslení stránky
        before = json.dumps(s5["pts"])
        await h.goto(2)
        await asyncio.sleep(0.6)
        await h.goto(1)
        await asyncio.sleep(0.8)
        s6 = await state(h)
        ok("úprava zůstala po překreslení", json.dumps(s6["pts"]) == before,
           f"{before[:60]} vs {json.dumps(s6.get('pts'))[:60]}")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
