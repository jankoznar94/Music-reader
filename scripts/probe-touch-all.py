#!/usr/bin/env python3
"""STABILITA DOTYKŮ V CELÉ APLIKACI — každý běžný úkon N-krát.

Jan: „Doteky prstem i perem jsou občas nestabilní. Někdy je appka bere v potaz,
někdy ne. Rozhodně z toho nemám 100% plynulý a spolehlivý pocit. Je to tabletem,
nebo nastavením aplikace?“ — a upřesnil, že to myslí OBECNĚ, na všechny doteky
v appce, ne jen na vkládání textu.

Metoda: stejný podnět N-krát, počítá se úspěšnost. 100 % = chyba je v doručování
z tabletu; méně = chyba je v obsluze v aplikaci.

Měřené úkony (každý N-krát):
  A) klepnutí na tlačítko v horní liště (přepínač anotací) — tam i zpět
  B) volba nástroje v anotačním panelu (Tužka / Guma)
  C) pero: krátký tah se uloží
  D) pero: klepnutí na plátno otevře dialog textu
  E) prst: klepnutí v okraji otočí stránku (střídavě podle toho, kam to jde)
  F) prst: dvouprstý pinch změní zoom

⚠️ Poučení z předchozích běhů (každé jedno zdržení):
  1. CDP pero (`dispatchMouseEvent{pointerType:'pen'}`) NEDORUČÍ `pointerdown`
     → pero se staví SYNTETICKÝMI `PointerEvent`y na `.annot-layer`.
  2. **Sbalený anotační panel NEMÁ tlačítka nástrojů v DOM** → nástroj se musí
     vybrat PŘED sbalením, jinak se tiše nevybere a test měří jiný nástroj.
  3. **Dialog má pojistku `dialogArmed`** → programové `.click()` na „Zrušit“
     správně NIC neudělá; dialog zůstane přes celou obrazovku a další pokusy
     nemají na plátno cestu. Zavírej SKUTEČNÝM dotykem (pointerdown + click).
  4. **Na poslední stránce je „další“ no-op** a na první zase „předchozí“ →
     směr listování volej podle aktuálního čísla stránky.
  5. **Když úkon nemá co měřit, přiznej to** — prázdný výsledek není FAIL appky.

    NOTY_CDP=http://127.0.0.1:9247 NOTY_N=12 python3 scripts/probe-touch-all.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9247")
N = int(os.environ.get("NOTY_N", "12"))


def _load():
    p = os.path.expanduser("~/noty-app/cdp-e2e-harness.py")
    s = importlib.util.spec_from_file_location("hh", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_m = _load()
_m.CDP_HTTP = CDP
Harness, Check = _m.Harness, _m.Check

JS_PEN_TAP = """([x, y]) => {
  const l = document.querySelector('.annot-layer'); if (!l) return 'no-layer';
  const mk = (t, p) => new PointerEvent(t, { bubbles: true, cancelable: true,
    pointerId: 9101, pointerType: 'pen', isPrimary: true, pressure: p,
    buttons: p ? 1 : 0, clientX: x, clientY: y });
  l.dispatchEvent(mk('pointerdown', 0.5)); l.dispatchEvent(mk('pointerup', 0));
  return 'sent';
}"""

JS_PEN_STROKE = """([x0, y0, x1, y1]) => {
  const l = document.querySelector('.annot-layer'); if (!l) return 'no-layer';
  const mk = (t, x, y, p) => new PointerEvent(t, { bubbles: true, cancelable: true,
    pointerId: 9102, pointerType: 'pen', isPrimary: true, pressure: p,
    buttons: p ? 1 : 0, clientX: x, clientY: y });
  l.dispatchEvent(mk('pointerdown', x0, y0, 0.5));
  for (let i = 1; i <= 8; i++)
    l.dispatchEvent(mk('pointermove', x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * i / 8, 0.5));
  l.dispatchEvent(mk('pointerup', x1, y1, 0));
  return 'sent';
}"""


async def ev_args(h, js, args):
    return await h.ev("(%s)(%s)" % (js, json.dumps(args)))


async def annot_on(h):
    return await h.ev("""(() => { const b = [...document.querySelectorAll('.tb-btn')]
      .find(x => (x.title || '').startsWith('Anotace'));
      return b ? b.classList.contains('on') : null; })()""")


async def page_nums(h):
    raw = await h.ev("(document.querySelector('.tb-page')||{}).textContent || ''")
    try:
        a, b = raw.split('/')
        return int(a.strip().split()[0]), int(b.strip().split()[0])
    except Exception:
        return 0, 0


async def tap_in_toolbar(h):
    """Klepni na tlačítko anotací v liště SKUTEČNÝM dotykem prstu."""
    pt = await h.ev("""(() => { const b = [...document.querySelectorAll('.tb-btn')]
      .find(x => (x.title || '').startsWith('Anotace')); if (!b) return null;
      const r = b.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()""")
    if not pt:
        return False
    await h.finger_tap(pt["x"], pt["y"])
    await asyncio.sleep(0.7)
    return True


async def panel_open(h):
    return await h.ev("!!document.querySelector('.annot-panel .ap-cat')")


async def set_panel(h, want):
    for _ in range(4):
        if await panel_open(h) == bool(want):
            return True
        await h.ev("""(() => { const b = document.querySelector('.ap-collapse');
          if (b) b.click(); return true; })()""")
        await asyncio.sleep(0.5)
    return False


async def pick_tool(h, prefix):
    """Vyber nástroj KLIKEM (nástroj není „doteková" akce, jen nastavení režimu).
    POZOR: panel je v DOM jen v ANOTAČNÍM modu — bez něj není co kliknout."""
    for _ in range(3):
        if await annot_on(h):
            break
        await tap_in_toolbar(h)
    await set_panel(h, True)
    # ⚠️ Panel se rozbaluje ASYNCHRONNĚ (Vue překreslí DOM až po kliknutí na
    # „Rozbalit“). Bez čekání se hledá tlačítko v DOM, který ještě neexistuje,
    # a nástroj se tiše nevybere (naměřeno: „vybráno: None“).
    for _ in range(5):
        if await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
          .find(x => (x.title || '').startsWith(%s)); return !!b; })()""" % json.dumps(prefix)):
            break
        await asyncio.sleep(0.4)
    r = await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
      .find(x => (x.title || '').startsWith(%s));
      if (!b) return 'missing'; b.click(); return 'ok'; })()""" % json.dumps(prefix))
    await asyncio.sleep(0.5)
    return r == 'ok'


async def tool_on(h):
    return await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool.on')]
      .map(x => x.title); return JSON.stringify(b); })()""")


