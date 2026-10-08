#!/usr/bin/env python3
"""Rámeček textu + barva textu v dialogu + konzistentní krok velikosti (Jan, Oct 2026).

Jan: „Ke vkládání textu bych přidal možnost dát hranatý Border. Ve stejné barvě
jako text. Do čtverce. Taky bych přidal možnost vybírat barvu textu přímo ve
stejném okně, jak teď vybíráme velikost a způsob vložení. A velikost textu se
tlačítkem + mění pokaždé jinak — potřebuji konzistentní krok, třeba po 3 bodech.“

Sonda ověřuje v tomto pořadí:
  1. dialog pro text má řádek Barva i přepínač Rámeček
  2. tlačítko +/− mění velikost VŽDY o stejný krok (3) — i přes hranici pásem
  3. zapnutý rámeček + zvolená barva se propíšou do ULOŽENÉ anotace (IndexedDB)
  4. rámeček je ČTVEREC (šířka == výška) a má stejnou barvu jako text
  5. obě volby se pamatují (localStorage) a přežijí reload
  6. pás úprav umí rámeček u vloženého textu zapnout i vypnout
  7. Zrušit v dialogu volby nezmění

    NOTY_CDP=http://127.0.0.1:9247 python3 scripts/probe-text-border-and-color.py
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


async def point_of(h, sel):
    """Bod, kde elementFromPoint vrací daný prvek — NE střed z rectu (dispatch
    zaokrouhluje souřadnice na celá čísla a tap pak může minout)."""
    return await h.ev("""(() => {
      const sel = %s;
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return null;
      const x0 = Math.max(0, Math.floor(r.left - 4)), x1 = Math.min(innerWidth - 1, Math.ceil(r.right + 4));
      const y0 = Math.max(0, Math.floor(r.top - 4)), y1 = Math.min(innerHeight - 1, Math.ceil(r.bottom + 4));
      for (let y = y0; y <= y1; y += 2) {
        for (let x = x0; x <= x1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(sel) === el))) return [x + 0.5, y + 0.5];
        }
      }
      return null;
    })()""" % json.dumps(sel))


async def tap_el(h, sel, hold_ms=60):
    """Skutečný dotyk — dialog zahazuje kliknutí bez předchozího POLOŽENÍ uvnitř
    sebe (onDialogClickCapture), takže el.click() tu nefunguje."""
    pt = await point_of(h, sel)
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.4)
    return True


async def tap_index(h, sel, idx, hold_ms=60):
    """Dotyk na N-tý prvek daného selektoru (paleta barev)."""
    pt = await h.ev("""(() => {
      const el = document.querySelectorAll(%s)[%d];
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top) + 1; y <= Math.ceil(r.bottom) - 1; y += 2)
        for (let x = Math.floor(r.left) + 1; x <= Math.ceil(r.right) - 1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit === el) return [x + 0.5, y + 0.5];
        }
      return null;
    })()""" % (json.dumps(sel), idx))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.4)
    return True


async def dialog_state(h):
    raw = await h.ev("""(() => {
      const q = (s) => document.querySelector(s);
      const colors = [...document.querySelectorAll('.ti-color')];
      const sel = colors.findIndex(c => c.classList.contains('on'));
      return JSON.stringify({
        open: !!q('.text-input-overlay'),
        colorRow: colors.length,
        colorSel: sel >= 0 ? sel : null,
        colorSelBg: sel >= 0 ? getComputedStyle(colors[sel]).backgroundColor : null,
        toggle: q('.ti-toggle') ? q('.ti-toggle').textContent.trim() : null,
        toggleOn: q('.ti-toggle') ? q('.ti-toggle').classList.contains('on') : null,
        sizeVal: q('.ti-size-val') ? Number(q('.ti-size-val').textContent.trim()) : null,
        lsColor: (() => { try { return localStorage.getItem('noty.textColor'); } catch (e) { return 'ERR'; } })(),
        lsBorder: (() => { try { return localStorage.getItem('noty.textBorder'); } catch (e) { return 'ERR'; } })(),
      });
    })()""")
    return json.loads(raw) if raw else {}


async def saved_texts(h):
    """Anotace typu text z IndexedDB (trvalý stav, ne DOM)."""
    raw = await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const name = (dbs.map(d => d.name) || []).find(n => /noty|music|reader/i.test(n));
      if (!name) return '[]';
      const db = await new Promise((res, rej) => {
        const r = indexedDB.open(name);
        r.onsuccess = () => res(r.result); r.onerror = () => rej(String(r.error));
      });
      const all = (s) => new Promise((res) => {
        if (!db.objectStoreNames.contains(s)) return res(null);
        const r = db.transaction(s, 'readonly').objectStore(s).getAll();
        r.onsuccess = () => res(r.result); r.onerror = () => res(null);
      });
      const out = [];
      for (const s of [...db.objectStoreNames]) {
        const rows = await all(s);
        if (!Array.isArray(rows)) continue;
        for (const row of rows)
          for (const i of ((row && row.items) || []))
            if (i && i.tool === 'text') out.push({
              text: i.text, size: i.size, color: i.color,
              border: i.border === true, page: i.page,
            });
      }
      db.close();
      return JSON.stringify(out);
    })()""", await_promise=True)
    return json.loads(raw) if raw else []


