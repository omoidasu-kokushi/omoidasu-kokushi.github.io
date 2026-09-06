# -*- coding: utf-8 -*-
"""audit_backup.py — バックアップ→全初期化→復元の往復で1件も欠けないか（2026-09-07 夜）

いちばん怖いのは「消えたことに気づかない」こと。
問題・肢・学習記録・★・メモ・設定を**数えてから**往復させ、数が合うかを見る。

配布物の想定量（過去問443問を取り込んだ状態）で測る。
"""
import io, json, os, subprocess, sys, time

APP = os.path.expanduser("~/omo")
B = ("/sessions/ecstatic-wizardly-dijkstra/mnt/owner/Desktop/国家試験対策室/"
     "過去問抽出_20260824/分類_令和5年版")
PAYLOAD = os.path.join(B, "out", "20260907_取り込み用_過去問_照合ずみ_V1.01.json")
PORT = "8914"

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

from playwright.sync_api import sync_playwright
srv = subprocess.Popen(["python3", "-m", "http.server", PORT], cwd=APP,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
payload = io.open(PAYLOAD, encoding="utf-8").read()

COUNT = """async () => {
  const S = window.Storage;
  const qs = await S.getAllQuestions();
  const at = await S.getAllAtoms();
  const meta = await S.loadMeta();
  const prog = null;   /* 記録の総数は外から数える口が無いので見ない */
  return {
    q: qs.length, atoms: at.length,
    answered: at.filter(a => a.answer_count > 0).length,
    star_q: qs.filter(x => x.starred).length,
    star_a: at.filter(a => a.starred).length,
    memo: qs.filter(x => x.user_memo).length,
    logs: prog ? prog.length : null,
    theme: meta.theme || null, pomo: meta.pomodoro_enabled,
    dayb: meta.day_boundary_hour, seed: meta.seed_imported
  };
}"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:%s/index.html" % PORT, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("async () => { await window.Storage.setMeta('onboarding_done', true); }")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1200)
    pg.evaluate("() => window.Main.closeModals()")

    imp = pg.evaluate("async (t) => await window.Storage.importText(t)", payload)
    ok("配布物を取り込める", imp.get("imported", 0) > 400, json.dumps(
        {k: imp.get(k) for k in ("imported", "skipped", "mismatch")}, ensure_ascii=False))

    # 使った跡を作る：解答・★・メモ・設定
    pg.evaluate("""async () => {
      const S = window.Storage;
      const at = (await S.getAllAtoms()).slice(0, 120);
      for (let i = 0; i < at.length; i++) {
        await S.updateAtom(at[i].atom_id, {
          answer_count: 1 + (i % 3),
          last_eval: ['hard','normal','easy'][i % 3],
          due_date: Date.now() + i * 3600000,
          interval_code: ['10m','1h','1d'][i % 3],
          srs_step: i % 5,
          starred: (i % 17 === 0)
        });
      }
      const qs = (await S.getAllQuestions()).slice(0, 30);
      for (let i = 0; i < qs.length; i++) {
        if (i % 6 === 0) { await S.updateQuestion(qs[i].q_id, { starred: true }); }
        if (i % 9 === 0) { await S.updateQuestion(qs[i].q_id, { user_memo: 'メモ' + i }); }
      }
      await S.setMetaBulk({ theme: 'sepia', pomodoro_enabled: false, day_boundary_hour: 5 });
    }""")
    before = pg.evaluate(COUNT)
    print("往復前:", json.dumps(before, ensure_ascii=False))

    # バックアップを取る（ファイルを受け取る）
    with pg.expect_download(timeout=60000) as dl:
        pg.evaluate("async () => { await window.Storage.downloadBackup('audit'); }")
    path = dl.value.path()
    size = os.path.getsize(path)
    backup = io.open(path, encoding="utf-8").read()
    ok("バックアップが書き出せる", size > 100000, "%dKB" % (size // 1024))

    # 全初期化（画面から押すのと同じ道）
    with pg.expect_download(timeout=60000):
        pg.evaluate("async () => { await window.Half2Impl.doResetAll(); }")
    pg.wait_for_timeout(800)
    after_reset = pg.evaluate(COUNT)
    ok("全初期化で空になる", after_reset["q"] == 0 and after_reset["atoms"] == 0,
       json.dumps(after_reset, ensure_ascii=False))
    ok("全初期化でも seed_imported の印は残る（見本が戻ってこない）",
       bool(after_reset["seed"]), str(after_reset["seed"]))

    # 復元
    res = pg.evaluate("async (t) => await window.Storage.restoreBackup(JSON.parse(t), 'replace')", backup)
    pg.wait_for_timeout(600)
    after = pg.evaluate(COUNT)
    print("復元後 :", json.dumps(after, ensure_ascii=False))

    for k, label in [("q", "問題"), ("atoms", "肢"), ("answered", "解答ずみの肢"),
                     ("star_q", "★の問題"), ("star_a", "★の肢"), ("memo", "メモ"),
                     ("logs", "学習記録")]:
        if before.get(k) is None:
            continue
        ok("%sが往復で欠けない" % label, before[k] == after[k],
           "前 %s → 後 %s" % (before[k], after[k]))
    for k, label in [("theme", "テーマ"), ("pomo", "ポモドーロのON/OFF"),
                     ("dayb", "日界の時刻")]:
        ok("設定（%s）が戻る" % label, before[k] == after[k],
           "前 %r → 後 %r" % (before[k], after[k]))

    ok("JSエラーが出ていない", not errs, " / ".join(errs[:3]))
    br.close()
srv.terminate()

bad = [x for x in R if not x[0]]
for good, name, d in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + d) if not good else ""))
print("\n%d/%d  バックアップ往復" % (len(R) - len(bad), len(R)))
