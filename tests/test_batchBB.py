#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBB：同期の書き戻しは「増えた分だけ」（V1.77）

V1.76 は「1件も増えていないなら書かない」まで。相手が1件でも新しい記録を
持っていれば、いまも全消し＋全件書き直しで実測43.8秒（26,696行）かかっていた。
2台で使えば毎回ここを通る。

V1.77 は、合体の結果が**足されただけ**なら足すだけにし、
状態の作り直しも**記録が動いた肢だけ**に絞る。実測 45,484ms → 1,502ms。

ただし墓標（全消し・範囲リセット）で記録が落ちているときは、行を選んで
消す必要があるので**全件書き直しに倒す**。滅多に立たないし、
立ったときは正しさが速さより重い。

このバッチが固定するのは「**結果が全件書き直しと同一であること**」。
速さは同一性の後にしか意味がない。
"""
import io, json, os, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
sjs = read("storage.js")
djs = read("drive.js")

ok("storage に appendLogs がある", "function appendLogs(" in sjs)
ok("appendLogs は公開されている", "appendLogs         : appendLogs" in sjs)
ok("appendLogs は log_id を落とす（V1.48の衝突を繰り返さない）",
   "k !== 'log_id'" in sjs.split("function appendLogs(")[1][:600])
ok("重複判定は呼ぶ側の責任だと書いてある",
   "手元に無い記録だけ" in sjs)
ok("drive が足された記録を数える", "report.logs_added" in djs)
ok("全件書き直しに倒したことも報告に残す", "report.logs_full_rewrite" in djs)
ok("落ちた記録があるときは全件書き直しへ倒す",
   "kept !== mine.logs.length" in djs and "addedLogs = null" in djs)
ok("作り直しは動いた肢だけに絞る", "!only || only[a.atom_id]" in djs)
ok("なぜ倒すのかが書いてある（墓標のとき）", "正しさが速さより重い" in djs)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

SETUP = """async () => {
  const S = window.Storage;
  const atoms = (await S.getAllAtoms()).slice(0, 200);
  const base = Date.now() - 86400000 * 30;
  const mine = [], theirs = [];
  atoms.forEach((a, i) => {
    for (let k = 0; k < 3; k++) {
      mine.push({ atom_id: a.atom_id, q_id: a.q_id, answered_at: base + (i*3+k)*1000,
                  eval: ['hard','normal','easy'][k % 3], is_correct: k % 2 === 0,
                  mode: 'review', schedule_updated: true, interval_code: '1w', srs_step: 3 });
    }
  });
  atoms.slice(0, 40).forEach((a, i) => {
    theirs.push({ atom_id: a.atom_id, q_id: a.q_id, answered_at: Date.now() - i*1000,
                  eval: 'hard', is_correct: false, mode: 'review',
                  schedule_updated: true, interval_code: '10m', srs_step: 0 });
  });
  window.__mine = mine; window.__theirs = theirs;
  return { mine: mine.length, theirs: theirs.length };
}"""

RUN = """async (mode) => {
  const S = window.Storage, D = window.Drive, K = window.Scheduler;
  await S.replaceAllLogs(window.__mine);
  const meta = await S.loadMeta();
  const merged = K.mergeLogs(window.__mine, window.__theirs);
  let added = null;
  if (mode === 'inc') {
    const keys = {}; window.__mine.forEach(l => keys[K.logKey(l)] = 1);
    let kept = 0; added = [];
    merged.forEach(l => { if (keys[K.logKey(l)]) kept++; else added.push(l); });
    if (kept !== window.__mine.length) added = null;
  }
  await D.applyProgress(merged, meta, { addedLogs: added });
  const atoms = await S.getAllAtoms();
  const logs = await S.getAllLogs();
  return { added: added ? added.length : -1, logs: logs.length,
    snap: atoms.map(x => [x.atom_id, x.srs_step, x.interval_code, x.due_date,
              x.last_eval, x.answer_count, x.correct_count, x.hard_streak,
              x.weakness_pt, x._unlearned].join('|')).sort().join(';'),
    logSig: logs.map(l => [l.atom_id, l.answered_at, l.eval].join('|')).sort().join(';') };
}"""

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

    setup = pg.evaluate(SETUP)
    ok("下ごしらえ：手元600行・相手に40件の新しい記録", setup["mine"] == 600 and setup["theirs"] == 40,
       json.dumps(setup))

    full = pg.evaluate(RUN, "full")
    inc = pg.evaluate(RUN, "inc")
    ok("増えた分だけ書く経路が選ばれる", inc["added"] == 40, json.dumps({"added": inc["added"]}))
    ok("台帳の行数が全件書き直しと同じ", inc["logs"] == full["logs"],
       "%s / %s" % (inc["logs"], full["logs"]))
    ok("台帳の中身が全件書き直しと同一", inc["logSig"] == full["logSig"])
    ok("肢の状態が全件書き直しと同一（ここが本丸）", inc["snap"] == full["snap"])

    # 相手が同じものしか持っていない → 足す分ゼロ
    z = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      await S.replaceAllLogs(window.__mine);
      const merged = K.mergeLogs(window.__mine, window.__mine);
      const keys = {}; window.__mine.forEach(l => keys[K.logKey(l)] = 1);
      let kept = 0; const added = [];
      merged.forEach(l => { if (keys[K.logKey(l)]) kept++; else added.push(l); });
      return { added: added.length, same: merged.length === window.__mine.length };
    }""")
    ok("同じ記録どうしなら足す分は0件", z["added"] == 0 and z["same"], json.dumps(z))

    # 墓標で記録が落ちるとき → 全件書き直しに倒す
    t = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const merged = K.mergeLogs(window.__mine, window.__theirs)
        .filter(l => l.answered_at > window.__mine[10].answered_at);  // 墓標で切られた想定
      const keys = {}; window.__mine.forEach(l => keys[K.logKey(l)] = 1);
      let kept = 0; let added = [];
      merged.forEach(l => { if (keys[K.logKey(l)]) kept++; else added.push(l); });
      if (kept !== window.__mine.length) added = null;
      return { fallback: added === null, kept: kept, mine: window.__mine.length };
    }""")
    ok("記録が落ちていたら全件書き直しへ倒す", t["fallback"], json.dumps(t))

    # 実際に落ちた記録が消える（倒した経路が正しく効く）
    d = pg.evaluate("""async () => {
      const S = window.Storage, D = window.Drive, K = window.Scheduler;
      await S.replaceAllLogs(window.__mine);
      const meta = await S.loadMeta();
      const cut = window.__mine[10].answered_at;
      const merged = K.mergeLogs(window.__mine, window.__theirs).filter(l => l.answered_at > cut);
      await D.applyProgress(merged, meta, { addedLogs: null });
      const after = await S.getAllLogs();
      return { stored: after.length, merged: merged.length,
               oldGone: after.every(l => l.answered_at > cut) };
    }""")
    ok("倒した経路では落ちた記録が実際に消える", d["stored"] == d["merged"] and d["oldGone"],
       json.dumps(d))

    # appendLogs 単体：log_id を持ち込んでも衝突しない
    a = pg.evaluate("""async () => {
      const S = window.Storage;
      await S.replaceAllLogs([{ atom_id:'Z1', q_id:'QZ', answered_at: 1000, eval:'normal' }]);
      const before = await S.getAllLogs();
      await S.appendLogs([{ log_id: before[0].log_id, atom_id:'Z2', q_id:'QZ',
                            answered_at: 2000, eval:'hard' }]);
      const after = await S.getAllLogs();
      const ids = after.map(l => l.log_id);
      return { n: after.length, unique: new Set(ids).size === ids.length,
               kept: after.some(l => l.atom_id === 'Z1') && after.some(l => l.atom_id === 'Z2') };
    }""")
    ok("appendLogs は既存を消さずに足す", a["n"] == 2 and a["kept"], json.dumps(a))
    ok("持ち込まれた log_id で主キーが衝突しない", a["unique"], json.dumps(a))
    ok("0件を渡しても落ちない", pg.evaluate("window.Storage.appendLogs([]).then(n => n === 0)"))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBB" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
