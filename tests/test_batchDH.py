#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDH：★の段階色（V2.40）。1金→2橙→3赤→4紫→5青。4種のボタン全対象。"""
import io, os, sys, re
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
css = io.open(os.path.join(APP, "styles.css"), encoding="utf-8").read()
for lv in range(1, 6):
    blocks = re.findall(r'\[data-star-level="%d"\]' % lv, css)
    ok("段階%dの色指定が4種のボタンに効く" % lv, len(blocks) >= 4, str(len(blocks)))
colors = re.findall(r'data-star-level="(\d)"\]\{ color:(#[0-9A-Fa-f]{6})', css)
uniq = {c for _, c in colors}
ok("5段階で5色が全て異なる", len(uniq) == 5, str(uniq))
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDH" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
