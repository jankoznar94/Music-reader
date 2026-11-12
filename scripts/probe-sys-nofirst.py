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
# URL appky z prostředí — bez toho sonda míří na výchozích 5173, kde neběží
# server, zůstane na about:blank a spadne na „IndexedDB denied“ (past harnessu).
APP = os.environ.get("APP_URL") or os.environ.get("NOTY_APP")


async def main():
    ok = m.Check()
    async with (m.Harness(url=APP) if APP else m.Harness()) as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=PDF)
        await h.wait_for("!!(window.__barDev && window.__barDev.song)", 60, "app")

        # 1) SYSTÉM BEZ INDEXU: musí navázat na poslední index a očíslovat i první takt
        # Klepnutý bod se NEBERE od oka — systém se najde detekcí celé stránky
        # (`detectPageSystems`, stejně jako to dělá fillSystemAt) a klepe se do
        # jeho středu. Dřív tu byl odhad (300, 290) b, který na jiném PDF padl
        # mimo osnovu („nenašel jsem linky osnov“) a sonda hlásila chybu funkce.
        r = json.loads(await h.ev("""(async () => {
            const d = window.__barDev;
            const s = await d.layerScale(0);
            const { width: pw, height: ph } = await d.getPageWidthHeight(d.song, 1);
            const PPT = 5, MAX = 12e6;   // stejné rozlišení detekce jako fillSystemAt
            let W = pw * PPT, H = ph * PPT;
            const area = W * H; if (area > MAX) { const k = Math.sqrt(MAX / area); W *= k; H *= k; }
            const cv = document.createElement('canvas');
            await d.renderPageRegion(d.song, 1, cv, { x: 0, y: 0, w: pw, h: ph }, W, H, { dpr: 1 });
            const dpg = d.detectPageSystems(cv, cv.width / pw, { krok: 4 });
            const sys = (dpg.systems || []).filter(x => x.ok && x.bars >= 3)[0];
            if (!sys) return JSON.stringify({ reason: dpg.reason || 'žádný systém', n: (dpg.systems || []).length,
              sys0: (dpg.systems || []).map(x => ({ ok: x.ok, bars: x.bars, staves: x.staves, top: Math.round(x.sysTop), bot: Math.round(x.sysBot), reason: x.reason })) });
            // index 39 nad PRVNÍM použitelným systémem (stránka 0), vlevo nad osnovou
            d.annotations.value.items.push({ id: 'seed1', page: 0, tool: 'text', barNum: true,
              text: '39', size: 12, color: '#000', opacity: 1, border: false,
              x: 40 * s, y: (sys.sysTop - 12) * s });
            const cy = (sys.sysTop + sys.sysBot) / 2;
            await d.fillSystemAt({ x: Math.min(pw * 0.5, 300) * s, y: cy * s });
            const p = d.barFillPreview.value;
            return JSON.stringify(p ? { start: p.start, first: p.first, src: p.firstSrc,
              n: p.items.length, xs: p.items.map(i => Math.round(i.x / s)) }
              : { reason: d.toast.value, sys: { top: sys.sysTop, bot: sys.sysBot, bars: sys.bars } });
        })()""", await_promise=True))
        print("  preview:", r)
        if r and "first" in r:
            ok("navázal na poslední index (39)", r["first"] == 40, r)
            ok("první takt systému je očíslován", r["n"] >= 3, r)
            ok("číslo 1. taktu leží u levého okraje systému", r["xs"][0] < 100, r["xs"])
        else:
            # Stránka 1 zvoleného PDF nemá detekovatelné osnovy (např. titulní
            # strana 600dpi skenu) — dočíslování nemá co měřit. SKIP, ne zelené
            # „prošlo“: sonda to řekne nahlas, ať se to neplete s ověřenou funkcí.
            print("SKIP  dočíslování systému —", (r or {}).get("reason"), "| stránka bez osnov")
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
        # Jan (listopad 2026): režim se NESMÍ vypnout po výběru — jinak ho musí
        # po každém smazaném indexu znovu zapínat.
        ok("režim výběru zůstává po výběru zapnutý", not st["selOff"], st)
        # označení musí být U TOHO čísla, ne jinde na stránce
        near = (st.get("geo") and abs((st["geo"]["x"] + st["geo"]["w"] / 2) - pt["x"]) < 60
                and abs((st["geo"]["y"] + st["geo"]["h"] / 2) - pt["y"]) < 60)
        ok("označení leží u vybraného čísla", bool(near), {"geo": st.get("geo"), "tap": pt})
        ok.report()
        return 0 if not ok.failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
