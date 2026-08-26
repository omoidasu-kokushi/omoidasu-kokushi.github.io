#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""過去問を**解き切ったあと**にアプリが壊れないかを見る（手動・テスト一式には入れない）

なぜ要るか
  これまでの通し検証（journey.py）は「400日つかって合格するところ」までだった。
  そこでは未解答も弱点も残っている。**残っているうちは、どのモードにも出す球がある。**

  本当に危ないのはその先で、
    ・本日の復習に1問も出ない
    ・弱点の概念が1つも無い
    ・未学習バッジが全部0
    ・トピックガードが候補を全部除外する
    ・いじわる模試（弱点120問）に集める弱点が無い
  という「球が無い」状態。ここは誰も通っていない。

使い方
    cd <repo> && python3 -m http.server 8900 &
    python3 tools/journey_all.py --import /path/past_import.json
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
APP  = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from journey_lib import *   # noqa

URL = "http://127.0.0.1:8900/index.html"
LOG = []
def say(m):
    print(m, flush=True); LOG.append(m)

FAILS = []
def C(name, cond, detail=""):
    ok = bool(cond)
    say(("  ok  " if ok else "  NG  ") + name + (("   << " + str(detail)) if detail else ""))
    if not ok: FAILS.append(name)
    return ok

# --- 1周ぶん、いま出せる球を全部さばく（本物のキューを使う） ---
SWEEP = r"""
async (cfg) => {
  const K = window.Scheduler, S = window.Storage;
  const out = { review:0, fresh:0, master:0, easy:0, hard:0 };
  let seed = cfg.seed;
  const rnd = () => { seed = (seed*1103515245+12345) & 0x7fffffff; return seed/0x7fffffff; };
  async function run(q, mode, cap) {
    const qs = (q && q.questions) || [];
    for (let i=0; i<qs.length && i<cap; i++) {
      const item = qs[i]; const atoms = item.atoms || [];
      if (!atoms.length) continue;
      const right = rnd() < cfg.accuracy;
      const evals = atoms.map(a => {
        let ev;
        if (!right) { ev = 'hard'; }
        else if (cfg.master && (a.srs_step||0) >= window.Scheduler.MASTER_UNLOCK_FROM) { ev = 'master'; }
        else { ev = 'easy'; }
        out[ev === 'master' ? 'master' : (ev === 'easy' ? 'easy' : 'hard')]++;
        return { atom_id:a.atom_id, eval:ev, is_correct:right };
      });
      await K.applyQuestionEvaluations(item.q_id, evals,
        { mode: mode, sessionId: 'A'+mode, thinkMs: 1200 + Math.floor(rnd()*6000) });
      if (mode === 'review') out.review++; else out.fresh++;
    }
  }
  const rq = await K.getReviewQueue(cfg.cap);
  await run(rq, 'review', cfg.cap);
  const left = cfg.cap - out.review;
  if (left > 0) {
    const nq = await K.buildQueue({ mode:'random', count:left, applyGuard:false });
    await run(nq, 'random', left);
  }
  return out;
}
"""

