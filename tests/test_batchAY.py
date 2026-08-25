#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチAY：間違いノート印刷の量を、印刷する前に見せる（V1.74）

実測：1,173問を入れて「難しい」が100問たまると、A4・1段・解説ありで
**34.5枚**（400問なら233枚）。V1.73 までは上限も枚数の表示も無く、
利用者は何枚出るか分からないまま印刷画面を開いていた。

このバッチは「対象数と枚数の目安が出る」「絞ったときは何問中何問かを
紙面にも書く」「全部のときは従来どおり順序も件数も変えない」を固定する。
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
idx = read("index.html")
css = read("styles.css")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)

ok("ダイアログに問題数の選択がある", 'id="note-limit"' in idx and '直近100問' in idx)
ok("ダイアログに対象数の表示欄がある", 'id="note-count"' in idx)
ok("読み上げに載る（aria-live）", 'id="note-count"' in idx and 'aria-live="polite"' in idx)
ok("表示欄のスタイルがある", ".note-count{" in css)
ok("既存トークンを使う（新しい色名を作らない）", "--surface-soft" not in css)
ok("part2 に limitNoteItems がある", "function limitNoteItems(" in js)
ok("part2 に refreshNoteCount がある", "function refreshNoteCount(" in js)
ok("枚数の係数は実測に由来する（コメントに根拠）",
   "NOTE_PAGE_PER_Q" in js and "34.5枚" in js)
ok("開いたときと選択を変えたときに数え直す",
   "openModal('#modal-note');" in js and "refreshNoteCount();" in js and "'#note-limit'" in js)
ok("紙面に『何問中何問』を書く（黙って切らない）", "問中 '" in js and "最後に解いた順" in js)
ok("全部のときは並べ替えない（従来の順序を変えない）", "絞るときだけ並べ替える" in js)

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

    # 30問ぶんの「難しい」を作る（時刻をずらして、新しい順が判別できるようにする）
    made = pg.evaluate("""async () => {
      const S = window.Storage;
      const atoms = await S.getAllAtoms();
      const byQ = {};
      atoms.forEach(a => { (byQ[a.q_id] = byQ[a.q_id] || []).push(a); });
      const qids = Object.keys(byQ).slice(0, 30);
      const patch = {};
      const now = Date.now();
      qids.forEach((q, i) => {
        patch[byQ[q][0].atom_id] = { last_eval: 'hard', answer_count: 1,
                                     last_answered_at: now - (30 - i) * 60000 };
      });
      await S.updateAtomsBulk(patch);
      return { made: qids.length, newest: qids[qids.length - 1] };
    }""")
    ok("下ごしらえ：30問を「難しい」にできた", made["made"] == 30, json.dumps(made))

    # 対象数の表示（設定画面を開いてから、利用者と同じ操作で押す）
    pg.evaluate("window.Main.go('settings')")
    pg.wait_for_timeout(700)
    pg.click("#btn-note-print")
    pg.wait_for_timeout(900)
    txt = pg.text_content("#note-count") or ""
    ok("開いた時点で対象数が出る", "対象 30問" in txt, txt)
    ok("枚数の目安が出る", "およそ" in txt and "枚" in txt, txt)

    # 絞ると表示が変わる
    pg.select_option("#note-limit", "20")
    pg.wait_for_timeout(700)
    txt2 = pg.text_content("#note-count") or ""
    ok("絞ると対象数が変わる", "対象 20問" in txt2, txt2)
    ok("全体の数も併記する（何を落としたか分かる）", "全30問中" in txt2, txt2)

    # 解説なしにすると枚数の目安が減る
    n_all = pg.evaluate("window.Half2Impl.noteSheetsFor(100, '1', 'all')")
    n_none = pg.evaluate("window.Half2Impl.noteSheetsFor(100, '1', 'none')")
    n_two = pg.evaluate("window.Half2Impl.noteSheetsFor(100, '2', 'all')")
    ok("解説なしのほうが枚数が少ない", n_none < n_all, "%s < %s" % (n_none, n_all))
    ok("2段のほうが枚数が少ない", n_two < n_all, "%s < %s" % (n_two, n_all))
    ok("100問・A4・1段・解説ありは実測どおり30枚台", 30 <= n_all <= 40, str(n_all))

    # 紙面：絞ったときは「何問中何問」
    r = pg.evaluate("""async () => {
      const H = window.Half2Impl;
      const a = await H.buildPrintSheet({ kind:'hard', paper:'A4', cols:'1', explain:'all', limit:20 });
      const s = document.getElementById('print-sheet');
      const metaLimited = s.querySelector('.pn-meta').textContent;
      const b = await H.buildPrintSheet({ kind:'hard', paper:'A4', cols:'1', explain:'all', limit:0 });
      const metaAll = document.getElementById('print-sheet').querySelector('.pn-meta').textContent;
      return { limited: a.count, total: a.total, metaLimited: metaLimited,
               all: b.count, metaAll: metaAll,
               parent: document.getElementById('print-sheet').parentElement.tagName };
    }""")
    ok("絞ると印刷対象がその数になる", r["limited"] == 20, json.dumps(r))
    ok("総数は保持される", r["total"] == 30, json.dumps(r))
    ok("紙面に『30問中 20問』と書く", "30問中 20問" in r["metaLimited"], r["metaLimited"])
    ok("『最後に解いた順』だと明記する", "最後に解いた順" in r["metaLimited"], r["metaLimited"])
    ok("全部のときは総数だけを書く（従来の文面）",
       "30問" in r["metaAll"] and "中" not in r["metaAll"], r["metaAll"])
    ok("全部のときは全件そろう", r["all"] == 30, json.dumps(r))
    ok("紙面は body 直下のまま（V1.70の修正を壊していない）", r["parent"] == "BODY", r["parent"])

    # 絞ったときに残るのは「新しい順」の上位
    order = pg.evaluate("""() => {
      const H = window.Half2Impl;
      const items = [{q:'a', last_at: 10}, {q:'b', last_at: 300}, {q:'c', last_at: 200}];
      return H.limitNoteItems(items, 2).map(x => x.q).join(',');
    }""")
    ok("絞り込みは最後に解いた順（新しいものを残す）", order == "b,c", order)
    keep = pg.evaluate("""() => {
      const H = window.Half2Impl;
      const items = [{q:'a', last_at: 10}, {q:'b', last_at: 300}, {q:'c', last_at: 200}];
      return H.limitNoteItems(items, 0).map(x => x.q).join(',');
    }""")
    ok("上限なしなら順序を変えない", keep == "a,b,c", keep)

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAY" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
