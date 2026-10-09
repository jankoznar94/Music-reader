#!/usr/bin/env python3
"""Měření PŘETEČENÍ lišty úprav (`.edit-bar`) na tabletu (Jan, Oct 2026).

Jan: „Při upravování vložených textů je teď nabídka možností tak široká, že
tlačítko ‚smazat‘ s ikonou koše utíká mimo lištu.“

Sonda neměří dojem, ale čísla:
  - šířka lišty vs. šířka displeje (tablet 800, mobil 390, desktop 1280),
  - `scrollWidth` vs `clientWidth` lišty (přetečení obsahu),
  - každé dítě lišty: levý/pravý okraj, zda přesahuje vnitřek lišty a zda
    přesahuje displej,
  - u KOŠE zvlášť: sedí střed tlačítka na `elementFromPoint` (tedy je opravdu
    klikatelný), nebo ho překrývá něco jiného,
  - nejširší stav (text s rámečkem: čipy šířky + stylu) i nejužší (dynamika).

Použití:
    bash scripts/run-probe-fresh.sh scripts/diag-editbar-overflow.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


def _load_harness():
    for cand in (
        os.path.expanduser("~/noty-app/cdp-e2e-harness.py"),
        "/home/martin_fabian/noty-app/cdp-e2e-harness.py",
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness, Check = _m.Harness, _m.Check


MEASURE_JS = """(() => {
  const bar = document.querySelector('.edit-bar');
  if (!bar) return JSON.stringify({bar: false});
  const vw = window.innerWidth, vh = window.innerHeight;
  const r = bar.getBoundingClientRect();
  const cs = getComputedStyle(bar);
  const inner = {
    left: r.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth),
    right: r.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth),
  };
  const kids = [...bar.children].map(el => {
    const q = el.getBoundingClientRect();
    const label = (el.textContent || '').trim() || (el.title || el.className);
    return {
      tag: el.tagName.toLowerCase(), cls: el.className, label: label.slice(0, 22),
      w: Math.round(q.width * 10) / 10,
      left: Math.round(q.left), right: Math.round(q.right), top: Math.round(q.top),
      overBar: q.right > inner.right + 0.6 || q.left < inner.left - 0.6,
      overScreen: q.right > vw || q.left < 0,
    };
  });
  const trash = bar.querySelector(".eb-btn[title='Smazat']");
  let trashHit = null, trashBox = null;
  if (trash) {
    const t = trash.getBoundingClientRect();
    const el = document.elementFromPoint(t.left + t.width / 2, t.top + t.height / 2);
    trashHit = !!(el && (el === trash || (el.closest && el.closest(".eb-btn[title='Smazat']") === trash)));
    trashBox = {left: Math.round(t.left), right: Math.round(t.right)};
  }
  return JSON.stringify({
    bar: true, vw, vh,
    barLeft: Math.round(r.left), barRight: Math.round(r.right),
    barW: Math.round(r.width * 10) / 10,
    barTop: Math.round(r.top), barBottom: Math.round(r.bottom),
    scrollW: bar.scrollWidth, clientW: bar.clientWidth,
    overflowing: bar.scrollWidth > bar.clientWidth + 1,
    innerLeft: Math.round(inner.left), innerRight: Math.round(inner.right),
    kids, trashHit, trashBox, nKids: bar.children.length,
  });
})()"""


async def _click_sel(h, sel, hold_ms=70):
    """Skutečný dotek na prvek (nejen el.click()) — v liště i dialogu jsou
    pojistky proti zbloudilému kliknutí, které programové klepnutí spolknou."""
    pt = await h.ev("""(() => {
      const sel = %s;
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top) + 1; y <= Math.ceil(r.bottom) - 1; y += 2)
        for (let x = Math.floor(r.left) + 1; x <= Math.ceil(r.right) - 1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(sel) === el))) return [x + 0.5, y + 0.5];
        }
      return null;
    })()""" % json.dumps(sel))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.6)
    return True


# Panel anotací se sbalí/rozbalí TÍMŽ tlačítkem (SVG bez textu) — stav poznáš
# z `title` ("Sbalit" = panel je rozbalený). Past: hledat podle textu vždy mine.
COLLAPSE = ".ap-collapse"


async def collapse_panel(h):
    if await h.ev("!!document.querySelector(%s[title='Sbalit'])" % json.dumps(COLLAPSE)):
        await _click_sel(h, COLLAPSE)
    await asyncio.sleep(0.4)


async def open_panel(h):
    if await h.ev("!!document.querySelector(%s[title='Rozbalit'])" % json.dumps(COLLAPSE)):
        await _click_sel(h, COLLAPSE)
    await asyncio.sleep(0.4)


async def pick_tool(h, title):
    await open_panel(h)
    r = await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.getAttribute('title') || '').startsWith(%s));"
                   " if (!b) return 'missing'; b.click(); return 'ok'; })()"
                   % json.dumps(title))
    await asyncio.sleep(0.35)
    return r


async def free_xy(h):
    return await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer');
      if (!svg) return null;
      const r = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y) => boxes.some(q => q.width > 0 &&
        x > q.left - 26 && x < q.right + 26 && y > q.top - 22 && y < q.bottom + 22);
      for (const fy of [0.34, 0.42, 0.50, 0.58, 0.26]) for (const fx of [0.60, 0.52, 0.44, 0.68, 0.36]) {
        const x = r.left + r.width * fx, y = r.top + r.height * fy;
        if (document.elementFromPoint(x, y) === svg && !near(x, y)) return {x, y};
      }
      return null;
    })()""")


