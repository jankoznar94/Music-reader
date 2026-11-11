#!/usr/bin/env python3
"""Náhled dočíslování CELÉ STRÁNKY: okno číslování se smrskne na Vložit/Zrušit.

Ověřuje (na reálném PDF, přes skutečné UI):
  1. před náhledem je panel plný (hlavička, řádky Další/Krok, tlačítko stránky),
  2. po kliku na „Dočíslovat celou stránku“ je z panelu VIDĚT jen potvrzovací
     řádek s Vložit/Zrušit — hlavička, počítadla, skok i hinty jsou skryté,
  3. panel se vejde na obsah (užší než před náhledem) a NIC nepřetéká
     (scrollWidth == clientWidth), tlačítka jsou uvnitř panelu,
  4. panel nekryje střed/noty víc než předtím (menší plocha),
  5. po Zrušit se panel vrátí do plné podoby,
  6. po Vložit se také vrátí a čísla jsou v anotacích.
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


STATE_JS = r"""(() => {
  const p = document.querySelector('.barnum-panel');
  if (!p) return JSON.stringify({ panel: false });
  const vis = (s) => { const e = p.querySelector(s); if (!e) return null;
    const r = e.getBoundingClientRect();
    return !!(r.width || r.height); };
  const r = p.getBoundingClientRect();
  const ok = p.querySelector('.bn-fill-ok')?.getBoundingClientRect();
  const no = p.querySelector('.bn-fill-no')?.getBoundingClientRect();
  const txt = p.querySelector('.bn-fill-q');
  const tr = txt ? txt.getBoundingClientRect() : null;
  return JSON.stringify({
    panel: true,
    previewOnly: p.classList.contains('preview-only'),
    w: p.clientWidth, sw: p.scrollWidth, h: p.clientHeight,
    rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)],
    head: vis('.bn-head'), rows: vis('.bn-row'), page: vis('.bn-page'),
    go: vis('.bn-go'), hint: vis('.bn-hint'),
    confirm: vis('.bn-fill-preview'),
    okBtn: ok ? [Math.round(ok.left), Math.round(ok.top), Math.round(ok.width), Math.round(ok.height)] : null,
    noBtn: no ? [Math.round(no.left), Math.round(no.top), Math.round(no.width), Math.round(no.height)] : null,
    txtLines: tr ? Math.round(tr.height / 12) : null,
    q: txt ? txt.textContent.trim().slice(0, 80) : null,
    toast: window.__barDev ? window.__barDev.toast.value : null,
    preview: window.__barDev && window.__barDev.barFillPreview.value
      ? { page: window.__barDev.barFillPreview.value.pageMode,
          n: window.__barDev.barFillPreview.value.items.length } : null,
  });
})()"""


async def panel_state(h):
    return json.loads(await h.ev(STATE_JS))


async def open_barnum(h):
    for _ in range(5):
        st = json.loads(await h.ev("""(() => { const d=window.__barDev;
            return JSON.stringify({b:d.barnumMode.value, a:d.annotMode.value,
              panel: !!document.querySelector('.barnum-panel')}); })()"""))
        if st["b"] and st["a"] and st["panel"]:
            return True
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x => (x.title||'').startsWith('Číslování')); if (b) b.click(); })()")
        await asyncio.sleep(0.5)
    return False


async def main():
    h = m.Harness(url=os.environ.get("NOTY_APP", "http://localhost:5199/"))
    async with h:
        await h.open()
        await h.open_song(pdf=PDF)
        await h.goto(2)
        check("okno číslování se otevřelo", await open_barnum(h))
        await asyncio.sleep(0.4)

        before = await panel_state(h)
        print("  před náhledem:", json.dumps(before, ensure_ascii=False))
        check("před náhledem je panel plný (hlavička + řádky + tlačítko stránky)",
              before["head"] and before["rows"] and before["page"], json.dumps(before, ensure_ascii=False))
        check("před náhledem není potvrzovací řádek", not before["confirm"])
        check("před náhledem panel nepřetéká", before["w"] == before["sw"],
              "%s/%s" % (before["w"], before["sw"]))

        # náhled celé stránky
        await h.ev("(() => { const b=document.querySelector('.bn-page'); if (b) b.click(); })()")
        prev = ""
        for _ in range(80):
            prev = await h.ev("""(() => { const d=window.__barDev; const p=d.barFillPreview.value;
                return p ? JSON.stringify({n:p.items.length, page:p.pageMode}) : ''; })()""")
            if prev:
                break
            await asyncio.sleep(0.25)
        check("náhled celé stránky vznikl", bool(prev), prev)
        await asyncio.sleep(0.4)

        dur = await panel_state(h)
        print("  při náhledu:", json.dumps(dur, ensure_ascii=False))
        check("panel má stav preview-only", dur["previewOnly"])
        check("hlavička (lupa/✕/úchyt) je skrytá", not dur["head"])
        check("řádky Další/Krok/Vel. jsou skryté", not dur["rows"])
        check("tlačítko Dočíslovat celou stránku je skryté", not dur["page"])
        check("skok na takt i hinty jsou skryté", not dur["go"] and not dur["hint"])
        check("potvrzovací řádek s Vložit/Zrušit je vidět", dur["confirm"] and dur["okBtn"] and dur["noBtn"])
        check("panel se zmenšil (užší/nižší než plný)",
              dur["w"] < before["w"] or dur["h"] < before["h"],
              "%s×%s → %s×%s" % (before["w"], before["h"], dur["w"], dur["h"]))
        check("nic nepřetéká (clientWidth == scrollWidth)", dur["w"] == dur["sw"],
              "%s/%s" % (dur["w"], dur["sw"]))
        rx, ry, rw, rh = dur["rect"]
        for nm, b in (("Vložit", dur["okBtn"]), ("Zrušit", dur["noBtn"])):
            check("tlačítko %s je uvnitř panelu" % nm,
                  b[0] >= rx - 1 and b[0] + b[2] <= rx + rw + 1 and
                  b[1] >= ry - 1 and b[1] + b[3] <= ry + rh + 1,
                  "btn %s vs panel %s" % (b, dur["rect"]))
        check("tlačítka mají dotykovou výšku ≥ 34 px",
              dur["okBtn"][3] >= 34 and dur["noBtn"][3] >= 34,
              "%s / %s" % (dur["okBtn"][3], dur["noBtn"][3]))
        check("panel zabírá méně místa než plný",
              dur["rect"][2] * dur["rect"][3] < before["rect"][2] * before["rect"][3],
              "%d px² → %d px²" % (before["rect"][2] * before["rect"][3],
                                   dur["rect"][2] * dur["rect"][3]))

        # Zrušit → panel zpět
        await h.ev("(() => { const b=document.querySelector('.bn-fill-no'); if (b) b.click(); })()")
        await asyncio.sleep(0.6)
        after = await panel_state(h)
        print("  po Zrušit:", json.dumps(after, ensure_ascii=False))
        check("po Zrušit je okno číslování zase celé",
              after["head"] and after["rows"] and after["page"] and not after["confirm"],
              json.dumps(after, ensure_ascii=False))
        check("po Zrušit panel nepřetéká", after["w"] == after["sw"], "%s/%s" % (after["w"], after["sw"]))

        # znovu náhled → Vložit → panel zpět a čísla uložená
        await h.ev("(() => { const b=document.querySelector('.bn-page'); if (b) b.click(); })()")
        for _ in range(80):
            p2 = await h.ev("window.__barDev && window.__barDev.barFillPreview.value ? '1' : ''")
            if p2:
                break
            await asyncio.sleep(0.25)
        dur2 = await panel_state(h)
        check("druhý náhled zase smrskne panel", dur2["previewOnly"] and not dur2["head"])
        await h.ev("(() => { const b=document.querySelector('.bn-fill-ok'); if (b) b.click(); })()")
        await asyncio.sleep(1.0)
        commit = await panel_state(h)
        n = json.loads(await h.ev("""(() => { const a=window.__barDev.annotations.value.items
            .filter(i => i.barNum && i.page === 1); return JSON.stringify({n:a.length, t:a.length?a[0].text:null}); })()"""))
        print("  po Vložit:", json.dumps(commit, ensure_ascii=False), n)
        check("po Vložit se okno číslování vrátilo do plné podoby",
              commit["head"] and commit["rows"] and not commit["confirm"],
              json.dumps(commit, ensure_ascii=False))
        check("po Vložit jsou čísla v anotacích (str. 2 = 11 čísel)", n["n"] == 11, json.dumps(n))

    print("\n%d/%d OK" % (sum(1 for c in CHECKS if c[1]), len(CHECKS)))
    for name, ok, det in CHECKS:
        if not ok:
            print("  SELHALO:", name, det)


asyncio.run(main())
