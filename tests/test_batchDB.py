#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDB：使い方を全部読む＝目次つき縦スクロール（V2.33・利用者裁定）
「チュートリアルもう一度」より「知りたい所だけ拾い読み」。中身の正はHOME_TIPS
ただ1つ（二重管理しない）。文言の自分直し（text_overrides）も反映される。
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
ok("チュートリアル再体験も残る", 'id="set-onboarding"' in html)
ok("モーダルがある", 'id="modal-guide"' in html and 'id="guide-toc"' in html and 'id="guide-body"' in html)
ok("中身の正はHOME_TIPS", "HOME_TIPS.forEach(function (t) {" in js and "openGuideAll" in js)
ok("文言の自分直しを通す", js.count("ov(t.id + '.label'") >= 2)

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
      /* 目次ジャンプ */
      const rows = document.querySelectorAll('#guide-toc .guide-toc-row');
      const last = rows[rows.length - 1];
      const before = document.getElementById('guide-body').scrollTop;
      last.click();
      await new Promise(r2 => setTimeout(r2, 600));
      const after = document.getElementById('guide-body').scrollTop;
      return { groups, shown: !modal.hidden, toc, secs, items, jumped: after > before };
    }""")
    ok("モーダルが開き目次と本文が出る", r["shown"] and 5 <= r["toc"] <= 20 and r["secs"] == r["toc"], json.dumps(r))
    ok("全話が本文に並ぶ（30件以上）", r["items"] >= 30, json.dumps(r))
    ok("目次から末尾へ飛べる", r["jumped"], json.dumps(r))
    ok("実行時エラーなし", not errs, str(errs[:2]))
    br.close()
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDB" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
