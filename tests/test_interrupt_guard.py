# -*- coding: utf-8 -*-
"""test_interrupt_guard.py — 早期復習割り込みの「絶対ガード」を実測する（2026-09-07 夜）

§5-2 の絶対ガード：
  『本日の復習』『概念別弱点ノック』『力試し模試』『単元別学習』
  『単語検索での即時演習』の実行中は、割り込みを**完全に禁止**。

ここが破れると、模試の最中に別の問題が差し込まれる。
点数が狂うだけでなく、本番の練習として意味が壊れる。

読んで確かめるのではなく、**割り込みの球を溜めた状態で各モードを始めて**、
実際に差し込まれるかどうかを見る。
"""
import json, os, subprocess, time
from playwright.sync_api import sync_playwright

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("async () => { await window.Storage.setMeta('onboarding_done', true); }")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1500)
    pg.evaluate("() => window.Main.closeModals()")

    # 割り込みの仕組みが外から見えるか
    api = pg.evaluate("""() => {
      const K = window.Scheduler;
      const I = K && K.Interrupt;
      return { has: !!I, keys: I ? Object.keys(I) : [] };
    }""")
    ok("割り込みの仕組みが外から触れる", api["has"], json.dumps(api, ensure_ascii=False))

    # 割り込みの球を溜める（10分前・1時間前に「難しい」を押した肢を3つ）
    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler, I = K.Interrupt;
      const at = (await S.getAllAtoms()).slice(0, 3);
      for (const a of at) {
        await S.updateAtom(a.atom_id, {
          answer_count: 1, last_eval: 'hard',
          interval_code: '10m', srs_step: 1,
          due_date: Date.now() - 60 * 1000
        });
        /* 実際の道と同じ note() を通す。許可モードを渡さないと溜まらない
           （＝ここ自体がガードの一部）。 */
        I.note({ atom_id: a.atom_id, q_id: a.q_id, interval_code: '10m' }, 'random');
      }
      return { pool: I.pool.length, unique: I.uniqueQuestionCount() };
    }""")
    print("割り込みの球:", json.dumps(r, ensure_ascii=False))

    def start_and_check(mode_js, label, allowed):
        got = pg.evaluate("""async (js) => {
          const M = window.Main, K = window.Scheduler, I = K.Interrupt;
          M.endSession(); M.closeModals();
          await new Function('return (' + js + ')()')();
          await new Promise(r => setTimeout(r, 500));
          const s = M.state.session || {};
          const mode = s.mode || null;
          return { mode: mode,
                   allowed: I.isAllowed(mode),
                   trigger: I.shouldTrigger(mode),
                   pool: I.pool.length, unique: I.uniqueQuestionCount(),
                   active: I.active,
                   n: (s.questions || []).length };
        }""", mode_js)
        ok("%s で割り込みが%s" % (label, "許される" if allowed else "禁止される"),
           (got["allowed"] is True) if allowed else (got["allowed"] is False),
           json.dumps(got, ensure_ascii=False))
        # 呼んでも始まらないことまで見る（判定だけでなく実際の入口も塞がっているか）
        b = pg.evaluate("""async (mode) => {
          const I = window.Scheduler.Interrupt;
          const r = await I.begin(mode);
          return { started: !!(r && r.started), reason: (r && r.reason) || null };
        }""", got["mode"])
        if not allowed:
            ok("%s では begin() を呼んでも始まらない" % label, b["started"] is False,
               json.dumps(b, ensure_ascii=False))
        return got

    guarded = [
        ("async () => { await window.Main.startSession({ mode:'review', count:5 }); }", "本日の復習"),
        ("async () => { await window.Half2Impl.startKnock('#人口動態統計', 3); }", "概念別弱点ノック"),
        ("async () => { await window.Main.startSession({ mode:'exam', count:5 }); }", "力試し模試"),
        ("async () => { await window.Main.startSession({ mode:'unit', count:5 }); }", "単元別学習"),
        ("async () => { await window.Main.startSession({ mode:'search', count:5 }); }", "単語検索での即時演習"),
    ]
    for js, label in guarded:
        start_and_check(js, label, allowed=False)

    # V2.55（利用者裁定 2026-09-06）で割り込みは**全モードで発火させない**ことになった。
    # 「難しい」は20分後が期日なのに、割り込みは期日を待たずに数分で差し込んでいた。
    # 実装は消さず、INTERRUPT_ENABLED = false で止めてある。
    # なので random / new でも isAllowed は false が正しい。
    for js, label in [
        ("async () => { await window.Main.startSession({ mode:'random', count:5 }); }", "ランダム"),
        ("async () => { await window.Main.startSession({ mode:'new', count:5 }); }", "新規"),
    ]:
        start_and_check(js, label, allowed=False)

    # 止め方が「消した」ではなく「1行で戻せる」形になっているかを見る。
    # 消してしまうと、戻したくなったときに作り直しになる。
    src = open(os.path.join(APP, "scheduler.js"), encoding="utf-8").read()
    ok("止め方が1つのスイッチ（INTERRUPT_ENABLED）である",
       "var INTERRUPT_ENABLED = false;" in src)
    ok("なぜ止めたかが書いてある（V2.55の裁定）",
       "期日を待たずに" in src and "実装は消さない" in src)
    ok("許可モードの一覧は残っている（戻すときの土台）",
       "var INTERRUPT_ALLOWED_MODES = ['new', 'random'];" in src)

    # スイッチを入れたら本当に動くか（実装が腐っていないか）を、その場で確かめる
    revived = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage, I = window.Scheduler.Interrupt;
      /* テストの中だけで isAllowed を差し替え、実装が生きているかを見る。
         本体の定数は触らない。 */
      const orig = I.isAllowed;
      I.isAllowed = (mode) => mode === 'new' || mode === 'random';
      I.pool = []; I.active = false; I.run = 0;
      M.endSession(); M.closeModals();
      await M.startSession({ mode: 'random', count: 5 });
      /* 発火の条件は「3**問**たまったら」（肢ではない）。
         同じ問題の肢を3つ入れても unique は1のままなので、
         別々の問題から1肢ずつ取る。 */
      const all = await S.getAllAtoms();
      const seen = new Set(); const pick = [];
      for (const a of all) {
        if (seen.has(a.q_id)) { continue; }
        seen.add(a.q_id); pick.push(a);
        if (pick.length >= 3) { break; }
      }
      for (const a of pick) { I.note({ atom_id:a.atom_id, q_id:a.q_id, interval_code:'10m' }, 'random'); }
      const trig = I.shouldTrigger('random');
      const r = await I.begin('random');
      const out = { unique: I.uniqueQuestionCount(), trigger: trig,
                    started: !!(r && r.started), n: (r && r.questions ? r.questions.length : 0),
                    reason: (r && r.reason) || null };
      I.isAllowed = orig; I.pool = []; I.active = false; I.run = 0;
      return out;
    }""")
    ok("スイッチを入れれば割り込みは動く（実装が腐っていない）",
       revived["trigger"] and revived["started"], json.dumps(revived, ensure_ascii=False))
    ok("戻したあとは また止まっている",
       pg.evaluate("() => window.Scheduler.Interrupt.isAllowed('random')") is False)

    ok("JSエラーが出ていない", not errs, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, d in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + d) if not good else ""))
print("\n%d/%d  interrupt_guard" % (len(R) - len(bad), len(R)))
