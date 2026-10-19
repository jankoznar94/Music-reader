#!/usr/bin/env python3
"""Sonda: hustá stránka (osnovy až do spodku) na telefonu — rámeček musí
zahrnout i nejnižší noty a canvas se musí celý vejít na displej."""
import asyncio
import importlib.util
import os

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "cdp_e2e_harness", os.path.join(_HERE, "cdp-e2e-harness.py"))
_m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_m)
Harness, Check = _m.Harness, _m.Check


def make_pdf(path):
    """12 systémů od y=30 do y=800 (z 842) + nejnižší nota úplně dole."""
    lines = []
    for s in range(12):
        y = 30 + s * 65
        for i in range(5):
            lines.append(f"0.6 w 60 {y + i * 4} m 535 {y + i * 4} l S")
    lines.append("0 0 0 rg 300 8 10 6 re f")   # nejnižší nota u spodní hrany
    stream = "\n".join(lines)
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Contents 4 0 R /Resources << >> >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"]
    out, offsets = "%PDF-1.4\n", []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    with open(path, "w", encoding="latin-1") as fh:
        fh.write(out)
    return path


STATE = r"""
(() => {
  const c = document.querySelector('canvas.pdf-canvas');
  const r = c.getBoundingClientRect();
  const ctx = c.getContext('2d');
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  let iy1 = -1, iy0 = c.height;
  for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++) {
    const i = (y * c.width + x) * 4;
    if (d[i] < 200 || d[i+1] < 200 || d[i+2] < 200) { if (y > iy1) iy1 = y; if (y < iy0) iy0 = y; }
  }
  const dpr = window.devicePixelRatio || 1;
  return {
    top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height),
    winH: innerHeight,
    inkBottom: iy1 < 0 ? null : (c.height - 1 - iy1) / dpr,
    inkTop: iy0 === c.height ? null : iy0 / dpr,
    vb: document.querySelector('.annot-layer').getAttribute('viewBox'),
  };
})()
"""


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=make_pdf('/tmp/noty-dense.pdf'), pages=1)
        await h.cdp('Emulation.setDeviceMetricsOverride',
                    {'width': 390, 'height': 844, 'deviceScaleFactor': 2, 'mobile': True})
        await asyncio.sleep(1.0)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Vycentrovat a preference'));b&&b.click()})()")
        await asyncio.sleep(0.4)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.prefs-panel .prefs-icon')]"
                   ".find(x=>(x.title||'').startsWith('Oříznout'));b&&b.click()})()")
        await asyncio.sleep(2.4)
        s = await h.ev(STATE)
        print('DENSE PHONE:', s)
        chk('canvas se vejde na výšku displeje', s['bottom'] <= s['winH'] + 1,
            f"bottom {s['bottom']} vs {s['winH']}")
        chk('canvas nezačíná nad displejem', s['top'] >= 0, str(s['top']))
        chk('nejnižší nota je uvnitř s okrajem', s['inkBottom'] is not None and 4 <= s['inkBottom'] <= 60,
            str(s['inkBottom']))
        chk('nahoře je taky okraj', s['inkTop'] is not None and s['inkTop'] >= 3, str(s['inkTop']))
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
