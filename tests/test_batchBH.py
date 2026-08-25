#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBH：達成していないのに100%と出さない（V1.83）

インストールから合格までを400日ぶん通しで走らせたとき（`tools/journey.py`）、
**残り20肢（5,448中）のまま Level 4 が「100%」と表示され、
それ以上どうやっても進まない**状態になった。`Math.round(99.633)` が 100 だったため。

バーが満タンなのに次へ行かないのは、利用者からは不具合にしか見えない。
しかも「あと何をすればいいか」も画面から消える。
さらに高水位（max_pct_lvN）に 100 が焼き付くと、未達成のまま
「AREA CLEARED!」が出続ける。
"""
import io, json, os, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

kjs = read("scheduler.js")
ok("未達成なら99で止める関数がある", "function shown(n)" in kjs and "return 99;" in kjs)
ok("current_pct も pct_by_level も同じ関数を通す",
   "current_pct: shown(level)" in kjs and "1: shown(1), 2: shown(2)" in kjs)
ok("なぜ切り捨てではなく99なのかが書いてある", "「100% ＝ 達成」を崩さない" in kjs)
ok("高水位に焼き付く話が書いてある", "AREA CLEARED" in kjs and "焼き付" in kjs)
# 版番号を絶対値で書かない（batchAC が「上がっているか」を見ている）。
# ここで直書きすると、次の版で必ず赤くなる。V1.82→V1.83 で実際に踏んだ。
ok("版の表記が1箇所にまとまっている", 'id="build-stamp-settings"' in read("index.html"))

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1800)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(700)

    # Level 4 まであと1肢だけ残す（＝99.98%）。四捨五入なら100%になる状態。
    r = pg.evaluate("""async (leaveHard) => {
      const S = window.Storage, K = window.Scheduler;
      const atoms = await S.getAllAtoms();
      const now = Date.now(), patch = {};
      atoms.forEach((a, i) => {
        patch[a.atom_id] = { answer_count: 1, correct_count: 1,
          last_eval: (i < leaveHard ? 'normal' : 'easy'),
          last_answered_at: now - 86400000, srs_step: 4, interval_code: '30d',
          due_date: now + 86400000 * 30 };
      });
      await S.updateAtomsBulk(patch);
      const raw = await K.computeLevelRaw();
      const lv = await K.computeLevel();
      const m = await S.loadMeta();
      return { total: atoms.length, raw4: raw.pct_by_level[4], done4: raw.done_by_level[4],
               level: raw.level, display: lv.display_pct, cleared: lv.theme_cleared,
               max4: m.max_pct_lv4 };
    }""", 1)
    ok("あと1肢でも100%とは出さない", r["raw4"] == 99 and r["done4"] is False, json.dumps(r))
    ok("表示（不退転を通したあと）も100%にならない", r["display"] < 100, json.dumps(r))
    ok("未達成のまま「クリア」にならない", r["cleared"] is False, json.dumps(r))
    ok("高水位にも100が焼き付かない", r["max4"] < 100, json.dumps(r))
    ok("達成扱いにならない（＝先へ進まない）", r["done4"] is False, json.dumps(r))

    # 最後の1肢を片づけたら、その瞬間に100%＆レベルが進む
    r2 = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const atoms = await S.getAllAtoms();
      const patch = {};
      atoms.forEach(a => { if (a.last_eval === 'normal') patch[a.atom_id] = { last_eval: 'easy' }; });
      await S.updateAtomsBulk(patch);
      const raw = await K.computeLevelRaw();
      const lv = await K.computeLevel();
      return { raw4: raw.pct_by_level[4], done4: raw.done_by_level[4],
               level: raw.level, display: lv.display_pct, cleared: lv.theme_cleared };
    }""")
    ok("片づけた瞬間に100%になる", r2["raw4"] == 100 and r2["done4"] is True, json.dumps(r2))
    ok("そこで初めて達成扱いになる", r2["done4"] is True, json.dumps(r2))
    ok("100%と達成が同時に立つ（片方だけ先に立たない）",
       (r2["raw4"] == 100) == (r2["done4"] is True), json.dumps(r2))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBH" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
