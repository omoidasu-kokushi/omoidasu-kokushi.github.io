# -*- coding: utf-8 -*-
"""test_tax_slash.py — V2.51 分類の突合で全角／と半角/を同じ扱いにする

実測：配布JSON 176問のうち21問が、単元名のスラッシュが半角というだけで
「出題基準に無い分類」と数えられていた。3階層ツリーが単元から割れる。
"""
import os, re, subprocess, sys, json

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("normalizeTaxKeyに全角／の正規化がある", "replace(/／/g, '/')" in st)
ok("既存の括弧の正規化を消していない", "[（）]" in st)
ok("既存の不等号の正規化を消していない", "[＜＞]" in st)
ok("中黒（・）は触っていない（意味のある区切り）", "replace(/・/g" not in st)
ok("『無い分類は警告する』機能は残っている", "tax_bad" in st and "tax_examples" in st)

# 実際に storage.js の関数と同じ規則で突合する
NODE = """
const norm = v => String(v == null ? '' : v)
  .replace(/[（）]/g, m => m === '（' ? '(' : ')')
  .replace(/[＜＞]/g, m => m === '＜' ? '<' : '>')
  .replace(/／/g, '/')
  .replace(/[\\s\\u3000]+/g, ' ').trim();
const a = norm('在宅看護論／地域・在宅看護論');
const b = norm('在宅看護論/地域・在宅看護論');
const c = norm('地域・在宅看護論');
process.stdout.write(JSON.stringify({same: a === b, keepNakaguro: c.indexOf('・') >= 0}));
"""
r = subprocess.run(["node", "-e", NODE], capture_output=True, text=True)
d = json.loads(r.stdout or "{}")
ok("全角／と半角/が同じキーになる", d.get("same") is True, r.stdout + r.stderr)
ok("中黒は残る（別の分類を同じにしない）", d.get("keepNakaguro") is True, r.stdout)

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
print("\n%d/%d  tax_slash" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
