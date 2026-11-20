#!/usr/bin/env python3
"""Skoky 2. kolo: vzhled ZNAČKY CÍLE + prvky skoku jako objekty v okně Skoky.

Jan, 18. 11. 2026:
  * „Chtělo by to mít možnost customizovat i cílovou oblast. Když nebude žádná
    vložena, tak zkrátka jen skok skočí na danou stránku. Když cílová oblast
    (značka) bude umístěna na cílové stránce, tak se po skoku zvýrazní. Tato
    značka by se však měla dát různě upravit. Velikost, tvar, barva, atd.“
  * „Tlačítko pro skok a cílová značka by se měly dát po vytvoření snadno zase
    označit a upravit… Po kliknutí na tato tlačítka v okně pro Skoky appka sama
    skočí na stránku, kde se tlačítko/značka nachází, a rovnou ho označí.“

Co sonda ověřuje:
1. značka cíle má v panelu nastavení velikosti/šířky/výšky/tvaru/barvy/tloušťky
   a ULOŽÍ SE do dat skoku,
2. uložená geometrie se opravdu propíše do vykresleného rámečku (px, radius,
   barva, výplň),
3. pod každým skokem jsou dva zanořené objekty „Tlačítko“ a „Značka cíle“,
4. klepnutí na „Tlačítko“ skočí na jeho stránku a prvek OZNAČÍ (.selected),
5. označený prvek se dá táhnout po notách a nová pozice se uloží do DB,
6. totéž pro „Značku cíle“,
7. skok bez značky jen otevře cílovou stránku (žádný flash, žádný rámeček).

    NOTY_RESET_DB=1 python3 scripts/probe-jump-parts.py
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
RESET_DB = os.environ.get("NOTY_RESET_DB") == "1"


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

JS = "window.__barDev"


async def page(h):
    return (await h.page_text()).split("/")[0].strip()


async def panel_open(h):
    return bool(await h.ev("!!document.querySelector('[data-panel=\"jump\"]')"))


async def layer_point(h, fx, fy):
    """Bod na anotační vrstvě, který NENÍ pod plovoucím panelem."""
    return await h.ev("""(() => {
      const v = document.querySelector('.viewer').getBoundingClientRect();
      const x = v.left + v.width * %f;
      for (let d = 0; d <= 0.5; d += 0.03) {
        for (const f of [%f + d, %f - d]) {
          if (f < 0.3 || f > 0.95) continue;
          const y = v.top + v.height * f;
          const el = document.elementFromPoint(x, y);
          if (!el) continue;
          if (el.closest && el.closest('.jump-panel, .top-bar, .jump-strip, .jp-place-hint, .annot-nav')) continue;
          return {x, y};
        }
      }
      return null;
    })()""" % (fx, fy, fy))


async def tap_layer(h, fx, fy):
    p = await layer_point(h, fx, fy)
    if not p:
        return False
    await h.finger_tap(p["x"], p["y"])
    await asyncio.sleep(0.35)
    return True


async def db_jumps(h, song_id):
    return json.loads(await h.ev("""\
