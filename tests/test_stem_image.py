# -*- coding: utf-8 -*-
"""test_stem_image.py — 問題文に図がある問題の線画（V2.73）

【何を取りこぼしていたか】
  同梱していたのは
    ・別冊の線画（V2.65／4枚）
    ・**選択肢が**図の問題（V2.66・V2.67／12枚）
  だけだった。

  図が **問題文の側** にある問題（選択肢は ①②③④ の文字）は誰も拾っておらず、
  image_url が空のままだった。図が無いと「図の③はどれか」に答えようがない。
  **そもそも解けない問題**が配られようとしていた。

  数え方：res_finish の stem に「図に示す／図を示す／グラフに示す／表に示す／
  別に示す」が入っていて image_url が無い問題を全部出した。
  23問あり、6問は対応ずみ、**17問が未対応**。
  うち16問は線画・グラフ・表で使用可、1問（第111回午前問37）は写真で不可。

ここで固定するのは6つ。
  ① 16枚が images/stem に揃っている
  ② sw.js の OPTIONAL に16枚とも入っている（CORE ではない）
  ③ CORE に入れていない（1枚欠けてインストールが丸ごと失敗しないように）
  ④ 写真（第111回午前問37）は同梱していない
  ⑤ 画像アコーディオンの仕掛けは生きている（V2.65の機能を消していない）
  ⑥ 版・CACHE_NAME・?v= が揃っている
"""
import os, re, sys

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()

WANT = ["111_am11", "111_am18", "111_am77", "112_pm25", "112_pm39", "112_pm73",
        "113_am27", "113_am34", "113_am35", "113_pm77", "114_am30", "114_pm45",
        "114_pm55", "114_pm80", "115_pm28", "115_pm77"]

d = os.path.join(base, "images", "stem")
ok("images/stem がある", os.path.isdir(d))
have = sorted(f[:-4] for f in os.listdir(d)) if os.path.isdir(d) else []
ok("16枚そろっている", have == sorted(WANT), "%d枚 %s" % (len(have), have))

# 大きさ。線画なので1枚あたり数十KBに収まっているはず
if os.path.isdir(d):
    sizes = {f: os.path.getsize(os.path.join(d, f)) for f in os.listdir(d)}
    big = {k: v for k, v in sizes.items() if v > 120 * 1024}
    ok("1枚120KBを超えていない（線画なので太らない）", not big, str(big))
    ok("16枚あわせて600KB未満", sum(sizes.values()) < 600 * 1024,
       "%dKB" % (sum(sizes.values()) // 1024))

m = re.search(r"const OPTIONAL_ASSETS = \[([\s\S]*?)\];", sw)
opt = m.group(1) if m else ""
m2 = re.search(r"const CORE_ASSETS = \[([\s\S]*?)\];", sw)
core = m2.group(1) if m2 else ""
miss = [n for n in WANT if ("images/stem/%s.png" % n) not in opt]
ok("sw.js の OPTIONAL に16枚とも入っている", not miss, str(miss))
ok("CORE には入れていない（1枚欠けでインストールが死なないように）",
   "images/stem/" not in core)
ok("なぜOPTIONALかが書いてある", "問題文の側" in sw)

# 写真は同梱しない（裁定②）
ok("写真（第111回午前問37）は同梱していない",
   "111_am37" not in sw and "111_am37" not in "".join(have))

# V2.65 の機能を消していない
ok("画像アコーディオンの仕掛けは残っている",
   ("image_url" in p1) and ('id="q-image"' in ix or "q-image" in p1))
ok("別冊の線画も残っている（V2.65を消していない）",
   "images/bessatsu/111_am81.png" in sw)
ok("選択肢の図も残っている（V2.66/V2.67を消していない）",
   "images/sentakushi/112_am57.png" in sw and "images/sentakushi/114_am41.png" in sw)

def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
ix_q = _vers(ix, r"\?v=([0-9.]+)")
ok("index.htmlの?v=が1種類", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致", ix_q == _vers(sw, r"\?v=([0-9.]+)"), str(ix_q))
ok("build-stampの版が?v=と一致", _vers(ix, r"Omoidasu_V([0-9.]+)") == ix_q, str(ix_q))
ok("CACHE_NAMEが?v=と同じ系列", _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'") == [ix_q[0] + ".0"], str(ix_q))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  stem_image" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
