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

【V1.01】--profile を足した。**⑧が一度も完走していなかった**ため。

  ⑧「いじわる模試を120問UIから最後まで」はUI操作で約100秒かかる。
  ②「解き切るまで回す」だけで数十秒あるので、①〜⑧を1回で通すと
  MCP経由のシェルの2分の壁を越え、⑧は毎回途中で切られていた。
  JALL_FROM/JALL_TO で節は選べるが、③以降は
  **②で作った「全部マスター」の状態が要る**ので、単独では走らない。

  そこで、②までを1回走らせてブラウザのプロファイル（IndexedDB ごと）を
  ディスクに残し、次の呼び出しはその続きから始められるようにする。

    1回目  python3 tools/journey_all.py --import <json> --profile /tmp/jp --stop-after 2
    2回目  python3 tools/journey_all.py --profile /tmp/jp --resume     （JALL_FROM=8 JALL_TO=8）

  --resume のときは取り込みも②も走らせない。プロファイルの中身をそのまま使う。

【V1.02】①の取り込みが**毎回全滅していた**。原因は渡すファイルの取り違え。

  ext_v4.json は**機械抽出の生データ**で、キーは
    choices / correct / flags / kai / lead / multi / num / numeric_answer /
    session / source / stem / type
  の12個。**atoms が無い**（分類 unit/major/medium/target も無い）。
  取り込み側は stem と atoms を要るので、1,200問すべてが
  「stem または atoms がありません」で弾かれていた（実測：imported 0／skipped 1200／2ms）。

  そのため、この通しは**同梱シード453問だけで回っていた**。
  1,200問の規模で見ているつもりが、見ていなかった。

  さらに、期待値に 1200 と 14 を直接書いていたのも誤り。
  atoms 付きで1,200問のファイルは**存在しない**（仕上げが終わった分しか atoms は無い）。
  実測：いちばん多いもので916問（20260908_配布_V1.00.json）。
  数を埋め込まず、**入力そのものから期待値を作る**ように変えた。

  渡すのは「仕上げが終わって取り込める形になったもの」。
    分類_令和5年版/out/20260908_配布_V1.00.json   （916問・照合パッチ適用済み）
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
    # V1.01：2分の壁をまたぐための3つ。既定では今までと同じ動きをする。
    ap.add_argument("--profile", default=None,
                    help="ブラウザのプロファイルを置く場所。IndexedDB ごと残る")
    ap.add_argument("--stop-after", type=int, default=0,
                    help="この節まで終えたら止める（2＝解き切ったところで止める）")
    ap.add_argument("--resume", action="store_true",
                    help="取り込みも②も走らせない。--profile の続きから始める")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br, ctx, pg = new_page(pw, profile=a.profile)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        if a.resume:
            say("===== 続きから（--resume）=====")
            say("  取り込みも②も走らせません。プロファイルの中身をそのまま使います。")
            pg.goto(a.url, wait_until="load")
            pg.wait_for_function("window.__APP_READY === true", timeout=180000)
            pg.wait_for_timeout(1500)
            tour_skip(pg); close_modals(pg)
            pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
            s = pg.evaluate(SNAP)
            say("  いまの状態: " + json.dumps(s, ensure_ascii=False))
            C("続きから始められている（未解答が0＝②を通ったあと）",
              s["unlearned"] == 0, "未解答%d" % s["unlearned"])
            globals()["PG"] = pg
            from journey_all_modes import check_modes   # noqa
            check_modes(pg, say, C, errs)
            say("\n===== まとめ =====")
            say("  失敗 %d件 %s" % (len(FAILS), FAILS if FAILS else ""))
            ctx.close()
            if br: br.close()
            sys.exit(1 if FAILS else 0)

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
            # V1.02：数を埋め込まない。**入力そのものから期待値を作る**。
            _src = json.loads(payload)
            _qs = _src.get("questions") if isinstance(_src, dict) else _src
            _n = len(_qs)
            # 入力のうち、そもそも取り込めない形のもの（stem か atoms が無い）を数える。
            # 生の抽出JSONを間違って渡したときに、それが一目で分かるようにする。
            _broken = sum(1 for q in _qs
                          if not (q.get("stem") and (q.get("atoms") or [])))
            say("  入力 %d問（うち stem か atoms が無いもの %d問）" % (_n, _broken))
            C("生の抽出JSONではなく、取り込める形のものを渡している",
              _broken == 0,
              "" if _broken == 0 else
              "%d問に atoms が無い。ext_v4.json のような抽出直後のファイルは"
              " atoms を持たないので、仕上げ後のファイルを渡すこと" % _broken)
            C("入ったものと弾いたものの合計が、入力の数と合う",
              imp["imported"] + imp["updated"] + imp["skipped"] == _n,
              "入%d 更%d 弾%d ／ 入力%d"
              % (imp["imported"], imp["updated"], imp["skipped"], _n))
            C("黙って捨てていない（弾いたぶんは報告に出る）",
              imp["skipped"] == 0 or imp["skipped"] == _broken,
              "skipped=%s broken=%s" % (imp["skipped"], _broken))
            C("取り込める形のものは全部入る",
              imp["imported"] + imp["updated"] >= _n - _broken,
              json.dumps(imp, ensure_ascii=False))
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
        # 2026-09-07：この2つは**不具合ではなく §23-⑥ の判断待ち**。
        # 「マスター」は30日以上のステップに到達しないと押せない仕様なので、
        # 時計を進めないこの通しでは原理的に0のまま。実測：0/1816・0%。
        # 直すか（マスターの解禁条件を緩めるか）は利用者の裁定事項。
        # 警報として毎回赤く出ると、本物の退行が埋もれる。**保留として出す**。
        # V1.02：この文言は「原理的に0」と書いていたが、**0だったのは
        # 取り込みが全滅していたからで、仕様のせいではなかった**。
        # 916問を正しく入れた実測では 5,550/5,558（99%）まで届く。
        # §23-⑥「Level 5 は実質到達不能か」は、この数字で見直す必要がある。
        _mr = 100.0 * s["master"] / max(1, s["atoms"])
        say("  保留  全アトムがマスターになる（Level 5）   << %d/%d（%.1f%%）"
            "   ※§23-⑥ 判断待ち。残りは30日以上のステップに届いていない肢。"
            "V1.01まで『原理的に0』と書いていたが、0だったのは取り込みの取り違えが原因"
            % (s["master"], s["atoms"], _mr))
        C("Level 5 に到達する", s["level"] >= 5, "Lv%d" % s["level"])
        say("  保留  表示100%%になる   << %s%%   ※同上。達成前に100%%と出さない"
            "（V1.83：Math.round(99.6)=100 で『満タンなのに進まない』が起きたため99で止める）"
            % s["pct"])
        C("ここまでJSエラーが出ない", not errs, json.dumps(errs[:3], ensure_ascii=False))

        json.dump({"snapshot": s}, open(os.path.join(APP, "tmp_allmaster.json"), "w"), ensure_ascii=False)
        if a.stop_after and a.stop_after <= 2:
            say("\n（--stop-after 2 なのでここで止めます。"
                "続きは --profile %s --resume で）" % a.profile)
            say("\n===== まとめ =====")
            say("  失敗 %d件 %s" % (len(FAILS), FAILS if FAILS else ""))
            ctx.close()
            if br: br.close()
            sys.exit(1 if FAILS else 0)
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
