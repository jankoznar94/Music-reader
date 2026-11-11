#!/usr/bin/env python3
# Oindexování celého PDF vytištěnými čísly taktů — reálný běh na malém výřezu
# 600dpi Cherubiniho (tištěné stránky 11, 12, 13 = PDF 12, 13, 14).
# Ověřuje: nalezená čísla, monotonii, vložení skrytých indexů a to, že se
# jednorázové režimy vypnou při změně nástroje.
#
# NOTY_PDF=/tmp/cherub_small.pdf APP_URL=http://localhost:5173/ \
#   scripts/run-probe-fresh.sh scripts/probe-index-all.py
import asyncio, importlib.util, json, os, sys, time

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)
Harness, Check = m.Harness, m.Check

PDF = os.environ.get("NOTY_PDF", "/tmp/cherub_small.pdf")


async def main():
    ok = Check()
    async with Harness() as h:
        await h.open()
        await h.set_tablet()
        await h.open_song(pdf=PDF)
        await h.wait_for("!!(window.__barDev && window.__barDev.song)", 60, "app")
        dev = await h.ev("!!window.__barDev")
        ok("dev rozhraní dostupné", bool(dev))

        # 1) samotné skenování (bez zápisu)
        diag = await h.ev("""(async () => {
            const d = window.__barDev; const out = [];
            await d.warmOcr();
            for (let p = 0; p < 3; p++) {
              try {
                const s = await d.layerScale(p);
                let pw = 595, ph = 842;
                try { const g = await d.getPageWidthHeight(d.song, p + 1); if (g && g.width) { pw = g.width; ph = g.height; } } catch (e) {}
                const cv = document.createElement('canvas');
                await d.renderPageRegion(d.song, p + 1, cv, { x: 0, y: 0, w: pw, h: ph }, pw * 5 / (window.devicePixelRatio || 1), ph * 5 / (window.devicePixelRatio || 1));
                const dpg = d.detectPageSystems(cv, cv.width / pw, {});
                const f = await d.findPrintedBarNumbersOnPage(p);
                out.push({ p, s: +s.toFixed(3), cv: [cv.width, cv.height], ppt: +(cv.width / pw).toFixed(2),
                           systems: (dpg.systems || []).length, staves: dpg.staves,
                           firstBar: (dpg.systems || []).map(x => [Math.round(x.openingPt == null ? -1 : x.openingPt), +(x.spacePt || 0).toFixed(1), Math.round(x.sysTop)]),
                           found: f.map(x => [x.n, x.src]) });
              } catch (e) { out.push({ p, err: String(e && e.message || e) }); }
            }
            return JSON.stringify(out);
        })()""", await_promise=True)
        print("  po stránkách:", diag)
        dbg = await h.ev("""(async () => {
            const d = window.__barDev;
            const s = await d.layerScale(0);
            const t = performance.now();
            const p1 = { x: 146.4 * s, y: 24 * s };
            let r1 = null, e1 = null;
            try { r1 = await d.ocrBarNumberAt ? null : null; } catch (e) { e1 = String(e); }
            return JSON.stringify({ hasFn: typeof d.ocrBarNumberAt, s: +s.toFixed(3), dbg: (window.__barPickDbg || []).slice(-3) });
        })()""", await_promise=True)
        print("  diag2:", dbg)
        t0 = time.time()
        res = await h.ev("""(async () => {
            const d = window.__barDev;
            await d.indexAllPdf();
            const p = d.barIndexPreview.value;
            return JSON.stringify(p ? { n: p.items.length, first: p.first, last: p.last,
              pages: p.pages, items: p.items.map(i => [i.page, i.n, i.src]) } : null);
        })()""", await_promise=True)
        pv = json.loads(res) if res else None
        print("  náhled:", json.dumps(pv, ensure_ascii=False), f"({time.time()-t0:.1f} s)")
        ok("něco nalezeno", bool(pv and pv["n"]), pv)
        nums = [it[1] for it in (pv or {}).get("items", [])]
        ok("čísla rostou", nums == sorted(nums) and len(nums) == len(set(nums)), nums)
        ok("skok v rozumném rozsahu", all(1 <= b - a <= 64 for a, b in zip(nums, nums[1:])), nums)
        # Pozn.: míra nalezení u SKENU je zatím nízká (OCR drobných číslic),
        # proto se tu netvrdí počet stran, jen že něco prošlo celou cestou.
        print("  stran s indexem:", (pv or {}).get("pages"))

        # 2) vložení (indexy se opravdu uloží)
        before = await h.ev("window.__barDev.annotations.value.items.filter(i=>i.barNum).length")
        await h.ev("window.__barDev.commitBarIndexAll(); 1")
        await asyncio.sleep(0.6)
        after = await h.ev("window.__barDev.annotations.value.items.filter(i=>i.barNum).length")
        ok("indexy vloženy", after == (pv or {}).get("n", 0), f"{before} -> {after}")

        # 3) jednorázové režimy se vypnou při změně nástroje
        st = json.loads(await h.ev("""(() => {
            const d = window.__barDev;
            d.toggleBarnum();            // otevřít okno číslování
            return JSON.stringify({ barnum: d.barnumMode.value });
        })()"""))
        ok("okno číslování otevřené", st["barnum"], st)
        await asyncio.sleep(0.5)
        sel = json.loads(await h.ev("""(() => {
            const b = document.querySelector('.bn-pick[title^="Vybrat index"]');
            if (!b) return JSON.stringify({ err: 'no-btn' });
            b.click();
            return JSON.stringify({ clicked: true });
        })()"""))
        await asyncio.sleep(0.5)
        armed = await h.ev("!!window.__barDev.barSelArmed.value")
        ok("výběr indexu se zapnul", armed, armed)
        # přepnout nástroj = musí se vypnout
        await h.ev("""(() => {
            const d = window.__barDev;
            d.toggleBarnum();            // zavřít okno = konec režimů
            d.toggleBarnum();            // a znovu otevřít
            return 1;
        })()""")
        await asyncio.sleep(0.5)
        after = await h.ev("!!window.__barDev.barSelArmed.value")
        off = {"before": armed, "after": after}
        ok("výběr indexu se vypne při změně režimu", off["before"] and not off["after"], off)
        ok.report()
        return 0 if not ok.fails else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
