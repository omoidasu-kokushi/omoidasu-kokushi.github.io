#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCR：模試の○×は太く、根拠チェックの説明は［？］でいつでも読める（V2.23）

何が起きていたか（利用者フィードバック）：
1. 模試の復習で出る○×が細くて目に入らない
2. 根拠チェック☐の説明が初回の1回だけ。聞き流すと「なんだっけこれ」に戻れない
直し方：○×はfont-size 1.45em＋text-strokeで太く。説明は初回だけ開いた状態、
以後は選択肢の上に［？ 右の☐チェックとは］が常設され、押すと開閉する。
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
js1, css = read(p1), read("styles.css")
ok("○×が太く大きい", "font-size:1.45em" in css and "text-stroke" in css)
ok("［？］が常設される（初回だけの分岐をやめた）", "ground-help-btn" in js1 and "if (exam) {" in js1)
ok("初回は開いた状態", "var open = !state.groundHintShown" in js1)

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
      const origU = S.getUnlockState;
      S.getUnlockState = () => Promise.resolve([{ id: 'mock_30', unlocked: true }]);
      const origW = K.shouldWarnBeforeExam;
      K.shouldWarnBeforeExam = async () => ({ warn: false });
      await H.startExam('mock_30', 'real');
      S.getUnlockState = origU; K.shouldWarnBeforeExam = origW;
      const until = async (f) => { for (let i = 0; i < 100; i++) { if (f()) return true;
        await new Promise(r => setTimeout(r, 50)); } return false; };
      await until(() => M.state.session && M.state.session.mode === 'exam' && M.state.current);
      const btn = document.querySelector('.ground-help-btn');
      const hint = document.querySelector('.ground-hint');
      out.btnShown = !!btn;
      out.openFirst = !!(hint && !hint.hidden);
      btn.click(); out.closed = hint.hidden;      /* 閉じる */
      btn.click(); out.reopened = !hint.hidden;   /* もう一度開ける＝常設 */
      /* 次の問題でもボタンが居る */
      const cur = M.state.current; cur.selected = [cur.atoms[0].original_num]; M.confirmAnswer();
      await new Promise(r => setTimeout(r, 250));
      const btn2 = document.querySelector('.ground-help-btn');
      const hint2 = document.querySelector('.ground-hint');
      out.persistsNextQ = !!btn2;
      out.collapsedNextQ = !!(hint2 && hint2.hidden);   /* 2問目以降は畳まれている */
      return out;
    }""")
    ok("模試1問目：［？］が出て説明が開いている", r["btnShown"] and r["openFirst"], json.dumps(r))
    ok("押すと閉じ、もう一度押すと開く", r["closed"] and r["reopened"], json.dumps(r))
    ok("2問目以降も［？］は残り、説明は畳まれている", r["persistsNextQ"] and r["collapsedNextQ"], json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for g, name, detail in R:
    print(("  ok  " if g else "  NG  ") + name + (("   << " + detail) if (detail and not g) else ""))
print("\n%d/%d  batchCR" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
