#!/usr/bin/env python3
"""Uloží hvězdička (výchozí zobrazení skladby) opravdu i POSUN stránky?

Jan: „Hvězdička (oblíbené) teď uloží hodnotu zoom pro celý dokument. Asi by
bylo fajn, kdyby to ukládalo i pozici. Posun nahoru, do boku atd.“

Kód tvrdí, že panX/panY ukládá (saveZoomAsDefault → dbSaveSongView). Sonda to
NEVĚŘÍ a proměří celý řetězec, protože každé kolečko se dá pokazit jinde:

  1) čerstvá skladba                       → stav před (zoom 1, posun 0,0)
  2) dvouprstý posun (+40, +30)            → posun se opravdu hýbe?
  3) ULOŽIT (hvězdička)                    → co se zapsalo do IndexedDB? (celý záznam)
  4) VYCENTROVAT                          → vrátí se ULOŽENÝ posun, nebo se vynuluje?
       ⚠️ Tohle je klíčové: kdyby Vycentrovat posun ignorovalo, uživatel to
       uvidí jako „posun se neukládá“ — a přitom je chyba v obnově.
  5) reload + znovuotevřít skladbu         → vrátí se posun i po restartu?
  6) uložit STRÁNKU (disketa) a znovuotevřít → funguje posun i na úrovni stránky?

Hodnoty se čtou z COMPUTED TRANSFORM `.stage` (matrix(a,b,c,d,e,f): a = měřítko,
e/f = posun) a ze ZÁZNAMU v IndexedDB (meta 'view:<songId>' / 'pview:...') —
ne z refů, které by mohly lhát.

    scripts/run-probe-fresh.sh scripts/probe-favorite-position.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


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

# Živý stav čteme z computed transformu .stage — ten je jediná pravda o tom,
# co uživatel vidí. (matrix(a,b,c,d,e,f): a = zoom*liveFit, e/f = panX/panY)
STATE = r"""
(() => {
  const st = document.querySelector('.stage');
  let zoom = null, panX = null, panY = null, rot = null;
  if (st) {
    const tr = getComputedStyle(st).transform;
    if (tr && tr.startsWith('matrix')) {
      const v = tr.slice(tr.indexOf('(') + 1, -1).split(',').map(Number);
      zoom = Math.round(v[0] * 1000) / 1000;
      panX = Math.round(v[4] * 10) / 10;
      panY = Math.round(v[5] * 10) / 10;
    }
  }
  const ro = document.querySelector('.rotor');
  if (ro) {
    const tr = getComputedStyle(ro).transform;
    if (tr && tr.startsWith('matrix')) {
      const v = tr.slice(tr.indexOf('(') + 1, -1).split(',').map(Number);
      rot = Math.round(Math.atan2(v[1], v[0]) * 180 / Math.PI * 10) / 10;
    } else rot = 0;
  }
  return { zoom, panX, panY, rot, page: document.querySelector('.tb-page') ? document.querySelector('.tb-page').textContent.trim() : null };
})()
"""

# Co je OPRAVDU v IndexedDB (ne co si myslí kód)
DB_DUMP = r"""
new Promise((resolve) => {
  const req = indexedDB.open('noty-app');
  req.onsuccess = () => {
    const db = req.result;
    const t = db.transaction('meta', 'readonly');
    const s = t.objectStore('meta');
    const keys = s.getAllKeys();
    keys.onsuccess = () => {
      const out = {};
      const ks = (keys.result || []).filter(k => typeof k === 'string' && (k.startsWith('view:') || k.startsWith('pview:')));
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


async def tb_click(h, title_start):
    return await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                      ".find(x => (x.title || '').startsWith(%s));"
                      " if (!b) return 'missing'; b.click(); return 'ok'; })()"
                      % json.dumps(title_start))


def fmt(s):
    return f"zoom={s['zoom']} posun=({s['panX']},{s['panY']}) rot={s['rot']} str.{s['page']}"


async def finger_pan(h, cx, cy, dx, dy, gap=140, steps=6):
    """Dvouprstý POSUN: oba prsty se posunou o (dx, dy), vzdálenost zůstává.

    ⚠️ Posílá se JEN touchStart + touchMove + touchEnd (žádný touchstart
    s jedním prstem) — v `touchstart` s jedním prstem se totiž staví `_touchStart`
    pro okrajové listování, ale `_pinch` se nezakládá; ten vzniká až v touchmove
    se dvěma dotyky. Přesně tak to dělá appka.
    """
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


async def main():
    ok = Check()
    async with Harness(_m.APP_URL) as h:
        await h.open()
        await h.open_song(pages=6, reset=True)
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(0.6)

        g = await h.geo()
        cx = g["left"] + g["w"] / 2
        cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

        print("\n--- 1) čerstvá skladba (má být zoom 1, posun 0,0) ---")
        s0 = await h.ev(STATE)
        print("   živý stav:", fmt(s0))
        dump = await h.ev(DB_DUMP, await_promise=True)
        print("   v DB:", json.dumps(dump, ensure_ascii=False))
        ok("1) čerstvá skladba začíná bez posunu", s0["panX"] == 0 and s0["panY"] == 0, fmt(s0))

        print("\n--- 2) dvouprstý POSUN o +40 vpravo, +30 dolů ---")
        await finger_pan(h, cx, cy, 40, 30)
        s1 = await h.ev(STATE)
        print("   živý stav:", fmt(s1))
        ok("2) dvouprstý posun opravdu pohne stránkou",
           s1["panX"] > 10 and s1["panY"] > 8, fmt(s1))

        # Posun na výšku i do strany (Jan: „Posun nahoru, do boku atd.“)
        await finger_pan(h, cx, cy, -15, -60)
        s2 = await h.ev(STATE)
        print("   po druhém tahu (-15, -60):", fmt(s2))

        print("\n--- 3) ULOŽIT výchozí zobrazení SKLADBY (hvězdička) ---")
        print("   klik:", await tb_click(h, "Uložit jako výchozí pro celou"))
        await asyncio.sleep(1.2)
        dump = await h.ev(DB_DUMP, await_promise=True)
        print("   v DB:", json.dumps(dump, ensure_ascii=False))
        rec = next((v for k, v in dump.items() if k.startswith("view:")), None)
        ok("3) záznam skladby v DB obsahuje NENULOVÝ posun",
           bool(rec) and isinstance(rec, dict) and (rec.get("panX") or rec.get("panY")),
           json.dumps(rec, ensure_ascii=False))

        print("\n--- 4) VYCENTROVAT (má vrátit ULOŽENÝ stav včetně posunu) ---")
        # Nejdřív stránku odtáhneme jinam, ať je vidět, že ji Vycentrovat opravdu vrátí.
        await finger_pan(h, cx, cy, 120, 90)
        sMoved = await h.ev(STATE)
        print("   před vycentrováním (odtaženo):", fmt(sMoved))
        print("   klik:", await tb_click(h, "Vycentrovat"))
        await asyncio.sleep(1.0)
        s3 = await h.ev(STATE)
        print("   po vycentrování:", fmt(s3))
        ok("4) Vycentrovat vrátí uložený POSUN (ne 0,0)",
           s3["panX"] is not None and abs(s3["panX"] - s2["panX"]) < 2
           and abs(s3["panY"] - s2["panY"]) < 2,
           f"uloženo ({s2['panX']},{s2['panY']}) vs vráceno ({s3['panX']},{s3['panY']})")

        print("\n--- 5) reload stránky + znovuotevření skladby (přežije posun restart?) ---")
        await h.open()
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=30, label="knihovna po reloadu")
        await h.ev(h.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", 10, "seznam skladeb")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", 40, "otevření skladby")
        await h.wait_for("!document.querySelector('.viewer-loading')", 40, "první stránka")
        await asyncio.sleep(1.4)
        s4 = await h.ev(STATE)
        print("   po znovuotevření:", fmt(s4))
        ok("5) po znovuotevření skladby je POSUN zpět",
           s4["panX"] is not None and abs(s4["panX"] - s2["panX"]) < 2
           and abs(s4["panY"] - s2["panY"]) < 2,
           f"uloženo ({s2['panX']},{s2['panY']}) vs po reloadu ({s4['panX']},{s4['panY']})")

        print("\n--- 6) totéž pro úroveň STRÁNKY (disketa) ---")
        await finger_pan(h, cx, cy, 55, 35)
        s5 = await h.ev(STATE)
        print("   posun před uložením stránky:", fmt(s5))
        print("   klik:", await tb_click(h, "Uložit jako výchozí jen pro tuto"))
        await asyncio.sleep(1.2)
        dump = await h.ev(DB_DUMP, await_promise=True)
        prec = next((v for k, v in dump.items() if k.startswith("pview:")), None)
        print("   záznam stránky v DB:", json.dumps(prec, ensure_ascii=False))
        ok("6) záznam stránky v DB obsahuje NENULOVÝ posun",
           bool(prec) and isinstance(prec, dict) and (prec.get("panX") or prec.get("panY")),
           json.dumps(prec, ensure_ascii=False))

        # Přepnout na jinou stránku a zpět → musí se vrátit uložený posun
        await h.goto(3)
        await h.goto(1)
        await asyncio.sleep(0.8)
        s6 = await h.ev(STATE)
        print("   po cestě na str. 3 a zpět:", fmt(s6))
        ok("6) návrat na stránku vrátí její POSUN",
           s6["panX"] is not None and abs(s6["panX"] - s5["panX"]) < 2
           and abs(s6["panY"] - s5["panY"]) < 2,
           f"uloženo ({s5['panX']},{s5['panY']}) vs vráceno ({s6['panX']},{s6['panY']})")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
