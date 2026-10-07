#!/usr/bin/env python3
"""Ruční režim: klepnutí musí umístit dynamiku / text / značku.

Jan (Oct 2026): „při ručním režimu nelze vložit značky. Ani dynamiku, ani text,
ani jiné. Tap to zkrátka nebere v potaz.“

Sonda klepe PRSTEM (skutečný dotyk) na noty a měří, jestli se otevřel vstup
(`.text-input-card`) a jestli se prvek uložil (`annotCount`).

Režimy se zkoušejí:
  * „jen pero“ ZAPNUTO (default) — klepnutí perem i prstem
  * „jen pero“ VYPNUTO — klepnutí prstem
  * hned po tahu perem (doznívající pen-guard)

    NOTY_CDP=http://127.0.0.1:9242 python3 scripts/probe-manual-insert.py
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


async def stage(h):
    return await h.ev("(() => { const v = document.querySelector('.stage.backdrop')"
                      ".getBoundingClientRect(); return {left: v.left, top: v.top,"
                      " width: v.width, height: v.height}; })()")


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


async def tap(h, x, y, radius=12, hold_ms=60):
    await h.touch("touchStart", [(x, y, radius)])
    await asyncio.sleep(hold_ms / 1000)
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.7)


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

        g = await stage(h)
        tx = g["left"] + g["width"] * 0.62
        ty = g["top"] + g["height"] * 0.5
        under = await h.ev("(() => { const el = document.elementFromPoint(%d, %d);"
                           " return el && el.tagName + '.' + (el.className.baseVal !== undefined"
                           " ? el.className.baseVal : el.className); })()" % (int(tx), int(ty)))
        print("bod klepnutí:", int(tx), int(ty), under)

        async def try_insert(label, tool_title, use_pen=False, penonly=None):
            if penonly is not None:
                await set_penonly(h, penonly)
            picked = await pick_tool(h, tool_title)
            await asyncio.sleep(0.4)
            await h.ev("window.__navdbg && 0")  # nic
            before = await n_annot(h)
            print(f"   {label}: start (tool={tool_title}, pero={use_pen}, penOnly={penonly})")
            if use_pen:
                await h.pen_tap(tx, ty)
            else:
                await tap(h, tx, ty)
            card = await h.ev("!!document.querySelector('.text-input-card')")
            d = await dbg(h)
            print(f"     karta={card} lastDown='{d.get('lastDown')}' lastUp='{d.get('lastUp')}'"
                  f" activeStroke={d.get('activeStroke')} blocked={d.get('blocked')}")
            print("     log:", json.dumps([x for x in (d.get('evLog') or [])][-8:], ensure_ascii=False))
            c(f"{label}: klepnutí otevře vstup", card, str(card))
            if card:
                # Dialog zahazuje kliknutí, kterému nepředcházelo POLOŽENÍ prstu
                # uvnitř dialogu (`onDialogClickCapture`) — tlačítka se tedy musí
                # mačkat SKUTEČNÝM dotykem, ne `el.click()` (jinak sonda lže).
                async def tap_btn(text):
                    box = await h.ev(
                        "(() => { const b = [...document.querySelectorAll('.text-input-card button')]"
                        ".find(x => (x.textContent||'').trim() === %s);"
                        " if (!b) return null; const r = b.getBoundingClientRect();"
                        " return {x: r.left + r.width/2, y: r.top + r.height/2}; })()" % json.dumps(text))
                    if not box:
                        return False
                    await tap(h, box["x"], box["y"], hold_ms=60)
                    return True
                if tool_title == 'Dynamika':
                    await tap_btn('mf')
                elif tool_title == 'Značky':
                    await tap_btn('♭')
                if tool_title == 'Text':
                    await h.set_value(".ti-input", "test")
                await asyncio.sleep(0.3)
                ok_btn = await tap_btn('Uložit')
                await asyncio.sleep(0.8)
                still = await h.ev("!!document.querySelector('.text-input-card')")
                print(f"     potvrzení tlačítkem Uložit: {ok_btn}, karta po uložení: {still}")
            after = await n_annot(h)
            c(f"{label}: prvek se uloží", after > before, f"{before} -> {after}")
            # uklidit
            await h.ev("(() => { const b = [...document.querySelectorAll('button')]"
                       ".find(x => /Zrušit|Zavřít/.test(x.textContent||'')); if (b) b.click(); return !!b; })()")
            await asyncio.sleep(0.4)

        print("\n--- 1) ruční klepnutí PEREM („jen pero“ ON) ---")
        await try_insert("1a Dynamika (pero)", "Dynamika", use_pen=True, penonly=True)
        await try_insert("1b Text (pero)", "Text", use_pen=True, penonly=True)
        await try_insert("1c Značky (pero)", "Značky", use_pen=True, penonly=True)

        print("\n--- 2) ruční klepnutí PRSTEM s vypnutým „jen pero“ ---")
        await try_insert("2a Dynamika (prst)", "Dynamika", use_pen=False, penonly=False)
        await try_insert("2b Text (prst)", "Text", use_pen=False, penonly=False)
        await try_insert("2c Značky (prst)", "Značky", use_pen=False, penonly=False)

        print("\n--- 3) klepnutí PRSTEM se ZAPNUTÝM „jen pero“ = musí se IGNOROVAT ---")
        # „Jen pero“ znamená: prstem se nekreslí ani nevkládá, prst jen listuje.
        # (Jan: „ruční režim znamená vypnutý ‚jen pero‘“ → v ručním režimu se
        # vkládat MUSÍ, se zapnutým „jen pero“ NESMÍ.)
        await set_penonly(h, True)
        await pick_tool(h, "Dynamika")
        await asyncio.sleep(0.4)
        before = await n_annot(h)
        await tap(h, tx, ty)
        card = await h.ev("!!document.querySelector('.text-input-card')")
        after = await n_annot(h)
        c("3) se „jen pero“ prst NEvloží prvek (správně)",
          (not card) and after == before, f"karta={card}, {before} -> {after}")

        print("\n--- 4) klepnutí PO tahu perem (doznívá pen-guard) ---")
        # POZOR: pero s nástrojem Text samo otevře dialog — pak klepnutí na noty
        # spadne do dialogu, ne na vrstvu. Pro tenhle scénář proto pero kreslí
        # TUŽKOU (tah se uloží) a teprve pak se klepe na vložení textu.
        await set_penonly(h, True)
        await pick_tool(h, "Tužka")
        await asyncio.sleep(0.3)
        await h.pen_stroke(tx - 60, ty + 120, tx + 60, ty + 130)
        d = await dbg(h)
        print(f"     po tahu perem: activePtr={d.get('activePointerId')} blocked={d.get('blocked')}")
        # teď přepnout na text a klepnout PRSTEM (ruční režim)
        d = await dbg(h)
        await set_penonly(h, False)
        await pick_tool(h, "Text")
        await asyncio.sleep(0.3)
        before = await n_annot(h)
        await tap(h, tx, ty)
        card = await h.ev("!!document.querySelector('.text-input-card')")
        d = await dbg(h)
        print(f"     karta={card} lastDown='{d.get('lastDown')}' lastUp='{d.get('lastUp')}'"
              f" blocked={d.get('blocked')}")
        print("     log:", json.dumps((d.get('evLog') or [])[-6:], ensure_ascii=False))
        c("4) klepnutí po tahu perem otevře vstup", card, str(card))

    return c.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
