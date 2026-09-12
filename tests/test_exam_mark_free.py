# -*- coding: utf-8 -*-
"""test_exam_mark_free.py — 模試の☐は用途自由の印。評価の既定は 4-3。提出時は保留、閉じたら既定のまま記録（V3.05）

【何が起きていたか（利用者裁定 2026-09-12）】
  ・第11章③：正解＋根拠ON → 易30日／マ180日、それ以外 → 難。提出した瞬間に記録していた。
    利用者「チェックマークが長期記憶への昇格とかはしないでいい。用途自由。
            間違えた問題の選択肢は全て難しい・正解なら全て普通。評価ボタンはいつも通り置き、
            異議があれば変えてもらう。既出の問題は正解なら既定の評価を変えない」
  ・→ 既定は他モードと同じ recommendEvaluations（4-3）。提出時は meta.exam_pending に「保留」として置き、
       復習の［次へ］で確定（V3.06）。復習しないで閉じた・途中でやめた・アプリを閉じたときは既定のまま記録する。

【ここで固定すること】
  ・提出しただけでは記録が増えない（保留に30問ぶん）。結果画面は「評価の既定：難しい◯肢／普通◯肢」
  ・結果を閉じると既定のまま記録される：誤答の問題は全肢「難しい」、初見で正解は全肢「普通」、
    既出で正解は前回の評価のまま。記録の mode は exam、☐は ground_on として残る（評価には効かない）
  ・記録したら保留は空。二重に記録しない
  ・起動時に保留が残っていれば記録して知らせる（結果を見ずに閉じた端末）
  ・模試は今までどおり延べ解答数（Level 2 の分母）に入れない（applyQuestionEvaluations を通さない）
  ・applyExamResult は呼ばれない（旧記録の意味のために残す）
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(n): return io.open(os.path.join(base, n), encoding="utf-8").read()
p1, p2, sc = rd("20260815_main_part1_V1.38.js"), rd("20260815_main_part2_V1.45.js"), rd("scheduler.js")
ih = rd("index.html")

ok("提出時に applyExamResult を呼ばない（保留に置く）", "K.applyExamResult(" not in p2 and "function buildExamPending" in p2
   and "S.setMeta('exam_pending', pending)" in p2)
ok("既定は recommendEvaluations（4-3）", "K.recommendEvaluations(atoms, picked).recommendations" in p2)
ok("記録は applyEvaluation（門番も同じ）。日次の数・分母には入れない", "K.applyEvaluation(at.atom_id, at.eval, {" in p2
   and "applyQuestionEvaluations を通さない" in p2)
ok("☐は記録に ground_on として残る（評価には使わない）", "if (typeof ctx.groundOn === 'boolean') { log.ground_on = ctx.groundOn; }" in sc)
ok("結果を閉じたら保留を記録する", "on($('#modal-exam-result [data-close]'), 'click', function () {" in p2 and "flushExamPending().then" in p2)
ok("起動時に保留を拾う", "function flushExamPendingOnBoot" in p2 and "return flushExamPendingOnBoot();" in p2)
# V3.10：模試は問題用紙（part2 renderExamPaper）。前書きは index.html、吹き出しは part2、aria-label は肢の描画側
ok("☐の説明が「用途自由の印」になっている（前書き・ガイド・aria-label）", "自由に使える印です" in ih and "自由に使える印。" in p2
   and 'aria-label="この肢に印を付ける' in p2 and "長期記憶へ昇格" not in p2.split("function renderExamPaper")[1][:2500])
ok("applyExamResult は残っている（旧記録の意味）", "function applyExamResult" in sc and "V3.05 から呼ばれない" in sc)

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
      const ex = window.Half2Impl.state.exam;
      const len = ex.questions.length;
      const logs0 = await S.countLogs();
      const total0 = await S.getMeta('total_questions_answered', 0);
      /* 問3を「既出・易しい・期日ずみ」にしておく（模試を組んだ写しにも反映させる） */
      const q3 = ex.questions[2];
      const now = Date.now(), patchPrev = {};
      (q3.atoms || []).forEach(a => { patchPrev[a.atom_id] = { answer_count: 1, correct_count: 1, last_eval: 'easy',
        last_answered_at: now - 40 * 86400000, srs_step: 4, interval_code: '30d', due_date: now - 86400000 };
        Object.assign(a, patchPrev[a.atom_id]); });
      await S.updateAtomsBulk(patchPrev);
      /* V3.10：1枚の問題用紙。肢をタップして塗り、☐をタップして印を付ける */
      const plan = {};   /* q_id → {right, marked:[atom_id]} */
      ex.questions.forEach((qq, i) => {
        const li = document.querySelector('#paper-list .pq[data-index="' + i + '"]');
        const atoms = (qq.atoms || []).slice().sort((a, b) => a.original_num - b.original_num);
        const correct = atoms.filter(a => a.is_correct).map(a => a.original_num);
        const wrong = atoms.filter(a => !a.is_correct).map(a => a.original_num);
        const right = (i % 2 === 0) || i === 2;   /* 偶数と問3は正解 */
        (right ? correct : [wrong[0]]).forEach(n => li.querySelector('.choice-card[data-num="' + n + '"] .choice-body').click());
        const marked = [];
        if (i % 3 === 0) { const a = atoms[1] || atoms[0];
          li.querySelector('.choice-card[data-atom-id="' + a.atom_id + '"] .choice-mark').click(); marked.push(a.atom_id); }
        plan[qq.q_id] = { right, marked, atoms: atoms.map(a => a.atom_id) };
      });
      q('paper-submit').click(); await wait(250);
      q('exam-submit-go').click();
      for (let i = 0; i < 100; i++) { if (!q('modal-exam-result').hidden) break; await wait(100); }
      out.resultOpen = !q('modal-exam-result').hidden;
      out.scoreLine = q('exam-score').textContent;
      const pend = await S.getMeta('exam_pending', null);
      out.pendingItems = pend && pend.items ? pend.items.length : 0;
      out.logsUnchangedAtSubmit = (await S.countLogs()) === logs0;
      /* 保留の既定：誤答は全肢 hard／初見正解は全肢 normal／問3（既出・正解）は easy のまま */
      let okHard = true, okNormal = true, okKept = true, okMarks = true;
      pend.items.forEach(it => {
        const pl = plan[it.q_id];
        it.atoms.forEach(at => {
          if (it.q_id === q3.q_id) { if (at.eval !== 'easy') okKept = false; }
          else if (!pl.right) { if (at.eval !== 'hard') okHard = false; }
          else { if (at.eval !== 'normal') okNormal = false; }
          if (!!at.ground_on !== (pl.marked.indexOf(at.atom_id) >= 0)) okMarks = false;
        });
      });
      out.defaults = { okHard, okNormal, okKept, okMarks };
      /* 結果を閉じる → 記録される */
      document.querySelector('#modal-exam-result [data-close]').click();
      for (let i = 0; i < 100; i++) { const p2 = await S.getMeta('exam_pending', null); if (!p2) break; await wait(100); }
      out.pendingCleared = !(await S.getMeta('exam_pending', null));
      const logs = (await S.getAllLogs()).filter(l => l.mode === 'exam');
      out.examLogs = logs.length;
      const byAtom = {}; logs.forEach(l => { byAtom[l.atom_id] = l; });
      let recHard = true, recNormal = true, recKept = true, recMarks = true, groundBool = true;
      Object.keys(plan).forEach(qid => { const pl = plan[qid]; pl.atoms.forEach(id => {
        const l = byAtom[id]; if (!l) { recHard = recNormal = recKept = false; return; }
        if (typeof l.ground_on !== 'boolean') groundBool = false;
        if (qid === q3.q_id) { if (l.eval !== 'easy') recKept = false; }
        else if (!pl.right) { if (l.eval !== 'hard') recHard = false; }
        else { if (l.eval !== 'normal') recNormal = false; }
        if (l.ground_on !== (pl.marked.indexOf(id) >= 0)) recMarks = false;
      }); });
      out.recorded = { recHard, recNormal, recKept, recMarks, groundBool };
      out.noExamPattern = logs.every(l => l.exam_pattern === undefined);
      out.totalUnchanged = (await S.getMeta('total_questions_answered', 0)) === total0;
      const a3 = await S.getAtom(q3.atoms[0].atom_id);
      out.q3Advanced = a3.answer_count === 2 && a3.last_eval === 'easy';
      /* 二重に記録しない：もう一度閉じても増えない */
      await H.flushExamPending();
      out.noDouble = (await S.getAllLogs()).filter(l => l.mode === 'exam').length === logs.length;
      /* 起動時の回収：保留を手で置いて再読込 */
      const anyAtom = (await S.getAllAtoms()).filter(a => a.pool !== 'mock' && !a.answer_count)[0];
      await S.setMeta('exam_pending', { session_id: 'EXTEST', exam_id: 'mock_30', at: Date.now(),
        items: [{ q_id: anyAtom.q_id, think_ms: 1000, answered_right: false, picked: [], atoms: [{ atom_id: anyAtom.atom_id, original_num: anyAtom.original_num, eval: 'hard', is_correct: false, ground_on: true }] }] });
      out.bootAtom = anyAtom.atom_id;
      return out; }""")
    ok("提出しただけでは記録が増えない（保留に全問ぶん）", r["resultOpen"] and r["pendingItems"] == 30 and r["logsUnchangedAtSubmit"], r["pendingItems"])
    ok("結果画面は「評価の既定」（昇格・降格の行は無い）", "評価の既定" in r["scoreLine"] and "自動昇格" not in r["scoreLine"], r["scoreLine"][-80:])
    ok("既定：誤答は全肢 難／初見の正解は全肢 普／既出の正解は前回のまま／☐は印として残る", all(r["defaults"].values()), r["defaults"])
    ok("結果を閉じると既定のまま記録され、保留は空になる", r["pendingCleared"] and r["examLogs"] > 0, r["examLogs"])
    ok("記録の中身：難／普／前回のまま・mode=exam・ground_on は真偽値", all(r["recorded"].values()), r["recorded"])
    ok("exam_pattern は書かない（昇格／降格はもう無い）", r["noExamPattern"])
    ok("模試は延べ解答数に入れない（今までどおり）", r["totalUnchanged"])
    ok("既出の肢は模試の解答で回数が進む（記録された）", r["q3Advanced"])
    ok("二重には記録しない", r["noDouble"])
    # 再読込 → 保留の回収
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.wait_for_timeout(800)
    b = pg.evaluate("""async (atomId) => { const S = window.Storage;
      const logs = (await S.getLogsByAtom(atomId)).filter(l => l.mode === 'exam');
      return { pending: await S.getMeta('exam_pending', null), n: logs.length, ev: logs[0] && logs[0].eval, g: logs[0] && logs[0].ground_on,
               toast: document.body.innerText.indexOf('前回の模試の評価を記録しました') >= 0 || (document.querySelector('#toast')||{}).textContent || '' }; }""", r["bootAtom"])
    ok("起動時に残っていた保留を記録して知らせる", b["pending"] is None and b["n"] == 1 and b["ev"] == "hard" and b["g"] is True, json.dumps(b, ensure_ascii=False)[:200])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_mark_free" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
