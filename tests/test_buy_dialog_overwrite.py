# -*- coding: utf-8 -*-
"""test_buy_dialog_overwrite.py — V2.50 買い切りの案内を別の案内で上書きしない

無料枠（200問）を使い切った状態でランダムを押すと、
買い切りの案内が一瞬で消え、「初見の問題は残っていません」に置き換わっていた。
利用者からは「ポップアップが一瞬出て消える」ようにしか見えず、
何が起きたのか分からない。
"""
import os, re, re, sys

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

# V2.71 で startRandom は「開始前の確認」と「実際に始める処理」に割れた。
# 買い切りの案内を守る番人は startRandomNow の側にいる。
# 観点は変えず、見る場所だけ移す（片方が無くなったら気づけるよう両方見る）。
m0 = re.search(r"function startRandom\([\s\S]*?\n  \}", p2)
m = re.search(r"function startRandomNow\([\s\S]*?\n  \}", p2)
body = m.group(0) if m else ""
ok("startRandomが見つかる", bool(m0))
ok("startRandomNowが見つかる（V2.71で分かれた）", bool(m))
ok("入口から startRandomNow へ渡している", "startRandomNow(scope, count)" in (m0.group(0) if m0 else ""))
ok("買い切りの案内が開いていたら初見なしを開かない",
   "modal-buy" in body and "buyCard.hidden" in body)
ok("上書き防止はopenModalより前に効く",
   body.find("buyCard") < body.find("#modal-no-new"))
ok("初見が尽きた場合の案内は残っている（機能を消していない）",
   "#modal-no-new" in body)

# --- 版は決め打ちしない（版は毎回上がる）。互いに一致しているかだけ見る ---
def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
sw_cache = _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'")
sw_q     = _vers(sw, r"\?v=([0-9.]+)")
ix_q     = _vers(ix, r"\?v=([0-9.]+)")
ix_stamp = _vers(ix, r"Omoidasu_V([0-9.]+)")   # ファイル名の _V1.38.js を拾わない
ok("index.htmlの?v=が1種類に揃っている", len(ix_q) == 1, str(ix_q))
ok("sw.jsの?v=が1種類に揃っている", len(sw_q) == 1, str(sw_q))
ok("indexとswの?v=が一致している", ix_q == sw_q, str(ix_q) + " vs " + str(sw_q))
ok("build-stampの版が?v=と一致している",
   len(ix_stamp) == 1 and ix_stamp[0] == ix_q[0], str(ix_stamp) + " vs " + str(ix_q))
ok("CACHE_NAMEが?v=と同じ系列（v<版>.0）",
   len(sw_cache) == 1 and sw_cache[0] == ix_q[0] + ".0",
   str(sw_cache) + " vs " + str(ix_q))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  buy_dialog_overwrite" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
