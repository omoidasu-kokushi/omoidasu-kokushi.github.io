#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDF：★の段階に名前を付ける（V2.38）
meta.star_labels（5要素）。★ノートの絞り込みチップと印刷のセレクタに反映。
ガイドに「★は5段階」の項（見本UI付き）。
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
ok("設定に入口がある", 'id="btn-star-labels"' in html)
ok("編集モーダルがある", 'id="modal-star-labels"' in html and 'id="star-labels-save"' in html)
ok("ガイドに★5段階の項", "★は5段階" in js and "★1→★2→★3→★4→★5→解除" in js)

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
    pg.evaluate("() => { const b = document.getElementById('welcome-start'); if (b) b.click(); }")
    pg.wait_for_timeout(400)
    r = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl || window.Half2;
      const out = {};
      /* 編集モーダル：★1に「疑問」・★2に「再学習」を入れて保存 */
      await H.openStarLabels();
      await new Promise(r2 => setTimeout(r2, 200));
      const inputs = [...document.querySelectorAll('#star-label-rows .star-label-input')];
      out.inputs = inputs.length;
      inputs[0].value = '疑問'; inputs[1].value = '再学習';
      await H.saveStarLabels();
      await new Promise(r2 => setTimeout(r2, 200));
      out.saved = await S.getMeta('star_labels', null);
      /* ★ノートのチップへ反映 */
      await H.openStarredNote();
      await new Promise(r2 => setTimeout(r2, 300));
      const chip1 = document.querySelector('#star-lv-filter [data-lvfilter="1"]').textContent;
      const chip3 = document.querySelector('#star-lv-filter [data-lvfilter="3"]').textContent;
      out.chip1 = chip1; out.chip3 = chip3;
      /* 印刷セレクタへ反映 */
      await H.applyStarLabels();
      const opt2 = document.querySelector('#note-starlv option[value="2"]').textContent;
      out.opt2 = opt2;
      return out;
    }""")
    ok("入力欄は5つ", r["inputs"] == 5, json.dumps(r, ensure_ascii=False))
    ok("保存される", r["saved"] == ["疑問", "再学習", "", "", ""], json.dumps(r["saved"], ensure_ascii=False))
    ok("チップに名前が出る（未設定は数字のまま）",
       r["chip1"] == "★1 疑問" and r["chip3"] == "★3", json.dumps(r, ensure_ascii=False))
    ok("印刷セレクタにも出る", r["opt2"] == "★2 再学習 だけ", json.dumps(r, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDF" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
