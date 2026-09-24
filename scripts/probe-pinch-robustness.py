#!/usr/bin/env python3
"""OVĚŘENÍ opravy dvouprstého zoomu (Jan, Sep 2026): „chvíli zoomuje, pak ne,
jako kdyby prsty ztratily kontakt“.

Měří se chování appky, ne to, že je něco v bundle. Zoom se čte z transformu
`.stage` (panel zoomu zavře kdejaký tap), rotace z `.rotor` přes DOMMatrix.

⚠️ DVA PROSTŘEDÍ, KTERÁ SONDU ZABIJÍ (obojí naměřeno, obojí se hlásí jako
falešný FAIL „oprava nefunguje“):
  1. **Zaseknutý renderer.** Po pokusech s `Emulation.setTouchEmulationEnabled`
     přestane Chrome doručovat dotyky ÚPLNĚ (i mouse funguje dál, takže to
     vypadá, že CDP žije). Řešení: otevřít NOVÝ page target přes
     `PUT /json/new` a měřit v něm — čerstvý renderer doručuje hned.
     Proto `fresh_harness()` níže.
  2. **`Emulation.setTouchEmulationEnabled`** — v této sestavě doručování
     dotyků naopak ZABIJE. Nikdy ho nezapínej.
  Oba případy odhalí preflight; bez něj sonda vyplivne samé nuly.

Scénáře:
  A) čistý pinch ................................... zoomne (kontrola)
  B) dva PRSTY + opřená DLAŇ (r=70) ................ zoom MUSÍ pokračovat
     a dlaň nesmí stránku pootočit (klíčová oprava — dřív dlaň = třetí prst)
  C) dlaň přidána a odebrána uprostřed pinche ....... zoom MUSÍ pokračovat
  D) jeden prst zvednut, druhý táhne ................ posun (stav dřív visel)
  E) touchcancel uprostřed gesta .................... gesto se uklidí
  F) strop zoomu .................................... clamp 2,5
  G) tři PRSTY ...................................... otočí ~40°, NEZMĚNÍ zoom/posun
"""
import asyncio
import importlib.util
import json
import math
import os
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
CDP_BASE = "http://127.0.0.1:9222"


