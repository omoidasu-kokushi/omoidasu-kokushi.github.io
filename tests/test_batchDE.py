#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDE：間違いノート印刷の★段階絞り込み（V2.37）
「★2だけ印刷」ができる。難しいだけのときは段階は効かず、
段階指定でも「難しい」由来の問題は混ざらない（★由来のみ絞る）。
"""
import io, os, sys, glob, json
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
ok("印刷設定に段階セレクタ", 'id="note-starlv"' in html)

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
      const S = window.Storage, H = window.Half2Impl || window.Half2;
      const qs = await S.getAllQuestions();
      const tap = async (fn, id, n2) => { for (let i = 0; i < n2; i++) { await fn.call(S, id); } };
      await tap(S.toggleQuestionStar, qs[0].q_id, 2);   /* ★2 */
      await tap(S.toggleQuestionStar, qs[1].q_id, 1);   /* ★1 */
      const c0 = await H.collectNoteItems('star', 0);
      const c2 = await H.collectNoteItems('star', 2);
      const c5 = await H.collectNoteItems('star', 5);
      const h2 = await H.collectNoteItems('hard', 2);
      return { all: c0.length, lv2: c2.length,
               lv2id: c2.length === 1 ? c2[0].question.q_id === qs[0].q_id : false,
               lv5: c5.length, hardIgnores: h2.length };
    }""")
    ok("全段階で2件", r["all"] == 2, json.dumps(r))
    ok("★2だけに絞れる", r["lv2"] == 1 and r["lv2id"], json.dumps(r))
    ok("該当なしは0件", r["lv5"] == 0, json.dumps(r))
    ok("難しいだけのときは段階は無関係（★を混ぜない）", r["hardIgnores"] == 0, json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDE" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
