#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCT：ライセンス入力欄に見える枠を・呼び名は「シリアル」（V2.25）

何が起きていたか：.lic-key が存在しないCSS変数（--text-main／--surface-1／
--border-1）を参照し、枠線・背景・文字色が全部無効＝「見えない入力欄」だった
（利用者報告「どこに貼ればいいか分からない」）。加えて「鍵」という呼び名が
分かりにくい（利用者要望）→ 利用者向け文言を「シリアル」へ統一。
license.js等の内部コメント・変数名は変えない（挙動不変）。
"""
import io, os, sys, glob, re
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
css = io.open(os.path.join(APP, "styles.css"), encoding="utf-8").read()
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
p2 = sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1]
js = io.open(p2, encoding="utf-8").read()
i = css.find(".lic-key{"); blk = css[i:css.find("}", i)]
defined = set(re.findall(r"--([\w-]+)\s*:", css))
used = set(re.findall(r"var\(--([\w-]+)", blk))
ok("入力欄が使う変数はすべて定義済み", used <= defined, str(used - defined))
ok("入力欄に見える枠（破線）がある", "dashed" in blk)
ok("フォーカスで枠が実線になる", ".lic-key:focus" in css)
ok("placeholderがシリアル", "ここにシリアルを貼り付け" in html)
ok("登録ボタンがシリアル", "シリアルを登録する" in html)
ok("画面の利用者向け文言に「鍵」が残っていない",
   "鍵を入れる" not in html and "鍵を貼り付け" not in html and "鍵を持っている" not in html)
ok("エラーメッセージもシリアル", "シリアルの形が違います" in js and "鍵の形が違います" not in js)
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCT" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
