#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBP：評価の回数表示（V1.91）

【なぜ要るか】
「普通」は 初見1h → 1d → **以降『簡単』を押すまで1週間固定ループ**（§4-4）。
押し続けているかぎり、その肢は永久に卒業しない。ところが画面には
「いま何回目か」がどこにも出ていないので、**止まっていること自体が見えない。**

【何を出して、何を出さないか】
出すのは**数字だけ**。「◯回も押している」と煽らない。
自己評価は本人の観測で、外から上書きするものではない。

例外は1つだけ。**同じ評価が続いていて、しかもその間ずっと正解している**とき。
これは「解けているのに自分を低く見積もっている」という、記録から読める事実。
逆に**間違えながら「普通」を押している人には何も言わない**。
そちらは正しい自己評価で、押し上げると予定のほうが嘘になる。

【飛び級させない】
声をかける先は1つ上だけ（難しい→普通／普通→易しい）。
易しい・マスターには何も言わない。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


sc = read("scheduler.js")
css = read("styles.css")
p1 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
j1 = read(p1)
html = read("index.html")

ok("履歴の計算がある", "function evalHistoryFromLogs(" in sc)
ok("声かけの判定がある", "function evalStepUpHint(" in sc)
ok("声をかける回数が定数になっている", "var EVAL_STREAK_HINT = 4;" in sc)
ok("煽らないと書いてある", "煽らない" in sc and "煽らない" in j1)
ok("枠を先に置く（あとで高さが動かない）", 'class="eval-count"' in j1 and "hidden></p>" in j1)
ok("描画を止めて待たない", "loadEvalHistory().catch(noop);" in j1)
ok("評価を押したら出し替える", "renderEvalCounts();          /* V1.91" in j1)
# 版そのものは batchAC / batchAH が横断で見ている。ここで数字を焼くと
# 次の改修で必ず赤くなり、**関係ない場所を直させる**ので焼かない。
ok("版番号・CACHE_NAME・?v= の3箇所が揃っている",
   read("index.html").count("?v=") >= 6
   and read("sw.js").count("?v=") >= 6
   and (lambda i, w: i and w and i == w)(
       (re.search(r"\?v=([0-9.]+)", read("index.html")) or [None, None])[1],
       (re.search(r"\?v=([0-9.]+)", read("sw.js")) or [None, None])[1]))
