#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDI：★ノート内検索＋名前設定の移設（V2.41）
キーワード（問題文・選択肢・解説）＋出題回・単元・大項目・中項目・小項目・タグで
絞れる。selectの選択肢は「★が付いている問題」から作る。段階名の編集入口は
設定から★ノート内へ移設。
"""
import io, os, sys, glob, json
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
star_sec = html[html.find('id="screen-starred"'):html.find('id="star-list"')]
ok("検索バーがある", 'id="star-search"' in star_sec)
ok("詳しい絞り込み6種がある", all(('id="star-f-%s"' % k) in star_sec
   for k in ('exam', 'unit', 'major', 'medium', 'sub', 'tag')))
ok("名前設定の入口が★ノート内", 'id="btn-star-labels"' in star_sec)
set_sec = html[html.find('8. 表示のカスタマイズ'):html.find('9. データ')]
ok("設定側の入口は撤去済み", 'id="btn-star-labels"' not in set_sec)

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
      /* 異なる単元の2問に★ */
      const q1 = qs[0];
      const q2 = qs.find(q => q.unit !== q1.unit) || qs[1];
      await S.toggleQuestionStar(q1.q_id);
      await S.toggleQuestionStar(q2.q_id);
      await H.openStarredNote();
      await new Promise(r2 => setTimeout(r2, 300));
      const out = {};
      const count = () => document.querySelectorAll('#star-list .star-item').length;
      out.all = count();
      /* 単元で絞る */
      const unitSel = document.getElementById('star-f-unit');
      out.unitOpts = unitSel.options.length;
      unitSel.value = q1.unit;
      unitSel.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 300));
      out.byUnit = count();
      out.noteShown = !document.getElementById('star-hit-note').hidden;
      /* クリア */
      document.getElementById('star-f-clear').click();
      await new Promise(r2 => setTimeout(r2, 300));
      out.cleared = count();
      /* キーワード（問題文の先頭6文字） */
      const kw = (q1.stem || '').slice(0, 6);
      const inp = document.getElementById('star-search');
      inp.value = kw;
      inp.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r2 => setTimeout(r2, 500));
      out.byKw = count();
      out.kwHitHasQ1 = !!document.querySelector('#star-list .star-item[data-qid="' + q1.q_id + '"]');
      /* 名前設定の入口が開く */
      document.getElementById('btn-star-labels').click();
      await new Promise(r2 => setTimeout(r2, 300));
      out.labelModal = !document.getElementById('modal-star-labels').hidden;
      return out;
    }""")
    ok("全2件から始まる", r["all"] == 2, json.dumps(r, ensure_ascii=False))
    ok("単元selectは★の付いた問題から作られる（すべて+2単元）", r["unitOpts"] == 3, json.dumps(r))
    ok("単元で1件に絞れて件数表示が出る", r["byUnit"] == 1 and r["noteShown"], json.dumps(r))
    ok("クリアで戻る", r["cleared"] == 2, json.dumps(r))
    ok("キーワードで絞れる", r["byKw"] >= 1 and r["kwHitHasQ1"], json.dumps(r))
    ok("★ノート内から名前設定が開く", r["labelModal"], json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDI" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
