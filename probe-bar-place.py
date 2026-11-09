#!/usr/bin/env python3
"""E2E: umístění čísla taktu obdélníkem — výška a ořez.

Jan (Nov 2026): „Takty se teď ručním číslováním umisťují příliš vysoko nad
osnovu“ a „někdy se číslo ořízne, místo 177 je vidět jen 77“.

Ověřuje:
  * horní okraj čísla = horní hrana obdélníku (číslo sedí V rohu, ne nad ním)
  * s velkým obdélníkem (začíná kus nad systémem) číslo nevisí vysoko
  * s rámem (ořezem) se číslo nepoloží mimo viditelnou plochu → neořízne se
  * číslo 177 se vykreslí celé (levý okraj textu == x, žádné uříznutí)
"""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("h", os.path.join(_HERE, "cdp-e2e-harness.py"))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def center(js):
    return ("(() => { const b = %s; if (!b) return null; const r = b.getBoundingClientRect();"
            " return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2)}; })()" % js)


BAR_TOOL = center("[...document.querySelectorAll('.ap-tool')].find(e => (e.title||'').startsWith('Čísla taktů'))")


async def texts(h):
    return await h.ev("""[...document.querySelectorAll('.annot-layer text')]
        .filter(t => +t.getAttribute('x') !== 0 || +t.getAttribute('y') !== 0)
        .map(t => { const r = t.getBoundingClientRect();
          return {txt: t.textContent, x: +t.getAttribute('x'), y: +t.getAttribute('y'),
                  left: Math.round(r.left), top: Math.round(r.top),
                  right: Math.round(r.right), bottom: Math.round(r.bottom)}; })""")


async def drag(h, x0, y0, x1, y1):
    await h.pen_down(x0, y0)
    await h.pen_move((x0 + x1) / 2, (y0 + y1) / 2)
    await h.pen_move(x1, y1)
    await h.pen_up(x1, y1)
    await asyncio.sleep(0.45)


async def main():
    fails = []
    async with m.Harness() as h:
        await h.cdp("Storage.clearDataForOrigin", {"origin": "http://localhost:5173", "storageTypes": "all"})
        await h.open()
        await h.ev("(() => { localStorage.clear(); navigator.serviceWorker && navigator.serviceWorker"
                   ".getRegistrations().then(rs => rs.forEach(r => r.unregister())); return true; })()")
        await h.open_song(pages=3)
        await h.annot_toggle()
        await asyncio.sleep(0.6)
        t = await h.ev(BAR_TOOL)
        await h.pen_tap(t["x"], t["y"])
        await asyncio.sleep(0.5)

        # 1) obdélník 880..960 — číslo musí sedět u horní hrany (ne nad ní)
        await drag(h, 470, 880, 700, 960)
        a = await texts(h)
        print("po obdélníku:", a)
        if not a:
            fails.append("číslo se nevložilo")
        else:
            n = a[0]
            # horní hrana obdélníku na obrazovce = 880; inkoust čísla má začínat tam
            if not (870 <= n["top"] <= 884):
                fails.append("číslo nesedí u horní hrany obdélníku (top=%s, čekáno ~880)" % n["top"])
            # číslo se posouvá o ~0,35×velikost doprava (zarovno s osnovou)
            if not (470 < n["left"] <= 486):
                fails.append("číslo není zarovno s levou hranou obdélníku (left=%s)" % n["left"])

        # 2) velký obdélník začínající vysoko nad systémem → i tak sedí u jeho hrany
        await drag(h, 470, 800, 700, 1000)
        a = await texts(h)
        print("po vysokém obdélníku:", a[-1] if a else None)
        if len(a) < 2 or not (790 <= a[-1]["top"] <= 812):
            fails.append("u vysokého obdélníku číslo nezačíná u jeho horní hrany")

        # 3) rám (ořez) + číslo u levého okraje → nesmí se oříznout
        # 3) číslo u ÚPLNÉHO levého okraje vrstvy (případ, kdy se dřív ořezávalo)
        box = await h.ev("""(() => { const s = document.querySelector('.annot-layer');
            const r = s.getBoundingClientRect();
            const vb = (s.getAttribute('viewBox') || '0 0 0 0').split(/\s+/).map(Number);
            return {l: Math.round(r.left), t: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
                    vb: vb}; })()""")
        print("vrstva:", box)
        if True:
            # vlož 177 (Další přepiš na 177) a táhni od levého okraje viditelné plochy
            if not await h.ev("!!document.querySelector('.ap-tool')"):
                await h.annot_toggle()
                await asyncio.sleep(0.5)
            if not await h.ev("!!document.querySelector('.ap-bar-next')"):
                t = await h.ev(BAR_TOOL)
                if t:
                    await h.pen_tap(t["x"], t["y"])
                    await asyncio.sleep(0.4)
            await h.set_value(".ap-bar-next:not(.ap-bar-step)", "177")
            await h.ev("document.querySelector('.ap-bar-next:not(.ap-bar-step)').dispatchEvent(new Event('change',{bubbles:true}))")
            await asyncio.sleep(0.3)
            await drag(h, box["l"] + 2, box["t"] + 700, box["l"] + 180, box["t"] + 760)
            a = await texts(h)
            n = a[-1] if a else None
            print("číslo 177:", n)
            if not n or n["txt"] != "177":
                fails.append("číslo 177 se nevložilo (%s)" % (n and n["txt"]))
            else:
                if n["left"] < box["l"] - 1:
                    fails.append("číslo 177 je oříznuté — začíná před vrstvou (left=%s, vrstva=%s)" % (n["left"], box["l"]))
                if n["x"] < box["vb"][0]:
                    fails.append("číslo 177 má x=%s mimo viewBox (x0=%s)" % (n["x"], box["vb"][0]))
                if n["right"] > box["l"] + box["w"]:
                    fails.append("číslo 177 přetéká vpravo mimo vrstvu")

        print("VÝSLEDEK:", "OK" if not fails else "PROBLÉM: " + "; ".join(fails))


asyncio.run(main())
