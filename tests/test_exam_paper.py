# -*- coding: utf-8 -*-
"""test_exam_paper.py — 模試は1枚の問題用紙（全問スクロール・最下部の［提出する］・制限時間）（V3.10）

【何が起きていたか（利用者裁定 2026-09-12）】
  ・V2.17〜V3.09 の模試は出題画面を1問ずつ使い、前へ／次へ／解答一覧／提出のナビで行き来していた。
    「模試自体全てスクロールでは駄目なの？そうすれば次へ前へボタンが不要になる。前へボタンもどれだけ押せばいいか分からない」
    「一覧表示的な機能も無くす。チェックを入れた問題も自分で確認することでより本番度が増す」
    「ボタンは最下部に到達したときに『提出する』が出てくるだけ。解き終わってない問題があっても押せる。
      押したときに『見直しはしましたか？試験終了まで残り○○分です。』とだけ。［見直す］［これで提出］の2択。
      未回答があっても提出してしまう。自己責任」
  ・付随の裁定（既定で進めた）：制限時間は本番の配分 80秒/問（30問40分／60問80分／120問160分）。
    0分で自動提出。5分前に1回通知。残り時間は問題用紙の上に固定で出す。◀戻る／ホームは「模試をやめますか」で1度確認。

【ここで固定すること】
  ・模試を始めると #screen-exam-paper。全問ぶんの .pq が並び、ナビ（#exam-nav）も一覧（#screen-exam-sheet）も無い
  ・肢をタップ＝解答（st.exam.picks）。もう一度押すと外れる。**数で止めない**（1つ選ぶ問でも何個でも塗れる・V3.10 追加裁定）。☐→☑は各肢に残る
  ・［提出する］は最下部（.paper-foot）。未回答があっても押せて、確認は「見直しはしましたか？」＋「試験終了まで残り◯分です。」だけ
  ・［見直す］で戻れる（提出されない）。［これで提出］で採点。未回答は不正解（answered_right=false）で復習に「未回答」と出る
  ・☑は ground_on として記録に残る。反応時間は取れない（think_ms=null。欄はある）
  ・残り時間：開始直後は制限時間そのもの。5分を切ると1回だけ通知＋赤。0で自動提出（gradeExam）
    （V3.15：帯の表示は「終了 13:45」の固定表記になった。表示そのものは test_exam_endtime）
  ・◀戻る／ホームは確認を出す（V3.11 で文言は「模試を中断しますか」＝解答は残る。中断と再開そのものは test_exam_resume）。
    畳むと aborted・時計停止でホームへ。やめなければ残る
  ・⚙設定へ寄り道して戻っても問題用紙と解答が残っている
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
ih, css = rd("index.html"), rd("styles.css")
p1, p2 = rd("20260815_main_part1_V1.38.js"), rd("20260815_main_part2_V1.45.js")

ok("問題用紙の画面がある。ナビと一覧は無い", 'id="screen-exam-paper" class="screen" data-screen="exam_paper"' in ih and 'id="paper-list"' in ih
   and 'id="paper-submit"' in ih and 'id="exam-nav"' not in ih and 'id="screen-exam-sheet"' not in ih and 'id="btn-exam-next"' not in ih)
ok("提出の確認は文言だけ（未回答の数は出さない）", 'id="modal-exam-submit"' in ih and '見直しはしましたか？' in ih and '>見直す<' in ih and '>これで提出<' in ih
   and "'試験終了まで残り' + Math.ceil(left / 60000) + '分です。'" in p2 and "未回答が" not in p2.split("function openExamSubmit")[1][:600])
ok("制限時間は本番の配分（80秒/問）・5分前に通知・0で自動提出",
   "mock_30: 40 * 60000, mock_60: 80 * 60000, mock_120: 160 * 60000, mock_weak: 160 * 60000" in p2
   and "var EXAM_WARN_MS = 5 * 60000;" in p2 and "if (left <= 0) { submitPaper({ timeUp: true }); }" in p2)
ok("解答は提出時に問題用紙から写す。反応時間は null", "function collectPaperAnswers" in p2 and "think_ms: null," in p2 and "ex.answers = answers;" in p2)
ok("選択の数で止めない（利用者裁定「いくらでも選べる」）", "**数で止めない。**" in p2
   and "var need" not in p2.split("function onPaperChoice")[1][:700])
ok("模試は出題画面を通らない（part1 のナビ・復元・移動は消した）", "function examJump" not in p1 and "function restoreExamAnswer" not in p1
   and "function refreshExamNav" not in p1 and "M.hooks.afterGrade = function" not in p2 and "M.go('exam_paper')" in p2)
ok("◀戻る／ホームは確認してから畳む", "function confirmLeaveExam" in p1 and "confirmAction({ title: '模試を中断しますか'," in p1
   and "confirmLeaveExam().then(function (yes) {" in p1)   # V3.11：文言は「中断」へ（解答は残る・test_exam_resume）
ok("残り時間の帯は固定・5分を切ると赤", ".paper-bar{\n  position:sticky;" in css and ".paper-timer.is-warn{ color:var(--c-hard); }" in css)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

FILL = """
      const fillPaper = (n, o) => { o = o || {}; const ex = window.Half2Impl.state.exam;
        ex.questions.forEach((qq, i) => {
          if (n !== undefined && i >= n) return;
          const li = document.querySelector('#paper-list .pq[data-index="' + i + '"]');
          if (qq.question_type === 'numeric') { li.querySelector('.pq-num-input').value = o.wrong ? '0' : String(qq.numeric_answer); return; }
          const atoms = (qq.atoms || []).slice().sort((a, b) => a.original_num - b.original_num);
          const need = Math.max(1, atoms.filter(a => a.is_correct).length);
          let nums = atoms.filter(a => a.is_correct).map(a => a.original_num);
          if (o.wrong) { const w = atoms.filter(a => !a.is_correct).map(a => a.original_num); nums = w.length ? w.slice(0, need) : nums; }
          nums.forEach(num => li.querySelector('.choice-card[data-num="' + num + '"] .choice-body').click());
          if (o.mark && i % 2 === 0) { const b = li.querySelector('.choice-mark'); if (b) b.click(); }
        }); };
