#!/usr/bin/env python3
"""Sonda nástroje ZNAČKY (posuvky, ozdoby, artikulace) — dev server.

Ověřuje celý životní cyklus nové značky na notách:
  1) dlaždice v panelu (nástroj Značky) + dialog má tři sekce a správné dlaždice
  2) klepnutí na dlaždici (perem) vloží SPRÁVNÝ SMuFL kód — a to pro každou rodinu
  3) dialog otevíraný z gesta samo nic nevloží (stejná past jako u dynamiky)
  4) značka se uloží do IndexedDB i s klíčem (ne jen „nějaký glyf")
  5) rukou (nástroj Upravit) ji lze přemístit
  6) guma ji smaže

Klíčové: dlaždice se hledá přes document.elementFromPoint (sken mřížky) a klepe se
na CELOČÍSELNÉ souřadnice — dispatchnutý tap dorazí se souřadnicemi zaokrouhlenými
na celá čísla a na zlomkovém středu může spadnout za hranici dlaždice.
"""
import asyncio
import importlib.util
import json

_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", "/home/martin_fabian/noty-app/cdp-e2e-harness.py")
_h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h)
Harness, Check, make_pdf = _h.Harness, _h.Check, _h.make_pdf

# klíč -> očekávaný SMuFL kód (musí odpovídat MARK_GROUPS v Prohlizec.vue)
KEYS = {
    "b": 0xE260, "odr": 0xE261, "k": 0xE262, "bb": 0xE264, "kk": 0xE263,
    "trylek": 0xE566, "obal": 0xE567, "mord": 0xE56D,
    "ferm": 0xE4C0, "cez": 0xE4D1, "dech": 0xE4CE,
    "akc": 0xE4A0, "stacc": 0xE4A2, "ten": 0xE4A4,
}


async def glyphs(h):
    return await h.ev("(() => [...document.querySelectorAll('.annot-layer text')]"
                      ".map(t => t.textContent.codePointAt(0)))()")


async def dialog_state(h):
    return await h.ev("""(() => {
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      return {
        label: (card.querySelector('.ti-label') || {}).textContent || '',
        sections: [...card.querySelectorAll('.mark-sec-label')].map(e => e.textContent.trim()),
        tiles: [...card.querySelectorAll('.mark-sec .dyn-btn')].map(b => b.title),
        tiles_n: card.querySelectorAll('.mark-sec .dyn-btn').length
      };
    })()""")


async def pick_tool(h, prefix):
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.title || '').startsWith(%s)); if (b) b.click(); })()"
               % json.dumps(prefix))
    await asyncio.sleep(0.4)


async def tile_point(h, title):
    """Bod na dlaždici značky nalezený PŘES elementFromPoint, zaokrouhlený na celá čísla."""
    return await h.ev("""(() => {
      const want = %s;
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      const seen = new Set();
      for (let y = Math.ceil(r.top); y < r.bottom; y++) {
        for (let x = Math.ceil(r.left); x < r.right; x++) {
          const el = document.elementFromPoint(x, y);
          const hit = el && el.closest ? el.closest('.mark-sec .dyn-btn') : null;
          if (!hit || hit.title !== want) continue;
          // potvrď, že i na ZAOKROUHLENÉM bodě vrací tentýž prvek
          const el2 = document.elementFromPoint(x, y);
          if (el2 && el2.closest && el2.closest('.mark-sec .dyn-btn')?.title === want) {
            const k = x + ',' + y;
            if (!seen.has(k)) { seen.add(k); return [x, y]; }
          }
        }
      }
      return null;
    })()""" % json.dumps(title))


async def open_dialog(h):
    for _ in range(8):
        p = await h.free_point()
        if not p:
            continue
        await h.pen_stroke(p["x"], p["y"], p["x"] + 2, p["y"] + 2)
        await asyncio.sleep(0.8)
        if await h.ev("!!document.querySelector('.text-input-overlay')"):
            return p
    return None


async def dismiss(h):
    if not await h.ev("!!document.querySelector('.text-input-overlay')"):
        return True
    pt = await h.ev("""(() => {
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      for (let y = Math.ceil(r.top); y < r.bottom; y++)
        for (let x = Math.ceil(r.left); x < r.right; x++) {
          const el = document.elementFromPoint(x, y);
          const b = el && el.closest ? el.closest('.jp-btn') : null;
          if (b && /Zru/i.test(b.textContent || '')) return [x, y];
        }
      return null; })()""")
    if not pt:
        return False
    await h.pen_tap(pt[0], pt[1])
    await asyncio.sleep(0.6)
    return not await h.ev("!!document.querySelector('.text-input-overlay')")


async def placed_items(h):
    """Přečti anotace, které appka skutečně zapsala (hook na IDB put)."""
    return await h.ev("window.__marks || []")