async def insert_text(h, x, y, text):
    await pick_tool(h, "Text")
    await collapse_panel(h)
    await h.pen_tap(x, y)
    await asyncio.sleep(0.8)
    if not await h.ev("!!document.querySelector('.text-input-overlay')"):
        return False
    await h.set_value(".ti-input", text)
    await _click_sel(h, ".text-input-overlay .jp-btn.primary")
    await asyncio.sleep(1.0)
    return True


async def select_with_hand(h, x, y):
    await pick_tool(h, "Upravit")
    await collapse_panel(h)
    await h.pen_tap(x, y)
    await asyncio.sleep(0.9)


BORDER_BTN = ".edit-bar .eb-btn[title*='ráme']"


async def border_on(h):
    """Přepínač rámečku DOROVNEJ (nepřepínej naslepo — volba se pamatuje)."""
    st = await h.ev("""(() => { const b = document.querySelector(%s);
      if (!b) return 'missing'; return b.classList.contains('on') ? 'on' : 'off'; })()"""
                    % json.dumps(BORDER_BTN))
    if st == "off":
        await _click_sel(h, BORDER_BTN)
    return st


async def measure(h, label, ok, expect_fit=True):
    raw = await h.ev(MEASURE_JS)
    m = json.loads(raw)
    if not m.get("bar"):
        ok(label + " — lišta existuje", False, "lišta v DOM není")
        return None
    print(f"\n=== {label} (displej {m['vw']}×{m['vh']}) ===")
    print(f"  lišta: x {m['barLeft']}..{m['barRight']} (šířka {m['barW']}), "
          f"scrollW {m['scrollW']} vs clientW {m['clientW']}, dětí {m['nKids']}")
    print(f"  vnitřek lišty: {m['innerLeft']}..{m['innerRight']}, koš: "
          f"{m['trashBox']}, klikatelný: {m['trashHit']}")
    for k in m["kids"]:
        flag = ("PŘES LIŠTU" if k["overBar"] else "ok") + (" / MIMO DISPLEJ" if k["overScreen"] else "")
        print(f"    [{k['tag']:6}] {k['label']:24} w={k['w']:6} x={k['left']:5}..{k['right']:5}  {flag}")
    ok(label + " — obsah lišty se vejde do lišty", not m["overflowing"],
       f"scrollW={m['scrollW']} clientW={m['clientW']}")
    ok(label + " — žádné dítě nepřetéká vnitřek lišty",
       not any(k["overBar"] for k in m["kids"]),
       "; ".join(f"{k['label']}→{k['right']}" for k in m["kids"] if k["overBar"]) or "-")
    ok(label + " — koš je uvnitř displeje a klikatelný",
       m["trashHit"] is True, json.dumps({"trashHit": m["trashHit"], "koš": m["trashBox"]}))
    return m


