#!/usr/bin/env python3
"""Sonda: šířku rámečku určují OSNOVY, ne text v levém okraji („piano forte“).
Text před osnovou nesmí roztáhnout rámeček a posunout noty doprava."""
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
    """Osnovy 60..535 (z 595), text „piano forte“ 6..50, hluboká nota dole."""
    lines = []
    for s in range(11):
        y = 120 + s * 58
        for i in range(5):
            lines.append(f"0.6 w 60 {y + i * 4} m 535 {y + i * 4} l S")
    # text před osnovou (dynamika) — nesmí určovat šířku rámečku
    lines.append("0 0 0 rg 6 300 44 12 re f")
    # hluboká nota u spodního okraje
    lines.append("300 6 8 6 re f")
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


async def main():
    chk = Check()
    async with Harness() as h:
        await h.open()
        await h.open_song(pdf=make_pdf('/tmp/noty-horizontal.pdf'), pages=1)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.tb-btn')]"
                   ".find(x=>(x.title||'').startsWith('Vycentrovat a preference'));b&&b.click()})()")
        await asyncio.sleep(0.4)
        await h.ev("(()=>{const b=[...document.querySelectorAll('.prefs-panel .prefs-icon')]"
                   ".find(x=>(x.title||'').startsWith('Oříznout'));b&&b.click()})()")
        await asyncio.sleep(2.4)
        s = await h.ev(r"""
        (() => {
          const svg = document.querySelector('.annot-layer');
          const [x, y, w, h] = svg.getAttribute('viewBox').split(' ').map(Number);
          const c = document.querySelector('canvas.pdf-canvas');
          const ctx = c.getContext('2d');
          const W = c.width, H = c.height, d = ctx.getImageData(0, 0, W, H).data;
          let ix0 = W, ix1 = -1, iy1 = -1;
          for (let yy = 0; yy < H; yy++) for (let xx = 0; xx < W; xx++) {
            const i = (yy * W + xx) * 4;
            if (d[i] < 200 || d[i+1] < 200 || d[i+2] < 200) {
              if (xx < ix0) ix0 = xx; if (xx > ix1) ix1 = xx; if (yy > iy1) iy1 = yy;
            }
          }
          const dpr = window.devicePixelRatio || 1;
          return {vb: {x, y, w, h}, W: W / dpr, H: H / dpr,
                  inkLeft: ix0 / dpr, inkRight: (W - 1 - ix1) / dpr,
                  inkBottom: (H - 1 - iy1) / dpr};
        })()
        """)
        print('VÝŘEZ:', s)
        vb = s['vb']
        # Referenční soustava: plná šířka stránky = 788 px (při okně 800).
        # Osnovy začínají na 60/595 → ~79 px; text „piano forte“ na 6/595 → ~8 px.
        chk('levý okraj rámečku je u osnov, ne u textu',
            60 <= vb['x'] <= 95, f"vb.x = {vb['x']:.1f} (text by byl ~8)")
        chk('pravý okraj rámečku je za koncem osnov (535/595)',
            690 <= vb['x'] + vb['w'] <= 740, f"pravý = {vb['x'] + vb['w']:.1f}")
        chk('řádek s textem není v canvasu (text se neořezává uprostřed)',
            s['inkLeft'] >= 2, f"levý okraj inkoustu {s['inkLeft']:.1f} px")
        chk('hluboká nota dole není uříznutá', 4 <= s['inkBottom'] <= 45,
            f"{s['inkBottom']:.1f} px")
    return chk.report()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
