# -*- coding: utf-8 -*-
"""模試解禁ずみの復元用データを作る V1.00（2026-09-11・V3.02）
   実機確認用。模試が解禁ずみの復元用データ（バックアップJSON）を、アプリ自身に作らせる。
   使い方：cd ~/omo && python3 -m http.server 8900 &  →  python3 tools/模試解禁ずみの復元用データを作る_V1.00.py <出力フォルダ>
   出力：20260911_模試解禁ずみデータ_プチハーフ_V1.00.json（プチ・ハーフだけ解禁）／同 _全部_V1.00.json（4つとも解禁）
   復元：アプリ → 設定 →「バックアップから復元する」→ 入れ替える
   - 本体（必修249問）だけ。体験用の90問と印 free_mock_imported は入れない
     （復元したあと V3.01 以降を起動すると「既存端末に90問が入る」道を通るようにする）
   - 肢の状態と台帳（progress_log）を両方書く（解禁は台帳から導く実データと同じ形）
   - 2種類：プチ・ハーフだけ解禁／全部解禁（フル・いじわるも）
"""
import io, json, os, re, sys, time
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
OUT = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs"
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "20260815_main_part2_V1.45.js")

s = io.open(SRC, encoding="utf-8").read()
i = s.index("var TIPS = {"); j = s.index("var tipState", i)
TIPS = re.findall(r"^\s{4}(\w+)\s*:\s*\{\s*step:", s[i:j], flags=re.M)

FILL = """async (o) => {
  const S = window.Storage, K = window.Scheduler;
  const atoms = await S.getAllAtoms();
  const main = atoms.filter(a => a.pool !== 'mock');
  const byQ = {}; const order = [];
  main.forEach(a => { if (!byQ[a.q_id]) { byQ[a.q_id] = []; order.push(a.q_id); } byQ[a.q_id].push(a); });
  const now = Date.now(), D = 86400000;
  const patch = {}; const logs = [];
  const budget = Math.floor(main.length * o.unique_pct / 100);   /* 肢の数で数える（問題ごとの肢数がばらつくため） */
  let used = 0;
  order.forEach((qid, idx) => {
    if (used >= budget) { return; }
    const r = idx % 100;
    const kind = (r < o.hard_pct) ? 'hard' : ((r < o.hard_pct + o.easy_pct) ? 'easy' : 'normal');
    used += byQ[qid].length;
    const at = now - (1 + (idx % 20)) * D - (idx % 7) * 3600000;
    byQ[qid].forEach((a, k) => {
      const correct = kind !== 'hard';
      const step = kind === 'hard' ? 0 : (kind === 'easy' ? 4 : 2);
      const code = kind === 'hard' ? '10m' : (kind === 'easy' ? '30d' : '1d');
      const due  = kind === 'hard' ? (at + 600000) : (now + (1 + (idx % 10)) * D);
      patch[a.atom_id] = { answer_count: 1, correct_count: correct ? 1 : 0, last_eval: kind,
                           last_answered_at: at, srs_step: step, interval_code: code, due_date: due };
      logs.push({ atom_id: a.atom_id, q_id: qid, eval: kind, is_correct: correct, mode: 'random', session_id: null,
                  answered_at: at, interval_code: code, srs_step_after: step, schedule_updated: true,
                  early_miss: false, think_ms: 2200 + k * 350 + (idx % 5) * 100 });
    });
  });
  await S.updateAtomsBulk(patch);
  await S.appendLogs(logs);
  await S.setMetaBulk(Object.assign({ onboarding_done: true, tips_seen: o.tips }, o.extra || {}));
  for (const h of (o.history || [])) { await S.saveExamResult(h); }
  await K.refreshAll({ recomputeWeakness: true });
  const r = await K.refreshUnlocks();
  const b = await S.exportBackup();
  return { unlocks: r.unlocks.map(u => [u.id, u.unlocked, u.pct]),
           stats: { q: r.stats.total_questions, uniq: r.stats.unique_answered_ratio, np: r.stats.normal_plus_ratio },
           patched: Object.keys(patch).length, logs: logs.length, backup: b };
}"""

def strip_mock(b):
    qs = b["stores"]["questions"]
    drop = set(q["q_id"] for q in qs if (q.get("pool") == "mock"))
    b["stores"]["questions"] = [q for q in qs if q["q_id"] not in drop]
    b["stores"]["atoms"] = [a for a in b["stores"]["atoms"] if a["q_id"] not in drop]
    b["stores"]["progress_log"] = [l for l in b["stores"]["progress_log"] if l.get("q_id") not in drop]
    b["stores"]["meta"] = [m for m in b["stores"]["meta"] if m.get("key") not in ("free_mock_imported", "free_mock_version")]
    c = b["counts"]
    c["questions"] = len(b["stores"]["questions"]); c["atoms"] = len(b["stores"]["atoms"])
    c["progress_log"] = len(b["stores"]["progress_log"]); c["meta"] = len(b["stores"]["meta"])
    b["notes"] = (b.get("notes") or []) + ["模試解禁ずみの復元用データ（本体249問だけ・体験用90問は起動時に入る）"]
    return b, len(drop)

def make(pg, name, opts):
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    for _ in range(300):
        if pg.evaluate("async () => await window.Storage.countQuestions()") >= 339: break
        pg.wait_for_timeout(200)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    pg.evaluate("() => { window.Main.closeModals(); }")
    res = pg.evaluate(FILL, opts)
    b, dropped = strip_mock(res["backup"])
    path = os.path.join(OUT, name)
    io.open(path, "w", encoding="utf-8").write(json.dumps(b, ensure_ascii=False))
    print(name, "| unlocks:", res["unlocks"], "| stats:", res["stats"], "| patched:", res["patched"], "logs:", res["logs"],
          "| dropped mock:", dropped, "| q:", b["counts"]["questions"], "atoms:", b["counts"]["atoms"], "| bytes:", os.path.getsize(path))
    # 消してから次へ（同じプロファイルを使い回さない）
    pg.evaluate("async () => { const S = window.Storage; await S.resetAll(); }")

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    now = int(time.time() * 1000)
    make(pg, "20260911_模試解禁ずみデータ_プチハーフ_V1.00.json",
         { "unique_pct": 47, "hard_pct": 2, "easy_pct": 10, "tips": TIPS })
    ctx.close(); ctx = br.new_context(viewport={"width": 390, "height": 900}); pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    make(pg, "20260911_模試解禁ずみデータ_全部_V1.00.json",
         { "unique_pct": 62, "hard_pct": 4, "easy_pct": 14, "tips": TIPS,
           "extra": { "full_mock_pass_streak": 2, "unlock_mock_weak": True, "unlock_pct_mock_weak": 100 },
           "history": [ { "exam_id": "mock_120", "at": now - 9 * 86400000, "total": 120, "correct": 101, "passed": True, "elapsed_ms": 5400000 },
                        { "exam_id": "mock_120", "at": now - 3 * 86400000, "total": 120, "correct": 104, "passed": True, "elapsed_ms": 5100000 } ] })
    print("pageerrors:", errs)
    br.close()
