# -*- coding: utf-8 -*-
"""test_wording_together.py — 比較表の画面の呼び名を「一緒に覚えたい！」に統一（V3.18）

【何が起きていたか（利用者裁定 2026-09-12）】
  「一緒に覚えるだとどっかの看護こくしアプリのパクりになるから一緒に覚えたい！にする」

  もともと画面の呼び名は「比較表」で、設定の1か所だけ「一緒に覚える（表）」と書いてあった。
  ①「一緒に覚える」は他アプリの呼び名なので使わない
  ②中身は表だけではない（「その他にこれとこれがある」の羅列も入れる方針になった）ので、
    「比較表」という名前がもう合っていない

【ここで固定すること】
  ・画面に出る呼び名は **「一緒に覚えたい！」**（詳しい解説の見出し・復習のボタン・設定・検索の種別・ツアー・取り込みの案内）
  ・画面から「比較表」「一緒に覚える」は消す（コードのコメントと作問仕様書の中は別。あちらはデータの説明）
  ・**データの項目名 `comparison_table` は変えない**。作問側との契約なので、名前を変えると両側がズレる（§24）
"""
import os, sys, io, re
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
ih = rd("index.html")
p1, p2 = rd("20260815_main_part1_V1.38.js"), rd("20260815_main_part2_V1.45.js")

ok("詳しい解説の見出し", '<h4 class="detail-h">一緒に覚えたい！</h4>' in ih)
ok("復習のボタン", '<details class="xr-table"><summary>一緒に覚えたい！</summary>' in p2)
ok("設定（自分で登録した画像の位置）", '一緒に覚えたい！の直後<small>表や羅列のすぐ下</small>' in ih)
ok("検索結果の種別ラベル", "table: '一緒に覚えたい！'" in p2)
ok("オンボーディングの吹き出し", "全体解説・一緒に覚えたい！・図解はここにまとめてあります。" in p2)
ok("取り込みの案内（index.html と設定の中の両方）",
   "解説は一緒に覚えたい！も図解も、すべて11列目に入れます。" in ih
   and "解説は一緒に覚えたい！も図解も<b>すべて11列目</b>です。" in p2)

# 画面に出る文字列だけを見る（HTMLコメントと JS のコメント行は外す）
ih_body = re.sub(r"<!--.*?-->", "", ih, flags=re.S)
def strip_js_comments(s):
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", ln) for ln in s.split("\n"))
p2_code = strip_js_comments(p2)
p1_code = strip_js_comments(p1)
ok("画面の文言に「比較表」が残っていない", "比較表" not in ih_body and "比較表" not in p2_code and "比較表" not in p1_code,
   [x for x in ["index.html"] if "比較表" in ih_body] + [x for x in ["part2"] if "比較表" in p2_code])
ok("他アプリの呼び名「一緒に覚える」を画面で使っていない",
   "一緒に覚える" not in ih_body and "一緒に覚える" not in p2_code and "一緒に覚える" not in p1_code)
ok("データの項目名は変えていない（comparison_table のまま・作問側との契約）",
   "comparison_table" in rd("storage.js") and "comparison_table" in p1 and "q.comparison_table" in p2)
ok("作問仕様書はデータの説明なので「比較表」のままでよい（画面の呼び名とは別）",
   "比較表" in rd("作問仕様書_V1.00.md"))

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(400)
    r = pg.evaluate("""() => {
      const out = {};
      const h = document.querySelector('#sec-table .detail-h');
      out.head = h ? h.textContent.trim() : null;
      const rad = document.querySelector('input[name="userimgpos"][value="after-table"]');
      out.radio = rad ? rad.closest('label').textContent.replace(/\\s+/g, '') : null;
      /* 画面のどこにも「比較表」「一緒に覚える（！なし）」が出ていない */
      const txt = document.body.textContent || '';
      out.noOld = txt.indexOf('比較表') < 0;
      out.noCopy = !/一緒に覚える(?!たい)/.test(txt);
      out.hasNew = txt.indexOf('一緒に覚えたい！') >= 0;
      return out; }""")
    ok("画面の見出しが「一緒に覚えたい！」になっている", r["head"] == "一緒に覚えたい！", r["head"])
    radio = r["radio"] or ""
    ok("設定のラジオも新しい呼び名", "一緒に覚えたい！の直後" in radio, radio)
    ok("画面のどこにも「比較表」が出ていない", r["noOld"])
    ok("画面のどこにも「一緒に覚える」（！なし）が出ていない", r["noCopy"])
    ok("新しい呼び名が画面に出ている", r["hasNew"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + str(detail)))
print("\n%d/%d  wording_together" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
