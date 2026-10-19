#!/usr/bin/env python3
"""Sonda horní lišty: ve čtení je schovaná, tap na STŘED ji ukáže, další tap
schová; noty se přitom roztáhnou do uvolněného pruhu. V anotaci je vždy vidět."""
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

STATE = r"""
(() => {
  const bar = document.querySelector('.top-bar');
  const c = document.querySelector('canvas.pdf-canvas');
  const cr = c ? c.getBoundingClientRect() : null;
  return {
    hidden: bar.classList.contains('hidden'),
    barTop: Math.round(bar.getBoundingClientRect().top),
    barBottom: Math.round(bar.getBoundingClientRect().bottom),
    canvasTop: cr ? Math.round(cr.top) : null,
    canvasH: cr ? Math.round(cr.height) : null,
    pad: getComputedStyle(document.querySelector('.viewer')).getPropertyValue('--topbar-h').trim(),
  };
})()
"""


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=pp.make_pdf('/tmp/noty-topbar.pdf', 3), pages=3)
        await h.cdp('Emulation.setDeviceMetricsOverride',
                    {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        await asyncio.sleep(1.0)
        # výchozí stav: schovaná (nebo ji necháme schovat tapem)
        s = await h.ev(STATE)
        print('START:', s)
        if not s['hidden']:
            await h.finger_tap(195, 420)
            await asyncio.sleep(0.8)
            s = await h.ev(STATE)
        chk('lišta je při čtení schovaná', s['hidden'], str(s))
        chk('lišta je mimo obraz', s['barBottom'] <= 0, f"bottom {s['barBottom']}")
        hidden_canvas_top = s['canvasTop']
        hidden_canvas_h = s['canvasH']

        # tap na střed → lišta se ukáže a noty se zmenší
        await h.finger_tap(195, 420)
        await asyncio.sleep(1.0)
        s = await h.ev(STATE)
        print('PO TAPU:', s)
        chk('tap na střed lištu ukázal', not s['hidden'], str(s))
        chk('lišta je vidět nahoře', s['barBottom'] > 0, f"bottom {s['barBottom']}")
        chk('lišta je OVERLAY: stránka se nepohnula (top)', s['canvasTop'] == hidden_canvas_top,
            f"canvasTop {hidden_canvas_top} -> {s['canvasTop']}")
        chk('lišta je OVERLAY: stránka se nezměnila (výška)', s['canvasH'] == hidden_canvas_h,
            f"{hidden_canvas_h} -> {s['canvasH']}")
        chk('horní okraj not je pod lištou', s['canvasTop'] >= s['barBottom'] - 1,
            f"canvas {s['canvasTop']} vs bar {s['barBottom']}")

        # další tap na střed → schovat
        await h.finger_tap(195, 420)
        await asyncio.sleep(1.0)
        s = await h.ev(STATE)
        chk('další tap lištu schoval', s['hidden'], str(s))
        chk('po schování se stránka taky nehnula', s['canvasTop'] == hidden_canvas_top,
            f"canvasTop {s['canvasTop']} vs {hidden_canvas_top}")

        # tap na okraj nesmí lištu přepnout (listuje)
        before = await h.page_text()
        await h.finger_tap(370, 420)
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        chk('tap na okraj lištu nemění', s['hidden'], str(s))
        chk('tap na okraj listuje', before != await h.page_text(), before)

        # anotace: lišta se musí ukázat
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Anotace'));b&&b.click()})()")
        await asyncio.sleep(0.8)
        s = await h.ev(STATE)
        chk('v anotaci je lišta vidět', not s['hidden'], str(s))
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
