#!/usr/bin/env python3
"""ŽIVÝ web: ukládá hvězdička i POSUN stránky, nebo jen zoom?

Jan: „Hvězdička (oblíbené) teď uloží hodnotu zoom pro celý dokument. Asi by
bylo fajn, kdyby to ukládalo i pozici. Posun nahoru, do boku atd.“

Dev sestava ukládá i obnovuje posun správně (probe-favorite-position.py), takže
rozhoduje jediná otázka: **je to i v NASazené appce?** PWA drží starý service
worker, takže Jan může vidět starou verzi i po nasazení — sonda proto nejdřív
odregistruje SW, smaže CacheStorage i IndexedDB (jinak hlásí falešný FAIL).

Navíc se podívá PŘÍMO DO NASAZENÉHO BUNDLU, jestli v něm ta funkce vůbec je —
odpoví to na „je to stará verze, nebo se to neukládá“ bez hádání.

    NOTY_CDP=http://127.0.0.1:9226 python3 -u scripts/probe-live-favorite-position.py
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_HERE)
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_APP, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check = _mod.Harness, _mod.Check
# Port si ber z prostředí — jinak by sonda mluvila na výchozí 9223 a spadla
# na ConnectionRefused, i když Chrome běží jinde.
_mod.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")

LIVE = "https://harlequin-music-reader.web.app/"

STATE = r"""
(() => {
  const st = document.querySelector('.stage');
  let zoom = null, panX = null, panY = null;
  if (st) {
    const tr = getComputedStyle(st).transform;
    if (tr && tr.startsWith('matrix')) {
      const v = tr.slice(tr.indexOf('(') + 1, -1).split(',').map(Number);
      zoom = Math.round(v[0] * 1000) / 1000;
      panX = Math.round(v[4] * 10) / 10;
      panY = Math.round(v[5] * 10) / 10;
    }
  }
  return { zoom, panX, panY,
           page: document.querySelector('.tb-page') ? document.querySelector('.tb-page').textContent.trim() : null };
})()
"""

CLEAN = r"""
(async () => {
  const rs = await navigator.serviceWorker.getRegistrations();
  for (const r of rs) await r.unregister();
  for (const k of await caches.keys()) await caches.delete(k);
  indexedDB.deleteDatabase('noty-app');
  return true;
})()
"""

DB_DUMP = r"""
new Promise((resolve) => {
  const req = indexedDB.open('noty-app');
  req.onsuccess = () => {
    const db = req.result;
    const s = db.transaction('meta', 'readonly').objectStore('meta');
    const keys = s.getAllKeys();
    keys.onsuccess = () => {
      const out = {};
      const ks = (keys.result || []).filter(k => typeof k === 'string' &&
        (k.startsWith('view:') || k.startsWith('pview:')));
      if (!ks.length) return resolve(out);
      let n = 0;
      for (const k of ks) {
        const g = s.get(k);
        g.onsuccess = () => { out[k] = g.result; if (++n === ks.length) resolve(out); };
        g.onerror = () => { out[k] = 'ERR'; if (++n === ks.length) resolve(out); };
      }
    };
    keys.onerror = () => resolve({ err: 'keys' });
  };
  req.onerror = () => resolve({ err: 'open' });
})
"""


def fmt(s):
    return f"zoom={s['zoom']} posun=({s['panX']},{s['panY']}) str.{s['page']}"


async def tb_click(h, title_start):
    return await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                      ".find(x => (x.title || '').startsWith(%s));"
                      " if (!b) return 'missing'; b.click(); return 'ok'; })()"
                      % json.dumps(title_start))


async def finger_pan(h, cx, cy, dx, dy, gap=140, steps=6):
    def pts(f):
        return [(cx - gap / 2 + dx * f, cy + dy * f, 12),
                (cx + gap / 2 + dx * f, cy + dy * f, 12)]
    await h.touch("touchStart", pts(0))
    await asyncio.sleep(0.08)
    for i in range(1, steps + 1):
        await h.touch("touchMove", pts(i / steps))
        await asyncio.sleep(0.03)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.9)


async def main():
    ok = Check()
    async with Harness(url=LIVE) as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await h.ev(CLEAN, await_promise=True)
        await asyncio.sleep(1.0)
        await h.cdp("Page.reload", {"ignoreCache": True})
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(3.0)

        # --- Je funkce vůbec v nasazeném bundlu? (jinak je to stará verze) ---
        bundle = await h.ev(r"""
(async () => {
  const src = performance.getEntriesByType('resource')
    .map(e => e.name).filter(n => /assets\/index-.*\.js$/.test(n) || /assets\/Prohlizec-.*\.js$/.test(n));
  const out = [];
  for (const u of src) {
    const t = await (await fetch(u)).text();
    out.push({ url: u, len: t.length,
      savesPan: t.includes('panX') && t.includes('Výchozí zobrazení skladby uloženo'),
      toast: t.includes('Výchozí zobrazení skladby uloženo') });
  }
  return out;
})()
""", await_promise=True)
        print("nasazené bundly:")
        for b in (bundle or []):
            print(f"   {b['url']}  ({b['len']} B)  ukládá posun: {b['savesPan']}  hlaska: {b['toast']}")

        # --- nahraj fixture a otevři skladbu ---
        pdf = _mod.make_pdf(6)
        await h.set_file_input("input[type=file]", pdf)
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=90, label="PDF upload")
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "seznam")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 60, "otevření skladby")
        await h.wait_for("!document.querySelector('.viewer-loading')", 60, "první stránka")
        await asyncio.sleep(2.0)

        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

        print("\n--- 1) čerstvá skladba ---")
        s0 = await h.ev(STATE)
        print("   ", fmt(s0))

        print("\n--- 2) dvouprstý POSUN (+40, +30) ---")
        await finger_pan(h, cx, cy, 40, 30)
        s1 = await h.ev(STATE)
        print("   ", fmt(s1))
        ok("na ŽIVÉM webu dvouprstý posun pohne stránkou",
           s1["panX"] is not None and s1["panX"] > 10 and s1["panY"] > 8, fmt(s1))

        print("\n--- 3) hvězdička = uložit výchozí zobrazení skladby ---")
        print("   klik:", await tb_click(h, "Uložit jako výchozí pro celou"))
        await asyncio.sleep(1.5)
        dump = await h.ev(DB_DUMP, await_promise=True)
        print("   v DB:", json.dumps(dump, ensure_ascii=False))
        rec = next((v for k, v in dump.items() if k.startswith("view:")), None)
        ok("záznam skladby v DB obsahuje NENULOVÝ posun",
           bool(rec) and isinstance(rec, dict) and (rec.get("panX") or rec.get("panY")),
           json.dumps(rec, ensure_ascii=False))

        print("\n--- 4) reload + znovuotevření skladby (vrátí se POSUN?) ---")
        await h.open()
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=60, label="knihovna po reloadu")
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 15, "seznam")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 60, "otevření skladby")
        await h.wait_for("!document.querySelector('.viewer-loading')", 60, "první stránka")
        await asyncio.sleep(2.5)
        s2 = await h.ev(STATE)
        print("   ", fmt(s2))
        ok("po znovuotevření na ŽIVÉM webu je posun zpět",
           s2["panX"] is not None and abs(s2["panX"] - s1["panX"]) < 2
           and abs(s2["panY"] - s1["panY"]) < 2,
           f"uloženo ({s1['panX']},{s1['panY']}) vs vráceno ({s2['panX']},{s2['panY']})")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
