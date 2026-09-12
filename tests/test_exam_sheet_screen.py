# -*- coding: utf-8 -*-
"""test_exam_sheet_screen.py — 模試の解答一覧を画面にする。行に問題文（ひと回り小さく2行まで）と答え・☑（V3.04）

【何が起きていたか（利用者裁定 2026-09-12）】
  ・V2.17 の一覧はモーダルで、行は「番号＋自分の答え（①）＋☑×2」だけ。
    「問1がどんな問題でどう悩んだのか分からない」→ 問題文を出す。モーダルでは狭いので**画面遷移**にする
  ・☑は「迷った二択の印」のような用途自由の印（V3.05 で意味を確定）。どの肢に付けたかを番号で出す

【ここで固定すること】
  ・一覧は画面（#screen-exam-sheet）。ヘッダーの題は「解答一覧」。行に問題文があり、2行で切る（CSS）
  ・行の答えの欄：「答え ②」＋「☑ ①③」（付けた肢の番号）。未回答は「未回答」
  ・行タップ → 解答画面のその問題へ。［解答に戻る］→ 同じ問題へ。ヘッダーの◀戻る → 模試を畳まずに解答画面へ
  ・一覧の［提出する］は確認なしで採点（一覧そのものが確認）
  ・一覧を開いている間もフック（afterGrade 等）は生きている（模試は続いている）
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

ok("解答一覧の画面がある（モーダルは無い）", 'id="screen-exam-sheet" class="screen" data-screen="exam_sheet"' in ih
   and 'id="modal-exam-confirm"' not in ih and 'id="exam-confirm-list"' in ih and 'id="exam-confirm-submit" disabled' in ih)
ok("ヘッダーの題は「解答一覧」", "exam_sheet: '解答一覧'" in p1)
ok("行に問題文（.ec-stem）と答え（.ec-ans）", "'<p class=\"ec-stem\">' + esc(q.stem || '') + '</p>'" in p2 and "'答え <b>'" in p2 and "'　☑ ' + esc(marks)" in p2)
ok("問題文は2行で切り、解答画面よりひと回り小さい", "-webkit-line-clamp:2" in css[css.index(".ec-stem{"):css.index(".ec-stem{")+300]
   and "font-size:var(--fs-base)" in css[css.index(".ec-stem{"):css.index(".ec-stem{")+300] and "font-size:var(--fs-lg)" in css[css.index(".q-stem-full{"):css.index(".q-stem-full{")+400])
ok("一覧を開くのは画面遷移（openExamConfirm → go('exam_sheet')）", "return M.go('exam_sheet', { replace: false });" in p2 and "openModal('#modal-exam-confirm')" not in p2)
ok("戻りは解答画面の同じ問題へ（backToExam）", "function backToExam(index)" in p2 and "M.examJump(isNum(index) ? index : M.state.session.index)" in p2)

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
      const S = window.Storage, K = window.Scheduler, M = window.Main, H = window.Half2;
      const out = {}; const wait = (ms) => new Promise(r => setTimeout(r, ms));
      const q = (id) => document.getElementById(id);
      const origU = S.getUnlockState;
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      const origW = K.shouldWarnBeforeExam;
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      await H.startExam('mock_30', 'real');
      S.getUnlockState = origU; K.shouldWarnBeforeExam = origW;
      for (let i = 0; i < 100; i++) { if (M.state.session && M.state.session.mode === 'exam' && M.state.current) break; await wait(50); }
      M.closeModals();
      const len = M.state.session.questions.length;
      const sheetOpen = () => q('screen-exam-sheet').classList.contains('is-active');
      const quizOpen = () => q('screen-quiz').classList.contains('is-active');
      /* 問1：肢1を選び、肢2と肢3に☑ */
      const cur = M.state.current;
      cur.selected = [cur.atoms[0].original_num];
      const marks = [cur.atoms[1], cur.atoms[2]].filter(Boolean).map(a => a.atom_id);
      marks.forEach(id => { cur.eliminated[id] = true; });
      const markNums = [cur.atoms[1], cur.atoms[2]].filter(Boolean).map(a => a.original_num);
      const stem1 = cur.question.stem;
      M.confirmAnswer(); await wait(300);
      /* 一覧を開く */
      q('btn-exam-list').click(); await wait(350);
      out.sheetOpen = sheetOpen() && !quizOpen();
      out.title = q('hdr-path').textContent;
      const rows = document.querySelectorAll('#exam-confirm-list .ec-row');
      out.rows = rows.length === len;
      const r1 = rows[0];
      out.stemShown = r1.querySelector('.ec-stem').textContent === stem1;
      out.ansShown = /答え/.test(r1.querySelector('.ec-ans').textContent) && /☑/.test(r1.querySelector('.ec-ans').textContent);
      const circ = '①②③④⑤⑥⑦⑧⑨⑩';
      out.marksShown = markNums.every(n => r1.querySelector('.ec-ans').textContent.split('☑')[1].indexOf(circ[n - 1]) >= 0);
      out.unanswered = document.querySelectorAll('#exam-confirm-list .ec-row.is-un').length === len - 1
        && rows[1].querySelector('.ec-ans').textContent === '未回答';
      out.hooksAlive = typeof M.hooks.afterGrade === 'function' && M.state.session.mode === 'exam';
      /* 2行で切る：長い問題文でも行の高さが問題文2行ぶんまで */
      const st = getComputedStyle(r1.querySelector('.ec-stem'));
      out.clamped = st.webkitLineClamp === '2' && st.overflow === 'hidden';
      /* 行タップ → その問題へ */
      rows[4].click(); await wait(400);
      out.rowJump = quizOpen() && !sheetOpen() && M.state.session.index === 4 && q('hdr-crumb').hidden === false;
      /* もう一度開いて［解答に戻る］→ 同じ問題 */
      q('btn-exam-list').click(); await wait(300);
      q('exam-confirm-close').click(); await wait(350);
      out.backSame = quizOpen() && M.state.session.index === 4;
      /* ヘッダーの◀戻る → 模試を畳まずに解答画面へ */
      q('btn-exam-list').click(); await wait(300);
      q('btn-back').click(); await wait(350);
      out.headerBack = quizOpen() && M.state.session.mode === 'exam' && typeof M.hooks.afterGrade === 'function'
        && q('hdr-path').textContent !== '解答一覧' && M.state.session.index === 4;
      /* 全問埋めて、一覧の提出（確認なし）で採点 */
      for (let i = 0; i < len; i++) {
        M.examJump(i); await wait(40);
        if (!M.hooks.examSavedFor(M.state.current.question.q_id)) {
          const c = M.state.current; c.selected = [c.atoms[0].original_num]; M.confirmAnswer(); await wait(40);
          if (sheetOpen()) { q('exam-confirm-close').click(); await wait(120); } }
      }
      q('btn-exam-list').click(); await wait(300);
      out.sheetSubmitEnabled = sheetOpen() && q('exam-confirm-submit').disabled === false;
      q('exam-confirm-submit').click();
      for (let i = 0; i < 100; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      out.gradedNoConfirm = !q('modal-exam-result').hidden && q('modal-confirm').hidden;
      return out; }""")
    ok("一覧は画面で開く（解答画面は隠れる）・題は「解答一覧」", r["sheetOpen"] and r["title"] == "解答一覧", r["title"])
    ok("全問ぶんの行。行に問題文がそのまま出る", r["rows"] and r["stemShown"])
    ok("答えと☑を付けた肢の番号が出る", r["ansShown"] and r["marksShown"])
    ok("未回答の行は「未回答」", r["unanswered"])
    ok("問題文は2行で切る", r["clamped"])
    ok("一覧を開いている間も模試は続いている（フックが生きている）", r["hooksAlive"])
    ok("行タップでその問題の解答画面へ（パンくずも戻る）", r["rowJump"])
    ok("［解答に戻る］は同じ問題へ", r["backSame"])
    ok("ヘッダーの◀戻るでも模試を畳まずに解答画面へ", r["headerBack"])
    ok("一覧の提出は確認なしで採点する", r["sheetSubmitEnabled"] and r["gradedNoConfirm"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_sheet_screen" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
