#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCR：復習の○×は太く、☐の説明はいつでも読める（V2.23 → V3.10 で作り直し）

【もともと何を見ていたか（V2.23・利用者フィードバック）】
1. 模試の復習で出る○×が細くて目に入らない
2. 根拠チェック☐の説明が初回の1回だけ。聞き流すと「なんだっけこれ」に戻れない
   直し方：○×はfont-size 1.45em＋text-strokeで太く。説明は選択肢の上の［？］を押すといつでも開く
   （V3.03 で［？］は☐列の上の小さい印にし、既定は閉じた）

【なぜ書き換えたか（V3.10・2026-09-12・利用者裁定）】
・模試が1枚の問題用紙になり、解答画面（part1 renderChoices）を通らなくなった。［？］もそこにあったので消えた。
・**「説明にいつでも戻れる」という要求は消えていない**。置き場所が変わっただけで、
  いまは問題用紙の前書き（.paper-lead）に**常に出ている**（押す操作すら要らない＝V2.23 の要求より強い）。

このバッチが見るもの：
  ○×が太いこと／☐の説明が押さずに読めること／1文に流れていること（V3.08）／［？］の分岐が残っていないこと
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
js1, css, html = read(p1), read("styles.css"), read("index.html")
ok("○×が太く大きい", "font-size:1.45em" in css and "text-stroke" in css)
ok("☐の説明は問題用紙の前書きに常にある（押す操作が要らない）",
   "自由に使える印です" in html and "評価には影響しません" in html and 'class="sc-lead paper-lead"' in html)
ok("［？］の分岐は残っていない（置き場所が変わったので消した）",
   "ground-help-btn" not in js1 and "var open = !state.groundHintShown" not in js1)

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
      const wait = (ms) => new Promise(r => setTimeout(r, ms));
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      S.getExamHistory = () => Promise.resolve([]);
      await H.startExam('mock_30', 'real');
      for (let i = 0; i < 100; i++) { if (M.state.session && M.state.session.mode === 'exam'
        && document.getElementById('screen-exam-paper').classList.contains('is-active')) break; await wait(50); }
      M.closeModals();
      const lead = document.querySelector('#screen-exam-paper .paper-lead');
      out.leadShown = !!lead && lead.offsetParent !== null && getComputedStyle(lead).display !== 'none';
      out.leadText = lead ? lead.textContent : '';
      out.saysFree = /自由に使える印/.test(out.leadText) && /評価には影響しません/.test(out.leadText);
      /* V3.08：1文に流れていること（flex で「右の／☐／は…」と3つに割れていた） */
      out.oneLine = !!lead && getComputedStyle(lead).display.indexOf('flex') < 0;
      out.noHelpBtn = !document.querySelector('.ground-help-btn');
      /* 30問ぶん全部に☐がある（説明の対象が全問にある） */
      out.marksEverywhere = document.querySelectorAll('#paper-list .choice-mark[data-kind="ground"]').length
        === document.querySelectorAll('#paper-list .choice-card').length;
      return out;
    }""")
    ok("問題用紙を開いた時点で説明が見えている（押さなくてよい）", r["leadShown"], json.dumps(r, ensure_ascii=False)[:200])
    ok("「自由に使える印」「評価には影響しません」と書いてある", r["saysFree"], r["leadText"][:120])
    ok("説明は1文に流れている（V3.08 の直しが生きている）", r["oneLine"] and r["noHelpBtn"])
    ok("☐は全問の全肢にある", r["marksEverywhere"])
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for g, name, detail in R:
    print(("  ok  " if g else "  NG  ") + name + (("   << " + detail) if (detail and not g) else ""))
print("\n%d/%d  batchCR" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
