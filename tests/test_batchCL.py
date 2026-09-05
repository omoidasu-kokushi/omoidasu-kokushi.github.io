#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCL：模試中は正誤ポップアップを出さない／根拠チェックはカード外で色はマークだけ（V2.15）

何が起きていたか（利用者の実機指摘）：
1) 模試中も1問ごとに「○正解／×不正解（正解は…）」ポップアップが出て、
   一括採点（§11）の緊張感を壊していた。さらに模試の進行では cur の指す問題と
   ポップアップの正解文が食い違う取り違えが確認された。
2) 根拠チェック（消去法）を付けると選択肢カード自体に緑の縁と色が付き、
   「選択した」と見間違えた。
直し方：模試中は showVerdictPopup を出さない。カード側の色は廃止し、
色が付くのはチェックマーク自身だけ。模試ではチェックをカード右外側（欄外）へ。
"""
import io, json, os, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


import glob as _g
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
js = read(p1)
css = read("styles.css")
seg = js.split("function showVerdictPopup(")[1][:600]
ok("ポップアップは模試中に早期returnする", "isExamMode()" in seg)
ok("取り違えの経緯がコードに書いてある", "食い違う" in seg)
ok("カード側の色付けが消えている", ".choice-card.is-eliminated{ }" in css)
ok("旧・縁色ルールが残っていない", "is-eliminated{ border-left" not in css)
ok("模試では欄外配置のスタイルがある", '#choice-list.is-exam .choice-mark[data-kind="ground"]' in css)
ok("描画側が is-exam を付け外しする", "toggleClass($('#choice-list'), 'is-exam', exam)" in js)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1000)

    r = pg.evaluate("""() => {
      const M = window.Main;
      const cur = { atoms: [{ is_correct: true, original_num: 1, text: 'ダミー' }], answeredRight: false };
      const pop = document.getElementById('verdict-pop');
      const before = M.state.session.mode;
      M.state.session.mode = 'exam';
      M.showVerdictPopup(cur);
      const examHidden = pop.hidden;
      M.state.session.mode = 'random';
      M.showVerdictPopup(cur);
      const normalShown = !pop.hidden;
      M.hideVerdictPopup();
      M.state.session.mode = before;
      return { examHidden, normalShown };
    }""")
    ok("模試モードでは出ない", r["examHidden"] is True, json.dumps(r))
    ok("通常モードでは従来どおり出る", r["normalShown"] is True, json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCL" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
