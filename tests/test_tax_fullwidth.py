# -*- coding: utf-8 -*-
"""test_tax_fullwidth.py — V2.52 取り込みが分類名の全角記号を壊さない

実測（配布JSON 176問）：単元「在宅看護論／地域・在宅看護論」が
取り込み後に「在宅看護論/地域・在宅看護論」へ変わり、
同梱453問と別の単元として3階層ツリーに生えていた（21問）。
数字・英字の表記ゆれ吸収（１.→1.）は残したまま、
マスタが使う記号だけ保つ。
"""
import json, os, re, re, subprocess, sys

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("taxKeyに除外リストがある", "TAX_KEEP_WIDE" in st)
ok("除外は（）＜＞／～の6文字", "'（）＜＞／～'" in st)

# マスタが使う全角記号を実際に数える（増えたら気づけるように）
NODE_M = ("global.window={};global.self=global;"
          "eval(require('fs').readFileSync('questions.js','utf8'));"
          "const M=global.window.TAXONOMY_MASTER;const s=new Set();"
          "M.forEach(r=>r.forEach(c=>{for(const ch of String(c)){"
          "const cp=ch.codePointAt(0);if(cp>=0xFF01&&cp<=0xFF5E)s.add(ch);}}));"
          "process.stdout.write(JSON.stringify([...s]));")
r = subprocess.run(["node", "-e", NODE_M], capture_output=True, text=True, cwd=base)
wide = json.loads(r.stdout or "[]")
ok("マスタの全角記号が除外リストに全部入っている",
   all(c in "（）＜＞／～" for c in wide), json.dumps(wide, ensure_ascii=False))

# taxKey の挙動そのもの
NODE_T = ("""
var TAX_KEEP_WIDE = '（）＜＞／～';
function taxKey(s) {
  return String(s == null ? '' : s)
    .replace(/[\uFF01-\uFF5E]/g, function (c) {
      if (TAX_KEEP_WIDE.indexOf(c) >= 0) { return c; }
      return String.fromCharCode(c.charCodeAt(0) - 0xFEE0);
    })
    .replace(/\u3000/g, ' ').replace(/\s+/g, ' ').trim();
}
process.stdout.write(JSON.stringify({
  slash: taxKey('在宅看護論／地域・在宅看護論'),
  num:   taxKey('１. 健康の定義と理解'),
  alpha: taxKey('Ａ. 健康の定義'),
  paren: taxKey('看護師（准看護師）'),
  tilde: taxKey('０～６歳'),
  space: taxKey('  余白　を  つめる ')
}));""")
r = subprocess.run(["node", "-e", NODE_T], capture_output=True, text=True)
d = json.loads(r.stdout or "{}")
ok("全角／が保たれる（マスタと一致する）",
   d.get("slash") == "在宅看護論／地域・在宅看護論", json.dumps(d, ensure_ascii=False))
ok("全角数字は半角へ寄せる（従来どおり）", d.get("num") == "1. 健康の定義と理解", str(d.get("num")))
ok("全角英字は半角へ寄せる（従来どおり）", d.get("alpha") == "A. 健康の定義", str(d.get("alpha")))
ok("全角括弧は保たれる", d.get("paren") == "看護師（准看護師）", str(d.get("paren")))
ok("全角～は保たれ、数字だけ半角になる", d.get("tilde") == "0～6歳", str(d.get("tilde")))
ok("空白の詰めは従来どおり", d.get("space") == "余白 を つめる", repr(d.get("space")))


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
print("\n%d/%d  tax_fullwidth" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
