#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2.09 検証：取り込みの取りこぼし2件と、解説styleからの外部通信の再発を固定する

何が起きていたか（実測・別セッションの作業を引き取り）：
 1. Excel は改行入りのセルを "…" で包んで書き出す。TSV を \\n で割るとそのセルの途中で
    行が切れ、2行とも列数不足→スキップになり、**問題が黙って消えていた**
 2. 「１. 健康の定義と理解」（全角の1）が別の大項目として単元別の木に生え、
    num_code が [1-?-…] になっていた
 3. style の url( を字面で止めていたが、CSSエスケープ（\\75rl( ）や image-set( で
    外部へリクエストが飛んでいた（V1.84 で止めたはずの再発）

固定すること：
 - 引用符付きの改行入りセルを含む行が、1問として入る（解説に2行目が残る）
 - 全角の大項目が半角へ寄り、num_code に ? が残らない
 - cleanStyle が \\75rl( / image-set( / position:fixed を落とし、色や太さは残す
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    import io
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


# ---- 静的：実装が入っていること ----
st = read("storage.js")
p1 = read(sorted([f for f in os.listdir(APP) if "main_part1_V" in f])[-1])
ok("splitTsvRecords（引用符内の改行で切らない）がある", "function splitTsvRecords" in st)
ok("taxKey（全角→半角の寄せ）を分類4列に当てている", st.count("taxKey(csvUnquote(") >= 4)
ok("STYLE_BAD が バックスラッシュ／image-set／position:fixed を落とす",
   "image-set" in p1 and "position\\s*:\\s*(fixed|sticky)" in p1 and "/\\\\|url" in p1)

# ---- 実行時 ----
QTEXT = "【batchCG】引用符セルの問題"
ROW = "\t".join([
    "必修", "目標Ⅰ", "S",
    "１. 健康の定義と理解",            # 全角の1（表記ゆれ）
    "B. 健康に関する指標", "a. 総人口", "single",
    QTEXT,
    json.dumps(["① あ", "② い", "③ う", "④ え"], ensure_ascii=False),
    "[1]",
    '"1行目の解説\n2行目の解説（""引用""つき）"',    # 引用符で包まれた改行入りセル
    json.dumps([["#人口動態統計"]] * 4, ensure_ascii=False),
    "",
])

with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(APP_URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1500)

    rep = pg.evaluate("""async (row) => {
      const r = await window.Storage.importText(row);
      const qs = await window.Storage.getAllQuestions();
      const q = qs.filter(x => String(x.stem || '').indexOf('【batchCG】') >= 0)[0] || null;
      return { imported: r.imported, updated: r.updated, skipped: r.skipped, tax_bad: r.tax_bad,
               q: q ? { major: q.major, num_code: q.num_code, expl: q.overall_explanation || '' } : null };
    }""", ROW)
    ok("引用符で包まれた改行入りセルを含む行が、1問として入る（黙って消えない）",
       rep["imported"] == 1 and rep["skipped"] == 0 and rep["q"] is not None,
       json.dumps(rep, ensure_ascii=False)[:300])
    ok("解説に2行目が残っている", rep["q"] and "2行目" in rep["q"]["expl"], rep["q"] and rep["q"]["expl"][:80])
    ok("全角の大項目が半角へ寄る", rep["q"] and rep["q"]["major"] == "1. 健康の定義と理解",
       rep["q"] and rep["q"]["major"])
    ok("num_code に ? が残らない（出題基準に当たる）",
       rep["q"] and rep["q"]["num_code"] and "?" not in str(rep["q"]["num_code"]) and rep["tax_bad"] == 0,
       json.dumps({"num_code": rep["q"] and rep["q"]["num_code"], "tax_bad": rep["tax_bad"]}, ensure_ascii=False))

    san = pg.evaluate("""() => {
      const f = window.Main.sanitizeExplanationHtml;
      return {
        esc:  f('<span style="color:red;background:\\\\75rl(http://evil.test/x)">a</span>'),
        iset: f('<div style="background-image:image-set(\\'http://evil.test/x\\' 1x)">b</div>'),
        fix:  f('<p style="position:fixed;top:0;font-weight:bold">c</p>'),
        keep: f('<b style="color:#c00;font-weight:800">d</b>')
      }; }""")
    ok("CSSエスケープの url（\\75rl( ）を落とし、色は残す",
       "75rl" not in san["esc"] and "url(" not in san["esc"].lower() and "color:red" in san["esc"],
       san["esc"])
    ok("image-set( を落とす", "image-set" not in san["iset"] and "evil.test" not in san["iset"], san["iset"])
    ok("position:fixed を落とし、太さは残す", "fixed" not in san["fix"] and "font-weight" in san["fix"], san["fix"])
    ok("無害な色・太さはそのまま", "color:#c00" in san["keep"] and "font-weight:800" in san["keep"], san["keep"])
    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + str(detail)) if (detail and not good_) else ""))
print("\n%d/%d  batchCG" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
