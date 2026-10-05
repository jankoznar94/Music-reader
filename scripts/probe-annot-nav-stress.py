#!/usr/bin/env python3
"""Zátěžová sonda: KTERÁ anotační akce zasekne listování? (Jan, Oct 2026)

Jan: „Opravdu se občas stane, že při anotačním režimu přestane fungovat listování
stránek. Funguje to, ale prostě po určité době, nebo akci, se to sekne a pak už
listovat nejde. Jen po vypnutí anotačního režimu."

Sonda NEHÁDÁ mechanizmus — brute-force zkouší anotační akce jednu po druhé a po
KAŽDÉ zkusí prstem na okraji otočit stránku (2 pokusy, mezi nimi pauza, aby
neplatil 800ms pen-guard). Když oba pokusy selžou, akce je ta, co listování
zasekla, a sonda se zastaví a vypíše ji.

Navíc po zaseknutí zkusí vypnout a zapnout anotační režim — tím se ověří Janovo
„jen po vypnutí anotačního režimu se to rozjede".

    scripts/run-probe-fresh.sh scripts/probe-annot-nav-stress.py
"""
import asyncio
import importlib.util
import json
import os
import urllib.request

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")


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
Harness = _m.Harness

ANNOT = "Anotace / listování"
TOOL_MARK = "Značky pro výšky not (béčko, odrážka, křížek, ozdoby...)"
TOOL_TEXT = "Text (klávesnice)"
TOOL_PENCIL = "Tužka"
TOOL_HL = "Zvýraznění"
TOOL_ERASER = "Guma (maže anotace, přes které přejede)"
TOOL_EDIT = "Upravit / přesunout text či dynamiku"
TOOL_CRES = "Crescendo (3 body)"
TOOL_DYN = "Dynamika (p, f, mf, sfz...)"

GEO = ("(() => { const r = document.querySelector('.stage.backdrop').getBoundingClientRect();"
       " return { left: r.left, top: r.top, width: r.width, height: r.height }; })()")


