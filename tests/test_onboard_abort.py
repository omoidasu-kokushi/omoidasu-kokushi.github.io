# -*- coding: utf-8 -*-
"""test_onboard_abort.py — チュートリアルを途中でやめても、そのあとの学習を壊さない（V3.22）

【何が起きていたか（2026-09-15 実測）】
  DESIGN_DECISIONS 22-2（V1.85）は「モードを畳むとき hooks は各モードが自分で外す。
  endSession() は消さない。張ったら必ず onAbort で全部外す」と決めた。
  V1.85 は**模試**を直した。**オンボーディング（ツアー）は onAbort を張っていなかった。**

  ツアーは `afterCommit`（答えた数を数え、3問で終わらせる）と
  `onFinish`（既定の終了処理を止める）を張る。どちらも `st.onboard.active` を見て
  「ツアー中でなければ何もしない」形だが、**中断しても active が true のまま**だった。

  実測の並び：
    1. チュートリアルを始めて1問だけ答える（step 1）
    2. ホーム →「やめますか」→ やめる    … active は true のまま・hooks も残る
    3. 普通にランダム学習を始める
    4. **2問目を答えた瞬間にセッションが消えた**（step が 3 に達し、残った afterCommit が
       `M.endSession(); finishOnboarding();` を実行した）
    5. `tutorial_answered` が 1 → 20 に書き換わった

  利用者から見ると「ランダムを始めたのに2問で勝手に終わってホームに戻される」。
  しかも一度きりのツアー完了処理（記録の保持のお願いなど）が、学習の途中で走る。

【直し方】
  `startOnboarding` が `M.hooks.onAbort` を張り、そこで
  `st.onboard.active = false` と afterCommit・onFinish・onAbort を落とす。
  畳むだけにする（中断を知らせない・進み具合を書き換えない）。
  `tutorial_answered` は残す（§8-4「前回の続きから」が効かなくなるため）。

【ここで固定すること】
  ・中断すると active が false になり、hooks が1つも残らない
  ・中断したあとのランダム学習が、何問続けてもセッションを奪われない
  ・中断しても `tutorial_answered` は保たれる（続きから始められる）
  ・3問そろえて普通に終わる道は、これまでどおり終わる（onAbort を足しても壊れない）
  ・張った側が自分で外す、と書いてある（22-2 を引いている）
"""
import os, sys, io, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import glob as _g
p2 = sorted(_g.glob(os.path.join(base, "*main_part2_V*.js")))[-1]
js2 = io.open(p2, encoding="utf-8").read()

seg = js2[js2.index("function startOnboarding"):js2.index("function finishOnboarding")]
ok("ツアーが onAbort を張る", "M.hooks.onAbort = function" in seg)
ok("onAbort が印を落とす", "st.onboard.active = false" in seg)
ok("onAbort が3本とも落とす",
   seg.count("M.hooks.afterCommit = null") >= 1 and seg.count("M.hooks.onFinish = null") >= 1
   and seg.count("M.hooks.onAbort = null") >= 1)
ok("22-2 を引いている", "22-2" in seg)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

RUN = """async () => {
  const S = window.Storage, M = window.Main, HI = window.Half2Impl;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const names = ['afterGrade','onFinish','onAbort','afterCommit','beforeLeave'];
  const left = () => names.filter(n => typeof M.hooks[n] === 'function');
  const out = {};

  const answerOne = async () => {
    const c = M.state.current; if (!c) { return false; }
    c.selected = [c.atoms[0].original_num];
    M.confirmAnswer(); await wait(450);
    const sel = [...document.querySelectorAll('#atom-selector button, .atom-tab')];
    for (let i = 0; i < Math.max(1, sel.length); i++) {
      if (sel[i]) { sel[i].click(); await wait(50); }
      const chip = [...document.querySelectorAll('button')].find(b => /普通/.test(b.textContent) && b.offsetParent);
      if (chip) { chip.click(); await wait(50); }
    }
    const next = document.getElementById('btn-next');
    if (next && !next.disabled) { next.click(); }
    await wait(700);
    return true;
  };
  const goHome = async () => {
    document.getElementById('btn-home').click();
    for (let i = 0; i < 40; i++) {
      const mc = document.getElementById('modal-confirm');
      if (mc && !mc.hidden) { const cg = document.getElementById('confirm-go'); if (cg) { cg.click(); } break; }
      await wait(50);
    }
    for (let i = 0; i < 40; i++) { if (!(M.state.session && M.state.session.mode)) { break; } await wait(50); }
  };

  /* ① ツアーを1問でやめる */
  await HI.startOnboarding(0);
  await wait(700);
  out.開始 = { active: HI.state.onboard.active, hooks: left() };
  await answerOne();
  const step1 = HI.state.onboard.step;
  const ta1 = await S.getMeta('tutorial_answered', 0);
  await goHome();
  out.中断後 = { active: HI.state.onboard.active, hooks: left(), step: HI.state.onboard.step,
                  tutorial_answered: await S.getMeta('tutorial_answered', 0), step1: step1, ta1: ta1 };

  /* ② そのあとランダムを4問続ける。奪われないこと */
  await M.startSession({ mode: 'random', count: 6 });
  await wait(500);
  const seq = [];
  for (let i = 0; i < 4; i++) {
    await answerOne();
    seq.push((M.state.session && M.state.session.mode) || null);
    if (!(M.state.session && M.state.session.mode)) { break; }
  }
  out.ランダム4問 = seq;
  M.endSession(); await wait(200);
  names.forEach(n => { M.hooks[n] = null; });

  /* ③ 3問そろえる普通の道は、これまでどおり終わる */
  await S.setMeta('tutorial_answered', 0);
  await HI.startOnboarding(0);
  await wait(700);
  for (let i = 0; i < 3; i++) {
    if (!(M.state.session && M.state.session.mode)) { break; }
    await answerOne();
  }
  await wait(900);
  out.完走 = { active: HI.state.onboard.active, hooks: left(),
                session: (M.state.session && M.state.session.mode) || null,
                step: HI.state.onboard.step };
  return out;
}"""

def wait_init(pg, limit=60):
    t0 = time.time()
    while time.time() - t0 < limit:
        if pg.evaluate("() => window.__INIT_DONE === true"):
            return True
        pg.wait_for_timeout(200)
    return False

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    ok("同梱2本の取り込みが終わる（__INIT_DONE）", wait_init(pg))
    r = pg.evaluate(RUN)
    ok("ツアー開始で afterCommit・onFinish・onAbort が張られる",
       set(r["開始"]["hooks"]) >= {"afterCommit", "onFinish", "onAbort"}, r["開始"])
    ok("中断すると印（active）が下りる", r["中断後"]["active"] is False, r["中断後"])
    ok("中断すると hooks が1つも残らない", not r["中断後"]["hooks"], r["中断後"]["hooks"])
    ok("中断しても続きの数は残る（前回の続きから）",
       r["中断後"]["tutorial_answered"] >= 1, r["中断後"])
    ok("そのあとのランダムが4問とも奪われない",
       r["ランダム4問"] == ["random"] * 4, r["ランダム4問"])
    ok("3問そろえる普通の道は、これまでどおり終わる",
       r["完走"]["active"] is False and not r["完走"]["session"], r["完走"])
    ok("完走後も hooks が残らない", not r["完走"]["hooks"], r["完走"]["hooks"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  onboard_abort" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
