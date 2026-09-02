#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2.08 検証：同梱データの版が上がったら、既存の見本問題だけ自動で最新になる

何が起きていたか：見本は「問題数0のとき1回だけ」入る設計で、V2.07 でシードに
マスタタグを追記しても既存の端末には届かず、更新後も旧タグのままだった
（クラウド検証で実測：更新後も inMaster 45/1817・テーマ14）。
V2.08：questions.js の SEED_VERSION と meta.seed_version を比べ、違えば
importText(seed, { onlyExisting:true }) で既存の見本だけ上書きし、版を記録する。

固定すること：
 1. 旧タグのDB（版未記録）を読み込み直すと、マスタタグが入り、版が記録される
 2. 学習の記録・★・メモは引き継がれる
 3. 消した見本問題は戻らない（onlyExisting）。全初期化後も見本は入らない
 4. 同じ版なら2回目は何もしない（更新0）
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def boot(pg, wait_version=True):
    pg.goto(APP_URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    if wait_version:
        # 初回取り込み／版更新は 200行ずつの非同期書き込み。版の記録は取り込み完了の
        # あとに立つので、これを待つ（待たないと途中の件数を数えてしまう）。
        # 注意：wait_for_function に Promise を返すと Promise 自体が真値で即通過する。
        # evaluate は Promise を待つので、Python側で回す。
        import time
        t0 = time.time()
        while time.time() - t0 < 60:
            if pg.evaluate("() => window.Storage.loadMeta().then(m => m.seed_version === window.SEED_VERSION)"):
                break
            pg.wait_for_timeout(200)
    pg.wait_for_timeout(800)
    pg.evaluate("() => { const M = window.Main; try { M.closeModals && M.closeModals(); } catch (e) {} }")


COVER = """async () => {
  const M = new Set(window.CONCEPT_TAGS_MASTER.map(x => x.tag));
  const S = window.Storage;
  const qs = await S.getAllQuestions();
  let total = 0, hit = 0; const themes = new Set();
  for (const q of qs) for (const a of await S.getAtomsByQuestion(q.q_id))
    for (const t of (a.tags || [])) { total++; if (M.has(t)) { hit++; themes.add(t); } }
  const meta = await S.loadMeta();
  return { questions: qs.length, total, hit, themes: themes.size,
           seed_version: meta.seed_version || null, SEED_VERSION: window.SEED_VERSION }; }"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context()
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    boot(pg)

    c0 = pg.evaluate(COVER)
    ok("初回取り込みで版が記録される", c0["seed_version"] == c0["SEED_VERSION"] and c0["questions"] == 453,
       json.dumps(c0, ensure_ascii=False))

    # --- 旧端末を再現：マスタタグを剥がした旧シードを入れ、版の記録を消す ---
    old = pg.evaluate("""async () => {
      const M = new Set(window.CONCEPT_TAGS_MASTER.map(x => x.tag));
      const rows = window.SEED_QUESTIONS_TSV.split('\\n').map(line => {
        const c = line.split('\\t');
        try { const t2 = JSON.parse(c[11]);
              c[11] = JSON.stringify(t2.map(a => a.filter(t => !M.has(t)))); } catch (e) {}
        return c.join('\\t'); });
      const rep = await window.Storage.importText(rows.join('\\n'));
      const K = window.Scheduler, S = window.Storage;
      const q = (await S.getAllQuestions())[0];
      const atoms = await S.getAtomsByQuestion(q.q_id);
      await K.applyQuestionEvaluations(q.q_id, atoms.map(a => ({ atom_id:a.atom_id, eval:'easy', is_correct:true })),
                                       { mode:'random', sessionId:'R', thinkMs:1200 });
      await S.setMeta('seed_version', null);
      const a2 = await S.getAtomsByQuestion(q.q_id);
      return { updated: rep.updated, q_id: q.q_id, step: a2[0].srs_step, due: a2[0].due_date,
               logs: await S.countLogs() }; }""")
    c1 = pg.evaluate(COVER)
    ok("旧タグの端末を再現できた（マスタ内0・版なし）", c1["hit"] == 0 and c1["seed_version"] is None,
       json.dumps(c1, ensure_ascii=False))

    # --- 読み込み直し＝アプリ更新後の起動。自動で最新になるか ---
    boot(pg)
    c2 = pg.evaluate(COVER)
    ok("**読み込み直すだけで、既存の見本問題が最新のタグになる**",
       c2["hit"] > 1000 and c2["themes"] >= 40 and c2["questions"] == 453, json.dumps(c2, ensure_ascii=False))
    ok("版が記録される（2回目は走らない）", c2["seed_version"] == c2["SEED_VERSION"], c2["seed_version"])
    after = pg.evaluate("""async (qid) => {
      const S = window.Storage; const a = await S.getAtomsByQuestion(qid);
      return { step: a[0].srs_step, due: a[0].due_date, logs: await S.countLogs(),
               tags: a[0].tags.length }; }""", old["q_id"])
    ok("学習の記録は引き継がれる（srs_step・期日・ログ数）",
       after["step"] == old["step"] and after["due"] == old["due"] and after["logs"] == old["logs"],
       json.dumps({"before": old, "after": after}, ensure_ascii=False))
    ok("自由タグを消さずに足している", after["tags"] >= 2, after["tags"])

    # --- 消した見本は戻らない：全初期化→印を立てる→読み込み直し ---
    pg.evaluate("""async () => { await window.Storage.resetAll(); await window.Storage.setMeta('seed_imported', true); }""")
    boot(pg, wait_version=False)
    pg.wait_for_timeout(2500)
    c3 = pg.evaluate(COVER)
    ok("**全初期化で消した見本は、版更新でも戻らない**", c3["questions"] == 0, json.dumps(c3, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCF" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
