# -*- coding: utf-8 -*-
"""test_exam_marks.py — 印（☑）だけの一覧（V3.12）

【何が起きていたか（利用者裁定 2026-09-12）】
  ・V3.10 で解答一覧を消したあと、利用者「そしたら、マーク状態だけ一覧で確認できるようにして」。
    120問を上から下まで見返さないと「どこに印を付けたか」が分からなくなっていた。
  ・ただし戻すのは**印だけ**。「チェックを入れた問題も自分で確認することでより本番度が増す」（V3.10 の裁定）ので、
    どの問が未回答かが一目で分かる画面は戻さない。

【ここで固定すること】
  ・問題用紙の帯に［☑ N］。N は印を付けた**問**の数（肢の数ではない）。押すと一覧が開く
  ・一覧に出るのは **問N と、印を付けた肢の番号だけ**。答えた／未回答は出さない
  ・行をタップするとその問へ移る（一覧は閉じる）
  ・印が無いときは「まだ印はありません」
  ・印は DOM が正（collectPaperAnswers・paperStateNow と同じ読み方）。中断から再開しても数が合う
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
ih, css = rd("index.html"), rd("styles.css")
p2 = rd("20260815_main_part2_V1.45.js")

ok("帯に［☑ N］、一覧のモーダルがある", 'id="paper-marks"' in ih and 'id="paper-marks-n"' in ih
   and 'id="modal-exam-marks"' in ih and 'id="exam-mark-list"' in ih
   and ".paper-marks{" in css and ".mk-row{" in css)
ok("一覧に出るのは問番号と肢の番号だけ（答えたかは出さない）", "'<span class=\"mk-no\">問'" in p2
   and "'<span class=\"mk-nums\">☑ '" in p2
   and "未回答" not in p2.split("function openExamMarks")[1][:900])
ok("印は DOM が正（同じ読み方）", "function markedQuestions" in p2
   and p2.split("function markedQuestions")[1][:700].count(".choice-mark[aria-pressed=\"true\"]") == 1)
ok("再開したときも数が合う", "refreshMarkCount();   /* V3.12：再開したときも印の数を合わせる */" in p2)

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
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      S.getExamHistory = () => Promise.resolve([]);
      await H.startExam('mock_30', 'real');
      for (let i = 0; i < 100; i++) { if (q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      M.closeModals();
      const li = (i) => document.querySelector('#paper-list .pq[data-index="' + i + '"]');
      const card = (i, k) => li(i).querySelectorAll('.choice-card')[k];
      /* 印が無いとき */
      out.zero = q('paper-marks-n').textContent === '0' && !q('paper-marks').classList.contains('is-on');
      q('paper-marks').click(); await wait(200);
      out.empty = !q('modal-exam-marks').hidden && /まだ印はありません/.test(q('exam-mark-list').textContent)
        && q('exam-mark-note').textContent === '';
      M.closeModals(); await wait(200);
      /* 問1に2つ、問5に1つ印（問1は肢も塗る＝解答と印は別） */
      card(0, 0).querySelector('.choice-mark').click();
      card(0, 2).querySelector('.choice-mark').click();
      card(4, 1).querySelector('.choice-mark').click();
      card(0, 1).querySelector('.choice-body').click();
      card(7, 0).querySelector('.choice-body').click();   /* 印の無い解答（一覧に出てはいけない） */
      await wait(200);
      out.count = q('paper-marks-n').textContent === '2' && q('paper-marks').classList.contains('is-on');
      q('paper-marks').click(); await wait(250);
      const rows = [...document.querySelectorAll('#exam-mark-list .mk-row')];
      out.rows = rows.length === 2
        && rows[0].querySelector('.mk-no').textContent === '問1'
        && rows[1].querySelector('.mk-no').textContent === '問5';
      const n0 = parseInt(card(0, 0).getAttribute('data-num'), 10), n2 = parseInt(card(0, 2).getAttribute('data-num'), 10);
      const circ = '①②③④⑤⑥⑦⑧⑨⑩';
      out.nums = rows[0].querySelector('.mk-nums').textContent === '☑ ' + circ[n0 - 1] + circ[n2 - 1];
      out.noAnswerInfo = !/未回答|答え/.test(q('exam-mark-list').textContent)
        && !/問8/.test(q('exam-mark-list').textContent);
      /* 行タップでその問へ（一覧は閉じる） */
      rows[1].click(); await wait(500);
      out.jumped = q('modal-exam-marks').hidden && q('screen-exam-paper').classList.contains('is-active');
      /* 印を外すと一覧から消える */
      card(0, 0).querySelector('.choice-mark').click();
      card(0, 2).querySelector('.choice-mark').click();
      await wait(150);
      out.afterOff = q('paper-marks-n').textContent === '1';
      q('paper-marks').click(); await wait(250);
      out.rowsAfter = document.querySelectorAll('#exam-mark-list .mk-row').length === 1
        && document.querySelector('#exam-mark-list .mk-no').textContent === '問5';
      M.closeModals(); await wait(200);
      /* 中断 → 再開しても数が合う */
      await wait(700);
      q('btn-home').click(); await wait(200); q('confirm-go').click(); await wait(500);
      await H.resumeExam();
      for (let i = 0; i < 100; i++) { if (q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      await wait(300);
      out.afterResume = q('paper-marks-n').textContent === '1'
        && card(4, 1).querySelector('.choice-mark').getAttribute('aria-pressed') === 'true';
      q('paper-marks').click(); await wait(250);
      out.rowsResume = document.querySelectorAll('#exam-mark-list .mk-row').length === 1;
      M.closeModals();
      return out; }""")
    ok("印が無いときは 0・一覧は「まだ印はありません」", r["zero"] and r["empty"], json.dumps(r, ensure_ascii=False)[:240])
    ok("数えるのは問の数（1問に2つ付けても1）", r["count"])
    ok("一覧は印を付けた問だけ（順番どおり）", r["rows"])
    ok("印を付けた肢の番号が出る", r["nums"])
    ok("答えた／未回答の情報は出さない", r["noAnswerInfo"])
    ok("行タップでその問へ移り、一覧は閉じる", r["jumped"])
    ok("印を外すと数も一覧も減る", r["afterOff"] and r["rowsAfter"])
    ok("中断から再開しても数と印が合う", r["afterResume"] and r["rowsResume"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_marks" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
