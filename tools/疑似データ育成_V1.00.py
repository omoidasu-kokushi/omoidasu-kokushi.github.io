#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""疑似的に「長く使い込んだ状態」を育てて、バックアップJSONとして書き出す道具。

なぜ要るか
  お気に入り・復習期日・弱点pt・レベル・解禁などの「数値が溜まった状態」の
  操作感は、新規状態ではいつまでも確かめられない。journey（通し検証）と同じ
  仕組み（時計差し替え＋ロジック直結の1日学習）で日数を稼ぎ、その結果を
  アプリ標準のバックアップとして持ち出して、実機の「設定→復元」で再現する。

分割実行式（1回の呼び出しが短時間で切れる環境でも回せる）
    python3 tools/疑似データ育成_V1.00.py --selftest
    python3 tools/疑似データ育成_V1.00.py --init --copies 3
    python3 tools/疑似データ育成_V1.00.py --study 50     # 何度でも。合計日数は状態ファイルが覚える
    python3 tools/疑似データ育成_V1.00.py --status
    python3 tools/疑似データ育成_V1.00.py --export --out /path/to/backup.json

  プロファイルと時計オフセットは /tmp/omo_pseudo/ に永続し、続きから再開できる。
"""
import argparse, io, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from journey_lib import new_page, boot, advance_days, tour_skip, close_modals  # noqa

BASE = "/tmp/omo_pseudo"
PROF = os.path.join(BASE, "profile")
STATE = os.path.join(BASE, "state.json")
TSV = os.path.join(BASE, "stress.tsv")
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

STUDY_DAY = r"""
async (cfg) => {
  const K = window.Scheduler, S = window.Storage;
  const acc = cfg.accuracy;
  const out = { review: 0, fresh: 0, right: 0, wrong: 0, starred: 0 };
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
        eval: right ? ((a.srs_step || 0) >= 2 ? 'easy' : 'normal') : 'hard',
        is_correct: right
      }));
      await K.applyQuestionEvaluations(item.q_id, evals,
        { mode: mode, sessionId: 'P' + mode, thinkMs: 1500 + Math.floor(rnd() * 8000) });
      if (right) out.right++; else out.wrong++;
      if (mode === 'review') out.review++; else out.fresh++;
      /* たまに★を付ける（お気に入りノートに中身を作る） */
      if (rnd() < cfg.starRate) {
        if (rnd() < 0.5) { await S.toggleQuestionStar(item.q_id); }
        else { await S.toggleAtomStar(atoms[Math.floor(rnd() * atoms.length)].atom_id); }
        out.starred++;
      }
    }
  }
  const rq = await K.getReviewQueue(cfg.reviewCap);
  await doQueue(rq, 'review', cfg.reviewCap);
  if (out.review < cfg.dailyTotal) {
    const nq = await K.buildQueue({ mode: 'random', count: cfg.dailyTotal - out.review, applyGuard: false });
    await doQueue(nq, 'random', cfg.dailyTotal - out.review);
  }
  return out;
}
"""

SNAPSHOT = r"""
async () => {
  const K = window.Scheduler, S = window.Storage;
  const lv = await K.computeLevel();
  const un = await K.refreshUnlocks();
  const m = await S.loadMeta();
  const u = {}; (un.unlocks || []).forEach(x => u[x.id] = !!x.unlocked);
  return { date: new Date().toISOString().slice(0, 10),
           answered: m.total_questions_answered || 0,
           level: lv.level, pct: lv.display_pct, unlocks: u };
}
"""


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


def load_state():
    return json.load(io.open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"offset": 0, "days": 0}


def save_state(st):
    io.open(STATE, "w", encoding="utf-8").write(json.dumps(st))


def open_app(pw, st):
    br, ctx, pg = new_page(pw, profile=PROF)
    boot(pg, URL)
    if st["offset"]:
        pg.evaluate("(ms) => window.__setOffset(ms)", st["offset"])
    tour_skip(pg); close_modals(pg)
    return ctx, pg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--copies", type=int, default=3)
    ap.add_argument("--study", type=int, default=0)
    ap.add_argument("--daily", type=int, default=40)
    ap.add_argument("--accuracy", type=float, default=0.72)
    ap.add_argument("--star-rate", type=float, default=0.02)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--out", default=os.path.join(BASE, "backup.json"))
    a = ap.parse_args()

    if a.selftest:
        assert "applyQuestionEvaluations" in STUDY_DAY and "toggleQuestionStar" in STUDY_DAY
        assert "__setOffset" in io.open(os.path.join(HERE, "journey_lib.py"), encoding="utf-8").read()
        n = build_tsv(1); assert n["rows"] > 400, n
        print("selftest OK（STUDY_DAY部品・時計API・TSV生成 " + str(n["rows"]) + "行）"); return

    from playwright.sync_api import sync_playwright
    os.makedirs(BASE, exist_ok=True)
    st = load_state()

    with sync_playwright() as pw:
        if a.init:
            import shutil
            if os.path.exists(PROF): shutil.rmtree(PROF)
            if os.path.exists(STATE): os.remove(STATE)
            st = {"offset": 0, "days": 0}
            n = build_tsv(a.copies)
            ctx, pg = open_app(pw, st)
            t = io.open(TSV, encoding="utf-8").read()
            r = pg.evaluate("async (t) => { const x = await window.Storage.importText(t); return { imported: x.imported, skipped: x.skipped }; }", t)
            print("取り込み:", r, "（同梱453問＋複製", n["rows"], "行）")
            save_state(st); ctx.close(); return

        if a.study:
            ctx, pg = open_app(pw, st)
            for i in range(a.study):
                advance_days(pg, 1)
                out = pg.evaluate(STUDY_DAY, {
                    "accuracy": a.accuracy, "dailyTotal": a.daily, "reviewCap": 200,
                    "seed": (st["days"] + 1) * 7919 + 13, "starRate": a.star_rate})
                st["days"] += 1
                st["offset"] = pg.evaluate("() => window.__offset()")
                save_state(st)
            snap = pg.evaluate(SNAPSHOT)
            print("累計", st["days"], "日 / 本日:", out, "/ 状態:", json.dumps(snap, ensure_ascii=False))
            ctx.close(); return

        if a.status or a.export:
            ctx, pg = open_app(pw, st)
            snap = pg.evaluate(SNAPSHOT)
            print("累計", st["days"], "日 / 状態:", json.dumps(snap, ensure_ascii=False))
            if a.export:
                b = pg.evaluate("async () => await window.Storage.exportBackup()")
                io.open(a.out, "w", encoding="utf-8").write(json.dumps(b, ensure_ascii=False))
                print("書き出し:", a.out, "/", json.dumps(b.get("counts", {}), ensure_ascii=False))
            ctx.close(); return

    ap.print_help()


if __name__ == "__main__":
    main()
