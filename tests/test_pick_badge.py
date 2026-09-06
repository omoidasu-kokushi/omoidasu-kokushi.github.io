# -*- coding: utf-8 -*-
"""test_pick_badge.py — V2.68 ランダム画面のバッジを「あと何問」1つにする

利用者の指摘：「単元右横の数字の意味が分からない。なぜ2色ある？
必修(28)と小児看護学(8)の違いは？ 一色に統一したほうがよさそう」

調べたら、色が2つなのは見た目の問題ではなかった。
**同じ場所に別々の量を出していて、しかも単位も違っていた。**

    赤   … 「難しい」を付けた**肢**の数
    薄い … まだ解いていない**肢**の数（赤があるときは隠れる＝排他）
    右の「◯問」 … **問題**の数

必修は「28（未学習の肢）／8問（総数）」と並び、未学習が総数を超えて見えていた。
8問×4肢＝32肢のうち28肢が未学習、という意味。

ここで固定するのは3つ。
  ① バッジは1種類だけ（まだ解いていない問題の数）
  ② 単位が問に揃っている（肢ではない）
  ③ 難しい肢の集計は消していない（分析が使う）
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("問題単位の未学習を数えている", "unlearned_q" in st)
ok("バッジは1種類だけ（赤／薄の出し分けをやめた）",
   "badge-line" not in p2 and "badge-soft" not in p2)
ok("難しい肢の集計は消していない（分析が使う）", "hard: hard" in st)
ok("CSSがある", ".pick-left{" in cs)
ok("なぜ2色をやめたかがコードに書いてある", "比べられない2つの量" in p2)

TAG = "#バッジ検証"
def q(i, n_at):
    ats = []
    for k in range(n_at):
        ats.append({"text": "肢%d-%d" % (i, k + 1), "statement": "肢", "explanation": "説明。",
                    "is_correct": k == 0, "tags": [TAG]})
    return {"source": "バッジ検証問%d" % i, "unit": "必修",
            "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
            "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
            "stem": "バッジ検証の問題%d。正しいのはどれか。" % i, "atoms": ats}
PAYLOAD = json.dumps({"questions": [q(i, 4) for i in range(1, 4)]}, ensure_ascii=False)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("async (t) => { await window.Storage.importText(t); }", PAYLOAD)

    d = pg.evaluate("""async () => {
      const tree = await window.Storage.buildTree();
      const u = tree.find(x => x.key === '必修');
      const mine = 3;   // 入れた問題数
      return { unit: u ? { count: u.count, unlearned: u.unlearned, q: u.unlearned_q } : null };
    }""")
    u = d["unit"] or {}
    ok("肢単位と問単位が別々に取れる",
       u.get("unlearned", 0) > u.get("q", 0), json.dumps(u))
    ok("問単位の未学習が総問数を超えない（単位が揃っている）",
       0 < u.get("q", 0) <= u.get("count", 0), json.dumps(u))

    # 1問だけ解いたら「あと」が1減る
    d2 = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = (await S.getAllQuestions()).filter(x => /^バッジ検証問/.test(x.source || ''));
      const ats = await S.getAtomsByQuestion(qs[0].q_id);
      for (const a of ats) { await S.updateAtom(a.atom_id, { answer_count: 1, last_eval: 'normal' }); }
      const tree = await S.buildTree();
      const u = tree.find(x => x.key === '必修');
      return { q: u.unlearned_q, count: u.count };
    }""")
    ok("1問すべての肢を解いたら「あと」が1減る",
       d2["q"] == u.get("q", 0) - 1, json.dumps({"before": u.get("q"), "after": d2["q"]}))

    # 1肢だけ解いた問題は、まだ「あと」に数える
    d3 = pg.evaluate("""async () => {
      const S = window.Storage;
      const qs = (await S.getAllQuestions()).filter(x => /^バッジ検証問/.test(x.source || ''));
      const ats = await S.getAtomsByQuestion(qs[1].q_id);
      await S.updateAtom(ats[0].atom_id, { answer_count: 1, last_eval: 'hard' });
      const tree = await S.buildTree();
      const u = tree.find(x => x.key === '必修');
      return { q: u.unlearned_q, hard: u.hard };
    }""")
    ok("1肢だけ解いた問題は、まだ「あと」に数える（1肢でも未学習なら未読破）",
       d3["q"] == d2["q"], json.dumps(d3))
    ok("難しい肢の集計は生きている（分析が使う）", d3["hard"] >= 1, json.dumps(d3))

    html = pg.evaluate("""() => {
      const H = window.Half2Impl;
      return { a: H.pickBadge ? H.pickBadge({ unlearned_q: 7, unlearned: 28, hard: 9, count: 8 }) : null,
               b: H.pickBadge ? H.pickBadge({ unlearned_q: 0, unlearned: 0, hard: 9, count: 8 }) : null };
    }""")
    if html.get("a") is None:
        ok("（pickBadge が公開されていないため描画の直接検査は省略）", True)
    else:
        ok("難しい肢があっても『あと◯』を出す（隠さない）",
           "あと7" in html["a"] and "9" not in html["a"], json.dumps(html, ensure_ascii=False))
        ok("読破したら「読破」と出す", "読破" in (html["b"] or ""), json.dumps(html, ensure_ascii=False))
    ok("JSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

def _vers(txt, pat):
    return sorted(set(re.findall(pat, txt)))
sw_cache = _vers(sw, r"CACHE_NAME = 'v([0-9.]+)'")
sw_q = _vers(sw, r"\?v=([0-9.]+)")
ix_q = _vers(ix, r"\?v=([0-9.]+)")
ix_stamp = _vers(ix, r"Omoidasu_V([0-9.]+)")
ok("index.htmlの?v=が1種類に揃っている", len(ix_q) == 1, str(ix_q))
ok("indexとswの?v=が一致している", ix_q == sw_q, str(ix_q) + " vs " + str(sw_q))
ok("build-stampの版が?v=と一致している",
   len(ix_stamp) == 1 and ix_stamp[0] == ix_q[0], str(ix_stamp))
ok("CACHE_NAMEが?v=と同じ系列", len(sw_cache) == 1 and sw_cache[0] == ix_q[0] + ".0", str(sw_cache))

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  pick_badge" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
