# -*- coding: utf-8 -*-
"""test_exam_review_back.py — ［見直す］で問1まで戻す（V3.16）

【何が起きていたか（利用者裁定 2026-09-12）】
  ［提出する］は問題用紙の最下部にしか無い（V3.10）。だから押した時点で必ず最後の問のところにいる。
  そこで覆いを畳むだけだと、見直しは**最後の問から上へ**という不自然な向きになる。
  利用者「見直す押したら問1にスクロールアップして」

【ここで固定すること】
  ・［見直す］は覆いを畳んで、**問1まで戻す**（提出はされない）
  ・飛んだ先は固定ヘッダーと帯の下に潜らない（.pq の scroll-margin-top）
  ・［これで提出］は今までどおり採点する（戻らない）
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
ih, css, p2 = rd("index.html"), rd("styles.css"), rd("20260815_main_part2_V1.45.js")

ok("［見直す］に id が付いた（data-close は残す）", 'id="exam-submit-back" data-close>見直す<' in ih)
ok("押すと問1へ戻す", "on($('#exam-submit-back'), 'click', function () { jumpToPaperQuestion(0); });" in p2)
ok("飛んだ先が固定ヘッダーの下に潜らない", "scroll-margin-top:104px" in css[css.index(".pq{"):css.index(".pq{") + 200])

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
      await S.setMeta('exam_resume', null);
      await H.startExam('mock_30', 'real');
      for (let i = 0; i < 120; i++) { if (q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      M.closeModals(); await wait(300);
      /* いちばん下（提出する）まで送る */
      q('paper-submit').scrollIntoView({ block: 'end' });
      await wait(400);
      out.atBottom = window.scrollY > 500;
      out.scrollBefore = window.scrollY;
      q('paper-submit').click(); await wait(250);
      out.askShown = !q('modal-exam-submit').hidden;
      /* ［見直す］→ 覆いが畳まれて問1へ戻る */
      q('exam-submit-back').click();
      await wait(900);
      out.closed = q('modal-exam-submit').hidden;
      out.notSubmitted = HI.state.exam.submitted !== true && q('modal-exam-result').hidden
        && q('screen-exam-paper').classList.contains('is-active');
      out.scrollAfter = window.scrollY;
      out.wentUp = out.scrollAfter < 200 && out.scrollAfter < out.scrollBefore - 400;
      /* 問1が固定ヘッダーの下に潜っていない */
      const li1 = document.querySelector('#paper-list .pq[data-index="0"]');
      const top = li1.getBoundingClientRect().top;
      const hdr = q('app-header').getBoundingClientRect().bottom;
      out.q1Visible = top >= 0 && top >= hdr - 2;
      out.q1Top = Math.round(top); out.hdrBottom = Math.round(hdr);
      /* ［これで提出］は今までどおり採点する */
      q('paper-submit').scrollIntoView({ block: 'end' }); await wait(300);
      q('paper-submit').click(); await wait(250);
      q('exam-submit-go').click();
      for (let i = 0; i < 120; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      out.graded = !q('modal-exam-result').hidden && HI.state.exam.submitted === true;
      return out; }""")
    ok("最下部の［提出する］から確認が出る", r["atBottom"] and r["askShown"])
    ok("［見直す］で覆いが畳まれる（提出されない）", r["closed"] and r["notSubmitted"])
    ok("問1まで戻る（上へスクロールする）", r["wentUp"], json.dumps({"before": r["scrollBefore"], "after": r["scrollAfter"]}))
    ok("問1が固定ヘッダーの下に潜らない", r["q1Visible"], json.dumps({"q1Top": r["q1Top"], "hdrBottom": r["hdrBottom"]}))
    ok("［これで提出］は今までどおり採点する", r["graded"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_review_back" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
