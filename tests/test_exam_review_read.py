# -*- coding: utf-8 -*-
"""test_exam_review_read.py — 模試の復習を読みやすくする3点（V3.13）

【何が起きていたか（利用者の指摘 2026-09-12・実機）】
  ④「復習にて、正解した問題まで開かれてる。正解した問題は問題文と答えの選択肢だけ見せて、残りは閉じといていいよ」
     V3.09 は問1を必ず開いていた。問1が正解だと、読む必要のない問が開いた状態で始まる。
  ⑤「解説を見るを開くと元々あった⇒誤り に加えてさらに⇒誤りと出てきて無駄。解説の中身に「誤り:」は入れないでいい」
     V2.95 で正誤チップを details の外（.cx-verdict）へ出したのに、本文の頭にも「⇒ 誤り：」を足していた。
     開いた瞬間、同じ語が縦に2つ並んでいた。
  ⑥「全体解説のボタンがひっそりしすぎているからもう2段階くらい分かりやすくして」
     V3.09 の全体解説・比較表・図解は「文字が緑なだけ」の行で、押せることが読み取れなかった。

【ここで固定すること】
  ・最初に開くのは**最初に間違えた問**。全問正解なら1問も開かない
  ・正解した問の見出しは「正解 ③ ＋ その肢の本文」（自分の答えは出さない。正解と同じなので）
  ・間違えた問の見出しは今までどおり「あなたの答え ② ／ 正解 ①」
  ・ボタンで開く形の解説は、本文の頭に正誤チップを足さない（左の .cx-verdict が常に出している）
  ・**全部出す形（explain_mode: open）では足す**。あちらは .cx-verdict を持たないので、外すと正誤が画面から消える
  ・全体解説は［解説を見る］と同じ押せる面（44px・面あり・枠2px）。比較表・図解はその1段下（枠線だけ・40px）
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
css = rd("styles.css")
p1, p2 = rd("20260815_main_part1_V1.38.js"), rd("20260815_main_part2_V1.45.js")

ok("ボタンで開く形だけチップを足さない", "prepareAtomExplanation(a.explanation, a, { noChip: true })" in p1
   and "if (mode === 'open') { return prepareAtomExplanation(a.explanation, a); }" in p1
   and "function prepareAtomExplanation(html, atom, opts)" in p1)
ok("最初に開くのは最初に間違えた問", "if (!right && firstWrong < 0) { firstWrong = i; }" in p2
   and "if (firstWrong >= 0) { openExamReviewQ(firstWrong, { noScroll: true }); }" in p2
   and "openExamReviewQ(0, { noScroll: true });" not in p2)
ok("正解した問の見出しは「正解 ③ 本文」", "'正解 <b>' + esc(corNums) + '</b> <span class=\"xr-ans\">'" in p2
   and ".xr-sum.is-right .xr-ans{" in css)
ok("全体解説は押せる面（44px・枠2px）", ".xr-overall > summary{" in css
   and "min-height:44px" in css[css.index(".xr-overall > summary{"):css.index(".xr-overall > summary{") + 400]
   and "border:2px solid var(--accent)" in css[css.index(".xr-overall > summary{"):css.index(".xr-overall > summary{") + 400])
ok("比較表・図解はその1段下（枠線だけ）", ".xr-fig > summary, .xr-table > summary{" in css
   and "min-height:40px" in css[css.index(".xr-fig > summary, .xr-table > summary{"):css.index(".xr-fig > summary, .xr-table > summary{") + 400])

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

def run(pg, all_right):
    """all_right=True なら全問正解で受ける"""
    return pg.evaluate("""async (allRight) => {
      const S = window.Storage, K = window.Scheduler, M = window.Main, H = window.Half2, HI = window.Half2Impl;
      const out = {}; const wait = (ms) => new Promise(r => setTimeout(r, ms));
      const q = (id) => document.getElementById(id);
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      S.getExamHistory = () => Promise.resolve([]);
      await S.setMeta('exam_resume', null);
      await H.startExam('mock_30', 'real');
      for (let i = 0; i < 120; i++) { if (M.state.session && M.state.session.mode === 'exam'
        && q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      M.closeModals();
      const ex = HI.state.exam;
      const len = ex.questions.length;
      out.len = len;
      /* allRight=false なら 問1・問2 を誤答、あとは正解 */
      ex.questions.forEach((qq, i) => {
        const li = document.querySelector('#paper-list .pq[data-index="' + i + '"]');
        const atoms = (qq.atoms || []).slice().sort((a, b) => a.original_num - b.original_num);
        const correct = atoms.filter(a => a.is_correct).map(a => a.original_num);
        const wrong = atoms.filter(a => !a.is_correct).map(a => a.original_num);
        const right = allRight || i >= 2;
        const nums = right ? correct : (wrong.length ? wrong.slice(0, correct.length) : correct);
        nums.forEach(n => { const c = li.querySelector('.choice-card[data-num="' + n + '"] .choice-body'); if (c) c.click(); });
        if (!li.querySelector('.choice-card')) { const inp = li.querySelector('.pq-num-input');
          if (inp) { inp.value = right ? String(qq.numeric_answer) : '0'; } }
      });
      q('paper-submit').click(); await wait(250);
      q('exam-submit-go').click();
      for (let i = 0; i < 120; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      q('btn-exam-review').click(); await wait(350);
      q('exam-review-style-button').click(); await wait(700);
      const items = [...document.querySelectorAll('#exam-review-list .xr-q')];
      out.rows = items.length === len;
      out.openIdx = items.findIndex(li => li.classList.contains('is-open'));
      out.openCount = items.filter(li => li.classList.contains('is-open')).length;
      const rightIdx = items.findIndex(li => li.querySelector('.xr-mark.is-correct'));
      if (rightIdx >= 0) {
        const sum = items[rightIdx].querySelector('.xr-sum');
        const qq = ex.questions[parseInt(items[rightIdx].getAttribute('data-index'), 10)];
        const cor = (qq.atoms || []).filter(a => a.is_correct);
        out.rightSum = sum.classList.contains('is-right') && /^正解/.test(sum.textContent.trim())
          && !/あなたの答え/.test(sum.textContent)
          && cor.every(a => sum.querySelector('.xr-ans').textContent.indexOf(String(a.text || '').trim()) >= 0);
        out.rightClosed = !items[rightIdx].classList.contains('is-open')
          && items[rightIdx].querySelector('.xr-body').hidden === true;
        out.rightStem = items[rightIdx].querySelector('.xr-stem').textContent === (qq.stem || '');
      }
      const wrongIdx = items.findIndex(li => li.querySelector('.xr-mark.is-wrong'));
      if (wrongIdx >= 0) {
        const sum = items[wrongIdx].querySelector('.xr-sum');
        out.wrongSum = /あなたの答え/.test(sum.textContent) && /正解/.test(sum.textContent) && !sum.classList.contains('is-right');
        /* ⑤ 正誤が二重に出ない：開いた肢の本文に「誤り：」「正解：」のチップが無い */
        const li0 = items[wrongIdx];
        if (!li0.classList.contains('is-open')) { li0.querySelector('.xr-head').click(); await wait(400); }
        const det = li0.querySelector('details.cx-exp');
        det.open = true; await wait(120);
        const art = det.closest('.cx');
        out.verdictOutside = art.querySelectorAll('.cx-verdict .vd-chip').length === 1;
        out.noDoubleVerdict = det.querySelector('.explanation-body').querySelectorAll('.vd-chip').length === 0
          && !/^\\s*⇒?\\s*(誤り|正解)[:：]/.test(det.querySelector('.explanation-body').textContent.trim());
        /* ⑥ 全体解説・比較表・図解のボタン */
        const ov = li0.querySelector('details.xr-overall > summary');
        if (ov) {
          const cs = getComputedStyle(ov);
          out.overallBtn = parseFloat(cs.minHeight) >= 44 && parseFloat(cs.borderTopWidth) >= 2
            && cs.backgroundColor !== 'rgba(0, 0, 0, 0)';
        }
      }
      /* 全部出す形では正誤を本文が持つ（外すと画面から消えるので、残っていること） */
      HI.state.exam.review.mode = 'open';
      H.renderExamReviewList(); await wait(400);
      const items2 = [...document.querySelectorAll('#exam-review-list .xr-q')];
      const w2 = items2.find(li => li.classList.contains('is-open')) || items2[0];
      if (!w2.classList.contains('is-open')) { w2.querySelector('.xr-head').click(); await wait(400); }
      out.openModeKeepsChip = w2.querySelectorAll('.cx .explanation-body .vd-chip').length >= 1
        && w2.querySelectorAll('details.cx-exp').length === 0;
      q('exam-review-done').click(); await wait(1200);
      return out; }""", all_right)

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

    a = run(pg, False)
    ok("復習は全問ぶん並ぶ", a["rows"], json.dumps(a, ensure_ascii=False)[:260])
    ok("最初に開くのは最初に間違えた問（1問だけ）", a["openIdx"] == 0 and a["openCount"] == 1, a["openIdx"])
    ok("正解した問は閉じたまま・問題文は出る", a["rightClosed"] and a["rightStem"])
    ok("正解した問の見出しは「正解 ③ ＋ 肢の本文」（自分の答えは出さない）", a["rightSum"])
    ok("間違えた問の見出しは「あなたの答え ／ 正解」のまま", a["wrongSum"])
    ok("正誤は解説の外に1つだけ出る", a["verdictOutside"])
    ok("開いた解説の本文に「誤り：」「正解：」を足さない", a["noDoubleVerdict"])
    ok("全体解説は押せる面になっている（44px・面と枠）", a["overallBtn"])
    ok("全部出す形では本文が正誤を持つ（外さない）", a["openModeKeepsChip"])

    b = run(pg, True)
    ok("全問正解なら1問も開かない", b["openCount"] == 0 and b["openIdx"] == -1, json.dumps({k: b.get(k) for k in ["openIdx", "openCount"]}))
    ok("全問正解でも見出しに正解の肢が出る", b["rightSum"] and b["rightClosed"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_review_read" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
