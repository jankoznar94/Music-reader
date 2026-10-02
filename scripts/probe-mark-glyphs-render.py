#!/usr/bin/env python3
"""Ověření: glyfy Značek se SKUTEČNĚ vykreslují (ne prázdné obdélníčky).

Jan: „Celý tento nástroj nemá ikonu a ani jednotlivé prvky v tomto nástroji ji
nemají. Vše jsou jen obdélníčky jakožto náhrada nenactene ikony/textu."

PROČ TO MĚŘIT INKOUSTEM, A NE PŘÍTOMNOSTÍ V DOM:
Když font glyf NEMÁ, prohlížeč použije `.notdef` — „tofu" obdélníček. Ten má
NENULOVOU šířku (0,375 em) i nenulový inkoust, takže testy typu „element
existuje / má šířku > 0 / textContent je správný znak" projdou, i když uživatel
vidí prázdné obdélníčky. Přesně tak se Značky tvářily jako funkční.

ROZHODUJÍCÍ MĚŘENÍ (dvě nezávislá, obě v sondě):
  1) INKOUST vs notdef — vykresli kód fontem NotyDyn a porovnej s kódem, který
     ve fontu URČITĚ není (U+EFFF). Když jsou obrazce shodné, glyf chybí.
  2) ADVANCE — změř šířku glyfu a porovnej s metrikou z fontu (MARK_ADV).
     Chybějící glyf dá 0,375 em (notdef) místo skutečné šířky.

Prostředí: dev server :5173 + headless Chrome s CDP na :9222.
⚠️ Font se musí nejdřív vynutit (`document.fonts.load`) — bez toho je ve stavu
„unloaded" a canvas vykreslí fallback.
"""
import asyncio
import importlib.util
import json
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


def fresh_harness(url="http://localhost:5173/"):
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(url)
    h._fresh_target = info.get("id")
    return h


# Klíč → (kód, šířka z metrik fontu v em) — stejná čísla jako MARK_ADV v appce.
MARKS = {
    "bb":     (0xE264, 0.413), "b": (0xE260, 0.226), "odr": (0xE261, 0.168),
    "k":      (0xE262, 0.249), "kk": (0xE263, 0.250),
    "trylek": (0xE566, 0.521), "obal": (0xE567, 0.460),
    "obalo":  (0xE568, 0.457), "trylks": (0xE56C, 0.730),
    "mord":   (0xE56D, 0.729),
    "ferm":   (0xE4C0, 0.605), "cez": (0xE4D1, 0.385),
    "dech":   (0xE4CE, 0.153), "akc": (0xE4A0, 0.339),
    "stacc":  (0xE4A2, 0.084), "ten": (0xE4A4, 0.338),
    "dyn_mf": (0xE52D, 0.797), "dyn_pp": (0xE52B, 0.727),
}
NOTDEF_CP = 0xEFFF   # ve fontu není → vykreslí se .notdef (tofu)
NOTDEF_ADV = 0.375   # advance .notdef z fontu

# Vrátí {ink, advanceEm} pro daný kód. Font se vynutí před měřením.
MEASURE = """(async (cp) => {
  try { await document.fonts.load('40px NotyDyn'); } catch (e) {}
  const S = 64, PX = 40;
  const cv = document.createElement('canvas');
  cv.width = S; cv.height = S;
  const ctx = cv.getContext('2d');
  ctx.font = PX + 'px NotyDyn';
  ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left';
  const adv = ctx.measureText(String.fromCodePoint(cp)).width / PX;
  ctx.clearRect(0, 0, S, S);
  ctx.fillStyle = '#000';
  ctx.fillText(String.fromCodePoint(cp), 2, S - 10);
  const d = ctx.getImageData(0, 0, S, S).data;
  let ink = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 40) ink++;
  return { ink: ink, advanceEm: +adv.toFixed(4) };
})"""


async def measure(h, cp):
    return await h.ev(f"({MEASURE})({cp})", await_promise=True)


async def main():
    ok = Check()
    async with fresh_harness() as h:
        await h.open()
        await h.set_tablet(800, 1280, 2)
        await asyncio.sleep(1.5)

        # Vynuť font; bez toho je „unloaded" a měřil by se fallback.
        await h.ev("(async()=>{try{await document.fonts.load('40px NotyDyn')}catch(e){};return 1})()",
                   await_promise=True)
        await asyncio.sleep(0.6)
        ready = await h.ev("document.fonts.check('40px NotyDyn')")
        ok("font NotyDyn je načtený", ready, f"check={ready}")
        if not ready:
            print("   fonty:", await h.ev("JSON.stringify([...document.fonts].map(f=>[f.family,f.status]))"))

        tofu = await measure(h, NOTDEF_CP)
        print(f"   notdef (U+EFFF): inkoust={tofu['ink']} advance={tofu['advanceEm']} em")

        # Kontrola slepoty: neznámý kód MUSÍ vyjít jako notdef. Kdyby ne,
        # sonda by nedokázala rozlišit chybějící glyf od skutečného.
        ok("kontrola slepoty: neznámý kód dá notdef (0,375 em)",
           abs(tofu["advanceEm"] - NOTDEF_ADV) < 0.01,
           f"advance={tofu['advanceEm']} em, čekáno {NOTDEF_ADV}")

        bad = []
        for key, (cp, exp_adv) in MARKS.items():
            m = await measure(h, cp)
            real = (abs(m["advanceEm"] - exp_adv) < 0.02
                    and m["ink"] > 0
                    and m["ink"] != tofu["ink"])
            if not real:
                bad.append(key)
            ok(f"glyf {key} ({hex(cp)}) se vykresluje", real,
               f"inkoust={m['ink']} (notdef {tofu['ink']}), "
               f"advance={m['advanceEm']} em (čekáno {exp_adv})")

        if bad:
            print(f"\n   CHYBÍ GLYFY: {bad}")
        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
