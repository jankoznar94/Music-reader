#!/usr/bin/env python3
"""E2E: „Dočíslovat systém“ na SKUTEČNÉM PDF — čísla musí sednout na takty.

Proč: detekci lze měřit naslepo (probe-barline-detect.py), ale uživatel klepne
do stránky a dostane NÁHLED. Test proto projde celou cestu appky: nahraje PDF,
otevře skladbu, nastaví 1. takt a Krok, klepne na systém (skutečný dotykový
event) a zkontroluje, že náhled má `Krok − 1` čísel, první číslo je
`1. takt + 1`, čísla stojí na skutečných vnitřních čarách a po potvrzení se
„Další“ posune na `1. takt + Krok`.

Pozn.: nahrání souboru přes `DOM.setFileInputFiles` tady na Chrome 149 vrací
0 souborů (input má atribut `hidden`), proto se soubor podává stejně jako
z reálného `change` eventu — přes `DataTransfer` v JS. Ověřuje se počet
`input.files.length`, ne „předpokládám, že to prošlo“.

Předpoklad: vite na 5173 + Chrome s --remote-debugging-port=9222.

Použití:
  python3 scripts/probe-barfill-e2e.py --pdf scripts/fixtures/ave.pdf \
      --krok 8 --first 8 --ypt 427 --expect 132,191,251,311,371,432,492
"""
import argparse
import asyncio
import base64
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "cdp_harness", os.path.join(HERE, "..", "cdp-e2e-harness.py"))
hh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hh)
hh.CDP_HTTP = "http://127.0.0.1:9222"
Harness = hh.Harness

LAYER = """(() => {
  const svg = document.querySelector('.annot-layer');
  if (!svg) return null;
  const r = svg.getBoundingClientRect();
  const vb = svg.viewBox.baseVal;
  return { left: r.left, top: r.top, w: r.width, h: r.height,
           vbx: vb.x, vby: vb.y, vbw: vb.width, vbh: vb.height };
})()"""


