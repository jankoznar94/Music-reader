#!/usr/bin/env python3
"""Výběr prvku rukou NESMÍ rovnou smazat prvek (Jan, Oct 2026).

Jan: „Když vyberu nástroj ‚ruka‘ a vyberu prvek, který je přímo na pozici
tlačítka ‚smazat‘ u okna pro editaci prvku, tak se rovnou smaže. Jak kdyby se
označení nástrojem ruka rovnou počítalo i jako pokyn po smazání.“

PŘÍČINA: výběr prvku vzniká už v `pointerdown` (`onLayerDown` → `editingId`),
takže lišta úprav se vykreslí POD PRSTEM a tentýž dotyk prohlížeč vzápětí
vyřídí jako kompatibilitní `click` — ten dopadne na to, co je na tom místě TEĎ,
tedy na tlačítko lišty (nejčastěji 🗑).

Sonda testuje přesně tuhle událost, ne geometrii:
  1. výběr rukou vyvolá lištu úprav a změří se místo tlačítka 🗑
  2. ZBLOUDILÉ klepnutí na místo 🗑 (bez předchozího položení v liště) →
     PRVEK MUSÍ ZŮSTAT a lišta i rámeček taky
     + kontrola, že to klepnutí opravdu mířilo na 🗑 (jinak by test nic nedokazoval)
  3. PROTIDŮKAZ: totéž klepnutí, ale PO položení uvnitř lišty (skutečné ťuknutí
     na tlačítko) → prvek se smaže. Pojistka tedy neblokuje normální ovládání.
  4. skutečný dotyk na 🗑 prvek smaže (end-to-end)
  5. skutečný dotyk na ✏️ otevře dialog (lišta není mrtvá)

    NOTY_CDP=http://127.0.0.1:9242 python3 scripts/probe-editbar-stray-click.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
TRASH = ".edit-bar .eb-btn[title='Smazat']"


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


# --- měření ---------------------------------------------------------------

async def item_count(h):
    """Počet ULOŽENÝCH anotací z IndexedDB — koš maže i v datech, ne jen v DOM."""
    raw = await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const name = (dbs.map(d => d.name) || []).find(n => /noty|music|reader/i.test(n));
      if (!name) return '-1';
      const db = await new Promise(res => { const r = indexedDB.open(name);
        r.onsuccess = () => res(r.result); r.onerror = () => res(null); });
      if (!db) return '-1';
      let n = 0;
      if (db.objectStoreNames.contains('annotations')) {
        const rows = await new Promise(res => {
          const r = db.transaction('annotations', 'readonly').objectStore('annotations').getAll();
          r.onsuccess = () => res(r.result); r.onerror = () => res(null); });
        for (const row of (rows || [])) n += ((row.items || []).length);
      }
      db.close();
      return String(n);
    })()""", await_promise=True)
    return int(raw)


async def bar_state(h):
    return json.loads(await h.ev("""(() => JSON.stringify({
      bar: !!document.querySelector('.edit-bar'),
      box: !!document.querySelector('.annot-selected'),
      ebType: (document.querySelector('.eb-type') || {}).textContent || null,
      editSize: (document.querySelector('.eb-val') || {}).textContent || null,
    }))()"""))


async def pick_tool(h, title):
    await h.ev("""(() => {
      const b = [...document.querySelectorAll('.ap-collapse, .ap-collapse-label')]
        .find(x => /Rozbalit/.test(x.textContent || '')); if (b) b.click(); return !!b; })()""")
    await asyncio.sleep(0.4)
    r = await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.getAttribute('title') || '').startsWith(%s));"
                   " if (!b) return 'missing'; b.click(); return 'ok'; })()"
                   % json.dumps(title))
    await asyncio.sleep(0.35)
    return r


async def collapse_panel(h):
    """Sbal panel — jinak sedí v pásu horní lišty a klepnutí do něj mine vrstvu."""
    await h.ev("""(() => {
      const b = [...document.querySelectorAll('.ap-collapse, .ap-collapse-label')]
        .find(x => /Sbalit/.test(x.textContent || '')); if (b) b.click(); return !!b; })()""")
    await asyncio.sleep(0.5)


