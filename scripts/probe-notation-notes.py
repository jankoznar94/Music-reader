#!/usr/bin/env python3
"""Sonda nástroje VKLÁDÁNÍ NOT (notové hodnoty + pomlky) — dev server.

Ověřuje celý životní cyklus vložené noty:
  1) tlačítko nástroje v panelu + dialog se dvěma sekcemi a 14 dlaždicemi
  2) SUBSET FONTU: každý kód se skutečně měří fontem NotyDyn (chybějící glyf by
     spadl do záložního písma a šířka by neseděla s metrikami v kódu)
  3) velikost noty PŘED vložením: ± mění náhled i vloženou notu, volba se pamatuje
  4) klepnutí na dlaždici (perem) vloží SPRÁVNÝ SMuFL kód — pro každou hodnotu
  5) dialog otevíraný z gesta sám nic nevloží (stejná past jako u dynamiky)
  6) uložen je klíč, barva i velikost
  7) RÁMEČEK RUKY I HIT-TEST SEDÍ NA OTISK NOTY — měřeno Z PIXELŮ snímku:
     obrysové meze glyfu, takže musí být vidět i nožička, ne jen hlavička
  8) nota přežije reload, ruka ji přemístí, guma smaže

⚠️ Nota se kreslí barvou pera; sonda si proto v panelu vybere ČERVENOU
(#c0392b), aby se otisk v pixelovém měření dal spolehlivě odlišit od textu PDF
i od zlatého rámečku výběru. Noty se umisťují do VZÁJEMNĚ VZDÁLENÝCH bodů —
kdyby se slévaly na jedno místo, měření otisku z pixelů by míchalo sousedy.
"""
import asyncio
import base64
import importlib.util
import io
import json
import os

import numpy as np
from PIL import Image

_CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", "/home/martin_fabian/noty-app/cdp-e2e-harness.py")
_h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h)
_h.CDP_HTTP = _CDP
Harness, Check, make_pdf = _h.Harness, _h.Check, _h.make_pdf

TOOL_TITLE = "Vkládání not"
RED = "#c0392b"

# klíč -> (očekávaný SMuFL kód, popisek dlaždice, šířka glyfu v em z fontu)
NOTES = {
    "cela":       (0xE1D2, "celá nota", 0.4590),
    "pulova_h":   (0xE1D3, "půlová nota (nožička nahoru)", 0.3410),
    "pulova_d":   (0xE1D4, "půlová nota (nožička dolů)", 0.3410),
    "ctvrt_h":    (0xE1D5, "čtvrťová nota (nožička nahoru)", 0.3320),
    "ctvrt_d":    (0xE1D6, "čtvrťová nota (nožička dolů)", 0.3320),
    "osm_h":      (0xE1D7, "osminová nota (nožička nahoru)", 0.5660),
    "osm_d":      (0xE1D8, "osminová nota (nožička dolů)", 0.3320),
    "sestn_h":    (0xE1D9, "šestnáctinová nota (nožička nahoru)", 0.5810),
    "sestn_d":    (0xE1DA, "šestnáctinová nota (nožička dolů)", 0.3320),
    "poml_cela":  (0xE4E3, "pomlka celá", 0.2830),
    "poml_pul":   (0xE4E4, "pomlka půlová", 0.2830),
    "poml_ctvrt": (0xE4E5, "pomlka čtvrťová", 0.2700),
    "poml_osm":   (0xE4E6, "pomlka osminová", 0.2500),
    "poml_sestn": (0xE4E7, "pomlka šestnáctinová", 0.3200),
}
# Obrysové meze VŠECH hodnot (x0, x1, y0, y1 v em) — musí odpovídat NOTE_GROUPS
# v Prohlizec.vue; sonda z nich počítá, jak má rámeček výběru vypadat.
BOXES = {
    "cela":       (0.0000, 0.4590, -0.1370, 0.1360),
    "pulova_h":   (0.0000, 0.3410, -0.1450, 0.8750),
    "pulova_d":   (0.0000, 0.3410, -0.8750, 0.1450),
    "ctvrt_h":    (0.0000, 0.3320, -0.1410, 0.8750),
    "ctvrt_d":    (0.0000, 0.3320, -0.8750, 0.1410),
    "osm_h":      (0.0000, 0.5660, -0.1380, 0.8730),
    "osm_d":      (0.0000, 0.3320, -0.8820, 0.1410),
    "sestn_h":    (0.0000, 0.5810, -0.1380, 0.8730),
    "sestn_d":    (0.0000, 0.3320, -0.8830, 0.1410),
    "poml_cela":  (0.0000, 0.2820, -0.1350, 0.0090),
    "poml_pul":   (0.0000, 0.2820, -0.0020, 0.1420),
    "poml_ctvrt": (0.0010, 0.2700, -0.3750, 0.3730),
    "poml_osm":   (0.0000, 0.2470, -0.2510, 0.1740),
    "poml_sestn": (0.0000, 0.3200, -0.5000, 0.1790),
}
# Kolik pixelů na jednotku vrstvy (měřítko čtečky) — pro přepočet mezí rámečku.
async def layer_scale(h):
    return await h.ev("(() => { const m = document.querySelector('.annot-layer')"
                      ".getScreenCTM(); return m ? Math.hypot(m.a, m.b) : 1; })()")


