#!/usr/bin/env python3
"""LUPA na VYTIŠTĚNÁ čísla taktů (Nov 2026).

Jan: „Nešla by ještě náhodou přidat funkce (tlačítko lupy v okně pro číslování
taktů), že bych klikl do oblasti, kde se vyskytuje vytištěné číslo v originálním
PDF a appka by v té oblasti (+- 50px) sama našla číslo taktu a nastavila by mu
neviditelný index pro 'skákání' na takty?“

Sonda staví PDF s ČÍSLY JAKO TEXTEM na známých souřadnicích (Helvetica 10,
„42“ na 60/700, „43“ na 60/600 v bodech PDF) a měří:
  1. tlačítko lupy je v malém okně a přepne nástroj
  2. klepnutí na vytištěné číslo v okolí 50 px najde SPRÁVNÉ číslo
  3. uloží se jako SKRYTÝ index (barNum + hidden) — v notách není vidět
  4. počítadlo „Další“ se přitom nemění (index ≠ číslování)
  5. klepnutí mimo číslo nic nepřidá
  6. index opravdu vstoupí do „Známých taktů“ pro skok na takt

    scripts/run-probe-fresh.sh scripts/probe-barnum-picker.py
"""
import asyncio
import importlib.util
import json
import os

_CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
FIX = "/tmp/bars-fixture.pdf"


def _load_harness():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_m = _load_harness()
_m.CDP_HTTP = _CDP
Check = _m.Check


def make_bars_pdf(path=FIX):
    """Jednostránkové PDF: vytištěná čísla taktů jako TEXT na známých bodech."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"]
    # Čísla schválně ve STŘEDU stránky, ne u levého okraje — levý horní roh
    # zakrývá plovoucí anotační panel a klepnutí by spadlo na něj.
    # Čísla v PRAVÉ DOLNÍ části stránky: levý horní roh zakrývá anotační panel
    # a pravý horní roh okno čísel, klepnutí by spadlo na ně.
    stream = ("BT /F1 10 Tf 450 300 Td (42) Tj ET\n"
              "BT /F1 10 Tf 450 200 Td (43) Tj ET\n"
              "BT /F1 18 Tf 120 600 Td (Andante) Tj ET")
    objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n")
    open(path, "w", encoding="latin-1").write(out)
    return path


BARS_JS = """(async () => {
  const q = indexedDB.open('noty-app');
  const db = await new Promise(res => { q.onsuccess = () => res(q.result); q.onerror = () => res(null); });
  if (!db) return '[]';
  const rows = await new Promise(res => {
    const r = db.transaction('annotations', 'readonly').objectStore('annotations').getAll();
    r.onsuccess = () => res(r.result || []); r.onerror = () => res([]);
  });
  db.close();
  const out = [];
  for (const row of rows) for (const it of (row.items || [])) if (it.barNum) out.push(it);
  return JSON.stringify(out);
})()"""

# Bod v souřadnicích VRSTVY → souřadnice displeje (stejná matice jako toLayerCoords)
TO_SCREEN_JS = """(() => {
  const svg = document.querySelector('.annot-layer');
  const m = svg.getScreenCTM();
  const p = new DOMPoint(%f, %f).matrixTransform(m);
  return JSON.stringify({ x: p.x, y: p.y });
})()"""

PANEL_JS = """(() => { const p = document.querySelector('.barnum-panel');
  if (!p) return null;
  return JSON.stringify({
    title: (p.querySelector('.bn-title') || {}).textContent,
    pickOn: !!p.querySelector('.bn-pick.on'),
    next: (p.querySelectorAll('.bn-input')[0] || {}).value,
  }); })()"""


async def bars(h):
    return json.loads(await h.ev(BARS_JS, await_promise=True) or "[]")


async def pick_tool(h, title_part):
    if not await h.ev("document.querySelectorAll('.ap-tool').length"):
        await h.ev("(() => { const b = document.querySelector('.ap-collapse');"
                   " if (b) b.click(); return !!b; })()")
        await asyncio.sleep(0.5)
    ok = await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
        .find(x => (x.title || '').startsWith(%s)); if (!b) return false; b.click(); return true; })()"""
                    % json.dumps(title_part))
    await asyncio.sleep(0.5)
    return ok


