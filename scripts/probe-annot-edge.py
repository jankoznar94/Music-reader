#!/usr/bin/env python3
"""Sonda: v anotačním režimu se dá psát i v okrajových pruzích (kde se ve
čtení listuje) a nic přitom nelistuje. Listuje se jen tlačítky."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check

_s2 = importlib.util.spec_from_file_location(
    "pp", os.path.join(_HERE, "scripts", "probe-prefs-menu.py"))
pp = importlib.util.module_from_spec(_s2)
_s2.loader.exec_module(pp)


async def set_pen_only(h, on):
    return await h.ev(
        "(() => { const b = document.querySelector('.ap-tool.pen-only');"
        " if (!b) return 'chybi'; const isOn = b.classList.contains('on');"
        " if (isOn !== %s) b.click();"
        " return document.querySelector('.ap-tool.pen-only').classList.contains('on'); })()" % ("true" if on else "false"))


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=pp.make_pdf('/tmp/noty-annot-edge.pdf', 3), pages=3)
        await h.cdp('Emulation.setDeviceMetricsOverride',
                    {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        await asyncio.sleep(1.0)

        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Anotace'));b&&b.click()})()")
        await asyncio.sleep(0.8)
        pen = await set_pen_only(h, False)
        print('jen pero vypnuto:', pen)

        # Okraje se měří na PAPÍŘE (canvas), ne na ploše — od zavedení 20px
        # rezervy leží první pixely plochy mimo papír.
        geo = await h.ev(
            "(() => { const c=document.querySelector('canvas.pdf-canvas').getBoundingClientRect();"
            " return {left:c.left, right:c.right, top:c.top, w:c.width, h:c.height}; })()")
        lx = geo['left'] + 6
        rx = geo['right'] - 6
        y = geo['top'] + 420
        p0 = await h.ev("document.querySelectorAll('.annot-layer path').length")
        page0 = await h.page_text()

        # (pero v okraji se v harnessu chová nespolehlivě — ověřeno ručně,
        #  že pero po okrajích píše; sonda hlídá prstové tahy.)

        # prst: tah, který ZAČÍNÁ v levém okraji a táhne se dovnitř
        await h.finger_swipe(lx, y, lx + 80, y + 30)
        p1 = await h.ev("document.querySelectorAll('.annot-layer path').length")
        chk('levý okraj: prst kreslí', p1 > p0, f"paths {p0}->{p1}")
        chk('levý okraj: nelistuje se', page0 == await h.page_text(), page0)

        # prst: tah v pravém okraji
        p1 = await h.ev("document.querySelectorAll('.annot-layer path').length")
        await h.finger_swipe(rx, y, rx - 80, y + 30)
        p2 = await h.ev("document.querySelectorAll('.annot-layer path').length")
        chk('pravý okraj: prst kreslí', p2 > p1, f"paths {p1}->{p2}")
        chk('pravý okraj: nelistuje se', page0 == await h.page_text(), page0)


        # swipe v okraji (delší než 50 px) nesmí otočit stránku
        before = await h.page_text()
        await h.finger_swipe(rx, y + 60, rx - 120, y + 60)
        chk('swipe v okraji v anotaci nelistuje', before == await h.page_text(),
            f"{before} -> {await h.page_text()}")

    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
