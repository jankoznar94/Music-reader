#!/usr/bin/env python3
"""Sonda nástroje VKLÁDÁNÍ NOT na ŽIVÉM webu (po nasazení).

Živé prostředí má tři pasti, které v dev režimu nejsou: starý service worker
(drží starý HTML i staré assety), stará CacheStorage a stará IndexedDB. Sonda
proto nejdřív odregistruje SW, smaže cache i IndexedDB, teprve pak měří.

Ověřuje totéž co dev sonda, ale jen to podstatné:
  1) nasazený bundle opravdu obsahuje nástroj (jinak se měří stará verze)
  2) nástroj v panelu, dialog se dvěma sekcemi a 14 dlaždicemi
  3) SUBSET FONTU: každý kód se měří fontem NotyDyn (živý woff2, ne lokální)
  4) klepnutí na dlaždici vloží SPRÁVNÝ SMuFL kód
  5) rámeček ruky obepíná CELÝ otisk noty (měřeno z pixelů)
  6) nota přežije reload

    NOTY_TARGET=https://harlequin-music-reader.web.app/ \
        bash scripts/run-probe-fresh.sh scripts/probe-live-notes.py
"""
import asyncio
import importlib.util
import json
import os

import numpy as np  # noqa: F401  (používá ho modul se sondou)

_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", "/home/martin_fabian/noty-app/cdp-e2e-harness.py")
_h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_h)
_h.CDP_HTTP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
Harness, Check, make_pdf = _h.Harness, _h.Check, _h.make_pdf

_dspec = importlib.util.spec_from_file_location(
    "dev_notes_probe", "/home/martin_fabian/noty-app/scripts/probe-notation-notes.py")
_d = importlib.util.module_from_spec(_dspec)
_dspec.loader.exec_module(_d)

LIVE = os.environ.get("NOTY_TARGET", "https://harlequin-music-reader.web.app/")


class LiveHarness(Harness):
    async def wipe(self):
        """Odregistruj SW + smaž cache a IndexedDB, ať sonda nevidí starou verzi."""
        try:
            await self.ev("(async () => {"
                          " const rs = await navigator.serviceWorker.getRegistrations();"
                          " for (const r of rs) await r.unregister();"
                          " for (const k of await caches.keys()) await caches.delete(k);"
                          " return true; })()", await_promise=True)
        except Exception as exc:
            print("   (wipe SW selhalo:", exc, ")")
        try:
            await self.ev("indexedDB.deleteDatabase('noty-app')")
        except Exception:
            pass
        await asyncio.sleep(1.2)
        await self.open()
        n = await self.ev("navigator.serviceWorker.getRegistrations().then(r => r.length)",
                          await_promise=True)
        print("   service workerů po vyčištění:", n)


async def bundle_has_note_tool(h):
    return await h.ev(r"""(async () => {
      const urls = performance.getEntriesByType('resource')
        .map(e => e.name).filter(n => /assets\/index-.*\.js$/.test(n));
      const out = [];
      for (const u of urls) {
        const t = await (await fetch(u)).text();
        // Adresa fontu je v CSS, ne v JS — tady se kontroluje jen to, co má být v bundlu.
        out.push({ url: u, len: t.length,
                   tool: t.includes('Vkládání not') && t.includes('Pomlky'),
                   sekce: t.includes('Vkládání not') });
      }
      return out;
    })()""", await_promise=True)


