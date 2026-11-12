#!/usr/bin/env python3
"""SONDA: chování nástrojů Značky / Vkládání not (listopad 2026).

Reprodukuje Janovy stížnosti:
  1. klepnutí na tlačítko skupiny (ikona ♫) — vybarví se? jaký nástroj je vybraný?
  2. vložení noty a klepnutí na „Uložit“ — zmizí okno?
  3. řádek Linky — jsou Nahoru/Dolů/Mezera na jednom řádku?

Spouštěj:  scripts/run-probe-fresh.sh probe-note-flow.py
"""
import asyncio
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)
Harness = m.Harness
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)


TAP = "finger" if os.environ.get("PROBE_INPUT") == "finger" else "pen"


async def tap(h, x, y):
    if TAP == "finger":
        await h.finger_tap(x, y)
    else:
        await h.pen_tap(x, y)


def center(js):
    return ("(() => { const b = %s; if (!b) return null;"
            " const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2),"
            " on: b.classList.contains('on')}; })()" % js)


async def main():
    fails = []
    async with Harness() as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=m.make_pdf(6))
        await h.annot_toggle()
        await asyncio.sleep(0.8)

        # --- 1. tlačítko skupiny -------------------------------------------
        g = await h.ev(center("document.querySelector('.ap-tool.nota-tool')"))
        await tap(h, g["x"], g["y"])
        await asyncio.sleep(0.6)
        st = await h.ev("window.__navdbg()")
        on = await h.ev("document.querySelector('.ap-tool.nota-tool').classList.contains('on')")
        print("1) po klepnutí na skupinu: tool=%r, skupina svítí=%s, řádek otevřený=%s"
              % (st["tool"], on, await h.ev("!!document.querySelector('.ap-nota-row')")))
        if not on:
            fails.append("skupinové tlačítko po klepnutí nesvítí (tool=%s)" % st["tool"])

        # --- otevřít okno noty ----------------------------------------------
        mk = await h.ev(center("[...document.querySelectorAll('.ap-nota-row .ap-tool')]"
                               ".find(e => (e.title||'').startsWith('Vkládání not'))"))
        await tap(h, mk["x"], mk["y"])
        await asyncio.sleep(0.4)
        p = await h.free_point(0.55, 0.8)
        await tap(h, p["x"], p["y"])
        await h.wait_for("!!document.querySelector('.ti-note-body')", timeout=10, label="dialog noty")
        await asyncio.sleep(0.4)

        # --- Velikost v okně není + dialog otevírá s předvybranou notou -----
        d = await h.ev("""(() => {
          const c = document.querySelector('.text-input-card');
          const labels = [...c.querySelectorAll('.ti-size-label')].map(e => e.textContent.trim());
          const on = c.querySelector('.dyn-btn.on');
          return { labels, vybrana: on ? on.title : null,
                   maVelikost: labels.includes('Velikost'),
                   nazev: [...c.querySelectorAll('.ti-note')].map(e => e.textContent.trim()) };
        })()""")
        print("3) popisky v okně:", d["labels"], "| vybraná dlaždice:", d["vybrana"])
        if d["maVelikost"]:
            fails.append("v okně noty je pořád „Velikost“")
        if d["nazev"]:
            fails.append("dole je pořád název noty: %s" % d["nazev"])
        if not d["vybrana"]:
            fails.append("dialog neotevírá s předvybranou notou")

        # --- tři volby umístění linek ---------------------------------------
        plus = await h.ev(center("[...document.querySelectorAll('.text-input-card .ti-size-btn')]"
                                 ".find(e => e.title && e.title.includes('Přidat pomocnou'))"))
        await tap(h, plus["x"], plus["y"])
        await asyncio.sleep(0.5)
        rows = await h.ev("""(() => {
          const c = document.querySelector('.text-input-card');
          const chips = [...c.querySelectorAll('.ti-toggle')]
            .filter(e => ['Nahoru','Dolů','Nota v mezeře','Mezera'].some(t => (e.textContent||'').trim().startsWith(t)));
          const tops = chips.map(e => Math.round(e.getBoundingClientRect().top));
          return { count: chips.length, tops, oneLine: new Set(tops).size === 1,
                   labels: chips.map(e => (e.textContent||'').trim()) };
        })()""")
        print("3) volby umístění linek:", rows)
        # screenshot okna se zapnutou pomocnou linkou (na posouzení očima)
        import base64
        card = await h.ev("(() => { const r = document.querySelector('.text-input-card')"
                          ".getBoundingClientRect();"
                          " return {x: r.left, y: r.top, w: r.width, h: r.height}; })()")
        shot = await h.cdp("Page.captureScreenshot", {"format": "png", "clip": {
            "x": card["x"], "y": card["y"], "width": card["w"],
            "height": card["h"], "scale": 2}})
        open("/tmp/note-linky.png", "wb").write(base64.b64decode(shot["data"]))
        print("   screenshot → /tmp/note-linky.png")
        if rows["count"] < 3:
            fails.append("volby umístění linek nejsou 3 (je %d)" % rows["count"])
        elif not rows["oneLine"]:
            fails.append("volby umístění linek nejsou na jednom řádku (topy %s)" % rows["tops"])

        # --- 2. Uložit ------------------------------------------------------
        ok = await h.ev(center("[...document.querySelectorAll('.ti-actions .jp-btn')]"
                               ".find(e => (e.textContent||'').trim() === 'Uložit')"))
        await tap(h, ok["x"], ok["y"])
        await asyncio.sleep(1.2)
        after = await h.ev("""(() => ({ overlay: !!document.querySelector('.text-input-overlay'),
                                        editbar: !!document.querySelector('.edit-bar'),
                                        dbg: window.__navdbg() }))()""")
        print("2) po Uložit: overlay=%s editbar=%s tool=%r editingAnnotationId=%r not=%d"
              % (after["overlay"], after["editbar"], after["dbg"]["tool"],
                 after["dbg"]["editingAnnotationId"], after["dbg"]["annotCount"]))
        if after["overlay"]:
            fails.append("okno po Uložit nezmizelo")
        if after["dbg"]["annotCount"] != 1:
            fails.append("nota se nevložila (not=%d)" % after["dbg"]["annotCount"])

    print("VÝSLEDEK:", "OK" if not fails else "CHYBY: " + "; ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
