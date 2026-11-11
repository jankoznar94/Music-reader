#!/usr/bin/env python3
# Dočíslování SYSTÉMU bez vytištěného indexu + vizuální označení vybraného indexu.
# NOTY_PDF=/tmp/cherub_small.pdf APP_URL=http://localhost:5173/ \
#   scripts/run-probe-fresh.sh scripts/probe-sys-nofirst.py
import asyncio, importlib.util, json, os, sys

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
PDF = os.environ.get("NOTY_PDF", "/tmp/cherub_small.pdf")


async def main():
    ok = m.Check()
    async with m.Harness() as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=PDF)
        await h.wait_for("!!(window.__barDev && window.__barDev.song)", 60, "app")

        # 1) SYSTÉM BEZ INDEXU: musí navázat na poslední index a očíslovat i první takt
        r = json.loads(await h.ev("""(async () => {
            const d = window.__barDev;
            const s = await d.layerScale(0);
            // index 39 nad PRVNÍM systémem (stránka 0), vlevo nad osnovou
            d.annotations.value.items.push({ id: 'seed1', page: 0, tool: 'text', barNum: true,
              text: '39', size: 12, color: '#000', opacity: 1, border: false,
              x: 40 * s, y: 26 * s });
            await d.fillSystemAt({ x: 300 * s, y: 290 * s });
            const p = d.barFillPreview.value;
            return JSON.stringify(p ? { start: p.start, first: p.first, src: p.firstSrc,
              n: p.items.length, xs: p.items.map(i => Math.round(i.x / s)) } : null);
        })()""", await_promise=True))
        print("  preview:", r)
        ok("navázal na poslední index (39)", r and r["first"] == 40, r)
        ok("první takt systému je očíslován", r and r["n"] >= 3, r)
        ok("číslo 1. taktu leží u levého okraje systému",
           r and r["xs"][0] < 100, r["xs"] if r else None)
        # náhled zruš, ať do výběru indexu nezasahuje
        await h.ev("(() => { window.__barDev.barFillPreview.value = null; })()")

        # 2) VYBRANÝ INDEX SE V NOTÁCH OZNAČÍ
        # Okno číslování otevři (potřebuje ho viditelnost označení) a najdi bod,
        # který OPRAVDU trefí anotační vrstvu — panel číslování kryje levý horní roh.
        # POZOR: `free_point()` hledá `elementFromPoint == .annot-layer`, takže
        # musí být anotační režim ZAPNUTÝ — jinak vrátí None (vrstva je
        # pointer-events:none a elementFromPoint vidí plátno pod ní).
        await h.ev("(() => { const d = window.__barDev;"
                   " if (!d.barnumMode.value) d.toggleBarnum(); })()")
        await asyncio.sleep(0.6)
        pt = await h.free_point(0.45, 0.85)
        if not pt:
            ok("volný bod pro klepnutí", False, None)
            ok.report()
            return 1
        seed = json.loads(await h.ev("""(() => {
            const d = window.__barDev;
            if (!d.barnumMode.value) d.toggleBarnum();
            const svg = document.querySelector('svg.annot-layer');
            const r = svg.getBoundingClientRect();
            const vb = svg.viewBox.baseVal;
            const sx = %s, sy = %s;
            // obrazovka -> souřadnice vrstvy (viewBox), stejně jako toLayerCoords
            const lx = vb.x + (sx - r.left) * vb.width / r.width;
            const ly = vb.y + (sy - r.top) * vb.height / r.height;
            // číslo taktu polož tak, aby klepnutý bod ležel UVNITŘ jeho rámečku
            const it = { id: 'seed2', page: d.currentPage.value, tool: 'text', barNum: true,
              text: '77', size: 14, color: '#000', opacity: 1, border: false,
              x: lx - 4, y: ly + 5 };
            const old = d.annotations.value.items.findIndex(i => i.id === 'seed2');
            if (old >= 0) d.annotations.value.items.splice(old, 1);
            d.annotations.value.items.push(it);
            d.editingId.value = null;
            d.barSelArmed.value = true;
            return JSON.stringify({ lx, ly, page: d.currentPage.value });
        })()""" % (pt["x"], pt["y"])))
        await asyncio.sleep(0.5)
        hit = json.loads(await h.ev(
            "(() => { const el = document.elementFromPoint(%s, %s);"
            " const inLayer = !!(el && el.closest && el.closest('.annot-layer'));"
            " const panel = !!(el && el.closest && el.closest('.barnum-panel'));"
            " return JSON.stringify({ tag: el && el.tagName, layer: inLayer, panel }); })()"
            % (pt["x"], pt["y"])))
        print("  cíl klepnutí:", hit, "seed:", seed)
        # klepnutí smí trefit i <text>/<rect> UVNITŘ vrstvy, ale nikdy panel
        ok("klepnutí míří do anotační vrstvy (ne na panel)",
           hit and hit.get("layer") and not hit.get("panel"), hit)

        await h.finger_tap(pt["x"], pt["y"])
        await asyncio.sleep(0.6)
        st = json.loads(await h.ev("""(() => {
            const d = window.__barDev;
            const box = document.querySelector('.barnum-selected');
            let geo = null;
            if (box) {
              const rr = box.getBoundingClientRect();
              geo = { x: Math.round(rr.x), y: Math.round(rr.y),
                      w: Math.round(rr.width), h: Math.round(rr.height) };
            }
            const it = d.annotations.value.items.find(i => i.id === 'seed2');
            return JSON.stringify({ editing: !!(d.editingId.value && d.editingId.value === 'seed2'),
              marked: !!box, geo, text: it && it.text,
              selOff: !d.barSelArmed.value, toast: d.toast.value });
        })()"""))
        print("  výběr:", st)
        ok("index se vybral", st["editing"], st)
        ok("vybraný index je v notách označený", st["marked"], st)
        ok("režim výběru se po výběru vypnul", st["selOff"], st)
        # označení musí být U TOHO čísla, ne jinde na stránce
        near = (st.get("geo") and abs((st["geo"]["x"] + st["geo"]["w"] / 2) - pt["x"]) < 60
                and abs((st["geo"]["y"] + st["geo"]["h"] / 2) - pt["y"]) < 60)
        ok("označení leží u vybraného čísla", bool(near), {"geo": st.get("geo"), "tap": pt})
        ok.report()
        return 0 if not ok.failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
