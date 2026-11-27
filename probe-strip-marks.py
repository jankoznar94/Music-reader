#!/usr/bin/env python3
"""Přepínač dole: lišta umí ZÁLOŽKY i ZNAČKY (Jan, 27. 11. 2026).

Ověřuje, že značky nejsou jen v panelu:
  * lišta má vlevo přepínač (dvě kolečka: záložky / značky),
  * v režimu záložek se v liště kreslí záložky, v režimu značek značky —
    STEJNĚ (odznak s číslem stránky + text),
  * klepnutí na značku v liště skočí na její stránku a zvýrazní ji,
  * volba se pamatuje (localStorage) a drží i po reloadu,
  * ťuknutí prstem na přepínač přepne lištu a NEotočí stránku ani neschová lištu,
  * přepínač nepřekrývá seznam.
"""
import asyncio
import base64
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness, Check, make_pdf = m.Harness, m.Check, m.make_pdf

APP = os.environ.get("APP_URL", "http://localhost:5173/")
SHOT = "/tmp/strip-marks.png"

GET_SONG = r"""
new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('songs', 'readonly').objectStore('songs').getAll();
    r.onsuccess = () => resolve(r.result.length ? r.result[0].id : null);
  };
})
"""

SEED = r"""
((songId) => new Promise((resolve) => {
  const bms = [];
  for (let i = 0; i < 5; i++) bms.push({ id: 'bm-' + i, page: i, label: 'Skladba ' + (i + 1) });
  const letters = ['A', 'B', 'C', 'D', 'E'];
  const items = letters.map((t, i) => ({
    id: 'mk-' + i, page: i, x: 120 + i * 10, y: 300 + i * 5,
    tool: 'text', text: t, mk: true, hidden: true, size: 18, border: false,
    color: '#0b6bff',
  }));
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const db = q.result;
    const tx = db.transaction(['bookmarks', 'annotations'], 'readwrite');
    tx.objectStore('bookmarks').put({ songId, items: bms, manualOrder: false });
    tx.objectStore('annotations').put({ songId, items, mkOrder: null, mkVisible: false, mkSize: 18 });
    tx.oncomplete = () => resolve(true);
  };
}))(__SONG__)
"""

GEO = r"""
(() => {
  const wrap = document.querySelector('.bottom-strip');
  const strip = document.querySelector('.bookmark-strip');
  const sw = document.querySelector('.strip-switch');
  const on = strip ? strip.querySelector('.bookmark-btn.on') : null;
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect();
    return {l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top), b: Math.round(b.bottom),
            w: Math.round(b.width), h: Math.round(b.height)}; };
  return {
    wrap: r(wrap), strip: r(strip), switch: r(sw),
    switchBtns: [...document.querySelectorAll('.strip-switch-btn')].map(x => x.querySelector('svg') ? 'svg' : x.textContent.trim()),
    onSwitch: [...document.querySelectorAll('.strip-switch-btn')].findIndex(x => x.classList.contains('on')),
    btns: [...document.querySelectorAll('.bookmark-btn')].map(x => x.textContent.trim()),
    active: on ? on.textContent.trim() : null,
    scrollLeft: strip ? strip.scrollLeft : null,
    maxScroll: strip ? strip.scrollWidth - strip.clientWidth : null,
    mode: window.__barDev ? window.__barDev.stripMode.value : null,
    saved: localStorage.getItem('noty.stripMode'),
    barHidden: document.querySelector('.top-bar').classList.contains('hidden'),
  };
})()
"""