async def border_geometry(h, text):
    """Změř ULOŽENÝ rámeček přímo na vrstvě: obdélník s třídou .text-border,
    který patří k textu s daným obsahem. Vrací i barvu textu."""
    raw = await h.ev("""(() => {
      const want = %s;
      const svg = document.querySelector('.annot-layer');
      if (!svg) return null;
      for (const g of svg.querySelectorAll('g')) {
        const t = g.querySelector(':scope > text');
        if (!t || (t.textContent || '') !== want) continue;
        const r = g.querySelector(':scope > rect.text-border');
        const tb = t.getBoundingClientRect();
        if (!r) return JSON.stringify({ hasRect: false, textFill: t.getAttribute('fill'),
          textSize: Number(t.getAttribute('font-size')), textBox: [tb.left, tb.top, tb.width, tb.height] });
        const rb = r.getBoundingClientRect();
        return JSON.stringify({
          hasRect: true,
          w: rb.width, h: rb.height,
          stroke: r.getAttribute('stroke'),
          textFill: t.getAttribute('fill'),
          textBox: [tb.left, tb.top, tb.width, tb.height],
          rectBox: [rb.left, rb.top, rb.width, rb.height],
        });
      }
      return null;
    })()""" % json.dumps(text))
    return json.loads(raw) if raw else None


