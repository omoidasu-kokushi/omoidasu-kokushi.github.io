#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDL：出題量設定の再設計（V2.44・裁定）
ポモドーロを大きく表示（タップでON/OFF・setPomodoroEnabledと連動）、
下に問題数スライダー（5〜120・5刻み）。出題数ロック（§8-3の初回解放制）は廃止。
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
ok("ポモドーロ大表示がある", 'id="qty-pomo"' in html and "25分で区切ります" in html)
ok("スライダーがある（5〜120・5刻み）", 'id="qty-range"' in html and 'min="5" max="120" step="5"' in html)
ok("旧ロックボタンが無い", 'data-qty="120" disabled' not in html and "qty-btn is-locked" not in html)
ok("ロック描画コードも廃止", "random_qty_unlocked;" not in js.split("refreshQtyPomo")[0][-2000:])
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
      const rng = document.getElementById('qty-range');
      const out = { init: rng.value, initLabel: document.getElementById('qty-range-val').textContent };
      /* スライダーを50問へ（新規データでもロックされない） */
      rng.value = '50';
      rng.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 200));
      out.label50 = document.getElementById('qty-range-val').textContent;
      /* ポモドーロOFF→表示が変わりmetaも変わる */
      document.getElementById('qty-pomo').click();
      await new Promise(r2 => setTimeout(r2, 400));
      out.pomoOffText = document.querySelector('#qty-pomo .qty-pomo-big').textContent;
      out.metaOff = (await S.loadMeta()).pomodoro_enabled;
      document.getElementById('qty-pomo').click();
      await new Promise(r2 => setTimeout(r2, 400));
      out.metaOn = (await S.loadMeta()).pomodoro_enabled;
      /* 50問で開始できる */
      const sess = await M.startSession({ mode: 'random', count: 50 });
      out.started = !!(sess && sess.questions && sess.questions.length > 10);
      return out;
    }""")
    ok("初期値10問", r["init"] == "10" and r["initLabel"] == "10問", json.dumps(r, ensure_ascii=False))
    ok("新規データでも50問に動かせる", r["label50"] == "50問", json.dumps(r, ensure_ascii=False))
    ok("ポモドーロON/OFFが大表示から切り替わる",
       "時間では区切りません" in r["pomoOffText"] and r["metaOff"] is False and r["metaOn"] is True,
       json.dumps(r, ensure_ascii=False))
    ok("50問で開始できる（ロック廃止）", r["started"], json.dumps(r, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDL" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
