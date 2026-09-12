# -*- coding: utf-8 -*-
"""test_free_exam_cards.py — 力試しカードの無料版表示と、結果画面の下の購入への線（V3.01・実装計画 段2＋段4）

【何を作ったか（無料版の設計 §3-3）】
  ・力試し画面（鍵なし）：上に1行「プチ模試とハーフ模試を1回ずつ受けられます…必修は全部使えます」。
    プチ／ハーフのカードに「1回ぶん」、受け終わったら「受けた日：9/11（結果を見る）」。
    **受け終わったカードも押せる**（押すと V2.98 の案内＝［結果を見る］がある）。押せなくしない
  ・フル／いじわるのカードは「有料版で受けられます」。押すと購入の案内（解禁の判定には触らない）
  ・結果画面（採点のときも過去の結果のときも）の下に、購入への線を1本。鍵が無いときだけ。
    結果を見るのに購入は要求しない（閉じるを妨げない）
  ・購入済みは何も変わらない（1行も線も出ず、フル・いじわるは普通に押せる）

【ここで固定すること】
  ・鍵なし：1行が出る／プチ・ハーフ「1回ぶん」／フル・いじわる「有料版で」＋押すと購入の案内
  ・受けたあと：カードが「受けた日」になり、押すと案内が開く（始まらない）
  ・結果画面に線が出る（鍵なし）／鍵ありは線も1行も無く、フルは普通に startExam へ
"""
import os, sys, io, json, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = io.open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
ih = io.open(os.path.join(base, "index.html"), encoding="utf-8").read()
css = io.open(os.path.join(base, "styles.css"), encoding="utf-8").read()

ok("カードの無料版情報は freeExamGate から導く（別の項目で持たない）", "function freeCardsInfo" in p2 and "freeExamGate('mock_30', unlocks)" in p2)
ok("受け終わったカードも押せる（押せなくしていない）", "受け終わったカードも押せる" in p2 and "data-free', 'taken'" in p2)
ok("フル・いじわるは有料版。押すと購入の案内", "data-free', 'paid-only'" in p2 and "=== 'paid-only') { M.openBuyDialog(); return; }" in p2)
ok("解禁の判定（MOCK_DEFS）には触っていない", "MOCK_DEFS" not in p2[p2.index("function freeCardsInfo"):p2.index("function openExamList")])
ok("画面の上の1行がある", 'id="exam-free-note"' in ih and "1回ずつ" in ih and "過去問の必修は全部使えます" in ih)
ok("結果画面の下に購入への線がある（1本）", ih.count('id="exam-buy-line"') == 1 and 'id="exam-buy-open"' in ih)
ok("線は鍵が無いときだけ（showExamBuyLine）", "function showExamBuyLine" in p2 and "line.hidden = !free;" in p2)
ok("採点のときも過去の結果のときも線を出す", p2.count("showExamBuyLine();") == 2)
ok("購入は BUY_URL 1箇所", "on($('#exam-buy-open'), 'click', function () { global.open(M.BUY_URL, '_blank', 'noopener'); });" in p2)
ok("受け終わったカードを灰色にしない（CSS）", '.exam-card[data-free="taken"] .exam-state' in css and '.exam-card[data-free="paid-only"]' in css)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
GOOD = ("OMOI1.eyJuIjoiQk9PVEgtVEVTVCIsInQiOjE3NTYwMDAwMDAwMDB9."
        "-2H0zVWaIJ_x2TS5kzEUDkxLSn0TJ23d7-rDjp1gmkc0cRZ7iWREfqGc69hU5D29FFNGwjjaFN7Q_mDQxQnhOQ")
