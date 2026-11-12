#!/usr/bin/env python3
"""Malé samostatné okno pro ČÍSLA TAKTŮ + posun čísla nad ťuknutý bod (Nov 2026).

Jan: „Anotační okno už je samo o sobě příšerně velké a rozsáhlé. Když chce
uživatel číslovat, tak neustále musí schovávat/zobrazovat anotační okno, aby
spočítal takty v systému, nebo ho přesouvat. Okno, ve kterém si volím číslo taktu
a velikost kroku musí být separované, malé a nesmí zavazet.“
+ „Čísla taktů dáme ještě o trošičku výš vůči vybranému bodu pro vložení čísla.“

Sonda měří to, co si uživatel stáhne na tablet:
  1. při nástroji Čísla taktů existuje SAMOSTATNÝ panel `.barnum-panel`
     a obsahuje „Další“ i „Krok“ (a velikost) — velký anotační panel je neobsahuje
  2. panel je MALÝ a CELÝ na displeji (měřeno getBoundingClientRect, ne existencí)
  3. jeho tlačítka jsou skutečně chytatelná (`elementFromPoint` + closest)
  4. se SBALENÝM anotačním oknem panel zůstává a „Další +“ funguje
  5. ťuknutím na plátno se vloží číslo `BAR_TAP_GAP` px NAD bod
     (počítá se v souřadnicích vrstvy přes getScreenCTM, ne od oka)
  6. panel se dá odtáhnout a pozice přežije reload
  7. panel neblokuje vložení čísla pod sebou (klepnutí na panel nevloží číslo)

    scripts/run-probe-fresh.sh scripts/probe-barnum-panel.py
"""
import asyncio
import importlib.util
import json
import os

_CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9223")
# Volitelně proti ŽIVÉMU webu (po nasazení): NOTY_APP=https://harlequin-music-reader.web.app/
LIVE = os.environ.get("NOTY_APP")


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
_m.CDP_HTTP = _CDP
Check = _m.Check

PANEL_JS = """(() => {
  const p = document.querySelector('.barnum-panel');
  if (!p) return null;
  const r = p.getBoundingClientRect();
  const kids = [...p.querySelectorAll('.bn-btn, .bn-input, .bn-toggle, .panel-grip, .bn-insert')].map(el => {
    const b = el.getBoundingClientRect();
    const hit = document.elementFromPoint(b.left + b.width / 2, b.top + b.height / 2);
    return {
      cls: el.className, x: Math.round(b.left), y: Math.round(b.top),
      w: Math.round(b.width), h: Math.round(b.height),
      hit: !!(hit && (hit === el || el.contains(hit) || hit.closest('.bn-btn, .bn-input, .bn-toggle, .panel-grip, .bn-insert'))),
      hitCls: hit ? (hit.className || hit.tagName) : null,
    };
  });
  return JSON.stringify({
    r: { left: r.left, top: r.top, right: r.right, bottom: r.bottom, w: r.width, h: r.height },
    vw: window.innerWidth, vh: window.innerHeight,
    kids,
    text: p.textContent.replace(/\\s+/g, ' ').trim(),
    vals: {
      next: (p.querySelectorAll('.bn-input')[0] || {}).value,
      step: (p.querySelectorAll('.bn-input')[1] || {}).value,
      size: (p.querySelector('.bn-val') || {}).textContent,
      insertOn: !!(p.querySelector('.bn-insert') || {}).classList
        && p.querySelector('.bn-insert').classList.contains('on'),
      insertText: (p.querySelector('.bn-insert') || {}).textContent,
    },
  });
})()"""

# Souřadnice vrstvy pro daný klientský bod — STEJNÝ převod jako toLayerCoords().
LAYER_JS = """(() => {
  const svg = document.querySelector('svg.annot-layer') || document.querySelector('.annot-layer');
  const r = svg.getBoundingClientRect();
  const ctm = svg.getScreenCTM();
  const p = new DOMPoint(%f, %f).matrixTransform(ctm.inverse());
  return JSON.stringify({ x: p.x, y: p.y, svgLeft: r.left, svgTop: r.top });
})()"""

