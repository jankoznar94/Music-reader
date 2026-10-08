#!/usr/bin/env python3
"""Velikost textu PŘED vložením + rovnou ruka po vložení (Jan, Oct 2026).

Jan: „V anotačním režimu je možné vkládat text... Uživatel ale nemá úplně možnost
vybrat velikost písma. Může ji upravit až po vložení pomocí nástroje ‚ruka‘.
Měla by být možnost tento text nastavit ještě před vložením. A po vložení by na
vložený text měl být rovnou aplikovaný nástroj ‚ruka‘, aby mohl hned manipulovat
s vloženým prvkem.“

Sonda ověřuje:
  1. dialog pro text má ovladač velikosti a ten mění hodnotu i náhled („Aa“)
  2. zvolená velikost se propíše do ULOŽENÉ anotace (ne jen do UI)
  3. volba se pamatuje i pro další text (localStorage, přežije reload)
  4. „Uložit“ → další text se vkládá ve zvolené velikosti
  5. „Uložit a ruka“ → nástroj = ruka a vložený prvek je ROVNOU vybraný
     (rámeček + pás úprav), takže s ním lze hned hýbat
  6. rukou otevřený dialog ukazuje velikost TOHO prvku, ne tu pro nový text
  7. zrušení dialogu velikost nezmění

    NOTY_CDP=http://127.0.0.1:9242 python3 scripts/probe-text-size-before-insert.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


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
    """Bod, kde elementFromPoint vrací daný prvek — NE střed z rectu. Dispatchnutý
    dotyk má souřadnice zaokrouhlené na celá čísla, takže tap na zlomkový střed
    může spadnout za hranici prvku (u dlaždic trefí souseda). Skenuje se okolí
    rectu a bere se první bod, kde prvek skutečně leží pod kurzorem."""
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
    """Skutečný dotyk na prvek. Dialog zahazuje kliknutí bez předchozího
    POLOŽENÍ uvnitř sebe (onDialogClickCapture), takže el.click() tu nefunguje."""
    pt = await point_of(h, sel)
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.5)
    return True


async def dialog_state(h):
    raw = await h.ev("""(() => {
      const on = !!document.querySelector('.text-input-overlay');
      const row = document.querySelector('.ti-size-row');
      const val = document.querySelector('.ti-size-val');
      const aa = document.querySelector('.ti-size-aa');
      const btn = [...document.querySelectorAll('.jp-btn')]
        .map(b => (b.textContent || '').trim());
      return JSON.stringify({
        open: on,
        sizeRow: !!row,
        sizeVal: val ? val.textContent.trim() : null,
        aaPx: aa ? getComputedStyle(aa).fontSize : null,
        aaFits: aa ? (aa.parentElement.scrollHeight <= aa.parentElement.clientHeight + 1) : null,
        buttons: btn,
        hand: !!document.querySelector('.jp-btn.hand'),
        ls: (() => { try { return localStorage.getItem('noty.textSize'); } catch (e) { return 'ERR'; } })(),
      });
    })()""")
    return json.loads(raw) if raw else {}


async def items(h):
    """Přečti ULOŽENÉ anotace z IndexedDB (ne z DOM) — ověřuje trvalý stav."""
    raw = await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const name = (dbs.map(d => d.name) || []).find(n => /noty|music|reader/i.test(n));
      if (!name) return '{"db":null}';
      const db = await new Promise((res, rej) => {
        const r = indexedDB.open(name);
        r.onsuccess = () => res(r.result); r.onerror = () => rej(String(r.error));
      });
      const all = (storeName) => new Promise((res) => {
        if (!db.objectStoreNames.contains(storeName)) return res(null);
        const r = db.transaction(storeName, 'readonly').objectStore(storeName).getAll();
        r.onsuccess = () => res(r.result); r.onerror = () => res(null);
      });
      const stores = [...db.objectStoreNames];
      const out = { db: name, stores };
      for (const s of stores) {
        const rows = await all(s);
        if (Array.isArray(rows) && rows.some(r => r && Array.isArray(r.items))) {
          out[s] = rows.map(r => ({ songId: r.songId, items: (r.items || []).map(i => ({
            tool: i.tool, text: i.text, size: i.size })) }));
        }
      }
      db.close();
      return JSON.stringify(out);
    })()""", await_promise=True)
    return json.loads(raw) if raw else {}


async def saved_texts(h):
    data = await items(h)
    out = []
    for key, rows in data.items():
        if key in ("db", "stores") or not isinstance(rows, list):
            continue
        for r in rows:
            for i in (r.get("items") or []):
                if isinstance(i, dict) and i.get("tool") == "text":
                    out.append(i)
    return out


