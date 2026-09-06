#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチDG：ひとことメモ整理（V2.39）
t12（忘却曲線④）削除＝t08マスターと重複（利用者指示）。★5段階の新機能の話を
t36/t37として追加。件数の固定記載（全34件）をやめ、idの欠番は詰めない
（text_overridesのキーを揺らさない）。
"""
import io, os, sys, glob
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
p2 = sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1]
js = io.open(p2, encoding="utf-8").read()
ok("t12が消えている", "id:'t12'" not in js)
ok("削除理由がコメントで残る", "t08「評価ボタン：マスター」と内容が重複" in js)
ok("★5段階の話が追加", "id:'t36'" in js and "★1→★2→★3→★4→★5→解除" in js)
ok("段階絞り・名前の話も追加", "id:'t37'" in js and "★2だけ印刷" in js)
ok("件数の固定記載をやめた", "全34件あります" not in js)
ok("欠番を詰めていない（t11とt13は残る）", "id:'t11'" in js and "id:'t13'" in js)
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchDG" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
