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
# Klíče „_h“/„_d“: v NABÍDCE je jen jedna dlaždice na hodnotu („_h“), směr dolů
# vzniká svislým zrcadlením (výměnou glyfu). Klíče „_d“ zůstávají kvůli starším
# uloženým notám — proto je sonda zná taky.
NOTES = {
    "cela":       (0xE1D2, "celá nota", 0.4590),
    "pulova_h":   (0xE1D3, "půlová nota", 0.3410),
    "pulova_d":   (0xE1D4, "půlová nota (dolů)", 0.3410),
    "ctvrt_h":    (0xE1D5, "čtvrťová nota", 0.3320),
    "ctvrt_d":    (0xE1D6, "čtvrťová nota (dolů)", 0.3320),
    "osm_h":      (0xE1D7, "osminová nota", 0.5660),
    "osm_d":      (0xE1D8, "osminová nota (dolů)", 0.3320),
    "sestn_h":    (0xE1D9, "šestnáctinová nota", 0.5810),
    "sestn_d":    (0xE1DA, "šestnáctinová nota (dolů)", 0.3320),
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


async def eb_button_point(h, title):
    """Bod na tlačítku pásu úprav podle title (např. „Zvětšit“)."""
    return await h.ev("""(() => {
      const b = [...document.querySelectorAll('.edit-bar button')]
        .find(x => (x.title || '') === %s);
      if (!b) return null;
      const r = b.getBoundingClientRect();
      return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
    })()""" % json.dumps(title))


async def eb_size(h):
    return await h.ev("(() => { const e = document.querySelector('.eb-val');"
                      " return e ? parseInt(e.textContent, 10) : null; })()")


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
              .map(x => ({ id: x.id, page: x.page, text: x.text, size: Math.round(x.size),
                           fill: (x.color || '').toLowerCase(),
                           flipX: !!x.flipX, flipY: !!x.flipY,
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


async def anchor_screen(h, it):
    """Bod ukotvení noty (střed hlavičky) v souřadnicích OBRAZOVKY, přes matici vrstvy."""
    return await h.ev("""(() => {
      const m = document.querySelector('.annot-layer').getScreenCTM();
      if (!m) return null;
      const p = new DOMPoint(%f, %f).matrixTransform(m);
      return [p.x, p.y];
    })()""" % (it["x"], it["y"]))


async def flip_toggles(h):
    return await h.ev("""(() => {
      const card = document.querySelector('.text-input-card');
      if (!card) return null;
      const b = [...card.querySelectorAll('.ti-toggle')];
      return b.map(x => ({ label: x.textContent.trim(), on: x.classList.contains('on'),
                           x: Math.round(x.getBoundingClientRect().left
                                         + x.getBoundingClientRect().width / 2),
                           y: Math.round(x.getBoundingClientRect().top
                                         + x.getBoundingClientRect().height / 2) }));
    })()""")


async def tap_label_button(h, label):
    pt = await h.ev("""(() => {
      const els = [...document.querySelectorAll('.ti-toggle, .eb-chip')]
        .filter(x => x.textContent.trim() === %s);
      if (!els.length) return null;
      const r = els[0].getBoundingClientRect();
      return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)];
    })()""" % json.dumps(label))
    if not pt:
        return False
    await h.pen_tap(pt[0], pt[1])
    await asyncio.sleep(0.45)
    return True


async def transform_attr(h, idx=-1):
    return await h.ev("""(() => {
      const ts = [...document.querySelectorAll('.annot-layer text')];
      const t = ts[ts.length + %d];
      return t ? (t.getAttribute('transform') || '') : null;
    })()""" % idx)


async def stem_side(h, ink, dsf=2, bottom=False):
    """Na kterou stranu od středu otisku leží pás s NOŽIČKOU (vodorovná poloha).

    Vrací (střed_pásu − střed_otisku) v CSS px: kladné = nožička vpravo.
    Tohle rozliší zrcadlení VODOROVNĚ i tam, kde je obrysová mez symetrická
    (čtvrťová nota má obrys přesně přes šířku zápisu, takže bounding box se
    zrcadlením nezmění — změnit se musí jen ROZLOŽENÍ otisku).

    ⚠️ Pás se musí vybrat podle SVISLÉHO zrcadlení: nožička nahoru je v HORNÍM
    pásu otisku, po svislém zrcadlení visí DOLŮ a je ve SPODNÍM pásu. Když se
    hledá nožička vždy nahoře, u svisle zrcadlené noty se měří hlavička (a vyjde
    „nožička uprostřed“).
    """
    shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
    img = Image.open(io.BytesIO(base64.b64decode(shot["data"]))).convert("RGB")
    x0 = int(ink["x"] * dsf); y0 = int(ink["y"] * dsf)
    w = int(ink["w"] * dsf); hh = int(ink["h"] * dsf)
    crop = np.asarray(img.crop((x0, y0, x0 + w, y0 + hh))).astype(int)
    r, g, b = crop[:, :, 0], crop[:, :, 1], crop[:, :, 2]
    mask = (r - g > 60) & (r - b > 60)
    band = mask[max(0, hh - int(hh * 0.3)):] if bottom else mask[:max(1, int(hh * 0.3))]
    ys, xs = np.nonzero(band)
    if len(xs) == 0:
        return None
    return (x0 + (xs.min() + xs.max() + 1) / 2) / dsf - (ink["x"] + ink["w"] / 2)


async def ink_at_layer(h, x, y, dsf, half=40):
    """Otisk noty v pixelech kolem bodu ukotvení (zadaného v souřadnicích Vrstvy)."""
    pt = await h.ev("""(() => { const m = document.querySelector('.annot-layer').getScreenCTM();
      if (!m) return null; const p = new DOMPoint(%f, %f).matrixTransform(m);
      return [p.x, p.y]; })()""" % (x, y))
    if not pt:
        return None
    return await shot_ink(h, {"x": pt[0] - half, "y": pt[1] - half,
                              "w": half * 2, "h": half * 2}, dsf, pad=0)


async def reload_and_reopen(h):
    """Reload stránky a znovu otevřít skladbu + anotační režim."""
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


async def read_legacy_note(h):
    """Přečti anotaci id 'legacy-1' přímo z IndexedDB (nový zápis = klíč _h + flipY)."""
    return await h.ev("""(async () => {
      const db = await new Promise((res, rej) => { const r = indexedDB.open('noty-app');
        r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
      const st = db.transaction('annotations', 'readonly').objectStore('annotations');
      const all = await new Promise((res) => { const rq = st.getAll(); rq.onsuccess = () => res(rq.result); });
      for (const rec of all) for (const it of (rec.items || []))
        if (it.id === 'legacy-1') return { text: it.text, flipX: it.flipX, flipY: it.flipY,
                                           size: it.size, x: it.x, y: it.y };
      return null;
    })()""", await_promise=True)


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
            ok("dialog nabízí 10 dlaždic (jedna na hodnotu)", len(d["tiles"]) == 10,
               f"n={len(d['tiles'])}")
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
        # Jan: „Velikost not bych ideálně měnil po 1px. Teď to skáče po 3px.“
        ok("tlačítko + zvětší notu po 1 px (2 kroky)",
           bool(d2) and d2["size_val"] == size0 + 2,
           f"{size0} -> {d2['size_val'] if d2 else '?'} (čekáno {size0 + 2})")
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

        # Jan: „Po vložení noty by se nota automaticky měla označit. Aby mohl uživatel
        # hned notu upravit a přemístit.“ = dlaždice se chová jako „Uložit a ruka“.
        nv = await h.ev("window.__navdbg()") or {}
        bar = await h.ev("!!document.querySelector('.edit-bar')")
        ok("po vložení noty se nota sama označí (pás úprav + výběr)",
           nv.get("tool") == "edit" and nv.get("editingId") == first.get("id") and bar,
           f"nástroj {nv.get('tool')!r}, vybráno {nv.get('editingId')!r} vs nota "
           f"{first.get('id')!r}, pás úprav v DOM: {bar}")
        ok("nástroj Vkládání not už není zapnutý (další klepnutí notu nepřidá)",
           not await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                          ".find(x => (x.title || '').startsWith('Vkládání not'));"
                          " return !!(b && b.classList.contains('on')); })()"),
           "")
        ok("v pásu úprav je i „Hotovo“ a koš (nota se dá hned upravit i smazat)",
           bool(await h.ev("!!document.querySelector('.eb-btn.done')")),
           await h.ev("(() => [...document.querySelectorAll('.edit-bar button')]"
                      ".map(b => (b.title || '') + ':' + (b.className || '')).join(' | '))()"))
        # Velikost se musí měnit STEJNĚ v dialogu i v pásu úprav — Jan jednou hlásil,
        # že „+“ ubírá jinde jiný počet bodů než v dialogu. U noty po 1 px.
        s_before = await eb_size(h)
        ep = await eb_button_point(h, "Zvětšit")
        if ep:
            await h.pen_tap(ep[0], ep[1])
            await asyncio.sleep(0.35)
            await h.pen_tap(ep[0], ep[1])
            await asyncio.sleep(0.5)
        s_after = await eb_size(h)
        ok("v pásu úprav u vložené noty se velikost mění po 1 px (2 kroky)",
           bool(ep) and s_before is not None and s_after == s_before + 2,
           f"{s_before} -> {s_after} (tlačítko {ep})")

        # Uklidit po sobě: zbytek sondy měří bez rámečku výběru (jako předtím).
        await end_edit(h)

        # --- 4) samovolné vložení (past zabloudilého kliku) --------------------
        auto = []
        for i in range(3):
            await pick_tool(h, TOOL_TITLE)      # po vložení je aktivní ruka (auto označení)
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
        # Jen hodnoty, které má nabídka (směrové „_d“ dlaždice už v nabídce nejsou).
        order = ["cela", "osm_h", "poml_ctvrt", "poml_osm", "pulova_h",
                 "sestn_h", "poml_cela", "poml_pul", "poml_sestn"]
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
            await end_edit(h)   # nota je po vložení vybraná — uklidit před dalším krokem

        await asyncio.sleep(0.6)
        sn = await saved_notes(h)
        keys_saved = sorted({x["text"] for x in sn})
        ok("všechny vložené noty jsou uložené i s klíčem",
           len(sn) >= 10 and all(k in NOTES for k in keys_saved)
           and all(x["fill"] == RED for x in sn),
           f"uloženo {len(sn)}: {keys_saved}")

        # --- 6) rámeček ruky = obrys glyfu + 8 px (nezávislý přepočet metrik) --
        # Obtažení obrysu = ztluštění nožičky (Jan: „Nešla by nožička noty udělat
        # o trochu tlustší?“). Tloušťku tahu UVNITŘ glyfu měnit nelze, proto se obarví
        # celý obrys (paint-order: stroke) — nožička se ztluští relativně nejvíc.
        # Značky se obtažené být NESMÍ (mění se jen noty).
        strokes = await h.ev("""(() => [...document.querySelectorAll('.annot-layer text')]
          .map(t => ({ cp: t.textContent.codePointAt(0) || 0,
                       stroke: t.getAttribute('stroke'),
                       sw: parseFloat(t.getAttribute('stroke-width') || '0') || 0,
                       paint: t.getAttribute('paint-order'),
                       size: parseFloat(getComputedStyle(t).fontSize) })))()""")
        notes_s = [s for s in strokes if 0xE1D2 <= s["cp"] <= 0xE1DA or 0xE4E3 <= s["cp"] <= 0xE4E7]
        marks_s = [s for s in strokes if s not in notes_s]
        ok("noty jsou obtažené (nožička tlustší) přesně na svou velikost",
           bool(notes_s) and all(s["stroke"] not in (None, "none") and s["paint"] == "stroke"
                                 and abs(s["sw"] - s["size"] * 0.025) < 0.02 for s in notes_s),
           f"např. {notes_s[0] if notes_s else 'žádná nota'}")
        ok("značky obtažené nejsou (mění se jen nožičky not)",
           all(s["stroke"] in (None, "none") or s["sw"] == 0 for s in marks_s),
           f"obtažené značky: {[s for s in marks_s if s['stroke'] not in (None, 'none')]}")

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
        for key in ("ctvrt_h", "osm_h", "cela", "poml_sestn", "poml_ctvrt", "sestn_h"):
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


        # --- 9) ZRCADLENÍ NOTY (vodorovně / svisle) ----------------------------
        # Noty se umisťují do VZDUŠNÝCH bodů — měření otisku z pixelů nesmí míchat
        # sousedy. Zrcadlení se zkouší u čtvrťové noty: má symetrický obrys přes
        # šířku zápisu, takže zrcadlení VODOROVNĚ se v ohraničujícím boxu neprojeví
        # a musí se měřit z ROZLOŽENÍ otisku (kde je nožička).
        cases = [("flipX", True, False), ("flipY", False, True), ("oba", True, True)]
        measured = {}
        for i, (name, fx, fy) in enumerate(cases):
            # Body 4–16 už zabrala zkouška všech hodnot — ber až ty za nimi,
            # aby se otisky nepřekrývaly (měření z pixelů by míchalo sousedy).
            at = pts[17 + i] if len(pts) > 17 + i else None
            if not at:
                ok(f"místo pro zrcadlení '{name}'", False, "málo vzdušných bodů")
                continue
            await pick_tool(h, TOOL_TITLE)
            p = await open_dialog(h, at)
            if not p:
                ok(f"dialog pro zrcadlení '{name}'", False, "neotevřel se")
                continue
            tg = await flip_toggles(h)
            ok(f"dialog nabízí zrcadlení vodorovně i svisle ('{name}')",
               bool(tg) and [t["label"] for t in tg] == ["Vodorovně", "Svisle"],
               f"přepínače={tg}")
            if fx:
                await tap_label_button(h, "Vodorovně")
            if fy:
                await tap_label_button(h, "Svisle")
            tg2 = await flip_toggles(h)
            ok(f"přepínače se rozsvítí podle volby ('{name}')",
               bool(tg2) and tg2[0]["on"] == fx and tg2[1]["on"] == fy, f"{tg2}")
            tpt = await tile_point(h, NOTES["ctvrt_h"][1])
            if not tpt:
                ok(f"dlaždice pro '{name}'", False, "bod nenalezen")
                await dismiss(h)
                continue
            await h.pen_tap(tpt[0], tpt[1])
            await asyncio.sleep(0.85)
            sn = await saved_notes(h)
            last = sn[-1] if sn else {}
            ok(f"volba zrcadlení se uloží ('{name}')",
               last.get("text") == "ctvrt_h" and last.get("flipX") == fx
               and last.get("flipY") == fy, f"uloženo {last}")
            tr = await transform_attr(h, -1) or ''
            cp = await h.ev("""(() => { const ts=[...document.querySelectorAll('.annot-layer text')];
                 return ts.length ? (ts[ts.length-1].textContent.codePointAt(0)||0) : 0; })()""")
            exp_cp = NOTES["ctvrt_d"][0] if fy else NOTES["ctvrt_h"][0]
            ok(f"kreslení odpovídá zrcadlení ('{name}')",
               cp == exp_cp and (("scale(-1 1)" in tr) if fx else tr == ""),
               f"glyf U+{cp:04X} (čekáno U+{exp_cp:04X}), transform={tr!r}")
            measured[name] = (last, await text_box(h, -1))
            # Nota je po vložení vybraná — před měřením z pixelů rámeček sundat,
            # jinak by se do otisku noty přimíchal rámeček (má stejnou červenou).
            await end_edit(h)

        # Otisk zrcadlených not: horní okraj musí sedět u ÚČAŘÍ (ne o osnovu výš)
        # a nožička musí zůstat/přesunout se na správnou stranu.
        await pick_tool(h, "Upravit")
        await asyncio.sleep(0.4)
        scale = await layer_scale(h)
        b0, b1 = BOXES["ctvrt_h"][2], BOXES["ctvrt_h"][3]
        for name, (item, box) in measured.items():
            if not box:
                ok(f"nota '{name}' je na stránce", False, "prvek nenalezen")
                continue
            ink = await shot_ink(h, box, dsf)
            if not ink:
                ok(f"otisk zrcadlené noty ('{name}')", False, "v pixelech nenalezen")
                continue
            anchor = await anchor_screen(h, item)
            s = item["size"] * scale
            pred_top = anchor[1] + (b0 * s if item["flipY"] else -b1 * s)
            ok(f"zrcadlená nota sedí na ukotvení — hlavička u účaří ('{name}')",
               abs(ink["y"] - pred_top) <= 4,
               f"horní okraj otisku {ink['y']:.1f} px vs předpověď {pred_top:.1f} px "
               f"(svisle zrcadleno: {item['flipY']})")
            # Svisle = výměna glyfu (nožička dolů je vlevo), vodorovně = zrcadlení
            # (strana se obrátí). Očekávaná strana je tedy XOR obojího.
            dirn = "down" if item["flipY"] else "up"
            side = await stem_side(h, ink, dsf, bottom=(dirn == "down"))
            expect_right = (dirn == "up") != bool(item["flipX"])
            ok(f"nožička je po zrcadlení na správné straně ('{name}')",
               side is not None and (side > 2 if expect_right else side < -2),
               f"nožička {side:+.1f} px od středu otisku, směr {dirn}, vodorovně "
               f"zrcadleno {item['flipX']} → čekáno {'vpravo' if expect_right else 'vlevo'}, "
               f"měřeno v {'spodním' if dirn == 'down' else 'horním'} pásu")
            pos = [int(ink["x"] + ink["w"] / 2), int(ink["y"] + ink["h"] / 2)]
            await h.pen_tap(pos[0], pos[1])
            await asyncio.sleep(0.5)
            frame = await frame_box(h)
            if frame:
                m = [ink["x"] - frame["x"], ink["y"] - frame["y"],
                     (frame["x"] + frame["w"]) - (ink["x"] + ink["w"]),
                     (frame["y"] + frame["h"]) - (ink["y"] + ink["h"])]
                ok(f"rámeček obepíná i ZRCADLENÝ otisk ('{name}')",
                   all(-1.5 <= v <= 8 * scale + 6 for v in m),
                   f"mezery L={m[0]:.1f} T={m[1]:.1f} P={m[2]:.1f} D={m[3]:.1f} "
                   f"(očekáváno ~{8 * scale:.1f} px)")
            else:
                ok(f"rámeček obepíná i ZRCADLENÝ otisk ('{name}')", False, "rámeček není")
            # přepnutí zrcadlení v pásu úprav u UŽ VLOŽENÉ noty
            eb = await h.ev("""(() => {
              const bar = document.querySelector('.edit-bar');
              if (!bar) return null;
              return (bar.textContent || '').includes('Zrcadlení');
            })()""")
            ok(f"pás úprav nabízí zrcadlení u vložené noty ('{name}')", bool(eb))
            if name == "flipX":
                before_saved = await saved_notes(h)
                await tap_label_button(h, "Svisle")
                after_saved = await saved_notes(h)
                b_it = next((x for x in before_saved if x["text"] == "ctvrt_h"
                             and x["flipX"] and not x["flipY"]), None)
                a_it = next((x for x in after_saved if x["text"] == "ctvrt_h"
                             and x["flipX"] and x["flipY"]), None)
                ok("pás úprav zrcadlení zapne i u vložené noty", bool(b_it) and bool(a_it),
                   f"před={b_it} po={a_it}")
            await end_edit(h)

        # --- 10) reload --------------------------------------------------------
        n_before = await h.ev("document.querySelectorAll('.annot-layer text').length")
        await reload_and_reopen(h)
        n_after = await h.ev("document.querySelectorAll('.annot-layer text').length")
        ok("noty přežijí reload", n_after == n_before and n_after > 0, f"{n_before} -> {n_after}")
        counts = await h.ev("""(() => {
          const ts = [...document.querySelectorAll('.annot-layer text')];
          const down = [0xE1D4, 0xE1D6, 0xE1D8, 0xE1DA];
          return { tr: ts.filter(t => t.getAttribute('transform')).length,
                   down: ts.filter(t => down.includes(t.textContent.codePointAt(0))).length };
        })()""")
        ok("zrcadlení přežije reload (vodorovné i svislé)",
           counts["tr"] >= 1 and counts["down"] >= 1, f"{counts}")

        # --- 12) STARŠÍ NOTY (klíč „…_d“) — musí se dál kreslit a srovnat se ---
        # Noty vložené před zrcadlením mají směr nožičky v klíči. Nový zápis drží
        # směr ve `flipY`, takže se při načtení srovnávají — a hlavně: kreslit se
        # musí POŘÁD stejně (nožička dolů), jinak by uživateli v notách zmizely.
        song_id = await h.ev("""(async () => {
          const db = await new Promise((res, rej) => { const r = indexedDB.open('noty-app');
            r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
          const stores = [...db.objectStoreNames];
          const st = db.transaction('annotations', 'readwrite').objectStore('annotations');
          const all = await new Promise((res) => { const rq = st.getAll(); rq.onsuccess = () => res(rq.result); });
          const rec = all[0];
          if (!rec || stores.indexOf('annotations') < 0) return null;
          rec.items.push({ id: 'legacy-1', page: 0, tool: 'note', text: 'ctvrt_d',
                           color: '#c0392b', opacity: 1, size: 36, x: 620, y: 320 });
          await new Promise((res) => { const rq = st.put(rec); rq.onsuccess = () => res(); });
          return rec.songId;
        })()""", await_promise=True)
        ok("starší nota (klíč „ctvrt_d“) se podařilo zapsat do databáze", bool(song_id),
           f"songId={song_id}")
        if song_id:
            await reload_and_reopen(h)
            cps = await h.ev("(() => [...document.querySelectorAll('.annot-layer text')]"
                             ".map(t => t.textContent.codePointAt(0) || 0))()")
            ok("starší nota s nožičkou dolů se kreslí dál",
               NOTES["ctvrt_d"][0] in cps, f"kódy: {['U+%04X' % c for c in cps]}")
            legacy_item = await read_legacy_note(h)
            ok("starší nota je srovnaná na nový zápis (klíč „_h“ + flipY)",
               bool(legacy_item) and legacy_item.get("text") == "ctvrt_h"
               and legacy_item.get("flipY") is True,
               f"{legacy_item}")
            # a pás úprav ji umí přepnout na nožičku nahoru
            await pick_tool(h, "Upravit")
            await asyncio.sleep(0.4)
            if legacy_item:
                ink = await ink_at_layer(h, legacy_item["x"], legacy_item["y"], dsf)
                if ink:
                    await h.pen_tap(int(ink["x"] + ink["w"] / 2), int(ink["y"] + ink["h"] / 2))
                    await asyncio.sleep(0.5)
                    await tap_label_button(h, "Svisle")
                    flipped = await read_legacy_note(h)
                    ok("starší notu lze přepnout na nožičku nahoru",
                       bool(flipped) and flipped.get("flipY") is False,
                       f"{flipped}")
                    await end_edit(h)
                else:
                    ok("starší notu lze najít v pixelech", False, "otisk nenalezen")

        # --- 13) guma ----------------------------------------------------------
        await pick_tool(h, "Guma")
        await asyncio.sleep(0.3)
        pos2 = await h.ev("""(() => {
          const ts = [...document.querySelectorAll('.annot-layer text')];
          if (!ts.length) return null;
          const r = ts[ts.length - 1].getBoundingClientRect();
          return [Math.round(r.left + r.width/2), Math.round(r.top + r.height/2)];
        })()""")
        # Počet se bere TADY, ne z reloadu — mezi tím přibyla starší nota z databáze.
        n_before_guma = await h.ev("document.querySelectorAll('.annot-layer text').length")
        if pos2:
            await h.pen_stroke(pos2[0] - 20, pos2[1], pos2[0] + 20, pos2[1], steps=10)
            await asyncio.sleep(0.7)
            n_gone = await h.ev("document.querySelectorAll('.annot-layer text').length")
            ok("guma notu smaže", n_gone < n_before_guma,
               f"{n_before_guma} -> {n_gone}")
        else:
            ok("guma notu smaže", False, "žádný glyf na stránce")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
