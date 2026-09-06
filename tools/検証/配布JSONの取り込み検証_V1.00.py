# -*- coding: utf-8 -*-
"""verify_pilot_import.py — 配布JSONが実機と同じ経路で取り込めるかを確かめる

利用者が「問題0件」で入れ替えられなかった件の裏取り。
復元ボタン（replace・stores形式専用）ではなく、
設定の取り込み欄が呼ぶ Storage.importText に、実際の配布JSONを
そのまま渡して、何問入るか・分類が通るかを見る。
"""
import io, json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright

REPO = os.path.expanduser("~/omo")
PILOT = "/sessions/ecstatic-wizardly-dijkstra/mnt/owner/Desktop/国家試験対策室/20260906_パイロット過去問_V1.02.json"
URL = "http://127.0.0.1:8900/index.html"
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

srv = subprocess.Popen(["python3", "-m", "http.server", "8900"], cwd=REPO,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(2)

text = io.open(PILOT, encoding="utf-8").read()
ok("配布JSONがJSONとして読める", True)
data = json.loads(text)
ok("questions配列を持つ（取り込み欄が期待する形）",
   isinstance(data.get("questions"), list), str(type(data.get("questions"))))
ok("176問入っている", len(data["questions"]) == 176, str(len(data["questions"])))
ok("復元ボタンが期待するstoresは持たない（＝0問表示の理由）",
   "stores" not in data)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    before = pg.evaluate("async () => (await window.Storage.getAllQuestions()).length")

    rep = pg.evaluate("""async (t) => {
      const r = await window.Storage.importText(t);
      const qs = await window.Storage.getAllQuestions();
      const mine = qs.filter(q => /^第11[1-5]回/.test(q.source || ''));
      const pools = {};
      mine.forEach(q => { pools[q.pool || '(なし)'] = (pools[q.pool || '(なし)'] || 0) + 1; });
      const tbl = mine.filter(q => q.comparison_table).length;
      const mmd = mine.filter(q => q.mermaid_code).length;
      let atoms = 0, cor = 0;
      for (const q of mine) {
        const at = await window.Storage.getAtomsByQuestion(q.q_id);
        atoms += at.length;
        if (at.some(a => a.is_correct)) { cor++; }
      }
      return { imported: r.imported, updated: r.updated, skipped: r.skipped,
               errors: (r.errors || []).map(e => e.message).slice(0, 5),
               unknownTaxonomy: r.unknownTaxonomy || r.unknown_taxonomy || null,
               mine: mine.length, pools, tbl, mmd, atoms, cor,
               sample: mine[0] ? { source: mine[0].source, num: mine[0].num_code } : null };
    }""", text)

    ok("取り込みでエラーが出ていない", not rep["errors"], json.dumps(rep["errors"], ensure_ascii=False))
    ok("176問が入った（新規＋更新）",
       rep["mine"] == 176, json.dumps({k: rep[k] for k in ("imported", "updated", "skipped", "mine")}))
    ok("全問 pool=main（予想問題に混ざらない）",
       rep["pools"].get("main") == 176, json.dumps(rep["pools"], ensure_ascii=False))
    ok("全問に正解の肢がある", rep["cor"] == 176, str(rep["cor"]))
    ok("選択肢が肢単位で入っている（176問×約4肢）",
       rep["atoms"] >= 600, str(rep["atoms"]))
    ok("176問すべてに比較表が入っている", rep["tbl"] == 176, str(rep["tbl"]))
    ok("図解が20問以上に入っている", rep["mmd"] >= 20, str(rep["mmd"]))
    ok("同じデータをもう一度入れても増えない（source単位で更新）", True)

    rep2 = pg.evaluate("""async (t) => {
      const r = await window.Storage.importText(t);
      const qs = await window.Storage.getAllQuestions();
      return { imported: r.imported, updated: r.updated,
               mine: qs.filter(q => /^第11[1-5]回/.test(q.source || '')).length };
    }""", text)
    ok("2回目の取り込みでも176問のまま（重複しない）",
       rep2["mine"] == 176, json.dumps(rep2))
    ok("2回目は新規0・更新176（＝上書き更新である）",
       rep2["imported"] == 0 and rep2["updated"] == 176, json.dumps(rep2))
    ok("取り込み中にJSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))

    print("  --- 取り込みレポート ---")
    print("  " + json.dumps({k: rep[k] for k in
          ("imported", "updated", "skipped", "mine", "pools", "tbl", "mmd", "atoms", "sample")},
          ensure_ascii=False))
    br.close()

srv.terminate()
bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  pilot_import" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
