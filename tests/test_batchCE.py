#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V2.07 検証：同梱シードが103マスタのタグを十分に持っている（案A'の固定）

シードは74→103のマスタ拡張（V2.05）後も再タグ付けされず、
マスタ内1.5%・球のあるテーマ14/103だった
（claude/20260901_同梱シードのタグが103マスタと合わない_判断待ち_V1.01）。
V2.07 で中項目→対応表の既定タグを全肢へ追記した。この水準が
将来のシード差し替えで黙って崩れないよう、静的に固定する。
ブラウザ不要（questions.js の字面だけを見る）。
"""
import io
import json
import os
import re
import sys

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = io.open(os.path.join(APP, "questions.js"), encoding="utf-8").read()
R = []


def ok(n, c, d=""):
    R.append((bool(c), n, d))


master = set(re.findall(r'tag:\s*"(#[^"]+)"', src))
i = src.index('const SEED_QUESTIONS_TSV = [')
j = src.index('].join("\\n");', i)
rows = []
for ln in src[i:j].splitlines():
    m = re.match(r'^\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', ln)
    if m:
        rows.append(json.loads('"' + m.group(1) + '"').split("\t"))

total = hits = bad = 0
themes = set()
for c in rows:
    try:
        t2 = json.loads(c[11])
        flat = [t for a in t2 for t in (a if isinstance(a, list) else [a])]
    except Exception:
        bad += 1
        flat = []
    total += len(flat)
    for t in flat:
        if t in master:
            hits += 1
            themes.add(t)

ok("タグマスタは103件", len(master) == 103, len(master))
ok("シードは453問", len(rows) == 453, len(rows))
ok("全行のタグ列がJSONとして読める", bad == 0, "壊れた行 %d" % bad)
rate = 100.0 * hits / max(total, 1)
ok("マスタ内タグ率が40%以上（V2.07実測50.6%を固定）", rate >= 40.0, "%.1f%%" % rate)
ok("球のあるテーマが40以上（V2.07実測48を固定）", len(themes) >= 40, len(themes))
ok("自由タグも残っている（追記方式であって置換ではない）",
   (total - hits) >= 1000, "自由タグ %d" % (total - hits))

fails = [x for x in R if not x[0]]
for f, n, d in R:
    print(("  ok  " if f else "  NG  ") + n +
          (("   << " + str(d)) if (d != "" and not f) else ""))
print("%d/%d  batchCE" % (len(R) - len(fails), len(R)))
sys.exit(1 if fails else 0)