async def fresh_harness():
    req = urllib.request.Request(f"{CDP}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    await asyncio.sleep(0.8)
    h = Harness(_m.APP_URL)
    h._fresh_target = info.get("id")
    return h


async def page_num(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    return t.split(" ")[0].strip()


async def page_info(h):
    t = await h.ev("document.querySelector('.tb-page').textContent.trim()")
    left, rest = t.split("/")
    cur = int(left.split(" ")[0].strip())
    # celkový počet bez případného " (z N)"
    tot = int(rest.strip().split(" ")[0])
    return cur, tot


async def swipe_dir(h, direction):
    """direction: +1 = na další stránku (z pravého okraje doleva),
    -1 = na předchozí (z levého okraje doprava)."""
    g = await h.ev(GEO)
    y = g["top"] + g["height"] * 0.5
    if direction > 0:
        x0 = g["left"] + g["width"] - 18
        x1 = g["left"] + g["width"] * 0.55
    else:
        x0 = g["left"] + 18
        x1 = g["left"] + g["width"] * 0.45
    before = await page_num(h)
    await h.finger_swipe(x0, y, x1, y, r=12, steps=10)
    await asyncio.sleep(1.0)
    return before, await page_num(h)


async def try_swipe(h, attempts=2):
    """Otočí stránku TAM, kam to jde (na poslední stránce zpět) — aby se
    „nejde dál, protože jsem na konci" nepletlo se „listování je zaseknuté"."""
    global _dir
    for i in range(attempts):
        cur, tot = await page_info(h)
        d = 1 if cur < tot else -1
        _dir = d
        b, a = await swipe_dir(h, d)
        if b != a:
            return True, "%s->%s (%s, pokus %d)" % (b, a, "vpřed" if d > 0 else "zpět", i + 1)
        await asyncio.sleep(1.0)   # nechat vypršet pen-guard / palm-guard
    return False, "stuck na str. %s (směr %s)" % (b, "vpřed" if d > 0 else "zpět")


_dir = 1


async def tool(h, title):
    return await h.ev(
        "(() => { const b = [...document.querySelectorAll('.ap-tool')]"
        ".find(x => x.getAttribute('title') === %s); if (!b) return 'missing';"
        " b.click(); return 'ok'; })()" % json.dumps(title))


async def centre(h, fx=0.5, fy=0.45):
    g = await h.ev(GEO)
    return (g["left"] + g["width"] * fx, g["top"] + g["height"] * fy)


async def dialog_ok(h, label="Uložit"):
    """Dialog má `dialogArmed` ochranu — nejdřív pointerdown na overlay, pak klik."""
    r = await h.ev(
        "(() => { const b = [...document.querySelectorAll('.ti-actions .jp-btn')]"
        ".find(x => x.textContent.trim() === %s); if (!b) return 'missing';"
        " const rc = b.getBoundingClientRect();"
        " const o = { bubbles:true, cancelable:true, pointerId:777, pointerType:'touch',"
        "             clientX: rc.left + rc.width/2, clientY: rc.top + rc.height/2 };"
        " const ov = document.querySelector('.text-input-overlay');"
        " if (ov) { ov.dispatchEvent(new PointerEvent('pointerdown', o));"
        "           ov.dispatchEvent(new MouseEvent('click', o)); }"
        " b.click(); return 'ok'; })()" % json.dumps(label))
    await asyncio.sleep(0.9)
    return r


async def has_dialog(h):
    return await h.ev("!!document.querySelector('.text-input-overlay')")


async def close_any_dialog(h):
    if await has_dialog(h):
        await dialog_ok(h, "Uložit")


# --- jednotlivé akce --------------------------------------------------------

async def act_pen_stroke(h):
    await tool(h, TOOL_PENCIL)
    x, y = await centre(h, 0.5, 0.35)
    await h.pen_stroke(x - 40, y, x + 40, y, steps=8)


async def act_finger_stroke(h):
    """Prst po plátně (s vypnutým „jen pero") — druhá cesta k anotaci."""
    x, y = await centre(h, 0.5, 0.4)
    g = await h.ev(GEO)
    await h.finger_swipe(x, y, x + 60, y + 10, r=12, steps=8)


async def act_pen_eraser(h):
    await tool(h, TOOL_ERASER)
    x, y = await centre(h, 0.5, 0.35)
    await h.pen_stroke(x - 40, y, x + 40, y, steps=8)


async def act_pen_highlight(h):
    await tool(h, TOOL_HL)
    x, y = await centre(h, 0.35, 0.5)
    for dy in (0, 30, 0):
        await h.pen_tap(x, y + dy if dy else y)
        await asyncio.sleep(0.35)


async def act_crescendo(h):
    await tool(h, TOOL_CRES)
    x, y = await centre(h, 0.4, 0.55)
    for dx in (0, 30, 30):
        await h.pen_tap(x + dx, y if dx == 0 else y + 20)
        await asyncio.sleep(0.35)


async def act_mark(h):
    await tool(h, TOOL_MARK)
    x, y = await centre(h, 0.5, 0.45)
    await h.pen_tap(x, y)
    await asyncio.sleep(0.8)
    st = "no-dialog"
    if await has_dialog(h):
        # klepni dlaždici značky (pointerdown.prevent) → rovnou potvrdí
        st = await h.ev("(() => { const b = document.querySelector('.dyn-btn');"
                        " if (!b) return 'no-tile'; const r = b.getBoundingClientRect();"
                        " b.dispatchEvent(new PointerEvent('pointerdown',"
                        "  { bubbles:true, cancelable:true, pointerId:88, pointerType:'pen',"
                        "    clientX: r.left + r.width/2, clientY: r.top + r.height/2 }));"
                        " return 'tile'; })()")
        await asyncio.sleep(0.8)
        await close_any_dialog(h)
    return "mark:" + st


async def act_dynamic(h):
    await tool(h, TOOL_DYN)
    x, y = await centre(h, 0.55, 0.5)
    await h.pen_tap(x, y)
    await asyncio.sleep(0.8)
    st = "no-dialog"
    if await has_dialog(h):
        st = await h.ev("(() => { const b = document.querySelector('.dyn-btn');"
                        " if (!b) return 'no-tile'; const r = b.getBoundingClientRect();"
                        " b.dispatchEvent(new PointerEvent('pointerdown',"
                        "  { bubbles:true, cancelable:true, pointerId:89, pointerType:'pen',"
                        "    clientX: r.left + r.width/2, clientY: r.top + r.height/2 }));"
                        " return 'tile'; })()")
        await asyncio.sleep(0.8)
        await close_any_dialog(h)
    return "dyn:" + st


async def act_text_cancel(h):
    """Text + ZRUŠIT dialog (ne Uložit) — jiná úklidová cesta."""
    await tool(h, TOOL_TEXT)
    x, y = await centre(h, 0.45, 0.6)
    await h.pen_tap(x, y)
    await asyncio.sleep(0.8)
    if await has_dialog(h):
        await dialog_ok(h, "Zrušit")
        return "text-cancel"
    return "text:no-dialog"


async def act_edit_drag(h):
    await tool(h, TOOL_EDIT)
    x, y = await centre(h, 0.5, 0.35)
    await h.pen_stroke(x, y, x + 50, y + 20, steps=8)


async def act_undo_redo(h):
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => x.getAttribute('title') === 'Zpět'); if (b && !b.disabled) b.click();"
               " return true; })()")
    await asyncio.sleep(0.5)
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => x.getAttribute('title') === 'Dopředu'); if (b && !b.disabled) b.click();"
               " return true; })()")


