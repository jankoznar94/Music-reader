#!/usr/bin/env python3
"""Ověření DVOU nových funkcí čtečky not (Jan, Sep 2026):

  1) ODEBRÁNÍ KONKRÉTNÍCH STRÁNEK (vratné) — stránka zmizí z listování, počítadlo
     i pás miniatur pracují se zobrazenými stránkami, ale anotace/záložky/skoky
     zůstávají na původní indexy PDF; vrátit lze jednotlivě i všechny.
  2) ZOOM POD 100 % — mez 25 %, krok tlačítek 5 %, tlačítko 100 % vrací fit.
  3) GESTA PODLE POČTU PRSTŮ — 2 prsty = zoom + posun, 3 prsty = rotace
     (rotace rigidní: nemění měřítko ani posun).

Vše se měří na REÁLNÉM stavu DOM (ne na tom, že je něco v bundle).
"""
import asyncio
import importlib.util
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
Harness, Check, make_pdf = _mod.Harness, _mod.Check, _mod.make_pdf

STATE = r"""
(() => {
  const stage = document.querySelector('.stage');
  const rotor = document.querySelector('.rotor');
  const ms = stage ? new DOMMatrix(getComputedStyle(stage).transform) : null;
  const mr = rotor ? new DOMMatrix(getComputedStyle(rotor).transform) : null;
  const ind = document.querySelector('.tb-page-center');
  const thumbs = [...document.querySelectorAll('.thumb-item')];
  return {
    counter: ind ? ind.textContent.replace(/\s+/g, ' ').trim() : null,
    zoomPct: ms ? +Math.hypot(ms.a, ms.b).toFixed(4) : null,
    panX: ms ? +ms.e.toFixed(2) : null,
    panY: ms ? +ms.f.toFixed(2) : null,
    deg: mr ? +(Math.atan2(mr.b, mr.a) * 180 / Math.PI).toFixed(2) : null,
    thumbSlots: thumbs.map(t => t.dataset.idx),
    thumbNums: thumbs.map(t => (t.querySelector('.thumb-num') || {}).textContent || ''),
    thumbX: thumbs.filter(t => t.querySelector('.thumb-x')).length,
    pagesPanel: !!document.querySelector('.tb-btn[title="Odebrat stránky"]'),
    pagesPanelOn: !!document.querySelector('.zoom-panel') &&
      [...document.querySelectorAll('.top-bar .tb-btn')].some(b => (b.title||'')==='Odebrat stránky' && b.classList.contains('on')),
    pageGoHint: !!document.querySelector('.pg-hint'),
  };
})()
"""


def shown(counter):
    """Počet ZOBRAZENÝCH stránek z počítadla ('1 / 5 (z 6)' → 5)."""
    try:
        return int(str(counter).split("/")[1].split("(")[0].strip())
    except Exception:
        return -1


def pos(counter):
    """Pozice (čitatel) z počítadla ('3 / 5' → 3)."""
    try:
        return int(str(counter).split("/")[0].strip())
    except Exception:
        return -1


async def tap_tb(h, title):
    n = await h.ev(
        "(() => { const b=[...document.querySelectorAll('.tb-btn')]"
        ".find(x=>(x.title||'')===%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title))
    await asyncio.sleep(0.5)
    return n == 1


async def click_panel_btn(h, title):
    n = await h.ev(
        "(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')]"
        ".find(x=>(x.title||'')===%s); if(b) b.click(); return b?1:0; })()"
        % json.dumps(title))
    await asyncio.sleep(0.7)
    return n == 1


async def pinch(h, factor=1.35, move=0):
    """Dva prsty = zoom + posun (žádné rozhodování podle pohybu)."""
    g = await h.geo()
    cx = g["left"] + g["w"] / 2
    cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2
    r0 = 100
    await h.touch("touchStart", [(cx - r0, cy, 12), (cx + r0, cy, 12)])
    for i in range(1, 11):
        t = i / 10
        r = r0 * (1 + (factor - 1) * t)
        dx = move * t
        await h.touch("touchMove", [(cx - r + dx, cy, 12), (cx + r + dx, cy, 12)])
        await asyncio.sleep(0.02)
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.2)


async def rotate3(h, deg=40, radius=150):
    """TŘI prsty po kružnici (rozptyly konstantní) = čistá rotace.
    Tři prsty rozložené po 120° → rotace celé trojice o `deg`."""
    g = await h.geo()
    cx = g["left"] + g["w"] / 2
    cy = g["barBottom"] + (g["h"] - g["barBottom"]) / 2

    def pts(a0):
        return [(cx + radius * math.cos(a0 + k * 2 * math.pi / 3),
                 cy + radius * math.sin(a0 + k * 2 * math.pi / 3), 12) for k in range(3)]

    await h.touch("touchStart", pts(0.0))
    steps = 40
    for i in range(1, steps + 1):
        await h.touch("touchMove", pts(math.radians(deg * i / steps)))
        await asyncio.sleep(0.015)
    await h.touch("touchEnd", [])
    await asyncio.sleep(1.6)


