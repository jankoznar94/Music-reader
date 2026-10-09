#!/usr/bin/env python3
"""Živý web: lišta úprav se MUSÍ vejít — koš uvnitř lišty i displeje (Jan, Oct 2026).

Ověřuje opravu proti https://harlequin-music-reader.web.app — tedy proti build,
který uživatel opravdu dostane. Nejdřív odregistruje starý service worker a smaže
CacheStorage i IndexedDB, jinak prohlížeč servíruje STAROU verzi a sonda hlásí
falešný FAIL (to je u PWA ta hlavní past).

Měří to, co Jan viděl jako „koš utíká mimo lištu“:
  - počet řádků lišty (musí být 2: hlavní + řádek rámu),
  - `scrollWidth` vs `clientWidth` lišty (obsah se nesmí přelévat),
  - každé dítě proti vnitřku lišty a proti displeji,
  - u 🗑 `elementFromPoint(jeho střed)` → musí trefit koš (jinak nejde stisknout).

    bash scripts/run-probe-fresh.sh scripts/probe-live-editbar-width.py
"""
import asyncio
import importlib.util
import json
import os

LIVE = os.environ.get("NOTY_TARGET", "https://harlequin-music-reader.web.app/")
CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("h", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = CDP
Harness, Check = _m.Harness, _m.Check

MEASURE = """(() => {
  const bar = document.querySelector('.edit-bar');
  if (!bar) return JSON.stringify({bar: false});
  const vw = innerWidth;
  const r = bar.getBoundingClientRect();
  const cs = getComputedStyle(bar);
  const inner = {
    left: r.left + parseFloat(cs.paddingLeft) + parseFloat(cs.borderLeftWidth),
    right: r.right - parseFloat(cs.paddingRight) - parseFloat(cs.borderRightWidth),
  };
  const kids = [...bar.querySelectorAll('.eb-row > *')].map(el => {
    const q = el.getBoundingClientRect();
    return {label: ((el.textContent || '').trim() || el.title || '').slice(0, 14),
            right: Math.round(q.right), left: Math.round(q.left),
            overBar: q.right > inner.right + 0.6 || q.left < inner.left - 0.6,
            overScreen: q.right > vw || q.left < 0};
  });
  const trash = bar.querySelector(".eb-btn[title='Smazat']");
  const t = trash.getBoundingClientRect();
  const hit = document.elementFromPoint(t.left + t.width / 2, t.top + t.height / 2);
  return JSON.stringify({
    bar: true, vw, rows: bar.querySelectorAll('.eb-row').length,
    barW: Math.round(r.width), scrollW: bar.scrollWidth, clientW: bar.clientWidth,
    overflowing: bar.scrollWidth > bar.clientWidth + 1,
    kids, nKids: kids.length,
    trashRight: Math.round(t.right), trashLeft: Math.round(t.left),
    trashOnScreen: t.right <= vw && t.left >= 0,
    trashClickable: !!(hit && hit.closest && hit.closest(".eb-btn[title='Smazat']") === trash),
  });
})()"""


async def tap_el(h, sel, hold=60):
    pt = await h.ev("""(() => {
      const sel = %s; const el = document.querySelector(sel); if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(sel) === el))) return [x+0.5, y+0.5];
        }
      return null; })()""" % json.dumps(sel))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.45)
    return True


async def tap_text(h, sel, label):
    pt = await h.ev("""(() => {
      const el = [...document.querySelectorAll(%s)].find(b => (b.textContent||'').trim() === %s);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top)+1; y <= Math.ceil(r.bottom)-1; y += 2)
        for (let x = Math.floor(r.left)+1; x <= Math.ceil(r.right)-1; x += 2)
          if (document.elementFromPoint(x, y) === el) return [x+0.5, y+0.5];
      return null; })()""" % (json.dumps(sel), json.dumps(label)))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(0.06)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.45)
    return True


COLLAPSE = ".ap-collapse"


async def panel(h, want):
    if await h.ev("!!document.querySelector(%s[title=%s])" % (json.dumps(COLLAPSE), json.dumps(want))):
        await tap_el(h, COLLAPSE)


