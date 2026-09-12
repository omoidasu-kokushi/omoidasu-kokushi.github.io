# -*- coding: utf-8 -*-
"""test_wording_product.py — 画面の「有料版」を「製品版」に言い換える／about.html の #buy を案Bに合わせる（V3.02）

【何が起きていたか】
  ・V2.98〜V3.01 で購入への線が3か所（結果画面の下・フル／いじわるのカード・2回目の案内）に増え、
    どれも「有料版」と書いていた。利用者裁定（2026-09-11）「金儲け感が前面に出てる。製品版にしておく」。
  ・その3か所の行き先 about.html#buy は「200問までは無料」のまま残っていた。
    数の門（FREE_LIMIT 200）は V3.00 で単元の門（案B）に変わっているので、**行き先だけが古い文言**だった。
    購入導線を増やした版（V3.01）が、増やしたぶんだけ古い案内へ人を送っていたことになる。

【ここで固定すること】
  ・画面に出る文字に「有料版」「購入ページ」が無い（コメントは対象外。過去の経緯はコメントに残す）
  ・ホームの1行・設定のライセンス欄・力試しのカード・購入の案内・結果画面の線・2回目の案内の全部が「製品版」
  ・about.html：「200問まで無料」が無い／「必修は無料で全部」「製品版は準備中です（10月30日予定）」がある
  ・購入への線は増えていない（3か所のまま。BUY_URL は1箇所）
"""
import os, sys, io, re
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
def strip_js(s):   # コメントを外す（画面に出る文字だけを見る）
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", s)
def strip_html(s):
    return re.sub(r"<!--.*?-->", "", s, flags=re.S)

ih, ab = strip_html(rd("index.html")), strip_html(rd("about.html"))
p1, p2, sc = strip_js(rd("20260815_main_part1_V1.38.js")), strip_js(rd("20260815_main_part2_V1.45.js")), strip_js(rd("scheduler.js"))

ok("index.html：画面の文字に「有料版」が無い", "有料版" not in ih)
ok("index.html：ボタンに「購入ページ」が無い（製品版を見る）", "購入ページ" not in ih and ih.count("製品版を見る") >= 3)
ok("part1：ホームの1行は「製品版」", "有料版" not in p1 and "模試の続きは製品版です" in p1)
ok("part2：カード・2回目の案内・設定欄が「製品版」", "有料版" not in p2 and "製品版で受けられます" in p2
   and "予想問題の続きは製品版に入っています" in p2 and "予想問題をぜんぶ使う（製品版を見る）" in p2)