async def scenario(h, ok, label, w, hh, dsf=2):
    await h.set_tablet(w, hh, dsf)
    got = await h.ev("window.innerWidth")
    if int(got) != w:
        print(f"   [!! emulace displeje nesedí: innerWidth={got}, chtěla jsem {w}]")
    await asyncio.sleep(0.4)
    return await measure(h, label, ok)


ANCESTORS_JS = """(() => {
  const bar = document.querySelector('.edit-bar');
  if (!bar) return 'no-bar';
  const out = [];
  let el = bar.parentElement;
  while (el && out.length < 8) {
    const cs = getComputedStyle(el);
    out.push({tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 40),
      pos: cs.position, tr: cs.transform === 'none' ? '-' : cs.transform.slice(0, 28),
      offW: el.offsetWidth, clientW: el.clientWidth});
    el = el.parentElement;
  }
  return JSON.stringify(out);
})()"""


BARSTYLE_JS = """(() => {
  const b = document.querySelector('.edit-bar');
  if (!b) return 'no-bar';
  const cs = getComputedStyle(b);
  const all = [...document.querySelectorAll('.edit-bar')].length;
  return JSON.stringify({n: all, pos: cs.position, disp: cs.display, width: cs.width,
    maxW: cs.maxWidth, minW: cs.minWidth, tr: cs.transform, box: cs.boxSizing,
    left: cs.left, right: cs.right, zoom: cs.zoom, rect: b.getBoundingClientRect().width,
    inline: b.getAttribute('style'), rows: [...b.children].map(c => c.getBoundingClientRect().width)});
})()"""


async def probe_ancestors(h):
    print("\n=== řetěz předků lišty (kdo určuje její šířku) ===")
    print(await h.ev(ANCESTORS_JS))
    print("STYL LIŠTY:", await h.ev(BARSTYLE_JS))


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await collapse_panel(h)

        p = await free_xy(h)
        ok("příprava: text se vložil", await insert_text(h, p["x"], p["y"], "Andante"), "")
        await select_with_hand(h, p["x"], p["y"])
        st = await border_on(h)
        print(f"   [rámeček před měřením: {st}]")

        await scenario(h, ok, "A) text s rámečkem — tablet 800", 800, 1280)
        await probe_ancestors(h)
        await scenario(h, ok, "B) text s rámečkem — mobil 390", 390, 844, 3)
        await scenario(h, ok, "C) text s rámečkem — desktop 1280", 1280, 800, 1)

        # Nejužší stav: dynamika (bez čipů rámu) pro srovnání
        await h.set_tablet(800, 1280, 2)
        await collapse_panel(h)
        p2 = await free_xy(h)
        if p2:
            await pick_tool(h, "Dynamika")
            await collapse_panel(h)
            await h.pen_tap(p2["x"], p2["y"])
            await asyncio.sleep(0.8)
            if await h.ev("!!document.querySelector('.text-input-overlay')"):
                await _click_sel(h, ".dyn-grid .dyn-btn")
            await select_with_hand(h, p2["x"], p2["y"])
            await measure(h, "D) dynamika (bez čipů rámu) — tablet 800", ok)
        else:
            print("\n[D) přeskočeno — nenašla jsem volné místo pro dynamiku]")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
