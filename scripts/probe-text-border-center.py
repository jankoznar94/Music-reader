#!/usr/bin/env python3
"""Rámeček textu: VYCENTROVÁNÍ + volitelná šířka a styl rámu (Jan, Oct 2026).

Jan po prvním nasazení: „Text teď není v rámečku vycentrovaný. A velikost a styl
rámečku by měl být taky na výběr.“

Dvě chyby, které to způsobily (obě v kódu appky, obě naměřené):
  1. rám se počítal z ODHADU (0,62 em na znak) → text seděl vodorovně mimo střed;
  2. výška se násobila poměrem místo použití naměřené hodnoty → rám 312 px místo
     35 px u dvacetibodového textu, text u spodku rámu.

⚠️ Jak to měřit, aby to NELHALO:
  - „text je uvnitř rámu“ projde i s tou chybou — kontroluj ODCHYLKU STŘEDŮ.
  - Vodorovně je referencí ADVANCE box <text> (tam text začíná a končí), proto
    se dx dá měřit přímo z DOM.
  - Svisle je referencí OTISK PÍSMEN, a ten se v prohlížeči měří jen přes canvas.
    Účaří vrstvy je na screen y = horní hrana `.annot-layer` (měřítko 1), z něj
    a z metrik canvasu se spočítá střed otisku — na appce NEZÁVISLE.
  - Sonda musí brát v úvahu, že si dialog PAMATUJE minulou volbu: přepínač
    rámečku se musí DOROVNAT na požadovaný stav, ne slepě přepnout.

    NOTY_CDP=http://127.0.0.1:9247 python3 scripts/probe-text-border-center.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")


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

# Měření otisku písma v prohlížeči (canvas) — stejná definice, jakou používá appka,
# ale spočítaná nezávisle na jejím stavu.
# ⚠️ `h.ev` vyhodnocuje výrazy ve STEJNÉM globálním kontextu, takže `const ink`
# při druhém volání spadne na „Identifier 'ink' has already been declared“.
# Proto je pomocná funkce UVNITŘ IIFE, ne vedle ní.
JS_INK = """
const ink = (text, size) => {
  const c = document.createElement('canvas').getContext('2d');
  c.font = size + 'px system-ui, sans-serif';
  const m = c.measureText(text || 'H');
  return { asc: m.actualBoundingBoxAscent, desc: m.actualBoundingBoxDescent,
           w: m.width };
};
"""


async def tap_el(h, sel, hold_ms=60):
    pt = await h.ev("""(() => {
      const el = document.querySelector(%s); if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(%s) === el))) return [x+0.5, y+0.5];
        }
      return null; })()""" % (json.dumps(sel), json.dumps(sel)))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.4)
    return True


async def tap_text(h, sel, label, hold_ms=60):
    """Dotyk na tlačítko podle jeho popisku (čipy šířky/stylu)."""
    pt = await h.ev("""(() => {
      const el = [...document.querySelectorAll(%s)].find(b => (b.textContent||'').trim() === %s);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2)
          if (document.elementFromPoint(x, y) === el) return [x+0.5, y+0.5];
      return null; })()""" % (json.dumps(sel), json.dumps(label)))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.4)
    return True


async def set_border(h, want):
    """Dorovnej přepínač rámečku na požadovaný stav (dialog si volbu pamatuje)."""
    for _ in range(3):
        on = await h.ev("!!document.querySelector('.ti-toggle.on')")
        if on == bool(want):
            return True
        await tap_el(h, ".ti-toggle")
    return False


async def use_text_tool(h):
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.title || '').startsWith('Text')); if (b) b.click(); })()")
    await asyncio.sleep(0.4)


async def free_xy(h):
    p = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y) => boxes.some(r => r.width > 0 &&
        x > r.left - 34 && x < r.right + 34 && y > r.top - 34 && y < r.bottom + 34);
      for (const fy of [0.30, 0.38, 0.46, 0.54, 0.62]) for (const fx of [0.60, 0.52, 0.44, 0.36, 0.68, 0.28]) {
        const x = v.left + v.width * fx, y = v.top + v.height * fy;
        if (document.elementFromPoint(x, y) === svg && !near(x, y)) return {x, y};
      }
      return null; })()""")
    return (p["x"], p["y"]) if p else None


