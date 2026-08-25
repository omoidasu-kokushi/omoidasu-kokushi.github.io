#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""印刷物に載せるQRコードの行列を生成する（V1.75）

なぜ実行時に作らないか：
  ・URLは固定（アプリ自身のURL）なので、毎回計算する意味がない
  ・QRの符号化器を積むと6〜8KBのコードが増える。オフライン要件のために
    外部CDNは使えないので、積むなら同梱するしかない
  ・行列は29×29＝約900バイト。**定数のほうが小さく、壊れる余地も無い**

URLを変えたときは、このスクリプトを実行して part2 の QR_MATRIX を差し替える。

    pip install segno --break-system-packages
    python3 tools/make_qr.py
"""
import sys

URL = "https://omoidasu-kokushi.github.io/"

try:
    import segno
except ImportError:
    print("segno が要ります： pip install segno --break-system-packages", file=sys.stderr)
    raise SystemExit(1)

q = segno.make(URL, error="m")
rows = ["".join("1" if c else "0" for c in row) for row in q.matrix]

print("/* --- 印刷用QR（V1.75・tools/make_qr.py で生成） ---")
print("   中身: " + URL)
print("   版" + str(q.version) + "・誤り訂正" + str(q.error).upper() +
      "・" + str(len(rows)) + "×" + str(len(rows[0])) + "モジュール")
print("   URLを変えたら make_qr.py を実行して差し替えること。 */")
print("var QR_URL = '" + URL + "';")
print("var QR_MATRIX = [")
for i, r in enumerate(rows):
    print("  '" + r + "'" + ("," if i < len(rows) - 1 else ""))
print("];")
