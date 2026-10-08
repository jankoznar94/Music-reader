#!/usr/bin/env python3
"""STABILITA DOTYKŮ — jedna věc po druhé, N-krát.

Jan: „Doteky prstem i perem jsou občas nestabilní. Někdy je appka bere v potaz,
někdy ne. Je to tabletem, nebo nastavením aplikace?“

Odpověď se hledá takhle: posílat STEJNÝ podnět N-krát a počítat úspěšnost.
Když je 100 %, chyba je v doručování z tabletu; když je nižší, je v obsluze.

⚠️ Poučení z předchozích běhů (každé jedno zdržení):
  1. **CDP pero (`Input.dispatchMouseEvent{pointerType:'pen'}`) NEDORUČÍ
     `pointerdown`** → „pero nekreslí“ je artefakt testu. Pero se staví
     SYNTETICKÝMI `PointerEvent`y na `.annot-layer`.
  2. **Nezapisuj do testu data, která si pak sám zavazí cestu.** Vložený text
     zůstává na stránce a `free_xy` pak nenajde volné místo → měření se zastaví
     a hlásí nesmysly. Proto se text NIKDY nepotvrzuje (Zrušit) a tah se hned maže.
  3. **Před každou částí zkontroluj mód, který test potřebuje** (anotace ON/OFF),
     jiného chování se jinak nedočkáš.
  4. **Když test nic nezjistí, přiznej to** — prázdný výsledek není FAIL appky.

    NOTY_CDP=http://127.0.0.1:9247 NOTY_N=12 python3 scripts/probe-touch-reliability.py
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
  const l = document.querySelector('.annot-layer');
  if (!l) return 'no-layer';
  const mk = (t, p) => new PointerEvent(t, { bubbles: true, cancelable: true,
    pointerId: 9101, pointerType: 'pen', isPrimary: true, pressure: p,
    buttons: p ? 1 : 0, clientX: x, clientY: y });
  l.dispatchEvent(mk('pointerdown', 0.5));
  l.dispatchEvent(mk('pointerup', 0));
  return 'sent';
}"""