def _load_harness():
    for cand in (
        os.path.join(_HERE, "cdp-e2e-harness.py"),
        os.path.expanduser(
            "~/.hermes/profiles/cfsb-agent/skills/software-development/"
            "pwa-pdf-viewer/scripts/cdp-e2e-harness.py"),
    ):
        if os.path.exists(cand):
            spec = importlib.util.spec_from_file_location("cdp_e2e_harness", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit("nenalezen cdp-e2e-harness.py")


_mod = _load_harness()
Harness, Check = _mod.Harness, _mod.Check


def fresh_harness(url=None):
    """Harness na NOVĚ otevřeném tabu (čerstvý renderer).

    Nutné: starý renderer po pokusech s emulací dotyky nedoručuje a sonda by
    měřila nuly. `Harness.__aenter__` bere první page target, což je po
    `PUT /json/new` přesně ten nový.
    """
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(url or _mod.APP_URL)
    h._fresh_target = info.get("id")
    return h

STATE = r"""
(() => {
  const stage = document.querySelector('.stage');
  const rotor = document.querySelector('.rotor');
  const ms = stage ? new DOMMatrix(getComputedStyle(stage).transform) : null;
  const mr = rotor ? new DOMMatrix(getComputedStyle(rotor).transform) : null;
  return {
    zoom: ms ? +Math.hypot(ms.a, ms.b).toFixed(4) : null,
    panX: ms ? +ms.e.toFixed(2) : null,
    panY: ms ? +ms.f.toFixed(2) : null,
    deg: mr ? +(Math.atan2(mr.b, mr.a) * 180 / Math.PI).toFixed(2) : null,
  };
})()
"""

# Panel zoomu je potřeba OTEVŘÍT, jinak tlačítka „100 %" v DOM vůbec nejsou a
# RESET tiše neudělá nic → měření pak začíná na zoomu 2,5 z předchozího případu
# a hlásí nesmysly (naměřeno: „zoom se změnil 2,5 -> 1,45").
OPEN_ZOOM = ("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
             ".find(x => (x.title || '').startsWith('Zvětšení')); if (b) b.click(); })()")

# Posun i zoom na výchozí stav. Vycentrovat vrací ULOŽENÉ zobrazení, proto se
# používá „100 %" z panelu zoomu, a úhel se nuluje tlačítkem .zp-rot.
RESET_STATE = ("(async () => { const z=[...document.querySelectorAll('.zp-btn')]"
               ".find(x=>x.title==='Zpět na 100 % (fit na šířku)'); if(z) z.click();"
               " const r=document.querySelector('.zp-rot'); if(r) r.click();"
               " return true; })()")


async def open_viewer(h, pages=6):
    """Otevři prohlížeč BEZ mazání IndexedDB.

    `Harness.open_song(reset=True)` maže databázi — jenže appka drží spojení
    otevřené, takže `deleteDatabase` zůstane zablokovaný (DOMException) a test
    spadne dřív, než něco změří. Pro gesta je jedno, KTERÁ skladba je otevřená,
    takže použijeme existující a fixture nahrajeme jen když žádná není.

    ⚠️ NIKDY nezapínej `Emulation.setTouchEmulationEnabled` — v této sestavě
    headless Chrome to doručování dotyků naopak ZABIJE (změřeno: s ním
    `Input.dispatchTouchEvent` nedoručí nic, bez něj dorazí touchstart/move/end
    správně). `Emulation.setDeviceMetricsOverride` s `mobile: True` stačí.
    `navigator.maxTouchPoints` zůstane 0 i tak — to je normální a nic neznamená.
    """
    await h.open()
    await h.set_tablet(800, 1280, 2)
    await asyncio.sleep(1.0)
    existing = await h.ev("document.querySelectorAll('li.song').length")
    if not existing:
        await h.set_file_input("input[type=file]", _mod.make_pdf(pages))
        await h.wait_for("document.querySelectorAll('.author-group').length > 0",
                         timeout=60, label="PDF upload")
    await h.ev(_mod.Harness.expand_authors_js())
    await h.wait_for("document.querySelectorAll('li.song').length > 0",
                     timeout=10, label="expand authors")
    await h.click(".song-name")
    await h.wait_for("!!document.querySelector('.tb-page')", timeout=40, label="open viewer")
    await h.wait_for("!document.querySelector('.viewer-loading')", timeout=40, label="first page")
    await asyncio.sleep(1.0)

# Kolik dotyků appka v každé chvíli viděla + jestli přišel touchcancel.
LOG_INSTALL = r"""
(() => {
  const v = document.querySelector('.viewer');
  if (!v || window.__tlog) return !!window.__tlog;
  window.__tlog = [];
  const rec = (e) => window.__tlog.push({
    t: e.type.replace('touch', ''), n: e.touches.length,
    r: [...e.touches].map(x => Math.round(Math.max(x.radiusX || 0, x.radiusY || 0))),
  });
  for (const k of ['touchstart','touchmove','touchend','touchcancel'])
    v.addEventListener(k, rec, { capture: true, passive: true });
  return true;
})()
"""


def _centre(g):
    return (g["left"] + g["w"] / 2, g["barBottom"] + (g["h"] - g["barBottom"]) / 2)


class S:
    """Body dotyků ve vzdálenosti `r` od středu (vodorovně).

    ⚠️ `three()` musí mít třetí dotyk s poloměrem DLANĚ (70), ne prstu (12) —
    jinak testujeme tři prsty a appka správně rotuje, takže sonda hlásí falešný
    FAIL „dlaň neotočila stránku“. Přesně na tomhle jsem spálila jeden běh.
    """

    def __init__(self, cx, cy):
        self.cx, self.cy = cx, cy

    def two(self, r, r2=None, dx=0):
        rr = r if r2 is None else r2
        return [(self.cx - r + dx, self.cy, 12), (self.cx + rr + dx, self.cy, 12)]

    def two_with_palm(self, r, palm_dx=330, palm_dy=300, palm_r=70):
        """Dva PRSTY + opřená DLAŇ (velký poloměr kontaktu)."""
        return [(self.cx - r, self.cy, 12), (self.cx + r, self.cy, 12),
                (self.cx + palm_dx, self.cy + palm_dy, palm_r)]

    def three_fingers(self, r, spread=300):
        """Tři PRSTY (všechny malý poloměr) — pro rotaci."""
        return [(self.cx - r, self.cy, 12), (self.cx + r, self.cy, 12),
                (self.cx, self.cy + spread, 12)]


async def pinch_steps(h, pts, r_from, r_to, steps=8, sleep=0.02):
    for i in range(1, steps + 1):
        r = r_from + (r_to - r_from) * i / steps
        await h.touch("touchMove", pts(r))
        await asyncio.sleep(sleep)


async def main():
    ok = Check()
    async with fresh_harness() as h:
        await open_viewer(h)
        g = await h.geo()
        cx, cy = _centre(g)
        s = S(cx, cy)

        # ---------- PREFLIGHT: bez doručovaných dotyků je každé další měření
        # nesmysl (sonda pak hlásí samé nuly a vypadá to jako chyba appky).
        # Přesně to se stalo: Chrome po restartu hlásil maxTouchPoints: 0 a
        # `Input.dispatchTouchEvent` nedoručil vůbec nic.
        mtp = await h.ev("navigator.maxTouchPoints")
        # `maxTouchPoints` je v headless Chrome 0 i tehdy, když dotyky chodí —
        # je to slabý signál, jen se vypíše pro kontext.
        print(f"   preflight: maxTouchPoints={mtp} (0 je v headless normální)")
        await h.ev("(() => { window.__pre=[];"
                   " document.addEventListener('touchstart', e => window.__pre.push(e.touches.length),"
                   " { capture: true, passive: true }); return true; })()")
        await h.touch("touchStart", s.two(100))
        await asyncio.sleep(0.1)
        await h.touch("touchEnd", [])
        pre = await h.ev("JSON.stringify(window.__pre)")
        # Rozhoduje DORUČENÍ dotyku, ne maxTouchPoints: bez něj by sonda měřila
        # samé nuly a hlásila by falešný FAIL „oprava nefunguje“.
        ok("preflight: syntetický dvouprstý dotyk se doručí do stránky",
           pre is not None and pre.startswith("[") and "2" in pre,
           f"zaznamenané touchstarty: {pre}")
        if not (pre is not None and pre.startswith("[") and "2" in pre):
            print("\nPREFLIGHT FAILED — prostředí nedoručuje dotyky, měření by lhalo. Konec.")
            return ok.report()

        assert await h.ev(LOG_INSTALL), "hook se nenainstaloval"

        # Panel zoomu musí být OTEVŘENÝ, jinak tlačítka „100 %"/„+"/„−" v DOM
        # nejsou a reset stavu tiše neudělá nic (měření by pak začínalo na
        # zoomu z předchozího případu).
        await h.ev(OPEN_ZOOM)
        await asyncio.sleep(0.5)

        # ---------- A) čistý pinch ----------
        st0 = await h.ev(STATE)
        await h.touch("touchStart", s.two(100))
        await pinch_steps(h, s.two, 100, 200)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.7)
        stA = await h.ev(STATE)
        ok("A) čistý pinch zoomne", stA["zoom"] > st0["zoom"] + 0.3,
           f"{st0['zoom']} -> {stA['zoom']}")
        await h.ev(RESET_STATE); await asyncio.sleep(0.8)

        # ---------- B) pinch + opřená dlaň (třetí dotyk se nehýbe) ----------
        # KLÍČOVÝ PŘÍPAD: dlaň má poloměr 70 (viz two_with_palm). Kdyby se dlaň
        # počítala jako třetí prst, gesto by se překlopilo do rotace → zoom by
        # ztuhl a stránka by se pootočila. Přesně to je Janovo „chvíli zoomuje,
        # pak najednou ne, jako by prsty ztratily kontakt“.
        st0 = await h.ev(STATE)
        await h.touch("touchStart", s.two_with_palm(100))
        await pinch_steps(h, s.two_with_palm, 100, 200, steps=10)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.7)
        stB = await h.ev(STATE)
        ok("B) pinch s opřenou dlaní: zoom POKRAČUJE", stB["zoom"] > st0["zoom"] + 0.3,
           f"{st0['zoom']} -> {stB['zoom']}")
        ok("B) nehybná dlaň neotočila stránku", abs(stB["deg"] - st0["deg"]) < 0.5,
           f"{st0['deg']} -> {stB['deg']}")
        print("   B) log:", json.dumps(await h.ev(
            "window.__tlog.slice(-3)"))[:200])
        await h.ev(RESET_STATE); await asyncio.sleep(0.8)

        # ---------- C) dlaň přidána a odebrána uprostřed pinche ----------
        await h.ev("window.__tlog.length = 0")
        await h.touch("touchStart", s.two(100))
        await pinch_steps(h, s.two, 100, 130, steps=4)
        mid_zoom = (await h.ev(STATE))["zoom"]
        # dlaň se přidá (dotyk navíc, poloměr 70)…
        await h.touch("touchStart", s.two_with_palm(130))
        await asyncio.sleep(0.05)
        # …a zase zmizí
        await h.touch("touchEnd", s.two(130))
        await asyncio.sleep(0.05)
        # uživatel pokračuje v pinchi stejným směrem
        await pinch_steps(h, s.two, 130, 200, steps=8)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.7)
        stC = await h.ev(STATE)
        ok("C) po odebrání dlaně zoom POKRAČUJE",
           stC["zoom"] - mid_zoom > 0.2,
           f"{mid_zoom} -> {stC['zoom']}")
        print("   C) log:", json.dumps(await h.ev(
            "window.__tlog.slice()"))[:400])
        await h.ev(RESET_STATE); await asyncio.sleep(0.8)

        # ---------- D) ZTRÁTA KONTAKTU UPROSTŘED GESTA ----------
        # Co je podstatné (a co bylo rozbité): po ztrátě jednoho prstu zůstal
        # stav gesta viset, a když uživatel prst znovu přiložil, zoom se do
        # mrtvého stavu jen „přilepil“ a NEREAGOVAL do konce tahu.
        # Test: pinch → prst se zvedne → prst se vrátí → pinch MUSÍ pokračovat.
        await h.ev("window.__tlog.length = 0")
        await h.touch("touchStart", s.two(120))
        await pinch_steps(h, s.two, 120, 150, steps=4)
        before = await h.ev(STATE)
        # jeden prst se zvedne (zůstane jen druhý)
        await h.touch("touchEnd", [(cx - 150, cy, 12)])
        await asyncio.sleep(0.06)
        # …a znovu se přiloží
        await h.touch("touchStart", s.two(150))
        await asyncio.sleep(0.06)
        # uživatel pokračuje v pinchi stejným směrem
        await pinch_steps(h, s.two, 150, 210, steps=8)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        stD = await h.ev(STATE)
        print("   D) log:", json.dumps(await h.ev(
            "window.__tlog.slice()"))[:500])
        ok("D) po ztrátě a obnovení kontaktu zoom POKRAČUJE",
           stD["zoom"] - before["zoom"] > 0.2,
           f"{before['zoom']} -> {stD['zoom']}")
        ok("D) rotace se přitom nezměnila", abs(stD["deg"] - before["deg"]) < 0.5,
           f"{before['deg']} -> {stD['deg']}")
        await h.ev(RESET_STATE); await asyncio.sleep(0.8)

        # ---------- E) touchcancel uprostřed gesta ----------
        await h.touch("touchStart", s.two(100))
        await pinch_steps(h, s.two, 100, 140, steps=4)
        await h.cdp("Input.dispatchTouchEvent", {"type": "touchCancel", "touchPoints": []})
        await asyncio.sleep(0.3)
        cancel_seen = await h.ev("window.__tlog.filter(x=>x.t==='cancel').length")
        ok("E) touchcancel došel do appky (handler existuje)", cancel_seen > 0,
           f"cancel událostí: {cancel_seen}")
        # nové gesto po cancelu musí normálně zoomovat
        z0 = (await h.ev(STATE))["zoom"]
        await h.touch("touchStart", s.two(100))
        await pinch_steps(h, s.two, 100, 180, steps=6)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.6)
        z1 = (await h.ev(STATE))["zoom"]
        ok("E) po touchcancelu nové gesto znovu zoomuje", z1 > z0 + 0.2,
           f"{z0} -> {z1}")
        await h.ev(RESET_STATE); await asyncio.sleep(0.8)

        # ---------- F) strop zoomu ----------
        await h.touch("touchStart", s.two(40))
        await pinch_steps(h, s.two, 40, 380, steps=14)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)
        zmax = (await h.ev(STATE))["zoom"]
        ok("F) strop: zoom se zastaví na 2,5 (ne přetečení)",
           abs(zmax - 2.5) < 0.01, str(zmax))
        await h.ev(RESET_STATE); await asyncio.sleep(0.8)

        # ---------- G) tři PRSTY = rigidní rotace ----------
        await h.touch("touchStart", s.two(120))
        await pinch_steps(h, s.two, 120, 150, steps=3)
        await h.touch("touchEnd", [])
        await asyncio.sleep(0.4)
        # Rotace se MUSÍ vynulovat před měřením — předchozí případy po sobě
        # nechávají úhel (např. 12°) a sonda by pak hlásila 52° místo 40°.
        # Přesně tenhle falešný FAIL jsem dostala napoprvé.
        await h.ev("(() => { const b=document.querySelector('.zp-rot'); if(b) b.click(); })()")
        await asyncio.sleep(1.4)
        before = await h.ev(STATE)
        ok("G) před rotací je úhel vynulovaný", abs(before["deg"]) < 0.5, str(before["deg"]))

        def pts(a0):
            return [(cx + 150 * math.cos(a0 + k * 2 * math.pi / 3),
                     cy + 150 * math.sin(a0 + k * 2 * math.pi / 3), 12)
                    for k in range(3)]

        await h.touch("touchStart", pts(0.0))
        for i in range(1, 41):
            await h.touch("touchMove", pts(math.radians(40 * i / 40)))
            await asyncio.sleep(0.015)
        await h.touch("touchEnd", [])
        await asyncio.sleep(1.4)
        stG = await h.ev(STATE)
        ok("G) tři prsty otočí ~40°", abs(abs(stG["deg"]) - 40) < 6, str(stG["deg"]))
        ok("G) rotace je rigidní: zoom se nezměnil",
           abs(stG["zoom"] - before["zoom"]) < 0.02,
           f"{before['zoom']} -> {stG['zoom']}")
        ok("G) rotace je rigidní: posun se nezměnil",
           abs(stG["panX"] - before["panX"]) < 1 and abs(stG["panY"] - before["panY"]) < 1,
           f"{before['panX']},{before['panY']} -> {stG['panX']},{stG['panY']}")

    return ok.report()


if __name__ == "__main__":
    port = os.environ.get("CDP_PORT", "9222")
    _mod.CDP_HTTP = f"http://127.0.0.1:{port}"
    raise SystemExit(asyncio.run(main()))
