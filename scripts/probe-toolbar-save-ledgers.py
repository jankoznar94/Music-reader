#!/usr/bin/env python3
"""Sonda: nástroje v panelu (značky v řadě), tlačítko Uložit v liště, pomocné linky not.

Co měří:
  1. Tlačítko notových nástrojů se chová jako každé jiné tlačítko řady — po
     přepnutí na jiný nástroj se řádek ZAVŘE a svítí právě jedno tlačítko.
  2. Kategorie „Sdílet“ v anotačním panelu UŽ NENÍ; export má vlastní tlačítko
     s ikonou diskety v hlavní liště a otevírá vlastní panel.
  3. Nástroj Text neukazuje v panelu žádnou sekci Styl (barva je v jeho okně).
  4. Vložená nota umí pomocné linky: počet, strana, „nota v mezeře“ — a kreslí
     se v SVG (prohlížeč) se správným krokem (0,25 em) a přesah (0,30 em).

Spuštění (dev server 5173 + Chrome s CDP na 9223 musí běžet):
    export LD_LIBRARY_PATH="$HOME/.agent-browser/lib:$LD_LIBRARY_PATH"
    python3 scripts/probe-toolbar-save-ledgers.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harness", os.path.join(os.path.dirname(_here), "cdp-e2e-harness.py"))
h_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h_mod)

Harness = h_mod.Harness
make_pdf = h_mod.make_pdf
Check = h_mod.Check

APP = os.environ.get("APP_URL") or "http://localhost:5173/"


async def panel_state(h):
    return await h.ev("""(() => {
      const p = document.querySelector('.annot-panel');
      if (!p) return null;
      return {
        labels: [...p.querySelectorAll('.ap-cat-label')].map(x => x.textContent.trim()),
        toolsOn: [...p.querySelectorAll('.ap-tool.on')].map(x => (x.title || '').slice(0, 20)),
        notaRow: !!p.querySelector('.ap-nota-row'),
        colors: p.querySelectorAll('.ap-color').length,
        share: p.querySelectorAll('.ap-share-btn').length,
      };
    })()""")


async def click_tool(h, title_prefix):
    return await h.ev("""(() => {
      const b = [...document.querySelectorAll('.annot-panel .ap-tool')]
        .find(x => (x.title || '').startsWith(%s));
      if (!b) return 'missing';
      b.click();
      return 'ok';
    })()""" % json.dumps(title_prefix))


async def main():
    ok = Check()
    async with Harness(url=APP) as h:
        await h.open()
        await h.set_tablet()
        # ⚠️ NIKDY `reset_db()` (deleteDatabase) — v headless Chromu nechá
        # pending delete a VŠECHNA další `indexedDB.open` visí (naměřeno:
        # appka zůstane na „Načítám…“ a upload na „Nahrávám noty… 0 / 1“).
        # Otevřeme existující skladbu, případně jednu nahrajeme.
        await h.ev(h.expand_authors_js())
        if not await h.ev("document.querySelectorAll('li.song').length"):
            await h.set_file_input("input[type=file]", make_pdf(3))
            await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                            timeout=60, label="PDF upload")
            await h.ev(h.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=15,
                        label="song rows")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="open viewer")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="first page")
        await asyncio.sleep(1.0)
        await h.annot_toggle()
        await h.wait_for("!!document.querySelector('.annot-panel')", timeout=10, label="annot panel")

        st = await panel_state(h)
        ok("panel se otevřel", st is not None, str(st))

        # --- 1) značky jako součást řady nástrojů -----------------------------
        await click_tool(h, "Noty a značky")
        await asyncio.sleep(0.3)
        st = await panel_state(h)
        ok("klik na noty otevře řádek", st and st["notaRow"], str(st and st["notaRow"]))
        await click_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        st = await panel_state(h)
        ok("jiný nástroj řádek ZAVŘE", st and not st["notaRow"], str(st and st["notaRow"]))
        ok("svítí právě jedno tlačítko", st and len(st["toolsOn"]) == 1, str(st and st["toolsOn"]))
        ok("svítí tužka", st and st["toolsOn"] and "Tužka" in st["toolsOn"][0], str(st and st["toolsOn"]))

        # --- 2) Sdílet ven z panelu, tlačítko v liště -------------------------
        ok("panel už nemá kategorii Sdílet", st and "Sdílet" not in st["labels"], str(st and st["labels"]))
        ok("panel už nemá tlačítka exportu", st and st["share"] == 0, str(st and st["share"]))

        tb = await h.ev("""(() => {
          const b = [...document.querySelectorAll('.top-bar .tb-btn')]
            .find(x => (x.title || '').startsWith('Uložit a sdílet'));
          if (!b) return null;
          return { title: b.title, rect: b.getBoundingClientRect().toJSON() };
        })()""")
        ok("tlačítko Uložit je v hlavní liště", tb is not None, str(tb and tb["title"]))
        if tb:
            r = tb["rect"]
            ok("tlačítko je viditelné v liště (ne mimo displej)",
               r["width"] > 10 and r["top"] >= 0 and r["right"] <= 810, str(r))

        await h.ev("""(() => { const b = [...document.querySelectorAll('.top-bar .tb-btn')]
            .find(x => (x.title || '').startsWith('Uložit a sdílet')); b.click(); })()""")
        await asyncio.sleep(0.4)
        sp = await h.ev("""(() => { const p = document.querySelector('.share-panel');
            if (!p) return null;
            return { btns: [...p.querySelectorAll('.ap-share-btn')].map(b => b.innerText.trim()),
                     box: p.getBoundingClientRect().toJSON() }; })()""")
        ok("panel Uložit se otevřel", sp is not None)
        ok("panel má obě cesty exportu",
           sp and sp["btns"] == ["Vypálit PDF", "PDF + JSON"], str(sp and sp["btns"]))
        if sp:
            b = sp["box"]
            ok("panel se vejde na displej", b["left"] >= 0 and b["right"] <= 810, str(b))
        # vzájemné vylučování s anotací: otevřený panel Uložit anotaci vypnul,
        # takže klepnutí na ✏️ anotaci ZAPNE a panel Uložit zmizí.
        await h.annot_toggle()
        await asyncio.sleep(0.5)
        ok("anotace zavře panel Uložit",
           await h.ev("!document.querySelector('.share-panel')"))
        await h.wait_for("!!document.querySelector('.annot-panel')", timeout=10, label="annot back")

        # --- 3) Text bez barev ------------------------------------------------
        await click_tool(h, "Text (klávesnice)")
        await asyncio.sleep(0.3)
        st = await panel_state(h)
        ok("Text nemá v panelu barvy", st and st["colors"] == 0, str(st and st["colors"]))
        ok("Text nemá sekci Styl", st and "Styl" not in st["labels"], str(st and st["labels"]))

        # --- 4) Pomocné linky u vložené noty ---------------------------------
        await click_tool(h, "Noty a značky")
        await asyncio.sleep(0.3)
        await click_tool(h, "Vkládání not")
        await asyncio.sleep(0.3)
        p = await h.free_point(0.35, 0.65)
        ok("volný bod pro notu", p is not None, str(p))
        if p:
            await h.pen_tap(p["x"], p["y"])
            got = await h.wait_for("!!document.querySelector('.text-input-card')", timeout=8,
                                   label="okno noty")
            ok("okno noty se otevřelo", bool(got))
            # první dlaždice nabídky = celá nota
            tile = await h.ev("""(() => {
              const b = document.querySelector('.text-input-card .dyn-btn');
              if (!b) return 'missing';
              b.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerType: 'pen'}));
              return b.title;
            })()""")
            await asyncio.sleep(0.6)
            ok("nota se vložila (dlaždice)", tile not in (None, "missing"), str(tile))
            n_items = await h.ev("window.__barDev.annotations.value.items.length")
            ok("nota je v datech", n_items and n_items > 0, str(n_items))

            # pás úprav: řádek Linky → 2 čárky a Dolů
            rows = await h.ev("""(() => [...document.querySelectorAll('.edit-bar .eb-row')]
                .map(r => r.innerText.replace(/\\s+/g, ' ').trim()))()""")
            ok("pás úprav má řádek Linky",
               any(r.startswith("Linky") for r in rows), str(rows))
            # ⚠️ Pás úprav má pojistku proti zbloudilému klepnutí: první `click`
            # bez předchozího POLOŽENÍ v liště se spolkne (`editBarArmed`).
            # Sonda proto posílá pointerdown na lištu a teprve pak click na čip.
            clicked = await h.ev("""(() => {
              const bar = document.querySelector('.edit-bar');
              const row = [...document.querySelectorAll('.edit-bar .eb-row')]
                .find(r => r.innerText.trim().startsWith('Linky'));
              if (!row) return 'no-row';
              const chip = [...row.querySelectorAll('.eb-chip')].find(c => c.textContent.trim() === '2');
              if (!chip) return 'no-chip';
              bar.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
              chip.click();
              return 'ok';
            })()""")
            ok("přidány 2 pomocné linky", clicked == "ok", str(clicked))
            await asyncio.sleep(0.5)
            info = await h.ev("""(() => {
              const d = window.__barDev;
              const it = d.annotations.value.items.at(-1);
              const lines = [...document.querySelectorAll('.annot-layer line')]
                .filter(l => (l.getAttribute('stroke') || '') === (it.color || ''))
                .map(l => ({ y1: +l.getAttribute('y1'), y2: +l.getAttribute('y2'),
                             x1: +l.getAttribute('x1'), x2: +l.getAttribute('x2'),
                             sw: +l.getAttribute('stroke-width') }));
              return { it: { x: it.x, y: it.y, size: it.size, ledgers: it.ledgers,
                             side: it.ledgerSide, gap: it.ledgerGap }, lines };
            })()""")
            it, lines = info["it"], info["lines"]
            ok("data noty nesou linky", it["ledgers"] == 2, str(it))
            ok("kreslí se 2 linky", len(lines) == 2, str(len(lines)))
            if len(lines) == 2 and it["size"]:
                step = 0.25 * it["size"]
                half = 0.30 * it["size"]
                y0, y1 = lines[0]["y1"], lines[1]["y1"]
                ok("první linka jde hlavičkou",
                   abs(y0 - it["y"]) <= 0.6 and abs(lines[0]["y2"] - y0) <= 0.6, f"{y0} vs {it['y']}")
                ok("krok = 0,25 em", abs(abs(y1 - y0) - step) <= 1.0, f"{abs(y1-y0):.2f} vs {step:.2f}")
                ok("linky jdou DOLŮ", y1 > y0, f"{y0} -> {y1}")
                ok("přesah 0,30 em na každou stranu",
                   abs((lines[0]["x2"] - lines[0]["x1"]) / 2 - half) <= 1.0,
                   f"{(lines[0]['x2']-lines[0]['x1'])/2:.2f} vs {half:.2f}")

            # „Nota v mezeře" posune první linku o půl mezery
            await h.ev("""(() => {
              const bar = document.querySelector('.edit-bar');
              const row = [...document.querySelectorAll('.edit-bar .eb-row')]
                .find(r => r.innerText.trim().startsWith('Linky'));
              const chip = [...row.querySelectorAll('.eb-chip')]
                .find(c => c.textContent.trim() === 'Mezera');
              if (chip) {
                bar.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                chip.click();
              }
            })()""")
            await asyncio.sleep(0.5)
            gap = await h.ev("""(() => {
              const it = window.__barDev.annotations.value.items.at(-1);
              const lines = [...document.querySelectorAll('.annot-layer line')]
                .filter(l => (l.getAttribute('stroke') || '') === (it.color || ''))
                .map(l => +l.getAttribute('y1'));
              return { gap: it.ledgerGap, lines };
            })()""")
            ok("Mezera zapne půlmezerový posun", gap["gap"] is True, str(gap))
            if len(gap["lines"]) == 2 and it["size"]:
                off = gap["lines"][0] - it["y"]
                ok("první linka o půl mezery dál",
                   abs(off - 0.125 * it["size"]) <= 1.0, f"{off:.2f} vs {0.125*it['size']:.2f}")

    return ok.report()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
