#!/usr/bin/env python3
"""VŠECHNY anotační nástroje klepané PRSTEM (ruční režim = vypnuté „jen pero“).

Jan: „Mám ještě další problémy… Tap to zkrátka nebere v potaz.“ Po opravě
vkládání textu/dynamiky/značky je potřeba proklepat i ostatní nástroje, aby
nikde nezůstala stejná past (nástroj, který jen čeká na další klepnutí, se
nesmí tvářit jako mrtvý tah).

Měří se ULOŽENÉ anotace (`__navdbg.annotCount`) a stav vstupu, ne vzhled:
  * Zvýraznění — 3 klepnutí prstem → pás se uloží
  * Crescendo / Decrescendo — 3 klepnutí prstem → klín se uloží
  * Guma — přejetí prstem přes tah → anotací ubude
  * Text / Dynamika / Značka — klepnutí prstem → otevře se vstup
  * Ruka (Upravit) — klepnutí na prvek → vybere se (editingId), tažení → přesun
  * Zpět / Dopředu — undo/redo po tahu prstem
  * se ZAPNUTÝM „jen pero“: prst NESMÍ nic z toho udělat (jen listuje)

    NOTY_CDP=http://127.0.0.1:9242 python3 scripts/probe-manual-tools.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9242")
DBG = "JSON.stringify(window.__navdbg ? window.__navdbg() : null)"


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


async def dbg(h):
    raw = await h.ev(DBG)
    return json.loads(raw) if raw else {}


async def n_annot(h):
    return (await dbg(h)).get("annotCount", -1)


async def set_penonly(h, want):
    have = await h.ev("(() => { const b = document.querySelector('.ap-tool.pen-only');"
                      " return b ? b.classList.contains('on') : null; })()")
    if have != want:
        await h.ev("document.querySelector('.ap-tool.pen-only').click()")
        await asyncio.sleep(0.4)
    return await h.ev("(() => { const b = document.querySelector('.ap-tool.pen-only');"
                      " return b ? b.classList.contains('on') : null; })()")


async def pick_tool(h, title):
    return await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
                      ".find(x => (x.getAttribute('title') || '').startsWith(%s));"
                      " if (!b) return 'missing'; b.click(); return 'ok'; })()"
                      % json.dumps(title))


async def tap(h, x, y, hold_ms=60, settle=0.7):
    await h.touch("touchStart", [(x, y, 12)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(settle)


async def drag(h, x0, y0, x1, y1, steps=8, settle=0.9):
    await h.touch("touchStart", [(x0, y0, 12)])
    for i in range(1, steps + 1):
        await h.touch("touchMove", [(x0 + (x1 - x0) * i / steps,
                                     y0 + (y1 - y0) * i / steps, 12)])
        await asyncio.sleep(0.03)
    await h.touch("touchEnd", [])
    await asyncio.sleep(settle)


async def tap_btn(h, text, selector=".annot-panel button, .text-input-card button, .edit-bar button"):
    """Klepne na tlačítko podle TEXTU nebo (když má jen SVG) podle `title`.

    POZOR: tlačítka Zpět/Dopředu nesou jen SVG, takže `textContent` je prázdný
    — hledat je podle textu znamená „tlačítko nenalezeno“ a sonda pak hlásí
    falešné selhání.
    """
    box = await h.ev(
        "(() => { const els = [...document.querySelectorAll(%s)];"
        " const b = els.find(x => (x.textContent||'').trim() === %s)"
        "   || els.find(x => (x.getAttribute('title')||'') === %s);"
        " if (!b) return null; if (b.disabled) return {disabled: true};"
        " const r = b.getBoundingClientRect();"
        " return {x: r.left + r.width/2, y: r.top + r.height/2}; })()"
        % (json.dumps(selector), json.dumps(text), json.dumps(text)))
    if not box or box.get("disabled"):
        return False
    await tap(h, box["x"], box["y"], settle=0.6)
    return True


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
        import base64
        pdf = _m.make_pdf(6)
        b64 = base64.b64encode(open(pdf, "rb").read()).decode()
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
        await h.ev("[...document.querySelectorAll('li.song .song-name')][0].click()")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40)
        await asyncio.sleep(1.0)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        # RUČNÍ REŽIM = vypnuté „jen pero“
        print("penOnly:", await set_penonly(h, False))

        g = await h.ev("(() => { const v = document.querySelector('.stage.backdrop')"
                       ".getBoundingClientRect(); return {left: v.left, top: v.top,"
                       " width: v.width, height: v.height}; })()")
        cx = g["left"] + g["width"] * 0.62
        cy = g["top"] + g["height"] * 0.40
        print("kreslící bod:", int(cx), int(cy))

        # --- 1) Zvýraznění: 3 klepnutí prstem ---------------------------
        print("\n--- 1) Zvýraznění (3 klepnutí prstem) ---")
        await pick_tool(h, "Zvýraznění")
        await asyncio.sleep(0.3)
        n0 = await n_annot(h)
        for i, dy in enumerate([0, -40, 0]):
            await tap(h, cx - 60 + i * 40, cy + dy)
        n1 = await n_annot(h)
        c("1) zvýrazňovač se uloží po 3 klepnutích prstem", n1 > n0, f"{n0} -> {n1}")

        # --- 2) Crescendo: 3 klepnutí prstem ---------------------------
        print("\n--- 2) Crescendo (3 klepnutí prstem) ---")
        await pick_tool(h, "Crescendo")
        await asyncio.sleep(0.3)
        n2 = await n_annot(h)
        for i, dy in enumerate([0, -30, 30]):
            await tap(h, cx - 60 + i * 60, cy + 120 + dy)
        n3 = await n_annot(h)
        c("2) crescendo se uloží po 3 klepnutích prstem", n3 > n2, f"{n2} -> {n3}")

        # --- 3) Decrescendo --------------------------------------------
        print("\n--- 3) Decrescendo (3 klepnutí prstem) ---")
        await pick_tool(h, "Decrescendo")
        await asyncio.sleep(0.3)
        n4 = await n_annot(h)
        for i, dy in enumerate([0, -30, 30]):
            await tap(h, cx - 60 + i * 60, cy + 200 + dy)
        n5 = await n_annot(h)
        c("3) decrescendo se uloží po 3 klepnutích prstem", n5 > n4, f"{n4} -> {n5}")

        # --- 4) Guma: přejetí prstem přes tah ---------------------------
        print("\n--- 4) Guma (přejetí prstem přes tah) ---")
        await pick_tool(h, "Guma")
        await asyncio.sleep(0.3)
        n6 = await n_annot(h)
        await drag(h, cx - 70, cy - 5, cx + 70, cy + 5)
        n7 = await n_annot(h)
        c("4) guma prstem smaže anotaci", n7 < n6, f"{n6} -> {n7}")

        # --- 5) Ruka: výběr a přesun ------------------------------------
        print("\n--- 5) Ruka (výběr klepnutím, přesun tažením) ---")
        # nejdřív si prstem udělej tah, ať je co vybírat
        await pick_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        await drag(h, cx - 60, cy + 260, cx + 60, cy + 270)
        await pick_tool(h, "Upravit")
        await asyncio.sleep(0.3)
        await tap(h, cx, cy + 265)
        d = await dbg(h)
        selected = d.get("editingId")
        c("5) ruka vybere prvek klepnutím prstem", bool(selected), str(selected))
        editbar = await h.ev("!!document.querySelector('.edit-bar')")
        c("5) ukáže se lišta úprav", editbar, str(editbar))
        if editbar:
            # zmenšit / zvětšit tlačítkem
            await tap_btn(h, "+")
            await tap_btn(h, "−")
            # přesun tažením
            await drag(h, cx, cy + 265, cx - 40, cy + 300)
            d = await dbg(h)
            c("5) přesun prstem proběhl (výběr drží)", bool(d.get("editingId")),
              str(d.get("editingId")))
            await tap_btn(h, "✓")   # Hotovo

        # --- 6) Zpět / Dopředu ------------------------------------------
        print("\n--- 6) Zpět / Dopředu (klepnutí prstem) ---")
        # Undo/redo se testuje na TUŽKOVÉM tahu (jedna jednoznačná akce), ne na
        # zvýrazňovači — u něj má undo vlastní historii a test by byl nepřesný.
        await pick_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        n_before = await n_annot(h)
        await drag(h, cx - 60, cy - 300, cx + 60, cy - 290)
        n_after_stroke = await n_annot(h)
        c("6) prstem nakreslený tah se uloží", n_after_stroke > n_before,
          f"{n_before} -> {n_after_stroke}")
        undone = await tap_btn(h, "Zpět")
        after = await n_annot(h)
        c("6) Zpět ubere anotaci", undone and after < n_after_stroke,
          f"{n_after_stroke} -> {after}, tlačítko={undone}")
        redone = await tap_btn(h, "Dopředu")
        after2 = await n_annot(h)
        c("6) Dopředu vrátí anotaci", redone and after2 > after,
          f"{after} -> {after2}, tlačítko={redone}")

        # --- 7) Text / Dynamika / Značka prstem -------------------------
        print("\n--- 7) Text / Dynamika / Značky (klepnutí prstem) ---")
        for label, title in (("Text", "Text"), ("Dynamika", "Dynamika"), ("Značky", "Značky")):
            await pick_tool(h, title)
            await asyncio.sleep(0.3)
            nx = await n_annot(h)
            await tap(h, cx, cy - 200)
            card = await h.ev("!!document.querySelector('.text-input-card')")
            c(f"7) {label}: klepnutí prstem otevře vstup", card, str(card))
            if card:
                if label == "Text":
                    await h.set_value(".ti-input", "test")
                elif label == "Dynamika":
                    await tap_btn(h, "mf", ".text-input-card button")
                else:
                    await tap_btn(h, "♭", ".text-input-card button")
                await asyncio.sleep(0.3)
                await tap_btn(h, "Uložit", ".text-input-card button")
                await asyncio.sleep(0.7)
            ny = await n_annot(h)
            c(f"7) {label}: prvek se uloží", ny > nx, f"{nx} -> {ny}")

        # --- 8) se ZAPNUTÝM „jen pero“ nic z toho prst nesmí -----------
        print("\n--- 8) se „jen pero“ ON: prst NESMÍ vkládat ---")
        await set_penonly(h, True)
        await pick_tool(h, "Zvýraznění")
        await asyncio.sleep(0.3)
        n8 = await n_annot(h)
        for i, dy in enumerate([0, -40, 0]):
            await tap(h, cx - 60 + i * 40, cy - 260 + dy)
        n9 = await n_annot(h)
        c("8) se „jen pero“ prst nepřidá zvýraznění (správně)", n9 == n8, f"{n8} -> {n9}")

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