# Který klíč patří kterému <text> (pořadí prvků = pořadí uložených anotací).
async def glyph_keys(h):
    cps = await h.ev("(() => [...document.querySelectorAll('.annot-layer text')]"
                     ".map(t => t.textContent.codePointAt(0)))()")
    by_cp = {v[0]: k for k, v in NOTES.items()}
    return [(by_cp.get(cp), cp) for cp in (cps or [])]


async def glyphs(h):
    return await h.ev("(() => [...document.querySelectorAll('.annot-layer text')]"
                      ".map(t => t.textContent.codePointAt(0)))()")


async def pick_tool(h, prefix):
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => (x.title || '').startsWith(%s)); if (b) b.click(); })()"
               % json.dumps(prefix))
    await asyncio.sleep(0.4)


async def pick_red(h):
    """Barva pera = červená (#c0392b) — druhá v paletě pera (viz PEN_COLORS)."""
    await h.ev("(() => { const cs = [...document.querySelectorAll('.ap-color')];"
               " if (cs[1]) cs[1].click(); return true; })()")
    await asyncio.sleep(0.25)
    return await h.ev("(() => { const cs = [...document.querySelectorAll('.ap-color')];"
                      " return cs[1] ? cs[1].classList.contains('on') : false; })()")


async def free_points(h, n, min_dist=95):
    """N vzdušných bodů na anotační vrstvě, od sebe dál než min_dist.

    Proč ne `free_point()` z harnessu: ta vrací VŽDY PRVNÍ trefu svého gridu, takže
    by všechny noty vznikly na jednom místě a měření otisku z pixelů by míchalo
    sousedy.
    """
    cand = await h.ev("""(() => {
      const v = document.querySelector('.viewer').getBoundingClientRect();
      const out = [];
      for (let fy = 0.30; fy <= 0.92; fy += 0.06) {
        for (let fx = 0.22; fx <= 0.80; fx += 0.06) {
          const x = Math.round(v.left + v.width * fx);
          const y = Math.round(v.top + v.height * fy);
          const el = document.elementFromPoint(x, y);
          if (el && el.classList && el.classList.contains('annot-layer')) out.push([x, y]);
        }
      }
      return out;
    })()""")
    picked = []
    for p in cand or []:
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= min_dist ** 2 for q in picked):
            picked.append(p)
        if len(picked) >= n:
            break
    return picked


