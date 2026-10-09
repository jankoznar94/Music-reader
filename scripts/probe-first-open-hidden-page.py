#!/usr/bin/env python3
"""První otevření skladby nerespektuje odebrané stránky (Jan, Oct 2026).

Jan: „Při otevření skladby se nerespektují odstraněné stránky. Při listování je to
v pořádku, ale při prvním otevření skladby se normálně zobrazí i první stránka,
která má být smazána (vyřazena).“

PŘÍČINA: `currentPage` je inicializovaný na 0 (index do PDF) a `onMounted` ho
NIKDY nepřesune na první ZOBRAZENOU stránku — `switchSong()` to dělá
(`currentPage.value = visiblePages.value[0]`), `onMounted` ne. Když je 1. stránka
odebraná, počítadlo i pás miniatur pracují s `visiblePages` (správně), ale
vykresluje se stránka index 0 = odebraná. Při listování to spraví `gotoPage()`.

Sonda měří na REÁLNÉM obsahu canvasu, ne na tom, že je něco v bundle:
  1. otevři 6stránkovou skladbu → otisk canvasu pro stránku 1 a stránku 2
  2. odeber 1. stránku (jsme na ní) → počítadlo „1 / 5 (z 6)“
  3. zpět do knihovny → znovu otevři TUTEŽ skladbu (bez nového uploadu)
  4. hned po otevření: otisk canvasu musí být otisk stránky 2 (první zobrazené),
     NIKDY otisk stránky 1 (odebrané) — a `__navdbg().page` musí být 1

    scripts/run-probe-fresh.sh scripts/probe-first-open-hidden-page.py
"""
import asyncio
import importlib.util
import json
import os

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

# Otisk viditelného canvasu: FNV-1a přes pixely. Prázdný canvas (prostředek
# listování) vrací 0 — proto se při vzorkování rozlišuje „nic“ a „něco“.
HASH_JS = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas');
  if (!c || !c.width || !c.height) return 0;
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let h = 2166136261;
  for (let i = 0; i < d.length; i += 971) {   // řídký vzorek stačí na otisk
    h ^= d[i]; h = (h * 16777619) >>> 0;
  }
  return h;
})()
"""

DBG_JS = "JSON.stringify(window.__navdbg ? {page: window.__navdbg().page} : null)"


async def canvas_hash(h):
    return await h.ev(HASH_JS)


async def settled_hash(h, timeout=4.0, poll=0.15):
    """Otisk canvasu po ustálení (render je asynchronní). Vrací (otisk, posloupnost)."""
    seq, last, stable = [], None, 0
    waited = 0.0
    while waited < timeout:
        v = await canvas_hash(h)
        if v:
            seq.append(v)
            if v == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = v
        await asyncio.sleep(poll)
        waited += poll
    return last, seq


async def counter(h):
    return await h.ev("(document.querySelector('.tb-page') || {}).textContent.trim() || null")


async def back_to_library(h):
    await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
               ".find(x => (x.title||'')==='Zpět'); if (b) b.click(); return !!b; })()")
    await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                     timeout=15, label="knihovna")
    await asyncio.sleep(0.5)


async def reopen_song(h):
    # Skupiny si knihovna pamatuje (libraryState.openAuthors) — po návratu z prohlížeče
    # může být skupina UŽ rozbalená a klik na hlavičku by ji naopak zavřel.
    if not await h.ev("document.querySelectorAll('li.song').length > 0"):
        await h.ev(h.expand_authors_js())
    await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=10, label="autoři")
    await h.click(".song-name")
    await h.wait_for("!!document.querySelector('.tb-page')", timeout=30, label="prohlížeč")
    # Loading overlay zmizí až po prvním renderu — ale právě ten je předmětem
    # zkoumání, takže se čeká jen na jeho zmizení, ne na ustálení obsahu.
    await h.wait_for("!document.querySelector('.viewer-loading')", timeout=30, label="první stránka")


async def remove_current_page(h):
    await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
               ".find(x => (x.title||'').startsWith('Odebrat stránky')); if (b) b.click(); })()")
    await asyncio.sleep(0.6)
    clicked = await h.ev("""(() => {
      const b = [...document.querySelectorAll('.zp-btn')]
        .find(x => (x.title || '').startsWith('Odebrat tuto stránku'));
      if (!b) return false; b.click(); return true; })()""")
    await asyncio.sleep(0.9)
    await h.ev("(() => { const b = [...document.querySelectorAll('.zp-btn')]"
               ".find(x => /Zavřít/.test(x.textContent || '')); if (b) b.click(); })()")
    await asyncio.sleep(0.5)
    return clicked


async def main():
    ok = Check()
    async with Harness() as h:
        await h.set_tablet(800, 1280, 2)
        await h.open()
        await asyncio.sleep(1.0)
        await h.open_song(pdf=_m.make_pdf(6), pages=6)
        await h.set_tablet()

        # --- 1) otisky stránky 1 a stránky 2 (korektní cesta přes gotoPage) ---
        await h.goto(1)
        hash1, seq1 = await settled_hash(h)
        await h.goto(2)
        hash2, seq2 = await settled_hash(h)
        ok("otisk stránky 1 a 2 se liší (měření má vypovídací hodnotu)",
           bool(hash1) and bool(hash2) and hash1 != hash2,
           f"str1={hash1} str2={hash2}")

        # --- 2) odeber PRVNÍ stránku (jsme na ní) ---
        await h.goto(1)
        await asyncio.sleep(0.4)
        ok("1. stránka se odebrala", await remove_current_page(h))
        ctr = await counter(h)
        ok("počítadlo po odebrání: 1 / 5 (z 6)", ctr == "1 / 5 (z 6)", str(ctr))
        # Po odebrání stojíme na původní 2. stránce (první zobrazené) = otisk str. 2
        here, _ = await settled_hash(h)
        ok("po odebrání se zobrazuje stránka 2 (listování funguje)", here == hash2,
           f"canvas={here} očekáváno={hash2} (str.1={hash1})")

        # --- 3) zpět do knihovny a ZNOVU otevřít tutéž skladbu ---
        await back_to_library(h)
        await reopen_song(h)
        dbg = await h.ev(DBG_JS)
        page_now = (json.loads(dbg) or {}).get("page") if dbg else None
        first, seq = await settled_hash(h)
        ctr = await counter(h)
        print("   posloupnost otisků po otevření:", seq[:12], "…" if len(seq) > 12 else "")
        ok("PRVNÍ otevření: canvas neukazuje odebranou 1. stránku", first != hash1,
           f"canvas={first} str.1(odebraná)={hash1}")
        ok("PRVNÍ otevření: canvas ukazuje první ZOBRAZENOU stránku (2.)", first == hash2,
           f"canvas={first} str.2={hash2}")
        ok("PRVNÍ otevření: vnitřní stránka je index 1 (PDF str. 2)", page_now == 1,
           f"__navdbg().page={page_now}")
        ok("PRVNÍ otevření: počítadlo hlásí 1 / 5 (z 6)", ctr == "1 / 5 (z 6)", str(ctr))

    ok.report()


if __name__ == "__main__":
    asyncio.run(main())
