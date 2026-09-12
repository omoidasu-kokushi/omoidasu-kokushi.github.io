# -*- coding: utf-8 -*-
"""test_exam_review_open.py — 模試の復習：予め閉じるのは正解した問だけ。1つしか開かないのは全体解説だけ（V3.17）

【何が起きていたか（利用者の指摘 2026-09-12・実機）】
  「復習時に予め閉じててほしいのは正解だった問題だけです。不正解の問題まで閉じちゃってる。
    1つしか開けない(他に開いているのがあった場合そちらは閉じる)のは『全体解説』だけです。その他はいい」

  V3.09 で「問は1つだけ開く」を入れ、V3.13 で「最初に開くのは最初に間違えた問」にした。
  そのため2問目以降の誤答は毎回見出しを押して開く必要があり、しかも押すと前の問が閉じた。
  復習で読みたいのは**間違えた問**なのに、いちばん読みたいものを1問ずつしか見られない形になっていた。

  V3.09 が1問だけにしたのは描画の重さが理由だった（120問ぶん全部描くと重い）。
  そこは content-visibility で解く（画面の外はブラウザに計算させない）。実測：
    120問・全問誤答＝17,000要素。一覧が出るまで 1,425ms → 221ms（V3.16 の1問だけ開く形は 155ms）

【ここで固定すること】
  ・一覧を描いたとき、**間違えた問は全部開く**。正解した問は閉じたまま（見出しだけ）。全問正解なら1問も開かない
  ・見出しの開閉は**問ごとに独立**。ある問を開いても閉じても、他の問は動かない
  ・畳んだ問は中身を捨てる（評価は保留にあるので、開き直せば押した評価のまま描き直せる）
  ・**全体解説だけ**は1つしか開かない。別の問の全体解説を開くと、前に開いていた全体解説が閉じる
  ・比較表・図解は排他にしない（短いので何個開いていても迷わない）
  ・画面の外の問はブラウザに計算させない（.xr-q の content-visibility:auto）
"""
import os, sys, io, json, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
css = rd("styles.css")
p2 = rd("20260815_main_part2_V1.45.js")

ok("予め開くのは間違えた問だけ（正解した問は開かない）",
   "if (!right) { wrongs.push(i); }" in p2
   and "wrongs.forEach(function (i) { openExamReviewQ(i, { noScroll: true }); });" in p2
   and "firstWrong" not in p2)
ok("開閉は問ごとに独立（他の問を閉じる処理が無い）",
   "rv.openIndex" not in p2
   and "if (li.classList.contains('is-open')) {" in p2
   and "body.innerHTML = ''; body.hidden = true;" in p2)
ok("1つしか開かないのは全体解説だけ（比較表・図解は触らない）",
   "function onExamReviewOverallToggle(det)" in p2
   and "list.querySelectorAll('details.xr-overall[open]')" in p2
   and "if (det.classList.contains('xr-overall')) { onExamReviewOverallToggle(det); }" in p2
   and "xr-table[open]" not in p2 and "xr-fig[open]" not in p2)
ok("画面の外の問はブラウザに計算させない（content-visibility）",
   "content-visibility:auto" in css[css.index(".xr-q{"):css.index(".xr-q{") + 500]
   and "contain-intrinsic-size" in css[css.index(".xr-q{"):css.index(".xr-q{") + 500])

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

