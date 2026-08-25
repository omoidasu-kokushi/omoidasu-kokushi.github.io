#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBA：新しい記録が無いときは台帳を書き戻さない（V1.76）

mergeLogs は重複を鍵（atom_id|answered_at）で落とすので、
**合体後の件数が手元と同じ ＝ 相手から新しい記録は1件も来ていない**。
それでも V1.75 までは台帳を全消しして全件書き直し、全肢の状態を作り直していた。

実測（1,173問・6,674肢・台帳26,696行）：37,000ms → **289ms**。
自分が上げた直後の同期では、落ちてくるのは自分が上げたファイルなので
**必ずこの空振りになる**。

固定するのは3つ：省いても中身が1文字も変わらないこと／新しい記録が
1件でもあれば省かないこと／★は台帳と無関係なので省かないこと。
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
djs = read("drive.js")

ok("合体後の件数で判定する", "merged.length === mine.logs.length" in djs)
ok("省いたことを報告に残す（黙って省かない）", "report.logs_write_skipped" in djs)
ok("applyProgress に skipLogs を渡す", "skipLogs: noNewLogs" in djs)
ok("skipLogs のとき replaceAllLogs を呼ばない",
   "opts.skipLogs\n      ? Promise.resolve(0)" in djs or "opts.skipLogs" in djs.split("var writeLogs")[1][:120])
ok("skipLogs のとき状態も作り直さない", "!opts.skipLogs && logs && logs.length" in djs)
ok("★は省かない（台帳と無関係）", "★は台帳と無関係" in djs)
ok("なぜ省いてよいかが書いてある（根拠つき）",
   "新しい記録は1件も来ていない" in djs and "37秒" in djs)
ok("画面の文言も分ける", "新しい記録はありません" in djs)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1200)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(600)

    # 台帳を作る（同梱シード規模。テストを重くしない）
    made = pg.evaluate("""async () => {
      const S = window.Storage;
      const atoms = (await S.getAllAtoms()).slice(0, 300);
      const logs = []; const base = Date.now() - 86400000 * 30;
      atoms.forEach((a, i) => {
        for (let k = 0; k < 3; k++) {
          logs.push({ atom_id: a.atom_id, q_id: a.q_id, answered_at: base + (i*3+k)*1000,
                      eval: ['hard','normal','easy'][k % 3], is_correct: k % 2 === 0,
                      mode: 'review', schedule_updated: true, interval_code: '1w', srs_step: 3 });
        }
      });
      await S.replaceAllLogs(logs);
      const D = window.Drive, K = window.Scheduler, meta = await S.loadMeta();
      const p0 = await D.collectProgress();
      await D.applyProgress(K.mergeLogs(p0.logs, []), meta, {});
      return { logs: logs.length };
    }""")
    ok("下ごしらえ：台帳を作れた", made["logs"] == 900, json.dumps(made))

    def snapshot():
        return pg.evaluate("""async () => {
          const a = await window.Storage.getAllAtoms();
          return a.slice(0, 300).map(x => [x.atom_id, x.srs_step, x.interval_code,
                    x.due_date, x.last_eval, x.answer_count, x.weakness_pt].join('|')).join(';');
        }""")

    before = snapshot()

    # 新しい記録が0件：省く
    r1 = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage, K = window.Scheduler;
      const p = await D.collectProgress(); const meta = await S.loadMeta();
      const merged = K.mergeLogs(p.logs, p.logs);
      const skip = merged.length === p.logs.length;
      await D.applyProgress(merged, meta, { skipLogs: skip });
      const after = await S.getAllLogs();
      return { skip: skip, merged: merged.length, mine: p.logs.length, stored: after.length };
    }""")
    ok("同じ台帳どうしの合体では増えない", r1["merged"] == r1["mine"], json.dumps(r1))
    ok("省くと判定される", r1["skip"], json.dumps(r1))
    ok("台帳の行数が変わらない", r1["stored"] == made["logs"], json.dumps(r1))
    ok("肢の状態が1文字も変わらない", snapshot() == before)

    # ★は省かない：台帳が増えていなくても書き戻る
    r2 = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage, K = window.Scheduler;
      const p = await D.collectProgress(); const meta = await S.loadMeta();
      const atoms = await S.getAllAtoms();
      const target = atoms[0].atom_id;
      const merged = K.mergeLogs(p.logs, p.logs);
      await D.applyProgress(merged, meta, { skipLogs: true,
        starsAtom: [{ id: target, on: true, at: Date.now() }] });
      const a2 = await S.getAllAtoms();
      const hit = a2.filter(x => x.atom_id === target)[0];
      return { starred: !!hit.is_starred, target: target };
    }""")
    ok("省いても★は書き戻る（★は台帳と無関係）", r2["starred"], json.dumps(r2))

    # 新しい記録が1件：省かない
    r3 = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage, K = window.Scheduler;
      const p = await D.collectProgress(); const meta = await S.loadMeta();
      const extra = Object.assign({}, p.logs[0], { answered_at: Date.now(), eval: 'hard' });
      const merged = K.mergeLogs(p.logs, [extra]);
      const skip = merged.length === p.logs.length;
      await D.applyProgress(merged, meta, { skipLogs: skip });
      const after = await S.getAllLogs();
      return { skip: skip, merged: merged.length, mine: p.logs.length, stored: after.length };
    }""")
    ok("新しい記録があると合体で1件増える", r3["merged"] == r3["mine"] + 1, json.dumps(r3))
    ok("そのときは省かない", not r3["skip"], json.dumps(r3))
    ok("台帳に書き戻る", r3["stored"] == r3["merged"], json.dumps(r3))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBA" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
