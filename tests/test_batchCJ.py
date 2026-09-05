#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCJ：TOP3は評価3件未満のテーマを出さない（V2.13・§23-⑩ 案a）

何が起きていたか：
V2.07 で全肢に中項目対応表の既定タグが付いた。その結果、1肢を「難しい」と
評価した瞬間、そのテーマは「理解率0%（評価1件）」と計算され、
最優先克服概念TOP3の先頭に出た。TOP3はタップ即「概念別弱点ノック」起動の
導線なので、評価1件のノイズが5〜10分の学習時間を誤誘導する。
裁定（2026-09-05・利用者＝案a）：evaluated_count >= 3 で足切りする。
足切りはTOP3だけ。§12-2の理解率集計・74概念アナライザーの一覧は間引かない。
"""
import io, json, os, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


sc = read("scheduler.js")
ok("足切り定数がある", "TOP3_MIN_EVALUATED = 3" in sc)
ok("TOP3が評価数を見る", "evaluated_count" in sc.split("function getTop3Concepts(")[1][:300])
ok("何が起きていたかがコードに書いてある", "§23-⑩" in sc and "誤誘導" in sc)
ok("間引く範囲の限定が書いてある", "間引くのはTOP3だけ" in sc)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(800)

    r = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      await S.saveConceptScores({
        '#CJ検証_評価1件': { score: 0,  evaluated_count: 1, atom_count: 4 },
        '#CJ検証_評価2件': { score: 0,  evaluated_count: 2, atom_count: 4 },
        '#CJ検証_評価3件': { score: 10, evaluated_count: 3, atom_count: 4 },
        '#CJ検証_理解済み': { score: 80, evaluated_count: 5, atom_count: 4 }
      });
      const top3 = await K.getTop3Concepts();
      return { tags: top3.map(t => t.tag), n: top3.length };
    }""")
    tags = r["tags"]
    ok("評価1件の0%テーマは出ない", "#CJ検証_評価1件" not in tags, json.dumps(r, ensure_ascii=False))
    ok("評価2件でもまだ出ない（境界）", "#CJ検証_評価2件" not in tags, json.dumps(r, ensure_ascii=False))
    ok("評価3件からは出る（境界）", "#CJ検証_評価3件" in tags, json.dumps(r, ensure_ascii=False))
    ok("50%以上は従来どおり出ない", "#CJ検証_理解済み" not in tags, json.dumps(r, ensure_ascii=False))
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCJ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
