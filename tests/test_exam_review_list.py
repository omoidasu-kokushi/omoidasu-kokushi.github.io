# -*- coding: utf-8 -*-
"""test_exam_review_list.py — 模試の復習＝全画面の一覧。入口の2択。評価は押した瞬間に保留、離れたら記録（V3.06）
                             ＋ 問は1つだけ開く・比較表と図解はタップで表示（V3.09）

【何が起きていたか（利用者裁定 2026-09-12）】
  ・V2.18 の復習はモーダルの折りたたみ一覧（誤答は展開・正答は畳む）で、評価は変えられず、通常の解説画面とは別物だった。
    利用者「画面推移して全画面に。いきなり1つ1つの解説ではなく、他のモードの解説画面と同じ感じに。
            じゃないと悩んだもう1つが正解だった悔しさが出ない。復習するを選んだ後に二択（1肢ずつ／全肢）」
    「復習画面では次へボタンなど出さない。一覧でスクロールしていく感じ。重くなるなら30問ずつに分けて」

【ここで固定すること】
  ・［復習を始める］→ 2択のモーダル → 全画面（#screen-exam-review）。問1から順に全問。次へボタンは無い
  ・1問＝○×・問題文・「あなたの答え／正解」・肢ごとのブロック（.cx：番号・本文・あなたの答え・☑・⇒正誤・解説・評価4つ）・全体解説
  ・1肢ずつ＝解説は「解説を見る」で開く（details）／全肢＝最初から開いている。設定（explain_mode）は変えない
  ・評価は既定（保留）が点いている。押すと保留が変わる。**この時点では記録しない**
  ・画面を離れる（◀戻る／ホーム／［評価を記録して終える］）と保留が記録され、変えた評価で入る。保留は空
  ・（V3.06 の30問ずつのページは V3.09 で撤去）問は畳んだ見出しで並ぶ。同じ見出しをもう一度押すと畳む。
    押した評価は保留にあるので、開き直しても残っている
  ・**V3.17：開閉は問ごとに独立**（V3.09 の「開くのは1問だけ」は撤回）。予め開くのは間違えた問（→ test_exam_review_open.py）
  ・比較表・図解はタップで表示（details）。図解は開いた瞬間に1回だけ描く（自分の枠へ・renderMermaidInto）
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

ok("復習は画面。2択のモーダルがある。旧モーダル（V2.18）は無い", 'id="screen-exam-review" class="screen" data-screen="exam_review"' in ih
   and 'id="exam-review-style-button"' in ih and 'id="exam-review-style-open"' in ih and 'id="modal-exam-review"' not in ih)
sec = ih[ih.index('id="screen-exam-review"'):ih.index('id="screen-exam"')]
ok("復習の画面に「次へ」は無い（終えるボタンだけ）", "btn-next" not in sec and 'id="exam-review-done"' in sec and "次へ" not in sec)
ok("問は見出しで開閉する（ページの帯は撤去）", "function openExamReviewQ" in p2 and "var REVIEW_PAGE = 30;" not in p2 and 'id="exam-review-pager"' not in ih
   and "body.innerHTML = ''; body.hidden = true;" in p2)
ok("開いた問へ寄せるとき固定ヘッダーの下に潜らない（scroll-margin-top）", "scroll-margin-top:96px" in css[css.index(".xr-q{"):css.index(".xr-q{")+200])
ok("一緒に覚えたい！・図解はタップで表示。図解は自分の枠へ描く", "'<details class=\"xr-table\"><summary>一緒に覚えたい！</summary>" in p2
   and "'<details class=\"xr-fig\"><summary>図解を見る</summary>" in p2 and "function renderMermaidInto" in p1 and "M.renderMermaidInto(frame, q.mermaid_code)" in p2)
ok("評価は押した瞬間に保留へ（次へ無し）", "function onExamReviewEval" in p2 and "updateExamPending(qid, patch)" in p2)
ok("画面を離れたら記録（beforeLeave）", "hooks.beforeLeave(state.screen, screen)" in p1 and "M.hooks.beforeLeave = function (from, to) {" in p2
   and "finishExamReview(false);" in p2)
ok("解説の見せ方は2択で決め、設定は変えない（renderAtomBody の modeOverride）", "function renderAtomBody(a, modeOverride)" in p1
   and "M.renderAtomBody(at, rv.mode)" in p2 and "setMeta('explain_mode'" not in p2[p2.index("function startExamReview"):p2.index("function finishExamReview")])
ok("ブロックは通常の解説画面と同じ部品（.cx／.eval-group／あなたの答え）", "'<article class=\"cx '" in p2[p2.index("function examReviewBodyHtml"):] and "cx-pick\">あなたの答え" in p2[p2.index("function examReviewBodyHtml"):])

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
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      S.getExamHistory = () => Promise.resolve([]);
      await H.startExam('mock_30', 'real');
      for (let i = 0; i < 100; i++) { if (M.state.session && M.state.session.mode === 'exam'
        && q('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      M.closeModals();
      const modeBefore = await S.getMeta('explain_mode', null);
      const ex = window.Half2Impl.state.exam;
      const len = ex.questions.length;
      /* V3.10：模試は1枚の問題用紙。肢をタップして塗り、最下部の［提出する］で出す */
      const plan = [];
      ex.questions.forEach((qq, i) => {
        const li = document.querySelector('#paper-list .pq[data-index="' + i + '"]');
        const atoms = (qq.atoms || []).slice().sort((a, b) => a.original_num - b.original_num);
        const correct = atoms.filter(a => a.is_correct).map(a => a.original_num);
        const wrong = atoms.filter(a => !a.is_correct).map(a => a.original_num);
        const right = (i % 2 === 1);   /* 問1は誤答 */
        const picked = right ? correct.slice() : [wrong[0]];
        picked.forEach(n => li.querySelector('.choice-card[data-num="' + n + '"] .choice-body').click());
        const markAtom = atoms[1] || atoms[0];
        if (i === 0) { li.querySelector('.choice-card[data-atom-id="' + markAtom.atom_id + '"] .choice-mark').click(); }
        plan.push({ qid: qq.q_id, right, picked, marked: i === 0 ? markAtom.atom_id : null, atoms: atoms.map(a => a.atom_id) });
      });
      q('paper-submit').click(); await wait(250);
      q('exam-submit-go').click();
      for (let i = 0; i < 100; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      /* 復習を始める → 2択 */
      q('btn-exam-review').click(); await wait(300);
      out.styleModal = !q('modal-exam-review-style').hidden;
      q('exam-review-style-button').click(); await wait(600);
      const scr = q('screen-exam-review');
      out.screenOpen = scr.classList.contains('is-active') && q('modal-exam-result').hidden && q('modal-exam-review-style').hidden;
      out.title = q('hdr-path').textContent;
      const items = document.querySelectorAll('#exam-review-list .xr-q');
      out.count = items.length;
      out.noNext = !scr.querySelector('#btn-next') && !scr.textContent.includes('次へ');
      out.noPager = !q('exam-review-pager');
      const b1 = items[0];
      /* V3.17：予め開くのは**間違えた問だけ**（問1は誤答・偶数番が誤答）。正解した問は見出しだけ */
      out.q1Open = b1.classList.contains('is-open') && !b1.querySelector('.xr-body').hidden
        && Array.from(items).every(li => {
             const wrong = !!li.querySelector('.xr-mark.is-wrong');
             return wrong ? li.classList.contains('is-open')
                          : (!li.classList.contains('is-open') && li.querySelector('.xr-body').innerHTML === '');
           });
      out.q1Wrong = b1.querySelector('.xr-mark').classList.contains('is-wrong') && /あなたの答え/.test(b1.querySelector('.xr-sum').textContent);
      out.q1Stem = b1.querySelector('.xr-stem').textContent === H.st.exam.questions[0].stem;
      out.q1Picked = !!b1.querySelector('.cx.is-picked .cx-pick');
      out.q1Mark = !!b1.querySelector('.cx[data-atom-id="' + plan[0].marked + '"] .cx-mark');
      out.q1Blocks = b1.querySelectorAll('.cx').length === plan[0].atoms.length;
      out.q1Verdict = b1.querySelectorAll('.cx .vd-chip').length >= plan[0].atoms.length;
      out.buttonMode = b1.querySelectorAll('details.cx-exp').length > 0;
      /* 評価：既定は誤答＝全肢 難 が点いている */
      out.q1DefaultHard = Array.from(b1.querySelectorAll('.cx .eval-group')).every(g => g.querySelector('.eval-btn.is-active').getAttribute('data-eval') === 'hard');
      /* 押す → 保留が変わる。記録はまだ */
      const target = b1.querySelector('.cx'); const targetId = target.getAttribute('data-atom-id');
      target.querySelector('.eval-btn[data-eval="normal"]').click(); await wait(300);
      out.activeMoved = target.querySelector('.eval-btn.is-active').getAttribute('data-eval') === 'normal';
      const pend = await S.getMeta('exam_pending', null);
      const it = pend.items.filter(x => x.q_id === plan[0].qid)[0];
      out.pendingChanged = it.atoms.filter(x => x.atom_id === targetId)[0].eval === 'normal';
      out.notRecordedYet = (await S.getAllLogs()).filter(l => l.mode === 'exam').length === 0;
      out.settingUnchanged = (await S.getMeta('explain_mode', null)) === modeBefore;
      /* V3.17：問2（正解・閉じている）を開いても問1は開いたまま。問2（正解）の既定は 普 */
      items[1].querySelector('.xr-head').click(); await wait(300);
      const b2 = items[1];
      out.accordion = b2.classList.contains('is-open') && b1.classList.contains('is-open')
        && !b1.querySelector('.xr-body').hidden
        && b1.querySelector('.xr-head').getAttribute('aria-expanded') === 'true';
      out.q2DefaultNormal = Array.from(b2.querySelectorAll('.cx .eval-group')).every(g => g.querySelector('.eval-btn.is-active').getAttribute('data-eval') === 'normal');
      /* 同じ見出しをもう一度押すと畳む（他の問は動かない） */
      b1.querySelector('.xr-head').click(); await wait(250);
      out.toggleClose = !b1.classList.contains('is-open') && b1.querySelector('.xr-body').hidden
        && b2.classList.contains('is-open');
      /* 問1を開き直す → 押した評価は残っている（保留から描く） */
      b1.querySelector('.xr-head').click(); await wait(300);
      out.activeKeptAfterRerender = b1.classList.contains('is-open')
        && b1.querySelector('.cx[data-atom-id="' + targetId + '"] .eval-btn.is-active').getAttribute('data-eval') === 'normal';
      /* 全肢表示：描き直すと解説が最初から開いている（問1が開く） */
      H.st.exam.review.mode = 'open'; H.renderExamReviewList(); await wait(200);
      const b1o = document.querySelectorAll('#exam-review-list .xr-q')[0];
      out.openMode = b1o.classList.contains('is-open') && b1o.querySelectorAll('details.cx-exp').length === 0 && b1o.querySelectorAll('.cx .explanation-body .vd-chip').length >= 1;
      /* 比較表・図解：問1に持たせて描き直す → タップで出る。図解は開いた瞬間に描く */
      H.st.exam.questions[0].comparison_table = '<table><tr><th>項目</th><th>値</th></tr><tr><td>A</td><td>1</td></tr></table>';
      H.st.exam.questions[0].mermaid_code = 'flowchart LR\\n  A[はじめ] --> B[おわり]';
      H.renderExamReviewList(); await wait(200);
      const b1t = document.querySelectorAll('#exam-review-list .xr-q')[0];
      const tbl = b1t.querySelector('details.xr-table'), fig = b1t.querySelector('details.xr-fig');
      out.tableFig = !!tbl && !!fig && !tbl.open && !fig.open && !!tbl.querySelector('table');
      out.figNotDrawnYet = fig.querySelector('.xr-mmd').getAttribute('data-drawn') === '0' && fig.querySelector('.xr-mmd').innerHTML === '';
      fig.open = true; await wait(50);
      for (let i = 0; i < 100; i++) { if (fig.querySelector('.xr-mmd').innerHTML.length > 20) break; await wait(100); }
      const mmd = fig.querySelector('.xr-mmd');
      out.figDrawn = mmd.getAttribute('data-drawn') === '1' && (mmd.querySelector('svg') !== null || /はじめ|図解/.test(mmd.textContent));
      out.figSvg = mmd.querySelector('svg') !== null;
      delete H.st.exam.questions[0].comparison_table; delete H.st.exam.questions[0].mermaid_code;
      /* ◀戻る → 記録される */
      q('btn-back').click();
      for (let i = 0; i < 100; i++) { if (!(await S.getMeta('exam_pending', null))) break; await wait(100); }
      out.leftToHome = q('screen-home').classList.contains('is-active');
      out.pendingCleared = !(await S.getMeta('exam_pending', null));
      const logs = (await S.getAllLogs()).filter(l => l.mode === 'exam');
      out.recorded = logs.length >= 30;
      const lt = logs.filter(l => l.atom_id === targetId)[0];
      out.changedRecorded = !!lt && lt.eval === 'normal';
      const other = logs.filter(l => plan[0].atoms.indexOf(l.atom_id) >= 0 && l.atom_id !== targetId);
      out.othersHard = other.length > 0 && other.every(l => l.eval === 'hard');
      out.hookCleared = !M.hooks.beforeLeave;
      return out; }""")
    ok("［復習を始める］→ 2択のモーダル → 全画面の復習（題は「模試の復習」）", r["styleModal"] and r["screenOpen"] and r["title"] == "模試の復習", r["title"])
    ok("全問が並び、次へは無い。ページの帯も無い", r["count"] == 30 and r["noNext"] and r["noPager"], r["count"])
    ok("間違えた問は最初から開き、正解した問は見出しだけ（中身は空）", r["q1Open"])
    ok("問1（誤答）：×・問題文・あなたの答え・☑・肢の数だけブロック・⇒正誤", r["q1Wrong"] and r["q1Stem"] and r["q1Picked"] and r["q1Mark"] and r["q1Blocks"] and r["q1Verdict"], r)
    ok("1肢ずつ：解説は「解説を見る」で開く", r["buttonMode"])
    ok("評価の既定が点いている（誤答は難）", r["q1DefaultHard"])
    ok("押すと保留が変わる。まだ記録しない。設定は変えない", r["activeMoved"] and r["pendingChanged"] and r["notRecordedYet"] and r["settingUnchanged"])
    ok("問2を開いても問1は開いたまま（開閉は問ごとに独立）。問2（正解）の既定は普", r["accordion"] and r["q2DefaultNormal"])
    ok("問1を開き直しても押した評価は残る。同じ見出しをもう一度押すと畳む", r["activeKeptAfterRerender"] and r["toggleClose"])
    ok("全肢表示：解説が最初から開く", r["openMode"])
    ok("比較表・図解はタップで表示（畳んだ状態で描く）。図解は開くまで描かない", r["tableFig"] and r["figNotDrawnYet"])
    ok("図解は開いた瞬間に自分の枠へ描く", r["figDrawn"], {"svg": r["figSvg"]})
    ok("◀戻るで離れると記録される（変えた肢は普通・他は難）。保留は空・フックは外れる", r["leftToHome"] and r["pendingCleared"] and r["recorded"] and r["changedRecorded"] and r["othersHard"] and r["hookCleared"], r)
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_review_list" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
