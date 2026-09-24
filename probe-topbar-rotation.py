#!/usr/bin/env python3
"""Měření horní lišty po přidání tlačítka ROTACE — nic se nesmí překrývat
a tlačítko musí být dosažitelné (i na mobilu) bez scrollování lišty.

⚠️ PAST: `set_tablet()` PŘEPÍNÁ DEVICE METRICS, ale měření hned po něm vrátí
staré hodnoty, dokud se view znovu nevykreslí — a `open_song()` defaultně volá
`reset_db()` (reload). Proto se zdejší měření dělá přes `Emulation.clearDevice…`
+ nové `set_tablet` a měří se až po opětovném otevření skladby. (V předchozím
běhu se „mobil 390" změřil jako 800 px — test prošel, ale měřil špatnou šířku;
to je přesně ta třída falešného OK, kterou je potřeba odhalit.)
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

MEASURE = r"""
(() => {
  const bar = document.querySelector('.top-bar');
  const br = bar.getBoundingClientRect();
  const items = [];
  bar.querySelectorAll('.tb-btn').forEach(b => {
    const r = b.getBoundingClientRect();
    items.push({ t: (b.title||'').slice(0, 24), x: +r.left.toFixed(1), r: +r.right.toFixed(1),
                 w: +r.width.toFixed(1) });
  });
  const cnt = document.querySelector('.tb-page-center');
  const cr = cnt.getBoundingClientRect();
  const bad = items.filter(i => i.t.includes('Rotace') || i.t.includes('Zvětšení'));
  const overlaps = bad.some(i => !(i.r <= cr.left || i.x >= cr.right));
  return {
    winW: window.innerWidth,
    barW: +br.width.toFixed(1),
    scrollW: bar.scrollWidth, clientW: bar.clientWidth,
    scrollable: bar.scrollWidth > bar.clientWidth + 1,
    counter: { x: +cr.left.toFixed(1), r: +cr.right.toFixed(1), t: cnt.textContent.trim() },
    counterOverlap: overlaps,
    items,
  };
})()
"""


async def run():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pages=6)          # nahraje fixture a otevře skladbu
        for w, hh, name in ((800, 1280, "tablet 800"), (390, 844, "mobil 390")):
            # přepni viewport a ověř, že se PROSAZENÍ SKUTEČNĚ projevilo
            await h.set_tablet(w, hh, 2)
            await asyncio.sleep(1.2)
            real = await h.ev("window.innerWidth")
            ok(f"[{name}] viewport se skutečně přepnul", real == w, f"innerWidth={real}")
            m = await h.ev(MEASURE)
            print(f"  [{name}] okno {m['winW']}px, lišta obsah {m['scrollW']} / vidno {m['clientW']}"
                  f"{'  (SCROLL!)' if m['scrollable'] else '  (vejde se)'}")
            for it in m["items"]:
                print(f"      {it['t']:<26} x {it['x']:>6} .. {it['r']:>6}  w {it['w']}")
            print(f"      počítadlo                  x {m['counter']['x']:>6} .. "
                  f"{m['counter']['r']:>6}  ({m['counter']['t']})")
            ok(f"[{name}] lišta se vejde bez scrollu", not m["scrollable"],
               f"obsah {m['scrollW']} vs {m['clientW']}")
            ok(f"[{name}] tlačítka zoom/rotace nekryjí počítadlo stránek",
               not m["counterOverlap"], "")
            ok(f"[{name}] tlačítko rotace je UVNITŘ displeje",
               any(i["t"].startswith("Rotace") and i["r"] <= m["winW"] for i in m["items"]),
               str([i for i in m["items"] if i["t"].startswith("Rotace")]))
            reach = await h.ev(
                "(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                ".find(x=>(x.title||'')==='Rotace stránky');"
                " if(!b) return null; const r=b.getBoundingClientRect();"
                " const el=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2);"
                " return {hit: !!el && (el===b || b.contains(el)),"
                "         vis: r.right<=window.innerWidth && r.left>=0}; })()")
            ok(f"[{name}] tlačítko rotace je klikatelné", reach and reach["hit"] and reach["vis"],
               json.dumps(reach))
            await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                       ".find(x=>(x.title||'')==='Rotace stránky'); b.click(); return true; })()")
            await asyncio.sleep(0.6)
            p = await h.ev(
                "(() => { const p=document.querySelector('.rot-panel'); if(!p) return null;"
                " const r=p.getBoundingClientRect();"
                " return {x:+r.left.toFixed(1), r:+r.right.toFixed(1),"
                "   inView: r.left>=-1 && r.right<=window.innerWidth+1}; })()")
            ok(f"[{name}] nabídka rotace se vejde na displej", p and p["inView"], json.dumps(p))
            # rotace tlačítky z nabídky: musí otočit a nesmí sáhnout na zoom
            b4 = await h.ev(
                "(() => { const s=document.querySelector('.stage');"
                " const m=new DOMMatrix(getComputedStyle(s).transform);"
                " return {sc:+Math.hypot(m.a,m.b).toFixed(4)}; })()")
            await h.ev("(() => { const b=[...document.querySelectorAll('.rot-panel .zp-btn')]"
                       ".find(x=>(x.title||'').startsWith('Otočit vpravo o 90')); b.click();"
                       " return true; })()")
            await asyncio.sleep(1.3)
            af = await h.ev(
                "(() => { const s=document.querySelector('.stage');"
                " const r=document.querySelector('.rotor');"
                " const m=new DOMMatrix(getComputedStyle(s).transform);"
                " const mr=new DOMMatrix(getComputedStyle(r).transform);"
                " return {sc:+Math.hypot(m.a,m.b).toFixed(4),"
                "   deg:+(Math.atan2(mr.b,mr.a)*180/Math.PI).toFixed(2)}; })()")
            ok(f"[{name}] tlačítko 90° v nabídce otočí stránku", abs(af["deg"] - 90) < 2,
               f"deg={af['deg']}")
            await h.ev("(() => { const b=[...document.querySelectorAll('.rot-panel .zp-rot')][0];"
                       " if(b) b.click(); return true; })()")
            await asyncio.sleep(1.2)
            await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                       ".find(x=>(x.title||'')==='Rotace stránky'); b.click(); return true; })()")
            await asyncio.sleep(0.4)
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