async def tile_point(h, title):
    """Bod na dlaždici noty přes elementFromPoint, zaokrouhlený na celá čísla."""
    return await h.ev("""(() => {
      const want = %s;
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const r = card.getBoundingClientRect();
      for (let y = Math.ceil(r.top); y < r.bottom; y++) {
        for (let x = Math.ceil(r.left); x < r.right; x++) {
          const el = document.elementFromPoint(x, y);
          const hit = el && el.closest ? el.closest('.mark-sec .dyn-btn') : null;
          if (!hit || hit.title !== want) continue;
          const el2 = document.elementFromPoint(x, y);
          if (el2 && el2.closest && el2.closest('.mark-sec .dyn-btn')?.title === want)
            return [x, y];
        }
      }
      return null;
    })()""" % json.dumps(title))


async def dialog_state(h):
    return await h.ev("""(() => {
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      return {
        label: (card.querySelector('.ti-label') || {}).textContent || '',
        sections: [...card.querySelectorAll('.mark-sec-label')].map(e => e.textContent.trim()),
        tiles: [...card.querySelectorAll('.mark-sec .dyn-btn')].map(b => ({
                 title: b.title, cp: (b.textContent || '').codePointAt(0) || 0 })),
        size_val: parseInt((card.querySelector('.ti-size-val') || {}).textContent || '0', 10),
        preview_px: card.querySelector('.ti-size-aa')
                    ? parseFloat(getComputedStyle(card.querySelector('.ti-size-aa')).fontSize) : 0,
        warn: (card.querySelector('.ti-warn') || {}).textContent || '',
      };
    })()""")


async def open_dialog(h, at=None):
    """Umístí prvek perem na daný bod a počká na dialog."""
    pts = [at] if at else await free_points(h, 1)
    if not pts:
        return None
    p = pts[0]
    await h.pen_stroke(p[0], p[1], p[0] + 2, p[1] + 2)
    await asyncio.sleep(0.8)
    return p if await h.ev("!!document.querySelector('.text-input-overlay')") else None


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


async def plus_button_point(h):
    return await h.ev("""(() => {
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const bs = [...card.querySelectorAll('.ti-size-btn')];
      if (bs.length < 2) return null;
      const r = bs[bs.length - 1].getBoundingClientRect();
      return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
    })()""")


async def end_edit(h):
    """Ukončí výběr tlačítkem ✓ v liště úprav.

    Musí to být SKUTEČNÝ klik (souřadnice + pero), ne `el.click()` — lišta má
    pojistku proti zbloudilé události: přijme jen klepnutí, jemuž předcházelo
    POLOŽENÍ uvnitř lišty.
    """
    pt = await h.ev("""(() => {
      const b = document.querySelector('.eb-btn.done');
      if (!b) return null;
      const r = b.getBoundingClientRect();
      return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
    })()""")
    if pt:
        await h.pen_tap(pt[0], pt[1])
        await asyncio.sleep(0.35)
    return not await h.ev("!!document.querySelector('.eb-btn.done')")


async def install_writer_hook(h):
    await h.ev("""(() => {
      if (window.__notesHooked) return true;
      window.__notesHooked = true;
      window.__notes = [];
      const orig = IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put = function (val, key) {
        try {
          if (this.name === 'annotations' && val && val.items) {
            const m = val.items.filter(x => x.tool === 'note')
              .map(x => ({ page: x.page, text: x.text, size: Math.round(x.size),
                           fill: (x.color || '').toLowerCase(),
                           x: Math.round(x.x), y: Math.round(x.y) }));
            if (m.length) window.__notes = m;
          }
        } catch (e) {}
        return orig.apply(this, arguments);
      };
      return true;
    })()""")


async def saved_notes(h):
    return await h.ev("window.__notes || []")


