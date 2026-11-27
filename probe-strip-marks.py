#!/usr/bin/env python3
"""Přepínač dole + ZNAČKY POD ZÁLOŽKAMI (Jan, 27. 11. 2026).

Ověřuje:
  * lišta má vlevo přepínač (ikona záložky / A) a v režimu značek mění obsah,
  * značky jsou v liště rozdělené podle záložek: rozbalovací tlačítko s názvem
    záložky, otevřená je VŽDY JEN JEDNA (ta, ve které stojíš), ostatní sbalené,
  * klepnutí na název záložky skočí na její začátek a tím ji otevře,
  * klepnutí na značku skočí na stránku a zvýrazní ji,
  * volba režimu drží po reloadu, ťuknutí prstem neotočí stránku,
  * bez záložek je plochý seznam značek, bez značek přepínač zmizí.
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
  const strip = document.querySelector('.bookmark-strip');
  const sw = document.querySelector('.strip-switch');
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect();
    return {l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top),
            b: Math.round(b.bottom), w: Math.round(b.width), h: Math.round(b.height)}; };
  return {
    strip: r(strip), switch: r(sw),
    switchBtns: [...document.querySelectorAll('.strip-switch-btn')]
      .map(x => x.querySelector('svg') ? 'svg' : x.textContent.trim()),
    onSwitch: [...document.querySelectorAll('.strip-switch-btn')].findIndex(x => x.classList.contains('on')),
    groups: [...document.querySelectorAll('.strip-group')].map(g => ({
      name: (g.querySelector('.strip-group-name') || {}).textContent,
      n: (g.querySelector('.strip-group-n') || {}).textContent,
      caret: (g.querySelector('.strip-group-caret') || {}).textContent,
      on: g.classList.contains('on'),
    })),
    btns: [...document.querySelectorAll('.bookmark-btn')].map(x => x.textContent.trim()),
    active: (strip ? strip.querySelector('.bookmark-btn.on') : null)
      ? strip.querySelector('.bookmark-btn.on').textContent.trim() : null,
    mode: window.__barDev ? window.__barDev.stripMode.value : null,
    openKey: window.__barDev ? window.__barDev.mkStripOpenKey.value : null,
    saved: localStorage.getItem('noty.stripMode'),
    barHidden: document.querySelector('.top-bar').classList.contains('hidden'),
  };
})()
"""


async def snapshot(h, ok, label):
    g = await h.ev(GEO)
    ok(f"[{label}] lišta je v DOM", bool(g and g["strip"]),
       "ok" if g and g["strip"] else str(g))
    return g