async def main():
    ok = Check()
    pdf = make_pdf(6)
    async with Harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.0)
        await h.open_song(pdf=pdf, pages=6)
        await asyncio.sleep(1.2)

        # ---------- 1) tlačítko a otevření panelu ----------
        s = STATE
        st = await h.ev(s)
        ok("tlačítko „Odebrat stránky“ je v liště", st["pagesPanel"])
        ok("počítadlo začíná 1 / 6", pos(st["counter"]) == 1 and shown(st["counter"]) == 6, st["counter"])

        opened = await tap_tb(h, "Odebrat stránky")
        st = await h.ev(s)
        ok("panel odebírání se otevřel", opened and st["pagesPanelOn"], json.dumps(st)[:150])

        # ---------- 2) odebrat AKTUÁLNÍ stránku ----------
        await click_panel_btn(h, "Odebrat tuto stránku ze skladby")
        st = await h.ev(s)
        ok("počet ZOBRAZENÝCH stránek klesl na 5", shown(st["counter"]) == 5, st["counter"])
        ok("zůstali jsme na své stránce (pozice 1)", pos(st["counter"]) == 1, st["counter"])
        ok("počítadlo ukazuje i původní počet (z 6)", "z 6" in (st["counter"] or ""), st["counter"])
        # Pás miniatur je vidět jen s otevřeným sliderem — otevřít a zkontrolovat.
        await tap_tb(h, "Slider stránek")
        await asyncio.sleep(1.2)
        st = await h.ev(s)
        ok("v pásu miniatur je 5 položek s ✕", st["thumbX"] == 5 and st["thumbSlots"][:3] == ["0", "1", "2"], json.dumps(st)[:200])
        await tap_tb(h, "Slider stránek")
        await asyncio.sleep(0.4)

        # odebraná stránka NENÍ v pásu (slot 0 = původní 1. stránka odebrána → sloty 0,1.. = PDF 1,2..)
        # (aktuální stránka byla 0 → odebrána → přesun na PDF 1, který je teď slot 0)
        ok("aktualni stranka se posunula na nejblizsi viditelnou", st["counter"] and st["counter"].startswith("1 / 5"), st["counter"])

        # ---------- 3) odebrání KONKRÉTNÍ stránky z pásu ----------
        await tap_tb(h, "Slider stránek")
        await asyncio.sleep(1.2)
        removed = await h.ev(
            "(() => { const t=[...document.querySelectorAll('.thumb-item')][2];"
            " if(!t) return 'none'; const x=t.querySelector('.thumb-x');"
            " const idx=t.dataset.idx; x.click(); return idx; })()")
        await asyncio.sleep(1.2)
        st = await h.ev(s)
        ok("✕ na miniaturе odebere prave tu stranku (4 zobrazene)", shown(st["counter"]) == 4, f"clicked_slot={removed} · {st['counter']}")
        ok("odebrání JINÉ stránky mi neshodí pozici v notách (zůstávám na 1.)", pos(st["counter"]) == 1, st["counter"])

        # ---------- 4) vrácení JEDNÉ stránky ze seznamu ----------
        await tap_tb(h, "Slider stránek")   # zavřít pás, ať nepřekáží
        await tap_tb(h, "Odebrat stránky")   # otevřít panel odebírání
        await click_panel_btn(h, "Seznam odebraných stránek")
        await asyncio.sleep(0.4)
        rows = await h.ev("(() => document.querySelectorAll('.pages-list .jp-item').length)()")
        ok("seznam odebraných má 2 řádky", rows == 2, f"rows={rows}")
        await h.ev("(() => { const b=[...document.querySelectorAll('.pages-list .jp-item .jp-btn')][0]; if(b) b.click(); return true; })()")
        await asyncio.sleep(1.0)
        st = await h.ev(s)
        ok("vrácení jedné stránky → 5 zobrazených", shown(st["counter"]) == 5, st["counter"])

        # ---------- 5) vrátit všechny ----------
        await click_panel_btn(h, "Vrátit odebrané stránky")
        st = await h.ev(s)
        ok("vrácení všech → 6 zobrazených", shown(st["counter"]) == 6, st["counter"])
        ok("„(z 6)“ zmizelo, když nic není odebrané", "z 6" not in (st["counter"] or ""), st["counter"])

        # ---------- 6) trvalost (IndexedDB) ----------
        await click_panel_btn(h, "Odebrat tuto stránku ze skladby")
        st = await h.ev(s)
        ok("znovu odebráno → 5 zobrazených", shown(st["counter"]) == 5, st["counter"])
        # Reload znovu otevře appku v KNIHOVNĚ (router), skladba je v IndexedDB →
        # otevřít ji znovu přes UI, bez nového uploadu (to je podstata testu trvalosti).
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.2)
        await h.ev(h.expand_authors_js())
        await asyncio.sleep(0.4)
        await h.click(".song-name")
        await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="znova otevrit")
        await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="prvni stranka")
        await asyncio.sleep(1.2)
        st = await h.ev(s)
        ok("odebrání PŘEŽILO reload (5 zobrazených)", shown(st["counter"]) == 5, st["counter"])
        await tap_tb(h, "Odebrat stránky")
        await click_panel_btn(h, "Vrátit odebrané stránky")
        st = await h.ev(s)
        ok("úklid: zpět na 6 zobrazených", shown(st["counter"]) == 6, st["counter"])
        await tap_tb(h, "Odebrat stránky")  # zavřít panel

        # ---------- 7) ZOOM POD 100 % ----------
        st = await h.ev(s)
        z0 = st["zoomPct"]
        ok("výchozí zoom = 100 %", abs(z0 - 1.0) < 0.02, str(z0))
        await tap_tb(h, "Zvětšení a posun")
        for _ in range(4):
            await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')].find(x=>x.textContent.trim()==='−10'); if(b) b.click(); return b?1:0; })()")
            await asyncio.sleep(0.25)
        st = await h.ev(s)
        ok("po 4× „−10“ je zoom 60 % (< 100 %)", abs(st["zoomPct"] - 0.60) < 0.02, str(st["zoomPct"]))
        for _ in range(8):
            await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')].find(x=>x.textContent.trim()==='−10'); if(b) b.click(); return 1; })()")
            await asyncio.sleep(0.2)
        st = await h.ev(s)
        ok("zoom se zastaví na minimu 25 %", abs(st["zoomPct"] - 0.25) < 0.02, str(st["zoomPct"]))
        # tlačítko 100 %
        await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')].find(x=>x.textContent.trim()==='100 %'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(0.5)
        st = await h.ev(s)
        ok("tlačítko „100 %“ vrátí fit", abs(st["zoomPct"] - 1.0) < 0.02, str(st["zoomPct"]))
        # pinch dolů musí jít taky pod 100 %
        await pinch(h, factor=0.55)
        st = await h.ev(s)
        ok("pinch dvěma prsty oddálí pod 100 %", st["zoomPct"] < 0.95 and st["zoomPct"] >= 0.24, str(st["zoomPct"]))
        # a nahoru
        await pinch(h, factor=1.9)
        st = await h.ev(s)
        ok("pinch dvěma prsty přiblíží", st["zoomPct"] > 0.9, str(st["zoomPct"]))
        await h.ev("(() => { const b=[...document.querySelectorAll('.zoom-panel .zp-btn')].find(x=>x.textContent.trim()==='100 %'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(0.4)

        # ---------- 8) GESTA: 2 prsty zoom/posun, 3 prsty rotace ----------
        st = await h.ev(s)
        ok("před gesty: úhel 0°", abs(st["deg"]) < 0.01, str(st["deg"]))
        await pinch(h, factor=1.5, move=70)
        st = await h.ev(s)
        ok("2 prsty: zoom se změnil", st["zoomPct"] > 1.05, str(st["zoomPct"]))
        ok("2 prsty: posun se změnil", abs(st["panX"]) > 1 or abs(st["panY"]) > 1, f"panX={st['panX']} panY={st['panY']}")
        ok("2 prsty: rotace se NEZMĚNILA", abs(st["deg"]) < 0.01, str(st["deg"]))
        z_before, px_before, py_before = st["zoomPct"], st["panX"], st["panY"]

        await rotate3(h, deg=40)
        st = await h.ev(s)
        ok("3 prsty: rotace se změnila (~40°)", abs(abs(st["deg"]) - 40) < 6, str(st["deg"]))
        ok("3 prsty: zoom se NEZMĚNIL (rigidní rotace)", abs(st["zoomPct"] - z_before) < 0.01, f"{z_before} → {st['zoomPct']}")
        ok("3 prsty: posun se NEZMĚNIL", abs(st["panX"] - px_before) < 1 and abs(st["panY"] - py_before) < 1, f"{px_before},{py_before} → {st['panX']},{st['panY']}")

        # ---------- 9) mřížka jen u rotace ----------
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')].find(x=>(x.title||'')==='Rotace stránky'); if(b) b.click(); return 1; })()")
        await asyncio.sleep(0.5)
        grid = await h.ev("(() => !!document.querySelector('.rot-grid'))()")
        ok("mřížka je vidět v nabídce rotace", grid is True, str(grid))

    ok.report()


if __name__ == "__main__":
    asyncio.run(main())
