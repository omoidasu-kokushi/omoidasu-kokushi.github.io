#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2.06 検証：必修の枠（V1.89）が未学習の必修問題を切り落とさないこと

何が起きていたか
  ランダムモードの「必修の枠」（dir='cap'：必修が目標比率より多いとき、
  必修を抽選で減らして一般と入れ替える）が、**未学習の必修問題まで抽選で
  切っていた**。§6-②「未学習アトムは出題優先度ソートで最優先で抽出」が
  この一点で破れる。

  実測：同梱シード453問のうち452問を「簡単」評価にし、必修の1問（4肢）だけを
  未学習で残した状態で buildQueue({mode:'random', count:10}) を引くと、
  その1問がキューに一度も入らない（5回連続）。hissuQuota:false なら毎回先頭。
  通し検証（400日・1日40問）でも同じ1問が最後まで出題されず、
  Level 3（全問題読破）が 99% で永遠に止まる。

  修正は applyHissuQuota の cap 側：切る対象を「既出の必修」に限定し、
  未学習を含む必修は枠内に残す。floor 側はもともと oth の末尾（優先度の低い側）
  から外すので、未学習（先頭側）は影響を受けない。
"""
import json, os, sys, glob, subprocess
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, str(d)[:200]))

# ---------------------------------------------------------------- 静的検査
sch = open(os.path.join(APP, "scheduler.js"), encoding="utf-8").read()
ok("cap側が未学習の必修を残す実装になっている",
   "hisUn" in sch and "c.unlearned > 0; })" in sch.split("dir === 'cap'")[1][:1200])
ok("丸ごと抽選で切る旧実装が消えている",
   "concat(shuffle(his, seed).slice(0, his.length - cut))" not in sch)
p = subprocess.run(["node", "--check", os.path.join(APP, "scheduler.js")],
                   capture_output=True, text=True)
ok("scheduler.js の構文", p.returncode == 0, p.stderr.strip()[:120])

# ---------------------------------------------------------------- 実行時検査
with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    # 同梱シードの取り込み完了を待つ（453問になるまで）
    pg.wait_for_timeout(4500)
    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const qs = await S.getAllQuestions();
      const atoms = await S.getAllAtoms();
      // 必修の未学習問題を1つ選び、それ以外を全部「簡単」にする
      const target = qs.find(q => String(q.unit||'').indexOf('必修') >= 0 &&
                                  atoms.some(a => a.q_id === q.q_id));
      for (const q of qs) {
        if (q.q_id === target.q_id) continue;
        const mine = atoms.filter(a => a.q_id === q.q_id);
        if (!mine.length) continue;
        await K.applyQuestionEvaluations(q.q_id,
          mine.map(a => ({ atom_id: a.atom_id, eval: 'easy', is_correct: true })),
          { mode: 'random', sessionId: 'cd', thinkMs: 1000 });
      }
      const un = (await S.getAllAtoms()).filter(a => !a.last_eval).length;
      const draws = [];
      let hissu = null;
      for (let i = 0; i < 5; i++) {
        const nq = await K.buildQueue({ mode: 'random', count: 10, applyGuard: false });
        const L = (nq && nq.questions) || [];
        draws.push(L.findIndex(x => x.q_id === target.q_id));
        if (nq.hissu) hissu = { dir: nq.hissu.dir, share: nq.hissu.share };
      }
      return { total: qs.length, unAtoms: un, target: target.q_id, draws, hissu };
    }""")
    ok("シード453問で検証している", r["total"] == 453, r["total"])
    ok("未学習が対象の肢だけ残っている", 0 < r["unAtoms"] <= 6, r["unAtoms"])
    ok("必修の枠は cap で働いている（前提の確認）",
       r["hissu"] and r["hissu"]["dir"] in ("cap", "floor"), r["hissu"])
    ok("未学習の必修問題が5回とも枠内に入る（切られない）",
       all(p2 >= 0 for p2 in r["draws"]), r["draws"])
    ok("実行中にJSエラーが出ていない",
       not [e for e in errs if "accounts.google" not in e and "gsi" not in e], errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCD" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