async def tap_layer(h, lx, ly):
    pt = json.loads(await h.ev(TO_SCREEN_JS % (lx, ly)))
    await h.finger_tap(pt["x"], pt["y"], r=11)
    await asyncio.sleep(0.9)


async def main():
    ok = Check()
    make_bars_pdf()
    async with _m.Harness() as h:
        await h.open()
        await h.open_song(pdf=FIX, pages=1)
        await h.annot_toggle()
        assert await pick_tool(h, "Čísla taktů"), "nástroj Čísla taktů nenalezen"
        await h.wait_for("!!document.querySelector('.barnum-panel')", timeout=8, label="panel")

        # --- 1. tlačítko lupy v okně -----------------------------------------
        has = await h.ev("!!document.querySelector('.barnum-panel .bn-pick')")
        ok("v okně čísel je tlačítko lupy", has)
        pick_pt = json.loads(await h.ev("""(() => { const b = document.querySelector('.bn-pick');
            const r = b.getBoundingClientRect();
            return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2,
              inside: (() => { const p = document.querySelector('.barnum-panel').getBoundingClientRect();
                return r.right <= p.right && r.bottom <= p.bottom && r.left >= p.left; })() }); })()"""))
        ok("tlačítko lupy je uvnitř okna", pick_pt["inside"])
        await h.finger_tap(pick_pt["x"], pick_pt["y"], r=10)
        await asyncio.sleep(0.5)
        st = json.loads(await h.ev(PANEL_JS))
        ok("lupa se zapnula (tlačítko svítí, titulek „Lupa na čísla“)",
           st["pickOn"] and "Lupa" in (st["title"] or ""), str(st))

        next_before = st["next"]

        # --- 2. klepnutí na vytištěné číslo „42“ ------------------------------
        # PDF: text na 450/300 (body odspodu), MediaBox 842 vysoký → účaří
        # 842-300 = 542 od shora; střed otisku ~ (455, 538).
        await tap_layer(h, 455, 538)
        items = await bars(h)
        ok("klepnutí na vytištěné číslo vložilo index", len(items) == 1, f"{len(items)} položek")
        if items:
            it = items[0]
            ok("našlo SPRÁVNÉ číslo (42)", str(it.get("text")) == "42", str(it.get("text")))
            ok("uloženo jako SKRYTÝ index", it.get("hidden") is True and it.get("barNum") is True,
               f"hidden={it.get('hidden')}")
            ok("index sedí na vytištěném čísle (±6 px)",
               abs(float(it.get("x") or 0) - 450) <= 6 and abs(float(it.get("y") or 0) - 542) <= 6,
               f"x={it.get('x')} y={it.get('y')}")

        # --- 3. skrytost: v notách nic nepřibylo ------------------------------
        drawn = await h.ev("""(() => { const t = [...document.querySelectorAll('.annot-layer text')]
            .map(e => (e.textContent || '').trim()).filter(Boolean);
            return JSON.stringify(t); })()""")
        ok("skrytý index se v notách nekreslí", "42" not in json.loads(drawn), drawn)
        raw2 = await h.ev(PANEL_JS)
        ok("okno čísel po klepnutí zůstalo", raw2 is not None)
        if raw2 is None:
            return ok.report()
        st2 = json.loads(raw2)
        ok("počítadlo „Další“ se nemění", st2["next"] == next_before,
           f"{next_before} -> {st2['next']}")

        # --- 4. mimo číslo (a mimo 50 px) nic nepřidá -------------------------
        await tap_layer(h, 200, 700)
        ok("klepnutí mimo čísla nic nepřidá", len(await bars(h)) == 1, f"{len(await bars(h))}")

        # --- 5. index vstoupí do „Známých taktů“ pro skok ---------------------
        await h.click(".tb-page")
        await asyncio.sleep(2.0)
        txt = await h.ev("""(() => { const el = [...document.querySelectorAll('.pg-hint')]
            .find(e => /Známých taktů/.test(e.textContent || ''));
            return el ? el.textContent.replace(/\\s+/g, ' ').trim() : null; })()""")
        n_known = 0
        if txt:
            import re as _re
            mm = _re.search(r"Známých taktů:\s*(\d+)", txt)
            n_known = int(mm.group(1)) if mm else 0
        ok("index je mezi známými takty (skok na takt ho vidí)", n_known >= 1,
           f"známých={n_known} | {txt}")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
