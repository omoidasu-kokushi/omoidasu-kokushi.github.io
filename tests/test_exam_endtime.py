# -*- coding: utf-8 -*-
"""test_exam_endtime.py — 残り時間のカウントダウンをやめ、終了時刻の固定表記にする（V3.15）

【何が起きていたか（利用者裁定 2026-09-12）】
  V3.10 は問題用紙の帯に「残り 39:58」を出し、1秒ごとに書き換えていた。
  動く数字は視界の端でも動きを拾うので、問題を読んでいるあいだ中ずっと気が散る。
  利用者「残り時間のカウントダウンはしないで。現在時刻をみて、終了○○時○○分 とだけ固定表記しておいて。
        中断・再開した際はその分差し引いて新たに終了時間を表記させて」

【ここで固定すること】
  ・帯に出るのは「終了 13:45」だけ（秒は出さない＝動いて見える）
  ・数字は動かない。1秒ごとの tick は続くが、書き換えるのは終了時刻が変わったときだけ
  ・中断→再開すると、終了時刻は**再開した分だけ繰り下がる**（deadline = 再開時刻 + 残り時間・V3.11）
  ・5分前の知らせと0分の自動提出は今までどおり（時計そのものは止めない）
  ・残り5分を切ると赤くなる（数字は動かないまま）
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
ih, css, p2 = rd("index.html"), rd("styles.css"), rd("20260815_main_part2_V1.45.js")

ok("帯の初期表示が終了時刻", 'id="paper-timer">終了 --:--<' in ih and '残り --:--' not in ih)
ok("終了時刻は時と分だけ（秒を出さない）", "function fmtEndClock" in p2
   and "':' + ('0' + d.getMinutes()).slice(-2);" in p2
   and "getSeconds" not in p2)
ok("書き換えるのは終了時刻が変わったときだけ", "function renderPaperEnd" in p2
   and "if (ex.shownDeadline !== ex.deadline)" in p2)
ok("カウントダウンの文字列はもう作らない", "'残り ' + fmtRemain(left)" not in p2)
ok("時計そのものは止めない（5分前と自動提出）", "if (!ex.warned && left <= EXAM_WARN_MS)" in p2
   and "if (left <= 0) { submitPaper({ timeUp: true }); }" in p2)
ok("中断の帯では残り時間のまま（duration であって時刻ではない）", "'／残り ' + fmtRemain(rs.remain_ms || 0)" in p2)

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
      const pad = (n) => ('0' + n).slice(-2);
      const clockOf = (ms) => { const d = new Date(ms); return pad(d.getHours()) + ':' + pad(d.getMinutes()); };
      await H.startExam('mock_30', 'real');
      for (let i = 0; i < 120; i++) { if (q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      M.closeModals();
      const ex = HI.state.exam;
      /* 40分の模試なので、終了は「いま＋40分」 */
      out.text0 = q('paper-timer').textContent;
      out.isEnd = out.text0 === '終了 ' + clockOf(ex.deadline);
      out.matchesLimit = Math.abs((ex.deadline - Date.now()) - 40 * 60000) < 5000;
      out.noSeconds = !/\\d+:\\d\\d:\\d\\d/.test(out.text0) && !/残り/.test(out.text0);
      /* 数字が動かない：2秒待っても同じ文字 */
      await wait(2100);
      out.stable = q('paper-timer').textContent === out.text0;
      /* 塗って中断 → 3分ぶん時間が過ぎたことにして再開 → 終了時刻が繰り下がる */
      document.querySelector('#paper-list .pq[data-index="0"] .choice-body').click();
      await wait(900);
      ex.deadline = Date.now() + 30 * 60000;   /* 残り30分の状態にする */
      H.renderPaperEnd();
      const endBefore = q('paper-timer').textContent;
      q('btn-home').click(); await wait(250); q('confirm-go').click(); await wait(600);
      /* 中断中に3分たったことにする（控えの残り時間は変えない＝時計は止まっている） */
      const rs = await S.getMeta('exam_resume', null);
      out.savedRemain = Math.round((rs.remain_ms || 0) / 60000);
      const t0 = Date.now();
      await H.resumeExam();
      for (let i = 0; i < 120; i++) { if (q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      await wait(300);
      const ex2 = HI.state.exam;
      out.endAfter = q('paper-timer').textContent;
      out.pushedBack = out.endAfter === '終了 ' + clockOf(ex2.deadline)
        && Math.abs((ex2.deadline - t0) - (rs.remain_ms || 0)) < 4000;
      out.changedFromBefore = (ex2.deadline > ex.deadline - 1000);   /* 中断のぶん後ろへ */
      /* 5分前：赤くなるが数字は動かない */
      ex2.deadline = Date.now() + 4 * 60000;
      H.tickPaper();
      const t4 = q('paper-timer').textContent;
      out.warnRed = q('paper-timer').classList.contains('is-warn') && t4 === '終了 ' + clockOf(ex2.deadline);
      await wait(1200);
      H.tickPaper();
      out.stillStable = q('paper-timer').textContent === t4;
      /* 0分で自動提出は生きている */
      ex2.deadline = Date.now() - 10;
      H.tickPaper();
      for (let i = 0; i < 120; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      out.autoSubmit = !q('modal-exam-result').hidden && ex2.submitted === true;
      return out; }""")
    ok("帯は「終了 13:45」（残り時間ではない・秒も出さない）", r["isEnd"] and r["noSeconds"], r["text0"])
    ok("終了時刻は制限時間ぶん先（30問＝40分）", r["matchesLimit"])
    ok("数字が動かない（2秒待っても同じ）", r["stable"])
    ok("中断すると残り時間が控えられる", r["savedRemain"] == 30, r["savedRemain"])
    ok("再開すると終了時刻が繰り下がる（再開時刻＋残り時間）", r["pushedBack"] and r["changedFromBefore"], r["endAfter"])
    ok("残り5分で赤くなる。数字は動かないまま", r["warnRed"] and r["stillStable"])
    ok("0分の自動提出は生きている", r["autoSubmit"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_endtime" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
