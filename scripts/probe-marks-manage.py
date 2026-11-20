#!/usr/bin/env python3
"""Panel Značky = stejné ovládání i vzhled jako panel Záložky (Jan, Nov 2026).

Ověřuje v reálném prohlížeči (skutečné dotyky přes CDP):
  1. seznam značek je jeden .jp-list s řádky .jp-item (táhlo + 2 ikony),
     výchozí pořadí čísla číselně, pak písmena abecedně,
  2. vzhled řádku je shodný s řádkem v seznamu záložek (pozadí, rám, radius,
     padding, výška) — měřeno computed stylem, ne odhadem,
  3. přejmenování na řádku (tužka → input → Enter) zapíše nový text do anotací,
  4. tažení za táhlo přerovná seznam, zapíše mkOrder do IndexedDB a po puštění
     nezůstane duch / slot / označený řádek,
  5. koš značku smaže (a uklidí její id z mkOrder),
  6. po reloadu drží ruční pořadí (mkOrder z DB).
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "..", "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
Harness, Check, make_pdf = m.Harness, m.Check, m.make_pdf

APP = os.environ.get("APP_URL", "http://localhost:5173/")

GET_SONG = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('songs', 'readonly').objectStore('songs').getAll();
    r.onsuccess = () => resolve(r.result.length ? r.result[0].id : null);
    r.onerror = () => resolve(null);
  };
  q.onerror = () => resolve(null);
})
"""

SEED = r"""
((songId) => new Promise((resolve) => {
  const mk = (id, page, text, y) => ({
    id, page, x: 120, y, text, mk: true, tool: 'text', hidden: true,
    size: 12, color: '#0b6bff', opacity: 1, border: false,
  });
  const items = [mk('mk-a', 0, 'A', 300), mk('mk-5', 1, '5', 200),
                 mk('mk-12', 2, '12', 240), mk('mk-b', 3, 'B', 320)];
  const bms = [{ id: 'bm-1', page: 0, label: 'Intro' }, { id: 'bm-2', page: 4, label: 'Coda' }];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction(['annotations', 'bookmarks'], 'readwrite');
    tx.objectStore('annotations').put({ songId, items, ref: null, mkOrder: null });
    tx.objectStore('bookmarks').put({ songId, items: bms, manualOrder: true });
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => resolve(false);
  };
  q.onerror = () => resolve(false);
}))(%s)
"""