async def tap_group(h, name):
    return await h.ev(
        "(() => { const g = [...document.querySelectorAll('.strip-group')]"
        ".find(x => x.querySelector('.strip-group-name').textContent === %s);"
        " if (!g) return false; g.click(); return true; })()" % json.dumps(name))


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

        g = await snapshot(h, ok, "výchozí stav (záložky)")
        ok("výchozí režim = záložky", g["mode"] == "bm", str(g["mode"]))
        ok("lišta ukazuje záložky (5)", len(g["btns"]) == 5 and all("Skladba" in b for b in g["btns"]),
           str(g["btns"]))
        ok("v režimu záložek nejsou skupiny značek", g["groups"] == [], str(g["groups"]))
        ok("přepínač má dvě volby (ikona záložky / A)", g["switchBtns"] == ["svg", "A"],
           str(g["switchBtns"]))
        ok("aktivní je ikona záložky", g["onSwitch"] == 0, str(g["onSwitch"]))
        ok("přepínač nepřekrývá seznam",
           bool(g["switch"]) and bool(g["strip"]) and g["switch"]["r"] <= g["strip"]["l"], "")

        # --- ťuknutí PRSTEM na „A“ ---
        page_before = await h.page_text()
        ax = g["switch"]["r"] - 18  # druhé kolečko = A
        ay = (g["switch"]["t"] + g["switch"]["b"]) / 2
        await h.finger_tap(ax, ay)
        g2 = await snapshot(h, ok, "po ťuknutí na A")
        ok("prst na přepínači přepne na značky", g2["mode"] == "mk", str(g2["mode"]))
        ok("přepnutí neotočilo stránku", page_before == await h.page_text(), page_before)
        ok("přepnutí neschovalo lištu", not g2["barHidden"], "")
        ok("volba se uložila", g2["saved"] == "mk", str(g2["saved"]))
        ok("značky jsou rozdělené po záložkách (5 tlačítek)", len(g2["groups"]) == 5,
           str([x["name"] for x in g2["groups"]]))
        ok("otevřená je JEN JEDNA skupina",
           sum(1 for x in g2["groups"] if x["on"]) == 1,
           str([x["name"] for x in g2["groups"] if x["on"]]))
        op = next((x for x in g2["groups"] if x["on"]), None)
        ok("otevřená je záložka, ve které stojím (Skladba 1)",
           bool(op) and op["name"] == "Skladba 1" and op["caret"] == "▾", str(op))
        ok("sbalené skupiny mají šipku ▸",
           all(x["caret"] == "▸" for x in g2["groups"] if not x["on"]),
           str([x["caret"] for x in g2["groups"]]))
        ok("vidět je jen značka otevřené skupiny (1A)",
           g2["btns"] == ["1A"], str(g2["btns"]))
        ok("skupina ukazuje počet značek", all(x["n"] == "1" for x in g2["groups"]),
           str([x["n"] for x in g2["groups"]]))

        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open(SHOT, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("screenshot:", SHOT)

        # --- klepnutí na název jiné záložky: skok + rozbalení ---
        ok("tlačítko Skladba 4 existuje", await tap_group(h, "Skladba 4"))
        await asyncio.sleep(1.0)
        g3 = await snapshot(h, ok, "po klepnutí na Skladba 4")
        ok("klepnutí na název záložky skočí na str. 4",
           (await h.page_text()).startswith("4 /"), await h.page_text())
        op3 = next((x for x in g3["groups"] if x["on"]), None)
        ok("otevřela se Skladba 4", bool(op3) and op3["name"] == "Skladba 4", str(op3))
        ok("zase je otevřená jen jedna skupina",
           sum(1 for x in g3["groups"] if x["on"]) == 1, "")
        ok("vidět je značka 4D", g3["btns"] == ["4D"], str(g3["btns"]))
        ok("aktivní značka je D", g3["active"] == "4D", str(g3["active"]))

        # --- klepnutí na značku uvnitř skupiny ---
        await h.ev("(() => { const b = document.querySelector('.bookmark-btn');"
                   " if (b) b.click(); return !!b; })()")
        await asyncio.sleep(0.8)
        ok("klepnutí na značku zvýrazní místo v notách",
           await h.ev("!!document.querySelector('.bar-jump-mark')"), "")

        # --- volba + otevřená skupina po reloadu ---
        await h.open()
        await h.set_tablet()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", label="songs 2")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", timeout=40, label="strip 2")
        await asyncio.sleep(1.0)
        g4 = await snapshot(h, ok, "po reloadu")
        ok("po reloadu zůstaly značky", g4["mode"] == "mk", str(g4["mode"]))
        ok("po reloadu je otevřená skupina podle aktuální stránky",
           bool(next((x for x in g4["groups"] if x["on"] and x["name"] == "Skladba 1"), None)),
           str([x["name"] for x in g4["groups"] if x["on"]]))

        # --- zavření otevřené záložky: hodně značek vytlačí ostatní záložky ---
        ok("otevřená skupina jde zavřít ťuknutím na svůj název",
           await tap_group(h, "Skladba 1"))
        await asyncio.sleep(0.6)
        g4b = await snapshot(h, ok, "po zavření skupiny")
        ok("po zavření není otevřená žádná skupina",
           [x for x in g4b["groups"] if x["on"]] == [] and g4b["openKey"] is None,
           str(g4b["openKey"]))
        ok("po zavření nejsou v liště žádné značky", g4b["btns"] == [], str(g4b["btns"]))
        ok("všechny skupiny mají šipku ▸",
           all(x["caret"] == "▸" for x in g4b["groups"]), str([x["caret"] for x in g4b["groups"]]))
        ok("zavření nezmění stránku", (await h.page_text()).startswith("1 /"), await h.page_text())

        # listování nesmí zavřenou skupinu znovu otevřít
        await h.goto(2)
        await asyncio.sleep(0.8)
        g4c = await snapshot(h, ok, "po listování se zavřenou skupinou")
        ok("po listování zůstává vše sbalené",
           [x for x in g4c["groups"] if x["on"]] == [] and g4c["btns"] == [],
           str(g4c["openKey"]))

        # otevření jiné záložky = skok na její začátek + rozbalení
        ok("jde otevřít jinou záložku", await tap_group(h, "Skladba 3"))
        await asyncio.sleep(1.0)
        g4d = await snapshot(h, ok, "po otevření Skladby 3")
        ok("otevření jiné záložky skočí na str. 3",
           (await h.page_text()).startswith("3 /"), await h.page_text())
        ok("otevřená je jen Skladba 3 a její značka 3C",
           [x["name"] for x in g4d["groups"] if x["on"]] == ["Skladba 3"]
           and g4d["btns"] == ["3C"], str(g4d["btns"]))

        # --- zpět na záložky ---
        await h.finger_tap(g4["switch"]["l"] + 18, (g4["switch"]["t"] + g4["switch"]["b"]) / 2)
        g5 = await snapshot(h, ok, "zpět na záložky")
        ok("přepnutí zpět na záložky", g5["mode"] == "bm" and all("Skladba" in b for b in g5["btns"]),
           str(g5["btns"]))
        ok("v režimu záložek skupiny zmizí", g5["groups"] == [], str(g5["groups"]))

        # --- značky bez záložek: plochý seznam ---
        await h.ev("(() => new Promise((res) => { const q = indexedDB.open('noty-app');"
                   " q.onsuccess = () => { const tx = q.result.transaction('bookmarks', 'readwrite');"
                   " tx.objectStore('bookmarks').delete(%s); tx.oncomplete = () => res(true); }; }))()"
                   % json.dumps(song), await_promise=True)
        await h.open()
        await h.set_tablet()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", label="songs 3")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", timeout=40, label="strip 3")
        await asyncio.sleep(1.0)
        g6 = await snapshot(h, ok, "jen značky, bez záložek")
        ok("bez záložek je plochý seznam značek (5)", len(g6["btns"]) == 5, str(g6["btns"]))
        ok("bez záložek nejsou skupiny", g6["groups"] == [], str(g6["groups"]))
        ok("bez záložek není přepínač", await h.ev("!document.querySelector('.strip-switch')"), "")

        # --- bez značek: přepínač zmizí, lišta ukáže záložky ---
        # (záložky se vracejí, protože předchozí krok je smazal)
        await h.ev(SEED.replace("__SONG__", json.dumps(song)), await_promise=True)
        await h.ev("(() => new Promise((res) => { const q = indexedDB.open('noty-app');"
                   " q.onsuccess = () => { const tx = q.result.transaction('annotations', 'readwrite');"
                   " tx.objectStore('annotations').delete(%s); tx.oncomplete = () => res(true); }; }))()"
                   % json.dumps(song), await_promise=True)
        await h.open()
        await h.set_tablet()
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", label="songs 4")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.bookmark-strip')", timeout=40, label="strip 4")
        await asyncio.sleep(0.8)
        ok("bez značek přepínač není", await h.ev("!document.querySelector('.strip-switch')"), "")
        ok("bez značek lišta ukazuje záložky",
           await h.ev("document.querySelectorAll('.bookmark-btn').length") == 5, "")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
