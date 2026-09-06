# -*- coding: utf-8 -*-
"""test_pomo_resume.py — 時計は1本（V2.71）

利用者の指摘：
  「他のモードでポモドーロ使ってるときにランダムモードに移動したときに、
   元のポモドーロが継続しちゃってる場合はどう処理する?
   理想は残り○○分間出題します。みたいなポップアップが出て
   勝手に出題される感じがいい。」

V2.70 での実測（不具合）：
  ポモドーロ残り5分の状態でランダムを「時間で区切る・25分」で始めると、
  ヘッダーは残り5分、ランダムのHUDは残り25分。**時計が2本**動き、
  5分後に「25分経過しました」、その20分後にセッション終了、と
  区切りが2回来ていた。V2.69 で入れた不具合。

V2.71：
  ポモドーロが動いていれば、その残りがそのまま区切りになる。
  始める前に「残り○○で区切ります」を告げる。
  残り3分未満のときだけ既定を［先に5分休憩する］に変える。

ここで固定するのは7つ。
  ① ポモドーロが効いていないときは案内を出さない（選んだ分数で切る）
  ② 動いているときは案内が出て、残り時間が本文に出る
  ③ ［このまま始める］でHUDとヘッダーの数字が一致する（時計が1本）
  ④ ［25分にし直す］で25分に戻る
  ⑤ 残り3分未満は既定が［先に5分休憩する］に変わる
  ⑥ 休憩を選んだら出題は始まらない
  ⑦ ポモドーロで区切れて終わったときだけ、内訳に休憩ボタンが出る
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

ok("開始前の案内が置いてある", 'id="modal-pomo-resume"' in ix and 'id="pr-go"' in ix and 'id="pr-fresh"' in ix)
ok("内訳から休憩へ行けるボタンがある", 'id="sess-break"' in ix)
ok("ポモドーロの残りを外へ出している", "function pomodoroLeftMs" in p1)
ok("25分にし直す口がある", "function restartPomodoro" in p1)
ok("HUDはポモドーロの残りを映す（別々に数えない）", "st.random.fromPomo\n      ? M.pomodoroLeftMs()" in p2)
ok("二重に鳴らさない仕掛けがある", "M.state.pomodoro.notified = true;" in p2)
ok("3分の閾値がコードにある", "POMO_RESUME_MIN_MS" in p2)
ok("なぜ3分で切るかが書いてある", "区切って休む" in p2)
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

    # ① ポモドーロOFF
    a = pg.evaluate("""async () => {
      const M = window.Main, H = window.Half2Impl;
      await M.setPomodoroEnabled(false); M.stopPomodoro();
      H.st.random.limit = 'time'; H.st.random.minutes = 10;
      H.startRandom(null, 10);
      await new Promise(r => setTimeout(r, 700));
      return { pop: !document.getElementById('modal-pomo-resume').hidden,
               hud: document.getElementById('knock-concept').textContent,
               clock: document.getElementById('knock-count').textContent };
    }""")
    ok("ポモドーロOFFなら案内を出さない", a["pop"] is False, json.dumps(a, ensure_ascii=False))
    ok("OFFなら選んだ分数で切る（10分）", a["clock"].startswith("10:") or a["clock"].startswith("09:5"),
       json.dumps(a, ensure_ascii=False))
    ok("OFFのHUD見出しは「時間で区切る」", a["hud"] == "時間で区切る", str(a["hud"]))

    # ② 残り18分
    b = pg.evaluate("""async () => {
      const M = window.Main, H = window.Half2Impl;
      M.endSession(); M.closeModals();
      await M.setPomodoroEnabled(true);
      await M.startSession({ mode: 'unit', count: 5 });
      M.startPomodoro();
      M.state.pomodoro.startedAt = Date.now() - 7 * 60 * 1000;
      M.state.pomodoro.lastActiveAt = Date.now();
      H.st.random.limit = 'time'; H.st.random.minutes = 25;
      H.startRandom(null, 10);
      await new Promise(r => setTimeout(r, 400));
      return { pop: !document.getElementById('modal-pomo-resume').hidden,
               title: document.getElementById('pr-title').textContent,
               body: document.getElementById('pr-body').textContent,
               go: document.getElementById('pr-go').textContent };
    }""")
    ok("動いているときは案内が出る", b["pop"], json.dumps(b, ensure_ascii=False))
    ok("見出しは「ポモドーロの続きです」", b["title"] == "ポモドーロの続きです", str(b["title"]))
    ok("残り時間が本文に出る（18:00）", "18:0" in b["body"], str(b["body"]))
    ok("主ボタンは「このまま始める」", b["go"] == "このまま始める", str(b["go"]))

    # ③ このまま始める → 時計が1本
    c = pg.evaluate("""async () => {
      document.getElementById('pr-go').click();
      await new Promise(r => setTimeout(r, 700));
      return { hud: document.getElementById('knock-count').textContent,
               head: document.getElementById('pomodoro-time').textContent,
               label: document.getElementById('knock-concept').textContent,
               left: Math.round(window.Main.pomodoroLeftMs() / 60000) };
    }""")
    ok("HUDとヘッダーの数字が一致する（時計は1本）", c["hud"] == c["head"], json.dumps(c, ensure_ascii=False))
    ok("HUDの見出しは「ポモドーロの続き」", c["label"] == "ポモドーロの続き", str(c["label"]))
    ok("区切りはポモドーロの残り（18分）", c["left"] == 18, str(c["left"]))

    # ④ 25分にし直す
    d = pg.evaluate("""async () => {
      const M = window.Main, H = window.Half2Impl;
      M.endSession(); M.closeModals();
      M.state.pomodoro.running = true;
      M.state.pomodoro.startedAt = Date.now() - 10 * 60 * 1000;
      M.state.pomodoro.lastActiveAt = Date.now();
      H.st.random.limit = 'time';
      H.startRandom(null, 10);
      await new Promise(r => setTimeout(r, 400));
      document.getElementById('pr-fresh').click();
      await new Promise(r => setTimeout(r, 700));
      return { left: Math.round(M.pomodoroLeftMs() / 60000),
               hud: document.getElementById('knock-count').textContent };
    }""")
    ok("［25分にし直す］で25分に戻る", d["left"] == 25, json.dumps(d, ensure_ascii=False))

    # ⑤⑥ 残り2分
    e = pg.evaluate("""async () => {
      const M = window.Main, H = window.Half2Impl;
      M.endSession(); M.closeModals();
      M.state.pomodoro.running = true;
      M.state.pomodoro.startedAt = Date.now() - 23 * 60 * 1000;
      M.state.pomodoro.lastActiveAt = Date.now();
      H.st.random.limit = 'time';
      H.startRandom(null, 10);
      await new Promise(r => setTimeout(r, 400));
      const go = document.getElementById('pr-go').textContent;
      const title = document.getElementById('pr-title').textContent;
      /* 「新しい出題が始まっていないこと」を見る。画面のidでは、
         直前のセッションの画面が残っているだけで誤判定する（実測）。 */
      const before = (window.Main.state.session || {}).startedAt || 0;
      document.getElementById('pr-go').click();
      await new Promise(r => setTimeout(r, 600));
      const after = (window.Main.state.session || {}).startedAt || 0;
      return { go: go, title: title,
               breakOpen: !document.getElementById('modal-break').hidden,
               sameSession: before === after,
               hudMounted: !document.getElementById('knock-hud').hidden };
    }""")
    ok("残り3分未満は見出しが変わる", e["title"] == "ポモドーロはもうすぐ終わります", str(e["title"]))
    ok("残り3分未満は既定が［先に5分休憩する］", e["go"] == "先に5分休憩する", str(e["go"]))
    ok("休憩を選んだら休憩が始まる", e["breakOpen"], json.dumps(e, ensure_ascii=False))
    ok("休憩を選んだら新しい出題は始まらない",
       e["sameSession"] and not e["hudMounted"], json.dumps(e, ensure_ascii=False))

    # ⑦ 内訳の休憩ボタン
    f = pg.evaluate("""() => {
      const H = window.Half2Impl;
      H.st.random.endedByPomo = false;
      const off = window.Half2.endedByPomodoro();
      H.st.random.endedByPomo = true;
      const on = window.Half2.endedByPomodoro();
      H.st.random.endedByPomo = false;
      return { off: off, on: on };
    }""")
    ok("ポモドーロ由来かどうかを外から見られる", f["off"] is False and f["on"] is True, json.dumps(f))

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
print("\n%d/%d  pomo_resume" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