DB_MARKS = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('annotations', 'readonly').objectStore('annotations').getAll();
    r.onsuccess = () => {
      const rec = r.result.length ? r.result[0] : null;
      if (!rec) return resolve(null);
      return resolve({
        texts: (rec.items || []).filter(i => i && i.mk).map(i => i.text),
        order: Array.isArray(rec.mkOrder) ? rec.mkOrder : null,
      });
    };
    r.onerror = () => resolve(null);
  };
  q.onerror = () => resolve(null);
})
"""

STATE = r"""
(() => {
  const rows = [...document.querySelectorAll('.marks-panel .jp-list .jp-item')];
  return {
    rows: rows.length,
    texts: rows.map(el => (el.querySelector('.marks-text') || {}).textContent?.trim() || null),
    each: rows.map(el => ({
      drag: !!el.querySelector('.jp-drag'),
      icons: el.querySelectorAll('.jp-icon').length,
    })),
    ghosts: document.querySelectorAll('.jp-ghost').length,
    gaps: document.querySelectorAll('.jp-gap').length,
    dragging: document.querySelectorAll('.jp-item.dragging').length,
    editing: !!document.querySelector('.marks-panel .jp-input-edit'),
  };
})()
"""

ROWBOX = r"""
((sel) => {
  const row = document.querySelector(sel + ' .jp-item');
  if (!row) return null;
  const cs = getComputedStyle(row);
  const r = row.getBoundingClientRect();
  return {
    bg: cs.backgroundColor, border: cs.borderTopColor, bw: cs.borderTopWidth,
    radius: cs.borderTopLeftRadius, pad: cs.paddingTop + ' ' + cs.paddingLeft,
    gap: cs.columnGap, h: Math.round(r.height),
  };
})(%s)
"""

OPEN_MARKS = "(() => { document.querySelector('.tb-mark').click(); return 1; })()"
OPEN_BOOKMARKS = ("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                  ".find(x => (x.title || '').startsWith('Přidat záložku')); b && b.click(); return !!b; })()")
CLOSE_PANELS = ("(() => { document.querySelectorAll('.jump-panel .jp-close').forEach(b => b.click()); return 1; })()")


async def row_center(h, idx, sel=".marks-panel .jp-list .jp-item"):
    return json.loads(await h.ev(
        "(() => { const el = document.querySelectorAll(%s)[%d]; if (!el) return 'null';"
        " const r = el.getBoundingClientRect();"
        " return JSON.stringify({x: r.left + r.width/2, y: r.top + r.height/2, top: r.top, h: r.height, bottom: r.bottom}); })()"
        % (json.dumps(sel), idx)))


async def handle_center(h, idx):
    """Střed táhla (.jp-drag) daného řádku — tažení musí začít na táhle."""
    return json.loads(await h.ev(
        "(() => { const el = document.querySelectorAll('.marks-panel .jp-list .jp-item')[%d];"
        " if (!el) return 'null'; const d = el.querySelector('.jp-drag'); if (!d) return 'null';"
        " const r = d.getBoundingClientRect();"
        " return JSON.stringify({x: r.left + r.width/2, y: r.top + r.height/2}); })()" % idx))


async def tap_icon(h, row_idx, icon_idx):
    """Klepni na ikonu (tužka/koš) v řádku — skutečný dotyk, ne el.click()."""
    c = json.loads(await h.ev(
        "(() => { const el = document.querySelectorAll('.marks-panel .jp-list .jp-item')[%d];"
        " if (!el) return 'null';"
        " const ic = el.querySelectorAll('.jp-icon')[%d]; if (!ic) return 'null';"
        " const r = ic.getBoundingClientRect();"
        " return JSON.stringify({x: r.left + r.width/2, y: r.top + r.height/2}); })()" % (row_idx, icon_idx)))
    await h.finger_tap(c["x"], c["y"])
    await asyncio.sleep(0.4)


async def drag(h, x, y0, y1, steps=14):
    await h.touch("touchStart", [(x, y0, 12)])
    await asyncio.sleep(0.05)
    for i in range(1, steps + 1):
        await h.touch("touchMove", [(x, y0 + (y1 - y0) * i / steps, 12)])
        await asyncio.sleep(0.03)
    await asyncio.sleep(0.05)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.6)


class P:
    def __init__(self):
        self.inner = Check()
        self.n = 0

    def __call__(self, ok, detail=""):
        self.n += 1
        self.inner(f"check {self.n}: {detail[:70]}", ok, detail="")

    def report(self):
        return self.inner.report()


async def main():
    c = P()
    async with Harness(APP) as h:
        await h.set_tablet()
        await h.open()
        await h.open_song(pdf=make_pdf(8), pages=8)
        song = await h.ev(GET_SONG, await_promise=True)
        assert song, "nenačetl se song"
        assert await h.ev(SEED % json.dumps(song), await_promise=True), "seed selhal"
        await h.open()                      # reload, ať se data načtou z DB
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer")
        await asyncio.sleep(1.2)

        # --- 1) vzhled řádku proti záložkám ---------------------------------
        c(await h.ev(OPEN_BOOKMARKS), "tlačítko záložek existuje")
        await h.wait_for("document.querySelectorAll('.jump-panel .jp-list .jp-item').length === 2", 10, "panel záložek")
        await asyncio.sleep(0.3)
        bm_style = await h.ev(ROWBOX % json.dumps(".jump-panel"))
        await h.ev(CLOSE_PANELS)
        await asyncio.sleep(0.3)

        await h.ev(OPEN_MARKS)
        await h.wait_for("document.querySelectorAll('.marks-panel .jp-list .jp-item').length === 4", 10, "panel značek")
        await asyncio.sleep(0.3)
        st = await h.ev(STATE)
        c(st["rows"] == 4, f"4 řádky seznamu (je {st['rows']})")
        c(st["texts"] == ["5", "12", "A", "B"], f"výchozí pořadí čísla→písmena: {st['texts']}")
        c(all(x["drag"] and x["icons"] == 2 for x in st["each"]),
          f"každý řádek má táhlo a 2 ikony: {st['each']}")
        c(st["ghosts"] == 0 and st["gaps"] == 0 and st["dragging"] == 0, f"čistý start: {st}")

        mk_style = await h.ev(ROWBOX % json.dumps(".marks-panel"))
        c(mk_style is not None and bm_style is not None, "obě řádky existují")
        if mk_style and bm_style:
            same = all(mk_style[k] == bm_style[k] for k in ("bg", "border", "bw", "radius", "pad", "gap"))
            c(same, f"stejný vzhled řádku jako záložky: značky={mk_style} záložky={bm_style}")
            c(abs(mk_style["h"] - bm_style["h"]) <= 1, f"stejná výška řádku ({mk_style['h']} vs {bm_style['h']})")

        # --- 2) přejmenování na řádku --------------------------------------
        # (řádek "A" se hledá podle textu, ne podle indexu — pořadí se po
        #  přejmenování hned přerovná podle výchozího řazení)
        ai = st["texts"].index("A")
        await tap_icon(h, ai, 0)          # tužka u "A"
        st = await h.ev(STATE)
        c(st["editing"], "tužka otevřela input přímo v řádku")
        await h.ev(
            "(() => { const i = document.querySelector('.marks-panel .jp-input-edit');"
            " i.value = 'C'; i.dispatchEvent(new Event('input', {bubbles: true}));"
            " i.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', bubbles: true})); return 1; })()")
        await asyncio.sleep(0.6)
        st = await h.ev(STATE)
        db = await h.ev(DB_MARKS, await_promise=True)
        c(set(st["texts"]) == {"5", "12", "B", "C"}, f"po přejmenování A→C: {st['texts']}")
        c(st["texts"] == ["5", "12", "B", "C"], f"přejmenovaná se zařadila podle abecedy: {st['texts']}")
        c("C" in (db or {}).get("texts", []) and "A" not in (db or {}).get("texts", []),
          f"nový text je v anotacích: {(db or {}).get('texts')}")
        c(not st["editing"], "input se po Enteru zavřel")

        # --- 3) přerovnání tažením (řádek "12" na konec) -------------------
        before = await h.ev(STATE)
        i12 = before["texts"].index("12")
        hd = await handle_center(h, i12)
        rlast = await row_center(h, len(before["texts"]) - 1)
        await drag(h, hd["x"], hd["y"], rlast["bottom"] - 4)
        st = await h.ev(STATE)
        db = await h.ev(DB_MARKS, await_promise=True)
        expect = [t for t in before["texts"] if t != "12"] + ["12"]
        c(st["texts"] == expect, f"po přesunu 12 na konec: {st['texts']} (čekáno {expect})")
        c(st["ghosts"] == 0 and st["gaps"] == 0 and st["dragging"] == 0,
          f"po puštění čisto: ghosts={st['ghosts']} gaps={st['gaps']} dragging={st['dragging']}")
        c((db or {}).get("order") == ["mk-5", "mk-b", "mk-a", "mk-12"],
          f"mkOrder v IndexedDB: {(db or {}).get('order')}")

        # --- 4) smazání košem (řádek "B") ----------------------------------
        bi = st["texts"].index("B")
        await tap_icon(h, bi, 1)
        await asyncio.sleep(0.5)
        st = await h.ev(STATE)
        db = await h.ev(DB_MARKS, await_promise=True)
        expect = [t for t in expect if t != "B"]
        c(st["texts"] == expect, f"po smazání B: {st['texts']} (čekáno {expect})")
        c("B" not in (db or {}).get("texts", []), f"B není v anotacích: {(db or {}).get('texts')}")
        c((db or {}).get("order") == ["mk-5", "mk-a", "mk-12"],
          f"mkOrder bez smazané značky: {(db or {}).get('order')}")

        # --- 5) po reloadu drží ruční pořadí ------------------------------
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand 2")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer 2")
        await asyncio.sleep(1.0)
        await h.ev(OPEN_MARKS)
        await h.wait_for("document.querySelectorAll('.marks-panel .jp-list .jp-item').length === 3", 10, "panel po reloadu")
        await asyncio.sleep(0.3)
        st = await h.ev(STATE)
        c(st["texts"] == ["5", "C", "12"], f"po reloadu stejné pořadí: {st['texts']}")

        raise SystemExit(c.report())


if __name__ == "__main__":
    asyncio.run(main())