SNAP = r"""
async () => {
  const K = window.Scheduler, S = window.Storage;
  const h = await K.getHomeState();
  const raw = await K.computeLevelRaw();
  const lv = await K.computeLevel();
  const un = await K.refreshUnlocks();
  const u = {}; (un.unlocks||[]).forEach(x => u[x.id] = !!x.unlocked);
  const atoms = await S.getAllAtoms();
  let unlearned=0, hard=0, normal=0, easy=0, master=0;
  atoms.forEach(a => {
    const e = a.last_eval || null;
    if (!e) unlearned++;
    else if (e === 'hard') hard++;
    else if (e === 'normal') normal++;
    else if (e === 'easy') easy++;
    else if (e === 'master') master++;
  });
  return { date:new Date().toISOString().slice(0,10), due:h.due_count,
    level:lv.level, pct:lv.display_pct, raw_pct:raw.current_pct,
    by_level:raw.pct_by_level, done:raw.done_by_level, unlocks:u,
    atoms:atoms.length, unlearned, hard, normal, easy, master,
    theme:h.visual_theme || (lv.theme||null), scan:(await K.getScanAccuracy()).pct };
}
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--import", dest="imp", default=None, help="取り込む過去問JSON")
    ap.add_argument("--max-rounds", type=int, default=200)
    ap.add_argument("--cap", type=int, default=400, help="1周でさばく問題数")
    ap.add_argument("--accuracy", type=float, default=1.0,
                    help="正解率。Level 5（全アトムのマスター化）は定義上100%%でしか到達しない")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br, ctx, pg = new_page(pw)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        say("===== ① 起動して過去問を取り込む =====")
        pg.goto(a.url, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=180000)
        pg.wait_for_timeout(2000)
        try:
            pg.click("#welcome-start", timeout=4000); pg.wait_for_timeout(800)
        except Exception:
            pass
        tour_skip(pg); close_modals(pg)
        seed_n = pg.evaluate("window.Storage.countQuestions()")
        say("  同梱シード %d問" % seed_n)

        if a.imp:
            payload = open(a.imp, encoding="utf-8").read()
            imp = pg.evaluate("""async (txt) => {
              const t0 = performance.now();
              const r = await window.Storage.importText(txt);
              return { ms:Math.round(performance.now()-t0), imported:r.imported, updated:r.updated,
                       skipped:r.skipped, mismatch:r.mismatch, atoms:r.atoms,
                       tax_bad:r.tax_bad, tax_examples:(r.tax_examples||[]).slice(0,3),
                       pool_main:r.pool_main||0, pool_mock:r.pool_mock||0 };
            }""", payload)
            say("  取り込み: " + json.dumps(imp, ensure_ascii=False))
            # 抽出JSONの時点で flags が付いている14問（選択肢が画像だけ12・正答なし2）は
            # 取り込めなくて正しい。**黙って入れないこと**を見る。
            C("取り込めるものは全部入る（既知の欠損14問を除く）",
              imp["imported"] == 1200 - 14, json.dumps(imp, ensure_ascii=False))
            C("落とした問題を報告に出す（黙って捨てない）",
              imp["skipped"] == 14 and imp["mismatch"] == 2,
              "skipped=%s mismatch=%s" % (imp["skipped"], imp["mismatch"]))
            C("出題基準に無い分類が0", imp.get("tax_bad", 0) == 0,
              json.dumps(imp.get("tax_examples"), ensure_ascii=False))
            C("全部が本体プールに入る（模試送りが0）", imp["pool_mock"] == 0, imp["pool_mock"])
        pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
        s = pg.evaluate(SNAP)
        say("  問題 %d / 肢 %d" % (pg.evaluate("window.Storage.countQuestions()"), s["atoms"]))

        say("\n===== ② 解き切るまで回す =====")
        t0 = time.time(); prev = None
        for rd in range(1, a.max_rounds + 1):
            advance_days(pg, 1 if rd % 3 else 12, to_hour=7)
            r = pg.evaluate(SWEEP, {"accuracy": a.accuracy, "cap": a.cap, "seed": rd * 7919, "master": True})
            if rd % 10 == 0 or rd < 4:
                pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
                s = pg.evaluate(SNAP)
                say("  %3d周 %s Lv%d %s%% 未解答%d 難%d 普%d 易%d マ%d 復習待ち%d" % (
                    rd, s["date"], s["level"], s["pct"], s["unlearned"], s["hard"],
                    s["normal"], s["easy"], s["master"], s["due"]))
                if s["master"] == s["atoms"]:
                    say("  → 全アトムがマスターになった（%d周）" % rd); break
                if prev == (s["unlearned"], s["hard"], s["normal"], s["easy"], s["master"], s["due"]):
                    say("  → 状態が動かなくなった（%d周で打ち切り）" % rd); break
                prev = (s["unlearned"], s["hard"], s["normal"], s["easy"], s["master"], s["due"])
        say("  （%.0f秒）" % (time.time() - t0))
        pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
        s = pg.evaluate(SNAP)
        say("  最終: " + json.dumps(s, ensure_ascii=False))
        C("未解答アトムが0になる（Level 3）", s["unlearned"] == 0, s["unlearned"])
        C("難・普が0になる（Level 4）", s["hard"] == 0 and s["normal"] == 0,
          "難%d 普%d" % (s["hard"], s["normal"]))
        C("全アトムがマスターになる（Level 5）", s["master"] == s["atoms"],
          "%d/%d" % (s["master"], s["atoms"]))
        C("Level 5 に到達する", s["level"] >= 5, "Lv%d" % s["level"])
        C("表示100%になる", s["pct"] >= 100, "%s%%" % s["pct"])
        C("ここまでJSエラーが出ない", not errs, json.dumps(errs[:3], ensure_ascii=False))

        json.dump({"snapshot": s}, open(os.path.join(APP, "tmp_allmaster.json"), "w"), ensure_ascii=False)
        say("\n（この状態のまま、モードごとの確認へ）")
        globals()["PG"] = pg
        from journey_all_modes import check_modes   # noqa
        check_modes(pg, say, C, errs)

        say("\n===== まとめ =====")
        say("  失敗 %d件 %s" % (len(FAILS), FAILS if FAILS else ""))
        ctx.close()
        if br: br.close()
    sys.exit(1 if FAILS else 0)

main()
