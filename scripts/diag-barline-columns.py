#!/usr/bin/env python3
"""Diagnostika detekce čar: vypíše PROFIL sloupců pro každou osnovu pásu.

Proč: „appka bere jako čáru i nožičky not“ se nedá opravit od oka — je potřeba
vidět, jakou výšku (souvislý svislý tah) má který sloupec a co je v něm.
Skript zopakuje kroky 1–2 z barLines.js a vypíše:
  * nalezené linky osnov (a jak jsou seskupené do systému),
  * pro osnovu u klepnutí sloupce s pokrytím >= 60 % výšky osnovy včetně
    nejdelšího souvislého tahu a přesahu nad/pod osnovu (to rozhoduje, jestli
    je to taktová čára, nebo nožička),
  * levý okraj osnovy (kde začíná linka) — tam je úvodní taktová čára.

Předpoklad: vite na 5173, Chrome na 9222.

Použití:
  python3 scripts/diag-barline-columns.py --img scripts/fixtures/ave-scan.png \
      --ppt 3 --band 260 --ypt 330
"""
import argparse
import asyncio
import base64
import json
import os
import urllib.request

import websockets

JS = """(async () => {
  const img = new Image();
  img.src = %(url)s;
  await img.decode();
  const ppt = %(ppt)s, band = %(band)s, ypt = %(ypt)s;
  let sy = 0, sh = img.height;
  if (band > 0) {
    sy = Math.max(0, Math.min((ypt - band / 2) * ppt, img.height - band * ppt));
    sh = Math.min(img.height - sy, band * ppt);
  }
  const cv = document.createElement('canvas');
  cv.width = img.width; cv.height = sh;
  cv.getContext('2d', { willReadFrequently: true }).drawImage(img, 0, sy, img.width, sh, 0, 0, img.width, sh);
  const w = cv.width, h = cv.height;
  const yy = ypt - sy / ppt;
  const d = cv.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, w, h).data;

  // --- stejné kroky jako barLines.js -------------------------------------
  function otsu(hist, total) {
    let sum = 0;
    for (let i = 0; i < 256; i++) sum += i * hist[i];
    let sumB = 0, wB = 0, best = -1, thr = 127;
    for (let t = 0; t < 256; t++) {
      wB += hist[t]; if (!wB) continue;
      const wF = total - wB; if (!wF) break;
      sumB += t * hist[t];
      const mB = sumB / wB, mF = (sum - sumB) / wF;
      const v = wB * wF * (mB - mF) * (mB - mF);
      if (v > best) { best = v; thr = t; }
    }
    return thr;
  }
  function longestRun(mask, off, w) {
    let best = 0, run = 0;
    for (let x = 0; x < w; x++) { if (mask[off + x]) { run++; if (run > best) best = run; } else run = 0; }
    return best;
  }
  const hist = new Uint32Array(256), gray = new Uint8Array(w * h);
  for (let i = 0, p = 0; p < w * h; p++, i += 4) {
    const v = (d[i] * 299 + d[i + 1] * 587 + d[i + 2] * 114) / 1000;
    gray[p] = v; hist[v | 0]++;
  }
  const thr = Math.min(235, otsu(hist, w * h) + 35);
  const mask = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) mask[p] = gray[p] < thr ? 1 : 0;
  const rows = [];
  { let runStart = -1;
    for (let y = 0; y <= h; y++) {
      let on = false;
      if (y < h) {
        const off = y * w; let ink = 0;
        for (let x = 0; x < w; x++) ink += mask[off + x];
        on = ink / w >= 0.30 || longestRun(mask, off, w) / w >= 0.45;
      }
      if (on && runStart < 0) runStart = y;
      if (!on && runStart >= 0) { rows.push(Math.round((runStart + y - 1) / 2)); runStart = -1; }
    }
  }
  const minSep = Math.max(2, Math.round(ppt * 0.8)), cs = [];
  for (const c of rows) {
    if (cs.length && c - cs[cs.length - 1] <= minSep) cs[cs.length - 1] = Math.round((cs[cs.length - 1] + c) / 2);
    else cs.push(c);
  }
  const gapMax = Math.max(12, Math.round(ppt * 8)), staves = [];
  let cur = [];
  for (const c of cs) {
    if (cur.length && c - cur[cur.length - 1] < gapMax) cur.push(c);
    else { if (cur.length) staves.push(cur); cur = [c]; }
  }
  if (cur.length) staves.push(cur);
  const real = staves.filter(s => s.length >= 4).map(s => ({ y0: s[0], y1: s[s.length - 1], n: s.length }));

  // osnova u klepnutí (bod v px)
  const ypx = yy * ppt;
  const pick = real.reduce((a, b) => {
    const dA = (a.y0 <= ypx && ypx <= a.y1) ? 0 : Math.min(Math.abs(ypx - a.y0), Math.abs(ypx - a.y1));
    const dB = (b.y0 <= ypx && ypx <= b.y1) ? 0 : Math.min(Math.abs(ypx - b.y0), Math.abs(ypx - b.y1));
    return dA <= dB ? a : b;
  });

  // profil sloupců v rozšířeném okně (1 mezera nad a pod)
  const space = (pick.y1 - pick.y0) / 4;
  const winTop = Math.max(0, Math.round(pick.y0 - space)), winBot = Math.min(h - 1, Math.round(pick.y1 + space));
  const prof = [];
  for (let x = 0; x < w; x++) {
    let inStaff = 0, run = 0, best = 0, bestStart = -1, cs2 = -1, overTop = 0, overBot = 0;
    for (let y = winTop; y <= winBot; y++) {
      const ink = mask[y * w + x];
      if (y >= pick.y0 && y <= pick.y1) inStaff += ink;
      if (ink) { if (cs2 < 0) cs2 = y; run = y - cs2 + 1; if (run > best) { best = run; bestStart = cs2; } }
      else cs2 = -1;
    }
    const staffH = pick.y1 - pick.y0;
    const cov = inStaff / staffH;
    if (cov >= 0.6) prof.push({ x: +(x / ppt).toFixed(1), cov: +(cov * 100).toFixed(0),
                                runPx: best, runPt: +(best / ppt).toFixed(1),
                                overTopPt: +((pick.y0 - bestStart) / ppt).toFixed(1),
                                overBotPt: +((bestStart + best - pick.y1) / ppt).toFixed(1) });
  }
  // levý okraj osnovy: první x, kde má horní linka osnovy inkoust
  let staffLeft = -1;
  for (let x = 0; x < w; x++) { if (mask[Math.round(pick.y0) * w + x]) { staffLeft = x / ppt; break; } }
  return { thr, space: +(space / ppt).toFixed(2), ypx, staffs: real.map(s => ({ y0: +(s.y0 / ppt).toFixed(1), y1: +(s.y1 / ppt).toFixed(1), lines: s.n })), pick: { y0: +(pick.y0 / ppt).toFixed(1), y1: +(pick.y1 / ppt).toFixed(1) }, staffLeft: +staffLeft.toFixed(1), prof };
})()"""


