#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCM：模試の解答と提出、そのあとの復習（V2.17 → V3.10/V3.13 で作り直し）

【もともと何を見ていたか（V2.17・2026-09-05裁定）】
・本番に即して前後の問題へ行き来できる／提出前に全問一覧で最終確認（未回答の可視化・行タップで戻る）
・「全解答を提出する」まで採点も正誤表示も一切しない
  設計：answers は q_id の置き換え式。think_ms は初回のみ。末尾でも自動採点せず必ず最終確認へ。

【なぜ書き換えたか（V3.10・2026-09-12・利用者裁定）】
・利用者「模試自体全てスクロールではダメなの？そうすれば次へ前へボタンが不要になる」
  「一覧表示的な機能も無くす。チェックを入れた問題も自分で確認することでより本番度が増す」
  → 前後移動・解答一覧・置き換え式の解答そのものが無くなった。**観点は同数のまま、問題用紙の言葉へ置き換えた**。
    残した芯は変わらない：**提出まで採点も正誤表示も一切しない**。

このバッチが見るもの（問題用紙版）：
  塗る／塗り直す／別の問へ行っても残る・提出まで正誤を出さない・未回答でも提出できる・
  採点後にフックが外れる・そのあとの復習（V3.06〜V3.13）
"""
import io, json, os, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


import glob as _g
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js1, js2, html = read(p1), read(p2), read("index.html")
ok("問題用紙のDOMがある（ナビは無い）", 'id="screen-exam-paper"' in html and 'id="paper-list"' in html
   and 'id="exam-nav"' not in html and 'id="btn-exam-prev"' not in html)
ok("印だけの一覧がある（解答一覧の画面は無い）", 'id="modal-exam-marks"' in html and 'id="screen-exam-sheet"' not in html)
ok("問題用紙は正誤を出さない（採点まで）", "is-correct" not in js2.split("function renderExamPaper")[1][:2500]
   and "if (!isExamMode()) $$('#choice-list .choice-card')" in js1)
ok("解答は問題用紙の状態そのもの（q_idの置き換え式はやめた）", "ex.picks[q.q_id]" in js2
   and "st.exam.answers[at] = entry" not in js2)
ok("反応時間は模試では取らない（V3.10・利用者裁定）", "think_ms: null," in js2
   and "think_ms: (typeof M.thinkMsForCurrent === 'function')" not in js2)
ok("提出は最下部だけ・確認は文言だけ", "function openExamSubmit" in js2
   and "'試験終了まで残り' + Math.ceil(left / 60000) + '分です。'" in js2)
ok("採点後・畳んだあとにフックを外す", js2.count("M.hooks.onAbort = null") >= 2)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1200)

    r = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage, K = window.Scheduler, HI = window.Half2Impl;
      const out = {};
      const wait = (ms) => new Promise(r2 => setTimeout(r2, ms));
      const q = (id) => document.getElementById(id);
      /* 初回ウェルカムを閉じる（残っていると画面遷移が始まらない） */
      const ws = q('welcome-start');
      if (ws) { ws.click(); await wait(500); }
      document.querySelectorAll('.modal-card:not([hidden])').forEach(m => { m.hidden = true; });
      const back = q('modal-backdrop');
      if (back) { back.hidden = true; }
      /* 解禁と警告を飛ばしてミニ模試を直接起動する */
      S.getUnlockState = () => Promise.resolve([
        { id: 'mock_30', unlocked: true }, { id: 'mock_60', unlocked: false },
        { id: 'mock_120', unlocked: false }, { id: 'mock_weak', unlocked: false }]);
      K.shouldWarnBeforeExam = () => Promise.resolve({ warn: false });
      S.getExamHistory = () => Promise.resolve([]);
      await window.Half2.startExam('mock_30', 'real');
      const until = async (f, ms) => { const t0 = Date.now();
        while (Date.now() - t0 < (ms || 8000)) { if (f()) { return true; }
          await wait(150); } return false; };
      out.launched = await until(() => M.state.session.mode === 'exam'
        && q('screen-exam-paper').classList.contains('is-active'));
      const ex = HI.state.exam;
      const len = ex.questions.length;
      const li = (i) => document.querySelector('#paper-list .pq[data-index="' + i + '"]');
      const card = (i, k) => li(i).querySelectorAll('.choice-card')[k];
      out.paperShown = document.querySelectorAll('#paper-list .pq').length === len
        && !q('screen-quiz').classList.contains('is-active');
      out.noNav = !q('exam-nav') && !q('btn-exam-prev') && !q('btn-exam-next') && !q('btn-exam-list');

      /* 問1を塗る → 画面は動かない（1枚のまま）・正誤も出ない */
      const q1id = ex.questions[0].q_id;
      card(0, 0).querySelector('.choice-body').click();
      await wait(150);
      out.paintKeeps = q('screen-exam-paper').classList.contains('is-active')
        && document.querySelectorAll('#paper-list .pq').length === len;
      out.domSelected = card(0, 0).classList.contains('is-selected');
      out.noVerdictOnCards = !document.querySelector('#paper-list .choice-card.is-correct')
        && !document.querySelector('#paper-list .choice-card.is-wrong');
      out.popupHidden = q('verdict-pop').hidden;

      /* 別の問を塗っても、問1の塗りは残る */
      card(4, 0).querySelector('.choice-body').click();
      await wait(120);
      out.staysPainted = card(0, 0).classList.contains('is-selected') && (ex.picks[q1id] || []).length === 1;

      /* 塗り直し：別の肢を足して、元の肢を外す（数は自由・V3.10） */
      const before = Object.keys(ex.picks).length;
      card(0, 1).querySelector('.choice-body').click();
      card(0, 0).querySelector('.choice-body').click();
      await wait(120);
      out.replaced = !card(0, 0).classList.contains('is-selected') && card(0, 1).classList.contains('is-selected')
        && (ex.picks[q1id] || []).length === 1;
      out.picksStable = Object.keys(ex.picks).length === before;

      /* 未回答だらけでも提出できる（確認は文言だけ） */
      q('paper-submit').click(); await wait(250);
      out.submitAsk = !q('modal-exam-submit').hidden && /残り\\d+分です/.test(q('exam-submit-body').textContent);
      out.submitEnabledAlways = !q('paper-submit').disabled;
      document.querySelector('#modal-exam-submit [data-close]').click(); await wait(200);
      out.unansweredOk = !ex.submitted && q('screen-exam-paper').classList.contains('is-active');

      /* 残りを埋めて（最後の1問だけ未回答のまま）提出 */
      ex.questions.forEach((qq, i) => {
        if (i === len - 1 || (ex.picks[qq.q_id] || []).length) { return; }
        const c = li(i).querySelectorAll('.choice-card')[0];
        if (c) { c.querySelector('.choice-body').click(); }
        else { const inp = li(i).querySelector('.pq-num-input'); if (inp) { inp.value = '1'; } }
      });
      await wait(200);
      q('paper-submit').click(); await wait(200);
      q('exam-submit-go').click();
      await until(() => !q('modal-exam-result').hidden, 20000);
      out.resultOpen = !q('modal-exam-result').hidden;
      out.gradedWithUnanswered = ex.answers.length === len
        && ex.answers[len - 1].unanswered === true && ex.answers[len - 1].answered_right === false;
      out.paperRows = len === 30;
      out.hooksCleared = !M.hooks.afterGrade && !M.hooks.onAbort && !M.hooks.onFinish;

      /* V2.18：復習（誤答は展開・正答は畳む）＋単元グラフ
         → V3.06：入口の2択 → 全画面のスクロール一覧（問ごとに○×・肢のブロック・評価ボタン）
         → V3.13：最初に開くのは最初に間違えた問。正解した問は畳んだまま（見出しに正解肢の本文） */
      q('btn-exam-review').click(); await wait(400);
      out.reviewOpen = !q('modal-exam-review-style').hidden;
      q('exam-review-style-button').click(); await wait(600);
      out.reviewRows = q('screen-exam-review').classList.contains('is-active')
        && document.querySelectorAll('#exam-review-list .xr-q').length === len;
      const rightN = ex.answers.filter(a => a.answered_right).length;
      out.closedMatchesRight = document.querySelectorAll('#exam-review-list .xr-mark.is-correct').length === rightN;
      out.wrongExpanded = document.querySelectorAll('#exam-review-list .xr-mark.is-wrong').length === len - rightN;
      out.graphRows = document.querySelectorAll('#exam-review-list .xr-q.is-open .eval-group').length >= 1;   /* 開いた問で評価が押せる（V3.09：開くのは1問） */
      /* 解説の開閉（1肢ずつ） */
      const firstExp = document.querySelector('#exam-review-list details.cx-exp');
      const wasOpen = firstExp.open;
      firstExp.querySelector('summary').click();
      out.toggleWorks = firstExp.open !== wasOpen;
      q('exam-review-done').click();
      await wait(1500);
      return out;
    }""")
    for k in ["launched", "paperShown", "noNav", "paintKeeps", "domSelected", "noVerdictOnCards", "popupHidden",
              "staysPainted", "replaced", "picksStable", "submitAsk", "submitEnabledAlways", "unansweredOk",
              "resultOpen", "gradedWithUnanswered", "paperRows", "hooksCleared", "reviewOpen", "reviewRows",
              "closedMatchesRight", "wrongExpanded", "graphRows", "toggleWorks"]:
        ok(k, r.get(k) is True, json.dumps({k: r.get(k)}, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCM" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
