#!/usr/bin/env python3
"""Značky: volitelně ZOBRAZIT v notách jako text (Jan, 20. 11. 2026).

Výchozí stav = neviditelný index (v notách se nekreslí). Tlačítko v panelu
„V notách: jen index / zobrazené“ stav přepne, uloží se k anotacím skladby
(`mkVisible`) a po reloadu drží.

Kontroly:
  1. výchozí: pageItems značky neobsahuje a v .annot-layer nejsou,
  2. po přepnutí: pageItems je obsahuje a v .annot-layer je vidět text,
  3. v IndexedDB je mkVisible = true,
  4. po reloadu zůstává zapnuto a značky jsou vidět,
  5. přepnutí zpět je zase schová (a do DB jde false).
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
    id, page, x: 200, y, text, mk: true, tool: 'text', hidden: true,
    size: 12, color: '#0b6bff', opacity: 1, border: false,
  });
  const items = [mk('mk-a', 0, 'A', 260), mk('mk-b', 0, 'B', 420)];
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const tx = q.result.transaction('annotations', 'readwrite');
    tx.objectStore('annotations').put({ songId, items, ref: null, mkOrder: null });
    tx.oncomplete = () => resolve(true);
    tx.onerror = () => resolve(false);
  };
  q.onerror = () => resolve(false);
}))(%s)
"""

DB_VIS = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('annotations', 'readonly').objectStore('annotations').getAll();
    r.onsuccess = () => resolve(r.result.length ? !!r.result[0].mkVisible : null);
    r.onerror = () => resolve(null);
  };
  q.onerror = () => resolve(null);
})
"""

STATE = r"""
(() => ({
  pageMarks: window.__barDev.pageItems.value.filter(i => i && i.mk).length,
  drawn: [...document.querySelectorAll('.annot-layer text, .annot-layer .annot-text')]
    .map(e => (e.textContent || '').trim()).filter(Boolean),
  btn: (() => { const b = [...document.querySelectorAll('.marks-panel .jp-btn')]
    .find(x => (x.textContent || '').includes('V notách')); return b ? b.textContent.trim() : null; })(),
  on: window.__barDev.mkVisible.value,
}))()
"""


async def tap_visible(h):
    c = json.loads(await h.ev(
        "(() => { const b = [...document.querySelectorAll('.marks-panel .jp-btn')]"
        ".find(x => (x.textContent || '').includes('V notách')); if (!b) return 'null';"
        " const r = b.getBoundingClientRect();"
        " return JSON.stringify({x: r.left + r.width/2, y: r.top + r.height/2}); })()"))
    await h.finger_tap(c["x"], c["y"])
    await asyncio.sleep(0.7)


CLOSE_PANEL = ("(() => { const b = document.querySelector('.marks-panel .jp-close');"
               " if (b) b.click(); return 1; })()")


async def main():
    c = Check()
    async with Harness(APP) as h:
        await h.set_tablet()
        await h.open()
        await h.open_song(pdf=make_pdf(8), pages=8)
        song = await h.ev(GET_SONG, await_promise=True)
        assert song, "nenačetl se song"
        assert await h.ev(SEED % json.dumps(song), await_promise=True), "seed selhal"
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer")
        await asyncio.sleep(1.2)

        # 1) zavřené okno + vypnutý přepínač = neviditelný index
        s0 = await h.ev(STATE)
        c("se zavřeným oknem jsou značky neviditelný index",
          s0["pageMarks"] == 0 and not s0["drawn"], str(s0))

        # 2) otevřené okno Značek = všechny značky stránky VIDĚT (i s vypnutým přepínačem)
        await h.ev("document.querySelector('.tb-mark').click()")
        await h.wait_for("!!document.querySelector('.marks-panel')", 10, "panel")
        await asyncio.sleep(0.4)
        s1 = await h.ev(STATE)
        c("s otevřeným oknem jsou značky vidět v notách", s1["pageMarks"] == 2, str(s1))
        c("a je vidět jejich text", sorted(set(s1["drawn"])) == ["A", "B"], str(s1["drawn"]))
        c("přepínač je pořád na „jen index“", "jen index" in (s1["btn"] or ""), str(s1["btn"]))

        # 3) přepínač „zobrazené" = vidět i po zavření okna, stav v DB
        await tap_visible(h)
        s2 = await h.ev(STATE)
        c("přepínač hlásí „zobrazené“", "zobrazené" in (s2["btn"] or ""), str(s2["btn"]))
        c("stav se uložil (mkVisible = true)", (await h.ev(DB_VIS, await_promise=True)) is True, "DB")
        await h.ev(CLOSE_PANEL)
        await asyncio.sleep(0.6)
        s3 = await h.ev(STATE)
        c("po zavření okna zůstávají vidět (přepínač zapnutý)",
          s3["pageMarks"] == 2 and sorted(set(s3["drawn"])) == ["A", "B"], str(s3))

        # 4) reload → drží
        await h.open()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "expand 2")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "viewer 2")
        await asyncio.sleep(1.2)
        s4 = await h.ev(STATE)
        c("po reloadu zůstávají vidět",
          s4["pageMarks"] == 2 and sorted(set(s4["drawn"])) == ["A", "B"], str(s4))

        # 5) zpět na index → po zavření okna zase neviditelné
        await h.ev("document.querySelector('.tb-mark').click()")
        await h.wait_for("!!document.querySelector('.marks-panel')", 10, "panel 2")
        await asyncio.sleep(0.4)
        await tap_visible(h)
        c("do DB jde false", (await h.ev(DB_VIS, await_promise=True)) is False, "DB 2")
        await h.ev(CLOSE_PANEL)
        await asyncio.sleep(0.6)
        s5 = await h.ev(STATE)
        c("se zavřeným oknem a vypnutým přepínačem zase neviditelné",
          s5["pageMarks"] == 0 and not s5["drawn"], str(s5))

        raise SystemExit(c.report())


if __name__ == "__main__":
    asyncio.run(main())
