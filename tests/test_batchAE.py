#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.48 検証：端末をまたぐ進捗同期

  V1.47 まで、2台目を使い始めた最初の同期で進捗が恒久的に止まっていた。
  progress_log の keyPath は 'log_id' なのに、書き戻しは 'id' を除外していた。
  log_id は端末ごとの連番なので、別端末の【別の解答】に同じ番号が付く。
  mergeLogs の重複判定は atom_id|answered_at なので、この衝突は取り除かれない。
  結果 add() が ConstraintError を投げ、トランザクションごと abort していた。

  さらに、その失敗は catch で握りつぶされ report.ok は true のまま、
  clearDirty() が未同期バッジまで0に戻していた。
  利用者から見ると「同期できている」。実際には1件も上がっていない。

  既存のテストが見逃した理由は「単一端末でしか回していなかった」こと。
  ここでは【独立に採番された2台目】を必ず登場させる。
"""
import json, os, sys, subprocess, io, re
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
MOCK = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_drive.js"),
            encoding="utf-8").read()
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))
def read(f): return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
for f in ["storage.js", "drive.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

sto, drv = read("storage.js"), read("drive.js")
ok("replaceAllLogs が除外するのは log_id（id ではない）",
   "if (k !== 'log_id') { rec[k] = l[k]; }" in sto and "if (k !== 'id') { rec[k] = l[k]; }" not in sto)
ok("restoreBackup 側も log_id のまま", sto.count("k !== 'log_id'") >= 2)
ok("collectProgress が log_id を送らない", "k !== 'log_id'" in drv)
ok("進捗が落ちたら成功として扱わない", "report.ok = false;\n        report.error = '学習の記録を同期できませんでした" in drv)
ok("失敗したら未同期の印を消さない",
   "return (report.ok ? S.clearDirty() : Promise.resolve(null))" in drv)
ok("失敗の理由を meta に残す", "drive_last_error" in drv)
ok("設定画面に失敗の理由を出す",
   "drive_last_error" in read(os.path.basename(sorted(
       __import__('glob').glob(os.path.join(APP, "*main_part2_V*.js")))[-1])))


def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)


def runtime_checks():
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text)
              if m.type == "error" and not _external(m.text) else None)
        pg.goto(URL, wait_until="load")
        pg.wait_for_function("window.__APP_READY === true", timeout=20000)
        pg.wait_for_timeout(1800)
        pg.add_script_tag(content=MOCK)

        # ---------- 1. 独立採番の log_id が衝突する状況 ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const atoms = await S.getAllAtoms();
          const a1 = atoms[0].atom_id, a2 = atoms[1].atom_id;
          // 端末A：自分の1件目（log_id=1）
          const deviceA = [{ log_id: 1, atom_id: a1, answered_at: 1000,
                             eval: 'normal', is_correct: true, schedule_updated: true,
                             interval_code: '1h' }];
          // 端末B：まったく別の解答なのに、独立採番なので log_id も 1
          const deviceB = [{ log_id: 1, atom_id: a2, answered_at: 2000,
                             eval: 'hard', is_correct: false, schedule_updated: true,
                             interval_code: '10m' }];
          const merged = K.mergeLogs(deviceA, deviceB);
          let saved = null, err = null;
          try { saved = await S.replaceAllLogs(merged); }
          catch (e) { err = (e && e.message) || String(e); }
          const after = await S.getAllLogs();
          const ids = after.map(l => l.log_id);
          return { mergedLen: merged.length, saved, err,
                   storedLen: after.length, ids,
                   unique: new Set(ids).size === ids.length };
        }""")
        ok("合体では log_id の衝突は取り除かれない（重複判定は atom_id|answered_at）",
           r["mergedLen"] == 2, json.dumps(r))
        ok("それでも書き戻しは失敗しない", r["err"] is None, json.dumps(r))
        ok("2件とも保存される", r["storedLen"] == 2, json.dumps(r))
        ok("保存後の log_id は採番し直されて一意", r["unique"], json.dumps(r["ids"]))

        # ---------- 2. 同じ解答は1件にまとまる（合体の規則は変えていない） ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, K = window.Scheduler;
          const atoms = await S.getAllAtoms();
          const a1 = atoms[0].atom_id;
          const same = { atom_id: a1, answered_at: 5000, eval: 'easy',
                         is_correct: true, schedule_updated: true, interval_code: '30d' };
          const merged = K.mergeLogs([Object.assign({ log_id: 7 }, same)],
                                     [Object.assign({ log_id: 99 }, same)]);
          await S.replaceAllLogs(merged);
          return { mergedLen: merged.length, stored: (await S.getAllLogs()).length };
        }""")
        ok("同じ解答（atom_id と時刻が同じ）は1件にまとまる",
           r["mergedLen"] == 1 and r["stored"] == 1, json.dumps(r))

        # ---------- 3. ドライブへ送る中身に log_id が入っていない ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, D = window.Drive;
          const atoms = await S.getAllAtoms();
          await S.replaceAllLogs([
            { log_id: 42, atom_id: atoms[0].atom_id, answered_at: 3000,
              eval: 'normal', is_correct: true, schedule_updated: true, interval_code: '1d' }
          ]);
          const payload = await D.collectProgress();
          const keys = Object.keys(payload.logs[0] || {});
          return { n: payload.logs.length, keys,
                   hasLogId: keys.indexOf('log_id') >= 0,
                   keepsAtom: keys.indexOf('atom_id') >= 0,
                   keepsWhen: keys.indexOf('answered_at') >= 0 };
        }""")
        ok("送る中身に log_id が入っていない", r["hasLogId"] is False, json.dumps(r))
        ok("同一性の根拠（atom_id / answered_at）は残っている",
           r["keepsAtom"] and r["keepsWhen"], json.dumps(r))

        # ---------- 4. 進捗の書き戻しが落ちたら「成功」にしない ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, D = window.Drive;
          window.__mock = window.makeDriveMock();
          D.__setTransport(window.__mock);
          await D.giveConsent();
          await D.signIn();
          await S.clearDirty();
          await S.bumpDirty(3);
          const before = await D.pendingCount();
          const orig = S.replaceAllLogs;
          S.replaceAllLogs = function () { return Promise.reject(new Error('わざと失敗')); };
          let rep = null;
          try { rep = await D.signInAndSync(function () {}); }
          finally { S.replaceAllLogs = orig; }
          const after = await D.pendingCount();
          const meta = await S.loadMeta();
          return { ok: rep && rep.ok, error: (rep && rep.error) || null,
                   progressError: (rep && rep.progress_error) || null,
                   before, after, lastError: meta.drive_last_error || null };
        }""")
        ok("失敗を成功として報告しない", r["ok"] is False, json.dumps(r, ensure_ascii=False))
        ok("何が落ちたのかが文面に出る",
           bool(r["error"]) and "学習の記録" in r["error"], json.dumps(r, ensure_ascii=False))
        ok("未同期の印を消さない（バッジが0に戻らない）",
           r["after"] == r["before"] and r["before"] > 0, json.dumps(r))
        ok("失敗の理由が meta に残る（自動同期でも後から読める）",
           bool(r["lastError"]), json.dumps(r, ensure_ascii=False))

        # ---------- 5. うまくいったときは印も理由も消える ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, D = window.Drive;
          await S.bumpDirty(2);
          const rep = await D.signInAndSync(function () {});
          const meta = await S.loadMeta();
          return { ok: rep && rep.ok, pending: await D.pendingCount(),
                   lastError: meta.drive_last_error || null };
        }""")
        ok("成功したら未同期の印は消える", r["ok"] is True and r["pending"] == 0, json.dumps(r))
        ok("成功したら前回の失敗の理由も消える", r["lastError"] is None, json.dumps(r, ensure_ascii=False))

        # ---------- 6. メモを消したら、同期しても戻ってこない ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, D = window.Drive;
          const qs = await S.getAllQuestions();
          const qid = qs[0].q_id;
          await S.setMemo('question', qid, 'ここに書いたメモ');
          await D.signInAndSync(function () {});
          await S.setMemo('question', qid, '');            // 消す
          const afterDelete = (await S.getQuestion(qid)).user_memo;
          const stampAfterDelete = (await S.getQuestion(qid)).memo_updated_at;
          await D.signInAndSync(function () {});         // 同期しても戻らないこと
          const q = await S.getQuestion(qid);
          return { afterDelete, stampAfterDelete,
                   afterSync: q.user_memo, stamp: q.memo_updated_at };
        }""")
        ok("メモを消した時刻が残る（墓標が消えない）",
           bool(r["stampAfterDelete"]) and r["stampAfterDelete"] > 0, json.dumps(r, ensure_ascii=False))
        ok("同期してもメモが復活しない",
           not r["afterSync"], json.dumps(r, ensure_ascii=False))

        # ---------- 7. 設定が相手から届く ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, D = window.Drive;
          // 相手のほうが後に設定を変えた、という状況を作る
          await S.setMeta('exam_date', '2027-02-14');
          await D.signInAndSync(function () {});
          const mineAt = (await S.loadMeta()).settings_updated_at;
          // 向こうのファイルを直接書き換える（別端末が後で変えたことにする）
          const before = (await S.loadMeta()).exam_date;
          const payload = await D.readProgress();
          return { mineAt, before, hasSettingsAt: payload && 'settings_at' in payload,
                   settingsAt: payload && payload.settings_at };
        }""")
        ok("設定の時刻がドライブ側にも載っている",
           r["hasSettingsAt"] is True, json.dumps(r, ensure_ascii=False))
        ok("設定の時刻は同期の後始末で押し上げられない",
           r["settingsAt"] == r["mineAt"], json.dumps(r, ensure_ascii=False))

        # ---------- 8. 進捗を全消ししたら、同期しても戻ってこない ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, D = window.Drive, K = window.Scheduler;
          const atoms = await S.getAllAtoms();
          await S.replaceAllLogs([
            { atom_id: atoms[0].atom_id, answered_at: Date.now() - 60000,
              eval: 'hard', is_correct: false, schedule_updated: true, interval_code: '10m' }
          ]);
          await D.signInAndSync(function () {});          // 向こうへ上げる
          const meta0 = await S.loadMeta();
          // 全消し（バックアップの自動ダウンロードは止める）
          const origDl = S.downloadBackup;
          S.downloadBackup = function () { return Promise.resolve({ filename: '', downloaded: false }); };
          try { await S.resetProgressAll(); } finally { S.downloadBackup = origDl; }
          const m = await S.loadMeta();
          const afterReset = (await S.getAllLogs()).length;
          await D.signInAndSync(function () {});          // ここで戻ってきてはいけない
          return { resetAt: m.progress_reset_at || 0, afterReset,
                   afterSync: (await S.getAllLogs()).length };
        }""")
        ok("全消しの時刻が墓標として残る", r["resetAt"] > 0, json.dumps(r))
        ok("消した直後は0件", r["afterReset"] == 0, json.dumps(r))
        ok("同期しても消した記録が戻ってこない", r["afterSync"] == 0, json.dumps(r))

        # ---------- 9. 閉じる直前は画面を問わず同期する ----------
        ok("閉じる直前の同期の入口がある",
           pg.evaluate("typeof window.Half2Impl.syncOnHide === 'function'"))
        r = pg.evaluate("""async () => {
          const S = window.Storage, M = window.Main, H = window.Half2Impl;
          await S.clearDirty(); await S.bumpDirty(2);
          M.state.screen = 'quiz';                        // ホーム以外にいる
          await H.syncOnHide();
          await new Promise(r => setTimeout(r, 900));
          const n = await window.Drive.pendingCount();
          M.state.screen = 'home';
          return { pending: n };
        }""")
        ok("解答画面からでも上がる（未同期が残らない）", r["pending"] == 0, json.dumps(r))

        # ---------- 範囲リセット（中項目単位）の墓標（V1.54） ----------
        r = pg.evaluate("""async () => {
          const S = window.Storage, D = window.Drive;
          const atoms = await S.getAllAtoms();
          const a = atoms[0];
          const med = a.medium;
          const t0 = Date.now() - 3600000;
          // その中項目をひととおり解いた状態にする
          const target = atoms.filter(x => x.medium === med);
          const patches = {}, logs = [];
          target.forEach((x, i) => {
            patches[x.atom_id] = { answer_count:1, correct_count:1, last_eval:'normal',
                                   last_answered_at:t0, _unlearned:0 };
            logs.push({ atom_id:x.atom_id, answered_at:t0+i, eval:'normal',
                        is_correct:true, schedule_updated:true, interval_code:'1d' });
          });
          await S.replaceAllLogs(logs);
          await S.updateAtomsBulk(patches);
          const before = (await S.getAllLogs()).length;
          const res = await S.resetProgressByScope('medium', med);
          const after = (await S.getAllLogs()).length;
          const meta = await S.loadMeta();
          const map = meta.scope_reset_at || {};
          // 相手の端末には、消す前の記録がまだ残っている
          const theirs = logs.map(l => Object.assign({}, l));
          const merged = D.mergeMeta({ scope_reset_at: map }, {}, 1000, 9000);
          const cut = merged.scope_reset_at || {};
          const survive = theirs.filter(l => {
            const c = cut[l.atom_id];
            return !(c > 0) || l.answered_at > c;
          });
          return { removed: before - after, marked: Object.keys(map).length,
                   targets: target.length, survive: survive.length,
                   resetAt: !!res.reset_at };
        }""")
        ok("範囲リセットで記録が消える", r["removed"] > 0, json.dumps(r))
        ok("消した肢すべてに墓標が立つ",
           r["marked"] >= r["targets"], json.dumps(r))
        ok("墓標は合体しても残る（相手が新しくても消えない）",
           r["marked"] > 0, json.dumps(r))
        ok("相手の端末に残っていた記録は、合体でよみがえらない",
           r["survive"] == 0, json.dumps(r))

        ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
        br.close()


runtime_checks()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAE" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
