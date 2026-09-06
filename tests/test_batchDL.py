#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDL：出題量設定（V2.44 → V2.69で作り直し）

V2.44 では「ポモドーロの大表示（ON/OFF）」＋「問題数スライダー」を並べていた。
V2.69（利用者裁定）で **区切り方は二択** になり、ポモドーロのトグルは無くなった。
理由：両方が同時に生きていて、実際に終了条件だったのは問題数だけ＝
「25分間出題」と書いてあるのに25分では終わらなかった。

観点は消さずに置き換える。
  ・ポモドーロのON/OFF   → 二択のセグメント（test_qty_mode.py が本体）
  ・問題数スライダーの段 → そのまま（ここで見る）
  ・旧ロックの不在       → そのまま
  ・50問で開始できる     → そのまま
"""
import io, os, sys, glob, json
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
p2 = sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1]
js = io.open(p2, encoding="utf-8").read()
ok("ポモドーロのON/OFFトグルは無くなった（V2.69）", 'id="qty-pomo"' not in html)
ok("代わりに区切り方の二択がある（V2.69）",
   'id="qty-mode"' in html and 'data-qmode="time"' in html and 'data-qmode="count"' in html)
ok("ポモドーロの推奨は残っている（25分）", 'id="qty-pomo-reco"' in html and "ポモドーロ" in html)
ok("問題数スライダーは粗い7段＋目盛り常時表示（V2.46）",
   'id="qty-range"' in html and 'min="0" max="6"' in html and ">120<" in html)
ok("時間スライダーもある（V2.69）", 'id="time-range"' in html and ">60<" in html)
ok("旧ロックボタンが無い", 'data-qty="120" disabled' not in html and "qty-btn is-locked" not in html)
ok("ロック描画コードも廃止", "random_qty_unlocked;" not in js)
ok("出どころの説明がある", "まだ解いていない問題から、弱点と頻出の優先順で出します" in html)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1200)
    pg.evaluate("async () => { await window.Storage.setMetaBulk({ onboarding_done: true }); }")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1000)
    pg.evaluate("() => window.Main.closeModals()")
    r = pg.evaluate("""async () => {
      const H = window.Half2, M = window.Main, S = window.Storage;
      await H.openRandomSelect();
      await new Promise(r2 => setTimeout(r2, 400));
      /* V2.69：問題数のスライダーは「問題数で区切る」を選んでから */
      document.querySelector('#qty-mode [data-qmode="count"]').click();
      await new Promise(r2 => setTimeout(r2, 200));
      const rng = document.getElementById('qty-range');
      const out = { init: rng.value, initLabel: document.getElementById('qty-range-val').textContent };
      rng.value = '4';
      rng.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 200));
      out.label50 = document.getElementById('qty-range-val').textContent;
      out.metaCount = (await S.loadMeta()).random_limit;
      /* 時間へ戻すと保存も変わる */
      document.querySelector('#qty-mode [data-qmode="time"]').click();
      await new Promise(r2 => setTimeout(r2, 300));
      out.metaTime = (await S.loadMeta()).random_limit;
      out.recoShown = !document.getElementById('qty-pomo-reco').hidden;
      /* 50問で開始できる */
      const sess = await M.startSession({ mode: 'random', count: 50 });
      out.started = !!(sess && sess.questions && sess.questions.length > 10);
      return out;
    }""")
    ok("初期値10問（=1段目）", r["init"] == "1" and r["initLabel"] == "10問", json.dumps(r, ensure_ascii=False))
    ok("新規データでも50問に動かせる", r["label50"] == "50問", json.dumps(r, ensure_ascii=False))
    ok("二択の選択が保存される（V2.69）",
       r["metaCount"] == "count" and r["metaTime"] == "time", json.dumps(r, ensure_ascii=False))
    ok("時間に戻すと25分でポモドーロの案内が出る", r["recoShown"], json.dumps(r, ensure_ascii=False))
    ok("50問で開始できる（ロック廃止）", r["started"], json.dumps(r, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDL" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
