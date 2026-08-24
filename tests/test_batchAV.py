#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチAV：取り込み時の分類ガード（V1.71）

391バッチのNB分類は表記ゆれを起こしやすく、中項目名が1字違うだけで
3階層ツリーが分裂する。出題基準タキソノミー（458中項目・questions.js）と
突合して警告が出ることを固定する。ブロックはしない（出題基準の改定や
意図的な独自分類を止めないため）。
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
qjs = read("questions.js")
sjs = read("storage.js")
import glob as _g
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
p2js = read(p2)

ok("questions.js に TAXONOMY_MASTER がある", "const TAXONOMY_MASTER" in qjs)
ok("TAXONOMY_MASTER が window に公開されている",
   "window.TAXONOMY_MASTER = TAXONOMY_MASTER" in qjs)
ok("storage.js に taxHas / taxCheckInto がある",
   "function taxHas(" in sjs and "function taxCheckInto(" in sjs)
ok("正規化は全角括弧・山括弧・空白を吸収する",
   "＜＞" in sjs.replace("[＜＞]", "＜＞") and "（）" in sjs.replace("[（）]", "（）"))
ok("part2 が tax_bad を表示する", "rep.tax_bad" in p2js and "出題基準に無い分類" in p2js)
ok("マスター不在時は検査しない（他環境での安全）",
   "if (!master || !master.length) { return true; }" in sjs)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

def q(medium, stem):
    return {"unit": "必修問題", "major": "1. 健康に関する指標", "medium": medium,
            "sub_item": "a. 総人口", "rank": "B", "pool": "main",
            "question_type": "single", "select_count": 1, "stem": stem,
            "atoms": [
                {"original_num": 1, "is_correct": True, "text": "正しい",
                 "statement": "正しい。", "explanation": "理由", "tags": ["#人口動態統計"]},
                {"original_num": 2, "is_correct": False, "text": "誤り",
                 "statement": "誤り。", "explanation": "理由", "tags": ["#人口動態統計"]}]}

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
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

    n = pg.evaluate("(window.TAXONOMY_MASTER || []).length")
    ok("マスターは458中項目", n == 458, str(n))

    r = pg.evaluate("""async (txt) => {
      const rep = await window.Storage.importText(txt, {});
      return { bad: rep.tax_bad, ex: rep.tax_examples, imported: rep.imported };
    }""", json.dumps({"questions": [q("A. 人口静態・人口動態", "分類ガード検証・正 v1")]},
                     ensure_ascii=False))
    ok("正しい分類は警告なし", r["bad"] == 0, json.dumps(r, ensure_ascii=False))
    ok("正しい分類は取り込まれる", r["imported"] == 1, str(r["imported"]))

    r = pg.evaluate("""async (txt) => {
      const rep = await window.Storage.importText(txt, {});
      return { bad: rep.tax_bad, ex: rep.tax_examples, imported: rep.imported };
    }""", json.dumps({"questions": [q("A. 人口静態と人口動態", "分類ガード検証・誤 v1")]},
                     ensure_ascii=False))
    ok("1字違いの中項目は警告される", r["bad"] == 1, json.dumps(r, ensure_ascii=False))
    ok("警告に実例（パンくず）が入る",
       r["ex"] and "人口静態と人口動態" in r["ex"][0], json.dumps(r["ex"], ensure_ascii=False))
    ok("警告してもブロックはしない（取り込まれる）", r["imported"] == 1, str(r["imported"]))

    # 全角括弧・山括弧の表記ゆれは許容される（警告しない）
    r = pg.evaluate("""async (txt) => {
      const rep = await window.Storage.importText(txt, {});
      return { bad: rep.tax_bad };
    }""", json.dumps({"questions": [
        {**q("B. 特異的生体防御反応（免疫系）", "分類ガード検証・括弧ゆれ v1"),
         "unit": "人体の構造と機能", "major": "9. 生体の防御機構"}]},
        ensure_ascii=False))
    ok("全角/半角括弧のゆれは警告しない", r["bad"] == 0, json.dumps(r))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAV" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
