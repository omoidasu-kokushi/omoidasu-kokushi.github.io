# -*- coding: utf-8 -*-
"""test_knock_count.py — V2.57 弱点ノックを分数から問題数へ

利用者の指摘：「弱点ノックを早めに触ってしまうと同じ問題ばかり出てしまったりする。
分数指定だと早く解いたら問題が枯渇する可能性があるから、
分数指定でなく問題数指定にしよう。10問、30問とか。」

真因はコードにそのまま書いてあった。
    while (pool.length < st.knock.minutes * 4 && q.questions.length) {
      pool = pool.concat(q.questions);
    }
終了条件が時間だったため、時間を埋めるだけの数が必要で、
足りないぶんを【同じキューの丸ごとコピー】で水増ししていた。
テーマの問題が12問しかなければ、10分ノックは同じ12問を3周する。

ここで固定するのは3つ。
  ① 水増しをしない（キューに同じ問題が二度入らない）
  ② 足りないときは、あるぶんだけ出して終わる（周回しない・黙らない）
  ③ 進み具合を出す（残り時間ではない）
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
sc = open(os.path.join(base, "scheduler.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("水増しのループが消えている（同じキューを concat しない）",
   "pool = pool.concat(q.questions)" not in p2)
ok("選ぶのは分ではなく問題数（10問／30問）",
   'data-knock="10">10問ノック' in ix and 'data-knock="30">30問ノック' in ix)
ok("ホームのカードも問題数で書いてある", "10問 / 30問" in ix)
ok("id が「時間」を名乗っていない（3/10 を knock-time が出すのは嘘）",
   'id="knock-count"' in ix and 'id="knock-hud"' in ix and 'id="knock-time"' not in ix)
ok("CSSも追随している", ".knock-hud{" in cs and ".knock-count{" in cs)
ok("時計を回していない（tick を起動しない）", "setInterval(tickKnock" not in p2)
ok("getKnockQueue が頼んだ数と出せた数の両方を返す",
   "q.requested = count;" in sc and "q.available =" in sc and "q.short =" in sc)
ok("ガイドの表記も問題数になっている",
   "テーマ別 弱点ノック（10問/30問）" in p2 and "10問・30問で集中演習" in p2)

TAG = "#ノック検証"
def q(i):
    return {"source": "検証問%d" % i, "unit": "必修",
            "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
            "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
            "stem": "ノック検証の問題%d。正しいのはどれか。" % i,
            "atoms": [{"text": "誤り%d" % i, "statement": "誤り", "explanation": "誤り。",
                       "is_correct": False, "tags": [TAG]},
                      {"text": "正しい%d" % i, "statement": "正しい", "explanation": "正しい。",
                       "is_correct": True, "tags": [TAG]}]}
PAYLOAD = json.dumps({"questions": [q(i) for i in range(1, 7)]}, ensure_ascii=False)   # 6問だけ
MORE = json.dumps({"questions": [q(i) for i in range(7, 27)]}, ensure_ascii=False)     # +20問

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.evaluate("async (t) => { await window.Storage.importText(t); }", PAYLOAD)

    # ① 6問しかないテーマに30問を頼む
    a = pg.evaluate("""async (tag) => {
      const H = window.Half2Impl, M = window.Main;
      await H.startKnock(tag, 30);
      const t0 = Date.now();
      while (M.state.screen !== 'quiz' && Date.now() - t0 < 8000) {
        await new Promise(r => setTimeout(r, 50));
      }
      const qs = M.state.session.questions.map(x => x.q_id);
      const uniq = Object.keys(qs.reduce((o,k)=>(o[k]=1,o),{})).length;
      const hud = (document.getElementById('knock-count')||{}).textContent;
      return { n: qs.length, uniq: uniq, hud: hud, tick: !!H.st.knock.tick,
               total: H.st.knock.total };
    }""", TAG)
    ok("6問しかないテーマで30問を頼んでも、水増しされない", a["n"] == 6, json.dumps(a, ensure_ascii=False))
    ok("同じ問題がキューに二度入らない", a["uniq"] == a["n"], json.dumps(a, ensure_ascii=False))
    ok("進み具合は 0 / 6 と出る", a["hud"] == "0 / 6", json.dumps(a, ensure_ascii=False))
    ok("時計は動いていない", a["tick"] is False, json.dumps(a, ensure_ascii=False))

    # 進み具合が進む
    b = pg.evaluate("""() => {
      const M = window.Main;
      M.hooks.afterCommit(null, { mode: 'knock' });
      M.hooks.afterCommit(null, { mode: 'knock' });
      return (document.getElementById('knock-count')||{}).textContent;
    }""")
    ok("解くたびに進み具合が進む", b == "2 / 6", str(b))

    # 片付け
    pg.evaluate("() => window.Main.endSession()")
    pg.wait_for_timeout(400)

    # ② 26問あるテーマに10問を頼む
    pg.evaluate("async (t) => { await window.Storage.importText(t); }", MORE)
    c = pg.evaluate("""async (tag) => {
      const H = window.Half2Impl, M = window.Main;
      await H.startKnock(tag, 10);
      const t0 = Date.now();
      while (M.state.screen !== 'quiz' && Date.now() - t0 < 8000) {
        await new Promise(r => setTimeout(r, 50));
      }
      const qs = M.state.session.questions.map(x => x.q_id);
      const uniq = Object.keys(qs.reduce((o,k)=>(o[k]=1,o),{})).length;
      return { n: qs.length, uniq: uniq,
               hud: (document.getElementById('knock-count')||{}).textContent };
    }""", TAG)
    ok("問題が足りているときは頼んだ数ちょうど（10問）", c["n"] == 10, json.dumps(c, ensure_ascii=False))
    ok("そのときも重複しない", c["uniq"] == 10, json.dumps(c, ensure_ascii=False))
    ok("進み具合は 0 / 10", c["hud"] == "0 / 10", json.dumps(c, ensure_ascii=False))

    d = pg.evaluate("""async (tag) => {
      const q = await window.Scheduler.getKnockQueue(tag, { count: 30 });
      return { requested: q.requested, available: q.available, short: q.short };
    }""", TAG)
    ok("頼んだ数と出せた数の差を、呼び出し側が知れる",
       d["requested"] == 30 and d["available"] == 26 and d["short"] is True,
       json.dumps(d, ensure_ascii=False))

    pg.evaluate("() => window.Main.endSession()")
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
print("\n%d/%d  knock_count" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
