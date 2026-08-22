#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V1.39 検証：ログイン＝同期の1ボタン化／トークンの持ち越し／未同期件数／
             自動同期の安全条件／ブラウザ案内とPWA導線"""
import json, os, sys, subprocess, glob, re
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", "drive.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
sw  = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
drv = open(os.path.join(APP, "drive.js"), encoding="utf-8").read()
p1s = open(os.path.join(APP, P1), encoding="utf-8").read()
p2s = open(os.path.join(APP, P2), encoding="utf-8").read()

ok("index の script/REQUIRED が実ファイルを指す", idx.count(P1) == 2 and idx.count(P2) == 2)
ok("sw の CORE_ASSETS が実ファイルを指す", P1 in sw and P2 in sw)
_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.28.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 28, 0),
   _c.group(0) if _c else "not found")

ok("ログインボタンが独立して残っていない", 'id="btn-drive-login"' not in idx)
ok("同期ボタンに未同期バッジがある", 'id="drive-pending"' in idx)
ok("ブラウザ案内の置き場がある", 'id="drive-browser-note"' in idx)
ok("ホーム画面追加の導線がある", 'id="btn-pwa-install"' in idx and 'id="btn-pwa-how"' in idx)
ok("ログイン＝同期の入口がある", "signInAndSync" in drv and "signInAndSync" in p2s)
ok("押さずに走る同期がある", "function autoSync" in drv)
ok("トークンを持ち越す仕掛けがある", "restoreToken" in drv and "drive_token" in drv)
ok("起動時に自動同期を試す（V1.40でスプラッシュへ移設）",
   "resolveSplash" in p1s and "D.autoSync" in p1s)
ok("ホーム復帰で自動同期を試す", "scheduleAutoSync(8000)" in p1s)
ok("学習中は自動同期しない条件がある", "autoSyncSafeNow" in p2s)
# 画面に出る文言だけを見る。ソースのコメントに製品名が出るのは
# 「なぜこの対策が要るか」の記録として必要なので、対象にしない。
_help = re.search(r"function showBrowserHelp[\s\S]*?\n  \}", p2s)
ok("案内の文言でブラウザを名指ししていない（条件で書く）",
   bool(_help) and "Brave" not in _help.group(0), "showBrowserHelp not found" if not _help else "")

MOCK = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_drive.js"),
            encoding="utf-8").read()

def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text)
          if m.type == "error" and not _external(m.text) else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(1500)
    try: pg.click("#welcome-start", timeout=2500)
    except Exception: pass
    pg.wait_for_timeout(500)
    pg.add_script_tag(content=MOCK)

    # ---------- 未同期の件数 ----------
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      await S.clearDirty();
      const a0 = await S.getDirty();
      const atoms = await S.getAllAtoms();
      await S.toggleAtomStar(atoms[0].atom_id);
      const a1 = await S.getDirty();
      const qs = await S.getAllQuestions();
      await S.toggleQuestionStar(qs[0].q_id);
      const a2 = await S.getDirty();
      await S.putUserImage(qs[0].q_id, new Blob([new Uint8Array([1,2])], {type:'image/jpeg'}),
                           {skipShrink:true, updatedAt: 500});
      const a3 = await S.getDirty();
      await S.deleteUserImage(qs[0].q_id, {deletedAt: 600});
      const a4 = await S.getDirty();
      return { a0, a1, a2, a3, a4 };
    }""")
    ok("未同期の初期値は0", r["a0"] == 0, json.dumps(r))
    ok("アトム★で1件増える", r["a1"] == 1, json.dumps(r))
    ok("問題★で1件増える", r["a2"] == 2, json.dumps(r))
    ok("図の追加で1件増える", r["a3"] == 3, json.dumps(r))
    ok("図の削除で1件増える", r["a4"] == 4, json.dumps(r))

    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const before = await S.getDirty();
      const atoms = await S.getAllAtoms();
      // 解答を1件積む（scheduler 経由の正規の経路）
      await S.commitAnswer(atoms[0].atom_id,
        { answer_count: (atoms[0].answer_count||0)+1, last_eval: 'normal' },
        { eval: 'normal', correct: true, answered_at: Date.now(), schedule_updated: false });
      const after = await S.getDirty();
      return { before, after };
    }""")
    ok("解答で1件増える", r["after"] == r["before"] + 1, json.dumps(r))

    # ---------- 同期でカウンタが0に戻る ----------
    r = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage;
      window.__mock = window.makeDriveMock();
      D.__setTransport(window.__mock);
      await D.giveConsent();
      await D.signIn();
      const rep = await D.syncNow();
      return { ok: rep.ok, dirty: await S.getDirty() };
    }""")
    ok("同期に成功すると未同期が0に戻る", r["ok"] and r["dirty"] == 0, json.dumps(r))

    # ---------- トークンの持ち越し ----------
    r = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage;
      const m1 = await S.loadMeta();
      const saved = !!(m1.drive_token && m1.drive_token.access_token);
      // 「アプリを開き直した」状態＝メモリ上のトークンだけ消す
      D.__state.token = null;
      const beforeValid = D.tokenValid();
      const t = await D.restoreToken();
      return { saved, beforeValid, restored: !!t, nowValid: D.tokenValid() };
    }""")
    ok("トークンが保存される", r["saved"], json.dumps(r))
    ok("開き直した直後は無効", r["beforeValid"] is False)
    ok("期限内なら押さずに戻せる（＝再ログイン不要）",
       r["restored"] and r["nowValid"], json.dumps(r))

    r = pg.evaluate("""async () => {
      const D = window.Drive, S = window.Storage;
      // 期限切れの控えを置く
      await S.setMeta('drive_token', {access_token:'old', expires_at: Date.now() - 1000});
      D.__state.token = null;
      const t = await D.restoreToken();
      const m = await S.loadMeta();
      return { restored: !!t, left: !!m.drive_token };
    }""")
    ok("期限切れの控えは戻さない", r["restored"] is False, json.dumps(r))
    ok("期限切れの控えは捨てる", r["left"] is False, json.dumps(r))

    # ---------- 押さずに走る同期 ----------
    r = pg.evaluate("""async () => {
      const D = window.Drive;
      D.__state.token = null;
      const noToken = await D.autoSync();
      await D.signIn();
      const withToken = await D.autoSync();
      return { noToken, withToken: { ok: withToken.ok, skipped: !!withToken.skipped } };
    }""")
    ok("ログインしていなければ自動同期は黙って見送る",
       r["noToken"]["skipped"] and r["noToken"]["reason"] == "NOT_SIGNED_IN",
       json.dumps(r["noToken"]))
    ok("期限内なら自動同期が走る",
       r["withToken"]["ok"] and not r["withToken"]["skipped"], json.dumps(r["withToken"]))

    # ---------- ログイン＝同期 ----------
    r = pg.evaluate("""async () => {
      const D = window.Drive;
      D.__state.token = null;
      const rep = await D.signInAndSync();
      return { ok: rep.ok, signedIn: D.tokenValid() };
    }""")
    ok("1回の呼び出しでログインと同期が済む",
       r["ok"] and r["signedIn"], json.dumps(r))

    # ---------- 学習中は自動同期しない ----------
    r = pg.evaluate("""() => {
      const H = window.Half2Impl, M = window.Main;
      const before = M.state.screen;
      M.state.screen = 'quiz';
      const onQuiz = H.autoSyncSafeNow();
      M.state.screen = 'home';
      const saveQ = M.state.current.question;
      M.state.current.question = null;
      const onHome = H.autoSyncSafeNow();
      M.state.current.question = saveQ;
      M.state.screen = before;
      return { onQuiz, onHome };
    }""")
    ok("学習中は自動同期しない", r["onQuiz"] is False, json.dumps(r))
    ok("ホームなら自動同期する", r["onHome"] is True, json.dumps(r))

    # ---------- 画面表示 ----------
    pg.evaluate("window.Main.go('settings')")
    pg.wait_for_timeout(300)
    r = pg.evaluate("""async () => {
      const S = window.Storage, H = window.Half2Impl;
      await S.clearDirty(); await S.bumpDirty(3);
      await H.refreshDrive();
      const b = document.getElementById('drive-pending');
      const lb = document.getElementById('drive-sync-label');
      const btn = document.getElementById('btn-drive-sync');
      return { hidden: b.hidden, text: b.textContent,
               label: lb.textContent, disabled: btn.disabled };
    }""")
    ok("未同期があるとバッジが出る", r["hidden"] is False and r["text"] == "3", json.dumps(r))
    ok("ログイン済みなら「今すぐ同期」", r["label"] == "今すぐ同期", json.dumps(r))
    ok("同期ボタンは押せる", r["disabled"] is False)

    r = pg.evaluate("""async () => {
      const D = window.Drive, H = window.Half2Impl;
      D.__state.token = null;
      await window.Storage.setMeta('drive_token', null);
      await H.refreshDrive();
      const btn = document.getElementById('btn-drive-sync');
      return { label: document.getElementById('drive-sync-label').textContent,
               disabled: btn.disabled };
    }""")
    ok("未ログインでも押せる（押した1回でログインまで済む）",
       r["disabled"] is False, json.dumps(r))
    ok("未ログインなら「ログインして同期」", r["label"] == "ログインして同期", json.dumps(r))

    # ---------- ブラウザ案内 ----------
    r = pg.evaluate("""() => {
      window.Half2Impl.showBrowserHelp('popup_failed_to_open');
      const el = document.getElementById('drive-browser-note');
      const cs = getComputedStyle(el);
      return { hidden: el.hidden, text: el.innerText,
               fg: cs.color, bg: cs.backgroundColor };
    }""")
    ok("案内が出る", r["hidden"] is False)
    ok("案内にポップアップ許可の手順がある", "ポップアップの許可" in r["text"])
    ok("案内に別ブラウザの案内がある", "Chrome" in r["text"])
    ok("案内にホーム画面追加の案内がある", "ホーム画面に追加" in r["text"])

    def lum(c):
        v = [int(x) / 255 for x in re.findall(r"\d+", c)[:3]]
        v = [(u / 12.92) if u <= 0.03928 else (((u + 0.055) / 1.055) ** 2.4) for u in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    l1, l2 = lum(r["fg"]), lum(r["bg"])
    ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
    ok("案内の文字と背景のコントラストが4.5以上", ratio >= 4.5,
       "%.2f  fg=%s bg=%s" % (ratio, r["fg"], r["bg"]))

    ok("実行中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  batchW" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
