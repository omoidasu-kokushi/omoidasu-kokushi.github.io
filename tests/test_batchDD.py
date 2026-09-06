#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDD：★ノートの段階フィルタ（V2.36）
「★2だけ」のように段階で絞れる。問題★がその段階、または肢★のどれかが
その段階なら表示。種別フィルタ（問題/選択肢）と併用できる。
"""
import io, os, sys, glob, json
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
ok("段階フィルタのUIがある", 'id="star-lv-filter"' in html and 'data-lvfilter="5"' in html)

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
      const S = window.Storage, H = window.Half2;
      const qs = await S.getAllQuestions();
      /* q0=★2（問題）、q1=肢に★3、q2=★1（問題） */
      const tap = async (fn, id, n2) => { for (let i = 0; i < n2; i++) { await fn.call(S, id); } };
      await tap(S.toggleQuestionStar, qs[0].q_id, 2);
      const full = (await S.getQuestionsFull([qs[1].q_id]))[0];
      await tap(S.toggleAtomStar, full.atoms[0].atom_id, 3);
      await tap(S.toggleQuestionStar, qs[2].q_id, 1);
      await H.openStarredNote();
      await new Promise(r2 => setTimeout(r2, 300));
      const count = () => document.querySelectorAll('#star-list .star-item').length;
      const out = { all: count() };
      document.querySelector('#star-lv-filter [data-lvfilter="2"]').click();
      await new Promise(r2 => setTimeout(r2, 250));
      out.lv2 = count();
      out.lv2id = out.lv2 === 1 && document.querySelector('#star-list .star-item').dataset.qid === qs[0].q_id;
      document.querySelector('#star-lv-filter [data-lvfilter="3"]').click();
      await new Promise(r2 => setTimeout(r2, 250));
      out.lv3 = count();
      out.lv3id = out.lv3 === 1 && document.querySelector('#star-list .star-item').dataset.qid === qs[1].q_id;
      document.querySelector('#star-lv-filter [data-lvfilter="0"]').click();
      await new Promise(r2 => setTimeout(r2, 250));
      out.back = count();
      /* 種別と併用：問題★のみ×★3 → 0件（★3は肢） */
      document.querySelector('[data-sfilter="question"]').click();
      await new Promise(r2 => setTimeout(r2, 200));
      document.querySelector('#star-lv-filter [data-lvfilter="3"]').click();
      await new Promise(r2 => setTimeout(r2, 250));
      out.qAnd3 = count();
      return out;
    }""")
    ok("全段階で3件", r["all"] == 3, json.dumps(r))
    ok("★2で絞ると該当1件だけ", r["lv2"] == 1 and r["lv2id"], json.dumps(r))
    ok("★3（肢）でも拾える", r["lv3"] == 1 and r["lv3id"], json.dumps(r))
    ok("全段階へ戻せる", r["back"] == 3, json.dumps(r))
    ok("種別フィルタと併用できる", r["qAnd3"] == 0, json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDD" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