async def ev(ws, i, expr):
    await ws.send(json.dumps({"id": i, "method": "Runtime.evaluate",
                              "params": {"expression": expr, "awaitPromise": True,
                                         "returnByValue": True}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == i:
            return msg


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default="scripts/fixtures/ave-scan.png")
    ap.add_argument("--ppt", type=float, default=3.0)
    ap.add_argument("--band", type=float, default=260)
    ap.add_argument("--ypt", type=float, default=330)
    a = ap.parse_args()
    with open(a.img, "rb") as fh:
        url = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list"))
    page = [t for t in tabs if t["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=64 << 20) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.navigate",
                                  "params": {"url": "http://127.0.0.1:5173/"}}))
        await asyncio.sleep(2.5)
        r = await ev(ws, 10, JS % {"url": json.dumps(url), "ppt": a.ppt,
                                  "band": a.band, "ypt": a.ypt})
        if r.get("result", {}).get("exceptionDetails"):
            print(json.dumps(r["result"]["exceptionDetails"])[:1500])
            return
        o = r["result"]["result"]["value"]
    print("thr", o["thr"], "| mezera", o["space"], "pt | klik px", round(o["ypx"], 1))
    print("osnovy:", o["staffs"])
    print("vybraná:", o["pick"], "| levý okraj osnovy x =", o["staffLeft"], "pt")
    print(f"\n{'x pt':>7} {'krytí':>6} {'tah pt':>7} {'nad':>6} {'pod':>6}")
    for p in o["prof"]:
        print(f"{p['x']:>7} {p['cov']:>5}% {p['runPt']:>7} {p['overTopPt']:>6} {p['overBotPt']:>6}")


asyncio.run(main())
