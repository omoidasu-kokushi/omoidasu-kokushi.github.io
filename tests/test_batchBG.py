#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBG：バックアップの大きさを押す前に見せる／消す前に同期を確かめる（V1.82）

上限規模の実測（DESIGN_DECISIONS §6-9）で、`exportBackup()` の書き出しが
**75.6MB** になることが分かった。しかもこれは全初期化の直前とメモありの
取り込み直前に**自動で走る**ので、「失わないための仕組み」のほうが先に重くなる。

いま入れたのは2つだけ。
  ・書き出す前に大きさを見せる（§4-25 を書き出しにも当てた）
  ・消す前に、ログイン中なら1回送る。**送れなかったら消さない**

gzip 化（貼り付け復元を失う）は採らなかった。判断の記録は
`claude/20260825_バックアップ75MB問題_判断待ち_V1.00.md`。
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

idx = read("index.html")
st  = read("storage.js")
css = read("styles.css")
p2  = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js  = read(p2)

# ---------------------------------------------------------------- 静的検査
ok("見積り関数がある", "function estimateBackupBytes(" in st and "estimateBackupBytes  : estimateBackupBytes," in st)
ok("見積りは全件を組み立てない（抜き取り）", "function samplePerRowBytes(" in st and "BACKUP_SAMPLE" in st)
ok("画像が30MB超で入らない場合を見積りから外す", "user_files_included" in st and "BACKUP_FILES_CAP" in st)
ok("なぜ要るかが書いてある", "75.6MB" in st and "失わないための仕組み" in st)
ok("表示欄がある", 'id="backup-size"' in idx)
ok("初期化ダイアログに内訳欄がある", 'id="reset-detail"' in idx)
ok("表示のCSSがある", ".backup-size" in css and ".modal-detail" in css)
ok("設定を開いたら見積りを出す", "refreshBackupSize().catch(noop)" in js)
ok("取り込みのあとに数え直す", js.count("refreshBackupSize().catch(noop)") >= 3)
ok("消す前に送る関数がある", "function syncBeforeReset(" in js)
ok("送れなければ確認で止める", "それでも消す" in js and "まだ消していません" in js)
ok("ログインしていなければ送らない（勝手にログイン窓を出さない）",
   "D.tokenValid && D.tokenValid()" in js.split("function syncBeforeReset(")[1][:400])
ok("初期化ダイアログは専用の開き方を通る", "openResetModal()" in js and "function openResetModal(" in js)
ok("同期を使っていない人にはそう言う", "同期を使っていません" in js)
ok("gzipにはしていない（貼り付け復元を残す）", ".json.gz" not in st and ".json.gz" not in js)
# 版番号は**絶対値で書かない**。batchAC が「上がっているか」と
# 「3箇所そろっているか」を見ているので、ここは重複させず、
# BG が入れた中身だけを見る。（V1.82 で 1.82 を直書きし、V1.83 で赤くした）
ok("問い合わせ先などの版表記は index.html 側で一元管理", 'id="build-stamp-settings"' in idx)

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
    pg.wait_for_timeout(1800)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(700)

    # --- 見積りが実物とどれだけ違うか（ここが緩むと表示が嘘になる）
    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const t0 = performance.now();
      const est = await S.estimateBackupBytes();
      const estMs = Math.round(performance.now() - t0);
      const real = JSON.stringify(await S.exportBackup());
      const realBytes = new Blob([real]).size;
      return { est: est, estMs: estMs, realBytes: realBytes,
               ratio: est.bytes / realBytes,
               q: await S.countQuestions() };
    }""")
    ratio = r["ratio"]
    ok("見積りが実物の±15%以内", 0.85 <= ratio <= 1.15,
       "見積り %d / 実物 %d （%.3f倍）" % (r["est"]["bytes"], r["realBytes"], ratio))
    ok("見積りは全件の組み立てより速い", r["estMs"] < 1500, "%dms" % r["estMs"])
    ok("件数が入っている", r["est"]["counts"]["questions"] == r["q"], json.dumps(r["est"]["counts"]))
    ok("この規模ではまだ警告を出さない", r["est"]["big"] is False, str(r["est"]["bytes"]))

    # --- 設定画面に大きさが出る
    pg.evaluate("window.Half2Impl.openSettings ? window.Half2Impl.openSettings() : window.Main.go('settings')")
    pg.wait_for_timeout(2000)
    txt = (pg.text_content("#backup-size") or "").strip()
    hidden = pg.evaluate("document.querySelector('#backup-size').hidden")
    ok("設定画面に書き出しの大きさが出る", (not hidden) and "書き出しは約" in txt, txt[:140])
    ok("内訳（問題・選択肢）も出る", "問題" in txt and "選択肢" in txt, txt[:140])

    # 記録が入ったら、その件数も出る（0件の行はそもそも出さないのが正しい）
    n2 = pg.evaluate("""async () => {
      await window.Storage.appendLogs([{ atom_id: (await window.Storage.getAllAtoms())[0].atom_id,
        eval:'normal', is_correct:true, mode:'random', answered_at: Date.now(),
        interval_code:'1d', srs_step_after:1, schedule_updated:true, think_ms:2000 }]);
      await window.Half2Impl.refreshBackupSize();
      return (document.querySelector('#backup-size') || {}).textContent || '';
    }""")
    ok("記録が入れば件数も出る", "学習の記録 1件" in n2, n2[:140])

    # --- 全初期化ダイアログ
    pg.click("#btn-reset-all")
    pg.wait_for_timeout(1800)
    det = (pg.text_content("#reset-detail") or "").strip()
    ok("消える中身がダイアログに出る", "消えるもの" in det, det[:160])
    ok("退避ファイルの大きさが出る", "自動で書き出すファイル" in det, det[:160])
    ok("同期で守られていないことを言う", "同期" in det, det[:160])
    ok("数えている途中の文言が残らない", "数えています" not in det, det[:80])

    # --- やめれば消えない
    pg.click("#modal-reset [data-close]")
    pg.wait_for_timeout(600)
    ok("やめれば中身は残る", pg.evaluate("window.Storage.countQuestions()") == r["q"])

    # --- 同期が失敗したら消さない（失敗注入）
    inj = pg.evaluate("""async () => {
      const D = window.Drive, H = window.Half2Impl, S = window.Storage;
      const before = await S.countQuestions();
      const okOrig = D.tokenValid, syncOrig = D.autoSync;
      let called = 0;
      D.tokenValid = () => true;
      D.autoSync = () => { called++; return Promise.reject(new Error('通信できません')); };
      const p = H.runResetAll();
      await new Promise(r => setTimeout(r, 1200));
      const title = (document.querySelector('#confirm-title') || {}).textContent || '';
      const open = !document.querySelector('#modal-confirm').hidden;
      // 「やめる」を押す
      const cancel = document.querySelector('#modal-confirm [data-close]');
      if (cancel) cancel.click();
      await p.catch(() => {});
      await new Promise(r => setTimeout(r, 800));
      D.tokenValid = okOrig; D.autoSync = syncOrig;
      return { before, after: await S.countQuestions(), called, title, open };
    }""")
    ok("消す前に同期を1回だけ試す", inj["called"] == 1, json.dumps(inj, ensure_ascii=False))
    ok("送れなかったら確認で止まる", inj["open"] and "送れませんでした" in inj["title"],
       json.dumps(inj, ensure_ascii=False))
    ok("そこで［やめる］を押せば中身は消えない（ここが核心）",
       inj["after"] == inj["before"] and inj["after"] > 0, json.dumps(inj, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBG" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
