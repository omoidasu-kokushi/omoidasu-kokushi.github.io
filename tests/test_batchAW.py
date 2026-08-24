#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチAW：同期で残せなかったメモ（V1.72）

競合解決は「新しい方を採用」のまま。負けた側のメモ文面が
meta.sync_conflicts（端末ローカル・上限20）へ控えられ、
設定から 読む・写す・片づける ができることを固定する。
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
djs = read("drive.js")
idx = read("index.html")
import glob as _g
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
p2js = read(p2)

ok("mergeIndex が lost_memo を控える（両方向）", djs.count("lost_memo:") >= 2)
ok("syncNow が meta.sync_conflicts へ退避する", "sync_conflicts" in djs and "list.slice(0, 20)" in djs)
ok("控えの保存失敗で同期全体を止めない", "控えの保存失敗で同期全体を止めない" in djs)
ok("sync_conflicts はどの同期キー一覧にも入っていない（端末ローカル）",
   "'sync_conflicts'" not in djs.split("META_NEWER_KEYS")[1][:2000])
ok("設定に行がある", 'id="btn-sync-conflicts"' in idx and "同期で残せなかったメモ" in idx)
ok("モーダルがある", 'id="modal-conflicts"' in idx and 'id="btn-conflicts-clear"' in idx)
ok("片づけは confirmAction を通る（§4-15）",
   p2js.count("M.confirmAction") >= 2 and "この控えを片づけますか" in p2js)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1500)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(900)

    # mergeIndex 単体：負けた側の文面が両方向で控えられる
    r = pg.evaluate("""() => {
      const D = window.Drive;
      const a = D.mergeIndex(
        [{q_id:'Q1',atom_id:'',memo:'L',updated_at:200}],
        {items:[{q_id:'Q1',atom_id:'',memo:'R',updated_at:100}]}).conflicts[0];
      const b = D.mergeIndex(
        [{q_id:'Q1',atom_id:'',memo:'L',updated_at:100}],
        {items:[{q_id:'Q1',atom_id:'',memo:'R',updated_at:200}]}).conflicts[0];
      const c = D.mergeIndex(   /* メモ同一・図だけ違う → 文面は控えない */
        [{q_id:'Q2',atom_id:'',memo:'同じ',image_file_id:'x',updated_at:200}],
        {items:[{q_id:'Q2',atom_id:'',memo:'同じ',image_file_id:'y',updated_at:100}]}).conflicts[0];
      return { a: a.lost_memo, b: b.lost_memo, c: c ? c.lost_memo : 'none' };
    }""")
    ok("ローカル勝ち→リモート文面を控える", r["a"] == "R", json.dumps(r))
    ok("リモート勝ち→ローカル文面を控える", r["b"] == "L", json.dumps(r))
    ok("メモが同じ競合（図のみ）は文面を控えない", r["c"] in (None, "none"), json.dumps(r))

    # UI：控えを模擬投入 → 行が出る → 一覧が開く → コピー → 片づける
    r = pg.evaluate("""async () => {
      const qs = await window.Storage.getAllQuestions();
      const qid = qs[0].q_id;
      await window.Storage.setMeta('sync_conflicts', [
        { at: Date.now(), key: qid + '|', kept: 'remote', memo: '控えテストA' },
        { at: Date.now() - 1000, key: qid + '|x', kept: 'local', memo: '控えテストB' }]);
      await window.Half2Impl.openSettings();
      await window.Half2Impl.refreshDrive();
      const row = document.getElementById('btn-sync-conflicts');
      return { hidden: row.hidden,
               note: document.getElementById('sync-conflicts-note').textContent };
    }""")
    ok("控えがあると設定に行が出る", r["hidden"] is False, json.dumps(r, ensure_ascii=False))
    ok("行に件数が出る", "2件" in r["note"], r["note"])

    r = pg.evaluate("""async () => {
      await window.Half2Impl.openSyncConflicts();
      await new Promise(res => setTimeout(res, 300));
      const items = document.querySelectorAll('#conflict-list .conflict-item');
      return { n: items.length,
               memo: items[0].querySelector('.conflict-memo').textContent,
               open: !document.getElementById('modal-conflicts').hidden };
    }""")
    ok("一覧が開き2件表示される", r["n"] == 2 and r["open"], json.dumps(r, ensure_ascii=False))
    ok("負けた文面が全文表示される", r["memo"] == "控えテストA", r["memo"])

    pg.click("#conflict-list [data-ccopy='0']")
    pg.wait_for_timeout(300)
    clip = pg.evaluate("navigator.clipboard.readText()")
    ok("文面をコピーできる", clip == "控えテストA", clip)

    pg.click("#conflict-list [data-cdel='0']")
    pg.wait_for_timeout(400)
    ok("片づけは確認を挟む", pg.evaluate("!document.getElementById('modal-confirm').hidden"))
    pg.click("#confirm-go")
    pg.wait_for_timeout(600)
    r = pg.evaluate("""async () => {
      const mm = await window.Storage.loadMeta();
      return { left: (mm.sync_conflicts || []).length,
               reopened: !document.getElementById('modal-conflicts').hidden,
               items: document.querySelectorAll('#conflict-list .conflict-item').length };
    }""")
    ok("片づけると1件減って保存される", r["left"] == 1, json.dumps(r))
    ok("片づけ後、一覧に戻ってくる（連続で片づけられる）",
       r["reopened"] and r["items"] == 1, json.dumps(r))

    # 全部片づける
    pg.click("#btn-conflicts-clear")
    pg.wait_for_timeout(400)
    pg.click("#confirm-go")
    pg.wait_for_timeout(600)
    r = pg.evaluate("""async () => {
      const mm = await window.Storage.loadMeta();
      await window.Half2Impl.refreshDrive();
      return { left: (mm.sync_conflicts || []).length,
               rowHidden: document.getElementById('btn-sync-conflicts').hidden };
    }""")
    ok("すべて片づけると空になり行も消える", r["left"] == 0 and r["rowHidden"], json.dumps(r))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAW" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