"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.wait_for_timeout(600)
    pg.evaluate("() => { const b = document.getElementById('welcome-start'); if (b) b.click(); }")
    pg.wait_for_timeout(400)
    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler, M = window.Main, H = window.Half2, HI = window.Half2Impl;
      const out = {}; const wait = (ms) => new Promise(r => setTimeout(r, ms));
      const q = (id) => document.getElementById(id);
      const toastText = () => (q('toast').hidden ? '' : q('toast-text').textContent);
      """ + FILL + """
      const start = async () => {
        const origU = S.getUnlockState;
        S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
        const origW = K.shouldWarnBeforeExam;
        K.shouldWarnBeforeExam = async () => ({ warn: false });
        /* 無料版の「1回ぶん」の門（V2.98）は別の試験（free_exam_once）で見る。ここは2回目・3回目も始めたいので履歴を空に見せる */
        const origH = S.getExamHistory;
        S.getExamHistory = () => Promise.resolve([]);
        await H.startExam('mock_30', 'real');
        S.getUnlockState = origU; K.shouldWarnBeforeExam = origW; S.getExamHistory = origH;
        for (let i = 0; i < 100; i++) { if (M.state.session && M.state.session.mode === 'exam' && q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
        M.closeModals();
      };
      await start();
      const ex = HI.state.exam;
      const len = ex.questions.length;
      out.len = len;
      /* 画面：全問並ぶ。ナビも一覧も無い。提出は最下部 */
      out.paper = q('screen-exam-paper').classList.contains('is-active') && document.querySelectorAll('#paper-list .pq').length === len
        && !q('exam-nav') && !q('screen-exam-sheet') && !q('screen-quiz').classList.contains('is-active');
      const scroll = q('screen-exam-paper').querySelector('.screen-scroll');
      out.submitLast = scroll.lastElementChild.classList.contains('paper-foot') && !!q('paper-submit') && !q('paper-submit').disabled;
      out.title = q('hdr-path').textContent;
      /* 残り時間：開始直後は 40:00 前後 */
      out.timer0 = q('paper-timer').textContent;
      out.limit = ex.limitMs === 40 * 60000 && Math.abs((ex.deadline - Date.now()) - 40 * 60000) < 5000
        && /^終了 \\d\\d:\\d\\d$/.test(out.timer0);   /* V3.15：表示は終了時刻 */
      /* 肢のタップ＝解答。もう一度で外れる。別の肢で置き換え */
      const li1 = document.querySelector('#paper-list .pq[data-index="0"]');
      const q1 = ex.questions[0];
      const cards = li1.querySelectorAll('.choice-card');
      cards[0].querySelector('.choice-body').click();
      out.pick = cards[0].classList.contains('is-selected') && (ex.picks[q1.q_id] || []).length === 1
        && ex.picks[q1.q_id][0] === parseInt(cards[0].getAttribute('data-num'), 10);
      cards[0].querySelector('.choice-body').click();
      out.unpick = !cards[0].classList.contains('is-selected') && (ex.picks[q1.q_id] || []).length === 0;
      /* V3.10：数で止めない。1つ選ぶ問でも3つ塗れる（採点で不正解になるだけ） */
      out.need1 = Math.max(1, (q1.atoms || []).filter(a => a.is_correct).length);
      cards[0].querySelector('.choice-body').click();
      cards[1].querySelector('.choice-body').click();
      cards[2].querySelector('.choice-body').click();
      out.manyPicks = ex.picks[q1.q_id].length === 3 && [0, 1, 2].every(k => cards[k].classList.contains('is-selected'));
      cards[2].querySelector('.choice-body').click();
      cards[0].querySelector('.choice-body').click();
      out.repick = ex.picks[q1.q_id].length === 1 && cards[1].classList.contains('is-selected');
      /* ☐→☑ */
      const mk = cards[2].querySelector('.choice-mark[data-kind="ground"]');
      mk.click();
      out.mark = mk.getAttribute('aria-pressed') === 'true' && mk.textContent === '☑' && cards[2].classList.contains('is-eliminated');
      out.noVerdict = !li1.querySelector('.choice-card.is-correct') && q('verdict-pop').hidden;
      /* 提出（未回答だらけ）→ 文言だけの確認 → 見直す */
      q('paper-submit').click(); await wait(200);
      out.askShown = !q('modal-exam-submit').hidden && /残り\\d+分です/.test(q('exam-submit-body').textContent)
        && q('exam-submit-body').textContent.indexOf('未回答') < 0;
      document.querySelector('#modal-exam-submit [data-close]').click(); await wait(200);
      out.reviewBack = q('modal-exam-submit').hidden && q('screen-exam-paper').classList.contains('is-active') && !ex.submitted
        && cards[1].classList.contains('is-selected') || (need1 !== 1 && !ex.submitted);
      /* ◀戻る → 確認 → やめない */
      q('btn-back').click(); await wait(200);
      out.leaveAsk = !q('modal-confirm').hidden && /模試を中断しますか/.test(q('confirm-title').textContent);   /* V3.11 */
      document.querySelector('#modal-confirm [data-close]').click(); await wait(200);
      out.stay = q('screen-exam-paper').classList.contains('is-active') && M.state.session.mode === 'exam' && !!ex.timer;
      /* ⚙設定へ寄り道 → ◀戻る → 問題用紙と解答が残る */
      q('btn-settings').click(); await wait(300);
      out.onSettings = M.state.screen === 'settings' && M.state.session.mode === 'exam';
      q('btn-back').click(); await wait(300);
      out.backToPaper = q('screen-exam-paper').classList.contains('is-active') && (ex.picks[q1.q_id] || []).length >= 1
        && document.querySelector('#paper-list .pq[data-index="0"] .choice-card.is-selected');
      /* 5分前の通知：期限を4分後にして tick */
      ex.deadline = Date.now() + 4 * 60000;
      H.tickPaper();
      out.warnText = toastText() + ' | ' + q('paper-timer').textContent + ' | ' + ex.warned;
      out.warn = /残り5分/.test(toastText()) && ex.warned === true && q('paper-timer').classList.contains('is-warn')
        && /^終了 \\d\\d:\\d\\d$/.test(q('paper-timer').textContent);   /* V3.15：赤くなるが数字は動かない */
      q('toast').hidden = true;
      H.tickPaper();
      out.warnOnce = toastText() === '' && ex.warned === true;
      /* 残りを埋める（問1は誤答のまま・問2〜は正解・偶数問に☑）。最後の2問は未回答で提出 */
      const picksBefore = ex.picks[q1.q_id].slice();
      fillPaper(len - 2, { mark: true });
      ex.picks[q1.q_id] = picksBefore;   /* 問1はさっきの手選び（fill で正解が足されたら戻す） */
      li1.querySelectorAll('.choice-card').forEach(c => c.classList.toggle('is-selected', picksBefore.indexOf(parseInt(c.getAttribute('data-num'), 10)) >= 0));
      /* 時間切れ → 自動提出（確認なし・トースト） */
      ex.deadline = Date.now() - 10;
      H.tickPaper();
      const timeUpToast = /試験終了の時刻です/.test(toastText());
      for (let i = 0; i < 100; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      out.timeUp = !q('modal-exam-result').hidden && timeUpToast && ex.submitted === true && !ex.timer;
      out.answers = ex.answers.length === len && ex.answers.filter(a => a.unanswered).length === 2
        && ex.answers.slice(-2).every(a => a.answered_right === false && a.atoms.every(x => !x.picked));
      out.thinkNull = ex.answers.every(a => ('think_ms' in a) && a.think_ms === null);
      out.groundKept = ex.answers[0].atoms.filter(x => x.ground_on).length === 2   /* 手で付けた1つ＋fill の1つ */
        && ex.answers[2].atoms.filter(x => x.ground_on).length === 1 && ex.answers[1].atoms.filter(x => x.ground_on).length === 0;
      out.score = q('exam-score').textContent;
      out.hooksCleared = !M.hooks.afterGrade && !M.hooks.onAbort && M.state.session.mode !== 'exam';
      /* 復習：未回答は「未回答」と出る */
      q('btn-exam-review').click(); await wait(300);
      q('exam-review-style-button').click(); await wait(600);
      const heads = document.querySelectorAll('#exam-review-list .xr-q');
      out.reviewUn = heads.length === len && /未回答/.test(heads[len - 1].querySelector('.xr-sum').textContent)
        && heads[len - 1].querySelector('.xr-mark.is-wrong');
      q('exam-review-done').click(); await wait(1200);

      /* 2回目：やめる（◀戻る → やめる）→ 畳まれてホーム */
      await start();
      const ex2 = HI.state.exam;
      document.querySelector('#paper-list .pq[data-index="0"] .choice-body').click();
      q('btn-back').click(); await wait(200);
      q('confirm-go').click(); await wait(400);
      out.abortDetail = { home: q('screen-home').classList.contains('is-active'), mode: M.state.session.mode, aborted: ex2.aborted, timer: ex2.timer, ans: ex2.answers.length, onAbort: typeof M.hooks.onAbort, screen: M.state.screen, confirmHidden: q('modal-confirm').hidden };
      out.abort = q('screen-home').classList.contains('is-active') && !M.state.session.mode && ex2.aborted === true && !ex2.timer
        && ex2.answers.length === 0 && !M.hooks.onAbort;
      /* 3回目：ホームでやめる */
      await start();
      const ex3 = HI.state.exam;
      q('btn-home').click(); await wait(200);
      out.homeAsk = !q('modal-confirm').hidden;
      q('confirm-go').click(); await wait(400);
      out.homeAbort = q('screen-home').classList.contains('is-active') && !M.state.session.mode && ex3.aborted === true;
      return out; }""")
    ok("模試を始めると問題用紙。全問並び、ナビも一覧も無い。題は「力試し模試」", r["paper"] and r["title"] == "力試し模試", json.dumps(r, ensure_ascii=False))
    ok("［提出する］は最下部にあり、最初から押せる", r["submitLast"])
    ok("制限時間は40分（30問＝本番の配分）・帯は終了時刻", r["limit"], r["timer0"])
    ok("肢のタップ＝解答。もう一度で外れる", r["pick"] and r["unpick"])
    ok("1つ選ぶ問でも何個でも塗れる（数で止めない）", r["manyPicks"] and r["repick"], r["need1"])
    ok("☐→☑が付く。正誤は一切出ない", r["mark"] and r["noVerdict"])
    ok("未回答があっても提出できる。確認は「残り◯分」だけ（未回答の数は出ない）", r["askShown"])
    ok("［見直す］で問題用紙へ戻る（提出されない）", r["reviewBack"])
    ok("◀戻るは確認を出す（V3.11：文言は「中断」）。やめなければ残る", r["leaveAsk"] and r["stay"])
    ok("⚙設定へ寄り道して戻っても問題用紙と解答が残る", r["onSettings"] and r["backToPaper"])
    ok("5分前に1回だけ通知・赤", r["warn"] and r["warnOnce"], json.dumps({"warn": r["warn"], "once": r["warnOnce"], "t": r.get("warnText")}, ensure_ascii=False))
    ok("0分で自動提出（確認なし）。未回答2問は不正解で入る", r["timeUp"] and r["answers"], r["score"])
    ok("反応時間は null（欄はある）。☑は ground_on に残る", r["thinkNull"] and r["groundKept"])
    ok("採点後はフックが外れる。復習に「未回答」と出る", r["hooksCleared"] and r["reviewUn"])
    ok("◀戻る→やめる：畳まれてホーム（時計も止まる）", r["abort"], json.dumps(r.get("abortDetail"), ensure_ascii=False))
    ok("ホーム→やめる：同じ", r["homeAsk"] and r["homeAbort"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_paper" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
