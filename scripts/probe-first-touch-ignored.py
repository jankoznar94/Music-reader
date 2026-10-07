#!/usr/bin/env python3
"""Scénář Jana: „první dotek v anotaci je ignorován, tužka píše až na druhý“.

Sekvence, kterou Jan dělá na tabletu (a kterou sonda replikuje):
  1. anotační režim ON („jen pero“ je defaultně zapnuté)
  2. pero napíše tah  →  pero často ukončí kontakt BEZ pointerup (pero odjede
     z dosahu) → `_activePointerId` zůstane viset
  3. uživatel vypne „jen pero“ a chce psát prstem
  4. PRVNÍ tah prstem  →  je ignorován?   5. DRUHÝ tah prstem → kreslí?

A navíc: listování klepnutím na okraj v anotaci (bez „jen pero“ i s ním).

Sonda tiskne `__navdbg` PŘED každým krokem, takže je vidět, jestli visí
`activePointerId` (a tedy jestli `blockedNav()`/guard v onLayerDown blokuje).

    NOTY_CDP=http://127.0.0.1:9241 python3 scripts/probe-first-touch-ignored.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9241")
DBG = "JSON.stringify(window.__navdbg ? window.__navdbg() : null)"
STROKES = "document.querySelectorAll('.annot-layer > g').length"


def _load_harness():
    for cand in (
        os.path.expanduser("~/noty-app/cdp-e2e-harness.py"),
        "/home/martin_fabian/noty-app/cdp-e2e-harness.py",
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_m = _load_harness()
_m.CDP_HTTP = CDP
Harness, Check = _m.Harness, _m.Check


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def dbg(h, label):
    raw = await h.ev(DBG)
    d = json.loads(raw) if raw else None
    print(f"   [{label}] navdbg: {json.dumps(d, ensure_ascii=False)}")
    return d


async def strokes(h):
    """Počet ULOŽENÝCH anotací z diagnostiky appky.

    POZOR: nepočítat `.annot-layer > g` — aktivní tah má taky své `<g>`, takže
    počet skáče i při neuloženém tahu (falešné výsledky).
    """
    raw = await h.ev(DBG)
    return json.loads(raw)["annotCount"] if raw else 0


async def page(h):
    return (await h.ev("document.querySelector('.tb-page').textContent.trim()")).strip()


async def stage(h):
    return await h.ev("(() => { const v = document.querySelector('.stage.backdrop')"
                      ".getBoundingClientRect(); return {left: v.left, top: v.top,"
                      " width: v.width, height: v.height}; })()")


async def point(h, fy=0.5):
    """Bod na vrstvě, který NENÍ zakrytý anotačním panelem (ten sedí vlevo)."""
    g = await stage(h)
    x = g["left"] + g["width"] * 0.62
    y = g["top"] + g["height"] * (0.3 + 0.5 * fy)
    under = await h.ev("(() => { const el = document.elementFromPoint(%d, %d);"
                       " return el && el.tagName + '.' + (el.className.baseVal !== undefined"
                       " ? el.className.baseVal : el.className); })()" % (int(x), int(y)))
    return x, y, under


async def finger_stroke(h, x, y, r=12):
    await h.touch("touchStart", [(x, y, r)])
    for i in range(1, 7):
        await h.touch("touchMove", [(x + i * 12, y + i * 5, r)])
        await asyncio.sleep(0.03)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.7)


async def pen_lost_pointerup(h, x, y):
    """Tah perem, kterému NEDORAZÍ pointerup (pero odjelo z dosahu tabletu)."""
    return await h.ev(
        "(() => { const s = document.querySelector('.annot-layer');"
        " const mk = (t, X, Y, p) => new PointerEvent(t, {bubbles:true, cancelable:true,"
        "   pointerId:7777, pointerType:'pen', isPrimary:true, pressure:p,"
        "   buttons:p ? 1 : 0, clientX:X, clientY:Y});"
        " s.dispatchEvent(mk('pointerdown', %d, %d, 0.5));"
        " for (let i = 1; i <= 5; i++) s.dispatchEvent(mk('pointermove', %d + i * 10, %d, 0.5));"
        " return 'pen bez pointerup'; })()" % (int(x - 40), int(y), int(x - 40), int(y)))


async def set_penonly(h, want):
    have = await h.ev("(() => { const b = document.querySelector('.ap-tool.pen-only');"
                      " return b ? b.classList.contains('on') : null; })()")
    if have != want:
        await h.ev("document.querySelector('.ap-tool.pen-only').click()")
        await asyncio.sleep(0.4)
    return await h.ev("(() => { const b = document.querySelector('.ap-tool.pen-only');"
                      " return b ? b.classList.contains('on') : null; })()")


async def main():
    c = Check()
    h = await fresh_harness()
    async with h:
        await h.open()
        await h.cdp("Storage.clearDataForOrigin",
                    {"origin": "http://localhost:5173", "storageTypes": "indexeddb"})
        await asyncio.sleep(1.0)
        await h.open()
        await h.set_tablet()
        # nahrání přes DataTransfer (DOM.setFileInputFiles dělá nulový soubor)
        import base64
        pdf = _m.make_pdf(6)
        with open(pdf, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        await h.ev(
            "(() => { const bin = atob(%s); const u = new Uint8Array(bin.length);"
            " for (let i=0;i<bin.length;i++) u[i]=bin.charCodeAt(i);"
            " const f = new File([u], 'noty-fixture.pdf', {type:'application/pdf'});"
            " const dt = new DataTransfer(); dt.items.add(f);"
            " const el = document.querySelector('input[type=file]'); el.files = dt.files;"
            " el.dispatchEvent(new Event('change', {bubbles:true})); return f.size; })()"
            % json.dumps(b64))
        await h.wait_for("document.querySelectorAll('.author-group').length > 0", timeout=60)
        await h.ev(Harness.expand_authors_js())
        await h.wait_for("document.querySelectorAll('li.song').length > 0", timeout=15)
        await asyncio.sleep(0.5)
        await h.ev("[...document.querySelectorAll('li.song')].find(r => r.innerText"
                   ".includes('6 str.')).querySelector('.song-name').click()")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40)
        await asyncio.sleep(1.0)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                   ".find(x => (x.getAttribute('title') || '') === 'Tužka'); if (b) b.click(); })()")
        await asyncio.sleep(0.4)

        x, y, under = await point(h, 0.45)
        print("kreslící bod:", int(x), int(y), under)

        # --- A) pero napíše a ZTRATÍ pointerup ---------------------------
        print("\n--- A) pero odešlo z dosahu (pointerup nedorazí) ---")
        n0 = await strokes(h)
        print("  ", await pen_lost_pointerup(h, x, y))
        await asyncio.sleep(0.4)
        d = await dbg(h, "hned po ztraceném pointerupu")
        c("A) pointer po ztraceném tahu skutečně visí", d["activePointerId"] is not None,
          str(d["activePointerId"]))
        n1 = await strokes(h)
        pend = json.loads(await h.ev(DBG))["activeStroke"]
        # Tah bez pointerupu se do anotací (správně) NEULOŽÍ — zůstane jako
        # rozpracovaný. Důležité je, že visí pointer (a že se to pak uvolní).
        c("A) tah zůstal rozpracovaný (neuloží se bez pointerupu)", pend, str(pend))

        # --- B) vypnout „jen pero“, pak PRVNÍ a DRUHÝ tah prstem ---------
        print("\n--- B) „jen pero“ OFF → první tah prstem, pak druhý ---")
        await set_penonly(h, False)
        await dbg(h, "po vypnutí „jen pero“")
        bx, by, _ = await point(h, 0.6)
        n2 = await strokes(h)
        await finger_stroke(h, bx, by)
        n3 = await strokes(h)
        await dbg(h, "po PRVNÍM tahu prstem")
        c("B) PRVNÍ tah prstem kreslí", n3 > n2, f"{n2} -> {n3}")

        bx2, by2, _ = await point(h, 0.7)
        n4 = await strokes(h)
        await finger_stroke(h, bx2, by2)
        n5 = await strokes(h)
        c("B) DRUHÝ tah prstem kreslí", n5 > n4, f"{n4} -> {n5}")

        # --- C) listování klepnutím na okraj (bez „jen pero“) ------------
        # POZOR: `h.goto()` (dialog stránky) anotační režim VYPÍNÁ — sonda by
        # pak měřila listování ve čtení, ne v anotaci (falešný PASS).
        async def ensure_annot(h, on=True):
            have = await h.ev("!!document.querySelector('.annot-panel')")
            if have != on:
                await h.annot_toggle()
                await asyncio.sleep(0.5)

        print("\n--- C) listování klepnutím na okraj, „jen pero“ OFF ---")
        # POZOR: levý okraj je ZAKRYTÝ anotačním panelem (min-width 220 px, left 16 px)
        # → klepnutí tam legitimně NElístuje (`isControlTarget`). Testuj pravý okraj.
        v = await h.ev("(() => { const v = document.querySelector('.viewer').getBoundingClientRect();"
                       " const bar = document.querySelector('.top-bar').getBoundingClientRect();"
                       " return {left: v.left, width: v.width, barBottom: bar.bottom}; })()")
        ynav = v["barBottom"] + 220
        right_x = v["left"] + v["width"] - 22
        await ensure_annot(h, True)
        await set_penonly(h, False)
        p0 = await page(h)
        await dbg(h, "před klepnutím na okraj")
        await h.finger_tap(right_x, ynav, r=12)
        await asyncio.sleep(0.5)
        p1 = await page(h)
        ann = await h.ev("!!document.querySelector('.annot-panel')")
        c("C) klepnutí na okraj listuje (anotace ON, jen pero OFF)",
          p0 != p1, f"{p0} -> {p1}, annot={ann}")
        await dbg(h, "po klepnutí na okraj")

        await h.finger_tap(v["left"] + 22, ynav, r=12)
        await asyncio.sleep(0.5)
        p2 = await page(h)
        c("C2) OK: klepnutí do panelu vlevo NElístuje (sonda to jen dokumentuje)",
          p1 == p2, f"{p1} -> {p2}")

        # --- D) listování HNEĎ po tahu prstem ---------------------------
        print("\n--- D) klepnutí na okraj HNEĎ po tahu prstem ---")
        await ensure_annot(h, True)
        cx, cy, _ = await point(h, 0.5)
        await finger_stroke(h, cx, cy)
        before = await page(h)
        await dbg(h, "hned po tahu prstem")
        await h.finger_tap(right_x, ynav, r=12)
        await asyncio.sleep(0.5)
        after = await page(h)
        c("D) i hned po tahu prstem listuje", before != after, f"{before} -> {after}")

        # --- E) listování s „jen pero“ ZAPNUTÝM -------------------------
        print("\n--- E) listování klepnutím na okraj, „jen pero“ ON ---")
        await ensure_annot(h, True)
        await set_penonly(h, True)
        b1 = await page(h)
        await h.finger_tap(right_x, ynav, r=12)
        await asyncio.sleep(0.5)
        b2 = await page(h)
        c("E) klepnutí na okraj listuje i s „jen pero“", b1 != b2, f"{b1} -> {b2}")

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