ANN_JS = """(async () => {
  const id = location.pathname.split('/').pop();
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


ALL_JS = """(async () => {
  const q = indexedDB.open('noty-app');
  const db = await new Promise(res => { q.onsuccess = () => res(q.result); q.onerror = () => res(null); });
  if (!db) return '{}';
  const rows = await new Promise(res => {
    const r = db.transaction('annotations', 'readonly').objectStore('annotations').getAll();
    r.onsuccess = () => res(r.result || []); r.onerror = () => res([]);
  });
  db.close();
  let bar = 0, other = 0;
  for (const row of rows) for (const it of (row.items || [])) (it.barNum ? bar++ : other++);
  return JSON.stringify({ bar, other });
})()"""


async def free_point_retry(h, lo=0.3, hi=0.7, tries=8):
    """Volný bod na vrstvě — po přechodu na jinou stránku se viewer ještě chvíli
    překresluje, takže první pokus může trefit loading overlay."""
    for _ in range(tries):
        p = await h.free_point(lo, hi)
        if p:
            return p
        await asyncio.sleep(0.6)
    return None


async def counts(h):
    return json.loads(await h.ev(ALL_JS, await_promise=True) or "{}")


async def bar_nums(h):
    return json.loads(await h.ev(ANN_JS, await_promise=True) or "[]")


async def open_barnum(h):
    """Otevře okno Čísel taktů tlačítkem na HLAVNÍ LIŠTĚ.

    Nástroj už v anotačním panelu NENÍ (Jan, Nov 2026: „číslování bychom měli
    dát úplně mimo anotační menu — bude mít svoje vlastní tlačítko na hlavní
    liště“), takže staré `pick_tool('Čísla taktů')` nemá co najít.
    """
    if await h.ev("!!document.querySelector('.barnum-panel')"):
        return True
    okk = await h.ev("""(() => { const b = document.querySelector('.tb-btn[title^="Číslování taktů"]');
        if (!b) return false; b.click(); return true; })()""")
    try:
        await h.wait_for("!!document.querySelector('.barnum-panel')", timeout=8, label="barnum panel")
    except Exception:
        return False
    return bool(okk)


async def arm_insert(h):
    """Zapne přepínač „Vkládat“ (bez něj dotyk do not nic nevloží)."""
    st = json.loads(await h.ev(PANEL_JS))
    if st["vals"]["insertOn"]:
        return True
    pt = json.loads(await h.ev("""(() => { const b = document.querySelector('.barnum-panel .bn-insert');
        const r = b.getBoundingClientRect();
        return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); })()"""))
    await h.finger_tap(pt["x"], pt["y"], r=10)
    await asyncio.sleep(0.5)
    return json.loads(await h.ev(PANEL_JS))["vals"]["insertOn"]


async def pick_tool(h, title_part):
    # Velký panel se sbalením schová i tlačítka nástrojů — v tom případě ho
    # rozbal (tlačítko je jen ikona se šipkou, text „Rozbalit“ nemá).
    if not await h.ev("document.querySelectorAll('.ap-tool').length"):
        await h.ev("(() => { const b = document.querySelector('.ap-collapse');"
                   " if (b) b.click(); return !!b; })()")
        await asyncio.sleep(0.5)
    ok = await h.ev("""(() => { const b = [...document.querySelectorAll('.ap-tool')]
        .find(x => (x.title || '').startsWith(%s)); if (!b) return false; b.click(); return true; })()"""
                    % json.dumps(title_part))
    await asyncio.sleep(0.6)
    return ok


async def main():
    ok = Check()
    h = _m.Harness(url=LIVE) if LIVE else _m.Harness()
    if LIVE:
        print("   cíl:", LIVE)
    async with h:
        await h.open()          # IDB je na about:blank zakázaná → nejdřív appka
        if LIVE:
            # Starý service worker by servíroval starou verzi z precache →
            # sonda by měřila minulý build, ne ten nasazený.
            await h.ev("(async () => { const rs = await navigator.serviceWorker.getRegistrations();"
                       " for (const r of rs) await r.unregister();"
                       " for (const k of await caches.keys()) await caches.delete(k);"
                       " return true; })()", await_promise=True)
            await asyncio.sleep(1.0)
            await h.open()
        await h.open_song(pages=4)
        assert await open_barnum(h), "tlačítko Číslování taktů na hlavní liště nenalezeno"

        # --- 1. samostatný panel, velký panel už číslování neobsahuje ---------
        st = json.loads(await h.ev(PANEL_JS))
        ok("panel existuje", st is not None)
        ok("obsahuje Další i Krok i Vel.",
           all(k in st["text"] for k in ("Další", "Krok", "Vel.")), st["text"])
        big = await h.ev("""(() => { const p = document.querySelector('.annot-panel');
            if (!p) return 'no panel';
            return JSON.stringify({ barNext: p.querySelectorAll('.ap-bar-next').length,
              label: (p.textContent.match(/Čísla taktů/g) || []).length }); })()""")
        # Velký anotační panel se při číslování VŮBEC nekreslí (číslování má
        # vlastní okno a noty musí být vidět) — dřív tu stačilo, že v něm čísla
        # nejsou; teď je to silnější: panel neexistuje.
        bigd = json.loads(big) if big.startswith("{") else {"barNext": 0, "label": 0}
        ok("velký anotační panel se při číslování nekreslí / neobsahuje čísla",
           bigd["barNext"] == 0 and bigd["label"] == 0, big)

        # --- 2. malý a celý na displeji ---------------------------------------
        r = st["r"]
        # Šířka zůstává úzká (jedna kolona). Výška roste s řádky, které panel
        # v listopadu 2026 dostal (Výška, Vkládat, Smazat tuto stránku) — hlídá
        # se jen to, že nepřeteče displej.
        ok("panel je úzký (<= 250 px) a vejde se na displej", r["w"] <= 250 and r["h"] < st["vh"] - 40,
           f"{r['w']:.0f} x {r['h']:.0f} / displej {st['vw']}x{st['vh']}")
        ok("panel je celý na displeji",
           r["left"] >= 0 and r["top"] >= 0 and r["right"] <= st["vw"] and r["bottom"] <= st["vh"],
           f"panel {r['left']:.0f},{r['top']:.0f}..{r['right']:.0f},{r['bottom']:.0f} / displej {st['vw']}x{st['vh']}")

        # --- 3. tlačítka jsou chytatelná --------------------------------------
        bad = [k for k in st["kids"] if not k["hit"]]
        ok("všechna ovládání panelu jsou chytatelná (%d)" % len(st["kids"]), not bad, str(bad))
        small = [k for k in st["kids"] if k["cls"] != "panel-grip" and k["h"] < 28]
        ok("ovládací prvky mají dotykovou výšku >= 28 px", not small, str(small))

        # --- 3b. VKLÁDAT: explicitní přepínač, výchozí VYPNUTO ----------------
        # Jan (listopad 2026): „uživatel omylem vkládá indexy do not, aniž by
        # o tom věděl“ — otevřené okno čísel nesmí samo do not sáhnout.
        ok("panel má přepínač „Vkládat“", "Vkládat" in st["text"], st["text"])
        ok("po otevření číslování je vkládání VYPNUTÉ",
           (not st["vals"]["insertOn"]) and "vypnuto" in (st["vals"]["insertText"] or ""),
           st["vals"])
        n_off = len(await bar_nums(h))
        fp_off = await free_point_retry(h, 0.3, 0.6)
        await h.finger_tap(fp_off["x"], fp_off["y"], r=11)
        await asyncio.sleep(0.8)
        ok("s vypnutým „Vkládat“ dotyk do not NIC nevloží",
           len(await bar_nums(h)) == n_off,
           f"{n_off} -> {len(await bar_nums(h))}")
        ins_pt = json.loads(await h.ev("""(() => { const b = document.querySelector('.barnum-panel .bn-insert');
            const r = b.getBoundingClientRect();
            return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); })()"""))
        await h.finger_tap(ins_pt["x"], ins_pt["y"], r=10)
        await asyncio.sleep(0.5)
        st = json.loads(await h.ev(PANEL_JS))
        ok("klepnutím na přepínač se vkládání ZAPNE",
           st["vals"]["insertOn"] and "zapnuto" in (st["vals"]["insertText"] or ""),
           st["vals"])

        # --- 4. panel žije samostatně a počítadlo funguje ---------------------
        # Anotační panel je při číslování zavřený, takže „sbalení“ odpadá;
        # ověřuje se, že okno čísel stojí samo a jeho ovládání funguje.
        still = json.loads(await h.ev(PANEL_JS))
        ok("okno čísel stojí samostatně (bez anotačního panelu)",
           still is not None and not await h.ev("!!document.querySelector('.annot-panel')"))
        n0 = int(still["vals"]["next"])
        step0 = int(still["vals"]["step"])
        # klik na „+“ u Další přes CDP (skutečné klepnutí na střed tlačítka)
        pt = await h.ev("""(() => { const p = document.querySelector('.barnum-panel');
            const b = p.querySelectorAll('.bn-btn')[1];
            const r = b.getBoundingClientRect();
            return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); })()""")
        pt = json.loads(pt)
        await h.finger_tap(pt["x"], pt["y"], r=10)
        await asyncio.sleep(0.4)
        st2 = json.loads(await h.ev(PANEL_JS))
        ok("„Další +“ funguje i se sbaleným anotačním oknem",
           int(st2["vals"]["next"]) == n0 + step0, f"{n0} -> {st2['vals']['next']} (krok {step0})")

        # --- 5. číslo sedí 10 px nad ťuknutým bodem ---------------------------
        # bod, který jistě trefí vrstvu a NENÍ pod panelem
        fp = await h.free_point(0.25, 0.6)
        ok("volný bod na vrstvě nalezen", fp is not None, str(fp))
        before = len(await bar_nums(h))
        await h.finger_tap(fp["x"], fp["y"], r=11)
        await asyncio.sleep(0.8)
        items = await bar_nums(h)
        ok("ťuknutím se vložilo číslo", len(items) == before + 1, f"{before} -> {len(items)}")
        lay = json.loads(await h.ev(LAYER_JS % (fp["x"], fp["y"])))
        if items:
            it = items[-1]
            dy = lay["y"] - it["y"]
            ok("číslo je 10 px (±2) nad ťuknutým bodem", 8 <= dy <= 12,
               f"rozdíl {dy:.1f} px (x bodu {lay['x']:.1f} vs číslo {it['x']:.1f})")
            ok("číslo začíná na x ťuknutí (±2 px)", abs(lay["x"] - it["x"]) <= 2,
               f"dx {lay['x'] - it['x']:.1f} px")
        # Přepínač zůstává zapnutý i po vložení — číslování je série ťuknutí,
        # ne jedno číslo na každé zapnutí.
        ok("vkládání zůstává po vložení zapnuté",
           json.loads(await h.ev(PANEL_JS))["vals"]["insertOn"])

        # --- 6. klepnutí NA panel nevloží číslo -------------------------------
        n_before = len(await bar_nums(h))
        pt = json.loads(await h.ev("""(() => { const p = document.querySelector('.barnum-panel');
            const b = p.querySelector('.bn-btn'); const r = b.getBoundingClientRect();
            return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); })()"""))
        # klepnutí na TĚLO panelu (ne na tlačítko): mezi řádky
        body = json.loads(await h.ev("""(() => { const p = document.querySelector('.barnum-panel');
            const r = p.getBoundingClientRect();
            return JSON.stringify({ x: r.right - 4, y: r.top + r.height / 2 }); })()"""))
        await h.finger_tap(body["x"], body["y"], r=10)
        await asyncio.sleep(0.6)
        ok("klepnutí na panel nevloží číslo pod panel", len(await bar_nums(h)) == n_before)

        # --- 7. odtažení panelu + uložení pozice ------------------------------
        grip = json.loads(await h.ev("""(() => { const g = document.querySelector('.barnum-panel .panel-grip');
            const r = g.getBoundingClientRect();
            return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); })()"""))
        await h.finger_swipe(grip["x"], grip["y"], grip["x"] - 90, grip["y"] + 160, r=12, steps=8)
        moved = json.loads(await h.ev(PANEL_JS))["r"]
        ok("panel se dá odtáhnout", abs(moved["left"] - r["left"]) > 40,
           f"x {r['left']:.0f} -> {moved['left']:.0f}, y {r['top']:.0f} -> {moved['top']:.0f}")

        # --- 8. ZMĚNA KROKU PLATÍ UŽ U PRVNÍHO VLOŽENÍ -----------------------
        # Krok se „napíše“ do pole (input event); `change` přijde až s blurem,
        # tedy PO vložení — přesně ta situace, kterou Jan hlásil.
        prev_next = int(json.loads(await h.ev(PANEL_JS))["vals"]["next"])
        typed = await h.ev("""(() => { const p = document.querySelector('.barnum-panel');
            const el = p.querySelectorAll('.bn-input')[1];
            el.focus(); el.value = '6';
            el.dispatchEvent(new Event('input', { bubbles: true }));
            return el.value; })()""")
        ok("krok jde do pole napsat", typed == '6', str(typed))
        fp2 = await free_point_retry(h, 0.28, 0.62)
        await h.finger_tap(fp2["x"], fp2["y"], r=11)
        await asyncio.sleep(0.8)
        it2 = (await bar_nums(h))[-1]
        nxt_after = int(json.loads(await h.ev(PANEL_JS))["vals"]["next"])
        ok("vložené číslo = číslo před vložením", int(it2["text"]) == prev_next,
           f"vloženo {it2['text']}, mělo být {prev_next}")
        ok("NOVÝ krok (6) platí už u prvního vložení", nxt_after == prev_next + 6,
           f"další {prev_next} -> {nxt_after}")

        # --- 9. smazání číslování v CELÉM souboru ---------------------------
        # další číslo na JINÉ stránce → mazání musí projít všechny stránky
        # Listuj tlačítkem v anotaci, NE dialogem Přejít na stránku — ten
        # anotační režim VYPNE (jiný panel → vypnout anotaci), takže by panel
        # čísel zmizel a nebylo by co měřit.
        await h.ev("(() => { const b = [...document.querySelectorAll('.annot-nav-btn')]"
                   ".find(x => (x.title || '') === 'Další stránka'); if (b) b.click(); return !!b; })()")
        await h.wait_for("document.querySelector('.tb-page').textContent.trim().startsWith('2')",
                         timeout=15, label="page 2")
        fp3 = await free_point_retry(h, 0.3, 0.6)
        await h.finger_tap(fp3["x"], fp3["y"], r=11)
        await asyncio.sleep(0.9)
        # jedna NEčíselná anotace, aby „ostatní zůstaly“ nebylo prázdné tvrzení
        # (velký anotační panel je při číslování ZAVŘENÝ, takže se musí otevřít)
        await h.ev("(() => { const b = document.querySelector('.barnum-panel .bn-close'); if (b) b.click(); return !!b; })()")
        await asyncio.sleep(0.6)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        assert await pick_tool(h, "Tužka"), "nástroj Tužka nenalezen"
        await h.pen_stroke(300, 620, 420, 660)
        await asyncio.sleep(0.5)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        assert await open_barnum(h), "okno čísel se nepodařilo otevřít"
        assert await arm_insert(h), "nepodařilo se zapnout Vkládat"
        c0 = await counts(h)
        ok("čísla jsou na víc stránkách", c0["bar"] >= 3, str(c0))
        ok("v datech je i nečíselná anotace", c0["other"] >= 1, str(c0))
        clear_pt = json.loads(await h.ev("""(() => { const b = document.querySelector('.bn-clear');
            const r = b.getBoundingClientRect();
            return JSON.stringify({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); })()"""))
        await h.finger_tap(clear_pt["x"], clear_pt["y"], r=10)
        await asyncio.sleep(0.7)
        c1 = await counts(h)
        armed = await h.ev("!!document.querySelector('.bn-clear.armed')")
        ok("první klepnutí jen nabije (nic nemaže)", armed and c1["bar"] == c0["bar"],
           f"armed={armed} bar {c0['bar']} -> {c1['bar']}")
        await h.finger_tap(clear_pt["x"], clear_pt["y"], r=10)
        await asyncio.sleep(1.2)
        c2 = await counts(h)
        ok("druhé klepnutí smaže VŠECHNA čísla taktů", c2["bar"] == 0,
           f"bar {c1['bar']} -> {c2['bar']}")
        ok("ostatní anotace zůstaly", c2["other"] == c0["other"],
           f"jiné {c0['other']} -> {c2['other']}")
        ok("tlačítko se po smazání odjistilo",
           not await h.ev("!!document.querySelector('.bn-clear.armed')"))

        # --- 8. úzký telefon: panel se musí vejít a zůstat chytatelný -------
        await h.set_tablet(390, 844)
        await asyncio.sleep(0.8)
        ph = json.loads(await h.ev(PANEL_JS))
        pr = ph["r"]
        ok("na telefonu 390 px je panel celý na displeji",
           pr["left"] >= 0 and pr["right"] <= ph["vw"] and pr["bottom"] <= ph["vh"],
           f"panel {pr['left']:.0f}..{pr['right']:.0f} / displej {ph['vw']}x{ph['vh']}")
        bad_ph = [k for k in ph["kids"] if not k["hit"]]
        ok("na telefonu jsou ovládání chytatelná", not bad_ph, str(bad_ph))
        await h.set_tablet(800, 1280)
        await asyncio.sleep(0.6)

        # --- 9. screenshot pro oko -------------------------------------------
        import base64
        shot = await h.cdp("Page.captureScreenshot", {"format": "png"})
        with open("/tmp/barnum-panel.png", "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("   screenshot: /tmp/barnum-panel.png")

    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
