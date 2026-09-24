#!/usr/bin/env python3
"""Lišta po VYTAŽENÍ ukládacích tlačítek na hlavní lištu.

Jan: „tlačítko pro uložení stavu dané stránky vytáhnout na hlavní lištu. Když
ho teď sdílí dvě různé funkce. To stejné tlačítko pro uložení globálního
[zobrazení] a vycentrování" → na lištu šla VŠECHNA TŘI: Vycentrovat,
Uložit stav této stránky, Uložit jako výchozí pro celou skladbu.

Tím má lišta 10 tlačítek. Ověřuje se proto na pěti šířkách:
  * lišta nepřetéká (obsah <= viditelná šířka)
  * ŽÁDNÉ dva prvky se nepřekrývají (počítadlo vs tlačítka obou skupin)
  * tři vytažená tlačítka existují a jsou klikatelná
  * tři vytažená tlačítka už NEJSOU v panelu zoomu (nesmí zůstat duplicitně)
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

# všechny klikatelné prvky lišty + počítadlo, s překryvovou kontrolou
MEASURE = r"""
(() => {
  const bar = document.querySelector('.top-bar');
  const els = [];
  bar.querySelectorAll('.tb-btn, .tb-page, .tb-nav button').forEach(b => {
    const r = b.getBoundingClientRect();
    els.push({ t: (b.title||b.textContent.trim()).slice(0,26),
               x:+r.left.toFixed(1), r:+r.right.toFixed(1), w:+r.width.toFixed(1) });
  });
  const cnt = bar.querySelector('.tb-page-center');
  const cr = cnt.getBoundingClientRect();
  const cs = getComputedStyle(cnt);
  // každá dvojice, která se reálně překrývá (tolerance 0,5 px)
  const ov = [];
  for (let i=0;i<els.length;i++) for (let j=i+1;j<els.length;j++)
    if (els[i].r > els[j].x + 0.5 && els[j].r > els[i].x + 0.5)
      ov.push(els[i].t + ' × ' + els[j].t);
  const inside = el => el && el.closest('.top-bar') !== null;
  const titles = [...document.querySelectorAll('.top-bar .tb-btn')].map(b=>b.title);
  return {
    winW: window.innerWidth,
    barW: +bar.getBoundingClientRect().width.toFixed(1),
    scrollW: bar.scrollWidth, clientW: bar.clientWidth,
    scrollable: bar.scrollWidth > bar.clientWidth + 1,
    counterPos: cs.position,
    counter: [+cr.left.toFixed(1), +cr.right.toFixed(1)],
    count: els.length,
    overlaps: ov,
    titles,
    // vytažená tlačítka: na liště?
    onBar: {
      center: titles.some(t=>(t||'').startsWith('Vycentrovat')),
      page:   titles.some(t=>(t||'').startsWith('Uložit jako výchozí jen pro tuto stránku')),
      global: titles.some(t=>(t||'').startsWith('Uložit jako výchozí pro celou skladbu')),
    },
    // a zůstala (omylem) i v panelu zoomu?
    inZoomPanel: [...document.querySelectorAll('.zoom-panel .zp-btn')]
        .map(b=>(b.title||'')).filter(t=>t.startsWith('Vycentrovat') ||
        t.startsWith('Uložit jako výchozí')),
  };
})()
"""


async def run():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.0)
        await h.open_song(pages=6)
        for w, hh, name in ((1100, 800, "široký 1100"), (800, 1280, "tablet 800"),
                            (700, 1000, "700"), (620, 900, "hranice 620"),
                            (390, 844, "mobil 390")):
            await h.set_tablet(w, hh, 2)
            await asyncio.sleep(1.2)
            real = await h.ev("window.innerWidth")
            ok(f"[{name}] viewport se skutečně přepnul", real == w, f"innerWidth={real}")
            m = await h.ev(MEASURE)
            print(f"  [{name}] {m['barW']} px, obsah {m['scrollW']}/{m['clientW']}, "
                  f"prvků {m['count']}, počítadlo position={m['counterPos']}")
            for t in m["titles"]:
                print(f"      · {(t or '?')[:52]}")
            ok(f"[{name}] lišta nepřetéká", not m["scrollable"],
               f"{m['scrollW']} vs {m['clientW']}")
            ok(f"[{name}] ŽÁDNÉ dva prvky se nepřekrývají", not m["overlaps"],
               "; ".join(m["overlaps"][:3]))
            ok(f"[{name}] Vycentrovat je na liště", m["onBar"]["center"], "")
            ok(f"[{name}] Uložit stav TÉTO stránky je na liště", m["onBar"]["page"], "")
            ok(f"[{name}] Uložit pro CELOU skladbu je na liště", m["onBar"]["global"], "")
            ok(f"[{name}] žádné z nich nezůstalo v panelu zoomu",
               not m["inZoomPanel"], str(m["inZoomPanel"]))
            # klikatelnost všech tří
            for part in ("Vycentrovat", "Uložit jako výchozí jen pro tuto stránku",
                         "Uložit jako výchozí pro celou skladbu"):
                r = await h.ev(
                    "(() => { const b=[...document.querySelectorAll('.top-bar .tb-btn')]"
                    ".find(x=>(x.title||'').startsWith(%s));"
                    " if(!b) return null; const q=b.getBoundingClientRect();"
                    " const el=document.elementFromPoint((q.left+q.right)/2,(q.top+q.bottom)/2);"
                    " return {hit: !!el && (el===b || b.contains(el)),"
                    "         vis: q.right<=window.innerWidth && q.left>=0}; })()"
                    % json.dumps(part))
                ok(f"[{name}] „{part[:24]}…\" klikatelné",
                   r and r["hit"] and r["vis"], json.dumps(r))
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
