#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCM：模試の前後移動・解答の置き換え・提出前最終確認（V2.17）

利用者要望（2026-09-05裁定）：
・本番に即して前後の問題へ行き来できる
・提出前に全問一覧で最終確認（未回答の可視化・行タップで戻る）
・「全解答を提出する」まで採点も正誤表示も一切しない

設計（claude/20260905_模試V2.16設計）：
answers は q_id の置き換え式。think_ms は初回のみ。末尾でも自動採点せず必ず最終確認へ。
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
ok("模試ナビのDOMがある", 'id="exam-nav"' in html and 'id="btn-exam-prev"' in html)
ok("最終確認モーダルがある", 'id="modal-exam-confirm"' in html and 'id="exam-confirm-submit"' in html)
ok("確定時のカード正誤色は模試では出さない", "if (!isExamMode()) $$('#choice-list .choice-card')" in js1)
ok("解答はq_idの置き換え式", "st.exam.answers[at] = entry" in js2)
ok("think_msは初回のみ", "entry.think_ms = st.exam.answers[at].think_ms" in js2)
ok("末尾でも自動採点せず最終確認へ", "必ず最終確認を通す" in js2)
ok("採点後は新フックも外す", js2.count("M.hooks.examSavedFor = null") >= 2)

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
      const M = window.Main, S = window.Storage, K = window.Scheduler;
      const out = {};
      /* 初回ウェルカムを閉じる（残っていると画面遷移が始まらない） */
      const ws = document.getElementById('welcome-start');
      if (ws) { ws.click(); await new Promise(r2 => setTimeout(r2, 500)); }
      document.querySelectorAll('.modal-card:not([hidden])').forEach(m => { m.hidden = true; });
      const back = document.getElementById('modal-backdrop');
      if (back) { back.hidden = true; }
      /* 解禁と警告を飛ばしてミニ模試を直接起動する */
      S.getUnlockState = () => Promise.resolve([
        { id: 'mock_30', unlocked: true }, { id: 'mock_60', unlocked: false },
        { id: 'mock_120', unlocked: false }, { id: 'mock_weak', unlocked: false }]);
      K.shouldWarnBeforeExam = () => Promise.resolve({ warn: false });
      await window.Half2.startExam('mock_30', 'real');
      const until = async (f, ms) => { const t0 = Date.now();
        while (Date.now() - t0 < (ms || 8000)) { if (f()) { return true; }
          await new Promise(r2 => setTimeout(r2, 150)); } return false; };
      out.launched = await until(() => M.state.session.mode === 'exam' && M.state.current);
      const len = M.state.session.questions.length;
      out.mode = M.state.session.mode;
      out.navVisible = !document.getElementById('exam-nav').hidden;
      out.prevDisabledAtStart = document.getElementById('btn-exam-prev').disabled;

      const answer = (nums) => {
        const cur = M.state.current;
        cur.selected = nums !== undefined ? nums
          : [cur.atoms[0].original_num];
        M.confirmAnswer();
      };
      /* Q1を1番で確定 → 自動前進 */
      const q1id = M.state.current.question.q_id;
      answer();
      await new Promise(r2 => setTimeout(r2, 300));
      out.movedTo2 = M.state.session.index === 1;
      out.noVerdictOnCards = !document.querySelector('#choice-list .choice-card.is-correct');
      out.popupHidden = document.getElementById('verdict-pop').hidden;

      /* 前へ戻ると保存が復元される */
      M.examJump(0);
      await new Promise(r2 => setTimeout(r2, 200));
      out.restored = M.state.current.selected.length === 1;
      out.domSelected = !!document.querySelector('#choice-list .choice-card.is-selected');

      /* 解き直し：別の肢に置き換え（answeredCountは増えない） */
      const before = M.state.session.answeredCount;
      const alt = M.state.current.atoms[1] ? [M.state.current.atoms[1].original_num]
                                            : [M.state.current.atoms[0].original_num];
      answer(alt);
      await new Promise(r2 => setTimeout(r2, 200));
      const sv = M.hooks.examSavedFor ? M.hooks.examSavedFor(q1id) : null;
      out.replaced = !!sv && sv.atoms.filter(x => x.picked)[0].original_num === alt[0];
      out.countStable = M.state.session.answeredCount === before;

      /* 一覧を開く → 未回答が出ている → 行タップで移動 */
      M.hooks.openExamConfirm();
      await new Promise(r2 => setTimeout(r2, 300));
      const modal = document.getElementById('modal-exam-confirm');
      out.confirmOpen = !modal.hidden;
      out.rows = document.querySelectorAll('#exam-confirm-list .ec-row').length === len;
      out.hasUnanswered = document.querySelectorAll('#exam-confirm-list .ec-row.is-un').length === len - 1;
      document.querySelectorAll('#exam-confirm-list .ec-row')[4].click();
      await new Promise(r2 => setTimeout(r2, 300));
      out.jumpedTo5 = M.state.session.index === 4 && modal.hidden;

      /* 提出（未回答confirmはOKで通す）→ 採点結果 */
      window.confirm = () => true;
      M.hooks.openExamConfirm();
      await new Promise(r2 => setTimeout(r2, 200));
      document.getElementById('exam-confirm-submit').click();
      await new Promise(r2 => setTimeout(r2, 2500));
      out.resultOpen = !document.getElementById('modal-exam-result').hidden;
      out.hooksCleared = !M.hooks.afterGrade && !M.hooks.examSavedFor;
      return out;
    }""")
    for k in ["launched", "navVisible", "prevDisabledAtStart", "movedTo2", "noVerdictOnCards", "popupHidden",
              "restored", "domSelected", "replaced", "countStable", "confirmOpen", "rows",
              "hasUnanswered", "jumpedTo5", "resultOpen", "hooksCleared"]:
        ok(k, r.get(k) is True, json.dumps({k: r.get(k)}, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCM" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
