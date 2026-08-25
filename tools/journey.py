#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""インストールから合格まで、時計を進めながら一本で走らせる（手動・テスト一式には入れない）

なぜ要るか
  ここまでの検証は「その瞬間の1動作」しか見ていない。
  実際の利用は**何ヶ月もの状態遷移**で、忘却スケジュール・模試の解禁・
  レベルの進行・不退転はすべて「何日経ったか」で動く。
  実時間で待てないので `Date` ごと差し替え、日数を進めて通す。

  ここで壊れると、利用者が**何ヶ月も使ったあとにしか**分からない。

使い方
    cd <repo> && python3 -m http.server 8900 &
    python3 tools/journey.py                 # 既定：360日ぶん
    python3 tools/journey.py --days 720 --copies 2
"""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from journey_lib import *   # noqa

URL = "http://127.0.0.1:8900/index.html"
TSV = os.path.join(APP, "tmp_journey.tsv")
LOG = []


def say(msg):
    print(msg, flush=True)
    LOG.append(msg)


def check(name, cond, detail=""):
    mark = "  ok  " if cond else "  NG  "
    say(mark + name + (("   << " + str(detail)) if detail else ""))
    return bool(cond)


def build_tsv(copies):
    js = r"""
    const fs=require('fs'); global.window={}; global.self=global;
    eval(fs.readFileSync(process.argv[1],'utf8'));
    const rows=global.window.SEED_QUESTIONS_TSV.split(/\r\n|\r|\n/).filter(s=>s.trim());
    const n=parseInt(process.argv[3],10); const out=[];
    for(let c=1;c<=n;c++) for(const r of rows){
      const cells=r.split('\t'); cells[7]='【第'+(105+c)+'回】'+cells[7]; out.push(cells.join('\t'));
    }
    fs.writeFileSync(process.argv[2], out.join('\n'),'utf8');
    console.log(JSON.stringify({rows:out.length}));
    """
    r = subprocess.run(["node", "-e", js, os.path.join(APP, "questions.js"), TSV, str(copies)],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stderr); sys.exit(1)
    return json.loads(r.stdout.strip())


# 1日ぶんの学習を、画面ではなくロジックに直接流し込む。
# 画面での操作性は別の検証（batchBD/BE・規模計測）で見ている。
# ここで見たいのは**何ヶ月ぶんの状態遷移**なので、日数を稼げる形にする。
STUDY_DAY = r"""
async (cfg) => {
  const K = window.Scheduler, S = window.Storage;
  const acc = cfg.accuracy;
  const out = { review: 0, fresh: 0, right: 0, wrong: 0 };
  let seed = cfg.seed;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };

  async function doQueue(q, mode, cap) {
    const qs = (q && q.questions) || [];
    for (let i = 0; i < qs.length && i < cap; i++) {
      const item = qs[i];
      const atoms = item.atoms || [];
      if (!atoms.length) continue;
      const right = rnd() < acc;
      const evals = atoms.map(a => ({
        atom_id: a.atom_id,
        /* 正解なら「普通」、続けて出来ていれば「簡単」。間違えたら「難しい」。
           仕様§4-③の初期点灯（初見正解＝普／初見不正解＝難）に沿う。 */
        eval: right ? ((a.srs_step || 0) >= 2 ? 'easy' : 'normal') : 'hard',
        is_correct: right
      }));
      await K.applyQuestionEvaluations(item.q_id, evals,
        { mode: mode, sessionId: 'J' + mode, thinkMs: 1500 + Math.floor(rnd() * 8000) });
      if (right) out.right++; else out.wrong++;
      if (mode === 'review') out.review++; else out.fresh++;
    }
  }

  const rq = await K.getReviewQueue(cfg.reviewCap);
  await doQueue(rq, 'review', cfg.reviewCap);
  if (out.review < cfg.dailyTotal) {
    const nq = await K.buildQueue({ mode: 'random', count: cfg.dailyTotal - out.review,
                                    applyGuard: false });
    await doQueue(nq, 'random', cfg.dailyTotal - out.review);
  }
  return out;
}
"""

SNAPSHOT = r"""
async () => {
  const K = window.Scheduler, S = window.Storage;
  const h = await K.getHomeState();
  const lv = await K.computeLevel();
  const raw = await K.computeLevelRaw();
  const un = await K.refreshUnlocks();
  const m = await S.loadMeta();
  const u = {}; (un.unlocks || []).forEach(x => u[x.id] = !!x.unlocked);
  return {
    date: new Date().toISOString().slice(0, 10),
    due: h.due_count, answered: m.total_questions_answered || 0,
    level: lv.level, pct: lv.display_pct, raw_pct: raw.current_pct,
    by_level: raw.pct_by_level, done: raw.done_by_level,
    unlocks: u, streak: m.full_mock_pass_streak || 0,
    scan: (await K.getScanAccuracy()).pct,
    theme: h.visual_theme || (lv.theme || null)
  };
}
"""


def snapshot(pg):
    return pg.evaluate(SNAPSHOT)


def run_exam_ui(pg, exam_id, size, accuracy, ground_ratio=1.0, cap=None):
    """模試を画面から通しで受験する。正解率を指定できる（合否を作るため）。"""
    pg.evaluate("([id, n]) => window.Half2Impl.launchExam(id, n, 'real')", [exam_id, size])
    try:
        pg.wait_for_selector("#choice-list .choice-card, #numeric-wrap", timeout=60000)
    except Exception:
        return None
    n = cap or (size + 10)
    answered = 0
    for i in range(n):
        if pg.is_visible("#modal-exam-result"):
            break
        # 37 は100と互いに素なので 0〜99 を一巡する。
        # 997 を使うと (1000-3i) になり **前半が全部「不正解」に偏る**（実際に踏んで 1/30 になった）。
        want = ((i * 37) % 100) < accuracy * 100
        gr = ((i * 37 + 11) % 100) < ground_ratio * 100
        try:
            if not answer_current_ui(pg, want_right=want, ground=gr, timeout=20000):
                break
        except Exception:
            break
        answered += 1
        pg.wait_for_timeout(110)
    pg.wait_for_timeout(3000)
    res = pg.evaluate("""() => {
      const m = document.querySelector('#modal-exam-result');
      return { shown: !!(m && !m.hidden),
               title: (document.querySelector('#exam-result-title')||{}).textContent||'',
               score: (document.querySelector('#exam-score')||{}).textContent||'',
               body: (m ? m.textContent : '').replace(/\s+/g,' ').slice(0, 260) };
    }""")
    res["answered"] = answered
    close_modals(pg)
    pg.wait_for_timeout(600)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=360)
    ap.add_argument("--copies", type=int, default=2, help="同梱453問を何倍足すか（配布物の想定量に近づける）")
    ap.add_argument("--daily", type=int, default=40, help="1日に解く問題数")
    ap.add_argument("--url", default=URL)
    ap.add_argument("--profile", default=None, help="状態を残すプロファイル（あとで模試だけやり直せる）")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright
    fails = []

    def C(name, cond, detail=""):
        if not check(name, cond, detail):
            fails.append(name)

    say("見本を%d倍にしたTSVを作る…" % a.copies)
    say("  " + json.dumps(build_tsv(a.copies)))

    with sync_playwright() as pw:
        br, ctx, pg = new_page(pw, profile=a.profile)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        # ============================== ① インストール直後
        say("\n===== ① インストール直後 =====")
        pg.goto(a.url, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=180000)
        pg.wait_for_timeout(2200)
        C("時計の差し替えが効いている", pg.evaluate("() => Date.now() === new Date().getTime()"))
        C("同梱の見本問題が入っている", pg.evaluate("window.Storage.countQuestions()") > 0,
          pg.evaluate("window.Storage.countQuestions()"))
        sw = pg.evaluate("""async () => {
          if (!navigator.serviceWorker) return 'なし';
          const r = await navigator.serviceWorker.getRegistration();
          return r ? (r.active ? 'active' : 'installing') : '未登録';
        }""")
        C("Service Worker が登録される（オフライン動作の土台）", sw in ("active", "installing"), sw)
        C("分析精度は0%から始まる", (pg.text_content("#scan-pct") or "").strip() == "0")

        # ============================== ② チュートリアル3問
        say("\n===== ② 最初の3問（即時体験型チュートリアル） =====")
        pg.click("#welcome-start"); pg.wait_for_timeout(900)
        C("説明を挟まずいきなり1問目が出る", pg.is_visible("#choice-list .choice-card"),
          (pg.text_content("#q-counter") or "").strip())
        tour_next(pg, 3)
        done = 0
        for i in range(6):
            if not pg.is_visible("#screen-quiz"):
                break
            tour_next(pg, 3)
            try:
                if not answer_and_next(pg, want_right=(i != 1), timeout=12000):
                    break
            except Exception:
                break
            done += 1
        pg.wait_for_timeout(2500)
        C("3問でチュートリアルが終わる", done >= 3, "解いた %d問" % done)
        C("終わるとホームへ移る",
          pg.evaluate("() => (document.querySelector('.screen.is-active')||{}).id") == "screen-home")
        s = snapshot(pg)
        C("分析精度が動く", s["scan"] > 0, "%d%%" % s["scan"])
        say("  " + json.dumps(s, ensure_ascii=False))
        say("  ガイド送り: %d回" % tour_next(pg, 30))
        tour_skip(pg); close_modals(pg); pg.wait_for_timeout(500)

        # ============================== ③ 配布物の量まで中身を入れる
        say("\n===== ③ 過去問を取り込む（配布物の想定量） =====")
        imp = pg.evaluate("""async () => {
          const t = await (await fetch('/tmp_journey.tsv')).text();
          const t0 = performance.now();
          const r = await window.Storage.importText(t);
          return { ms: Math.round(performance.now()-t0), imported: r.imported,
                   skipped: r.skipped, mismatch: r.mismatch, atoms: r.atoms };
        }""")
        say("  " + json.dumps(imp, ensure_ascii=False))
        C("取り込みで落ちない", imp["imported"] > 0 and imp["mismatch"] == 0, json.dumps(imp))
        pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
        total_q = pg.evaluate("window.Storage.countQuestions()")
        say("  問題数: %d" % total_q)

        # ============================== ④ 毎日の学習（時計を進める）
        say("\n===== ④ 毎日の学習（%d日・1日%d問） =====" % (a.days, a.daily))
        milestones = []
        seen_unlock = {}
        first_pass = {}
        prev = None
        t0 = time.time()
        for day in range(1, a.days + 1):
            advance_days(pg, 1, to_hour=7)
            # 学習者は上達する：初日55% → 120日で85%で頭打ち
            acc = min(0.85, 0.55 + 0.30 * (day / 120.0))
            r = pg.evaluate(STUDY_DAY, {
                "accuracy": acc, "dailyTotal": a.daily, "reviewCap": max(10, a.daily),
                "seed": day * 7919
            })
            if day % 10 == 0 or day <= 3:
                pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
                s = snapshot(pg)
                s["day"] = day
                s["study"] = r
                milestones.append(s)
                for k, v in s["unlocks"].items():
                    if v and k not in seen_unlock:
                        seen_unlock[k] = day
                if day % 60 == 0:
                    say("  %3d日目 %s  Lv%d %s%%(実%s%%) 復習%s 累計%s 解禁%s" % (
                        day, s["date"], s["level"], s["pct"], s["raw_pct"],
                        s["due"], s["answered"], ",".join(sorted(k for k, v in s["unlocks"].items() if v)) or "なし"))
        say("  （%d日ぶんに %.0f秒）" % (a.days, time.time() - t0))
        s = snapshot(pg)
        say("  最終: " + json.dumps(s, ensure_ascii=False))
        C("模試（30問）が解禁された", s["unlocks"].get("mock_30"), json.dumps(seen_unlock))
        C("模試（60問）が解禁された", s["unlocks"].get("mock_60"), json.dumps(seen_unlock))
        C("模試（120問）が解禁された", s["unlocks"].get("mock_120"), json.dumps(seen_unlock))
        C("解禁が早すぎない（初日には開かない）",
          all(d > 1 for d in seen_unlock.values()), json.dumps(seen_unlock))
        C("レベルが上がっている", s["level"] >= 2, "Lv%d" % s["level"])
        C("この間にJSエラーが出ない", not errs, json.dumps(errs[:3], ensure_ascii=False))

        # ============================== ⑤ 模試を受ける
        say("\n===== ⑤ 模試（30→60→120） =====")
        r30 = run_exam_ui(pg, "mock_30", 30, accuracy=0.75)
        say("  30問: " + json.dumps(r30, ensure_ascii=False))
        C("30問プチ模試が最後まで通る", r30 and r30["answered"] >= 30 and r30["shown"],
          json.dumps(r30, ensure_ascii=False) if r30 else "None")
        r60 = run_exam_ui(pg, "mock_60", 60, accuracy=0.60)
        say("  60問: " + json.dumps(r60, ensure_ascii=False))
        C("60問ハーフ模試が最後まで通る", r60 and r60["answered"] >= 60 and r60["shown"],
          json.dumps(r60, ensure_ascii=False) if r60 else "None")

        # ============================== ⑥ 合格（必修80%以上・一般180点以上を2回連続）
        say("\n===== ⑥ 120問フル模試で合格する =====")
        passes = []
        for k in range(2):
            advance_days(pg, 3, to_hour=9)
            r = run_exam_ui(pg, "mock_120", 120, accuracy=0.92)
            st = snapshot(pg)
            passes.append({"r": r, "streak": st["streak"], "weak": st["unlocks"].get("mock_weak")})
            say("  %d回目: %s / 連続合格 %s / いじわる %s" % (
                k + 1, json.dumps(r, ensure_ascii=False)[:200], st["streak"], st["unlocks"].get("mock_weak")))
        C("120問フル模試が最後まで通る", passes[0]["r"] and passes[0]["r"]["answered"] >= 120,
          json.dumps(passes[0]["r"], ensure_ascii=False) if passes[0]["r"] else "None")
        C("合格判定が出る（必修80%以上・一般180点以上）",
          passes[-1]["r"] and ("合格" in (passes[-1]["r"]["title"] + passes[-1]["r"]["body"])),
          json.dumps(passes[-1]["r"], ensure_ascii=False) if passes[-1]["r"] else "None")
        C("2回連続合格で連勝が2になる", passes[-1]["streak"] >= 2, str(passes[-1]["streak"]))
        C("いじわる模試が解禁される", passes[-1]["weak"], str(passes[-1]["weak"]))

        # ============================== ⑦ その先（レベル進行）
        say("\n===== ⑦ 合格後：レベルはどこまで行くか =====")
        s = snapshot(pg)
        say("  " + json.dumps(s, ensure_ascii=False))
        C("最終レベルの表示が不退転（後戻りしない）", s["pct"] >= s["raw_pct"] - 1,
          "表示%s%% 実%s%%" % (s["pct"], s["raw_pct"]))
        C("最後までJSエラーが出ない", not errs, json.dumps(errs[:5], ensure_ascii=False))

        say("\n===== まとめ =====")
        say("  解禁された日: " + json.dumps(seen_unlock, ensure_ascii=False))
        say("  推移（60日ごと）:")
        for m in milestones:
            if m["day"] % 60 == 0:
                say("    %3d日 Lv%d 表示%s%% 実%s%% 各段階%s 累計%s" % (
                    m["day"], m["level"], m["pct"], m["raw_pct"],
                    json.dumps(m["by_level"]), m["answered"]))
        say("\n  失敗 %d件 %s" % (len(fails), fails if fails else ""))
        ctx.close()
        if br:
            br.close()

    if os.path.exists(TSV):
        os.remove(TSV)
    sys.exit(1 if fails else 0)


main()