async def close_dialog(h, label="Zrušit"):
    """Zavři dialog SKUTEČNÝM dotykem (dialog má pojistku `dialogArmed`).

    ⚠️ Pojistka se dá VYPÁLIT JEN JEDNOU. Dřív tu byl navíc syntetický
    `MouseEvent('click')` na překryv — ten pojistku spotřeboval, takže klepnutí
    na Zrušit (`b.click()`) našlo `dialogArmed === false`, překryv ho zablokoval
    a dialog zůstal otevřený. Sonda to hlásila jako „pero neotevřelo dialog“
    (naměřeno: 1/12), i když se dialog otevřel POKAŽDÉ — jen se nedal zavřít.
    Správně: `pointerdown` na překryvu (ozbrojí) + `b.click()` (spotřebuje).
    """
    r = await h.ev("""(() => { const b = [...document.querySelectorAll('.ti-actions .jp-btn')]
      .find(x => (x.textContent||'').trim() === %s); if (!b) return 'missing';
      const rc = b.getBoundingClientRect();
      const o = { bubbles:true, cancelable:true, pointerId:777, pointerType:'touch',
                  clientX: rc.left + rc.width/2, clientY: rc.top + rc.height/2 };
      const ov = document.querySelector('.text-input-overlay');
      if (ov) ov.dispatchEvent(new PointerEvent('pointerdown', o));
      b.click(); return 'ok'; })()""" % json.dumps(label))
    await asyncio.sleep(0.5)
    return r == "ok" and not await h.ev("!!document.querySelector('.text-input-overlay')")