SETUP = """async (arg) => {
  const S = window.Storage, K = window.Scheduler, M = window.Main, H = window.Half2, HI = window.Half2Impl;
  const out = {}; const wait = (ms) => new Promise(r => setTimeout(r, ms));
  const q = (id) => document.getElementById(id);
  S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }, { id: 'mock_120', unlocked: true }]);
  K.shouldWarnBeforeExam = async () => ({ warn: false });
  S.getExamHistory = () => Promise.resolve([]);
  await S.setMeta('exam_resume', null);
  await H.startExam(arg.exam, 'real');
  for (let i = 0; i < 240; i++) { if (M.state.session && M.state.session.mode === 'exam'
    && q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
  M.closeModals();
  const ex = HI.state.exam;
  out.len = ex.questions.length;
  const wrongIdx = [];
  ex.questions.forEach((qq, i) => {
    const li = document.querySelector('#paper-list .pq[data-index="' + i + '"]');
    if (!li) { return; }
    const atoms = (qq.atoms || []).slice().sort((a, b) => a.original_num - b.original_num);
    const correct = atoms.filter(a => a.is_correct).map(a => a.original_num);
    const wrong = atoms.filter(a => !a.is_correct).map(a => a.original_num);
    /* arg.mode: 'alt'=1問おきに誤答（問1は誤答） / 'allwrong' / 'allright' */
    const makeWrong = arg.mode === 'allwrong' ? true : (arg.mode === 'allright' ? false : (i % 2 === 0));
    const nums = makeWrong && wrong.length ? wrong.slice(0, correct.length) : correct;
    nums.forEach(n => { const c = li.querySelector('.choice-card[data-num="' + n + '"] .choice-body'); if (c) c.click(); });
    if (!li.querySelector('.choice-card')) { const inp = li.querySelector('.pq-num-input');
      if (inp) { inp.value = makeWrong ? '0' : String(qq.numeric_answer); } }
    if (makeWrong && wrong.length) { wrongIdx.push(i); }
  });
  q('paper-submit').click(); await wait(250);
  q('exam-submit-go').click();
  for (let i = 0; i < 300; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
  q('btn-exam-review').click(); await wait(350);
  const t0 = performance.now();
  q('exam-review-style-button').click();
  for (let i = 0; i < 400; i++) { if (document.querySelectorAll('#exam-review-list .xr-q').length) break; await wait(20); }
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  out.firstPaint_ms = Math.round(performance.now() - t0);
  const items = [...document.querySelectorAll('#exam-review-list .xr-q')];
  out.rows = items.length;
  out.domNodes = document.querySelectorAll('#exam-review-list *').length;
  const isOpen = (li) => li.classList.contains('is-open') && !li.querySelector('.xr-body').hidden;
  const wrongRows = items.filter(li => li.querySelector('.xr-mark.is-wrong'));
  const rightRows = items.filter(li => li.querySelector('.xr-mark.is-correct'));
  out.wrongCount = wrongRows.length; out.rightCount = rightRows.length;
  out.wrongAllOpen = wrongRows.length > 0 && wrongRows.every(isOpen)
    && wrongRows.every(li => li.querySelectorAll('.cx .eval-group').length > 0);
  out.rightAllClosed = rightRows.every(li => !li.classList.contains('is-open')
    && li.querySelector('.xr-body').innerHTML === '' && li.querySelector('.xr-body').hidden === true);
  out.openCount = items.filter(li => li.classList.contains('is-open')).length;
  if (arg.mode !== 'alt') { return out; }

  /* ① 正解した問を開いても、間違えた問は開いたまま */
  const r0 = rightRows[0], w0 = wrongRows[0], w1 = wrongRows[1];
  r0.querySelector('.xr-head').click(); await wait(300);
  out.openRightKeepsWrong = isOpen(r0) && isOpen(w0) && isOpen(w1);
  /* ② 間違えた問を畳む → その問だけ閉じて中身が捨てられる。他はそのまま */
  w0.querySelector('.xr-head').click(); await wait(250);
  out.closeOneOnly = !w0.classList.contains('is-open') && w0.querySelector('.xr-body').innerHTML === ''
    && w0.querySelector('.xr-body').hidden === true && isOpen(w1) && isOpen(r0)
    && w0.querySelector('.xr-head').getAttribute('aria-expanded') === 'false';
  /* ③ 押した評価は保留に残る：開き直すと点いたまま */
  w1.querySelector('.eval-btn[data-eval="normal"]').click(); await wait(250);
  const keepId = w1.querySelector('.cx').getAttribute('data-atom-id');
  w1.querySelector('.xr-head').click(); await wait(200);
  w1.querySelector('.xr-head').click(); await wait(300);
  out.evalKept = isOpen(w1)
    && w1.querySelector('.cx[data-atom-id="' + keepId + '"] .eval-btn.is-active').getAttribute('data-eval') === 'normal';
  /* ④ 全体解説：2つ目を開くと1つ目が閉じる（開いている問の中から2つ選ぶ） */
  const opened = [...document.querySelectorAll('#exam-review-list .xr-q.is-open')];
  const ovs = opened.map(li => li.querySelector('details.xr-overall')).filter(Boolean);
  out.overallSeen = ovs.length;
  if (ovs.length >= 2) {
    ovs[0].querySelector('summary').click(); await wait(120);
    out.overallOpen1 = ovs[0].open;
    ovs[1].querySelector('summary').click(); await wait(160);
    out.overallExclusive = ovs[1].open === true && ovs[0].open === false;
    /* 閉じるだけのときは他を開かない */
    ovs[1].querySelector('summary').click(); await wait(160);
    out.overallCloseQuiet = ovs[1].open === false && ovs[0].open === false;
  }
  /* ⑤ 比較表・図解は排他にしない（2問に持たせて描き直し、両方開けることを見る） */
  const ex2 = HI.state.exam;
  const wi = [...document.querySelectorAll('#exam-review-list .xr-q')]
    .map((li, i) => ({ li, i })).filter(x => x.li.querySelector('.xr-mark.is-wrong')).slice(0, 2).map(x => x.i);
  wi.forEach(i => { ex2.questions[i].comparison_table = '<table><tr><th>項目</th><th>値</th></tr><tr><td>A</td><td>1</td></tr></table>'; });
  H.renderExamReviewList(); await wait(300);
  const tbls = wi.map(i => document.querySelector('#exam-review-list .xr-q[data-index="' + i + '"] details.xr-table')).filter(Boolean);
  out.tableSeen = tbls.length;
  if (tbls.length >= 2) {
    tbls[0].querySelector('summary').click(); await wait(120);
    tbls[1].querySelector('summary').click(); await wait(160);
    out.tableNotExclusive = tbls[0].open === true && tbls[1].open === true;
  }
  wi.forEach(i => { delete ex2.questions[i].comparison_table; });
  q('exam-review-done').click(); await wait(1200);
  return out;
}"""

