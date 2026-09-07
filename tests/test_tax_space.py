# -*- coding: utf-8 -*-
"""test_tax_space.py — 番号の直後の空白で分類を取り違えない（V2.75）

【実測で見つけた不具合】
  1159問を検証して796問を結合し、取り込んだら tax_bad が1件出た。

    781件目：母性看護学 ＞ 3.女性のライフサイクル各期における看護
             ＞ B. 思春期・成熟期女性の健康課題      （第115回 午後問64）

  出題基準マスタは「3. 女性のライフサイクル各期における看護」で
  **「3.」の直後に半角スペースがある**。取り込んだ側には無い。
  **スペース1つの違いだけ**で「出題基準に無い分類」と数えられ、
  1問だけ落ちていた。他の791問は「3. 」の形なので気づきにくい。

【直し方と、やらなかったこと】
  番号の直後の空白は意味を持たないので寄せる。
  ただし**空白を全部消すことはしない**。分類名の中の空白には意味があり
  （「A. 人体の基本的な構造 and 正常な機能」のような語の区切り）、
  全部消すと別の分類どうしがぶつかりうる。
  寄せるのは **先頭の「番号＋ピリオド」の直後だけ**。

ここで固定するのは5つ。
  ① 「3.女性…」と「3. 女性…」を同じ分類として扱う
  ② 全角の「Ａ．」も同じに寄る（V2.09 の全角→半角と組み合わさる）
  ③ 番号の無い分類名（「必修」）は何も変わらない
  ④ 分類名の**途中**の空白は消さない（別の分類とぶつけない）
  ⑤ 出題基準に本当に無い分類は、これまでどおり数えて報告する
"""
import json, os, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
ok("番号直後の空白を寄せる一行がある",
   r"""replace(/^([0-9A-Za-z]{1,3})\.\s+/, '$1.')""" in st)
ok("なぜ全部消さないかが書いてある", "分類名の中の空白には意味がある" in st)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(1200)

    def imp(unit, major, medium, src):
        payload = json.dumps({"questions": [{
            "source": src, "pool": "main", "unit": unit, "major": major, "medium": medium,
            "sub_item": "a. テスト", "stem": "テストの問題文である。",
            "question_type": "single", "select_count": 1,
            "atoms": [{"text": "肢1", "statement": "肢1である。", "is_correct": True,
                       "explanation": "正しい。", "tags": []},
                      {"text": "肢2", "statement": "肢2である。", "is_correct": False,
                       "explanation": "誤り。", "tags": []}],
            "overall_explanation": "肢1が正しい。"
        }]}, ensure_ascii=False)
        return pg.evaluate("""async (t) => {
          const r = await window.Storage.importText(t);
          return { imported: r.imported, updated: r.updated, tax_bad: r.tax_bad,
                   examples: r.tax_examples || [] };
        }""", payload)

    MAJ_SP = "3. 女性のライフサイクル各期における看護"
    MAJ_NO = "3.女性のライフサイクル各期における看護"
    MED = "B. 思春期・成熟期女性の健康課題"

    a = imp("母性看護学", MAJ_SP, MED, "テスト_空白あり")
    ok("マスタと同じ「3. 女性…」は当然通る", a["tax_bad"] == 0, json.dumps(a, ensure_ascii=False))

    b = imp("母性看護学", MAJ_NO, MED, "テスト_空白なし")
    ok("「3.女性…」（空白なし）も同じ分類として通る（V2.75）",
       b["tax_bad"] == 0, json.dumps(b, ensure_ascii=False))

    c = imp("母性看護学", "３．女性のライフサイクル各期における看護", MED, "テスト_全角")
    ok("全角の「３．」も同じに寄る", c["tax_bad"] == 0, json.dumps(c, ensure_ascii=False))

    d = imp("必修", "1. 健康の定義と理解", "A. 健康の定義", "テスト_番号なし単元")
    ok("番号の無い単元名は何も変わらない", d["tax_bad"] == 0, json.dumps(d, ensure_ascii=False))

    e = imp("母性看護学", MAJ_SP, "Z. こんな中項目は無い", "テスト_本当に無い")
    ok("本当に無い分類は、これまでどおり数えて報告する",
       e["tax_bad"] == 1 and e["examples"], json.dumps(e, ensure_ascii=False))

    # ④ 途中の空白は消さない（3階層ツリーが二股に割れないことまで見る）
    tree = pg.evaluate("""async () => {
      const t = await window.Storage.buildTree();
      const names = t.map(u => u.unit || u.name || u.key || '');
      return { units: t.length, names: names,
               dup: names.length !== new Set(names).size };
    }""")
    ok("同じ単元が二股に割れていない", tree["dup"] is False, json.dumps(tree, ensure_ascii=False))

    mid = pg.evaluate("""() => {
      const f = window.Storage.__taxNormalizeForTest;
      return f ? f('A. 人体の基本的な構造 と 正常な機能') : null;
    }""")
    if mid is None:
        ok("分類名の途中の空白は残る（正規化の中身は storage.js の記述で担保）",
           "分類名の中の空白には意味がある" in st)
    else:
        ok("分類名の途中の空白は残る", " と " in mid, str(mid))

    ok("JSエラーが出ていない", not errs, " / ".join(errs[:3]))
    br.close()

import re
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()
def _v(t, p):
    return sorted(set(re.findall(p, t)))
ix_q = _v(ix, r"\?v=([0-9.]+)")
ok("index.htmlの?v=が1種類", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致", ix_q == _v(sw, r"\?v=([0-9.]+)"), str(ix_q))
ok("CACHE_NAMEが?v=と同じ系列", _v(sw, r"CACHE_NAME = 'v([0-9.]+)'") == [ix_q[0] + ".0"], str(ix_q))

bad = [x for x in R if not x[0]]
for good, name, d in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + d) if not good else ""))
print("\n%d/%d  tax_space" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