async def texts_from_ui(h):
    """Texty + velikosti z anotační vrstvy (DOM)."""
    raw = await h.ev("""(() => {
      const out = [];
      document.querySelectorAll('.annot-layer > g > text').forEach(t => {
        const t2 = t.textContent || '';
        if (!t2.trim()) return;
        if (/^[\\uE000-\\uF8FF]$/.test(t2.trim())) return;   // SMuFL glyf (dynamika)
        out.push({ text: t2, size: Number(t.getAttribute('font-size')) });
      });
      return JSON.stringify(out);
    })()""")
    return json.loads(raw) if raw else []


async def open_text_dialog(h, x, y, label=""):
    """Klepni perem na noty s nástrojem Text → otevře se dialog s prázdným polem."""
    await h.pen_tap(x, y)
    await asyncio.sleep(0.8)
    got = await h.ev("!!document.querySelector('.text-input-overlay')")
    ls = await h.ev("(() => { try { return localStorage.getItem('noty.textSize'); }"
                    " catch (e) { return 'ERR'; } })()")
    print(f"   [otevření dialogu {label}] bod=({x:.0f},{y:.0f}) dialog={got} ls={ls}")
    return got


async def free_xy(h):
    """Bod, kde je pod kurzorem PŘÍMO anotační vrstva (ne hotová anotace ani
    panel) a který je zároveň dál od existujících anotací. Harness `free_point`
    na hotové anotaci spadne — `classList` u SVG prvku `contains` nemá — takže
    se skenuje vlastní mřížka."""
    p = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer');
      if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y) => boxes.some(r => r.width > 0 &&
        x > r.left - 14 && x < r.right + 14 && y > r.top - 14 && y < r.bottom + 14);
      const xs = [0.62, 0.54, 0.46, 0.38, 0.70, 0.30];
      const ys = [0.30, 0.38, 0.46, 0.54];
      for (const fy of ys) for (const fx of xs) {
        const x = v.left + v.width * fx, y = v.top + v.height * fy;
        if (document.elementFromPoint(x, y) === svg && !near(x, y)) return {x, y};
      }
      return null;
    })()""")
    return (p["x"], p["y"]) if p else None


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()
        await h.annot_toggle()
        await asyncio.sleep(0.4)

        # nástroj Text
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Text')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)

        # 1) dialog má ovladač velikosti
        xy = await free_xy(h)
        opened = await open_text_dialog(h, *xy)
        st = await dialog_state(h)
        ok("1) text: dialog se otevřel a má ovladač velikosti", opened and st.get("sizeRow"),
           json.dumps(st, ensure_ascii=False))
        base = st.get("sizeVal")
        aa0 = st.get("aaPx")
        ok("1b) náhled „Aa“ ukazuje skutečnou velikost (px = hodnota)",
           aa0 == (base + "px"), f"val={base} aa={aa0}")

        # 2) +/− mění hodnotu i náhled (tlačítka jsou dvě: − a +)
        await tap_el(h, ".ti-size-btn:last-of-type")
        st2 = await dialog_state(h)
        ok("2) tlačítko + zvětší hodnotu i náhled",
           st2.get("sizeVal") != base and st2.get("aaPx") == (st2.get("sizeVal") + "px"),
           f"{base} -> {st2.get('sizeVal')} / aa={st2.get('aaPx')}")
        bigger = st2.get("sizeVal")
        await tap_el(h, ".ti-size-btn")          # −
        st2b = await dialog_state(h)
        ok("2b) tlačítko − zvětšenou hodnotu vrátí zpět",
           st2b.get("sizeVal") == base, f"− dalo {st2b.get('sizeVal')}, čekáno {base}")
        await tap_el(h, ".ti-size-btn:last-of-type")   # zpět na větší
        await asyncio.sleep(0.3)

        # 3) Uložit → velikost se propíše do ULOŽENÉ anotace (IndexedDB)
        await h.set_value(".ti-input", "velky text")
        await tap_el(h, ".jp-btn.primary")
        await asyncio.sleep(1.2)
        st3 = await dialog_state(h)
        ok("3) dialog se po Uložit zavřel", not st3.get("open"), json.dumps(st3, ensure_ascii=False))
        mine = [t for t in await saved_texts(h) if t.get("text") == "velky text"]
        ok("3b) ULOŽENÝ text má zvolenou velikost",
           bool(mine) and str(mine[0].get("size")) == bigger,
           f"uloženo={mine} chtěno={bigger}")

        # 4) volba se pamatuje pro DALŠÍ text (nový dialog začíná na ní)
        xy2 = await free_xy(h)
        await open_text_dialog(h, *xy2)
        st4 = await dialog_state(h)
        ok("4) další text začíná na zvolené velikosti", st4.get("sizeVal") == bigger,
           f"{st4.get('sizeVal')} vs {bigger}")

        # 5) Uložit a ruka → nástroj ruka + prvek hned vybraný
        await h.set_value(".ti-input", "rukou hned")
        await tap_el(h, ".jp-btn.hand")
        await asyncio.sleep(0.9)
        hand = await h.ev("""(() => JSON.stringify({
          dialog: !!document.querySelector('.text-input-overlay'),
          toolOn: (() => { const b = [...document.querySelectorAll('.ap-tool')]
            .find(x => (x.title || '').startsWith('Upravit')); return b ? b.classList.contains('on') : null; })(),
          box: !!document.querySelector('.annot-selected'),
          editBar: !!document.querySelector('.edit-bar'),
          editLabel: (document.querySelector('.eb-type') || {}).textContent || null,
          editSize: (document.querySelector('.eb-val') || {}).textContent || null,
        }))()""")
        hand = json.loads(hand)
        ok("5a) po „Uložit a ruka“ se dialog zavřel", not hand["dialog"], json.dumps(hand, ensure_ascii=False))
        ok("5b) nástroj je ruka (Upravit)", hand["toolOn"] is True, json.dumps(hand, ensure_ascii=False))
        ok("5c) vložený prvek je ROVNOU vybraný (rámeček + pás úprav)",
           hand["box"] and hand["editBar"], json.dumps(hand, ensure_ascii=False))
        ok("5d) pás úprav hlásí velikost vloženého textu",
           hand["editSize"] == bigger, f"{hand['editSize']} vs {bigger}")

        # 6) rukou otevřený dialog (✏️) ukazuje velikost TOHO prvku
        #    → prvek nejdřív zmenšíme přes pás úprav, pak otevřeme dialog pro přepis
        await tap_el(h, ".eb-btn[title='Zmenšit']")
        await asyncio.sleep(0.5)
        smaller = await h.ev("(document.querySelector('.eb-val') || {}).textContent")
        await tap_el(h, ".eb-btn[title='Přepsat text']")
        await asyncio.sleep(0.6)
        st6 = await dialog_state(h)
        ok("6) dialog otevřený rukou ukazuje velikost TOHO prvku",
           st6.get("open") and st6.get("sizeVal") == str(smaller).strip(),
           f"dialog={st6.get('sizeVal')} prvek={smaller}")
        ok("6b) dialog otevřený rukou NEnabízí přepnutí na ruku (už v ní jsme)",
           not st6.get("hand"), json.dumps(st6, ensure_ascii=False))
        # zrušit — a ověřit, že se dialog SKUTEČNĚ zavřel (jinak by další krok
        # měřil jiný dialog a sonda by lhala: naměřeno 20 místo 22)
        ok("6c) Zrušit v dialogu otevřeném rukou dialog zavře",
           (await tap_el(h, ".jp-btn:not(.primary):not(.hand)")) and
           not (await dialog_state(h)).get("open"),
           json.dumps(await dialog_state(h), ensure_ascii=False))
        await asyncio.sleep(0.4)

        # 7) zrušení dialogu NEMĚNÍ připravenou velikost pro nový text
        #    POZOR: po „Uložit a ruka“ je aktivní RUKA — zpátky na Text, jinak
        #    pero jen vybírá prvek a dialog se vůbec neotevře (sonda by lhala).
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.title || '').startsWith('Text')); if (b) b.click(); })()")
        await asyncio.sleep(0.4)
        xy3 = await free_xy(h)
        await open_text_dialog(h, *xy3)
        await tap_el(h, ".ti-size-btn:last-of-type")     # zvětšit jen v dialogu
        await tap_el(h, ".jp-btn:not(.primary):not(.hand)")   # Zrušit
        await asyncio.sleep(0.6)
        xy4 = await free_xy(h)
        await open_text_dialog(h, *xy4)
        st7 = await dialog_state(h)
        ok("7) Zrušit neuloží velikost ani text",
           st7.get("open") and st7.get("sizeVal") == bigger,
           f"po zrušení dialog ukazuje {st7.get('sizeVal')}, očekáváno {bigger}")
        texts = [t.get("text") for t in await saved_texts(h)]
        ok("7b) zrušený text se neuložil", "" not in texts and None not in texts,
           f"uložené texty: {texts}")
        await tap_el(h, ".jp-btn:not(.primary):not(.hand)")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
