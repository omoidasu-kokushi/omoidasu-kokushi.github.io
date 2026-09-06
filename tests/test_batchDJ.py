#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDJ：チュートリアルのスキップ廃止・OKだけに（V2.42・利用者指示）
スキップは押すと勝手にホームへ戻る等が分かりにくく、「わかった」との違いも
伝わらないため廃止。中断はアプリを閉じればチェックポイント復帰が受け止める。
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
ok("スキップボタンが無い", 'id="onb-skip"' not in html)
ok("ボタンはOK", '>OK</button>' in html)
ok("バインディングも撤去", "on($('#onb-skip')" not in js)
ok("既定ラベルがOK", "opts.nextLabel || 'OK'" in js)
ok("「わかった」ラベルは廃止", "nextLabel: 'わかった'" not in js)
ok("チェックポイント復帰は残る", 'id="resume-continue"' in html and "startOnboarding(n)" in js)

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
    r = pg.evaluate("""async () => {
      /* 初回：welcome→開始→最初の吹き出しにOKだけが出る */
      const b = document.getElementById('welcome-start');
      if (b) b.click();
      await new Promise(r2 => setTimeout(r2, 900));
      const bubble = document.getElementById('onb-bubble');
      const next = document.getElementById('onb-next');
      return { layerShown: !document.getElementById('onb-layer').hidden,
               skipGone: !document.getElementById('onb-skip'),
               btns: bubble ? bubble.querySelectorAll('button').length : 0,
               label: next ? next.textContent : null };
    }""")
    ok("吹き出しのボタンは1つだけ", r["btns"] == 1 and r["skipGone"], json.dumps(r, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDJ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