((songId) => new Promise((resolve) => {
  const q = indexedDB.open('noty-app');
  q.onsuccess = () => {
    const r = q.result.transaction('jumps', 'readonly').objectStore('jumps').get(songId);
    r.onsuccess = () => resolve(JSON.stringify(r.result ? r.result.items : []));
  };
}))(%s)""" % json.dumps(song_id)))


async def click_btn(h, text, panel='jump'):
    return await h.ev("""(() => {
      const b = [...document.querySelectorAll('[data-panel="%s"] .jp-btn')]
        .find(x => x.textContent.trim() === %s);
      if (b) b.click(); return !!b;
    })()""" % (panel, json.dumps(text)))


async def drag_rect(h, dx=26, dy=18):
    """Tažení označeného prvku: pointerdown uvnitř, move, up."""
    return await h.ev("""(() => {
      const sel = document.querySelector('.jump-on-btn.selected, .jump-target-mark.selected');
      if (!sel) return 'no-selected';
      const r = sel.getBoundingClientRect();
      const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
      const layer = document.querySelector('.annot-layer');
      const mk = (t, x, y, p) => new PointerEvent(t, {
        bubbles: true, cancelable: true, pointerId: 9301, pointerType: 'touch',
        isPrimary: true, pressure: p, buttons: p ? 1 : 0, clientX: x, clientY: y,
      });
      layer.dispatchEvent(mk('pointerdown', x0, y0, 0.5));
      for (let i = 1; i <= 4; i++) {
        layer.dispatchEvent(mk('pointermove', x0 + %d * i / 4, y0 + %d * i / 4, 0.5));
      }
      layer.dispatchEvent(mk('pointerup', x0 + %d, y0 + %d, 0));
      return 'ok';
    })()""" % (dx, dy, dx, dy))


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(reset=RESET_DB)
        await h.set_tablet(800, 1280, 2)
        song_id = await h.ev(f"{JS}.song.id")

        # --- 1. Skok se značkou cíle vytvořený přes UI ----------------------
        await h.ev("""(() => { const b = [...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title || '').startsWith('Vytvořit skok')); b.click(); return 1; })()""")
        await asyncio.sleep(0.5)
        ok("okno Skoků se otevřelo", await panel_open(h))

        await click_btn(h, "Start")
        await asyncio.sleep(0.3)
        p_start = await page(h)
        await h.goto(3)                       # cílová stránka = 3. stránka
        await asyncio.sleep(0.6)
        p_end = await page(h)
        await click_btn(h, "Konec")
        await asyncio.sleep(0.3)
        await h.ev(f"(() => {{ {JS}.jumpLabel.value = 'VIDE'; return 1; }})()")

        # tlačítko na noty: tři body (levý horní, levý spodní, pravý)
        await click_btn(h, "Umístit tlačítko na noty")
        await asyncio.sleep(0.4)
        for fx, fy in ((0.30, 0.62), (0.30, 0.78), (0.62, 0.78)):
            ok_t = await tap_layer(h, fx, fy)
            if not ok_t:
                ok("volný bod pro umístění tlačítka", False, f"{fx},{fy}")
        place = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumpPlace.value))()"))
        ok("tlačítko se umístilo na noty (3 body)", bool(place), json.dumps(place))

        # cíl na cílové stránce
        if await page(h) != p_end:
            await h.goto(3)
            await asyncio.sleep(0.6)
        await click_btn(h, "Označit cíl na stránce")
        await asyncio.sleep(0.4)
        ok("panel se při označování cíle schová", not await panel_open(h))
        await tap_layer(h, 0.40, 0.55)
        await asyncio.sleep(0.4)
        tm = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumpToMark.value))()"))
        ok("cíl se umístil na cílovou stránku", bool(tm) and tm.get("page") == 3, json.dumps(tm))

        # --- 2. Vzhled značky cíle ------------------------------------------
        ok("panel nabízí nastavení vzhledu značky",
           bool(await h.ev("!!document.querySelector('[data-panel=\"jump\"] [data-cfg=\"mark-color\"]')")))
        ok("panel nabízí tvary značky",
           bool(await h.ev("""[...document.querySelectorAll('[data-panel="jump"] .jp-btn.sm')]
             .some(b => b.textContent.trim() === 'Elipsa')""")))

        await click_btn(h, "Velká")
        await asyncio.sleep(0.2)
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn.sm')]
            .find(x => x.textContent.trim() === 'Elipsa'); b.click(); return 1; })()""")
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn.sm')]
            .find(x => x.textContent.trim() === '4'); b.click(); return 1; })()""")
        await h.ev("""(() => { const sw = document.querySelectorAll('[data-panel="jump"] [data-cfg="mark-color"] .jp-sw');
            sw[2].click(); return sw.length; })()""")      # 1. = „jako tlačítko“, 2. = akcent…
        await asyncio.sleep(0.3)
        cfg = json.loads(await h.ev(f"""(() => JSON.stringify({{
          w: {JS}.jumpMarkW.value, h: {JS}.jumpMarkH.value,
          shape: {JS}.jumpMarkShape.value, color: {JS}.jumpMarkColor.value,
          border: {JS}.jumpMarkBorder.value, fill: {JS}.jumpMarkFill.value }}))()"""))
        ok("vzhled značky jde v panelu nastavit", cfg["shape"] == "ellipse" and cfg["border"] == 4
           and cfg["w"] == 148, json.dumps(cfg))
        # náhled na stránce musí odpovídat okamžitě (ještě před uložením)
        prev = json.loads(await h.ev("""(() => { const el = document.querySelector('.jump-target-mark.preview');
          if (!el) return 'null';
          const c = getComputedStyle(el);
          return JSON.stringify({w: el.style.width, h: el.style.height, br: c.borderRadius,
            bd: c.borderWidth, bc: c.borderColor, bg: c.backgroundColor}); })()"""))
        ok("náhled značky má novou velikost", prev != "null" and prev["w"] != "", str(prev))

        await click_btn(h, "Uložit skok")
        await asyncio.sleep(0.8)
        j = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value))()"))
        ok("skok se uložil", len(j) == 1, json.dumps(j)[:200])
        if j:
            mk = j[0].get("toMark") or {}
            ok("značka cíle si nese velikost", mk.get("w") == 148 and mk.get("h") == 88, json.dumps(mk))
            ok("značka cíle si nese tvar", mk.get("shape") == "ellipse", str(mk.get("shape")))
            ok("značka cíle si nese barvu", mk.get("color") == "#2e8b57", str(mk.get("color")))
            ok("značka cíle si nese tloušťku", mk.get("border") == 4, str(mk.get("border")))
        db = await db_jumps(h, song_id)
        ok("vzhled značky je uložený i v IndexedDB",
           bool(db) and (db[0].get("toMark") or {}).get("shape") == "ellipse", json.dumps(db)[:200])

        # vykreslený rámeček
        rend = json.loads(await h.ev("""(() => { const el = document.querySelector('.jump-target-mark:not(.preview)');
          if (!el) return 'null';
          const c = getComputedStyle(el);
          return JSON.stringify({w: el.style.width, br: c.borderRadius, bd: c.borderTopWidth,
            bc: c.borderRightColor, bg: c.backgroundColor}); })()"""))
        ok("vykreslená značka je elipsa s tloušťkou 4",
           rend != "null" and rend["br"].startswith("50") and rend["bd"] == "4px", str(rend))
        ok("vykreslená značka má barvu a výplň",
           rend != "null" and rend["bc"] == "rgb(46, 139, 87)" and "rgba" in rend["bg"], str(rend))

        # --- 3. Prvky skoku jako objekty v okně Skoky -----------------------
        await h.ev("""(() => { const b = [...document.querySelectorAll('.tb-btn')]
            .find(x => (x.title || '').startsWith('Vytvořit skok')); b.click(); return 1; })()""")
        await asyncio.sleep(0.5)
        parts = json.loads(await h.ev("""(() => JSON.stringify(
          [...document.querySelectorAll('[data-panel="jump"] .jp-jump-card')].map(c => ({
            label: c.querySelector('.jp-item-label').textContent.trim(),
            parts: [...c.querySelectorAll('.jp-part')].map(p => p.querySelector('.jp-part-name').textContent.trim()
              + '|' + p.querySelector('.jp-part-where').textContent.trim()),
          })))) ()"""))
        ok("pod skokem jsou dva zanořené objekty", bool(parts) and len(parts[0]["parts"]) == 2, json.dumps(parts, ensure_ascii=False))
        if parts:
            ok("objekty se jmenují Tlačítko a Značka cíle",
               parts[0]["parts"][0].startswith("Tlačítko") and parts[0]["parts"][1].startswith("Značka cíle"),
               str(parts[0]["parts"]))
            ok("u objektů je vidět, na které stránce leží",
               "str. 3" in parts[0]["parts"][0] and "str. 3" in parts[0]["parts"][1],
               str(parts[0]["parts"]))

        # --- 4. Klepnutí na „Tlačítko“ = skoč tam a označ -------------------
        await h.goto(1)
        await asyncio.sleep(0.6)
        ok("jsme na jiné stránce než tlačítko", (await page(h)) != "3")
        await h.ev("""(() => { document.querySelectorAll('[data-panel="jump"] .jp-part')[0].click(); return 1; })()""")
        await asyncio.sleep(1.0)
        sel = json.loads(await h.ev(f"(() => JSON.stringify({{sel: {JS}.jumpSel.value, page: {JS}.currentPage.value}}))()"))
        ok("klepnutí na Tlačítko skočilo na jeho stránku", str(sel["page"] + 1) == "3", json.dumps(sel))
        ok("tlačítko je označené", bool(await h.ev("!!document.querySelector('.jump-on-btn.selected')")))
        ok("lištová nápověda k označenému prvku je vidět",
           bool(await h.ev("!!document.querySelector('.jp-place-hint')")))

        before = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value[0].place))()"))
        ok("tažení označeného tlačítka proběhlo", (await drag_rect(h, 30, 22)) == "ok")
        await asyncio.sleep(0.5)
        after = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value[0].place))()"))
        ok("tlačítko se posunulo",
           after["x"] != before["x"] and after["y"] != before["y"], f'{before} -> {after}')
        db = await db_jumps(h, song_id)
        ok("nová pozice tlačítka je v DB",
           bool(db) and db[0]["place"]["x"] == after["x"], json.dumps(db[0].get("place")))

        # --- 5. Klepnutí na „Značku cíle“ -----------------------------------
        await h.goto(1)
        await asyncio.sleep(0.5)
        await h.ev("""(() => { document.querySelectorAll('[data-panel="jump"] .jp-part')[1].click(); return 1; })()""")
        await asyncio.sleep(1.0)
        ok("klepnutí na Značku cíle skočilo na její stránku", (await page(h)) == "3", await page(h))
        ok("značka cíle je označená", bool(await h.ev("!!document.querySelector('.jump-target-mark.selected')")))
        tm0 = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value[0].toMark))()"))
        ok("tažení označené značky proběhlo", (await drag_rect(h, -22, 16)) == "ok")
        await asyncio.sleep(0.5)
        tm1 = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value[0].toMark))()"))
        ok("značka se posunula a neztratila vzhled",
           tm1["x"] != tm0["x"] and tm1["shape"] == "ellipse" and tm1["w"] == 148,
           f'{tm0} -> {tm1}')
        db = await db_jumps(h, song_id)
        ok("nová pozice značky je v DB",
           bool(db) and db[0]["toMark"]["x"] == tm1["x"], json.dumps(db[0].get("toMark")))

        # --- 6. Skok BEZ značky: jen otevře stránku -------------------------
        await h.ev("""(() => { const b = [...document.querySelectorAll('[data-panel="jump"] .jp-btn')]
            .find(x => x.textContent.trim() === '✕' && x.title === 'Zrušit cíl'); b.click(); return 1; })()""")
        await asyncio.sleep(0.3)
        await click_btn(h, "Uložit změny")
        await asyncio.sleep(0.8)
        j = json.loads(await h.ev(f"(() => JSON.stringify({JS}.jumps.value))()"))
        ok("skok je bez značky (toMark = null)", bool(j) and j[0].get("toMark") is None, json.dumps(j)[:160])

        await h.goto(1)
        await asyncio.sleep(0.6)
        await h.ev(f"(() => {{ {JS}.goJump({JS}.jumps.value[0]); return 1; }})()")
        await asyncio.sleep(1.0)
        ok("skok bez značky otevřel cílovou stránku", (await page(h)) == "3", await page(h))
        ok("bez značky se nic nerozsvěcuje",
           not await h.ev("!!document.querySelector('.jump-target-mark')"))

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