async def free_xy(h):
    p = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')].map(e=>e.getBoundingClientRect());
      const near = (x,y) => boxes.some(r => r.width>0 && x>r.left-34 && x<r.right+34 && y>r.top-34 && y<r.bottom+34);
      for (const fy of [0.30,0.38,0.46,0.54,0.62]) for (const fx of [0.60,0.52,0.44,0.36,0.68,0.28]) {
        const x = v.left + v.width*fx, y = v.top + v.height*fy;
        if (document.elementFromPoint(x,y) === svg && !near(x,y)) return {x,y}; }
      return null; })()""")
    return (p["x"], p["y"]) if p else None


async def insert_text(h, txt, border):
    """Vloží text a VRÁTÍ bod, na kterém leží — tím se pak vybírá rukou.
    (Nové volání `free_xy` po vložení by vrátilo PRÁZDNÉ místo, klepnutí by
    text minulo a lišta úprav by se vůbec neotevřela.)"""
    xy = await free_xy(h)
    if not xy:
        return None
    await panel(h, "Rozbalit")
    await h.ev("(() => { const b=[...document.querySelectorAll('.ap-tool')].find(x=>(x.title||'').startsWith('Text')); if(b) b.click(); })()")
    await asyncio.sleep(0.35)
    await panel(h, "Sbalit")
    await h.pen_tap(xy[0], xy[1])
    await asyncio.sleep(0.9)
    await h.set_value(".ti-input", txt)
    on = await h.ev("!!document.querySelector('.ti-toggle.on')")
    if border and not on:
        await tap_el(h, ".ti-toggle")
    if not border and on:
        await tap_el(h, ".ti-toggle")
    await asyncio.sleep(0.3)
    await tap_el(h, ".jp-btn.primary")
    await asyncio.sleep(1.3)
    return xy


async def select_hand(h, xy):
    await panel(h, "Rozbalit")
    await h.ev("(() => { const b=[...document.querySelectorAll('.ap-tool')].find(x=>(x.title||'').startsWith('Upravit')); if(b) b.click(); })()")
    await asyncio.sleep(0.35)
    await panel(h, "Sbalit")
    await h.pen_tap(xy[0], xy[1])
    await asyncio.sleep(0.9)


async def main():
    ok = Check()
    async with Harness(LIVE) as h:
        await h.cdp("Page.navigate", {"url": LIVE})
        await h.wait_for("document.readyState === 'complete'", label="live load")
        await h.ev("""(async () => { if (navigator.serviceWorker) {
          const rs = await navigator.serviceWorker.getRegistrations();
          for (const r of rs) await r.unregister(); }
          if (window.caches) { const ks = await caches.keys(); for (const k of ks) await caches.delete(k); }
          return true; })()""", await_promise=True)
        await asyncio.sleep(0.5)
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet(800, 1280, 2)
        await h.annot_toggle()
        await asyncio.sleep(0.4)

        # --- A) text s rámečkem = nejširší stav lišty ------------------------
        xyA = await insert_text(h, "live sirka", True)
        ok("A0) živý web: vložil se text s rámečkem", xyA is not None, f"bod={xyA}")
        await select_hand(h, xyA)
        m = json.loads(await h.ev(MEASURE))
        if not m.get("bar"):
            ok("A1) živý web: lišta úprav se otevřela", False, "lišta v DOM není (výběr rukou minul?)")
            return ok.report()
        print("   [A] " + json.dumps({k: m[k] for k in
              ("vw", "rows", "barW", "scrollW", "clientW", "nKids", "trashLeft",
               "trashRight", "trashOnScreen", "trashClickable")}, ensure_ascii=False))
        for k in m["kids"]:
            print(f"      {k['label']:16} x={k['left']:5}..{k['right']:5}"
                  + ("  PŘES LIŠTU" if k["overBar"] else "")
                  + (" / MIMO DISPLEJ" if k["overScreen"] else ""))
        ok("A1) živý web: lišta má DVA řádky (hlavní + řádek rámu)",
           m["bar"] and m["rows"] == 2, f"řádků={m.get('rows')}")
        ok("A2) živý web: obsah lišty se NEpřelévá (scrollWidth ≤ clientWidth)",
           m["bar"] and not m["overflowing"], f"{m.get('scrollW')} vs {m.get('clientW')}")
        ok("A3) živý web: žádné tlačítko nepřetéká vnitřek lišty",
           m["bar"] and not any(k["overBar"] for k in m["kids"]),
           "; ".join(f"{k['label']}→{k['right']}" for k in m["kids"] if k["overBar"]) or "-")
        ok("A4) živý web: 🗑 je uvnitř displeje a KLIKATELNÝ (elementFromPoint)",
           bool(m["bar"]) and m["trashOnScreen"] and m["trashClickable"],
           json.dumps({"koš": [m.get("trashLeft"), m.get("trashRight")],
                       "naDispleji": m.get("trashOnScreen"),
                       "klikatelny": m.get("trashClickable"), "vw": m.get("vw")}, ensure_ascii=False))

        # --- B) text BEZ rámečku (nejužší stav) ------------------------------
        xyB = await insert_text(h, "live bez ramu", False)
        ok("B0) živý web: vložil se text bez rámečku", xyB is not None, f"bod={xyB}")
        await select_hand(h, xyB)
        m2 = json.loads(await h.ev(MEASURE))
        if not m2.get("bar"):
            ok("B1) živý web: lišta úprav se otevřela (bez rámečku)", False, "lišta v DOM není")
            return ok.report()
        print("   [B] " + json.dumps({k: m2[k] for k in
              ("vw", "rows", "barW", "scrollW", "clientW", "nKids", "trashRight",
               "trashClickable")}, ensure_ascii=False))
        ok("B1) živý web: bez rámečku má lišta JEDEN řádek a vše se vejde",
           m2["bar"] and m2["rows"] == 1 and not m2["overflowing"],
           f"řádků={m2.get('rows')} {m2.get('scrollW')} vs {m2.get('clientW')}")
        ok("B2) živý web: 🗑 klikatelný i bez rámečku",
           bool(m2["bar"]) and m2["trashOnScreen"] and m2["trashClickable"],
           json.dumps({"klikatelny": m2.get("trashClickable")}, ensure_ascii=False))

        # --- C) koš na živém webu opravdu maže (end-to-end) ------------------
        n0 = await h.ev("""(async () => {
          const dbs = await indexedDB.databases();
          const n = (dbs.map(d=>d.name)||[]).find(x=>/noty|music|reader/i.test(x)); if (!n) return -1;
          const db = await new Promise(res => { const r = indexedDB.open(n);
            r.onsuccess=()=>res(r.result); r.onerror=()=>res(null); });
          if (!db) return -1;
          let c = 0;
          for (const s of [...db.objectStoreNames]) {
            const rows = await new Promise(res => {
              const q = db.transaction(s,'readonly').objectStore(s).getAll();
              q.onsuccess=()=>res(q.result); q.onerror=()=>res(null); });
            for (const row of (rows||[])) c += ((row&&row.items)||[]).length;
          }
          db.close(); return c; })()""", await_promise=True)
        await tap_el(h, ".edit-bar .eb-btn[title='Smazat']")
        await asyncio.sleep(1.0)
        n1 = await h.ev("""(async () => {
          const dbs = await indexedDB.databases();
          const n = (dbs.map(d=>d.name)||[]).find(x=>/noty|music|reader/i.test(x)); if (!n) return -1;
          const db = await new Promise(res => { const r = indexedDB.open(n);
            r.onsuccess=()=>res(r.result); r.onerror=()=>res(null); });
          if (!db) return -1;
          let c = 0;
          for (const s of [...db.objectStoreNames]) {
            const rows = await new Promise(res => {
              const q = db.transaction(s,'readonly').objectStore(s).getAll();
              q.onsuccess=()=>res(q.result); q.onerror=()=>res(null); });
            for (const row of (rows||[])) c += ((row&&row.items)||[]).length;
          }
          db.close(); return c; })()""", await_promise=True)
        ok("C1) živý web: ťuknutí na 🗑 prvek SMAŽE (end-to-end)", n1 == n0 - 1, f"{n0} -> {n1}")
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
