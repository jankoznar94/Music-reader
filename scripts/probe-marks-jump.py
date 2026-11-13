#!/usr/bin/env python3
"""Značky: ruční indexace písmen/čísel + skoky v rozsahu záložky.

Jan, listopad 2026: „Budeme to dělat ručně“ + „Dvě sekce“ (čísla / písmena).
Sonda ověřuje v reálném prohlížeči:
1. tlačítko A na liště otevře panel Značky, ťuknutí do not vybere místo,
   opsaný text se uloží jako index (a v notách se NIKDY nekreslí),
2. panel má dvě sekce — Čísla a Písmena,
3. skok na existující značku (přesune stránku + zvýrazní místo),
4. skok na neexistující → nejbližší (u písmen abecedně),
5. se záložkou hledá jen v její části, bez záložek v celém díle.
"""
import asyncio
import importlib.util
import json
import os

CDP = os.environ.get("NOTY_CDP", "http://127.0.0.1:9226")
APP = os.environ.get("APP_URL") or os.environ.get("NOTY_APP")
# POZOR: `indexedDB.deleteDatabase` v běžícím Chromu nechá pending delete a
# všechna další `indexedDB.open` visí (knihovna „Načítám…“, upload 0/1).
# Proto se DB nemaže — test jede na ČISTÉM profilu (nový --user-data-dir).
RESET_DB = os.environ.get("NOTY_RESET_DB") == "1"


