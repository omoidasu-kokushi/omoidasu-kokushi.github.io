# -*- coding: utf-8 -*-
"""audit_volume.py — 「量に上限が無い出力は、押す前に量を見せる」を実測する

§22 の不変条件（V1.74／V1.82）。実際に起きたこと：
  ・間違いノートの印刷が **A4 233枚**になった
  ・バックアップが上限規模で **75.6MB** になった
どちらも押してから分かるのでは遅い。

もう1つ（V1.73）：
  ・取り込みの前に容量を見積もる。見積もりは**行数ではなく形式を見て**数える。
    改行数を問題数として数え、1,173問の取り込みが丸ごと拒否された。
"""
import json, os, subprocess, sys, time

APP = os.path.expanduser("~/omo")
B = ("/sessions/ecstatic-wizardly-dijkstra/mnt/owner/Desktop/国家試験対策室/"
     "過去問抽出_20260824/分類_令和5年版")
PAYLOAD = os.path.join(B, "out", "20260907_取り込み用_過去問_照合ずみ_V1.01.json")
PORT = "8917"
R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

from playwright.sync_api import sync_playwright
import io
srv = subprocess.Popen(["python3", "-m", "http.server", PORT], cwd=APP,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)
payload = io.open(PAYLOAD, encoding="utf-8").read()

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:%s/index.html" % PORT, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("async () => { await window.Storage.setMeta('onboarding_done', true); }")
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1200)
    pg.evaluate("() => window.Main.closeModals()")

    # ---- V1.73：見積もりは行数ではなく形式で数える ----
    est = pg.evaluate("""async (txt) => {
      const S = window.Storage;
      const f = S.estimateImportRows;
      if (!f) { return { missing: true }; }
      const oneline = JSON.stringify(JSON.parse(txt));   /* 改行を全部消す */
      return { normal: await f(txt), oneline: await f(oneline) };
    }""", payload)
    if est.get("missing"):
        ok("取り込み前の見積もりが外から呼べる", False, "estimateImport が見つからない")
    else:
        n1 = est["normal"]; n2 = est["oneline"]
        def num(x):
            if isinstance(x, dict):
                return x.get("questions") or x.get("count") or x.get("rows")
            return x
        ok("改行を消しても同じ数に見積もる（V1.73）", num(n1) == num(n2),
           "改行あり %s / 1行 %s" % (json.dumps(n1, ensure_ascii=False), json.dumps(n2, ensure_ascii=False)))

    imp = pg.evaluate("async (t) => await window.Storage.importText(t)", payload)
    ok("配布物443問を取り込める", imp.get("imported", 0) > 400, imp.get("imported"))

    # ---- V1.82：書き出す前に大きさを見せる ----
    sz = pg.evaluate("""async () => {
      const S = window.Storage;
      const f = S.estimateBackupBytes;
      if (!f) { return { missing: true }; }
      return { est: await f() };
    }""")
    if sz.get("missing"):
        ok("バックアップの大きさを事前に出せる（V1.82）", False, "estimateBackupSize が見つからない")
    else:
        ok("バックアップの大きさを事前に出せる（V1.82）", True, json.dumps(sz, ensure_ascii=False))

    # ---- V1.74：間違いノートの枚数を事前に出す ----
    pr = pg.evaluate("""async () => {
      const H = window.Half2Impl, S = window.Storage;
      /* 全部を「難しい」にして、印刷が最大量になる状態を作る */
      const at = await S.getAllAtoms();
      for (let i = 0; i < at.length; i += 1) {
        if (i % 3) { continue; }
        await S.updateAtom(at[i].atom_id, { answer_count: 1, last_eval: 'hard' });
      }
      /* 印刷の対象は「難しい」と★。設定画面を開いて、枚数の表示を読む。 */
      window.Main.go('settings');
      await new Promise(r => setTimeout(r, 700));
      const n = await H.refreshNoteCount();
      const el = document.getElementById('note-count');
      return { n: n, text: el ? el.textContent : null,
               sheets1: H.noteSheetsFor ? H.noteSheetsFor(400, '1', 'all') : null,
               sheets2: H.noteSheetsFor ? H.noteSheetsFor(400, '2', 'none') : null };
    }""")
    txt = (pr.get("text") or "")
    ok("印刷の前に「何問・およそ何枚か」が出る（V1.74）",
       ("問" in txt and "枚" in txt), json.dumps(pr, ensure_ascii=False))
    ok("400問なら三桁の枚数になる（知らずに始めさせない）",
       (pr.get("sheets1") or 0) >= 100, "1段解説あり %s枚 / 2段解説なし %s枚"
       % (pr.get("sheets1"), pr.get("sheets2")))

    ok("JSエラーが出ていない", not errs, " / ".join(errs[:3]))
    br.close()
srv.terminate()

bad = [x for x in R if not x[0]]
for good, name, d in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + d) if not good else ""))
print("\n%d/%d  量を見せる" % (len(R) - len(bad), len(R)))