MODAL = "(sel) => { const m = document.querySelector(sel); return !!(m && !m.hidden); }"
CARDS = """() => { const out = {}; document.querySelectorAll('#exam-list .exam-card').forEach(c => {
  out[c.dataset.examId] = { state: c.querySelector('.exam-state').textContent, free: c.getAttribute('data-free') }; });
  out.note = { hidden: document.querySelector('#exam-free-note').hidden, text: document.querySelector('#exam-free-note').textContent };
  return out; }"""

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

    # 解禁条件を満たす（本体の肢に履歴を付ける）
    unl = pg.evaluate("""async () => {
      const S = window.Storage; const atoms = await S.getAllAtoms();
      const now = Date.now(), patch = {};
      atoms.forEach((a, i) => { if (a.pool === 'mock' || i % 5 === 0) return;
        patch[a.atom_id] = { answer_count:1, correct_count:1, last_eval:'normal',
          last_answered_at: now - 86400000*20, srs_step:3, interval_code:'1w', due_date: now + 86400000 }; });
      await S.updateAtomsBulk(patch);
      const r = await window.Scheduler.refreshUnlocks();
      return r.unlocks.map(x => [x.id, x.unlocked]); }""")
    ok("下ごしらえ：プチ・ハーフが解禁される", dict(unl).get("mock_30") and dict(unl).get("mock_60"), unl)

    # --- 鍵なし：カード ---
    pg.evaluate("async () => { await window.Half2Impl.openExamList(); }")
    pg.wait_for_timeout(500)
    c = pg.evaluate(CARDS)
    ok("鍵なし：画面の上に1行が出る", not c["note"]["hidden"] and "1回ずつ" in c["note"]["text"], c["note"])
    ok("鍵なし：プチ・ハーフは「1回ぶん」", "1回ぶん" in c["mock_30"]["state"] and "1回ぶん" in c["mock_60"]["state"]
       and c["mock_30"]["free"] == "once" and c["mock_60"]["free"] == "once", (c["mock_30"], c["mock_60"]))
    ok("鍵なし：フル・いじわるは「製品版で受けられます」（V3.02：有料版と言わない）", c["mock_120"]["state"] == "製品版で受けられます" and c["mock_weak"]["free"] == "paid-only", (c["mock_120"], c["mock_weak"]))

    # フルのカードを押すと購入の案内（模試は始まらない）
    pg.click('#exam-list .exam-card[data-exam="full120"]')
    pg.wait_for_timeout(500)
    ok("鍵なし：フルを押すと購入の案内が開き、模試は始まらない",
       pg.evaluate(MODAL, "#modal-buy") and pg.evaluate("() => (window.Main.state.session||{}).mode") != "exam")
    pg.evaluate("() => { window.Main.closeModals(); }")

    # プチを受けたことにする（印つきの記録）→ カードが「受けた日」になり、押すと案内
    pg.evaluate("""async () => { await window.Storage.saveExamResult({ exam_id:'mock_30', variant:'free_a', at: Date.now(), total:30, correct:22,
      hisshu:{total:6,correct:5,pct:83,pass:true}, ippan:{total:24,correct:17,score:177,pass:false}, passed:false, elapsed_ms:60000 }); }""")
    pg.evaluate("async () => { await window.Half2Impl.openExamList(); }")
    pg.wait_for_timeout(500)
    c2 = pg.evaluate(CARDS)
    ok("受けたあと：プチは「受けた日：M/D（結果を見る）」・ハーフは「1回ぶん」のまま",
       c2["mock_30"]["free"] == "taken" and "受けた日" in c2["mock_30"]["state"] and "結果を見る" in c2["mock_30"]["state"]
       and c2["mock_60"]["free"] == "once", (c2["mock_30"], c2["mock_60"]))
    pg.click('#exam-list .exam-card[data-exam="mini30"]')
    pg.wait_for_timeout(600)
    ok("受けたカードは押せる：V2.98 の案内が開く（結果を見る がある）",
       pg.evaluate(MODAL, "#modal-free-exam") and pg.evaluate("() => !!document.querySelector('#free-exam-actions [data-fx=\"result\"]')"))
    pg.click('#modal-free-exam [data-fx="result"]')
    pg.wait_for_timeout(400)
    ok("結果画面の下に購入への線が出る（鍵なし・過去の結果）",
       pg.evaluate(MODAL, "#modal-exam-result") and pg.evaluate("() => !document.querySelector('#exam-buy-line').hidden"))
    pg.evaluate("() => { window.Main.closeModals(); }")

    # 採点の結果画面にも線が出る
    pg.evaluate("""() => { window.Half2Impl.showExamResult({ exam_id:'mock_60', style:'real', at: Date.now(), total:60, correct:40,
      hisshu:{total:14,correct:12,pct:86,pass:true}, ippan:{total:46,correct:28,score:152,pass:false}, passed:false,
      patterns:{A:3,B:0,C:10}, by_unit:null, elapsed_ms:60000 }); }""")
    pg.wait_for_timeout(700)
    ok("採点の結果画面にも線が出る（鍵なし）", pg.evaluate("() => !document.querySelector('#exam-buy-line').hidden"))
    ok("線は閉じるを妨げない（閉じるボタンは残っている）", pg.evaluate("() => !!document.querySelector('#modal-exam-result [data-close]')"))
    pg.evaluate("() => { window.Main.closeModals(); }")

    # --- 鍵あり：何も変わらない ---
    act = pg.evaluate("async (k) => { const r = await window.NurseLicense.activate(k); await window.Main.refreshHome(); return r.ok; }", GOOD)
    ok("下ごしらえ：本物の鍵が通る", act is True, act)
    pg.evaluate("async () => { await window.Half2Impl.openExamList(); }")
    pg.wait_for_timeout(500)
    c3 = pg.evaluate(CARDS)
    ok("鍵あり：1行は出ず、カードに無料版の印が無い",
       c3["note"]["hidden"] and all(c3[k]["free"] is None for k in ("mock_30", "mock_60", "mock_120", "mock_weak"))
       and "1回ぶん" not in c3["mock_30"]["state"] and c3["mock_120"]["state"] != "製品版で受けられます", c3)
    pg.evaluate("""() => { window.Half2Impl.showExamResult({ exam_id:'mock_30', style:'real', at: Date.now(), total:30, correct:22,
      hisshu:{total:6,correct:5,pct:83,pass:true}, ippan:{total:24,correct:17,score:177,pass:false}, passed:false,
      patterns:{A:3,B:0,C:10}, by_unit:null, elapsed_ms:60000 }); }""")
    pg.wait_for_timeout(700)
    ok("鍵あり：結果画面に線は出ない", pg.evaluate("() => document.querySelector('#exam-buy-line').hidden"))
    pg.evaluate("() => { window.Main.closeModals(); }")
    # フルを押すと購入の案内ではなく startExam の道（未解禁なら「まだ解禁されていません」のトースト）
    pg.evaluate("async () => { await window.Half2Impl.openExamList(); }")
    pg.wait_for_timeout(500)
    pg.click('#exam-list .exam-card[data-exam="full120"]')
    pg.wait_for_timeout(500)
    ok("鍵あり：フルを押しても購入の案内は開かない", not pg.evaluate(MODAL, "#modal-buy"))
    pg.evaluate("async () => { await window.NurseLicense.deactivate(); window.Main.closeModals(); }")

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  free_exam_cards" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
