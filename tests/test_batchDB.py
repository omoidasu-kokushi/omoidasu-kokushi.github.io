#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDB：使い方を全部読む＝体系的UI紹介ガイド（V2.45で増強）
各節の冒頭に画面モック（解答画面には問題文と選択肢が見える）、ほぼ全項目に
見本UI。模試の節に「提出後の復習」の項。中身の正はTIPSただ1つ。
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
ok("ガイド節に「全部読む」行がある", 'id="btn-guide-all"' in html)
ok("チュートリアル再実行の行は撤去済み", 'id="set-onboarding"' not in html)
ok("モーダルがある", 'id="modal-guide"' in html and 'id="guide-toc"' in html and 'id="guide-body"' in html)
ok("中身の正はTIPS（チュートリアル文）", "GUIDE_SECTIONS" in js and "TIPS[it.k]" in js)
ok("文言の自分直しを通す", "ov('g.' + it.k + '.step'" in js and "ov('g.' + it.k + '.text'" in js)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(800)
    # ガイドは設定から開く導線＝オンボーディング完了後の世界。welcomeが
    # 再表示されてガイドを隠すのは初回だけの挙動なので、完了状態で試す。
    pg.evaluate("async () => { await window.Storage.setMetaBulk({ onboarding_done: true }); }")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(800)
    pg.evaluate("() => window.Main.closeModals()")
    pg.wait_for_timeout(300)
    r = pg.evaluate("""async () => {
      const H = window.Half2;
      const groups = await H.openGuideAll();
      await new Promise(r2 => setTimeout(r2, 300));
      const modal = document.getElementById('modal-guide');
      const toc = document.querySelectorAll('#guide-toc .guide-toc-row').length;
      const secs = document.querySelectorAll('#guide-body .guide-sec').length;
      const items = document.querySelectorAll('#guide-body .guide-item').length;
      const ui = document.querySelectorAll('#guide-body .guide-ui').length;
      const mockStem = !!document.querySelector('#guide-body .q-stem-sample');
      const mockChoices = document.querySelectorAll('#guide-body .choice-list-sample .choice-card').length;
      const hasExamReview = [...document.querySelectorAll('#guide-body .guide-item-title')]
        .some(t => t.textContent.includes('提出後の復習'));
      const hasEvalRoles = [...document.querySelectorAll('#guide-body .guide-item-title')]
        .some(t => t.textContent.includes('評価4ボタンの役割'));
      const noUi = [...document.querySelectorAll('#guide-body .guide-item')]
        .filter(it => !it.querySelector('.guide-ui')).length;
      /* 目次ジャンプ */
      const rows = document.querySelectorAll('#guide-toc .guide-toc-row');
      const last = rows[rows.length - 1];
      const before = document.getElementById('guide-body').scrollTop;
      last.click();
      await new Promise(r2 => setTimeout(r2, 600));
      const after = document.getElementById('guide-body').scrollTop;
      return { groups, shown: !modal.hidden, toc, secs, items, ui, mockStem, mockChoices,
               hasExamReview, hasEvalRoles, noUi, jumped: after > before };
    }""")
    ok("モーダルが開き目次と本文が出る", r["shown"] and 5 <= r["toc"] <= 12 and r["secs"] == r["toc"], json.dumps(r))
    ok("全項目が本文に並ぶ（30件以上）＋見本UIがほぼ全項目に付く", r["items"] >= 30 and r["ui"] >= 33, json.dumps(r))
    ok("評価4ボタンの役割の項がある", r["hasEvalRoles"], json.dumps(r))
    ok("見本UIの無い項目は2つ以下", r["noUi"] <= 2, json.dumps(r))
    ok("解答画面のモックに問題文と選択肢がある", r["mockStem"] and r["mockChoices"] >= 2, json.dumps(r))
    ok("模試後の復習の項がある", r["hasExamReview"], json.dumps(r))
    ok("目次から末尾へ飛べる", r["jumped"], json.dumps(r))
    ok("実行時エラーなし", not errs, str(errs[:2]))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDB" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