JS_PEN_STROKE = """([x0, y0, x1, y1]) => {
  const l = document.querySelector('.annot-layer');
  if (!l) return 'no-layer';
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


async def set_annot(h, want):
    for _ in range(4):
        if await annot_on(h) == bool(want):
            return True
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Anotace')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
    return False


async def use_tool(h, prefix):
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.title || '').startsWith(%s)); if (b) b.click(); })()"
               % json.dumps(prefix))
    await asyncio.sleep(0.4)


async def close_dialog(h, label="Zrušit"):
    """Zavři dialog SKUTEČNÝM dotykem (pointerdown na overlay + click) — dialog má
    pojistku `dialogArmed`, takže programové `.click()` správně NIC neudělá.
    Když se zavírání mine, dialog zůstane přes celou obrazovku (`position:fixed`)
    a další pokusy nemají na plátno cestu (test hlásí „nešlo změřit“)."""
    r = await h.ev("""(() => { const b = [...document.querySelectorAll('.ti-actions .jp-btn')]
      .find(x => (x.textContent||'').trim() === %s); if (!b) return 'missing';
      const rc = b.getBoundingClientRect();
      const o = { bubbles:true, cancelable:true, pointerId:777, pointerType:'touch',
                  clientX: rc.left + rc.width/2, clientY: rc.top + rc.height/2 };
      const ov = document.querySelector('.text-input-overlay');
      if (ov) { ov.dispatchEvent(new PointerEvent('pointerdown', o));
                ov.dispatchEvent(new MouseEvent('click', o)); }
      b.click(); return 'ok'; })()""" % json.dumps(label))
    await asyncio.sleep(0.5)
    still = await h.ev("!!document.querySelector('.text-input-overlay')")
    return r == 'ok' and not still


async def expand_panel(h):
    """Rozbal anotační panel (sbalený nemá tlačítka nástrojů v DOM)."""
    await h.ev("""(() => { const b = document.querySelector('.ap-collapse');
      if (!b) return 'no-toggle';
      if (!document.querySelector('.annot-panel .ap-cat')) b.click();
      return 'ok'; })()""")
    await asyncio.sleep(0.4)


async def page_nums(h):
    raw = await h.ev("(document.querySelector('.tb-page')||{}).textContent || ''")
    try:
        a, b = raw.split('/')
        return int(a.strip().split()[0]), int(b.strip().split()[0])
    except Exception:
        return 0, 0


async def collapse_panel(h):
    """Sbal anotační panel — rozbalený zakrývá velkou část plátna a `free_xy`
    pak nenajde volný bod (naměřeno: 11 z 12 pokusů „nešlo změřit“)."""
    await h.ev("""(() => { const b = document.querySelector('.ap-collapse');
      if (!b) return 'no-toggle';
      const open = document.querySelector('.annot-panel .ap-cat');
      if (open) b.click();
      return 'ok'; })()""")
    await asyncio.sleep(0.4)


async def free_xy(h):
    """Volný bod plátna — SKENUJE se, nebere se pevná mřížka bodů. Rozbalený panel
    i nasbírané anotace jinak seberou všechny zkoušené body."""
    raw = await h.ev("""(() => {
      const svg = document.querySelector('.annot-layer'); if (!svg) return null;
      const v = svg.getBoundingClientRect();
      const boxes = [...svg.querySelectorAll('g > text, g > path, g > rect, g > line')]
        .map(e => e.getBoundingClientRect());
      const near = (x, y, d) => boxes.some(r => r.width > 0 &&
        x > r.left - d && x < r.right + d && y > r.top - d && y < r.bottom + d);
      for (const d of [30.0, 20.0, 12.0]) {
        for (let y = v.top + 40; y < v.bottom - 40; y += 14) {
          for (let x = v.left + 24; x < v.right - 24; x += 14) {
            if (document.elementFromPoint(x, y) !== svg) continue;
            if (near(x, y, d)) continue;
            return {x, y};
          }
        }
      }
      return null; })()""")
    return (raw["x"], raw["y"]) if raw else None


async def clear_annots(h):
    """Ukliď anotace (tlačítko „Smazat všechny anotace“), ať se plocha nezaplní."""
    await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
      .find(x => (x.title || '').startsWith('Smazat všechny anotace'));
      if (b) b.click(); return true; })()""")
    await asyncio.sleep(0.4)
    # potvrď dialog
    await h.ev("(() => { const ok = [...document.querySelectorAll('button')]"
               ".find(x => /^(Smazat|OK)$/.test((x.textContent||'').trim()));"
               " if (ok) ok.click(); return true; })()")
    await asyncio.sleep(0.6)


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(8))
        await h.set_tablet()
        await set_annot(h, True)
        await use_tool(h, "Text")   # PRED sbalenim: sbaleny panel nema .ap-tool v DOM
        await collapse_panel(h)     # rozbaleny panel zakryva platno

        # ---------- A) pero položí text, N-krát (text se NEUKLÁDÁ) -------------
        hits, miss = 0, 0
        for i in range(N):
            xy = await free_xy(h)
            if not xy:
                miss += 1
                await clear_annots(h)
                continue
            await ev_args(h, JS_PEN_TAP, [xy[0], xy[1]])
            await asyncio.sleep(0.85)
            if await h.ev("!!document.querySelector('.text-input-overlay')"):
                hits += 1
                # Zrušit SKUTEČNÝM dotykem — jinak dialog zůstane přes celou
                # obrazovku a další pokusy nemají na plátno cestu (naměřeno).
                await close_dialog(h, "Zrušit")
            else:
                miss += 1
        done = hits + miss - (0 if miss == 0 else 0)
        ok(f"A) pero: dialog se otevřel ve VŠECH {N} pokusech", hits == N and miss == 0,
           f"otevřeno {hits}/{N}, nešlo změřit {miss}" if miss else f"otevřeno {hits}/{N}")

        # ---------- B) pero krátký tah se uloží, N-krát ------------------------
        await expand_panel(h)
        await use_tool(h, "Tužka")
        await collapse_panel(h)
        drawn, miss2 = 0, 0
        for i in range(N):
            before = await h.ev("document.querySelectorAll('.annot-layer g > path').length")
            xy = await free_xy(h)
            if not xy:
                miss2 += 1
                await clear_annots(h)
                continue
            await ev_args(h, JS_PEN_STROKE, [xy[0], xy[1], xy[0] + 70, xy[1] + 25])
            await asyncio.sleep(0.6)
            after = await h.ev("document.querySelectorAll('.annot-layer g > path').length")
            if after > before:
                drawn += 1
            else:
                miss2 += 1
        ok(f"B) pero: krátký tah se uložil ve VŠECH {N} pokusech",
           drawn == N, f"nakresleno {drawn}/{N}, nezměřeno {miss2}")

        # ---------- C) prst v okraji listuje, N-krát (anotace VYPNUTÁ) ---------
        await clear_annots(h)
        await set_annot(h, False)
        # NA PRVNI strance je levy okraj logicky no-op (neni kam couvat).
        await h.goto(2)
        await asyncio.sleep(0.6)
        geo = await h.ev("""(() => { const v = document.querySelector('.viewer');
          const r = v.getBoundingClientRect();
          const ew = parseFloat(getComputedStyle(v).getPropertyValue('--edge-w')) || 80;
          return { left: r.left, top: r.top, h: r.height, vwidth: r.width, ew }; })()""")
        flipped, miss3, notes = 0, 0, []
        for i in range(N):
            before = await h.ev("(document.querySelector('.tb-page')||{}).textContent || ''")
            # KAM to jde: na posledni strance je „dalsi“ no-op (falesny FAIL).
            cur, tot = await page_nums(h)
            right = cur < tot
            x = (geo["left"] + geo["vwidth"] - geo["ew"] * 0.5) if right \
                else (geo["left"] + geo["ew"] * 0.5)
            y = geo["top"] + geo["h"] * 0.5
            await h.finger_tap(x, y)
            await asyncio.sleep(0.9)
            after = await h.ev("(document.querySelector('.tb-page')||{}).textContent || ''")
            if after != before:
                flipped += 1
            else:
                miss3 += 1
        # kontrola, že test vůbec mířil do pruhu
        check = await h.ev("""(() => { const v = document.querySelector('.viewer');
          const r = v.getBoundingClientRect();
          const ew = parseFloat(getComputedStyle(v).getPropertyValue('--edge-w')) || 80;
          const x = %f, y = %f;
          const el = document.elementFromPoint(x, y);
          return { inViewer: !!(el && el.closest && el.closest('.viewer')),
                   localX: x - r.left, fromRight: r.right - x, ew }; })()"""
          % (geo["left"] + geo["vwidth"] - geo["ew"] * 0.5, geo["top"] + geo["h"] * 0.5))
        ok(f"C) prst v okraji otočil stránku ve VŠECH {N} pokusech", flipped == N,
           f"otočeno {flipped}/{N}, neotočilo {miss3} | klepáno {check['fromRight']:.1f} px "
           f"od PRAVÉHO okraje, pruh je {check['ew']:.1f} px | uvnitř čtečky={check['inViewer']}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