async def font_widths(h):
    expect = {k: v[0] for k, v in NOTES.items()}
    return await h.ev("""(async () => {
      const expect = %s;
      await document.fonts.load('100px NotyDyn');
      const cx = document.createElement('canvas').getContext('2d');
      cx.font = '100px NotyDyn';
      const out = {};
      for (const k of Object.keys(expect))
        out[k] = cx.measureText(String.fromCodePoint(expect[k])).width;
      return out;
    })()""" % json.dumps(expect), await_promise=True)


async def text_box(h, idx=-1):
    return await h.ev("""(() => {
      const ts = [...document.querySelectorAll('.annot-layer text')];
      const t = ts[ts.length + %d];
      if (!t) return null;
      const r = t.getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height,
               size: Number(t.getAttribute('font-size') || 0) };
    })()""" % idx)


async def frame_box(h):
    return await h.ev("""(() => {
      const r = document.querySelector('.annot-selected rect');
      if (!r) return null;
      const b = r.getBoundingClientRect();
      return { x: b.left, y: b.top, w: b.width, h: b.height };
    })()""")


async def shot_ink(h, box, dsf=2, pad=20):
    """Bbox ČERVENÝCH pixelů (otisk noty) v okolí prvku — v CSS px."""
    shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
    img = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")
    x0 = max(0, int((box["x"] - pad) * dsf)); y0 = max(0, int((box["y"] - pad) * dsf))
    x1 = int((box["x"] + box["w"] + pad) * dsf); y1 = int((box["y"] + box["h"] + pad) * dsf)
    crop = np.asarray(img.crop((x0, y0, x1, y1))).astype(int)
    r, g, b = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    mask = (r - g > 60) & (r - b > 60)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return {"x": (x0 + xs.min()) / dsf, "y": (y0 + ys.min()) / dsf,
            "w": (xs.max() + 1 - xs.min()) / dsf, "h": (ys.max() + 1 - ys.min()) / dsf}