async def upload(h, path):
    b64 = base64.b64encode(open(path, "rb").read()).decode()
    n = await h.ev("""(() => { const bin = atob(%s); const u = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
      const dt = new DataTransfer();
      dt.items.add(new File([u], %s, {type: 'application/pdf'}));
      const el = document.querySelectorAll('input[type=file]')[0];
      el.files = dt.files;
      const n = el.files.length;
      el.dispatchEvent(new Event('change', {bubbles: true}));
      return n; })()""" % (json.dumps(b64), json.dumps(os.path.basename(path))))
    return n


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default="scripts/fixtures/ave.pdf")
    ap.add_argument("--krok", type=int, default=8)
    ap.add_argument("--first", type=int, default=8)
    ap.add_argument("--ypt", type=float, default=427)
    ap.add_argument("--xpt", type=float, default=300)
    ap.add_argument("--expect", default="")
    a = ap.parse_args()
    expect = [float(v) for v in a.expect.split(",") if v.strip()]
    pdf = os.path.abspath(a.pdf)
    res = {"pdf": os.path.basename(pdf), "krok": a.krok, "first": a.first, "checks": []}

    def chk(name, ok, detail=""):
        res["checks"].append({"name": name, "ok": (None if ok is None else bool(ok)),
                              "detail": str(detail)})
        print(("  OK   " if ok else ("  =    " if ok is None else "  FAIL "))
              + name + (" — " + str(detail) if detail else ""))

    async with Harness() as h:
        await h.set_tablet()
        await h.open()
        # čistá IndexedDB: jinak se sčítají čísla z předchozího běhu a test lže
        await h.ev("indexedDB.deleteDatabase('noty-app')")
        await asyncio.sleep(0.8)
        await h.open()
        if not await h.ev("!!document.querySelector('input[type=file]')"):
            chk("knihovna s nahráváním", False, "chybí input[type=file]")
            return finish(res)
        n = await upload(h, pdf)
        chk("PDF nahráno", n == 1, n)
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=60, label="PDF upload")
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0",
                         timeout=15, label="autoři")
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="čtečka")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="stránka")
        await asyncio.sleep(1.2)
        chk("skladba otevřená", True, await h.page_text())

        await h.ev("(() => { const b = [...document.querySelectorAll('.tb-btn')]"
                   ".find(x => /Číslování taktů/.test(x.title || '')); if (b) b.click();"
                   " return !!b; })()")
        await asyncio.sleep(0.8)
        if not await h.ev("!!document.querySelector('.barnum-panel')"):
            await h.annot_toggle()
            await asyncio.sleep(0.6)
        chk("panel Číslování taktů otevřený", await h.ev("!!document.querySelector('.barnum-panel')"))
        if not await h.ev("!!document.querySelector('.barnum-panel')"):
            return finish(res)

        await h.ev("(() => { const i = document.querySelectorAll('.bn-input');"
                   " i[0].value = %d; i[0].dispatchEvent(new Event('change', {bubbles:true}));"
                   " i[1].value = %d; i[1].dispatchEvent(new Event('change', {bubbles:true}));"
                   " return true; })()" % (a.first, a.krok))
        await asyncio.sleep(0.3)
        vals = await h.ev("[...document.querySelectorAll('.bn-input')].map(i => i.value)")
        chk("nastaven 1. takt a Krok", vals == [str(a.first), str(a.krok)], vals)

        geo = await h.ev(LAYER)
        chk("vrstva anotací nalezena", bool(geo))
        if not geo:
            return finish(res)
        cx = geo["left"] + (a.xpt - geo["vbx"]) * geo["w"] / geo["vbw"]
        cy = geo["top"] + (a.ypt - geo["vby"]) * geo["h"] / geo["vbh"]

        await h.click(".bn-fill")
        await asyncio.sleep(0.4)
        chk("režim Dočíslovat zapnutý", await h.ev("!!document.querySelector('.bn-fill.on')"))
        await h.finger_tap(cx, cy, r=12)
        try:
            await h.wait_for("(() => { const r = window.__barDev && window.__barDev.barFillPreview;"
                             " const pp = r && r.value !== undefined ? r.value : r;"
                             " return !!(pp && pp.items && pp.items.length); })()",
                             timeout=30, label="náhled dočíslování")
        except TimeoutError:
            diag = await h.ev("(document.querySelector('.bn-diag')||{}).textContent || ''")
            dbg = await h.ev("JSON.stringify((((window.__barPickDbg||[]).filter(x=>x.fill).pop()||{}).fill||{}).dbg||null)")
            chk("náhled vznikl", False, diag)
            print("     det.dbg =", dbg)
            return finish(res)

        pv = await h.ev("""(() => { const r = window.__barDev.barFillPreview;
          const pp = (r && r.value !== undefined) ? r.value : r;
          if (!pp) return null;
          return { bars: pp.bars, first: pp.first, start: pp.start,
                   items: (pp.items || []).map(i => ({ text: i.text, x: i.x, y: i.y })) }; })()""")
        scale = await h.ev("""(async () => { const v = await window.__barDev.layerScale(window.__barDev.currentPage);
          if (typeof v === 'number') return v;
          if (v && typeof v.value === 'number') return v.value;
          if (v && typeof v.s === 'number') return v.s;
          return null; })()""")
        bars = pv.get("bars") or 0
        texts = [it["text"] for it in pv.get("items", [])]
        res["scale"] = scale
        res["geo"] = geo
        # Vrstva má souřadnice v pixelech CSS (viewBox = plocha plátna), takže
        # „bod PDF“ = x / (šířka vrstvy / šířka stránky); číslo je posunuté
        # o +1,5 b za čarou, proto se to odečítá.
        lay = geo["w"] / 595.0
        xs = [round(it["x"] / lay - 1.5, 1) for it in pv.get("items", [])]
        res["layerScale"] = round(lay, 4)
        res["preview"] = {"bars": bars, "texts": texts, "lines": xs}
        # POČET ČÍSEL SE NEŘÍDÍ „Krokem" — appka takty spočítá z čar. Krok je
        # jen kontrola, takže očekávaný počet bereme z ověřených pozic čar.
        want_n = len(expect) if expect else a.krok - 1
        chk("náhled vznikl", True, f"bars={bars}")
        chk("počet čísel = počet nalezených čar", bars == want_n, f"{bars} vs {want_n}")
        chk("první číslo = 1. takt + 1", texts[:1] == [str(a.first + 1)], texts[:2])
        chk("poslední číslo = 1. takt + počet čar",
            texts[-1:] == [str(a.first + want_n)], texts[-1:])
        pv_mis = await h.ev("""(() => { const r = window.__barDev.barFillPreview;
          const pp = (r && r.value !== undefined) ? r.value : r;
          return pp ? !!pp.mismatch : null; })()""")
        if a.krok >= 2:
            chk("nesouhlas s Krokem je označený", pv_mis == (a.krok - 1 != want_n), pv_mis)
        if expect:
            bad = [(v, e) for v, e in zip(xs, expect) if abs(v - e) > 3]
            chk("čísla stojí na vnitřních čarách",
                len(xs) == len(expect) and not bad, f"{xs} | mimo: {bad}")

        await h.click(".bn-fill-ok")
        await asyncio.sleep(1.0)
        nxt = await h.ev("Number(document.querySelectorAll('.bn-input')[0].value)")
        chk("Další = 1. takt + počet čar", nxt == a.first + want_n + 1, nxt)
        cnt = await h.ev("""(() => { const r = window.__barDev.annotations;
          const a = (r && r.value !== undefined) ? r.value : r;
          const items = (a && a.items) || [];
          return items.filter(x => x && x.barNum).length; })()""")
        chk("uloženo tolik čísel, kolik bylo v náhledu", cnt == bars, cnt)
    return finish(res)


def finish(res):
    bad = [c for c in res["checks"] if c["ok"] is False]
    print("\nSOUHRN: %d/%d OK" % (len(res["checks"]) - len(bad), len(res["checks"])))
    with open("/tmp/barfill-e2e.json", "w") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    sys.exit(1 if bad else 0)


asyncio.run(main())
