#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCO：「難しい」の最短段は20分。旧'10m'データも同じ段として読める（V2.20）

利用者裁定（2026-09-06）：10分後は4択だと「さっき見た答えの表面記憶」で
正解してしまいやすい。最短段を20分へ。
互換：コードは '20m' 新設。保存済みの '10m'（atoms / logs / 同期台帳）は
書き換えず、STEP_INDEX のエイリアスで同じ段として読み続ける。
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
ok("梯子の先頭が20分", "{ code: '20m',  ms: 20 * MIN,  label: '20分後'" in kjs)
ok("旧10mのエイリアスがある", "STEP_INDEX['10m'] = STEP_INDEX['20m']" in kjs)
ok("緊急度は20mと10mが同格", "'20m': 0, '10m': 0" in kjs)
ok("割り込み候補は20mも拾う", "plan.interval_code === '20m' || plan.interval_code === '10m'" in kjs)
ok("裁定の理由が書いてある", "表面記憶" in kjs)

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
    pg.wait_for_timeout(1000)

    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const atoms = await S.getAllAtoms();
      const a = atoms[0];
      const t0 = Date.now();
      await K.applyQuestionEvaluations(a.q_id, [
        { atom_id: a.atom_id, eval: 'hard', is_correct: false }],
        { mode: 'random', sessionId: 'CO' });
      const saved = await S.getAtom(a.atom_id);
      const logs = await S.getLogsByAtom(a.atom_id);
      const last = logs[logs.length - 1];
      const diffMin = (saved.due_date - t0) / 60000;
      return { code: saved.interval_code, logCode: last.interval_code,
               diffMin: Math.round(diffMin),
               okRange: diffMin >= 19 && diffMin <= 21 };
    }""")
    ok("難しい→interval_codeが'20m'になる", r.get("code") == "20m", json.dumps(r))
    ok("ログにも'20m'が入る", r.get("logCode") == "20m", json.dumps(r))
    ok("期日が約20分後になる", r.get("okRange") is True, json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCO" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