async def main():
    ok = Check()
    async with Harness(url=_h.APP_URL) as h:
        await h.open()
        await h.set_tablet()
        await h.reset_db()
        await h.open_song(pdf=make_pdf(6))
        await h.annot_toggle()
        await install_writer_hook(h)
        dsf = await h.ev("window.devicePixelRatio")

        # --- 1) nástroj a dialog ------------------------------------------------
        ok("tlačítko nástroje je v panelu",
           bool(await h.ev("(() => [...document.querySelectorAll('.ap-tool')]"
                           ".some(x => (x.title||'').startsWith(%s)))()" % json.dumps(TOOL_TITLE))))
        await pick_tool(h, TOOL_TITLE)
        ok("nástroj se zapne (kolečko svítí)",
           bool(await h.ev("(() => [...document.querySelectorAll('.ap-tool')]"
                           ".some(x => (x.title||'').startsWith(%s) && x.classList.contains('on')))()"
                           % json.dumps(TOOL_TITLE))))
        icon = await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                          ".find(x => (x.title||'').startsWith(%s));"
                          " return b ? (b.textContent||'').codePointAt(0)||0 : 0; })()"
                          % json.dumps(TOOL_TITLE))
        ok("ikona nástroje je glyf noty z fontu", icon == NOTES["ctvrt_h"][0],
           f"ikona U+{icon:04X}, čekáno U+{NOTES['ctvrt_h'][0]:04X}")

        pts = await free_points(h, 24)
        ok("na stránce je dost vzdušných míst pro noty", len(pts) >= 16, f"bodů {len(pts)}")
        reds = await pick_red(h)
        ok("paleta pera je nastavená na červenou", bool(reds))

        p = await open_dialog(h, pts[0] if pts else None)
        ok("dialog noty se po položení pera otevře", bool(p))
        d = await dialog_state(h)
        if d:
            ok("dialog se jmenuje Nota", d["label"] == "Nota", f"label={d['label']!r}")
            ok("dialog má sekce Noty a Pomlky", d["sections"] == ["Noty", "Pomlky"],
               f"sekrece={d['sections']}")
            ok("dialog nabízí 14 dlaždic", len(d["tiles"]) == 14, f"n={len(d['tiles'])}")
            want = {v[1]: v[0] for v in NOTES.values()}
            bad = [(t["title"], "U+%04X" % t["cp"]) for t in d["tiles"]
                   if want.get(t["title"]) != t["cp"]]
            ok("každá dlaždice nese svůj kód", not bad, f"špatně: {bad}")
        else:
            ok("dialog noty má obsah", False, "karta nenalezena")

        # --- 2) subset fontu: každý kód se měří fontem NotyDyn ------------------
        w = await font_widths(h)
        bad_w = []
        for k, (cp, _lbl, adv) in NOTES.items():
            got = w.get(k)
            if got is None or abs(got - adv * 100) > 2:
                bad_w.append((k, hex(cp), got, round(adv * 100, 1)))
        ok("všechny noty a pomlky jsou v nasazeném fontu (šířky sedí)",
           not bad_w, f"mimo: {bad_w}")

        # --- 3) velikost PŘED vložením -----------------------------------------
        size0 = d["size_val"] if d else 0
        pplus = await plus_button_point(h)
        if pplus:
            await h.pen_tap(pplus[0], pplus[1])
            await h.pen_tap(pplus[0], pplus[1])
            await asyncio.sleep(0.4)
        d2 = await dialog_state(h)
        ok("tlačítko + zvětší notu (2 kroky po 3 px)", bool(d2) and d2["size_val"] == size0 + 6,
           f"{size0} -> {d2['size_val'] if d2 else '?'}")
        ok("náhled noty ukazuje zvolenou velikost", bool(d2) and abs(d2["preview_px"] - d2["size_val"]) < 0.6,
           f"náhled {d2['preview_px'] if d2 else '?'} px vs volba {d2['size_val'] if d2 else '?'}")
        chosen = d2["size_val"] if d2 else 0
        pt = await tile_point(h, NOTES["ctvrt_h"][1])
        ok("dlaždice čtvrťové noty je dosažitelná", bool(pt), f"bod {pt}")
        if pt:
            await h.pen_tap(pt[0], pt[1])
            await asyncio.sleep(0.9)
        sn = await saved_notes(h)
        first = sn[-1] if sn else {}
        ok("vložená nota má zvolenou velikost i klíč",
           first.get("size") == chosen and first.get("text") == "ctvrt_h",
           f"uloženo {first} vs volba {chosen}")
        ok("vložená nota má barvu pera (červená)", first.get("fill") == RED,
           f"fill={first.get('fill')!r}")

        # --- 4) samovolné vložení (past zabloudilého kliku) --------------------
        auto = []
        for i in range(3):
            before = await glyphs(h)
            p = await open_dialog(h, pts[1 + i] if len(pts) > 1 + i else None)
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
            await pick_tool(h, TOOL_TITLE)

        # --- 5) každá hodnota vloží SPRÁVNÝ kód --------------------------------
        order = ["cela", "pulova_d", "osm_h", "sestn_d", "poml_ctvrt", "poml_osm",
                 "pulova_h", "ctvrt_d", "osm_d", "sestn_h", "poml_cela", "poml_pul", "poml_sestn"]
        for i, key in enumerate(order):
            await pick_tool(h, TOOL_TITLE)
            at = pts[4 + i] if len(pts) > 4 + i else None
            if not at:
                break
            p = await open_dialog(h, at)
            if not p:
                ok(f"dialog pro '{key}'", False, "neotevřel se")
                continue
            before = await glyphs(h)
            tpt = await tile_point(h, NOTES[key][1])
            if not tpt:
                ok(f"dlaždice '{key}' dosažitelná", False, "bod nenalezen")
                await dismiss(h)
                continue
            await h.pen_tap(tpt[0], tpt[1])
            await asyncio.sleep(0.75)
            new = [g for g in await glyphs(h) if g not in before]
            ok(f"volba '{key}' vloží U+{NOTES[key][0]:04X}", new == [NOTES[key][0]],
               f"vloženo {['U+%04X' % g for g in new]}")

        await asyncio.sleep(0.6)
        sn = await saved_notes(h)
        keys_saved = sorted({x["text"] for x in sn})
        ok("všechny vložené noty jsou uložené i s klíčem",
           len(sn) >= 14 and all(k in NOTES for k in keys_saved)
           and all(x["fill"] == RED for x in sn),
           f"uloženo {len(sn)}: {keys_saved}")

        # --- 6) rámeček ruky = obrys glyfu + 8 px (nezávislý přepočet metrik) --
        await pick_tool(h, "Upravit")
        await asyncio.sleep(0.4)
        scale = await layer_scale(h)
        keys_dom = await glyph_keys(h)
        ok("pořadí vykreslených not odpovídá uloženým anotacím",
           len(keys_dom) == len(sn) and all(keys_dom[i][0] == sn[i]["text"]
                                            for i in range(len(keys_dom))),
           f"dom={[k for k, _ in keys_dom][:3]}… uloženo={[x['text'] for x in sn][:3]}…")
        # Rámeček musí být PŘESNĚ obrys glyfu + 8 px z každé strany (v jednotkách
        # vrstvy, proto se násobí měřítkem čtečky). Kdyby kód počítal jen hlavičku,
        # výška rámečku u noty s nožičkou vyjde několikanásobně menší.
        bad, rows, stem_case = [], [], None
        for key in ("ctvrt_h", "osm_h", "cela", "poml_sestn", "poml_ctvrt", "pulova_d"):
            if (key, NOTES[key][0]) not in keys_dom:
                bad.append((key, "na stránce není"))
                continue
            i = keys_dom.index((key, NOTES[key][0]))
            item = next(x for x in sn if x["text"] == key)
            box = await text_box(h, i - len(keys_dom))
            ink = await shot_ink(h, box, dsf) if box else None
            if not ink:
                bad.append((key, "otisk se v pixelech nenašel"))
                continue
            pos = [int(ink["x"] + ink["w"] / 2), int(ink["y"] + ink["h"] / 2)]
            await h.pen_tap(pos[0], pos[1])
            await asyncio.sleep(0.45)
            frame = await frame_box(h)
            if not frame:
                bad.append((key, "rámeček se neobjevil"))
                continue
            x0, x1, y0, y1 = BOXES[key]
            pred_w = (x1 - x0) * item["size"] * scale + 16 * scale
            pred_h = (y1 - y0) * item["size"] * scale + 16 * scale
            inside = (ink["x"] >= frame["x"] - 1.5 and ink["y"] >= frame["y"] - 1.5
                      and ink["x"] + ink["w"] <= frame["x"] + frame["w"] + 1.5
                      and ink["y"] + ink["h"] <= frame["y"] + frame["h"] + 1.5)
            rows.append(f"{key} {frame['w']:.0f}×{frame['h']:.0f} vs {pred_w:.0f}×{pred_h:.0f}")
            if abs(frame["w"] - pred_w) > 4 or abs(frame["h"] - pred_h) > 4 or not inside:
                bad.append((key, f"{frame['w']:.1f}×{frame['h']:.1f} vs "
                                 f"{pred_w:.1f}×{pred_h:.1f}, otisk uvnitř={inside}"))
            if key == "ctvrt_h":
                stem_case = (pos, ink, box)
            await end_edit(h)
        ok("rámeček výběru obepíná CELÝ obrys glyfu (i s nožičkou)",
           not bad, f"{bad if bad else ' · '.join(rows)}  (měřítko {scale:.2f})")

        # --- 7) hit-test pokrývá i nožičku --------------------------------------
        if stem_case:
            pos, ink, box = stem_case
            await h.pen_tap(pos[0], pos[1])
            await asyncio.sleep(0.45)
            ok("ruka notu vybere (rámeček)",
               bool(await h.ev("!!document.querySelector('.annot-selected')")))
            await end_edit(h)
            stem = [int(box["x"] + box["w"] * 0.78), int(ink["y"] + ink["h"] * 0.14)]
            await h.pen_tap(stem[0], stem[1])
            await asyncio.sleep(0.45)
            ok("hit-test pokrývá i nožičku (klepnutí vysoko na notě)",
               bool(await h.ev("!!document.querySelector('.annot-selected')")),
               f"klepnuto na {stem}, otisk od y={ink['y']:.0f} do {ink['y'] + ink['h']:.0f}")
            await end_edit(h)
            await h.pen_tap(int(pos[0]), int(max(6, ink["y"] - 34)))
            await asyncio.sleep(0.45)
            ok("kousek NAD notou ji už nevybere",
               not await h.ev("!!document.querySelector('.annot-selected')"))

            # --- 8) přesun rukou ----------------------------------------------
            before_items = await saved_notes(h)
            b_item = next((x for x in before_items if x["text"] == "ctvrt_h"), None)
            await h.pen_tap(pos[0], pos[1])
            await asyncio.sleep(0.4)
            await h.pen_stroke(pos[0], pos[1], pos[0] + 40, pos[1] + 30, steps=6)
            await asyncio.sleep(0.7)
            after_items = await saved_notes(h)
            a_item = next((x for x in after_items if x["text"] == "ctvrt_h"), None)
            # Musí se posunout PRÁVĚ ta nota, kterou jsme chytili — ne nějaká jiná.
            moved = (bool(a_item) and bool(b_item)
                     and abs((a_item["x"] - b_item["x"]) - 40) <= 6
                     and abs((a_item["y"] - b_item["y"]) - 30) <= 6)
            ok("ruka notu přemístí o přesně tažený kus", moved,
               f"před={b_item} po={a_item}")


        # --- 9) reload --------------------------------------------------------
        n_before = await h.ev("document.querySelectorAll('.annot-layer text').length")
        await h.cdp("Page.reload", {"ignoreCache": True})
        await h.wait_for("document.readyState === 'complete'", label="reload")
        await asyncio.sleep(2.5)
        if not await h.ev("!!document.querySelector('.tb-page')"):
            await h.ev("(() => { const b = document.querySelector('.tb-btn[title=\"Zpět\"]');"
                       " if (b) b.click(); return true; })()")
            await asyncio.sleep(1.2)
            await h.ev(Harness.expand_authors_js())
            await h.wait_for("document.querySelectorAll('li.song').length > 0",
                             timeout=25, label="seznam souborů")
            await h.click(".song-name")
            await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="znovu otevřít")
            await asyncio.sleep(1.5)
        await h.annot_toggle()
        await asyncio.sleep(0.9)
        n_after = await h.ev("document.querySelectorAll('.annot-layer text').length")
        ok("noty přežijí reload", n_after == n_before and n_after > 0, f"{n_before} -> {n_after}")

        # --- 10) guma ----------------------------------------------------------
        await pick_tool(h, "Guma")
        await asyncio.sleep(0.3)
        pos2 = await h.ev("""(() => {
          const ts = [...document.querySelectorAll('.annot-layer text')];
          if (!ts.length) return null;
          const r = ts[ts.length - 1].getBoundingClientRect();
          return [Math.round(r.left + r.width/2), Math.round(r.top + r.height/2)];
        })()""")
        if pos2:
            await h.pen_stroke(pos2[0] - 20, pos2[1], pos2[0] + 20, pos2[1], steps=10)
            await asyncio.sleep(0.7)
            n_gone = await h.ev("document.querySelectorAll('.annot-layer text').length")
            ok("guma notu smaže", n_gone < n_after, f"{n_after} -> {n_gone}")
        else:
            ok("guma notu smaže", False, "žádný glyf na stránce")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