def _load():
    spec = importlib.util.spec_from_file_location(
        "h", os.path.expanduser("~/noty-app/cdp-e2e-harness.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.CDP_HTTP = CDP
    return m


m = _load()
Harness, Check = m.Harness, m.Check

PANEL = """(() => {
  const p = document.querySelector('.marks-panel');
  if (!p) return JSON.stringify({ open: false });
  const secs = [...p.querySelectorAll('.marks-sec')].map(e => e.textContent.trim());
  const items = [...p.querySelectorAll('.marks-item')].map(e => ({
    text: e.querySelector('.marks-text').textContent.trim(),
    page: e.querySelector('.marks-page').textContent.trim(),
  }));
  return JSON.stringify({ open: true, secs, items });
})()"""


async def st(h):
    return json.loads(await h.ev(PANEL))


async def add_mark(h, page_idx, text):
    """Přejdi na stránku, zapni výběr místa a ťukni doprostřed not."""
    await h.ev("(() => { window.__barDev.currentPage.value = " + str(page_idx) + "; return 1; })()")
    await asyncio.sleep(0.6)
    await h.ev("window.__barDev.startMarkPick()")
    await asyncio.sleep(0.3)
    c = json.loads(await h.ev(
        "(() => { const r=document.querySelector('.viewer').getBoundingClientRect();"
        " return JSON.stringify({x: r.x + r.width*0.35, y: r.y + r.height*0.42}); })()"))
    await h.finger_tap(c["x"], c["y"])
    await asyncio.sleep(0.4)
    await h.ev("window.__barDev.mkLabel.value = " + json.dumps(text))
    await h.ev("window.__barDev.saveMark()", await_promise=True)
    await asyncio.sleep(0.3)


async def main():
    ok = Check()
    pdf = m.make_pdf(8)
    async with (Harness(url=APP) if APP else Harness()) as h:
        await h.open()
        await h.open_song(pdf, reset=RESET_DB)
        await asyncio.sleep(1.0)

        await h.ev("document.querySelector('.tb-mark').click()")
        await h.wait_for("!!document.querySelector('.marks-panel')", 8, "panel Značky")
        s0 = await st(h)
        ok("tlačítko A otevře panel Značky", s0["open"] is True, str(s0))

        # Jan: „při vkládání značky se zapíná anotační mód — to bych nedělal.“
        await h.ev("window.__barDev.startMarkPick()")
        await asyncio.sleep(0.4)
        am = await h.ev("(() => window.__barDev.annotMode.value)()")
        ok("výběr místa značky NEZAPNE anotační mód", am is False, str(am))
        ap = await h.ev("(() => !!document.querySelector('.annot-panel'))()")
        ok("anotační panel se u výběru značky neotevře", ap is False, str(ap))
        lay = await h.ev("(() => { const s=document.querySelector('.annot-layer');"
                         " return getComputedStyle(s).pointerEvents; })()")
        ok("vrstva při výběru značky ťuknutí přijme", lay == "auto", str(lay))
        await h.ev("window.__barDev.startMarkPick()")   # přepínač zpět = zrušit
        await asyncio.sleep(0.3)
        am2 = await h.ev("(() => window.__barDev.annotMode.value)()")
        ok("po zrušení výběru zůstává anotace vypnutá", am2 is False, str(am2))

        await add_mark(h, 0, "A")
        await add_mark(h, 2, "C")
        await add_mark(h, 4, "12")
        await add_mark(h, 5, "7")

        s1 = await st(h)
        print("panel:", s1)
        ok("panel má DVĚ sekce (Čísla, Písmena)",
           s1["secs"] == ["Čísla", "Písmena"], str(s1["secs"]))
        nums = [i["text"] for i in s1["items"] if i["text"].isdigit()]
        letters = [i["text"] for i in s1["items"] if not i["text"].isdigit()]
        ok("čísla jdou číselně (7, 12)", nums == ["7", "12"], str(nums))
        ok("písmena abecedně (A, C)", letters == ["A", "C"], str(letters))

        # v notách se značky nekreslí (žádná anotace s mk v pageItems)
        drawn = await h.ev("(() => window.__barDev.pageItems.value.some(i => i && i.mk))()")
        ok("značky se v notách nekreslí", drawn is False, str(drawn))

        # --- skok na existující značku ---
        await h.ev("(() => { window.__barDev.currentPage.value = 0; return 1; })()")
        await asyncio.sleep(0.5)
        await h.ev("(() => { window.__barDev.mkJumpValue.value = 'C'; window.__barDev.goToTypedMark(); return 1; })()")
        await asyncio.sleep(0.8)
        page = await h.ev("window.__barDev.currentPage.value")
        marked = await h.ev("(() => { const m = window.__barDev.barJumpMark.value;"
                            " return m ? m.page : null; })()")
        ok("skok na C přejde na str. 3", page == 2, str(page))
        ok("po skoku se místo zvýrazní", marked == 2, str(marked))

        # zvýraznění samo zmizí
        await asyncio.sleep(4.4)
        gone = await h.ev("(() => window.__barDev.barJumpMark.value ? 1 : 0)()")
        ok("zvýraznění po 4 s zmizí", gone == 0, str(gone))

        # --- neexistující písmeno → nejbližší v abecedě ---
        await h.ev("(() => { window.__barDev.currentPage.value = 0; return 1; })()")
        await asyncio.sleep(0.5)
        await h.ev("(() => { window.__barDev.mkJumpValue.value = 'B'; window.__barDev.goToTypedMark(); return 1; })()")
        await asyncio.sleep(0.7)
        t = json.loads(await h.ev("(() => JSON.stringify(window.__barDev.findMarkTarget('B')))()"))
        print("nejbližší k B:", t)
        ok("B není → nejbližší je A nebo C (písmeno, ne číslo)",
           t and t["text"] in ("A", "C") and t["exact"] is False, str(t))

        t2 = json.loads(await h.ev("(() => JSON.stringify(window.__barDev.findMarkTarget('10')))()"))
        ok("číslo 10 tu není → nejbližší číslo (7 nebo 12)",
           t2 and t2["text"] in ("7", "12") and t2["exact"] is False, str(t2))

        # --- rozsah podle záložky ---
        await h.ev("(() => { window.__barDev.currentPage.value = 0; return 1; })()")
        await asyncio.sleep(0.4)
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Přidat záložku')); b.click(); return 1; })()")
        await h.wait_for("!!document.querySelector('.jump-panel .jp-input')", 8, "panel záložky")
        await h.ev("(() => { const i=document.querySelector('.jump-panel .jp-input');"
                   " i.value='Část 1'; i.dispatchEvent(new Event('input')); return 1; })()")
        await h.ev("document.querySelector('.jump-panel .jp-btn.primary').click()")
        await asyncio.sleep(0.6)
        # druhá záložka na str. 5 → část 1 = str. 1-4 (značky A, C, 12), 7 je v části 2
        await h.ev("(() => { window.__barDev.currentPage.value = 4; return 1; })()")
        await asyncio.sleep(0.5)
        await h.ev("(() => { const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Přidat záložku')); b.click(); return 1; })()")
        await h.wait_for("!!document.querySelector('.jump-panel .jp-input')", 8, "panel záložky 2")
        await h.ev("(() => { const i=document.querySelector('.jump-panel .jp-input');"
                   " i.value='Část 2'; i.dispatchEvent(new Event('input')); return 1; })()")
        await h.ev("document.querySelector('.jump-panel .jp-btn.primary').click()")
        await asyncio.sleep(0.6)
        await h.ev("(() => { window.__barDev.currentPage.value = 0; return 1; })()")
        await asyncio.sleep(0.6)
        # záložky zavřely panel Značky → otevřít znovu
        if not (await st(h)).get("open"):
            await h.ev("document.querySelector('.tb-mark').click()")
            await asyncio.sleep(0.5)
        s2 = await st(h)
        print("v části 1:", s2)
        # část 1 = str. 1–4 → značky A (str. 1) a C (str. 3); „12“ je na str. 5
        # a „7“ na str. 6, takže v této záložce být NESMÍ
        ok("v záložce 1 panel ukazuje jen značky této části (12 i 7 chybí)",
           [i["text"] for i in s2["items"]] == ["A", "C"], str(s2["items"]))
    return ok.report()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