ok("色の意味が書いてある", ".eval-count.is-hint{" in css and "煽りではなく" in css)

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

    # --- 数え方そのもの ---
    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      const L = (ev, ok, t) => ({ eval:ev, is_correct:ok, answered_at:t });
      const mixed = K.evalHistoryFromLogs([
        L('hard', false, 1), L('normal', true, 2), L('normal', true, 3),
        L('easy', true, 4), L('normal', true, 5)
      ]);
      const stuck = K.evalHistoryFromLogs([
        L('normal', true, 1), L('normal', true, 2),
        L('normal', true, 3), L('normal', true, 4), L('normal', true, 5)
      ]);
      const wrong = K.evalHistoryFromLogs([
        L('normal', false, 1), L('normal', true, 2),
        L('normal', false, 3), L('normal', true, 4), L('normal', true, 5)
      ]);
      const hardRun = K.evalHistoryFromLogs([
        L('hard', true, 1), L('hard', true, 2), L('hard', true, 3), L('hard', true, 4)
      ]);
      const easyRun = K.evalHistoryFromLogs([
        L('easy', true, 1), L('easy', true, 2), L('easy', true, 3),
        L('easy', true, 4), L('easy', true, 5)
      ]);
      const noEval = K.evalHistoryFromLogs([{ answered_at:1 }, { answered_at:2 }]);
      /* 並び順がばらばらでも同じ答えになること */
      const shuffled = K.evalHistoryFromLogs([
        L('normal', true, 5), L('hard', false, 1), L('normal', true, 3),
        L('easy', true, 4), L('normal', true, 2)
      ]);
      return {
        mixed:mixed, stuck:stuck, wrong:wrong, hardRun:hardRun,
        easyRun:easyRun, noEval:noEval, shuffled:shuffled,
        hStuck: K.evalStepUpHint(stuck, 'normal'),
        hWrong: K.evalStepUpHint(wrong, 'normal'),
        hHard:  K.evalStepUpHint(hardRun, 'hard'),
        hEasy:  K.evalStepUpHint(easyRun, 'easy'),
        hOther: K.evalStepUpHint(stuck, 'hard'),
        hShort: K.evalStepUpHint(K.evalHistoryFromLogs([
          L('normal', true, 1), L('normal', true, 2), L('normal', true, 3)]), 'normal')
      };
    }""")
    ok("通算の回数を数えられる",
       r["mixed"]["counts"]["normal"] == 3 and r["mixed"]["counts"]["hard"] == 1,
       json.dumps(r["mixed"], ensure_ascii=False))
    ok("連続の回数は通算とは別に数える",
       r["mixed"]["streak"] == 1 and r["stuck"]["streak"] == 5,
       json.dumps({"mixed": r["mixed"], "stuck": r["stuck"]}, ensure_ascii=False))
    ok("並び順がばらばらでも同じ答えになる",
       r["shuffled"]["counts"]["normal"] == 3 and r["shuffled"]["streak"] == 1,
       json.dumps(r["shuffled"], ensure_ascii=False))
    ok("評価が入っていない記録は数えない",
       r["noEval"]["total"] == 0 and r["noEval"]["last_eval"] is None,
       json.dumps(r["noEval"], ensure_ascii=False))
    ok("**続けて正解している人には声をかける（普通→易しい）**",
       r["hStuck"] is not None and r["hStuck"]["to"] == "easy",
       json.dumps(r["hStuck"], ensure_ascii=False))
    ok("**間違えている人には声をかけない（自己評価が正しい）**",
       r["hWrong"] is None,
       json.dumps({"wrong": r["wrong"], "hint": r["hWrong"]}, ensure_ascii=False))
    ok("難しい→普通にも声をかける",
       r["hHard"] is not None and r["hHard"]["to"] == "normal",
       json.dumps(r["hHard"], ensure_ascii=False))
    ok("**易しい・マスターには声をかけない（飛び級させない）**",
       r["hEasy"] is None, json.dumps(r["hEasy"], ensure_ascii=False))
    ok("いま押している評価と続いている評価が違うなら黙る",
       r["hOther"] is None, json.dumps(r["hOther"], ensure_ascii=False))
    ok("3回では声をかけない（4回から）",
       r["hShort"] is None, json.dumps(r["hShort"], ensure_ascii=False))

    # --- 画面に出るか ---
    UNTIL = """const until = async (f, ms) => { const t = Date.now();
      while (!f() && Date.now() - t < (ms || 8000)) await new Promise(r => setTimeout(r, 50)); };
    """
    view = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage;
      """ + UNTIL + """
      await M.startSession({ mode:'random', count:3 });
      await until(() => { const c = document.querySelector('#choice-list .choice-card');
        return c && getComputedStyle(c).pointerEvents !== 'none'; });
      for (const c of document.querySelectorAll('#choice-list .choice-card')) {
        const b = document.getElementById('btn-confirm');
        if (b && !b.disabled) { break; }
        c.click();
      }
      await until(() => { const b = document.getElementById('btn-confirm'); return b && !b.disabled; });
      document.getElementById('btn-confirm').click();
      await until(() => document.getElementById('screen-quiz')
                          .getAttribute('data-phase') === 'review');
      const slots = document.querySelectorAll('#rv-choices .eval-count');
      /* 初見なので、まだ何も押していない。回数は「1回目」から始まる。 */
      await until(() => [...document.querySelectorAll('#rv-choices .eval-count')]
                        .some(e => !e.hidden), 6000);
      const first = [...slots].filter(e => !e.hidden).map(e => e.textContent);
      /* 「難しい」を押したら表示も難しいへ出し替わること */
      /* いま点いていない評価へ押し替える。初見・不正解なら全肢が［難しい］で
         始まる（§4-3）ので、決め打ちにすると空振りする。 */
      const cx = document.querySelector('#rv-choices .cx');
      const cur = cx && cx.querySelector('.eval-btn.is-active');
      const want = (cur && cur.getAttribute('data-eval') === 'easy') ? 'normal' : 'easy';
      const btn = cx && cx.querySelector('.eval-btn[data-eval="' + want + '"]');
      if (btn) { btn.click(); }
      await new Promise(r => setTimeout(r, 200));
      const after = [...document.querySelectorAll('#rv-choices .eval-count')]
                    .filter(e => !e.hidden).map(e => e.textContent);
      return { slots: slots.length, first: first, after: after };
    }""")
    ok("肢の数だけ枠がある", view["slots"] > 0, json.dumps(view, ensure_ascii=False))
    ok("**初見でも「1回目」から出る**",
       any("1回目" in t for t in view["first"]), json.dumps(view["first"], ensure_ascii=False))
    LABELS = ("難しい", "普通", "易しい", "マスター")
    ok("**押した評価の名前で出る**",
       view["first"] and all(t.split(" ")[0] in LABELS for t in view["first"]),
       json.dumps(view["first"], ensure_ascii=False))
    ok("**押し替えたら表示も入れ替わる**",
       view["after"] and view["after"][0] != view["first"][0]
       and view["after"][0].split(" ")[0] in LABELS,
       json.dumps({"first": view["first"], "after": view["after"]}, ensure_ascii=False))
    ok("初見では声をかけない（数字だけ）",
       not any("大丈夫かも" in t for t in view["first"]),
       json.dumps(view["first"], ensure_ascii=False))

    # --- 止まっている肢に、実際に声がかかるか（通しで確かめる） ---
    stuck = pg.evaluate("""async () => {
      const M = window.Main, S = window.Storage;
      const orig = S.getLogsByAtom;
      /* この肢は「普通」を5回押していて、その5回とも正解している、という履歴にする */
      S.getLogsByAtom = id => Promise.resolve([1,2,3,4,5].map(t => ({
        atom_id:id, eval:'normal', is_correct:true, answered_at:t })));
      /* 出るのは【いま点いている評価】の回数。履歴が「普通」なので、
         点灯も普通に揃えないと 0回のまま（＝仕様どおり）になる。 */
      document.querySelectorAll('#rv-choices .cx').forEach(cx => {
        const b = cx.querySelector('.eval-btn[data-eval="normal"]');
        if (b && !b.classList.contains('is-active')) { b.click(); }
      });
      M.renderReview();
      await new Promise(r => setTimeout(r, 600));
      const hint = [...document.querySelectorAll('#rv-choices .eval-count')]
        .filter(e => !e.hidden).map(e => ({ t:e.textContent,
                                            lit:e.classList.contains('is-hint') }));
      /* 間違えている履歴なら黙ること */
      S.getLogsByAtom = id => Promise.resolve([1,2,3,4,5].map(t => ({
        atom_id:id, eval:'normal', is_correct:(t % 2 === 0), answered_at:t })));
      document.querySelectorAll('#rv-choices .cx').forEach(cx => {
        const b = cx.querySelector('.eval-btn[data-eval="normal"]');
        if (b && !b.classList.contains('is-active')) { b.click(); }
      });
      M.renderReview();
      await new Promise(r => setTimeout(r, 600));
      const quiet = [...document.querySelectorAll('#rv-choices .eval-count')]
        .filter(e => !e.hidden).map(e => ({ t:e.textContent,
                                            lit:e.classList.contains('is-hint') }));
      S.getLogsByAtom = orig;
      return { hint:hint, quiet:quiet };
    }""")
    ok("**5回続けて正解している肢では「6回目」になる**",
       any("6回目" in x["t"] for x in stuck["hint"]),
       json.dumps(stuck["hint"], ensure_ascii=False))
    ok("**そのとき［易しい］を勧める一言が出る**",
       any("易しい" in x["t"] and "大丈夫かも" in x["t"] for x in stuck["hint"]),
       json.dumps(stuck["hint"], ensure_ascii=False))
    ok("**そのときだけ色が付く**",
       any(x["lit"] for x in stuck["hint"]), json.dumps(stuck["hint"], ensure_ascii=False))
    ok("**間違えている履歴なら回数だけで、何も勧めない**",
       stuck["quiet"] and all("大丈夫かも" not in x["t"] and not x["lit"] for x in stuck["quiet"]),
       json.dumps(stuck["quiet"], ensure_ascii=False))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBP" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
