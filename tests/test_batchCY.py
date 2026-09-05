#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCY：保存領域persistは自動要求（V2.30・利用者裁定）
［消えないようにする］ボタンを撤去し、保存領域欄の表示時に未許可なら
自動で要求（セッション1回）。V1.60の「起動直後は要求しない」は維持。
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
ok("ボタンが無い", 'id="btn-persist"' not in html)
ok("表示時の自動要求がある", "_persistAsked" in js)
ok("1回だけの歯止めがある", "!st._persistAsked" in js)
ok("チュートリアル完了時の要求は残る", "S.requestPersist().catch(noop)" in js)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(800)
    r = pg.evaluate("""async () => {
      let calls = 0;
      const orig = window.Storage.requestPersist;
      window.Storage.requestPersist = () => { calls++; return orig.call(window.Storage); };
      await window.Half2.openSettings();
      await new Promise(r2 => setTimeout(r2, 600));
      await window.Half2.refreshStorage();       /* 2回目の表示 */
      await new Promise(r2 => setTimeout(r2, 300));
      window.Storage.requestPersist = orig;
      const warn = document.getElementById('store-warn');
      return { calls, warnShown: !!(warn && !warn.hidden) };
    }""")
    ok("表示時に自動要求され、2回目は要求しない", r["calls"] == 1, json.dumps(r))
    ok("状態の言葉は出る", r["warnShown"], json.dumps(r))
    ok("実行時エラーなし", not errs, str(errs[:2]))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCY" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