async def act_palm(h):
    """Opřená dlaň na okraji displeje (velký poloměr) — má se ignorovat."""
    g = await h.ev(GEO)
    x = g["left"] + 40
    y = g["top"] + g["height"] * 0.5
    await h.palm_tap(x, y)


async def act_pinch(h):
    """Dvěma prsty zoom — po puštění musí zůstat listování funkční."""
    g = await h.ev(GEO)
    cx = g["left"] + g["width"] * 0.5
    cy = g["top"] + g["height"] * 0.4
    await h.touch("touchStart", [(cx - 40, cy), (cx + 40, cy)])
    await h.touch("touchMove", [(cx - 80, cy), (cx + 80, cy)])
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.8)


async def act_rotate3(h):
    """Tři prsty — rotace (OS si je na tabletu často vezme → touchcancel)."""
    g = await h.ev(GEO)
    cx = g["left"] + g["width"] * 0.5
    cy = g["top"] + g["height"] * 0.45
    await h.touch("touchStart", [(cx - 60, cy), (cx + 60, cy), (cx, cy + 60)])
    await h.touch("touchMove", [(cx - 50, cy - 20), (cx + 50, cy + 10), (cx, cy + 70)])
    await h.touch("touchEnd", [])
    await asyncio.sleep(0.8)


async def act_toggle_penonly(h):
    await h.ev("(() => { const b = [...document.querySelectorAll('.ap-tool')]"
               ".find(x => x.getAttribute('title') === 'Kreslit jen perem (ignorovat dotyk rukou)');"
               " if (b) b.click(); return true; })()")
    await asyncio.sleep(0.5)


ACTIONS = [
    ("tah perem (tužka)",            act_pen_stroke),
    ("tah prstem (penOnly vyp.)",    act_finger_stroke),
    ("guma",                         act_pen_eraser),
    ("zvýrazňovač (3 body)",         act_pen_highlight),
    ("crescendo (3 body)",           act_crescendo),
    ("značka + dlaždice",            act_mark),
    ("dynamika + dlaždice",          act_dynamic),
    ("text + Zrušit",                act_text_cancel),
    ("ruka: přetažení",              act_edit_drag),
    ("undo + redo",                  act_undo_redo),
    ("opřená dlaň na okraji",        act_palm),
    ("dvě prsty: zoom",              act_pinch),
    ("tři prsty: rotace",            act_rotate3),
    ("přepínač „jen pero“",          act_toggle_penonly),
]


async def main():
    h = await fresh_harness()
    async with h:
        await h.open()
        try:
            await h.ev("indexedDB.deleteDatabase('noty-app')")
        except Exception:
            pass
        await asyncio.sleep(0.6)
        await h.open()
        await h.open_song(pages=10, reset=False)

        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await h.wait_for("!!document.querySelector('.annot-panel')", 10, "anotační panel")
        await asyncio.sleep(0.6)

        ok, det = await try_swipe(h, attempts=2)
        print(("OK  " if ok else "FAIL") + " BASELINE listování v anotaci   " + det)
        if not ok:
            print("Baseline nefunguje — sonda nemá smysl.")
            return 1

        wedged_by = None
        for name, fn in ACTIONS:
            try:
                res = await fn(h)
            except Exception as e:
                res = "akce vyhodila: %s" % e
            await close_any_dialog(h)
            await asyncio.sleep(1.0)          # ať vyprší pen-guard (800 ms)
            ok, det = await try_swipe(h, attempts=2)
            print(("OK  " if ok else "FAIL") +
                  (" po akci: %-28s %s" % (name, det)) +
                  ("   [%s]" % res if res else ""))
            if not ok:
                wedged_by = name
                break

        if wedged_by is None:
            print("\nŽádná ze %d akcí listování nezasekla." % len(ACTIONS))
            return 0

        print("\n=== ZASEKNUTO akcí: %s ===" % wedged_by)
        # Jan: „jen po vypnutí anotačního režimu" — ověř to
        for extra in range(3):
            ok, det = await try_swipe(h, attempts=1)
            print("  další pokus %d bez vypnutí režimu: %s  %s"
                  % (extra + 1, "OK" if ok else "FAIL", det))
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.8)
        ok, det = await try_swipe(h, attempts=2)
        print("  po VYPNUTÍ anotačního režimu: %s  %s" % ("OK" if ok else "FAIL", det))
        await h.ev("document.querySelector('.tb-btn[title=%s]').click()" % json.dumps(ANNOT))
        await asyncio.sleep(0.8)
        ok, det = await try_swipe(h, attempts=2)
        print("  po ZAPNUTÍ anotačního režimu: %s  %s" % ("OK" if ok else "FAIL", det))
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
