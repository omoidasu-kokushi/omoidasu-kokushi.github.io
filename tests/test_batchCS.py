#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCS：必修コメントは「点」で語る（V2.24）

「合格ラインまで −3」は数式の顔をしていて意味が取りにくい（利用者要望）。
「37/50点 相当（合格ラインまであと3点）」／到達時「（合格ラインです）」へ。
"""
import io, os, sys, glob
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
p2 = sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1]
js = io.open(p2, encoding="utf-8").read()
ok("点の単位が付く", "/50点 相当" in js)
ok("未達は「あと○点」", "合格ラインまであと' + d.gap + '点" in js)
ok("到達は「合格ラインです」", "（合格ラインです）" in js)
ok("旧文言が残っていない", "合格ラインまで −" not in js and "合格ラインに乗っています" not in js)
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCS" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
