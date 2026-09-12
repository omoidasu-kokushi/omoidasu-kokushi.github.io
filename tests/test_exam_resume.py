# -*- coding: utf-8 -*-
"""test_exam_resume.py — 模試の中断と再開（誤タップで160分が飛ばない）（V3.11）

【何が起きていたか（利用者裁定 2026-09-12）】
  ・V3.10 で模試を1枚の問題用紙にしたが、◀戻る／ホームを押すと解答は捨てられていた
    （確認ダイアログを1枚足しただけで、押し間違えれば120問・160分が消える）。
    利用者「誤タップ防止はしよう。途中でやめても途中から再開できるようにしよう」
  ・付随の裁定（既定で進めた）：中断中は時計を止める。進めたままにすると、翌朝開いた瞬間に
    「残り0分」で自動提出になる。本番に寄せる理屈より、実際に起きる壊れ方のほうが重い。

【ここで固定すること】
  ・塗った肢・☑・入力した数値・残り時間・問の並びを meta.exam_resume に控える
    （肢や☑を押すたび＝少し待ってからまとめて／畳むとき＝すぐ）
  ・控えるのは q_id だけ。問題の本文は控えない（台帳から取り直す）
  ・◀戻る／ホームの確認は「模試を中断しますか」。**解答は消えない**
  ・力試しモードに［中断した模試を続ける］の帯が出る。押すと続きから（残り時間もそこから）
  ・模試カードを押したときも、中断があれば2択（続きから／最初から始める）。最初からは控えを捨てる
  ・提出すると控えは消える（結果の裏で「続きから」が残らない）
  ・問題が台帳から消えていたら、その分を除いて再開する（全部消えていたら控えを捨てる）
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
ih, css = rd("index.html"), rd("styles.css")
p1, p2, dr = rd("20260815_main_part1_V1.38.js"), rd("20260815_main_part2_V1.45.js"), rd("drive.js")

ok("中断の入口がある（帯と2択）", 'id="exam-resume-bar"' in ih and 'id="modal-exam-resume"' in ih
   and 'id="exam-resume-go">続きから<' in ih and 'id="exam-resume-fresh">最初から始める<' in ih
   and ".exam-resume-bar{" in css)
ok("控えるのは q_id だけ（問題の本文は控えない）", "q_ids: ex.questions.map(function (q) { return q.q_id; })" in p2
   and "function paperStateNow" in p2 and "S.getQuestionsFull(rs.q_ids)" in p2)
# 塗る（onPaperChoice）・印（onPaperMark）・数値（input）の3経路から控える
ok("押すたびに控える（少し待ってからまとめて）", "function savePaperState" in p2 and "resumeTimer = global.setTimeout" in p2
   and p2.count("savePaperState();") == 3)
ok("畳むとき・閉じるときはすぐ控える", "if (st.exam && !st.exam.submitted) { flushPaperState(); }" in p2
   and "'pagehide'" in p2 and "visibilitychange" in p2)
ok("提出したら控えを消す", "return clearExamResume().then(function () { return gradeExam(answers); });" in p2)
ok("◀戻る／ホームの文言が「中断」になった（解答は消えない）", "title: '模試を中断しますか'" in p1
   and "塗った解答・印・残り時間はそのまま残ります" in p1 and "解答は消え、採点されません" not in p1)
ok("中断中は時計を止める（残り時間から再開）", "deadline: Date.now() + Math.max(rs.remain_ms || 0, 1000)" in p2
   and "remain_ms: Math.max(0, ex.deadline - Date.now())" in p2)
ok("新規と再開で同じものを張る（onAbort の張り忘れを防ぐ）", "function mountPaper" in p2
   and "return mountPaper();" in p2 and "return mountPaper(rs);" in p2 and p2.count("function mountPaper") == 1)
ok("控えは端末内だけ（同期には乗せない）", "exam_resume" not in dr)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

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
      /* 解禁・定着率の警告・無料版の1回ぶんの門は、この試験の見たいものではない。最後まで外しておく
         （［最初から始める］は startExam をもう一度通るので、その時も外れている必要がある） */
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      S.getExamHistory = () => Promise.resolve([]);
      const start = async () => {
        await H.startExam('mock_30', 'real');
        for (let i = 0; i < 100; i++) { if (M.state.session && M.state.session.mode === 'exam'
          && q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
        M.closeModals();
      };
      await start();
      const ex = HI.state.exam;
      const len = ex.questions.length;
      const qids = ex.questions.map(x => x.q_id);
      /* 問1で肢2を塗り、問1の肢3に☑。問3で肢1を塗る */
      const li = (i) => document.querySelector('#paper-list .pq[data-index="' + i + '"]');
      const card = (i, k) => li(i).querySelectorAll('.choice-card')[k];
      card(0, 1).querySelector('.choice-body').click();
      card(0, 2).querySelector('.choice-mark').click();
      card(2, 0).querySelector('.choice-body').click();
      const pickedNum = parseInt(card(0, 1).getAttribute('data-num'), 10);
      const markedId = card(0, 2).getAttribute('data-atom-id');
      await wait(900);   /* debounce（600ms）を待つ */
      const rs0 = await S.getMeta('exam_resume', null);
      out.saved = !!rs0 && rs0.exam_id === 'mock_30' && rs0.q_ids.length === len
        && (rs0.picks[qids[0]] || [])[0] === pickedNum && !!(rs0.marks[qids[0]] || {})[markedId]
        && (rs0.picks[qids[2]] || []).length === 1;
      out.noBody = !!rs0 && !('questions' in rs0) && JSON.stringify(rs0).length < 60000;
      /* 残り時間を 12分にしてから、ホームで中断（確認あり） */
      ex.deadline = Date.now() + 12 * 60000;
      q('btn-home').click(); await wait(250);
      out.askIsPause = !q('modal-confirm').hidden && /中断/.test(q('confirm-title').textContent)
        && /残ります/.test(q('confirm-body').textContent);
      q('confirm-go').click(); await wait(500);
      const rs1 = await S.getMeta('exam_resume', null);
      out.keptOnLeave = q('screen-home').classList.contains('is-active') && !M.state.session.mode
        && !!rs1 && (rs1.picks[qids[0]] || [])[0] === pickedNum
        && rs1.remain_ms > 11 * 60000 && rs1.remain_ms <= 12 * 60000;
      /* 力試しモードに帯が出る */
      await H.openExamList(); await wait(600);
      const bar = q('exam-resume-bar');
      out.barShown = !bar.hidden && /中断した模試を続ける/.test(bar.textContent)
        && /プチ模試/.test(bar.textContent) && /解答ずみ 2問/.test(bar.textContent);
      /* 帯から続きから → 塗りも☑も残り時間も戻る */
      bar.click();
      for (let i = 0; i < 100; i++) { if (q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      await wait(300);
      const ex2 = HI.state.exam;
      out.resumed = ex2.resumed === true && ex2.questions.length === len
        && card(0, 1).classList.contains('is-selected')
        && card(0, 2).querySelector('.choice-mark').getAttribute('aria-pressed') === 'true'
        && card(2, 0).classList.contains('is-selected')
        && (ex2.picks[qids[0]] || [])[0] === pickedNum;
      const leftMin = (ex2.deadline - Date.now()) / 60000;
      out.clockKept = leftMin > 11 && leftMin <= 12.1;
      out.timerText = q('paper-timer').textContent;
      /* V3.15：帯は「終了 13:45」の固定表記。時計が生きていること＋終了時刻が deadline と一致することで見る */
      const pad2 = (n) => ('0' + n).slice(-2);
      const dd = new Date(ex2.deadline);
      out.timerRuns = !!ex2.timer && out.timerText === '終了 ' + pad2(dd.getHours()) + ':' + pad2(dd.getMinutes());
      /* 続きから提出 → 控えが消える */
      q('paper-submit').click(); await wait(200);
      q('exam-submit-go').click();
      for (let i = 0; i < 100; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      await wait(300);
      out.clearedOnSubmit = (await S.getMeta('exam_resume', null)) === null && !q('modal-exam-result').hidden;
      out.answersKept = ex2.answers.filter(a => !a.unanswered).length === 2;
      q('modal-exam-result').querySelector('[data-close]').click(); await wait(1500);

      /* 2回目：中断して「最初から始める」→ 控えを捨てて新しく始まる */
      await start();
      const ex3 = HI.state.exam;
      card(0, 0).querySelector('.choice-body').click();
      await wait(900);
      out.savedAgain = !!(await S.getMeta('exam_resume', null));
      q('btn-home').click(); await wait(200); q('confirm-go').click(); await wait(500);
      await H.openExamList(); await wait(500);
      document.querySelector('#exam-list .exam-card[data-exam-id="mock_30"]').click();
      await wait(400);
      out.askTwo = !q('modal-exam-resume').hidden && /続きから/.test(q('exam-resume-go').textContent);
      q('exam-resume-fresh').click();
      await wait(500);
      /* 受け方の2択（本番／直前）は今までどおり通る＝［最初から］は普通の開始と同じ道 */
      out.styleAsked = !q('modal-exam-style').hidden;
      document.querySelector('#modal-exam-style [data-exam-style="real"]').click();
      for (let i = 0; i < 120; i++) { if (HI.state.exam !== ex3 && q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      await wait(400);
      M.closeModals();
      const ex4 = HI.state.exam;
      out.freshDetail = { paper: q('screen-exam-paper').classList.contains('is-active'), resumed: !!ex4.resumed,
        picks: Object.keys(ex4.picks).length, sel: !!document.querySelector('#paper-list .choice-card.is-selected'),
        same: ex4 === ex3, screen: M.state.screen };
      out.freshStart = q('screen-exam-paper').classList.contains('is-active') && !ex4.resumed
        && Object.keys(ex4.picks).length === 0 && !document.querySelector('#paper-list .choice-card.is-selected');

      /* 3回目：問題が台帳から消えたとき（一部／全部） */
      const len4 = ex4.questions.length;
      card(0, 0).querySelector('.choice-body').click();
      await wait(900);
      q('btn-home').click(); await wait(200); q('confirm-go').click(); await wait(400);
      const origFull = S.getQuestionsFull;
      S.getQuestionsFull = (ids) => origFull(ids.slice(0, ids.length - 3));   /* 3問だけ見つからない */
      await H.resumeExam();
      for (let i = 0; i < 100; i++) { if (q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      await wait(300);
      S.getQuestionsFull = origFull;
      out.partialDetail = { qs: HI.state.exam.questions.length, pq: document.querySelectorAll('#paper-list .pq').length, want: len4 - 3 };
      out.partial = HI.state.exam.questions.length === len4 - 3
        && document.querySelectorAll('#paper-list .pq').length === len4 - 3;
      /* 全部消えていたら控えを捨てる */
      q('btn-home').click(); await wait(200); q('confirm-go').click(); await wait(400);
      S.getQuestionsFull = () => Promise.resolve([]);
      await H.resumeExam(); await wait(600);
      S.getQuestionsFull = origFull;
      out.allGone = (await S.getMeta('exam_resume', null)) === null
        && !q('screen-exam-paper').classList.contains('is-active');
      return out; }""")
    ok("塗った肢・☑が控えられる", r["saved"], json.dumps(r, ensure_ascii=False)[:300])
    ok("控えに問題の本文は入らない（q_id だけ）", r["noBody"])
    ok("◀戻る／ホームは「中断」（解答は消えない）", r["askIsPause"] and r["keptOnLeave"])
    ok("力試しモードに帯が出る（模試名・残り時間・解答ずみ）", r["barShown"])
    ok("帯から続きから：塗り・☑・解答が戻る", r["resumed"])
    ok("残り時間も中断したところから（終了時刻が繰り下がる）", r["clockKept"] and r["timerRuns"], r.get("timerText"))
    ok("続きから提出できる。控えは消える", r["clearedOnSubmit"] and r["answersKept"])
    ok("模試カードを押すと2択が出る", r["askTwo"] and r["savedAgain"], json.dumps({k: r.get(k) for k in ["askTwo", "savedAgain"]}, ensure_ascii=False))
    ok("［最初から］は普通の開始と同じ道（受け方の2択も通る）", r["styleAsked"])
    ok("「最初から始める」は控えを捨てて新しく始める", r["freshStart"], json.dumps(r.get("freshDetail"), ensure_ascii=False))
    ok("問題が一部消えていたら、その分を除いて再開する", r["partial"], json.dumps(r.get("partialDetail"), ensure_ascii=False))
    ok("全部消えていたら控えを捨てる（空の模試を開かない）", r["allGone"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_resume" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