async def put_text(h, text, size=None, border=True, width=None, style=None):
    """Vloží text se zvoleným rámem (volby se dorovnají, ne slepě přepnou)."""
    xy = await free_xy(h)
    if not xy:
        return False
    await h.pen_tap(xy[0], xy[1])
    await asyncio.sleep(0.8)
    if not await h.ev("!!document.querySelector('.text-input-overlay')"):
        return False
    await h.set_value(".ti-input", text)
    if size is not None:
        for _ in range(40):
            cur = await h.ev("Number((document.querySelector('.ti-size-val')||{}).textContent)")
            if cur == size:
                break
            await tap_el(h, ".ti-size-btn:last-of-type" if cur < size else ".ti-size-btn")
    await set_border(h, border)
    await asyncio.sleep(0.3)
    if border and width is not None:
        await tap_text(h, ".ti-chip", str(width))
    if border and style is not None:
        await tap_text(h, ".ti-chip", style)
    await tap_el(h, ".jp-btn.primary")
    await asyncio.sleep(1.2)
    return not await h.ev("!!document.querySelector('.text-input-overlay')")


async def saved_texts(h):
    raw = await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const n = (dbs.map(d=>d.name)||[]).find(x=>/noty|music|reader/i.test(x)); if (!n) return '[]';
      const db = await new Promise((res,rej)=>{const r=indexedDB.open(n);r.onsuccess=()=>res(r.result);r.onerror=()=>rej(String(r.error));});
      const all = s => new Promise(res => { if (!db.objectStoreNames.contains(s)) return res(null);
        const r = db.transaction(s,'readonly').objectStore(s).getAll(); r.onsuccess=()=>res(r.result); r.onerror=()=>res(null); });
      const out = [];
      for (const s of [...db.objectStoreNames]) { const rows = await all(s); if (!Array.isArray(rows)) continue;
        for (const row of rows) for (const i of ((row&&row.items)||[]))
          if (i && i.tool === 'text') out.push({text:i.text,size:i.size,color:i.color,
            border:i.border===true,borderWidth:i.borderWidth,borderStyle:i.borderStyle}); }
      db.close(); return JSON.stringify(out); })()""", await_promise=True)
    return json.loads(raw) if raw else []


async def geometry(h, text):
    """Změř rám a text. Vodorovně z DOM, svisle z canvasu přes účaří vrstvy."""
    raw = await h.ev("(() => {" + JS_INK + """return (() => {
      const want = %s;
      const svg = document.querySelector('.annot-layer');
      if (!svg) return null;
      const layerTop = svg.getBoundingClientRect().top;   // měřítko 1 → účaří y=0
      for (const g of svg.querySelectorAll('g')) {
        const t = g.querySelector(':scope > text');
        if (!t || (t.textContent || '') !== want) continue;
        const rects = [...g.querySelectorAll(':scope > rect.text-border')];
        if (!rects.length) return JSON.stringify({ hasRect: false });
        const r = rects.reduce((a, b) => {
          const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
          return (rb.width * rb.height > ra.width * ra.height) ? b : a;
        });
        const tb = t.getBoundingClientRect(), rb = r.getBoundingClientRect();
        const size = Number(t.getAttribute('font-size')) || 20;
        const k = ink(want, size);
        // Účaří v souřadnicích vrstvy = atribut `y` textu; na obrazovce je to
        // horní hrana vrstvy + y. Bez toho přičtení vyjde otisk o stovky px jinde.
        const baseline = layerTop + (Number(t.getAttribute('y')) || 0);
        // Otisk: horní hrana = účaří − ascent, dolní = účaří + descent.
        const inkTop = baseline - k.asc, inkBot = baseline + k.desc;
        const inkCy = (inkTop + inkBot) / 2;
        const rcx = rb.left + rb.width / 2, rcy = rb.top + rb.height / 2;
        const tcx = tb.left + tb.width / 2;
        return JSON.stringify({
          hasRect: true, rects: rects.length,
          dx: tcx - rcx, dy: inkCy - rcy,
          gapL: tb.left - rb.left, gapR: (rb.left + rb.width) - (tb.left + tb.width),
          gapT: inkTop - rb.top, gapB: (rb.top + rb.height) - inkBot,
          rw: rb.width, rh: rb.height,
          textW: tb.width, inkH: k.desc + k.asc, size,
          xAttr: r.getAttribute('x'), wAttr: r.getAttribute('width'),
          dash: rects[0].getAttribute('stroke-dasharray'),
          stroke: rects[0].getAttribute('stroke'),
        });
      }
      return null; })()""" % json.dumps(text) + "})()")
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


async def dialog_chips(h):
    raw = await h.ev("""(() => {
      const chips = [...document.querySelectorAll('.ti-chip')];
      const toggles = [...document.querySelectorAll('.ti-toggle')];
      return JSON.stringify({
        chipCount: chips.length,
        labels: chips.map(c => (c.textContent || '').trim()),
        selected: chips.filter(c => c.classList.contains('on')).map(c => (c.textContent || '').trim()),
        borderOn: toggles.length ? toggles[0].classList.contains('on') : null,
        previews: document.querySelectorAll('.ti-size-sample').length,
      }); })()""")
    return json.loads(raw) if raw else {}


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(8))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await use_text_tool(h)

        # --- 1) VYCENTROVÁNÍ: krátký i dlouhý text, dvě velikosti -----------------
        for label, size in [("a", 20), ("Bb", 20), ("oramovany text", 20),
                            ("delší poznámka na noty", 32)]:
            txt = f"c{label}"
            placed = await put_text(h, txt, size=size, border=True)
            await asyncio.sleep(0.5)
            g = await geometry(h, txt)
            if not (placed and g and g.get("hasRect")):
                ok(f"1) text „{txt}“ (vel. {size}) se vložil s rámem", False,
                   f"placed={placed} geo={g}")
                continue
            ok(f"1) text „{txt}“ (vel. {size}) je VYCENTROVANÝ (odchylka středů ≤ 1,5 px)",
               abs(g["dx"]) <= 1.5 and abs(g["dy"]) <= 1.5,
               f"dx={g['dx']:.2f} dy={g['dy']:.2f} | mezery L/R/T/B="
               f"{[round(g[k],1) for k in ('gapL','gapR','gapT','gapB')]} | "
               f"text {g['textW']:.1f}×{g['inkH']:.1f}")
            ok(f"1b) text „{txt}“: rám je ČTVEREC a sedí na velikost textu",
               abs(g["rw"] - g["rh"]) <= 1.5
               and g["rw"] <= max(g["textW"], g["inkH"]) + 2 * 16 + 2,
               f"{g['rw']:.1f} x {g['rh']:.1f} (text {g['textW']:.1f} x {g['inkH']:.1f})")
            ok(f"1c) text „{txt}“: protilehlé mezery jsou STEJNÉ (rám je souměrný)",
               abs(g["gapL"] - g["gapR"]) <= 1.5 and abs(g["gapT"] - g["gapB"]) <= 1.5,
               f"L={g['gapL']:.1f} R={g['gapR']:.1f} T={g['gapT']:.1f} B={g['gapB']:.1f} "
               f"(svisle větší mezera je důsledek ČTVERCE — vodorovná strana určuje hranu)")

        # --- 2) dialog nabízí šířku i styl (přepínač dorovnat na ZAP) -----------
        xy = await free_xy(h)
        await h.pen_tap(xy[0], xy[1]); await asyncio.sleep(0.8)
        await set_border(h, True)
        await asyncio.sleep(0.3)
        ch = await dialog_chips(h)
        ok("2a) dialog nabízí šířku rámu (5 voleb)",
           sum(1 for x in ch.get("labels", []) if x in ("4", "6", "8", "12", "16")) == 5,
           json.dumps(ch, ensure_ascii=False))
        ok("2b) dialog nabízí styl rámu (Plná/Čárky/Tečky/Dvojitá)",
           all(s in ch.get("labels", []) for s in ("Plná", "Čárky", "Tečky", "Dvojitá")),
           json.dumps(ch, ensure_ascii=False))
        ok("2c) v dialogu je náhled rámečku („Aa“)", ch.get("previews", 0) >= 1,
           json.dumps(ch, ensure_ascii=False))

        # --- 3) zvolená šířka + styl se propíšou do anotace i na plátno ---------
        await h.set_value(".ti-input", "stylovy")
        await tap_text(h, ".ti-chip", "12")
        await tap_text(h, ".ti-chip", "Čárky")
        ch3 = await dialog_chips(h)
        ok("3a) dialog hlásí zvolenou šířku 12 a styl Čárky",
           "12" in ch3.get("selected", []) and "Čárky" in ch3.get("selected", []),
           json.dumps(ch3, ensure_ascii=False))
        await tap_el(h, ".jp-btn.primary"); await asyncio.sleep(1.2)
        mine = [t for t in await saved_texts(h) if t.get("text") == "stylovy"]
        ok("3b) ULOŽENÝ text má šířku 12 a styl dashed",
           bool(mine) and mine[0].get("borderWidth") == 12 and mine[0].get("borderStyle") == "dashed",
           f"ulozeno={mine}")
        g3 = await geometry(h, "stylovy")
        ok("3c) rám na plátně má čárkovanou čáru",
           g3 and g3.get("hasRect") and g3.get("dash") == "7 5", json.dumps(g3, ensure_ascii=False))
        ok("3d) i se širším rámem zůstal text vycentrovaný",
           g3 and abs(g3["dx"]) <= 1.5 and abs(g3["dy"]) <= 1.5,
           f"dx={g3['dx']:.2f} dy={g3['dy']:.2f}")
        ok("3e) šířka rámu se projevila (odstup ≥ 11 px na všech stranách)",
           g3 and min(g3["gapL"], g3["gapR"], g3["gapT"], g3["gapB"]) >= 11,
           f"mezery={[round(g3[k],1) for k in ('gapL','gapR','gapT','gapB')]}")

        # --- 4) dvojitý rám = DVĚ linky ----------------------------------------
        # POZOR: dialog je po Uložit ZAVŘENÝ, takže se čip musí vzít v pásu úprav
        # (ruka + výběr), ne v dialogu — jinak sonda kliká do neexistujícího UI
        # a měří starý stav (přesně to se stalo napoprvé).
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Upravit')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)
        pt4 = await h.ev("""(() => { const svg = document.querySelector('.annot-layer');
          for (const g of svg.querySelectorAll('g')) { const t = g.querySelector(':scope > text');
            if (!t || (t.textContent||'') !== 'stylovy') continue;
            const r = t.getBoundingClientRect();
            return { x: r.left + 8, y: r.top + r.height / 2 }; }
          return null; })()""")
        if pt4:
            await h.pen_tap(pt4["x"], pt4["y"]); await asyncio.sleep(0.6)
        await tap_text(h, ".eb-chip", "Dvojitá")
        await asyncio.sleep(0.6)
        g4 = await geometry(h, "stylovy")
        ok("4) dvojitá linka se kreslí DVĚMA obdélníky", g4 and g4.get("rects") == 2,
           json.dumps(g4, ensure_ascii=False))
        ok("4b) dvojitý rám zůstal čtverec a text vycentrovaný",
           g4 and abs(g4["rw"] - g4["rh"]) <= 1.5 and abs(g4["dx"]) <= 1.5 and abs(g4["dy"]) <= 1.5,
           f"{g4['rw']:.1f} x {g4['rh']:.1f} dx={g4['dx']:.2f} dy={g4['dy']:.2f}")
        saved4 = [t for t in await saved_texts(h) if t.get("text") == "stylovy"]
        ok("4c) styl double se uložil a šířka 12 zůstala",
           bool(saved4) and saved4[0].get("borderStyle") == "double"
           and saved4[0].get("borderWidth") == 12, f"ulozeno={saved4}")

        # --- 5) volby přežijí reload -------------------------------------------
        await h.open()
        await h.open_song(pdf=_m.make_pdf(8), reset=False)
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await use_text_tool(h)
        xy5 = await free_xy(h)
        await h.pen_tap(xy5[0], xy5[1]); await asyncio.sleep(0.8)
        ch5 = await dialog_chips(h)
        ok("5) po reloadu dialog nabízí stejnou šířku i styl",
           "12" in ch5.get("selected", []) and "Dvojitá" in ch5.get("selected", []),
           json.dumps(ch5, ensure_ascii=False))
        await tap_el(h, ".jp-btn:not(.primary):not(.hand)"); await asyncio.sleep(0.4)

        # --- 6) změna rámu u VLOŽENÉHO textu v pásu úprav ----------------------
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Upravit')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)
        pt = await h.ev("""(() => { const svg = document.querySelector('.annot-layer');
          for (const g of svg.querySelectorAll('g')) { const t = g.querySelector(':scope > text');
            if (!t || (t.textContent||'') !== 'stylovy') continue;
            const r = t.getBoundingClientRect();
            return { x: r.left + 8, y: r.top + r.height / 2 }; }
          return null; })()""")
        if pt:
            await h.pen_tap(pt["x"], pt["y"]); await asyncio.sleep(0.6)
        bar = await h.ev("""(() => JSON.stringify({
          bar: !!document.querySelector('.edit-bar'),
          chips: [...document.querySelectorAll('.eb-chip')].map(c => (c.textContent||'').trim()),
        }))()""")
        bar = json.loads(bar)
        ok("6a) pás úprav u vloženého textu nabízí šířku i styl rámu",
           bar["bar"] and "12" in bar["chips"] and "Tečky" in bar["chips"],
           json.dumps(bar, ensure_ascii=False))
        await tap_text(h, ".eb-chip", "8")
        await tap_text(h, ".eb-chip", "Tečky")
        await asyncio.sleep(0.8)
        after = [t for t in await saved_texts(h) if t.get("text") == "stylovy"]
        ok("6b) změna v pásu úprav se ULOŽILA (8 / dotted)",
           bool(after) and after[0].get("borderWidth") == 8 and after[0].get("borderStyle") == "dotted",
           f"ulozeno={after}")
        g6 = await geometry(h, "stylovy")
        ok("6c) na plátně je tečkovaný rám a text zůstal vycentrovaný",
           g6 and g6.get("dash") == "1.5 4" and abs(g6["dx"]) <= 1.5 and abs(g6["dy"]) <= 1.5,
           json.dumps(g6, ensure_ascii=False))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