def boot(br):
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(180000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=240000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=90000)
    pg.wait_for_timeout(600)
    pg.evaluate("() => { const b = document.getElementById('welcome-start'); if (b) b.click(); }")
    pg.wait_for_timeout(400)
    return pg, errs

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg, errs = boot(br)
    a = pg.evaluate(SETUP, {"exam": "mock_30", "mode": "alt"})
    ok("間違えた問は最初から全部開く（評価もそのまま押せる）", a["wrongAllOpen"] and a["wrongCount"] >= 10,
       json.dumps({k: a.get(k) for k in ["wrongCount", "rightCount", "openCount"]}))
    ok("正解した問は閉じたまま（中身は描かない）", a["rightAllClosed"] and a["rightCount"] >= 10 and a["openCount"] == a["wrongCount"],
       json.dumps({k: a.get(k) for k in ["rightCount", "openCount", "wrongCount"]}))
    ok("正解した問を開いても、間違えた問は開いたまま（開閉は独立）", a["openRightKeepsWrong"])
    ok("間違えた問を畳むとその問だけ閉じ、中身が捨てられる", a["closeOneOnly"])
    ok("畳んで開き直しても、押した評価は残っている", a["evalKept"])
    ok("全体解説は2つ目を開くと1つ目が閉じる（1つだけ）", a.get("overallSeen", 0) >= 2 and a.get("overallOpen1") and a.get("overallExclusive"),
       json.dumps({k: a.get(k) for k in ["overallSeen", "overallOpen1", "overallExclusive"]}))
    ok("全体解説を閉じただけのときは、他の全体解説を開かない", a.get("overallCloseQuiet"))
    ok("比較表は排他にしない（2問ぶん同時に開ける）", a.get("tableSeen", 0) >= 2 and a.get("tableNotExclusive"),
       json.dumps({k: a.get(k) for k in ["tableSeen", "tableNotExclusive"]}))
    pg.close()

    pg, errs2 = boot(br)
    b = pg.evaluate(SETUP, {"exam": "mock_30", "mode": "allright"})
    ok("全問正解なら1問も開かない", b["openCount"] == 0 and b["rightCount"] == b["rows"], json.dumps({k: b.get(k) for k in ["openCount", "rows"]}))
    pg.close()

    pg, errs3 = boot(br)
    t0 = time.time()
    c = pg.evaluate(SETUP, {"exam": "mock_120", "mode": "allwrong"})
    ok("120問・全問誤答でも120問ぶん開く", c["rows"] == 120 and c["openCount"] == c["wrongCount"] and c["wrongCount"] >= 110,
       json.dumps({k: c.get(k) for k in ["rows", "openCount", "wrongCount"]}))
    ok("そのとき一覧が出るまで2秒以内（V3.09 が1問だけ開いていた理由をここで埋める）", c["firstPaint_ms"] < 2000,
       "%d ms / %d要素" % (c["firstPaint_ms"], c["domNodes"]))
    pg.close()
    ok("JSエラーが出ていない", not (errs + errs2 + errs3), (errs + errs2 + errs3)[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_review_open" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
