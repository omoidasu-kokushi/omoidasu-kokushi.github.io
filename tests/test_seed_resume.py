# -*- coding: utf-8 -*-
"""test_seed_resume.py — 途中で止まった同梱シードの取り込みは、次の起動で続きが入る（V2.97）

【何が起きていたか】
  同梱シード（必修249問）の取り込みは __APP_READY のあとも走っている（200件ずつの
  書き込み。249問がそろうのは READY から約1秒後）。その間に閉じる・再読込すると、
  200問だけ入って seed_imported が立たないまま止まる。
  V2.96 までの init() は「問題数0のときだけ入れる」だったので、次の起動では totalQ が
  200 で条件を外れ、V2.08 の onlyExisting 更新（既存200問の上書き）しか走らず、
  **残り49問は二度と入らなかった**。
  実測（V2.96 のテストで踏んだ）：countQuestions 200 のまま、last_import_report は
  updated 200／skipped_missing 49、seed_version だけ 3.03 が入る。

【直したこと】
  条件を「問題数0」から「入れ終えた印（seed_imported）が無い」へ。
  印は取り込みが終わってから立てる（順序は変えない）。
  V1.81（全初期化は seed_imported を残す＝見本は戻らない）はそのまま：
  印が立っている端末は問題数が0でも入れない。
  続きを入れる起動では autoMarkSplittable を走らせない（全問の読み→書き戻しが
  取り込みと同時に走ると、取り込んだ直後のレコードを古い写しで上書きしうる）。

【ここで固定すること】
  ・200問・印なし の端末は、次の起動で 249問・印あり になる（新規49／更新200）
  ・印あり・0問（全初期化のあと）は、再読込しても入らない（V1.81）
  ・続きを入れた起動では auto_split_done が立たず、その次の起動で立つ
"""
import os, sys, io, json, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = io.open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()

ok("入れるかどうかは印（seed_imported）で決める", "if (!meta.seed_imported && global.SEED_QUESTIONS_TSV)" in p2)
ok("旧条件（問題数0）は残っていない", "if (!totalQ) {\n        if (!global.SEED_QUESTIONS_TSV || meta.seed_imported)" not in p2)
ok("印あり・0問は入れない（V1.81 を守る）", "if (!totalQ) { global.__INIT_DONE = true; return null; }" in p2 and "見本は戻さない" in p2)
ok("なぜ変えたかが実測つきで書いてある", "残り49問は二度と入らなかった" in p2 and "skipped_missing 49" in p2)
ok("取り込みがある起動では autoMarkSplittable を同時に走らせない（取り込みのあとに回す）",
   "!pendingImport" in p2 and "autoSplitIfNeeded" in p2)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
META = """async () => { const S = window.Storage; const m = await S.loadMeta(); const r = m.last_import_report || {};
  const mainQ = (await S.getAllQuestions()).filter(q => (q.pool||'main') !== 'mock');
  const mainA = (await S.getAllAtoms()).filter(a => (a.pool||'main') !== 'mock');
  return { n: mainQ.length, a: mainA.length, seed_imported: !!m.seed_imported,
           seed_version: m.seed_version || null, auto_split_done: !!m.auto_split_done,
           imported: r.imported, updated: r.updated, skipped_missing: r.skipped_missing || 0 }; }"""

# V2.99：体験用の予想問題（pool mock・90問）も同梱されるようになった。
# ここで見たいのは同梱シード（本体・249問）なので、数えるのは main だけ。
COUNT_MAIN = "async () => (await window.Storage.getAllQuestions()).filter(q => (q.pool||'main') !== 'mock').length"
def wait_count(pg, want, limit=30):
    t0 = time.time()
    while time.time() - t0 < limit:
        n = pg.evaluate(COUNT_MAIN)
        if n >= want: return n
        pg.wait_for_timeout(150)
    return pg.evaluate(COUNT_MAIN)

def wait_flag(pg, key, limit=15):
    t0 = time.time()
    while time.time() - t0 < limit:
        if pg.evaluate("async () => { const m = await window.Storage.loadMeta(); return !!m['%s']; }" % key): return True
        pg.wait_for_timeout(150)
    return False

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    n0 = wait_count(pg, 249)
    ok("初回起動で同梱249問が入る", n0 == 249, n0)
    ok("入れ終えると印が立つ", wait_flag(pg, "seed_imported"))
    seedv = pg.evaluate("() => window.SEED_VERSION")

    # --- 途中で止まった端末を作る：全部消して（印も消える）、シードの先頭200問だけ入れる ---
    pre = pg.evaluate("""async () => {
      const S = window.Storage;
      await S.resetAll();
      const all = JSON.parse(window.SEED_QUESTIONS_TSV).questions;
      const rep = await S.importText(JSON.stringify({ questions: all.slice(0, 200) }));
      const m = await S.loadMeta();
      return { n: (await S.getAllQuestions()).filter(q => (q.pool||'main') !== 'mock').length,
               seed_imported: !!m.seed_imported, seed_version: m.seed_version || null,
               imported: rep.imported, total: all.length };
    }""")
    ok("再現：200問・印なし・版なし（取り込みが途中で止まった端末と同じ状態）",
       pre["n"] == 200 and not pre["seed_imported"] and pre["seed_version"] is None and pre["total"] == 249, pre)

    # --- 次の起動で続きが入るか ---
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    n1 = wait_count(pg, 249, limit=20)
    ok("次の起動で 249問 になる（V2.96 までは 200 のまま）", n1 == 249, n1)
    ok("印が立つ", wait_flag(pg, "seed_imported"))
    pg.wait_for_timeout(800)
    d = pg.evaluate(META)
    ok("版も入る", d["seed_version"] == seedv, (d["seed_version"], seedv))
    # V2.99：同じ起動で体験用の予想問題（90問）も続けて入るので、last_import_report はそちらになる。
    # シードの続きが入ったことは本体の数（249）と肢の数で見る。
    ok("続きが入り、飛ばした問題が無い（本体249問）", d["n"] == 249 and d["skipped_missing"] == 0, d)
    ok("肢もそろう（249問ぶん）", d["a"] >= 249 * 4, d["a"])
    # V2.99：印づけ（autoMarkSplittable）は取り込みと同時には走らせず、取り込みが終わったあと
    # **同じ起動の中で**走る（V2.97 では次の起動に回していた）。
    ok("続きを入れた起動でも、取り込みのあとに auto_split_done が立つ", wait_flag(pg, "auto_split_done"))

    # --- 次の起動でも二重に入らない ---
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)
    ok("次の起動でも auto_split_done は立ったまま", wait_flag(pg, "auto_split_done"))
    ok("本体の問題数は 249 のまま（二重に入らない）", pg.evaluate(COUNT_MAIN) == 249)

    # --- V1.81：全初期化のあとは戻らない（印が立っているので、0問でも入れない） ---
    pg.evaluate("() => { window.Main.closeModals(); }")
    r = pg.evaluate("""async () => {
      const H = window.Half2Impl, S = window.Storage;
      await H.doResetAll();
      const m = await S.loadMeta();
      return { n: await S.countQuestions(), seed_imported: !!m.seed_imported };
    }""")
    ok("全初期化で 0問・印あり", r["n"] == 0 and r["seed_imported"], r)
    pg.reload(wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(3000)
    n3 = pg.evaluate("async () => window.Storage.countQuestions()")
    ok("再読込しても見本は戻らない（V1.81 はそのまま）", n3 == 0, n3)

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  seed_resume" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