async def tap_el(h, sel, hold_ms=70):
    """Skutečný dotyk (touchStart/End) na prvek — ne el.click(), protože v liště
    i v dialogu je pojistka proti zbloudilému kliknutí."""
    pt = await h.ev("""(() => {
      const sel = %s;
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top); y <= Math.ceil(r.bottom); y += 2)
        for (let x = Math.floor(r.left); x <= Math.ceil(r.right); x += 2) {
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
    await asyncio.sleep(0.5)
    return True


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
    await tap_el(h, ".jp-btn.primary")
    await asyncio.sleep(1.0)
    return True


async def select_with_hand(h, x, y):
    await pick_tool(h, "Upravit")
    await collapse_panel(h)
    await h.pen_tap(x, y)
    await asyncio.sleep(0.9)


async def trash_point(h):
    return await h.ev("""(() => {
      const b = document.querySelector(%s);
      if (!b) return null;
      const r = b.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + r.height / 2;
      const el = document.elementFromPoint(x, y);
      return {x, y, hitTrash: !!(el && el.closest && el.closest(%s))};
    })()""" % (json.dumps(TRASH), json.dumps(TRASH)))


async def stray_click(h, x, y):
    """Zbloudilé kompatibilitní klepnutí: prohlížeč ho vyřídí sám po pointerup,
    nese souřadnice téhož dotyku a žádné předchozí POLOŽENÍ uvnitř lišty."""
    return await h.ev("""(() => {
      const el = document.elementFromPoint(%f, %f);
      if (!el) return 'no-target';
      el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true,
        clientX: %f, clientY: %f, view: window}));
      return 'sent';
    })()""" % (x, y, x, y))


async def armed_click(h, x, y):
    """Totéž klepnutí, ale PO položení uvnitř lišty — to je skutečné ťuknutí na
    tlačítko, které projít MUSÍ (protidůkaz, že pojistka neblokuje ovládání)."""
    return await h.ev("""(() => {
      const bar = document.querySelector('.edit-bar');
      if (!bar) return 'no-bar';
      bar.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true,
        clientX: %f, clientY: %f, pointerId: 4242, pointerType: 'touch', isPrimary: true}));
      const el = document.elementFromPoint(%f, %f);
      if (!el) return 'no-target';
      el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true,
        clientX: %f, clientY: %f, view: window}));
      return 'sent';
    })()""" % (x, y, x, y, x, y))


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await collapse_panel(h)

        # --- 1) prvek + lišta úprav, změření místa 🗑 ---
        p1 = await free_xy(h)
        ok("1) první text se vložil", await insert_text(h, p1["x"], p1["y"], "prvni"),
           f"bod=({p1['x']:.0f},{p1['y']:.0f})")
        n1 = await item_count(h)
        await select_with_hand(h, p1["x"], p1["y"])
        st = await bar_state(h)
        tp = await trash_point(h)
        ok("2) výběr rukou vyvolal lištu úprav a 🗑 je měřitelné",
           st["bar"] and st["box"] and bool(tp), json.dumps(st, ensure_ascii=False))
        if not tp:
            return ok.report()
        print(f"   [🗑 na ({tp['x']:.0f},{tp['y']:.0f}), klepnutí by mířilo na 🗑: {tp['hitTrash']}]")

        # --- 2) ZBLOUDILÉ klepnutí na místo 🗑 → prvek musí zůstat ---
        sent = await stray_click(h, tp["x"], tp["y"])
        await asyncio.sleep(0.8)
        n2 = await item_count(h)
        st2 = await bar_state(h)
        ok("3) zbloudilé klepnutí na místo 🗑 PRVEK NESMAŽE",
           n2 == n1, f"před={n1} po={n2} (klepnutí={sent}, mířilo na 🗑={tp['hitTrash']})")
        ok("3b) prvek zůstal vybraný (rámeček i lišta)",
           st2["box"] and st2["bar"], json.dumps(st2, ensure_ascii=False))
        ok("3c) test něco dokazuje — klepnutí opravdu dopadlo na 🗑",
           tp["hitTrash"] is True, json.dumps(tp, ensure_ascii=False))

        # --- 3) PROTIDŮKAZ: stejné klepnutí po položení v liště SMAZAT musí ---
        p2 = await free_xy(h)
        await insert_text(h, p2["x"], p2["y"], "druhy")
        n3 = await item_count(h)
        await select_with_hand(h, p2["x"], p2["y"])
        tp2 = await trash_point(h)
        await armed_click(h, tp2["x"], tp2["y"])
        await asyncio.sleep(0.8)
        n4 = await item_count(h)
        ok("4) ťuknutí na 🗑 (položení uvnitř lišty) prvek SMAŽE — pojistka neblokuje ovládání",
           n4 == n3 - 1, f"{n3} -> {n4}")

        # --- 4) end-to-end: skutečný dotyk na 🗑 ---
        p3 = await free_xy(h)
        await insert_text(h, p3["x"], p3["y"], "treti")
        n5 = await item_count(h)
        await select_with_hand(h, p3["x"], p3["y"])
        ok("5a) 🗑 je po výběru k dispozici", (await trash_point(h)) is not None, "")
        await tap_el(h, TRASH)
        await asyncio.sleep(0.9)
        n6 = await item_count(h)
        ok("5) skutečný dotyk na 🗑 prvek smaže (end-to-end)", n6 == n5 - 1, f"{n5} -> {n6}")

        # --- 5) ✏️ skutečným dotykem otevře dialog ---
        p4 = await free_xy(h)
        await insert_text(h, p4["x"], p4["y"], "ctvrty")
        await select_with_hand(h, p4["x"], p4["y"])
        await tap_el(h, ".edit-bar .eb-btn[title='Přepsat text']")
        await asyncio.sleep(0.8)
        ok("6) skutečný dotyk na ✏️ otevře dialog (lišta není mrtvá)",
           await h.ev("!!document.querySelector('.text-input-overlay')"),
           "dialog se neotevřel (podle očekávání se otevřít měl)")

        await pick_tool(h, "Text")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
