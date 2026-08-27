#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCB：何個選ばせるかは、正解の数から決める（V2.03）

【何が起きていたか】
`select_count` は正解数の**写し**（非正規化）で、`question_type` も同じく写し。
写しが古いまま残ると、

  「2つ選べ」と書いてあるのに `select_count` が 1 →
  2つ選ぶと確定が押せず、ボタンに **「-1つ選んでください」** と負の数が出る

という、先へ進めない詰みが起きる（実機で発生）。

取り込みの入口では `crossCheckJsonQuestion` が弾いている（V1.45）。
**ところが、すでにDBへ入っているものは誰も見ていなかった。**
検査を入口にだけ置くと、**入口ができる前に入ったものが永久に残る。**

【直し方】
**写しではなく本体を見る。** 正解の数は `atoms[].is_correct` が唯一の真実で、
それはこの画面に必ず読み込まれている。`select_count` は参照しない。
正解が0の壊れたデータでも、最低1つは選べるようにして詰ませない。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


html = read("index.html")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
j1 = read(p1)

ok("正解数から決める関数がある", "function needCount(" in j1 and "function isMultiPick(" in j1)
# コメント中の言及は残る。**コードとして読んでいないこと**を見る。
_code = "\n".join(l for l in j1.split("\n")
                  if "*" not in l.strip()[:2] and "/*" not in l)
ok("**select_count をもう読んでいない**",
   "q.select_count" not in _code and "select_count ||" not in _code)
ok("**question_type で選択の仕方を決めていない**",
   "q.question_type === 'multiple'" not in j1)
ok("なぜ写しを信じないか書いてある", "写しではなく本体を見る" in j1)
ok("入口だけの検査では足りないと書いてある", "入口ができる前に入ったものが永久に残ります" in j1)
ok("**負の数を出さないと書いてある**", "負の数を出さない" in j1)
# V2.04 で HTML を削ったとき、閉じ <div> を1つ多く消して**16スイートが落ちた**。
# 目に見えないので、構造そのものを数える。
_body = re.sub(r"<!--.*?-->", "", html, flags=re.S)
ok("**index.html の <div> が開閉ぴったり**",
   len(re.findall(r"<div\b", _body)) == len(re.findall(r"</div>", _body)),
   "%d / %d" % (len(re.findall(r"<div\b", _body)), len(re.findall(r"</div>", _body))))
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", html) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.set_default_timeout(120000)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(1400)

    n = pg.evaluate("""() => {
      const M = window.Main;
      const a = k => Array.from({length:5}, (_, i) => ({ is_correct: i < k }));
      return {
        none: M.needCount(a(0)), one: M.needCount(a(1)),
        two: M.needCount(a(2)), three: M.needCount(a(3)),
        empty: M.needCount([]), nul: M.needCount(null),
        m1: M.isMultiPick(a(1)), m2: M.isMultiPick(a(2))
      };
    }""")
    ok("正解2つなら2、3つなら3", n["two"] == 2 and n["three"] == 3, json.dumps(n))
    ok("正解1つなら1", n["one"] == 1, json.dumps(n))
    ok("**正解0の壊れたデータでも1（詰ませない）**",
       n["none"] == 1 and n["empty"] == 1 and n["nul"] == 1, json.dumps(n))
    ok("2つ以上で複数選択になる", n["m1"] is False and n["m2"] is True, json.dumps(n))

    # --- 実機で起きた形をそのまま再現する ---
    #   question_type:'multiple' / select_count:1 / でも正解は2つ
    #   → 旧実装は need=1 になり、2つ選ぶと「-1つ選んでください」で詰んだ
    r = pg.evaluate("""async () => {
      const M = window.Main;
      const until = async (f, ms) => { const t = Date.now();
        while (!f() && Date.now() - t < (ms || 8000)) await new Promise(r => setTimeout(r, 50)); };
      await M.startSession({ mode:'random', count:3 });
      await until(() => { const c = document.querySelector('#choice-list .choice-card');
        return c && getComputedStyle(c).pointerEvents !== 'none'; });

      const cur = M.state.current;
      /* 壊れた写しを、実機で起きたとおりに作る */
      cur.question.question_type = 'multiple';
      cur.question.select_count = 1;
      cur.atoms.forEach((a, i) => { a.is_correct = (i < 2); });
      cur.selected = [];
      M.renderChoices ? null : null;
      /* 画面を作り直す（案内文もここで決まる） */
      M.startQuestionRender ? null : null;
      /* 選び直して、確定ボタンの文言を見る */
      const cards = [...document.querySelectorAll('#choice-list .choice-card')];
      const nums = cards.map(c => parseInt(c.getAttribute('data-num'), 10));
      const btn = document.getElementById('btn-confirm');
      const out = { steps: [] };
      for (let i = 0; i < 3; i++) {
        (cards[i].querySelector('.choice-body') || cards[i]).click();
        await new Promise(r => setTimeout(r, 80));
        out.steps.push({ picked: cur.selected.length,
                         label: btn.textContent, disabled: btn.disabled });
      }
      out.need = M.needCount(cur.atoms);
      return out;
    }""")
    ok("**正解が2つなら、写しが1でも need は2**", r["need"] == 2, json.dumps(r, ensure_ascii=False))
    ok("**2つ選んだら確定が押せる（詰まない）**",
       any(s["picked"] == 2 and s["disabled"] is False for s in r["steps"]),
       json.dumps(r["steps"], ensure_ascii=False))
    ok("**どの段でも負の数が出ない**",
       all(not s["label"].startswith("-") and "-" not in s["label"] for s in r["steps"]),
       json.dumps(r["steps"], ensure_ascii=False))
    ok("3つ選んだら「多いです」と出る（押せないまま放置しない）",
       any(s["picked"] == 3 and "多いです" in s["label"] for s in r["steps"]),
       json.dumps(r["steps"], ensure_ascii=False))

    # --- ふつうの1つ選ぶ問題は今までどおり ---
    s1 = pg.evaluate("""async () => {
      const M = window.Main;
      const until = async (f, ms) => { const t = Date.now();
        while (!f() && Date.now() - t < (ms || 8000)) await new Promise(r => setTimeout(r, 50)); };
      await M.startSession({ mode:'random', count:3 });
      await until(() => { const c = document.querySelector('#choice-list .choice-card');
        return c && getComputedStyle(c).pointerEvents !== 'none'; });
      const cur = M.state.current;
      cur.atoms.forEach((a, i) => { a.is_correct = (i === 0); });
      cur.selected = [];
      const cards = [...document.querySelectorAll('#choice-list .choice-card')];
      const btn = document.getElementById('btn-confirm');
      (cards[0].querySelector('.choice-body') || cards[0]).click();
      await new Promise(r => setTimeout(r, 80));
      const first = { n: cur.selected.length, dis: btn.disabled, label: btn.textContent };
      /* 別の肢を押したら**入れ替わる**（増えない） */
      (cards[1].querySelector('.choice-body') || cards[1]).click();
      await new Promise(r => setTimeout(r, 80));
      const second = { n: cur.selected.length, dis: btn.disabled };
      return { first:first, second:second, inst: document.getElementById('q-instruction').textContent };
    }""")
    ok("**1つ選ぶ問題は1つで確定できる**",
       s1["first"]["n"] == 1 and s1["first"]["dis"] is False,
       json.dumps(s1, ensure_ascii=False))
    ok("**別の肢を押したら入れ替わる（増えない）**",
       s1["second"]["n"] == 1, json.dumps(s1, ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCB" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
