#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCQ：模試を「設定へ寄り道してから」抜けても、次の学習は記録される（V2.22）

何が起きていたか：
V1.85（§22-2）は「模試中に［ホーム］」の直行経路だけを直していた。
畳む条件が `state.screen === 'quiz'` だったため、模試中に⚙設定へ寄り道して
からホームを押すと screen が 'settings' で条件を素通りし、模試セッションと
hooks（afterGrade ほか5本）が全部生き残った。その状態でランダム学習を
始めると、解答が死んだ模試の answers へ吸い込まれ、解説も評価チップも出ず、
記録は1件も増えない（疑似1年データの夜間検証で発見・実UIクリックで再現）。
直し方：
1. ホームボタンは「画面」ではなく「セッションが生きているか」で畳む
2. startSession／模試開始は、畳み損ねの残骸があれば必ず畳んでから始める
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
js1, js2 = read(p1), read(p2)
ok("ホームボタンはセッションで畳む（画面では見ない）",
   "if (state.session.mode) { endSession(); }" in js1)
ok("startSessionは更地にしてから始める", js1.count("if (state.session.mode) { endSession(); }") >= 2)
ok("模試開始も更地にしてから始める", "M.state.session.mode) { M.endSession(); }" in js2)

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
    pg.evaluate("() => { const b = document.getElementById('welcome-start'); if (b) b.click(); }")
    pg.wait_for_timeout(400)

    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler, M = window.Main, H = window.Half2;
      const out = {};
      const until = async (f) => { for (let i = 0; i < 120; i++) { if (f()) return true;
        await new Promise(r => setTimeout(r, 50)); } return false; };

      /* 模試を強制解禁して開始 */
      const origU = S.getUnlockState;
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      const origW = K.shouldWarnBeforeExam;
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      await H.startExam('mock_30', 'real');
      S.getUnlockState = origU; K.shouldWarnBeforeExam = origW;
      out.launched = await until(() => M.state.session && M.state.session.mode === 'exam' && M.state.current);

      /* 1問解いて、⚙設定へ寄り道 → 🏠ホーム（実UIのクリック） */
      const cur = M.state.current;
      cur.selected = [cur.atoms[0].original_num];
      M.confirmAnswer();
      await new Promise(r => setTimeout(r, 150));
      document.getElementById('btn-settings').click();
      await new Promise(r => setTimeout(r, 350));
      out.onSettings = M.state.screen === 'settings';
      document.getElementById('btn-home').click();
      await new Promise(r => setTimeout(r, 350));

      /* 畳まれていること */
      out.sessionFolded = !M.state.session.mode;
      out.hooksCleared = !M.hooks.afterGrade && !M.hooks.onFinish &&
        !M.hooks.examSavedFor && !M.hooks.openExamConfirm;

      /* その後のランダム学習が普通に記録されること */
      const beforeN = (await S.getAllLogs()).length;
      await M.startSession({ mode: 'random', count: 2 });
      out.randomStarted = await until(() => M.state.session &&
        M.state.session.mode === 'random' && M.state.current);
      const c2 = M.state.current;
      c2.selected = [c2.atoms[0].original_num];
      M.confirmAnswer();
      await new Promise(r => setTimeout(r, 400));
      const chips = [...document.querySelectorAll('button')]
        .filter(b => /普通/.test(b.textContent) && b.offsetParent);
      out.evalShown = chips.length > 0;
      /* 全肢に評価を付けてから次へ（記録が確定するのは評価→次へ） */
      const selBtns = [...document.querySelectorAll('#atom-selector button, .atom-tab')];
      for (let i = 0; i < Math.max(1, selBtns.length); i++) {
        if (selBtns[i]) { selBtns[i].click(); await new Promise(r => setTimeout(r, 80)); }
        const c = [...document.querySelectorAll('button')]
          .find(b => /普通/.test(b.textContent) && b.offsetParent);
        if (c) { c.click(); await new Promise(r => setTimeout(r, 80)); }
      }
      const next = document.getElementById('btn-next');   /* 「この評価で次へ」 */
      out.nextFound = !!(next && next.offsetParent); out.nextDisabled = next ? next.disabled : null;
      if (next && !next.disabled) { next.click(); }
      await new Promise(r => setTimeout(r, 900));
      const afterN = (await S.getAllLogs()).length;
      out.logsAdded = afterN - beforeN;
      return out;
    }""")
    ok("模試が始まる", r["launched"], json.dumps(r))
    ok("設定へ寄り道できる", r["onSettings"], json.dumps(r))
    ok("寄り道後のホームでもセッションが畳まれる", r["sessionFolded"], json.dumps(r))
    ok("模試のhooksが全部消える", r["hooksCleared"], json.dumps(r))
    ok("その後のランダム学習が始まる", r["randomStarted"], json.dumps(r))
    ok("解説と評価チップが出る", r["evalShown"], json.dumps(r))
    ok("記録が書かれる", r["logsAdded"] >= 1, json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCQ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
