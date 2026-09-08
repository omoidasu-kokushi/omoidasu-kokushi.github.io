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

# V2.89（2026-09-09）：同梱シードを自由作問453問の13列TSV →
# 過去問の必修249問の **JSON** へ入れ替えた（利用者裁定）。
# 取り出し方が変わったので、ここも字面の切り出しから JSON の読み取りへ直す。
# 主張そのものは1つも消していない。数字だけ、入れ替え後の実測に合わせる。
import subprocess
NODE = ("const fs=require('fs');global.window={};global.self=global;"
        "eval(fs.readFileSync(process.argv[1],'utf8'));"
        "process.stdout.write(global.window.SEED_QUESTIONS_TSV);")
out = subprocess.run(["node", "-e", NODE, os.path.join(APP, "questions.js")],
                     capture_output=True, text=True)
ok("同梱シードを取り出せる", out.returncode == 0, (out.stderr or "")[:200])
qs = json.loads(out.stdout)["questions"]

total = hits = bad = 0
themes = set()
for q in qs:
    flat = []
    for a_ in (q.get("atoms") or []):
        tg = a_.get("tags")
        if tg is not None and not isinstance(tg, list):
            bad += 1
            continue
        flat.extend(tg or [])
    total += len(flat)
    for t in flat:
        if t in master:
            hits += 1
            themes.add(t)

ok("タグマスタは103件", len(master) == 103, len(master))
ok("シードは249問（V2.89で必修249問へ入れ替え）", len(qs) == 249, len(qs))
ok("全問のタグが配列になっている", bad == 0, "壊れた問 %d" % bad)
rate = 100.0 * hits / max(total, 1)
# 旧シードは自由タグだらけで、V2.07 の追記でようやく50.6%だった。
# 過去問シードは作問の段階でマスタから選ばせているので100%になる。
# 下限は上げるが、上げすぎない（将来の差し替えで意味のある幅を残す）。
ok("マスタ内タグ率が90%以上（過去問シードの実測100%）", rate >= 90.0, "%.1f%%" % rate)
ok("球のあるテーマが40以上（V2.07実測48を固定）", len(themes) >= 40, len(themes))
# 旧シードの「自由タグも残っている（追記方式であって置換ではない）」は、
# 追記の仕組みを見る主張だった。過去問シードには自由タグが無い（0件が正しい）。
# 主張は消さず、**退避した旧シードに対して**そのまま続ける。
OLDP = os.path.join(APP, "sample", "20260909_旧同梱シード_自由作問453問_V1.00.txt")
ok("旧シードを消さずに退避してある", os.path.exists(OLDP), OLDP)
old_rows = [r.split("\t") for r in
            io.open(OLDP, encoding="utf-8").read().split("\n") if r.strip()]
ok("旧シードは453問のまま", len(old_rows) == 453, len(old_rows))
o_total = o_hits = 0
for c in old_rows:
    try:
        t2 = json.loads(c[11])
        flat = [t for a_ in t2 for t in (a_ if isinstance(a_, list) else [a_])]
    except Exception:
        flat = []
    o_total += len(flat)
    o_hits += sum(1 for t in flat if t in master)
ok("旧シードでは自由タグも残っている（追記方式であって置換ではない）",
   (o_total - o_hits) >= 1000, "自由タグ %d" % (o_total - o_hits))
ok("旧シードのマスタ内タグ率は V2.07 実測どおり40%以上",
   100.0 * o_hits / max(o_total, 1) >= 40.0,
   "%.1f%%" % (100.0 * o_hits / max(o_total, 1)))

fails = [x for x in R if not x[0]]
for f, n, d in R:
    print(("  ok  " if f else "  NG  ") + n +
          (("   << " + str(d)) if (d != "" and not f) else ""))
print("%d/%d  batchCE" % (len(R) - len(fails), len(R)))
sys.exit(1 if fails else 0)