async def free_xy(h):
    raw = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y, d) => boxes.some(r => r.width > 0 &&
        x > r.left - d && x < r.right + d && y > r.top - d && y < r.bottom + d);
      for (const d of [30.0, 20.0, 12.0]) {
        for (let y = v.top + 40; y < v.bottom - 40; y += 14)
          for (let x = v.left + 24; x < v.right - 24; x += 14) {
            if (document.elementFromPoint(x, y) !== svg) continue;
            if (near(x, y, d)) continue;
            return {x, y};
          }
      }
      return null; })()""")
    return (raw["x"], raw["y"]) if raw else None


async def clear_annots(h):
    """Ukliď anotace PŘES IndexedDB, ne přes tlačítko v UI.

    ⚠️ Tlačítko „Smazat všechny anotace“ otevírá nativní `confirm()` — ten
    v headless prohlížeči BLOKUJE stránku (žádná událost nedorazí a sonda
    umře na timeout; naměřeno: běh se zasekl po části C). `Page.handleJavaScriptDialog`
    je potřeba volat zvlášť, takže je čistší anotace smazat mimo UI.
    """
    await h.ev("""(async () => {
      const dbs = await indexedDB.databases();
      const n = (dbs.map(d => d.name) || []).find(x => /noty|music|reader/i.test(x));
      if (!n) return 'no-db';
      const db = await new Promise((res, rej) => {
        const r = indexedDB.open(n);
        r.onsuccess = () => res(r.result); r.onerror = () => rej(String(r.error)); });
      const stores = [...db.objectStoreNames].filter(s => s !== 'songs');
      for (const s of stores) {
        const rows = await new Promise(res => {
          const q = db.transaction(s, 'readonly').objectStore(s).getAll();
          q.onsuccess = () => res(q.result); q.onerror = () => res([]); });
        for (const row of rows) {
          if (row && Array.isArray(row.items) && row.items.length) {
            row.items = [];
            await new Promise(res => {
              const q = db.transaction(s, 'readwrite').objectStore(s).put(row);
              q.onsuccess = () => res(1); q.onerror = () => res(0); });
          }
        }
      }
      db.close();
      return 'ok'; })()""", await_promise=True)
    await asyncio.sleep(0.3)


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(8))
        await h.set_tablet()
        await asyncio.sleep(0.4)

        # ---------- A) tlačítko v horní liště (tam i zpět) ---------------------
        good = 0
        for i in range(N):
            want = (i % 2 == 0)
            if not await tap_in_toolbar(h):
                continue
            if await annot_on(h) == want:
                good += 1
        ok(f"A) prst: tlačítko v horní liště reagovalo ve VŠECH {N} pokusech",
           good == N, f"zareagovalo {good}/{N}")

        # ---------- B) volba nástroje v panelu ---------------------------------
        # panel je jen v anotacnim modu
        if not await annot_on(h):
            await tap_in_toolbar(h)
        good_b = 0
        for i in range(N):
            prefix = "Tužka" if i % 2 == 0 else "Guma"
            if not await pick_tool(h, prefix):
                continue
            on = await h.ev("""(() => { const b = document.querySelector('.ap-tool.on');
              return b ? b.title : null; })()""")
            if on and on.startswith(prefix):
                good_b += 1
        ok(f"B) prst: volba nástroje v panelu prošla ve VŠECH {N} pokusech",
           good_b == N, f"prošlo {good_b}/{N}")

        # ---------- C) pero: krátký tah se uloží ------------------------------
        if not await annot_on(h):
            await tap_in_toolbar(h)
        await pick_tool(h, "Tužka")
        await set_panel(h, False)      # sbalený panel nekryje plátno
        drawn = 0
        for i in range(N):
            before = await h.ev("document.querySelectorAll('.annot-layer g > path').length")
            xy = await free_xy(h)
            if not xy:
                continue
            await ev_args(h, JS_PEN_STROKE, [xy[0], xy[1], xy[0] + 70, xy[1] + 25])
            await asyncio.sleep(0.55)
            if await h.ev("document.querySelectorAll('.annot-layer g > path').length") > before:
                drawn += 1
        ok(f"C) pero: krátký tah se uložil ve VŠECH {N} pokusech", drawn == N,
           f"nakresleno {drawn}/{N}")

        # ---------- D) pero: klepnutí na plátno otevře dialog textu -----------
        # `clear_annots` znovu načte stránku, takže se musí znovu nastavit mód
        # I nástroj — jinak pero kreslí do staré/nesprávné vrstvy a dialog
        # neotevře (naměřeno: 1/12).
        if not await annot_on(h):
            await tap_in_toolbar(h)
        await pick_tool(h, "Text")
        # Stav nastroje se cte, dokud je panel ROZBALENY: sbaleny panel nema
        # tlacitka v DOM, takze `.ap-tool.on` je pak None a kontrola lze.
        tool_now = await h.ev("""(() => { const b = document.querySelector('.ap-tool.on');
          return b ? b.title : null; })()""")
        await set_panel(h, False)
        ok("D0) před měřením je vybraný nástroj Text",
           bool(tool_now) and str(tool_now).startswith("Text"), f"vybráno: {tool_now}")
        opened = 0
        for i in range(N):
            xy = await free_xy(h)
            if not xy:
                continue
            await ev_args(h, JS_PEN_TAP, [xy[0], xy[1]])
            await asyncio.sleep(0.8)
            if await h.ev("!!document.querySelector('.text-input-overlay')"):
                opened += 1
                await close_dialog(h, "Zrušit")
        ok(f"D) pero: klepnutí na plátno otevřelo dialog ve VŠECH {N} pokusech",
           opened == N, f"otevřelo {opened}/{N}")

        # ---------- E) prst: klepnutí v okraji otočí stránku ------------------
        await set_panel(h, True)
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Anotace')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        await h.goto(2)
        await asyncio.sleep(0.6)
        geo = await h.ev("""(() => { const v = document.querySelector('.viewer');
          const r = v.getBoundingClientRect();
          const ew = parseFloat(getComputedStyle(v).getPropertyValue('--edge-w')) || 80;
          return { left: r.left, top: r.top, h: r.height, vwidth: r.width, ew }; })()""")
        flipped = 0
        for i in range(N):
            before, _ = await page_nums(h)
            cur, tot = await page_nums(h)
            x = (geo["left"] + geo["vwidth"] - geo["ew"] * 0.5) if cur < tot \
                else (geo["left"] + geo["ew"] * 0.5)
            await h.finger_tap(x, geo["top"] + geo["h"] * 0.5)
            await asyncio.sleep(0.85)
            after, _ = await page_nums(h)
            if after != before:
                flipped += 1
        ok(f"E) prst: klepnutí v okraji otočilo stránku ve VŠECH {N} pokusech",
           flipped == N, f"otočilo {flipped}/{N}")

        # ---------- F) prst: dvouprstý pinch změní zoom -----------------------
        z0 = await h.ev("""(() => { const s = document.querySelector('.stage');
          return s ? s.getBoundingClientRect().width : null; })()""")
        changed = 0
        cx = geo["left"] + geo["vwidth"] / 2
        cy = geo["top"] + geo["h"] / 2
        for i in range(N):
            before = await h.ev("""(() => { const s = document.querySelector('.stage');
              return s ? Math.round(s.getBoundingClientRect().width) : null; })()""")
            await h.touch("touchStart", [(cx - 60, cy, 12), (cx + 60, cy, 12)])
            for k in range(1, 7):
                await h.touch("touchMove", [(cx - 60 - k * 14, cy, 12), (cx + 60 + k * 14, cy, 12)])
                await asyncio.sleep(0.02)
            await h.touch("touchEnd", [])
            await asyncio.sleep(0.5)
            after = await h.ev("""(() => { const s = document.querySelector('.stage');
              return s ? Math.round(s.getBoundingClientRect().width) : null; })()""")
            if before is not None and after is not None and after != before:
                changed += 1
            # vrať zoom zpět, ať se nestrhne strop
            await h.ev("(document.querySelector('.tb-btn[title^=\"Vycentrovat\"]')||{}).click && "
                       "document.querySelector('.tb-btn[title^=\"Vycentrovat\"]').click()")
            await asyncio.sleep(0.4)
        ok(f"F) prst: dvouprstý pinch změnil zoom ve VŠECH {N} pokusech",
           changed == N, f"změnil {changed}/{N} | výchozí šířka stage={z0}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
