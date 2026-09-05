#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCX：「自分のGoogle Cloudで動かす」節を撤去（V2.29・利用者裁定）
UIのみ撤去。保存済みクライアントIDの読み出し（drive_client_id）は残るため、
過去に設定した人の同期は壊れない。関連JSは全てnull安全を確認済み。
"""
import io, os, sys
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
ok("上級者向け節が無い", 'id="drive-advanced"' not in html and
   '<summary>自分のGoogle Cloudで動かす' not in html)   # 撤去経緯のコメント内の言及は許す
ok("撤去の経緯コメントが残る", 'V1.32の上級者向け節）は\n               撤去' in html or '上級者向け節' in html)
ok("ドライブ同期本体の節は無事", 'ドライブ同期' in html and 'drive-privacy' in html)
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
      await window.Half2.openSettings();
      await new Promise(r2 => setTimeout(r2, 400));
      return { adv: !!document.getElementById('drive-advanced') };
    }""")
    ok("設定画面を開いても節が無い", r["adv"] is False)
    ok("起動・設定表示でエラーなし", not errs, str(errs[:2]))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCX" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