async def main():
    ok = Check()
    async with Harness(APP) as h:
        await h.open()
        await h.open_song(pages=6, reset=False)
        song = await h.ev(GET_SONG, await_promise=True)
        ok("test song exists", bool(song), str(song))
        if not song:
            return ok.report()
        await h.ev(SEED.replace("__SONG__", json.dumps(song)), await_promise=True)
        await asyncio.sleep(0.4)

        # lišta musí být vidět (výchozí stav má horní lištu schovanou)
        await h.ev("localStorage.setItem('topbarHidden', '0')")
        await h.ev("localStorage.removeItem('noty.stripMode')")
        await h.open()
        await h.set_tablet()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", label="songs")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", timeout=40, label="strip")
        await asyncio.sleep(1.0)

        g = await ok_geo(h, ok, "výchozí stav (záložky)")
        ok("výchozí režim = záložky", g["mode"] == "bm", str(g["mode"]))
        ok("lišta ukazuje záložky (5)", len(g["btns"]) == 5 and all("Skladba" in b for b in g["btns"]),
           str(g["btns"]))
        ok("přepínač má dvě volby (ikona záložky / A)", g["switchBtns"] == ["svg", "A"], str(g["switchBtns"]))
        ok("aktivní je ikona záložky", g["onSwitch"] == 0, str(g["onSwitch"]))
        ok("přepínač nepřekrývá seznam",
           bool(g["switch"]) and bool(g["strip"]) and g["switch"]["r"] <= g["strip"]["l"], str(g))

        # --- ťuknutí PRSTEM na „A“ ---
        page_before = await h.page_text()
        sx = (g["switch"]["l"] + g["switch"]["r"]) / 2
        ax = (g["switch"]["r"] - 18)  # druhé kolečko = A
        ay = (g["switch"]["t"] + g["switch"]["b"]) / 2
        await h.finger_tap(ax, ay)
        g2 = await ok_geo(h, ok, "po ťuknutí na A")
        ok("prst na přepínači přepne na značky", g2["mode"] == "mk", str(g2["mode"]))
        ok("lišta ukazuje značky (A–E)", [b[-1:] for b in g2["btns"]] == ["A", "B", "C", "D", "E"], str(g2["btns"]))
        ok("aktivní je A", g2["onSwitch"] == 1, str(g2["onSwitch"]))
        ok("přepnutí neotočilo stránku", page_before == await h.page_text(),
           f"{page_before} -> {await h.page_text()}")
        ok("přepnutí neschovalo lištu", not g2["barHidden"], str(g2["barHidden"]))
        ok("volba se uložila", g2["saved"] == "mk", str(g2["saved"]))
        ok("aktivní značka je A (str. 1)", g2["active"] == "1A", str(g2["active"]))
        await h.cdp("Page.captureScreenshot") if False else None
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open(SHOT, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("screenshot:", SHOT)

        # --- klepnutí na značku D v liště: skok + zvýraznění ---
        await h.ev("(() => { const b = [...document.querySelectorAll('.bookmark-btn')]"
                   ".find(x => x.textContent.trim() === '4D'); if (b) b.click(); return !!b; })()")
        await asyncio.sleep(1.0)
        ok("klepnutí na značku skočí na str. 4", (await h.page_text()).startswith("4 /"), await h.page_text())
        mark = await h.ev("!!document.querySelector('.bar-jump-mark')")
        ok("značka se v notách zvýrazní", mark, str(mark))
        g3 = await ok_geo(h, ok, "po skoku na D")
        ok("aktivní značka je D", g3["active"] == "4D", str(g3["active"]))

        # --- volba drží po reloadu ---
        await h.open()
        await h.set_tablet()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", label="songs 2")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", timeout=40, label="strip 2")
        await asyncio.sleep(1.0)
        g4 = await ok_geo(h, ok, "po reloadu")
        ok("po reloadu zůstaly značky", g4["mode"] == "mk" and len(g4["btns"]) == 5 and g4["btns"][0].endswith("A"), str(g4["btns"]))

        # --- zpět na záložky ---
        await h.finger_tap(g4["switch"]["l"] + 18, (g4["switch"]["t"] + g4["switch"]["b"]) / 2)
        g5 = await ok_geo(h, ok, "zpět na záložky")
        ok("přepnutí zpět na záložky", g5["mode"] == "bm" and all("Skladba" in b for b in g5["btns"]),
           str(g5["btns"]))

        # --- prázdno: skladba bez značek přepínač nemá ---
        await h.ev("(() => new Promise((res) => { const q = indexedDB.open('noty-app');"
                   " q.onsuccess = () => { const tx = q.result.transaction('annotations', 'readwrite');"
                   " tx.objectStore('annotations').delete(%s); tx.oncomplete = () => res(true); }; }))()"
                   % json.dumps(song), await_promise=True)
        await h.open()
        await h.set_tablet()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", label="songs 3")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", timeout=40, label="strip 3")
        await asyncio.sleep(0.8)
        ok("bez značek přepínač není", await h.ev("!document.querySelector('.strip-switch')"))
        ok("bez značek lišta ukazuje záložky",
           await h.ev("document.querySelectorAll('.bookmark-btn').length") == 5)

    return ok.report()


async def ok_geo(h, ok, label):
    g = await h.ev(GEO)
    ok(f"[{label}] lišta je v DOM", bool(g and g["strip"]), str(g and g["strip"]))
    return g or {"btns": [], "switch": None, "strip": None, "mode": None, "onSwitch": -1,
                 "saved": None, "barHidden": True, "active": None}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
