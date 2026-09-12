# -*- coding: utf-8 -*-
"""test_exam_nav_submit.py — 模試の解答画面：一覧と提出を分ける／提出は全問解答まで非アクティブ／［？］は小さく（V3.03）

【何が起きていたか（利用者裁定 2026-09-12）】
  ・V2.17 のナビは [前へ][一覧・提出][次へ] の1段で、一覧と提出が同じボタンだった。末尾の［次へ］は「一覧へ」に化けた。
    → [前へ][次へ]／[解答一覧]／[提出する] の3段。**提出は全問解答し終わるまで非アクティブ**。
      押せない理由をボタンに書く（「提出する（あと3問）」）
  ・V2.23 の［？ 右の☐チェックとは］は大きく、初回は説明が開いた状態だった。
    → ☐列の上の小さい［？］だけ。既定は閉じる。押すと説明が出る

【ここで固定すること】
  ・先頭で前へ無効／末尾で次へ無効（「一覧へ」にしない）／解答一覧は別ボタン
  ・提出は未回答がある間は disabled で「あと◯問」。全問答えると「提出する」で押せる
  ・解答画面の［提出する］は1度だけ確認する（取り消せないので）。一覧の［提出する］は確認しない（一覧が確認）
  ・末尾の解答を確定すると解答一覧が開く（未回答の確認と提出はそこで）
  ・［？］は小さい印で既定は閉じる。押すと開き、もう一度押すと閉じる。2問目以降も残る
  ・模試を畳んだら新しいフック（examUnanswered／examSubmit）も外れる
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

ok("ナビは3段（前へ・次へ／解答一覧／提出する）", 'class="exam-nav-row"' in ih and 'id="btn-exam-list">解答一覧<' in ih
   and 'id="btn-exam-submit" disabled>提出する<' in ih and "一覧・提出" not in ih)
ok("提出の状態は refreshExamNav が決める（あと◯問）", "function refreshExamNav" in p1 and "'提出する（あと' + un + '問）'" in p1)
ok("末尾で次へは無効（一覧へに化けない）", "nb.disabled = s.index >= s.questions.length - 1" in p1 and "'一覧へ ▶'" not in p1)
ok("未回答の数は answers から数える（hooks.examUnanswered）", "function examUnansweredCount" in p2 and "M.hooks.examUnanswered = function" in p2)
ok("解答画面の提出は1度だけ確認する", "function submitExamFromNav" in p2 and "title: '全解答を提出しますか'" in p2)
ok("畳むときに新しいフックも外す", p2.count("M.hooks.examUnanswered = null") >= 2 and p2.count("M.hooks.examSubmit = null") >= 2)
ok("［？］は小さい印・既定は閉じる", "aria-label=\"右の☐チェックの説明\">?</button>" in p1 and "&& false;   /* V3.03" in p1
   and ".ground-help-btn{\n  width:22px; height:22px;" in css)
ok("提出ボタンの見た目（accent・非アクティブは薄く）", ".exam-nav-btn.is-submit{" in css and ".exam-nav-btn.is-submit:disabled{" in css)
ok("ナビの文字は中央・［？］の説明は1文に流れる（V3.08）", "text-align:center;   /* V3.08" in css and "display:block;   /* V3.08" in css)

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
      const origU = S.getUnlockState;
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      const origW = K.shouldWarnBeforeExam;
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      await H.startExam('mock_30', 'real');
      S.getUnlockState = origU; K.shouldWarnBeforeExam = origW;
      for (let i = 0; i < 100; i++) { if (M.state.session && M.state.session.mode === 'exam' && M.state.current) break; await wait(50); }
      M.closeModals();
      const len = M.state.session.questions.length;
      out.len = len;
      const q = (id) => document.getElementById(id);
      const nav = q('exam-nav');
      out.navVisible = !nav.hidden;
      out.prevDisabled = q('btn-exam-prev').disabled === true;
      out.nextEnabled = q('btn-exam-next').disabled === false;
      out.submitDisabled = q('btn-exam-submit').disabled === true;
      out.submitText0 = q('btn-exam-submit').textContent;
      /* ［？］：小さい印・既定は閉じる・押すと開く */
      const hb = document.querySelector('.ground-help-btn'), hint = document.querySelector('.ground-hint');
      out.helpSmall = !!hb && hb.textContent.trim() === '?';
      out.helpClosedByDefault = !!hint && hint.hidden === true;
      hb.click(); out.helpOpens = hint.hidden === false;
      hb.click(); out.helpCloses = hint.hidden === true;

      const answer = () => { const cur = M.state.current; cur.selected = [cur.atoms[0].original_num]; M.confirmAnswer(); };
      answer(); await wait(300);
      out.movedTo2 = M.state.session.index === 1;
      out.submitText1 = q('btn-exam-submit').textContent;
      out.helpPersists = !!document.querySelector('.ground-help-btn') && document.querySelector('.ground-hint').hidden === true;
      /* 末尾へ：次へは無効 */
      M.examJump(len - 1); await wait(200);
      out.nextDisabledAtEnd = q('btn-exam-next').disabled === true && q('btn-exam-next').textContent.indexOf('一覧') < 0;
      /* 解答一覧は別ボタンで開く（未回答が出る）*/
      q('btn-exam-list').click(); await wait(300);
      const sheetOpen = () => q('screen-exam-sheet').classList.contains('is-active');   /* V3.04：一覧は画面 */
      out.listOpens = sheetOpen() && document.querySelectorAll('#exam-confirm-list .ec-row.is-un').length === len - 1;
      out.listSubmitDisabled = q('exam-confirm-submit').disabled === true && /未回答/.test(q('exam-confirm-submit').textContent);
      q('exam-confirm-close').click(); await wait(300);
      out.backToQuiz = q('screen-quiz').classList.contains('is-active') && M.state.session.index === len - 1;
      /* 提出を押しても（無効だが）採点されない */
      q('btn-exam-submit').click(); await wait(300);
      out.noGradeWhileUnanswered = q('modal-exam-result').hidden && !!M.hooks.afterGrade;
      /* 末尾の解答を確定すると一覧が開く */
      answer(); await wait(300);
      out.listAfterLast = sheetOpen();
      q('exam-confirm-close').click(); await wait(300);
      /* 全問埋める */
      for (let i = 0; i < len; i++) {
        M.examJump(i); await wait(40);
        if (!M.hooks.examSavedFor(M.state.current.question.q_id)) { answer(); await wait(40);
          if (sheetOpen()) { q('exam-confirm-close').click(); await wait(120); } }
      }
      M.examJump(2); await wait(150);
      out.submitEnabledWhenFull = q('btn-exam-submit').disabled === false && q('btn-exam-submit').textContent === '提出する';
      /* 解答画面の提出 → 確認 → 提出 */
      q('btn-exam-submit').click(); await wait(300);
      out.confirmAsked = !q('modal-confirm').hidden && /提出/.test(q('confirm-title').textContent);
      q('confirm-go').click();
      for (let i = 0; i < 100; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      out.resultOpen = !q('modal-exam-result').hidden;
      out.hooksCleared = !M.hooks.afterGrade && !M.hooks.examSavedFor && !M.hooks.examUnanswered && !M.hooks.examSubmit;
      return out; }""")
    ok("模試開始：ナビが出て、先頭は前へ無効・次へ有効", r["navVisible"] and r["prevDisabled"] and r["nextEnabled"], json.dumps(r, ensure_ascii=False))
    ok("提出は最初は非アクティブで「あと◯問」", r["submitDisabled"] and ("あと%d問" % r["len"]) in r["submitText0"], r["submitText0"])
    ok("［？］は小さい印・既定は閉じる・押すと開閉", r["helpSmall"] and r["helpClosedByDefault"] and r["helpOpens"] and r["helpCloses"], r)
    ok("1問答えると残りが1つ減る・［？］は2問目も残り閉じている", r["movedTo2"] and ("あと%d問" % (r["len"] - 1)) in r["submitText1"] and r["helpPersists"], r["submitText1"])
    ok("末尾では次へが無効（「一覧へ」に化けない）", r["nextDisabledAtEnd"])
    ok("解答一覧は別ボタン（画面）。未回答が出て、一覧の提出も非アクティブ", r["listOpens"] and r["listSubmitDisabled"])
    ok("一覧から「解答に戻る」で同じ問題の解答画面へ", r["backToQuiz"])
    ok("未回答のまま提出を押しても採点されない", r["noGradeWhileUnanswered"])
    ok("末尾の解答を確定すると解答一覧が開く", r["listAfterLast"])
    ok("全問答えると提出が押せる（文言は「提出する」）", r["submitEnabledWhenFull"])
    ok("解答画面の提出は1度確認してから採点する", r["confirmAsked"] and r["resultOpen"])
    ok("採点後は新しいフックも外れている", r["hooksCleared"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_nav_submit" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
