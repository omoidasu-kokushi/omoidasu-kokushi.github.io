#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCZ：ポモドーロの［10分延長］を撤去（V2.31・利用者裁定）
「5分休憩・10分延長は逃げすぎ」→ 裁定：休憩ボタンだけ残す。
"""
import io, os, sys, glob
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
p1 = sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1]
js1 = io.open(p1, encoding="utf-8").read()
ok("延長ボタンが無い", 'id="pomo-extend"' not in html)
ok("休憩ボタンは残る", 'id="pomo-break"' in html)
ok("OFFボタンも残る", 'id="pomo-off"' in html)
ok("バインディングも外した", "on($('#pomo-extend')" not in js1)
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCZ" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
