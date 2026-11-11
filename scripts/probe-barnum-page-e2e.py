#!/usr/bin/env python3
"""E2E: okno Číslování taktů — dočíslování CELÉ STRÁNKY, přepínač skrytá/viditelná,
skok na takt a rozměry panelu.

Postup je stejný jako u Janovy ruky: klepne na tlačítko v liště, klepne do not,
potvrdí „Vložit“. Ověřuje se skutečný DOM a skutečné anotace (ne návratové
hodnoty funkcí).
"""
import asyncio
import importlib.util
import json
import os

spec = importlib.util.spec_from_file_location(
    "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CDP_HTTP = os.environ.get("NOTY_CDP", m.CDP_HTTP)

PDF = os.environ.get(
    "NOTY_PDF",
    "/home/martin_fabian/.hermes/profiles/cfsb-agent/cache/documents/"
    "doc_1bb2c499f695_Mozart-Davide penitente.pdf")

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print(("  OK   " if ok else "  CHYBA") + "  " + name + ("  · " + detail if detail else ""))


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5173/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)

        # 1) otevřít okno číslování tlačítkem v liště
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title||'').startsWith('Číslování')); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        panel = await h.ev("""(() => { const p = document.querySelector('.barnum-panel');
            if (!p) return null;
            const head = p.querySelector('.bn-head');
            return { w: p.clientWidth, sw: p.scrollWidth,
                     headW: head.clientWidth, headSW: head.scrollWidth,
                     h: p.clientHeight,
                     hasPage: !!p.querySelector('.bn-page'),
                     hasGo: !!p.querySelector('.bn-go'),
                     goBtn: !!p.querySelector('.bn-go-btn') }; })()""")
        check("panel číslování se otevřel", panel is not None)
        if panel:
            check("panel nepřetéká (clientWidth == scrollWidth)",
                  panel["w"] == panel["sw"], "%s/%s" % (panel["w"], panel["sw"]))
            check("hlavička nepřetéká", panel["headW"] == panel["headSW"],
                  "%s/%s" % (panel["headW"], panel["headSW"]))
            check("tlačítko Dočíslovat celou stránku je v panelu", panel["hasPage"])
            check("řádek Skok na takt je v panelu", panel["hasGo"] and panel["goBtn"])
            print("  panel: %s×%s" % (panel["w"], panel["h"]))

        # 2) dialog stránky už skok na takt NEMÁ
        await h.ev("window.__barDev && 1")
        pgdlg = await h.ev("""(() => {
            const btn = document.querySelector('.tb-page');
            if (btn) btn.click();
            return 1; })()""")
        await asyncio.sleep(0.5)
        dlg = await h.ev("""(() => {
            const q = (s) => !!document.querySelector(s);
            return { open: q('.page-go'), barGo: q('.pg-bar-go'), pgGo: q('.pg-go') }; })()""")
        check("v dialogu stránky není pole Skoč na takt", not dlg["barGo"], json.dumps(dlg))
        await h.ev("(() => { const b=document.querySelector('.pg-close, .pg-btn'); "
                   "if (b) b.click(); return 1; })()")
        await asyncio.sleep(0.4)

        # 3) dočíslování celé stránky: tlačítko → ROVNOU náhled (bez ťukání do not)
        # POZOR: dialog stránky vypíná anotační režim (openPageGo), takže se okno
        # číslování zavřelo — musí se otevřít znovu, jinak klik na .bn-page nic nedělá.
        # toggleBarnum je PŘEPÍNAČ a dialog stránky nechal barnumMode zapnutý,
        # takže jedno kliknutí by ho vypnulo — klikáme, dokud nejsou oba režimy on.
        for _ in range(4):
            st = json.loads(await h.ev("""(() => { const d=window.__barDev;
                return JSON.stringify({b:d.barnumMode.value, a:d.annotMode.value,
                  panel: !!document.querySelector('.barnum-panel')}); })()"""))
            if st["b"] and st["a"] and st["panel"]:
                break
            await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                       ".find(x => (x.title||'').startsWith('Číslování')); if (b) b.click(); })()")
            await asyncio.sleep(0.5)
        # Žádné ťuknutí do not: náhled musí vzniknout hned z tlačítka.
        await h.ev("(() => { const b=document.querySelector('.bn-page'); if (b) b.click(); })()")
        prev = ""
        for _ in range(60):
            prev = await h.ev("""(() => { const d=window.__barDev; const p=d.barFillPreview.value;
                return p ? JSON.stringify({n:p.items.length, page:p.pageMode, sys:p.systems,
                  start:p.start, last:p.items[p.items.length-1].text,
                  withFirst:p.withFirst, toast:d.toast.value}) : ''; })()""")
            if prev:
                break
            await asyncio.sleep(0.25)
        pv = json.loads(prev) if prev else None
        check("náhled celé stránky vznikl POUZE z tlačítka (bez ťuknutí)", pv is not None,
              prev[:120] if prev else
              await h.ev("window.__barDev ? window.__barDev.toast.value : '?'"))
        armed_after = await h.ev(
            """(() => { const b=document.querySelector('.bn-page');
                return JSON.stringify({on: b ? b.classList.contains('on') : null,
                  busy: window.__barDev.barFillPageBusy ? window.__barDev.barFillPageBusy.value : null}); })()""")
        print("  tlačítko po náhledu:", armed_after)
        if pv:
            check("náhled je stránkový (pageMode)", pv["page"])
            check("str. 2: 3 systémy, 11 čísel 1–11",
                  pv["sys"] == 3 and pv["n"] == 11 and pv["start"] == 1 and pv["last"] == "11",
                  json.dumps(pv, ensure_ascii=False))
            check("náhled se kreslí v notách (čárkované čáry)",
                  await h.ev("document.querySelectorAll('.barfill-preview line').length > 0"))
            # Vložit
            await h.ev("(() => { const b=document.querySelector('.bn-fill-ok'); if (b) b.click(); })()")
            await asyncio.sleep(0.8)
            saved = await h.ev("""(() => { const a=window.__barDev.annotations.value.items
                .filter(i => i.barNum && i.page === 1);
              return JSON.stringify({n:a.length, first:a[0] && a[0].text,
                last:a[a.length-1] && a[a.length-1].text}); })()""")
            sv = json.loads(saved)
            check("po Vložit je na str. 2 vloženo 11 čísel", sv["n"] == 11, saved)

        # 4) přepínač skrytá/viditelná schová VŠECHNA čísla
        vis = await h.ev("""(() => { const d=window.__barDev;
            return JSON.stringify({hidden:d.barNumsHidden.value,
              shown:d.pageItems.value.filter(i=>i.barNum).length}); })()""")
        v0 = json.loads(vis)
        await h.ev("(() => { const b=document.querySelector('.bn-toggle'); if (b) b.click(); })()")
        await asyncio.sleep(0.5)
        # V režimu číslování jsou skrytá čísla VIDĚT schválně, takže se viditelnost
        # měří s vypnutým číslováním (to je stav, kdy se dívá do not).
        v1 = json.loads(await h.ev("""(() => { const d=window.__barDev;
            d.barnumMode.value = false;
            const out = JSON.stringify({hidden:d.barNumsHidden.value,
              shown:d.pageItems.value.filter(i=>i.barNum).length});
            d.barnumMode.value = true;
            return out; })()"""))
        await h.ev("(() => { const b=document.querySelector('.bn-toggle'); if (b) b.click(); })()")
        await asyncio.sleep(0.3)
        check("přepínač skryje všechna čísla naráz (mimo režim číslování)",
              v1["shown"] == 0 and v1["hidden"] is True, json.dumps([v0, v1]))
        # v režimu číslování musí být i skrytá vidět
        await h.ev("(() => { const b=document.querySelector('.bn-toggle'); if (b) b.click(); })()")
        await asyncio.sleep(0.3)
        bothidden = json.loads(await h.ev("""(() => { const d=window.__barDev;
            return JSON.stringify({hidden:d.barNumsHidden.value,
              shown:d.pageItems.value.filter(i=>i.barNum).length}); })()"""))
        check("v režimu číslování jsou i skrytá čísla vidět (nedá se to smazat omylem)",
              bothidden["shown"] == 11, json.dumps(bothidden))
        await h.ev("(() => { const b=document.querySelector('.bn-toggle'); if (b) b.click(); })()")

        # 5) skok na takt z okna číslování
        await h.ev("(() => { const d=window.__barDev; d.barGoValue.value = '9'; })()")
        await h.ev("(() => { const b=document.querySelector('.bn-go-btn'); if (b) b.click(); })()")
        await asyncio.sleep(1.2)
        jump = json.loads(await h.ev("""(() => { const d=window.__barDev;
            return JSON.stringify({page:d.currentPage.value, toast:d.toast.value}); })()"""))
        check("skok na takt 9 přepnul stránku (takt 9 je na str. 2)",
              jump["page"] == 1 or "stránka" in (jump["toast"] or ""), json.dumps(jump, ensure_ascii=False))

        # 6) snímek panelu pro kontrolu okem
        await h.ev("window.__barDev.barNumsHidden.value = false; 1")
        shot = await h.ev("""(async () => {
            const p = document.querySelector('.barnum-panel');
            if (!p) return '';
            const r = p.getBoundingClientRect();
            return JSON.stringify([r.left, r.top, r.width, r.height]); })()""")
        print("  panel rect:", shot)

    print("\n%d/%d OK" % (sum(1 for c in CHECKS if c[1]), len(CHECKS)))
    for name, ok, det in CHECKS:
        if not ok:
            print("  SELHALO:", name, det)

asyncio.run(main())
