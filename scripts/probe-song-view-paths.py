#!/usr/bin/env python3
"""Kde se uložený POSUN ještě může tiše ztratit?

Navazuje na probe-favorite-position.py (ten prokázal, že hvězdička posun uloží
i vrátí, a to i na živém webu). Zbývají dvě cesty, které Jan při čtení not
používá pořád:

  B) PŘEDNOST ÚROVNÍ: stránka s VLASTNÍM uloženým zobrazením (disketa) má
     přednost před hvězdičkou — a to i v polích, která má v záznamu (i nuly).
     Přesně to může uživatel popsat jako „hvězdička uloží zoom, ale ne pozici“.
     Sonda vypíše, co se na které stránce skutečně zobrazí.

  A) SESTAVA: uložit zobrazení skladby A s posunem → přepnout na skladbu B →
     zpět na A. Vrátí se posun? (`switchSong` mutuje `song.id` a pořadí volání
     applySongView/applyPageView je tam choulostivé.)

Sonda nic v appce nemění; jen měří. Sestavu si připraví zápisem záznamu do
IndexedDB (skupiny se v Knihovně čtou při otevření) — klikat se modálním oknem
by bylo křehčí a netestovalo by to, co potřebuju.

    scripts/run-probe-fresh.sh scripts/probe-song-view-paths.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


def _load_harness():
    cand = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness = _m.Harness

STATE = r"""
(() => {
  const st = document.querySelector('.stage');
  let panX = null, panY = null, zoom = null;
  if (st) {
    const tr = getComputedStyle(st).transform;
    if (tr && tr.startsWith('matrix')) {
      const v = tr.slice(tr.indexOf('(') + 1, -1).split(',').map(Number);
      zoom = Math.round(v[0] * 1000) / 1000;
      panX = Math.round(v[4] * 10) / 10;
      panY = Math.round(v[5] * 10) / 10;
    }
  }
  const nav = document.querySelector('.tb-nav');
  return { zoom, panX, panY,
           song: document.querySelector('.tb-song') ? document.querySelector('.tb-song').textContent.trim() : null,
           page: document.querySelector('.tb-page') ? document.querySelector('.tb-page').textContent.trim() : null,
           group: nav ? document.querySelector('.tb-grp').textContent.trim() : null };
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

# Založí skupinu ze všech nahraných skladeb — ekvivalent „Nová skupina" v Knihovně,
# jen spolehlivější pro test. Skupiny se čtou při otevření Knihovny a při
# navigaci na /prohlizec/<id>?group=<gid>.
MAKE_GROUP = r"""
new Promise((resolve) => {
  const req = indexedDB.open('noty-app');
  req.onsuccess = () => {
    const db = req.result;
    const t = db.transaction(['songs', 'groups'], 'readwrite');
    const songs = t.objectStore('songs').getAll();
    songs.onsuccess = () => {
      const ids = (songs.result || []).map(s => s.id);
      const gid = 'probe-group-1';
      t.objectStore('groups').put({ id: gid, name: 'Probe sestava', songIds: ids, createdAt: Date.now() });
      t.oncomplete = () => resolve({ gid, ids });
      t.onerror = () => resolve({ err: 'tx' });
    };
    songs.onerror = () => resolve({ err: 'songs' });
  };
  req.onerror = () => resolve({ err: 'open' });
})
"""


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
    await asyncio.sleep(0.8)


def fmt(s):
    return f"[{s['song']} {s['group'] or ''}] zoom={s['zoom']} posun=({s['panX']},{s['panY']}) str.{s['page']}"


ok = _m.Check()
c = _m.Check()


async def main():
    async with Harness(_m.APP_URL) as h:
        await h.open()
        await h.open_song(pages=6, reset=True)
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(0.8)

        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

        # ================= B) přednost úrovní =================
        print("\n=== B) stránka s vlastním záznamem vs hvězdička ===")
        print("--- B1) uložím zobrazení STRÁNKY 1 s posunem (disketa) ---")
        await finger_pan(h, cx, cy, 60, 40)
        sA = await h.ev(STATE)
        print("   stav před uložením stránky:", fmt(sA))
        print("   klik:", await tb_click(h, "Uložit jako výchozí jen pro tuto"))
        await asyncio.sleep(1.2)

        print("--- B2) jiný posun, pak hvězdička (celá skladba) ---")
        await finger_pan(h, cx, cy, -110, -90)
        sB = await h.ev(STATE)
        print("   stav před hvězdičkou:", fmt(sB))
        print("   klik:", await tb_click(h, "Uložit jako výchozí pro celou"))
        await asyncio.sleep(1.2)
        print("   v DB:", json.dumps(await h.ev(DB_DUMP, await_promise=True), ensure_ascii=False))

        print("--- B3) na str. 2 a zpět na str. 1 (co uživatel uvidí?) ---")
        await h.goto(2)
        await h.goto(1)
        await asyncio.sleep(0.9)
        s1 = await h.ev(STATE)
        print("   str. 1:", fmt(s1))
        await h.goto(3)
        await asyncio.sleep(0.9)
        s3 = await h.ev(STATE)
        print("   str. 3 (bez vlastního záznamu):", fmt(s3))

        c("B) stránka s VLASTNÍM záznamem drží svůj posun (disketa má přednost)",
          abs(s1["panX"] - sA["panX"]) < 2 and abs(s1["panY"] - sA["panY"]) < 2,
          f"záznam stránky ({sA['panX']},{sA['panY']}) vs viděno ({s1['panX']},{s1['panY']})")
        c("B) stránka BEZ záznamu dědí posun z hvězdičky",
          abs(s3["panX"] - sB["panX"]) < 2 and abs(s3["panY"] - sB["panY"]) < 2,
          f"hvězdička ({sB['panX']},{sB['panY']}) vs viděno ({s3['panX']},{s3['panY']})")

        # ================= A) sestava =================
        print("\n=== A) sestava: přepnutí skladby a zpět ===")
        # druhá skladba, aby sestava měla dvě položky
        await h.open()
        await h.wait_for("document.querySelectorAll('.author-group').length > 0", 60, "knihovna")
        await h.set_file_input("input[type=file]", _m.make_pdf(6, "/tmp/noty-fixture-2.pdf"))
        await asyncio.sleep(2.0)
        await h.open()
        await h.wait_for("document.querySelectorAll('.author-group').length > 0", 60, "knihovna")
        made = await h.ev(MAKE_GROUP, await_promise=True)
        print("   skupina:", json.dumps(made, ensure_ascii=False))
        if not made or "gid" not in made or len(made.get("ids", [])) < 2:
            print("   (nepodařilo se připravit 2 skladby — měření sestavy přeskočeno)")
            return ok.report() | c.report()

        gid, ids = made["gid"], made["ids"]
        # otevřít PRVNÍ skladbu sestavy přes router (stejná URL, jakou staví Knihovna)
        await h.cdp("Page.navigate", {"url": f"{_m.APP_URL}prohlizec/{ids[0]}?group={gid}"})
        await h.wait_for("!!document.querySelector('.tb-page')", 60, "viewer v sestavě")
        await h.wait_for("!document.querySelector('.viewer-loading')", 60, "první stránka")
        await asyncio.sleep(1.5)

        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

        print("--- A1) posun v 1. skladbě a uložení hvězdičkou ---")
        await finger_pan(h, cx, cy, 70, 45)
        sP = await h.ev(STATE)
        print("   ", fmt(sP))
        print("   klik:", await tb_click(h, "Uložit jako výchozí pro celou"))
        await asyncio.sleep(1.2)

        print("--- A2) další skladba v sestavě (tlačítko v liště) ---")
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '') === 'Další skladba'); if (b) b.click(); })()")
        await asyncio.sleep(2.5)
        sB2 = await h.ev(STATE)
        print("   ", fmt(sB2))

        print("--- A3) zpět na 1. skladbu ---")
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '') === 'Předchozí skladba'); if (b) b.click(); })()")
        await asyncio.sleep(2.5)
        sP2 = await h.ev(STATE)
        print("   ", fmt(sP2))
        print("   v DB:", json.dumps(await h.ev(DB_DUMP, await_promise=True), ensure_ascii=False))

        c("A) po přepnutí skladby a zpět se vrátí uložený POSUN",
          abs(sP2["panX"] - sP["panX"]) < 2 and abs(sP2["panY"] - sP["panY"]) < 2,
          f"uloženo ({sP['panX']},{sP['panY']}) vs po návratu ({sP2['panX']},{sP2['panY']})")
        c("A) přepnutí na jinou skladbu použije JEJÍ uložené zobrazení (ne posun z A)",
          abs(sB2["panX"] - sP["panX"]) > 5 or abs(sB2["panY"] - sP["panY"]) > 5,
          f"A=({sP['panX']},{sP['panY']}) vs B=({sB2['panX']},{sB2['panY']})")

    return ok.report() | c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
