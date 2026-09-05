#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCN：期日前ミスの評価は「既定は難・普通へ押し直し可」（V2.19・利用者裁定）

何が起きていたか：
期日前に間違えた肢は、UIが評価群ごとロックパネルに差し替えられ、
スケジューラも押された評価に関わらず「難しい」へ強制していた。
うっかりミスと本当の忘却を利用者が区別できなかった（利用者指摘・裁定済み）。

直し方：
・UI：期日前ミスでも評価群を出す。既定点灯は「難しい」のまま、「普通」は押せる。
　「易しい」「マスター」は disabled（開けると期日前の昇格を手動で作れてしまう＝従来の門番）
・スケジューラ：demote時は NORMAL だけ通し、それ以外は従来どおり HARD へ
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
js1, kjs, css = read(p1), read("scheduler.js"), read("styles.css")
ok("スケジューラ：demoteでもNORMALだけ通す", "evalKey === EVAL.NORMAL ? EVAL.NORMAL : EVAL.HARD" in kjs)
ok("門番の理由が残っている", "期日前の昇格を手動で作れてしまう" in kjs)
ok("UI：期日前ミスでも評価群を出す", "demoteNote" in js1 and "eval-demote-note" in js1)
ok("UI：易・マスターは押せない", "dec.demote && (e.k === 'easy' || e.k === 'master')" in js1)
ok("注記のスタイルがある", ".eval-demote-note" in css)
ok("旧・強制ロック文言が消えている", "に戻します</b>" not in js1 and "「難しい」</b>に戻します" not in js1)

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
      const byQ = {};
      atoms.forEach(a => { (byQ[a.q_id] = byQ[a.q_id] || []).push(a); });
      const qids = Object.keys(byQ).filter(q => byQ[q].length >= 2).slice(0, 2);
      const out = {};

      /* 事前に「易しい」（30日）で解いて長期ステップ＋期日未来に置く（門番はGATED_STEPS限定） */
      const prep = async (qid) => {
        await K.applyQuestionEvaluations(qid, byQ[qid].map(a => (
          { atom_id: a.atom_id, eval: 'easy', is_correct: true })),
          { mode: 'random', sessionId: 'CN' });
      };
      const lastLog = async (aid) => {
        const logs = await S.getLogsByAtom(aid);
        return logs[logs.length - 1];
      };

      /* ケース1：期日前ミス＋「普通」を押した → 普通が通り early_miss が付く */
      await prep(qids[0]);
      const a1 = byQ[qids[0]][0].atom_id;
      await K.applyQuestionEvaluations(qids[0], [
        { atom_id: a1, eval: 'normal', is_correct: false }],
        { mode: 'random', sessionId: 'CN' });
      const l1 = await lastLog(a1);
      out.normalAllowed = l1.eval === 'normal';
      out.earlyMissFlag = l1.early_miss === true;

      /* ケース2：期日前ミス＋「易しい」を押した → 従来どおり難しいへ */
      await prep(qids[1]);
      const a2 = byQ[qids[1]][0].atom_id;
      await K.applyQuestionEvaluations(qids[1], [
        { atom_id: a2, eval: 'easy', is_correct: false }],
        { mode: 'random', sessionId: 'CN' });
      const l2 = await lastLog(a2);
      out.easyClamped = l2.eval === 'hard';
      out.earlyMissFlag2 = l2.early_miss === true;
      return out;
    }""")
    ok("期日前ミスで「普通」が通る", r.get("normalAllowed") is True, json.dumps(r))
    ok("early_missの印は付く", r.get("earlyMissFlag") is True, json.dumps(r))
    ok("「易しい」は従来どおり難しいへ", r.get("easyClamped") is True, json.dumps(r))
    ok("その場合もearly_missが付く", r.get("earlyMissFlag2") is True, json.dumps(r))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCN" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