ok("scheduler：門で止まったときの理由も「製品版」", "有料版" not in sc and "この範囲の新しい問題は製品版に入っています" in sc)
ok("about.html：「200問まで無料」が消えている（V3.00 案Bと合っている）", "200問" not in ab)
ok("about.html：必修は無料で全部・他は製品版", "過去問の必修は、無料で全部使えます" in ab and "製品版に入っています" in ab)
ok("about.html：製品版は準備中（10月30日予定）", "製品版は準備中です（10月30日予定）" in ab)
ok("about.html：復習は続く・記録は消えない、を残している", "復習はそのまま続けられます" in ab and "消えたり" in ab)
ok("購入への線は増えていない（結果画面1・カード1・2回目の案内1）", rd("index.html").count('id="exam-buy-line"') == 1
   and rd("20260815_main_part2_V1.45.js").count("act: 'buy'") == 2 and "BUY_URL = 'https://omoidasu-kokushi.github.io/about.html#buy'" in rd("20260815_main_part1_V1.38.js"))

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
MODAL = "(sel) => { const m = document.querySelector(sel); return !!(m && !m.hidden); }"

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.evaluate("""async () => { await window.Storage.setMetaBulk({ onboarding_done: true,
      tips_seen: ['unit_hero','qty','next','scan','level','settings_btn','theme','back','home_tip',
                  'qstar','tagpill','star','locked','memo','detail','summary',
                  'q_star','img_toggle','numeric_input','pomodoro','stem_expand','ground','exam'] }); }""")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.wait_for_timeout(600)
    pg.evaluate("() => { window.Main.closeModals(); }")
    ok("鍵が無い＝無料版", pg.evaluate("() => !window.NurseLicense.isPaid()"))

    # DOM の文字ぜんぶ（隠れている枡も含む。コメントは textContent に入らない）
    ok("DOM の文字に「有料版」が無い", pg.evaluate("() => !document.body.textContent.includes('有料版')"))

    home = pg.evaluate("() => { window.Main.refreshFreeGate(); return document.querySelector('#free-gate-text').textContent; }")
    ok("ホームの1行：製品版", "製品版です" in home and "必修は全部使えます" in home, home)
    lic = pg.evaluate("() => { window.Half2Impl.refreshLicense(); return { note: document.querySelector('#lic-note').textContent, btn: document.querySelector('#lic-buy').textContent }; }")
    ok("設定のライセンス欄：製品版・ボタンは「製品版を見る」", "製品版です" in lic["note"] and lic["btn"].strip() == "製品版を見る", lic)
    buy = pg.evaluate("() => { window.Main.openBuyDialog(); return { title: document.querySelector('#modal-buy .modal-title').textContent, btn: document.querySelector('#buy-open').textContent }; }")
    ok("購入の案内：見出しとボタンが製品版", "製品版に入っています" in buy["title"] and buy["btn"].strip() == "製品版を見る", buy)
    pg.evaluate("() => { window.Main.closeModals(); }")

    # 解禁 → カード → 2回目の案内（両方受け終わり）
    pg.evaluate("""async () => {
      const S = window.Storage; const atoms = await S.getAllAtoms();
      const now = Date.now(), patch = {};
      atoms.forEach((a, i) => { if (a.pool === 'mock' || i % 5 === 0) return;
        patch[a.atom_id] = { answer_count:1, correct_count:1, last_eval:'normal',
          last_answered_at: now - 86400000*20, srs_step:3, interval_code:'1w', due_date: now + 86400000 }; });
      await S.updateAtomsBulk(patch);
      await window.Scheduler.refreshUnlocks();
      await S.saveExamResult({ exam_id:'mock_30', variant:'free_a', at: now - 5000, total:30, correct:22, passed:false, elapsed_ms:60000 });
      await S.saveExamResult({ exam_id:'mock_60', variant:'free_b', at: now - 3000, total:60, correct:40, passed:false, elapsed_ms:60000 });
      await window.Half2Impl.openExamList(); }""")
    pg.wait_for_timeout(500)
    cards = pg.evaluate("() => { const o = {}; document.querySelectorAll('#exam-list .exam-card').forEach(c => { o[c.dataset.examId] = c.querySelector('.exam-state').textContent; }); o.note = document.querySelector('#exam-free-note').textContent; return o; }")
    ok("力試し：フル・いじわるは「製品版で受けられます」・上の1行も製品版", cards["mock_120"] == "製品版で受けられます" and cards["mock_weak"] == "製品版で受けられます" and "製品版です" in cards["note"], cards)
    pg.evaluate("async () => { await window.Half2Impl.startExam('mock_60'); }")
    pg.wait_for_timeout(600)
    fx = pg.evaluate("() => ({ open: !document.querySelector('#modal-free-exam').hidden, title: document.querySelector('#free-exam-title').textContent, body: document.querySelector('#free-exam-body').textContent, btns: Array.from(document.querySelectorAll('#free-exam-actions button')).map(b => b.textContent) })")
    ok("両方受け終わりの案内：見出し・本文・ボタンが製品版（有料版と言わない）", fx["open"] and "製品版に入っています" in fx["title"]
       and "製品版には予想問題の続き" in fx["body"] and "製品版を見る" in fx["btns"] and "有料版" not in (fx["title"] + fx["body"] + "".join(fx["btns"])), fx)
    ok("案内に「必修は買わなくても使える」が残っている", "買わなくてもこのまま使えます" in fx["body"])
    pg.click('#modal-free-exam [data-fx="result"]')
    pg.wait_for_timeout(400)
    line = pg.evaluate("() => { const l = document.querySelector('#exam-buy-line'); return { hidden: l.hidden, text: l.textContent }; }")
    ok("結果画面の線：製品版に入っています／製品版を見る", not line["hidden"] and "製品版に入っています" in line["text"] and "製品版を見る" in line["text"], line)
    pg.evaluate("() => { window.Main.closeModals(); }")

    # about.html が実際に開けて、案内が出る
    pg.goto(URL.replace("index.html", "about.html") + "#buy", wait_until="load")
    pg.wait_for_timeout(300)
    at = pg.evaluate("() => document.body.innerText")
    ok("about.html#buy：製品版は準備中（10月30日予定）・200問の文言なし", "製品版は準備中です（10月30日予定）" in at and "200問" not in at and "有料版" not in at)

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  wording_product" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