async def main():
    ok = Check()
    async with LiveHarness(url=LIVE) as h:
        await h.open()
        await h.set_tablet()
        await h.ev("indexedDB.deleteDatabase('noty-app')")
        await h.wipe()

        # --- 1) je funkce v NASZENÉM bundlu? (jinak měříme starou verzi) -------
        bundles = await bundle_has_note_tool(h)
        print("nasazené bundly:")
        for b in bundles or []:
            print(f"   {b['url']}  ({b['len']} B)  nástroj Nota: {b['tool']}  sekce: {b['sekce']}")
        ok("nasazený bundle obsahuje nástroj Nota", any(b["tool"] for b in (bundles or [])),
           f"{bundles}")

        await h.open_song(pdf=make_pdf(6))
        await h.annot_toggle()
        await _d.install_writer_hook(h)
        dsf = await h.ev("window.devicePixelRatio")

        # --- 2) nástroj, dialog, dlaždice --------------------------------------
        ok("tlačítko nástroje je v panelu",
           bool(await h.ev("(() => [...document.querySelectorAll('.ap-tool')]"
                           ".some(x => (x.title||'').startsWith('Vkládání not')))()")))
        await _d.pick_tool(h, _d.TOOL_TITLE)
        await _d.pick_red(h)
        pts = await _d.free_points(h, 12)
        p = await _d.open_dialog(h, pts[0] if pts else None)
        ok("dialog noty se otevře", bool(p))
        d = await _d.dialog_state(h)
        if d:
            ok("dialog se jmenuje Nota", d["label"] == "Nota", f"label={d['label']!r}")
            ok("dialog má sekce Noty a Pomlky", d["sections"] == ["Noty", "Pomlky"],
               f"sekrece={d['sections']}")
            ok("dialog nabízí 14 dlaždic", len(d["tiles"]) == 14, f"n={len(d['tiles'])}")
            want = {v[1]: v[0] for v in _d.NOTES.values()}
            bad = [t["title"] for t in d["tiles"] if want.get(t["title"]) != t["cp"]]
            ok("každá dlaždice nese svůj kód", not bad, f"špatně: {bad}")
        else:
            ok("dialog noty má obsah", False, "karta nenalezena")

        # --- 3) živý font má všechny noty i pomlky ----------------------------
        w = await _d.font_widths(h)
        bad_w = [(k, hex(cp), w.get(k)) for k, (cp, _l, adv) in _d.NOTES.items()
                 if w.get(k) is None or abs(w[k] - adv * 100) > 2]
        ok("živý font má všechny noty a pomlky (šířky sedí)", not bad_w, f"mimo: {bad_w}")

        # --- 4) vložení: nota s nožičkou, celá nota, pomlka --------------------
        await _d.pick_tool(h, _d.TOOL_TITLE)
        pt = await _d.tile_point(h, _d.NOTES["ctvrt_h"][1])
        if pt:
            await h.pen_tap(pt[0], pt[1])
            await asyncio.sleep(0.9)
        await asyncio.sleep(0.5)
        sn = await _d.saved_notes(h)
        ok("nota se vloží i uloží (klíč, barva, velikost)",
           bool(sn) and sn[-1]["text"] == "ctvrt_h" and sn[-1]["fill"] == _d.RED
           and sn[-1]["size"] > 0, f"uloženo {sn[-1] if sn else None}")

        for key, idx in (("cela", 1), ("poml_ctvrt", 2), ("osm_h", 3)):
            await _d.pick_tool(h, _d.TOOL_TITLE)
            at = pts[idx] if len(pts) > idx else None
            if not at:
                continue
            p = await _d.open_dialog(h, at)
            if not p:
                ok(f"dialog pro '{key}'", False, "neotevřel se")
                continue
            before = await _d.glyphs(h)
            tpt = await _d.tile_point(h, _d.NOTES[key][1])
            if not tpt:
                ok(f"dlaždice '{key}'", False, "bod nenalezen")
                await _d.dismiss(h)
                continue
            await h.pen_tap(tpt[0], tpt[1])
            await asyncio.sleep(0.8)
            new = [g for g in await _d.glyphs(h) if g not in before]
            ok(f"volba '{key}' vloží U+{_d.NOTES[key][0]:04X}", new == [_d.NOTES[key][0]],
               f"vloženo {['U+%04X' % g for g in new]}")

        # --- 5) rámeček ruky sedí na otisku (měřeno z pixelů) -----------------
        await _d.pick_tool(h, "Upravit")
        await asyncio.sleep(0.4)
        scale = await _d.layer_scale(h)
        keys_dom = await _d.glyph_keys(h)
        sn = await _d.saved_notes(h)
        key = "ctvrt_h"
        if (key, _d.NOTES[key][0]) in keys_dom:
            i = keys_dom.index((key, _d.NOTES[key][0]))
            item = next(x for x in sn if x["text"] == key)
            box = await _d.text_box(h, i - len(keys_dom))
            ink = await _d.shot_ink(h, box, dsf) if box else None
            if ink:
                await h.pen_tap(int(ink["x"] + ink["w"] / 2), int(ink["y"] + ink["h"] / 2))
                await asyncio.sleep(0.5)
                frame = await _d.frame_box(h)
                x0, x1, y0, y1 = _d.BOXES[key]
                pred_w = (x1 - x0) * item["size"] * scale + 16 * scale
                pred_h = (y1 - y0) * item["size"] * scale + 16 * scale
                ok("rámeček ruky = obrys glyfu + 8 px (i s nožičkou)",
                   bool(frame) and abs(frame["w"] - pred_w) <= 4
                   and abs(frame["h"] - pred_h) <= 4,
                   f"rámeček {frame['w']:.0f}×{frame['h']:.0f} vs "
                   f"{pred_w:.0f}×{pred_h:.0f} (měřítko {scale:.2f})")
                await _d.end_edit(h)
            else:
                ok("otisk noty se v pixelech našel", False, "nenalezen")
        else:
            ok("nota je na stránce", False, f"{keys_dom}")

        # --- 6) zrcadlení noty (vodorovně + svisle) ---------------------------
        await _d.pick_tool(h, "Upravit")
        await h.ev("(() => { const b = document.querySelector('.eb-btn.done');"
                   " if (b) b.click(); return true; })()")
        await asyncio.sleep(0.3)
        await _d.pick_tool(h, _d.TOOL_TITLE)
        at = pts[5] if len(pts) > 5 else None
        if at:
            p = await _d.open_dialog(h, at)
            if p:
                await _d.tap_label_button(h, "Vodorovně")
                await _d.tap_label_button(h, "Svisle")
                tg = await _d.flip_toggles(h)
                ok("přepínače zrcadlení se rozsvítí",
                   bool(tg) and tg[0]["on"] and tg[1]["on"], f"{tg}")
                tpt = await _d.tile_point(h, _d.NOTES["ctvrt_h"][1])
                if tpt:
                    await h.pen_tap(tpt[0], tpt[1])
                    await asyncio.sleep(0.9)
                sn = await _d.saved_notes(h)
                last = next((x for x in reversed(sn) if x["flipX"] and x["flipY"]), None)
                ok("zrcadlená nota se uloží i s překlopením", bool(last), f"uloženo {sn[-1:]}")
                ok("kreslení má transformaci zrcadlení",
                   "scale(-1 -1)" in (await _d.transform_attr(h, -1) or ""),
                   f"transform={await _d.transform_attr(h, -1)!r}")
                await _d.pick_tool(h, "Upravit")
                await asyncio.sleep(0.4)
                box = await _d.text_box(h, -1)
                ink = await _d.shot_ink(h, box, dsf) if box else None
                ok("otisk zrcadlené noty se najde v pixelech", bool(ink))
                if ink and last:
                    anchor = await _d.anchor_screen(h, last)
                    sc = await _d.layer_scale(h)
                    b0 = _d.BOXES["ctvrt_h"][2]
                    pred_top = anchor[1] + b0 * last["size"] * sc
                    ok("zrcadlená nota sedí hlavičkou u účaří",
                       abs(ink["y"] - pred_top) <= 4,
                       f"horní okraj {ink['y']:.1f} vs předpověď {pred_top:.1f} px")
                    side = await _d.stem_side(h, ink, dsf, bottom=True)
                    ok("nožička se překlopila na druhou stranu",
                       side is not None and side < -2,
                       f"nožička {side:+.1f} px od středu otisku")
                    await h.pen_tap(int(ink["x"] + ink["w"] / 2), int(ink["y"] + ink["h"] / 2))
                    await asyncio.sleep(0.5)
                    frame = await _d.frame_box(h)
                    if frame:
                        m = [ink["x"] - frame["x"], ink["y"] - frame["y"],
                             (frame["x"] + frame["w"]) - (ink["x"] + ink["w"]),
                             (frame["y"] + frame["h"]) - (ink["y"] + ink["h"])]
                        ok("rámeček obepíná i zrcadlený otisk",
                           all(-1.5 <= v <= 8 * sc + 6 for v in m),
                           f"mezery L={m[0]:.1f} T={m[1]:.1f} P={m[2]:.1f} D={m[3]:.1f}")
                    else:
                        ok("rámeček obepíná i zrcadlený otisk", False, "rámeček není")
                    await _d.end_edit(h)
        else:
            ok("místo pro zrcadlenou notu", False, "málo vzdušných bodů")

        # --- 7) reload --------------------------------------------------------
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
        ok("noty přežijí reload i na živém webu", n_after == n_before and n_after > 0,
           f"{n_before} -> {n_after}")
        fl = await h.ev("(() => [...document.querySelectorAll('.annot-layer text')]"
                        ".filter(t => t.getAttribute('transform')).length)()")
        ok("zrcadlení přežije reload i na živém webu", fl >= 1, f"zrcadlených not: {fl}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