async def install_writer_hook(h):
    await h.ev("""(() => {
      if (window.__marksHooked) return true;
      window.__marksHooked = true;
      window.__marks = [];
      const orig = IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put = function (val, key) {
        try {
          if (this.name === 'annotations' && val && val.items) {
            const m = val.items.filter(x => x.tool === 'mark')
              .map(x => ({ page: x.page, text: x.text, size: x.size,
                           x: Math.round(x.x), y: Math.round(x.y) }));
            if (m.length) window.__marks = m;
          }
        } catch (e) {}
        return orig.apply(this, arguments);
      };
      return true;
    })()""")


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()               # NEJDŘÍV navigace — na about:blank nemá indexedDB origin
        await h.set_tablet()
        await h.reset_db()
        await h.open_song(pdf=make_pdf(6))
        await h.annot_toggle()
        await install_writer_hook(h)

        # --- 1) nástroj a dialog ---
        await pick_tool(h, "Značky")
        ok("nástroj Značky se zapne",
           bool(await h.ev("(() => [...document.querySelectorAll('.ap-tool')]"
                           ".some(x => (x.title||'').startsWith('Značky') && x.classList.contains('on')))()")))

        p = await open_dialog(h)
        ok("dialog značky se po položení pera otevře", bool(p))
        d = await dialog_state(h)
        if d:
            ok("dialog se jmenuje Značka", d["label"] == "Značka", f"label={d['label']!r}")
            ok("dialog má tři sekce", d["sections"] == ["Posuvky", "Ozdoby", "Drobnosti"],
               f"sekrece={d['sections']}")
            ok("dialog nabízí 16 dlaždic", d["tiles_n"] == 16, f"n={d['tiles_n']}")
            ok("sekce Posuvky má béčko, odrážku, křížek",
               all(t in d["tiles"] for t in ("béčko", "odrážka", "křížek")), f"{d['tiles']}")
        else:
            ok("dialog značky má obsah", False, "karta nenalezena")
        await dismiss(h)

        # --- 2) samovolné vložení (past zabloudilého kliku) ---
        auto = []
        for i in range(4):
            before = await glyphs(h)
            p = await open_dialog(h)
            if not p:
                ok(f"umístění #{i+1}: dialog se otevřel", False, "neotevřel se")
                continue
            after = await glyphs(h)
            new = [g for g in after if g not in before]
            auto += new
            ok(f"umístění #{i+1}: dialog zůstal a sám nic nevložil",
               bool(await h.ev("!!document.querySelector('.text-input-overlay')")) and not new,
               f"nové={['U+%04X' % g for g in new]}")
            await dismiss(h)
            await pick_tool(h, "Značky")
        ok("žádná samovolná značka", auto == [], f"samovolně {['U+%04X' % g for g in auto]}")

        # --- 3) každá rodina vloží SPRÁVNÝ kód ---
        for key in ("b", "odr", "k", "ferm", "trylek", "mord", "stacc"):
            await pick_tool(h, "Značky")
            p = await open_dialog(h)
            if not p:
                ok(f"dialog pro '{key}'", False, "neotevřel se")
                continue
            before = await glyphs(h)
            pt = await tile_point(h, {
                "b": "béčko", "odr": "odrážka", "k": "křížek", "ferm": "fermata (koruna)",
                "trylek": "trylek", "mord": "mordent", "stacc": "staccato"}[key])
            if not pt:
                ok(f"dlaždice '{key}' dosažitelná", False, "bod nenalezen")
                await dismiss(h)
                continue
            await h.pen_tap(pt[0], pt[1])
            await asyncio.sleep(0.7)
            new = [g for g in await glyphs(h) if g not in before]
            ok(f"volba '{key}' vloží U+{KEYS[key]:04X}", new == [KEYS[key]],
               f"vloženo {['U+%04X' % g for g in new]} (bod {pt})")

        # --- 4) uloženo i klíč, ne jen glyf ---
        await asyncio.sleep(0.6)
        saved = await placed_items(h)
        keys_saved = sorted({s["text"] for s in saved})
        ok("značky jsou uložené i s klíčem",
           all(k in KEYS for k in keys_saved) and len(saved) >= 6,
           f"uloženo {len(saved)}: {keys_saved}")

        # --- 5) přesun rukou ---
        await pick_tool(h, "Upravit")
        await asyncio.sleep(0.4)
        await h.ev("(() => { const t = document.querySelector('.annot-layer text');"
                   " if (t) t.dispatchEvent(new PointerEvent('pointerdown',"
                   "   {bubbles:true, cancelable:true, clientX: 0, clientY: 0})); })()")
        # ruka: klepni na střed posledního vykresleného glyfu, pak ho přetáhni
        pos = await h.ev("""(() => {
          const ts = [...document.querySelectorAll('.annot-layer text')];
          if (!ts.length) return null;
          const r = ts[ts.length - 1].getBoundingClientRect();
          return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
        })()""")
        moved = None
        if pos:
            before_items = await placed_items(h)
            await h.pen_tap(pos[0], pos[1])
            await asyncio.sleep(0.4)
            sel = await h.ev("!!document.querySelector('.annot-selected')")
            ok("ruka vybere značku (rámeček)", bool(sel))
            await h.pen_stroke(pos[0], pos[1], pos[0] + 40, pos[1] + 30, steps=6)
            await asyncio.sleep(0.6)
            after_items = await placed_items(h)
            moved = None
            for a in after_items:
                for b in before_items:
                    if a["text"] == b["text"] and (a["x"] != b["x"] or a["y"] != b["y"]):
                        moved = (b, a)
            ok("ruka značku přemístí", bool(moved),
               f"před={before_items[-1] if before_items else None} "
               f"po={after_items[-1] if after_items else None}")

        # --- 6) guma ---
        await pick_tool(h, "Guma")
        await asyncio.sleep(0.3)
        n_before = await h.ev("document.querySelectorAll('.annot-layer text').length")
        pos2 = await h.ev("""(() => {
          const ts = [...document.querySelectorAll('.annot-layer text')];
          if (!ts.length) return null;
          const r = ts[ts.length - 1].getBoundingClientRect();
          return [Math.round(r.left + r.width/2), Math.round(r.top + r.height/2)];
        })()""")
        if pos2:
            await h.pen_stroke(pos2[0] - 20, pos2[1], pos2[0] + 20, pos2[1], steps=10)
            await asyncio.sleep(0.6)
            n_after = await h.ev("document.querySelectorAll('.annot-layer text').length")
            ok("guma značku smaže", n_after < n_before, f"{n_before} -> {n_after}")
        else:
            ok("guma značku smaže", False, "žádný glyf na stránce")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
