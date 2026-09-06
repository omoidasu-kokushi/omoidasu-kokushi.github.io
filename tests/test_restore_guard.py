# -*- coding: utf-8 -*-
"""test_restore_guard.py — V2.49 復元ボタンの入口違いガード

【何が起きていたか】
  配布用の取り込みJSON（{"questions":[...]}）を「バックアップから復元する」で
  開くと「問題0問／選択肢0件」と表示され、そのまま「入れ替える」を押すと
  学習記録が全部消える状態だった（2026-09-06 利用者の実操作で発覚）。
  復元は replace（全消し→書き戻し）なので、取り込み形式と0問は入口で止める。
"""
import os, re, sys

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()

m = re.search(r"function runRestore\(\)[\s\S]*?readAsText", p2)
body = m.group(0) if m else ""
ok("runRestoreが見つかる", bool(m))
ok("取り込み形式（questions配列）を復元で開くと案内して止める",
   "Array.isArray(payload.questions)" in body and "一括インポート用" in body)
ok("案内はreplace実行前にreturnする",
   body.find("一括インポート用") < body.find("confirmAction"))
ok("0問＋0件のときは入れ替えを中止する",
   "n === 0 && na === 0" in body and "入れ替えを中止" in body)
ok("バックアップ形式（stores入り）はガードを素通りする",
   "!payload.stores &&" in body)
ok("CACHE_NAMEがv2.49.0", "const CACHE_NAME = 'v2.49.0'" in sw)
ok("index.htmlの?v=が2.49に揃っている",
   "?v=2.49" in ix and "?v=2.48" not in ix)
ok("build-stampがV2.49", "_V2.49" in ix and "_V2.48" not in ix)

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  restore_guard" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
