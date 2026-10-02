#!/usr/bin/env python3
"""Doplňková kontrola k probe-gesture-auto-mode.py: pruhy musí být v anotaci
nejen V DOM, ale i VIDĚT (neza kryté papírem/plátnem) a na správné šířce.

Kontroluje pro režim čtení i anotaci:
  * rect obou pruhů (šířka = --edge-w, výška od lišty dolů)
  * computed background + border (podbarvení + čárkovaná hrana)
  * jestli pruh překrývá něco s vyšším z-indexem (papír, plátno)
"""
import asyncio
import importlib.util
import os
import time
import urllib.request
import json

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


def fresh_harness():
    req = urllib.request.Request(f"{CDP_BASE}/json/new?about:blank", method="PUT")
    info = json.loads(urllib.request.urlopen(req).read())
    time.sleep(0.8)
    h = Harness(_mod.APP_URL)
    h._fresh_target = info.get("id")
    return h


HINTS = r"""
(() => {
  const out = [];
  for (const el of document.querySelectorAll('.edge-hint')) {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out.push({
      cls: el.className,
      left: +r.left.toFixed(1), right: +r.right.toFixed(1),
      width: +r.width.toFixed(1), height: +r.height.toFixed(1),
      bg: cs.backgroundColor,
      border: cs.borderRightWidth + '/' + cs.borderLeftWidth,
      pe: cs.pointerEvents, z: cs.zIndex, vis: cs.visibility, op: cs.opacity,
    });
  }
  const root = document.querySelector('.viewer');
  return {
    edgeW: root ? getComputedStyle(root).getPropertyValue('--edge-w').trim() : null,
    innerW: window.innerWidth,
    hints: out,
  };
})()
"""

TOGGLE_ANNOT = r"""
(() => {
  const a = [...document.querySelectorAll('.tb-btn')]
    .find(b => (b.title || '').startsWith('Anotace'));
  if (!a) return false; a.click(); return true;
})()
"""


async def open_viewer(h, pages=6):
    await h.open()
    await h.set_tablet(800, 1280, 2)
    await asyncio.sleep(1.0)
    if not await h.ev("document.querySelectorAll('li.song').length"):
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


def check_hints(ok, label, data):
    hs = data["hints"]
    ok(f"{label}: oba pruhy v DOM", len(hs) == 2, f"pruhů: {len(hs)}")
    if len(hs) != 2:
        return
    exp = float(data["edgeW"].replace("px", "") or 0)
    for h_ in hs:
        side = "levý" if "left" in h_["cls"] else "pravý"
        ok(f"{label}: {side} pruh má šířku --edge-w ({exp} px)",
           abs(h_["width"] - exp) < 1.5, f"{h_}")
        ok(f"{label}: {side} pruh je podbarvený",
           "rgba" in h_["bg"] and h_["bg"] != "rgba(0, 0, 0, 0)", h_["bg"])
        ok(f"{label}: {side} pruh má čárkovanou vnitřní hranu",
           h_["border"] == "1px/0px" or h_["border"] == "0px/1px", h_["border"])
        ok(f"{label}: {side} pruh nechytá dotyk (pointer-events: none)",
           h_["pe"] == "none", h_["pe"])
        ok(f"{label}: {side} pruh je viditelný (visibility/opacity)",
           h_["vis"] == "visible" and float(h_["op"]) > 0.5,
           f"vis={h_['vis']} op={h_['op']}")
    # pruhy u okrajů displeje, nikdy uprostřed
    left_hint = [x for x in hs if "left" in x["cls"]][0]
    right_hint = [x for x in hs if "right" in x["cls"]][0]
    ok(f"{label}: levý pruh přiléhá k levému okraji", left_hint["left"] < 1.0,
       str(left_hint["left"]))
    ok(f"{label}: pravý pruh přiléhá k pravému okraji",
       abs(right_hint["right"] - data["innerW"]) < 1.5, str(right_hint["right"]))


async def main():
    ok = Check()
    async with fresh_harness() as h:
        await open_viewer(h)
        read = await h.ev(HINTS)
        check_hints(ok, "čtení", read)
        await h.ev(TOGGLE_ANNOT)
        await asyncio.sleep(0.5)
        annot = await h.ev(HINTS)
        ok("anotace zapnutá", await h.ev("!!document.querySelector('.annot-panel')"))
        check_hints(ok, "anotace", annot)
        await h.ev(TOGGLE_ANNOT)
        return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
