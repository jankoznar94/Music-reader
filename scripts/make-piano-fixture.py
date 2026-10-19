"""Vytvoří testovací stránku jako klavírní sazbu: 8 systémů, pod poslední
osnovou hluboké basové noty s pomocnými linkami (14 px od spodní hrany)."""
L = []
for s in range(8):
    y = 60 + s * 95
    for i in range(5):
        L.append(f'0.6 w 60 {y + i * 4} m 530 {y + i * 4} l S')
    for i in range(5):
        L.append(f'0.6 w 60 {y + 34 + i * 4} m 530 {y + 34 + i * 4} l S')
for x in (120, 200, 280, 360):
    for k in range(6):
        L.append(f'1 w {x} {14 + k * 8} m {x + 16} {14 + k * 8} l S')
    L.append(f'0 0 0 rg {x - 2} 12 10 6 re f')
stream = '\n'.join(L)
objs = ['<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] '
        '/Contents 4 0 R /Resources << >> >>',
        f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream']
out = '%PDF-1.4\n'
offs = []
for i, o in enumerate(objs, 1):
    offs.append(len(out))
    out += f'{i} 0 obj\n{o}\nendobj\n'
x = len(out)
out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'
for o in offs:
    out += f'{o:010d} 00000 n \n'
out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n'
open('/tmp/noty-piano.pdf', 'w', encoding='latin-1').write(out)
print('ok', len(out))
