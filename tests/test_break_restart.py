# -*- coding: utf-8 -*-
"""test_break_restart.py — 休憩を挟んだら、次は新しい25分（V2.72）

利用者の質問：
  「ポモドーロONのときの休憩時間中に問題解きだしたら
   勝手にポモドーロ再スタートする?」

V2.71 時点での実測 — 答えは「しない」。しかも壊れていた。
  ① 休憩中に解きはじめても休憩タイマーは止まらず、ヘッダーは休憩色のまま。
     tickBreak が250msごとに数字を上書きするので、集中の残りが見えない。
  ② 5分後に「休憩おわり」の通知が、解いている最中に出る。
  ③ 休憩あけは endBreak → M.startPomodoro() だが pomodoroIsFresh() が真で
     **前の25分を引き継ぐ**。実測：休憩前に20分使っていると、
     休憩あけの残りは5.0分。休憩したのに5分後にまた「25分経過」。

V2.72：
  ・休憩中に解きはじめたら休憩を打ち切る（通知は出さない）
  ・休憩を挟んだら、自然終了でも打ち切りでも必ず新しい25分

ここで固定するのは5つ。
  ① 解きはじめると休憩タイマーが止まる
  ② 休憩色が外れる
  ③ 打ち切ったあとのポモドーロは25分（引き継がない）
  ④ 自然に終わったあとも25分
  ⑤ 打ち切ったことを黙って済ませない（1行伝える）
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()

ok("打ち切る口がある", "function abortBreakIfSolving" in p2)
ok("出題開始時に呼んでいる", "Half2.abortBreakIfSolving();" in p1)
ok("休憩あけは新しい25分にする", "if (wasRunning) { M.restartPomodoro(); }" in p2)
ok("打ち切りでは通知を出さない", "endBreak(false);" in p2)
ok("打ち切ったことを伝える", "休憩を切り上げました" in p2)
ok("なぜ引き継がないかが書いてある", "25分集中 → 休憩 → 新しい25分" in p2)
ok("V1.16の「跨いでも巻き戻さない」は残っている", "モードを跨いでも巻き戻さない" in p1)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
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
    pg.wait_for_timeout(1200)
    pg.evaluate("() => window.Main.closeModals()")

    a = pg.evaluate("""async () => {
      const M = window.Main, H = window.Half2Impl;
      await M.setPomodoroEnabled(true);
      M.startPomodoro();
      M.state.pomodoro.startedAt = Date.now() - 20 * 60 * 1000;   /* 20分使った */
      M.state.pomodoro.lastActiveAt = Date.now();
      await H.startBreak(5);
      await new Promise(r => setTimeout(r, 300));
      const ticking = !!H.st.breakT.tick;
      const isBreak = document.getElementById('pomodoro-chip').classList.contains('is-break');
      await M.startSession({ mode: 'random', count: 5 });
      await new Promise(r => setTimeout(r, 500));
      return { 休憩中だった: ticking, 休憩色だった: isBreak,
               後_tick: !!H.st.breakT.tick,
               後_休憩色: document.getElementById('pomodoro-chip').classList.contains('is-break'),
               後_残り分: Math.round(M.pomodoroLeftMs() / 60000),
               後_ヘッダー: document.getElementById('pomodoro-time').textContent };
    }""")
    ok("前提：休憩が始まっていた", a["休憩中だった"] and a["休憩色だった"], json.dumps(a, ensure_ascii=False))
    ok("解きはじめると休憩タイマーが止まる", a["後_tick"] is False, json.dumps(a, ensure_ascii=False))
    ok("休憩色が外れる", a["後_休憩色"] is False, json.dumps(a, ensure_ascii=False))
    ok("打ち切ったあとは新しい25分（前の残り5分を引き継がない）",
       a["後_残り分"] == 25, json.dumps(a, ensure_ascii=False))
    ok("ヘッダーもすぐ25:00になる（休憩の05:00が残らない）",
       a["後_ヘッダー"].startswith("25:") or a["後_ヘッダー"].startswith("24:5"), str(a["後_ヘッダー"]))

    b = pg.evaluate("""async () => {
      const M = window.Main, H = window.Half2Impl;
      M.endSession(); M.closeModals();
      M.startPomodoro();
      M.state.pomodoro.startedAt = Date.now() - 20 * 60 * 1000;
      M.state.pomodoro.lastActiveAt = Date.now();
      await H.startBreak(5);
      H.st.breakT.endsAt = Date.now() + 200;
      await new Promise(r => setTimeout(r, 1000));
      return { 残り分: Math.round(M.pomodoroLeftMs() / 60000),
               動いている: M.state.pomodoro.running,
               休憩色: document.getElementById('pomodoro-chip').classList.contains('is-break') };
    }""")
    ok("自然に終わったあとも新しい25分", b["残り分"] == 25, json.dumps(b, ensure_ascii=False))
    ok("休憩あけはポモドーロが動いている", b["動いている"], json.dumps(b, ensure_ascii=False))
    ok("休憩色が外れている", b["休憩色"] is False, json.dumps(b, ensure_ascii=False))

    c = pg.evaluate("""() => {
      /* 休憩していないときに呼んでも何もしない（誤爆しない） */
      return window.Half2.abortBreakIfSolving();
    }""")
    ok("休憩していないときは何もしない", c is False, str(c))
    ok("JSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
ix_q = _vers(ix, r"\?v=([0-9.]+)")
ok("index.htmlの?v=が1種類", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致", ix_q == _vers(sw, r"\?v=([0-9.]+)"), str(ix_q))
ok("CACHE_NAMEが?v=と同じ系列", _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'") == [ix_q[0] + ".0"], str(ix_q))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  break_restart" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
