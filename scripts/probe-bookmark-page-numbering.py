#!/usr/bin/env python3
"""Číslo záložky se musí posunout s odebranými stránkami (Jan, Oct 2026).

Jan: „Je možnost některé stránky odstranit. Tím se počítadlo stránek posune.
Co se ale neposouvá je číslování stránek u záložek.“

PŘÍČINA: lišta záložek počítala číslo jako `withOffset(b.page + 1)` — tedy přímo
index do PDF, bez přechodu na pořadí ZOBRAZENÝCH stránek. Počítadlo stránek
i seznam skoků jdou přes `dispPage()`, záložky ne, takže se rozešly.

Sonda ověřuje na skutečném scénáři:
  1. vloží 6stránkovou skladbu, na 5. stránce založí záložku → hlásí „5“
  2. odebere 2. stránku (PŘED záložkou) → záložka musí hlásit „4“,
     počítadlo na stejné stránce taky „4“ (obojí se musí shodovat)
  3. klepnutí na záložku pořád skočí na SPRÁVNOU stránku (ne na sousední)
  4. vrátí stránku zpět → záložka hlásí zase „5“
  5. posun číslování (+2) → záložka i počítadlo se posunou spolu

    NOTY_CDP=http://127.0.0.1:9242 python3 scripts/probe-bookmark-page-numbering.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")


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


async def tap_el(h, sel, hold_ms=70):
    pt = await h.ev("""(() => {
      const sel = %s;
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      for (let y = Math.floor(r.top); y <= Math.ceil(r.bottom); y += 2)
        for (let x = Math.floor(r.left); x <= Math.ceil(r.right); x += 2) {
          const hit = document.elementFromPoint(x, y);
          if (hit && (hit === el || (hit.closest && hit.closest(sel) === el))) return [x + 0.5, y + 0.5];
        }
      return null;
    })()""" % json.dumps(sel))
    if not pt:
        return False
    await h.touch("touchStart", [(pt[0], pt[1], 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.6)
    return True


async def counter(h):
    """Počítadlo na horní liště: 'X / Y (z Z)'."""
    return await h.ev("(document.querySelector('.tb-page') || {}).textContent.trim() || null")


async def strip_numbers(h):
    """Čísla v liště záložek (co uživatel vidí)."""
    return await h.ev("""(() => [...document.querySelectorAll('.bookmark-strip .bk-num')]
        .map(e => e.textContent.trim()))()""")


async def strip_title(h):
    return await h.ev("(document.querySelector('.bookmark-strip .bookmark-btn') || {}).title || null")


async def page_of(h):
    """Aktuální stránka jako index do PDF (z __navdbg v DEV)."""
    raw = await h.ev("JSON.stringify(window.__navdbg ? {page: window.__navdbg().page} : null)")
    return json.loads(raw) if raw else {}


async def make_bookmark(h, label="Coda"):
    await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
               ".find(x => (x.title || '').startsWith('Přidat záložku')); if (b) b.click(); })()")
    await asyncio.sleep(0.5)
    ok_open = await h.ev("!!document.querySelector('.jp-input')")
    if not ok_open:
        return False
    await h.set_value(".jp-input", label)
    await tap_el(h, ".jp-btn.primary")
    await asyncio.sleep(0.7)
    return True


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=_m.make_pdf(6))
        await h.set_tablet()

        # --- 1) na 5. stránce založ záložku ---
        await h.goto(5)
        p = await page_of(h)
        ok("1) jsme na 5. stránce PDF", p.get("page") == 4, json.dumps(p))
        ok("1b) záložka se založila", await make_bookmark(h, "Coda"), "panel se neotevřel")
        nums = await strip_numbers(h)
        ctr = await counter(h)
        ok("2) záložka na 5. stránce hlásí „5“ a počítadlo taky",
           nums == ["5"] and ctr.startswith("5 /"), f"záložky={nums} počítadlo='{ctr}'")

        # --- 2) odeber 2. stránku (PŘED záložkou) ---
        await h.goto(2)
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Odebrat stránky')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        removed = await h.ev("""(() => {
          const b = [...document.querySelectorAll('.zp-btn')]
            .find(x => (x.title || '').startsWith('Odebrat tuto stránku'));
          if (!b) return false; b.click(); return true; })()""")
        await asyncio.sleep(0.8)
        await h.ev("(() => { const b = [...document.querySelectorAll('.zp-btn')]"
                   ".find(x => /Zavřít/.test(x.textContent || '')); if (b) b.click(); })()")
        await asyncio.sleep(0.5)
        ok("3) 2. stránka se odebrala", removed, "tlačítko nenalezeno")

        # --- 3) na 5. stránce (index 4 → zobrazená 4.) musí obojí hlásit „4“ ---
        # POZOR: dialog „Přejít na stránku“ zadává číslo ZOBRAZENÉ stránky, takže
        # po odebrání 2. stránky znamená „4“ index 4 v PDF (před odebráním to bylo
        # „5“). Cílit proto na „4“, jinak sonda srovnává různé stránky.
        await h.goto(4)
        await asyncio.sleep(0.7)
        nums = await strip_numbers(h)
        ctr = await counter(h)
        title = await strip_title(h)
        p = await page_of(h)
        ok("4) ZÁLOŽKA SE POSUNULA: hlásí „4“ (dřív držela „5“)",
           nums == ["4"], f"záložky={nums}")
        ok("4b) záložka a počítadlo se SHODUJÍ (jsme na téže stránce)",
           ctr.startswith("4 /") and nums == ["4"] and p.get("page") == 4,
           f"záložky={nums} počítadlo='{ctr}' page={p.get('page')}")
        ok("4c) i tooltip záložky ukazuje posunuté číslo",
           title is not None and "4" in title, f"title={title!r}")

        # --- 4) klepnutí na záložku skočí na SPRÁVNOU stránku ---
        await h.goto(1)
        await asyncio.sleep(0.5)
        await tap_el(h, ".bookmark-strip .bookmark-btn")
        await asyncio.sleep(0.8)
        p = await page_of(h)
        ok("5) klepnutí na záložku skočí na původní 5. stránku PDF",
           p.get("page") == 4, f"page={p.get('page')} (čekáno index 4)")
        ok("5b) počítadlo po skoku hlásí „4“", (await counter(h)).startswith("4 /"),
           await counter(h))

        # --- 5) vrácení stránky zpět ---
        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title || '').startsWith('Odebrat stránky')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        restored = await h.ev("""(() => {
          const b = [...document.querySelectorAll('.zp-btn')]
            .find(x => (x.title || '').startsWith('Vrátit odebrané stránky'));
          if (!b || b.disabled) return false; b.click(); return true; })()""")
        await asyncio.sleep(0.9)
        await h.ev("(() => { const b = [...document.querySelectorAll('.zp-btn')]"
                   ".find(x => /Zavřít/.test(x.textContent || '')); if (b) b.click(); })()")
        await asyncio.sleep(0.5)
        nums = await strip_numbers(h)
        ok("6) po vrácení stránky záložka hlásí zase „5“", restored and nums == ["5"],
           f"vráceno={restored} záložky={nums}")

        # --- 6) posun číslování se musí projevit u obojího ---
        # POZOR: panel pro odebrání stránek je JEN pro odebrání; posun číslování
        # bydlí v něm taky, ale `goto` (i jiné panely) ho zavírá — takže se po
        # každé navigaci musí otevřít znovu.
        await h.goto(5)
        await asyncio.sleep(0.6)
        for _ in range(2):
            await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                       ".find(x => (x.title || '').startsWith('Odebrat stránky')); if (b) b.click(); })()")
            await asyncio.sleep(0.5)
            await h.ev("(() => { const b = [...document.querySelectorAll('.zp-btn')]"
                       ".find(x => (x.title || '').startsWith('Posunout číslování o 1 výš'));"
                       " if (b) b.click(); })()")
            await asyncio.sleep(0.4)
            await h.ev("(() => { const b = [...document.querySelectorAll('.zp-btn')]"
                       ".find(x => /Zavřít/.test(x.textContent || '')); if (b) b.click(); })()")
            await asyncio.sleep(0.4)
        nums = await strip_numbers(h)
        ctr = await counter(h)
        ok("7) posun číslování (+2) se projeví u záložky i počítadla",
           nums == ["6"] and ctr.startswith("6 /"), f"záložky={nums} počítadlo='{ctr}'")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