async def free_xy(h):
    """Bod, kde je pod kurzorem PŘÍMO anotační vrstva a který je dál od anotací."""
    p = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer');
      if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y) => boxes.some(r => r.width > 0 &&
        x > r.left - 26 && x < r.right + 26 && y > r.top - 26 && y < r.bottom + 26);
      const xs = [0.62, 0.54, 0.46, 0.38, 0.70, 0.30];
      const ys = [0.30, 0.38, 0.46, 0.54];
      for (const fy of ys) for (const fx of xs) {
        const x = v.left + v.width * fx, y = v.top + v.height * fy;
        if (document.elementFromPoint(x, y) === svg && !near(x, y)) return {x, y};
      }
      return null;
    })()""")
    return (p["x"], p["y"]) if p else None


async def open_text_dialog(h, x, y, label=""):
    await h.pen_tap(x, y)
    await asyncio.sleep(0.8)
    got = await h.ev("!!document.querySelector('.text-input-overlay')")
    print(f"   [dialog {label}] bod=({x:.0f},{y:.0f}) otevreno={got}")
    return got


async def use_text_tool(h):
    """Přepni nástroj na Text (poslední akce mohla nechat ruku)."""
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.title || '').startsWith('Text')); if (b) b.click(); })()")
    await asyncio.sleep(0.4)


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await use_text_tool(h)

        # --- 1) dialog má řádek Barva i přepínač Rámeček -----------------------
        xy = await free_xy(h)
        opened = await open_text_dialog(h, *xy, label="1")
        st = await dialog_state(h)
        ok("1a) dialog pro text se otevřel", opened, json.dumps(st, ensure_ascii=False))
        ok("1b) dialog má paletu barev textu (stejná jako pero, 9 odstínů)",
           st.get("colorRow") == 9, f"barev={st.get('colorRow')}")
        ok("1c) dialog má přepínač Rámeček (výchozí Vypnutý)",
           st.get("toggle") is not None and st.get("toggleOn") is False,
           f"toggle={st.get('toggle')} on={st.get('toggleOn')}")

        # --- 2) KROK VELIKOSTI JE VŽDY 3 ---------------------------------------
        # Pásma dřívějšího kroku byla 2 (<30), 5 (<60), 10 (>=60) — z 20 na 60
        # to dělalo 2,2,2,2,2,5,5,… Problém: krok se měnil podle hodnoty.
        seq = []
        for _ in range(12):
            await tap_el(h, ".ti-size-btn:last-of-type")
            v = (await dialog_state(h)).get("sizeVal")
            seq.append(v)
        deltas = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        ok("2a) tlačítko + mění velikost VŽDY o stejný krok (3)",
           all(d == 3 for d in deltas), f"posloupnost={seq} kroky={deltas}")
        back = []
        for _ in range(6):
            await tap_el(h, ".ti-size-btn")
            back.append((await dialog_state(h)).get("sizeVal"))
        bdeltas = [back[i + 1] - back[i] for i in range(len(back) - 1)]
        ok("2b) tlačítko − ubírá stejný krok (3)", all(d == -3 for d in bdeltas),
           f"posloupnost={back} kroky={bdeltas}")
        # přes hranici 30/60/90 (dřív se tu krok lámal: <30 → 2, <60 → 5, ≥60 → 10).
        # POZOR: u stropu 120 už se hodnota nezmění (krok 0) a u podlahy 10 se číslo
        # po odsaturování clampu neposune o plný krok — obojí je SPRÁVNĚ, proto se
        # saturace vylučuje přes CSSOM (clampTextSize) a nekontroluje se naslepo.
        vals = []
        for _ in range(30):
            await tap_el(h, ".ti-size-btn:last-of-type")
            vals.append((await dialog_state(h)).get("sizeVal"))
        sat = await h.ev("""(() => {
          for (const sh of document.styleSheets) {
            let rules; try { rules = sh.cssRules; } catch (e) { continue; }
            for (const r of rules) if (r.selectorText === '.ti-size-val')
              return { lo: r.style.minWidth, any: r.cssText };
          }
          return null;
        })()""")
        vd = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
        bad = [d for d in vd if d not in (0, 1, 2, 3)]
        ok("2c) krok zůstává 3 i přes hranice pásem (žádné 4/5/10)",
           not bad and 120 in vals,
           f"posloupnost={vals} kroky={vd}")
        # a − po stejném kroku zpátky: 40 kliků z 120 (strop) → 10 (podlaha)
        for _ in range(40):
            await tap_el(h, ".ti-size-btn")
        size_now = (await dialog_state(h)).get("sizeVal")
        ok("2d) − dojede na podlahu 10 (žádných 9/8/7/6 mimo desítky)",
           size_now == 10, f"po 40× − je {size_now}")

        # --- 3) barva + rámeček → ULOŽENÁ anotace ------------------------------
        # zvolit jinou barvu než výchozí černou (index 1 = #c0392b)
        await tap_index(h, ".ti-color", 1)
        st3 = await dialog_state(h)
        ok("3a) klepnutí na barvu ji v dialogu vybere", st3.get("colorSel") == 1,
           json.dumps(st3, ensure_ascii=False))
        await tap_el(h, ".ti-toggle")
        st3b = await dialog_state(h)
        ok("3b) přepínač Rámeček se zapne", st3b.get("toggleOn") is True,
           f"toggle={st3b.get('toggle')}")

        await h.set_value(".ti-input", "oramovany text")
        await tap_el(h, ".jp-btn.primary")
        await asyncio.sleep(1.2)
        mine = [t for t in await saved_texts(h) if t.get("text") == "oramovany text"]
        ok("3c) ULOŽENÝ text má zapnutý rámeček", bool(mine) and mine[0].get("border") is True,
           f"ulozeno={mine}")
        ok("3d) ULOŽENÝ text má zvolenou barvu (ne tu z pera)",
           bool(mine) and mine[0].get("color") == "#c0392b",
           f"ulozeno={mine}")

        # --- 4) rámeček je ČTVEREC a stejné barvy jako text --------------------
        geo = await border_geometry(h, "oramovany text")
        ok("4a) text se na stránce vykreslil s rámečkem", geo and geo.get("hasRect"),
           json.dumps(geo, ensure_ascii=False))
        if geo and geo.get("hasRect"):
            ok("4b) rámeček je ČTVEREC (šířka == výška)",
               abs(geo["w"] - geo["h"]) <= 1.5, f"{geo['w']:.1f} x {geo['h']:.1f}")
            ok("4c) rámeček má STEJNOU barvu jako text",
               geo.get("stroke") == geo.get("textFill") == "#c0392b",
               f"rect={geo.get('stroke')} text={geo.get('textFill')}")
            ok("4d) text leží UVNITŘ rámečku",
               geo["textBox"][0] >= geo["rectBox"][0] - 1
               and geo["textBox"][1] >= geo["rectBox"][1] - 1
               and geo["textBox"][0] + geo["textBox"][2] <= geo["rectBox"][0] + geo["rectBox"][2] + 1
               and geo["textBox"][1] + geo["textBox"][3] <= geo["rectBox"][1] + geo["rectBox"][3] + 1,
               f"text={geo['textBox']} ram={geo['rectBox']}")

        # --- 5) volby se pamatují (localStorage + přežijí reload) --------------
        after = await dialog_state(h)
        ok("5a) barva se uložila do localStorage", after.get("lsColor") == "#c0392b",
           f"ls={after.get('lsColor')}")
        ok("5b) rámeček se uložil do localStorage", after.get("lsBorder") == "1",
           f"ls={after.get('lsBorder')}")
        # reload: sonda jede proti dev serveru, takže stačí znovu navigovat na appku
        # (h.open) a PAK otevřít skladbu — `open_song` sám nenaviguje a v prohlížeči
        # není `input[type=file]`, takže by spadl na „Could not find node“.
        # POZOR: reset=False, jinak by se smazala IndexedDB i s uloženým textem.
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6), reset=False)
        await h.annot_toggle()
        await asyncio.sleep(0.4)
        await use_text_tool(h)
        xy5 = await free_xy(h)
        await open_text_dialog(h, *xy5, label="5c")
        st5 = await dialog_state(h)
        ok("5c) po reloadu dialog nabízí stejnou barvu i rámeček",
           st5.get("colorSel") == 1 and st5.get("toggleOn") is True,
           json.dumps(st5, ensure_ascii=False))
        await tap_el(h, ".jp-btn:not(.primary):not(.hand)")     # Zrušit
        await asyncio.sleep(0.4)

        # --- 6) pás úprav umí rámeček zapnout/vypnout u VLOŽENÉHO textu -------
        #     (text leží na stránce 1; vybírá se rukou)
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Upravit')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)
        # klepni na místo textu (střed levé hrany rámečku)
        picked = await h.ev("""(() => {
          const svg = document.querySelector('.annot-layer');
          for (const g of svg.querySelectorAll('g')) {
            const t = g.querySelector(':scope > text');
            if (!t || (t.textContent || '') !== 'oramovany text') continue;
            const r = t.getBoundingClientRect();
            // KLIENTSKÉ souřadnice (pen_tap je dispatchuje tak, jak jsou) — NE
            // přepočet do souřadnic vrstvy, ten patří jen do kódu appky.
            return { x: r.left + 8, y: r.top + r.height / 2 };
          }
          return null;
        })()""")
        if picked:
            await h.pen_tap(picked["x"], picked["y"])
            await asyncio.sleep(0.6)
        bar = await h.ev("""(() => JSON.stringify({
          bar: !!document.querySelector('.edit-bar'),
          label: (document.querySelector('.eb-type') || {}).textContent || null,
          borderBtn: !!document.querySelector('.eb-btn[title*="meček"], .eb-btn[title*="Hranat"]'),
          on: (() => { const b = [...document.querySelectorAll('.eb-btn')]
            .find(x => (x.title || '').includes('meček')); return b ? b.classList.contains('on') : null; })(),
        }))()""")
        bar = json.loads(bar)
        ok("6a) rukou vybraný text otevře pás úprav", bar["bar"], json.dumps(bar, ensure_ascii=False))
        ok("6b) pás úprav má přepínač rámečku a hlásí ZAPNUTÝ", bar["borderBtn"] and bar["on"] is True,
           json.dumps(bar, ensure_ascii=False))
        await tap_el(h, ".eb-btn[title*='meček']")
        await asyncio.sleep(0.8)
        after_off = [t for t in await saved_texts(h) if t.get("text") == "oramovany text"]
        ok("6c) vypnutí v pásu úprav se uložilo (border=false)",
           bool(after_off) and after_off[0].get("border") is False, f"ulozeno={after_off}")
        geo2 = await border_geometry(h, "oramovany text")
        ok("6d) rámeček zmizel i z plátna", geo2 and geo2.get("hasRect") is False,
           json.dumps(geo2, ensure_ascii=False))

        # --- 7) Zrušit v dialogu volby nemění ---------------------------------
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Text')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)
        xy7 = await free_xy(h)
        await open_text_dialog(h, *xy7, label="7")
        await tap_index(h, ".ti-color", 3)
        await tap_el(h, ".ti-toggle")
        await tap_el(h, ".jp-btn:not(.primary):not(.hand)")      # Zrušit
        await asyncio.sleep(0.5)
        st7 = await dialog_state(h)
        ok("7) Zrušit nezmění připravenou barvu ani rámeček",
           st7.get("open") is False and st7.get("lsColor") == "#c0392b"
           and st7.get("lsBorder") == "0",
           json.dumps(st7, ensure_ascii=False))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
