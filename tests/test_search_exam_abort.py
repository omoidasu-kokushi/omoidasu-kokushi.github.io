# -*- coding: utf-8 -*-
"""test_search_exam_abort.py — 単語検索の演習と模試の中断を実測する（2026-09-07 夜）

【単語検索の即時演習（§12-1）】
  「忘却スケジュールも弱点ptも更新せず、評価チップの入力をスキップ」。
  ノックは**期日だけ**触らない（評価と弱点ptは動かす）のに対し、
  検索は**何も記録しない**。この違いが効いているかを直に比べる。

【模試の中断（§11・V1.85）】
  途中でやめたとき hooks が外れるか。外れないと、そのあとの学習が
  丸ごと記録されなくなる（V1.85 で実際に起きた）。
"""
import json, os, subprocess, sys, time

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
sys.path.insert(0, os.path.join(APP, "tools"))
from playwright.sync_api import sync_playwright
from journey_lib import answer_and_next, close_modals, tour_skip

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

SNAP = """async (ids) => {
  const S = window.Storage; const out = {};
  for (const id of ids) {
    const a = await S.getAtom(id);
    out[id] = { due: a.due_date, iv: a.interval_code, step: a.srs_step,
                cnt: a.answer_count, ev: a.last_eval, wk: a.weakness_pt };
  }
  return out;
}"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("""async () => { await window.Storage.setMetaBulk({ onboarding_done: true,
      tips_seen: ['unit_hero','qty','next','scan','level','settings_btn','theme','back','home_tip',
                  'qstar','tagpill','star','locked','memo','detail','summary',
                  'q_star','img_toggle','numeric_input','pomodoro','stem_expand'] }); }""")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1500)
    close_modals(pg); tour_skip(pg)

    def cur_atoms():
        return pg.evaluate("""async () => {
          const s = window.Main.state.session;
          if (!s || !s.questions) { return null; }
          const q = s.questions[s.index || 0];
          const at = await window.Storage.getAtomsByQuestion(q.q_id);
          return at.map(a => a.atom_id);
        }""")

    # ---------------- 単語検索の演習 ----------------
    pg.evaluate("async () => { await window.Main.startSession({ mode: 'search', count: 2 }); }")
    pg.wait_for_timeout(700); close_modals(pg); tour_skip(pg)
    ids = cur_atoms()
    ok("検索の演習が始まる", bool(ids), str(ids))
    if ids:
        before = pg.evaluate(SNAP, ids)
        okA = answer_and_next(pg)
        pg.wait_for_timeout(500)
        after = pg.evaluate(SNAP, ids)
        moved = [i for i in ids if before[i] != after[i]]
        ok("検索の演習で1問解ける", okA)
        ok("検索は何も記録しない（期日・評価・弱点ptとも動かない）",
           not moved, json.dumps({k: [before[k], after[k]] for k in moved[:1]}, ensure_ascii=False))

    # ---------------- 模試の中断 ----------------
    pg.evaluate("() => { window.Main.endSession(); window.Main.closeModals(); window.Main.go('home'); }")
    pg.wait_for_timeout(500); close_modals(pg)
    # 画面から始めるのと同じ道（launchExam）を通す。
    # M.startSession({mode:'exam'}) を直に呼ぶと hooks を張らないので、
    # 「hooks が外れるか」を検査できない（実測でここを踏んだ）。
    st = pg.evaluate("""async () => {
      const M = window.Main, H = window.Half2Impl;
      await H.launchExam('mock_30', 5, 'real');
      await new Promise(r => setTimeout(r, 600));
      return { mode: (M.state.session||{}).mode,
               hooks: Object.keys(M.hooks||{}).filter(k => typeof M.hooks[k] === 'function') };
    }""")
    ok("模試が始まり hooks を張る", st["mode"] == "exam" and st["hooks"],
       json.dumps(st, ensure_ascii=False))

    # 途中でホームへ戻る（中断）
    pg.evaluate("""() => {
      const M = window.Main;
      if (typeof M.hooks.onAbort === 'function') { M.hooks.onAbort(); }
      M.endSession(); M.closeModals(); M.go('home');
    }""")
    pg.wait_for_timeout(600); close_modals(pg)
    st2 = pg.evaluate("() => Object.keys(window.Main.hooks||{}).filter(k => typeof window.Main.hooks[k] === 'function')")
    ok("中断すると hooks が外れる（V1.85）", not st2, json.dumps(st2, ensure_ascii=False))

    # 中断のあと、ふつうの学習がちゃんと記録されるか（V1.85 で壊れていた本体）
    pg.evaluate("async () => { await window.Main.startSession({ mode: 'random', count: 2 }); }")
    pg.wait_for_timeout(700); close_modals(pg); tour_skip(pg)
    ids2 = cur_atoms()
    if ids2:
        b2 = pg.evaluate(SNAP, ids2)
        answer_and_next(pg)
        pg.wait_for_timeout(500)
        a2 = pg.evaluate(SNAP, ids2)
        moved2 = [i for i in ids2 if b2[i] != a2[i]]
        ok("模試を中断したあとの学習がちゃんと記録される（V1.85の本体）",
           len(moved2) == len(ids2),
           "%d/%d肢が更新" % (len(moved2), len(ids2)))
    ok("JSエラーが出ていない", not errs, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, d in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + d) if not good else ""))
print("\n%d/%d  search_exam_abort" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
