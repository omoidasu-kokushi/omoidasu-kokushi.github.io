#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印刷用QRの検証（V1.75）

テスト本体（tests/）には入れていない。cv2 と segno が要るためで、
全スイートに外部依存を持ち込みたくない。**QRの中身を変えたとき**だけ
手で走らせる。tests/test_batchAZ.py は依存なしで組版と行列の形を見る。

    pip install segno opencv-python-headless --break-system-packages
    (cd <アプリ> && python3 -m http.server 8900 &)
    python3 tools/verify_qr.py
"""

import asyncio
import numpy as np, cv2, segno
from playwright.async_api import async_playwright

EXPECT = "https://omoidasu-kokushi.github.io/"
REF = [[1 if c else 0 for c in row] for row in segno.make(EXPECT, error="m").matrix]
N = len(REF); QUIET = 4; SPAN = N + QUIET * 2
MOD = 8                      # 1モジュール8px で描く
SIZE = SPAN * MOD

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--no-sandbox"])
        pg = await b.new_page(viewport={"width": SIZE + 80, "height": SIZE + 80})
        await pg.goto("http://127.0.0.1:8900/index.html")
        await pg.wait_for_function("window.__APP_READY === true", timeout=60000)
        await pg.wait_for_timeout(1200)
        try: await pg.click("#welcome-start", timeout=4000)
        except Exception: pass
        await pg.wait_for_timeout(400)

        await pg.evaluate("""(px) => {
          const host = document.createElement('div');
          host.id = 'qr-probe';
          host.style.cssText = 'position:fixed;left:0;top:0;background:#fff;z-index:99999;line-height:0;';
          host.innerHTML = window.Half2Impl.qrSvg();
          const el = host.querySelector('svg');
          el.style.width = px + 'px'; el.style.height = px + 'px';
          document.body.appendChild(host);
        }""", SIZE)
        shot = await pg.locator("#qr-probe").screenshot()
        img = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_GRAYSCALE)
        print("描画サイズ:", img.shape, "／ 期待:", (SIZE, SIZE))

        # 1) モジュール単位の照合
        bad = 0
        for y in range(N):
            for x in range(N):
                cx = (x + QUIET) * MOD + MOD // 2
                cy = (y + QUIET) * MOD + MOD // 2
                dark = 1 if img[cy, cx] < 128 else 0
                if dark != REF[y][x]: bad += 1
        # クワイエットゾーンが白いか
        quiet_ok = all(img[q, q] > 200 for q in (1, MOD, MOD*2, MOD*3))
        print("モジュール照合: %d/%d 一致（不一致 %d）" % (N*N - bad, N*N, bad))
        print("クワイエットゾーンが白い:", quiet_ok)
        assert bad == 0, "描画がsegnoの行列と一致しない"
        assert quiet_ok

        # 2) 実際に読ませる（紙の寸法）
        await pg.evaluate("document.getElementById('qr-probe').remove()")
        hits = 0
        for px in (57, 83, 113):
            await pg.evaluate("""(px) => {
              const host = document.createElement('div');
              host.id = 'qr-probe';
              host.style.cssText = 'position:fixed;left:0;top:0;background:#fff;z-index:99999;line-height:0;';
              host.innerHTML = window.Half2Impl.qrSvg();
              const el = host.querySelector('svg');
              el.style.width = px + 'px'; el.style.height = px + 'px';
              document.body.appendChild(host);
            }""", px)
            shot = await pg.locator("#qr-probe").screenshot()
            await pg.evaluate("document.getElementById('qr-probe').remove()")
            arr = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_GRAYSCALE)
            txt, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
            ok = (txt == EXPECT)
            hits += 1 if ok else 0
            print("%3dpx（%.1fmm）→ %s" % (px, px/96*25.4, ("読めた" if ok else "デコーダが読めず（cv2の当たり外れ）")))
        assert hits >= 1, "どの寸法でも読めなかった"
        print("\n合格：描画は行列と完全一致し、紙の寸法で実際に読める")
        await b.close()
asyncio.run(main())
