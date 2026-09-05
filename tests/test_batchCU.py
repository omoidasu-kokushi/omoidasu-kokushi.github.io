#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCU：文言2点（V2.26）— ポモドーロ「集中時間」／解説「ボタンを押したら出す」"""
import io, os, sys, glob
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
p1 = sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1]
js1 = io.open(p1, encoding="utf-8").read()
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
ok("ポモドーロは「集中時間」", "集中時間：残り" in js1 and "集中中：残り" not in js1)
ok("解説設定は「ボタンを押したら出す」", "ボタンを押したら出す" in html)
ok("旧「ボタンで出す」が残っていない", ">ボタンで出す<" not in html)
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCU" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
