#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチAU：学習レポート（V1.70）＆ 白紙印刷バグの再発防止

V1.70 で見つけた重大バグ：#print-sheet は index.html 上 #modal-layer の中に
あり、印刷CSSはレイヤーごと display:none で消す（2箇所とも）。そのため
間違いノート印刷は V1.51 以来【実機で必ず白紙】だった。
修正は「組み立て時に body 直下へ移す」。ここではその再発と、
学習レポートの内容（実測値のみ・予測値なし）を固定する。
"""
import io, json, os, re, sys

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

import glob as _g
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
js = read(p2)
css = read("styles.css")
idx = read("index.html")

# ---------------------------------------------------------------- 静的検査
ok("part2 に buildReportSheet がある", "function buildReportSheet(" in js)
ok("part2 に runPrintReport がある", "function runPrintReport(" in js)
ok("設定に［学習レポートを書き出す］の行がある",
   'id="btn-report-print"' in idx and "学習レポートを書き出す" in idx)
ok("白紙バグ修正：紙面を body 直下へ移す処理が両ビルダーにある",
   js.count("sheet.parentElement !== global.document.body") == 2,
   "count=%d" % js.count("sheet.parentElement !== global.document.body"))
ok("印刷CSSに .rp-table がある", ".rp-table" in css)
ok("レポートは A4 固定（@page を A4 で書き換える）", "'@page{ size:A4; margin:" in js)
# 「合格可能性」の類をレポートに載せない（コメントは除いた実コードで見る）
_body = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
ok("レポート出力コードに『合格可能性』が無い", "合格可能性" not in _body)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 794, "height": 1123}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1500)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(1600)

    # 解答が無いうちは書き出せない（0件で安全に止まる）
    r0 = pg.evaluate("window.Half2Impl.buildReportSheet().then(r => r.count)")
    ok("解答ゼロのときは 0 件で止まる（白紙のPDFを作らせない）", r0 == 0, str(r0))

    # 1問解く
    pg.click("#choice-list .choice-card:nth-child(2) .choice-body")
    pg.wait_for_timeout(200)
    pg.click("#btn-confirm")
    pg.wait_for_timeout(900)
    pg.click("#btn-next")
    pg.wait_for_timeout(1200)

    r = pg.evaluate("""async () => {
      const res = await window.Half2Impl.buildReportSheet();
      const s = document.getElementById('print-sheet');
      return { count: res.count,
               parent: s.parentElement.tagName,
               title: s.innerHTML.includes('学習レポート'),
               credit: s.innerHTML.includes('omoidasu-kokushi.github.io'),
               pct: s.innerHTML.includes('合格可能性'),
               dbl: s.innerHTML.includes('[['),
               tables: s.querySelectorAll('.rp-table').length,
               secs: s.querySelectorAll('.rp-sec').length };
    }""")
    ok("1問解けばレポートが組み上がる", r["count"] >= 1, str(r["count"]))
    ok("紙面は body 直下にある（白紙バグの核心）", r["parent"] == "BODY", r["parent"])
    ok("表題がある", r["title"])
    ok("出典表記（URL）がある", r["credit"])
    ok("『合格可能性』を載せていない（実測値のみ）", not r["pct"])
    ok("番号コードの二重括弧が無い", not r["dbl"])
    ok("表が2枚以上ある（学習量＋単元別）", r["tables"] >= 2, str(r["tables"]))
    ok("節見出しが2つ以上ある", r["secs"] >= 2, str(r["secs"]))

    # 印刷メディアで実寸が出る（display:none のままなら height 0 ＝ 白紙）
    pg.emulate_media(media="print")
    pg.wait_for_timeout(300)
    h = pg.evaluate("() => Math.round(document.getElementById('print-sheet').getBoundingClientRect().height)")
    ok("印刷メディアで紙面に実寸がある（レポート）", h > 300, "h=%d" % h)

    # 間違いノート側も同じ修正が効いている
    pg.emulate_media(media="screen")
    pg.wait_for_timeout(200)
    rn = pg.evaluate("""async () => {
      const res = await window.Half2Impl.buildPrintSheet(
        { kind: 'both', paper: 'A4', cols: '1', explain: 'all' });
      const s = document.getElementById('print-sheet');
      return { count: res.count, parent: s.parentElement.tagName,
               items: s.querySelectorAll('.pn-item').length };
    }""")
    ok("間違いノートも組み上がる", rn["count"] >= 1, str(rn["count"]))
    ok("間違いノートの紙面も body 直下", rn["parent"] == "BODY", rn["parent"])
    pg.emulate_media(media="print")
    pg.wait_for_timeout(300)
    h2 = pg.evaluate("() => Math.round(document.getElementById('print-sheet').getBoundingClientRect().height)")
    ok("印刷メディアで紙面に実寸がある（間違いノート）", h2 > 200, "h=%d" % h2)

    ok("実行中エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAU" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
