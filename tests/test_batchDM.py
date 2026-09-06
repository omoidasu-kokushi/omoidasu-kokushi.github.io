#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDM：★詳細検索の階層連動＋選択肢キーワード（V2.47・利用者指示）
単元→大項目→中項目→小項目は選ぶたびに配下だけへ絞られ、親を選び直すと
子はリセット。大項目・中項目・小項目・タグは選択肢自体をキーワードで絞れる。
表記：「詳細検索（年度・単元・項目・タグ）」「✏名前変更」。
"""
import io, os, sys, glob, json
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
ok("表記が指定どおり", "詳細検索（年度・単元・項目・タグ）" in html and "✏ 名前変更" in html)
ok("選択肢キーワード欄が4つ", html.count('class="star-f-search set-select"') == 4)

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
      /* 単元Aから大項目違いの2問、単元Bから1問に★ */
      const q1 = qs[0];
      const q2 = qs.find(q => q.unit === q1.unit && q.major !== q1.major) || qs[1];
      const q3 = qs.find(q => q.unit !== q1.unit) || qs[2];
      for (const q of [q1, q2, q3]) { await S.toggleQuestionStar(q.q_id); }
      await H.openStarredNote();
      await new Promise(r2 => setTimeout(r2, 300));
      const out = {};
      const majSel = document.getElementById('star-f-major');
      out.majAll = majSel.options.length - 1;   /* 単元未選択＝3問ぶんの大項目 */
      /* 単元q1を選ぶ→大項目はその単元の2つだけ */
      const unitSel = document.getElementById('star-f-unit');
      unitSel.value = q1.unit;
      unitSel.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 300));
      out.majInUnit = document.getElementById('star-f-major').options.length - 1;
      /* 大項目q1を選ぶ→中項目はq1の1つだけ */
      const majSel2 = document.getElementById('star-f-major');
      majSel2.value = q1.major;
      majSel2.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 300));
      out.medInMajor = document.getElementById('star-f-medium').options.length - 1;
      out.medIsQ1 = document.getElementById('star-f-medium').options[1].value === q1.medium;
      /* 単元を選び直す→大項目の選択はリセット */
      const unitSel2 = document.getElementById('star-f-unit');
      unitSel2.value = q3.unit;
      unitSel2.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 300));
      out.majReset = document.getElementById('star-f-major').value === '';
      /* タグの選択肢キーワード */
      document.getElementById('star-f-clear').click();
      await new Promise(r2 => setTimeout(r2, 300));
      const tagSel = document.getElementById('star-f-tag');
      out.tagAll = tagSel.options.length - 1;
      const someTag = tagSel.options[1].value;   /* 例：#人口動態統計 */
      const fltKey = someTag.slice(1, 3);        /* 先頭2文字で絞る */
      const flt = document.querySelector('.star-f-search[data-flt="tag"]');
      flt.value = fltKey;
      flt.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 500));
      const tagSel2 = document.getElementById('star-f-tag');
      out.tagFiltered = tagSel2.options.length - 1;
      out.tagMatch = [...tagSel2.options].slice(1).every(o => o.value.includes(fltKey));
      return out;
    }""")
    ok("単元未選択では全大項目", r["majAll"] >= 2, json.dumps(r, ensure_ascii=False))
    ok("単元を選ぶと配下の大項目だけ", r["majInUnit"] == 2, json.dumps(r, ensure_ascii=False))
    ok("大項目を選ぶと配下の中項目だけ", r["medInMajor"] == 1 and r["medIsQ1"], json.dumps(r, ensure_ascii=False))
    ok("親を選び直すと子はリセット", r["majReset"], json.dumps(r, ensure_ascii=False))
    ok("タグの選択肢をキーワードで絞れる",
       r["tagFiltered"] >= 1 and r["tagFiltered"] < r["tagAll"] and r["tagMatch"], json.dumps(r, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDM" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
