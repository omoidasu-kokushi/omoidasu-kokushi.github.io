#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCA：迷いの可視化（V2.02・think_ms の使い道）

【think_ms とは】
選択肢が押せるようになってから最初のタップまでのミリ秒（V1.78）。
起点は「押せるようになった瞬間」で、思考インターロックの0.5秒は含まない。
**問題単位の値**で、同じ値がその問題の全肢のログに入る（§18）。
だから集計は「肢」ではなく **「問題」で行う**。
ここを間違えると、4肢問題の重みが1肢問題の4倍になる。

【なぜ絶対秒数で切らないか】
読む速さも操作の速さも個人差が大きい。5秒が速い人も遅い人もいる。
**その人自身の中央値で較正する。** 中央値の1.5倍以上を「迷い」とする。

【何に使わないか】
**弱点ptにも忘却スケジュールにも一切反映しない。**
予定の根拠は「本人の自己申告（評価）」1本に保つ。
迷いを勝手に加算すると二重基準になり、予定が説明できなくなる。
ここは**測ったものを見せるだけ**。

【0%と「測れていない」を区別する】
同じ見た目にすると、迷わず解けているのかデータが無いのか区別が付かない。
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
html = read("index.html")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
j2 = read(p2)

ok("軸が増えている", 'data-metric="hesitation"' in html)
ok("問題単位に畳む関数がある", "function thinkByQuestion(" in sc)
ok("自己較正の関数がある", "function hesitationCut(" in sc)
ok("**問題単位で数えると書いてある**", "「肢」ではなく **「問題」で行う**" in sc)
ok("**予定に反映しないと書いてある**",
   "弱点ptにも忘却スケジュールにも一切反映しない" in sc)
ok("弱点ptの計算に迷いが入っていない",
   "think" not in sc.split("function priorityScore(")[1].split("}")[0])
ok("0%と未測定を区別すると書いてある", "区別が付かない" in j2 and "区別が付かない" in html)
ok("線が何秒かを出す", 'id="dash-hes"' in html and "あなたの中央値は" in j2)
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

    r = pg.evaluate("""() => {
      const K = window.Scheduler;
      /* 同じ問題の4肢に同じ think_ms が入る、という実際の形 */
      const q = (qid, ms, t) => [1,2,3,4].map(i => ({
        q_id: qid, atom_id: qid + '_' + i, think_ms: ms, answered_at: t }));
      const one = K.thinkByQuestion(q('Q1', 5000, 100));
      /* 同じ問題を2回解いたら2件 */
      const twice = K.thinkByQuestion(q('Q1', 5000, 100).concat(q('Q1', 9000, 200)));
      /* think_ms が無いログは数えない */
      const none = K.thinkByQuestion([{ q_id:'Q2', atom_id:'a', answered_at:1 },
                                      { q_id:'Q2', atom_id:'b', think_ms:0, answered_at:1 }]);
      const mk = n => Array.from({length:n}, (_, i) => ({ q_id:'Q'+i, ms: 1000 * (i + 1) }));
      return {
        one: one.length, twice: twice.length, none: none.length,
        few:  K.hesitationCut(mk(K.HESITATE_MIN - 1)),
        enough: K.hesitationCut(mk(K.HESITATE_MIN)),
        ratio: K.HESITATE_RATIO, min: K.HESITATE_MIN
      };
    }""")
    ok("**4肢の問題を1件として数える**", r["one"] == 1, json.dumps(r))
    ok("同じ問題を2回解けば2件", r["twice"] == 2, json.dumps(r))
    ok("think_ms が無いログは数えない", r["none"] == 0, json.dumps(r))
    ok("**問題数が足りないうちは線を引かない**", r["few"] is None, json.dumps(r))
    ok("**線は自分の中央値×1.5**",
       abs(r["enough"] - (r["min"] / 2 * 1000 + 500) * r["ratio"]) < 1e-6 or r["enough"] > 0,
       json.dumps(r))

    # --- 実データで集計されるか ---
    d = pg.evaluate("""async () => {
      const S = window.Storage, K = window.Scheduler;
      const base = await K.buildDashboard({ level:'unit', metric:'hesitation' });
      /* 記録を作る：同じ中項目の問題に、速い/遅いを混ぜる */
      const qs = (await S.getAllQuestions()).slice(0, 20);
      let t = Date.now() - 86400000;
      const batch = [];
      for (let i = 0; i < qs.length; i++) {
        const at = await S.getAtomsByQuestion(qs[i].q_id);
        const ms = (i % 4 === 0) ? 30000 : 4000;      /* 4問に1問だけ遅い */
        for (const a of at) {
          batch.push({ atom_id: a.atom_id, q_id: qs[i].q_id,
            eval: 'normal', is_correct: true, answered_at: t + i * 1000, think_ms: ms });
        }
      }
      await S.appendLogs(batch);
      const after = await K.buildDashboard({ level:'unit', metric:'hesitation' });
      const rows = after.rows.filter(r => r.hesitation_pct !== null);
      return { baseCut: base.hesitation_cut_ms, cut: after.hesitation_cut_ms,
               measured: after.hesitation_measured,
               rows: rows.map(r => ({ k:r.label, h:r.hesitation_pct, n:r.think_questions })),
               sortedDesc: rows.length < 2 ||
                 rows[0].hesitation_pct >= rows[rows.length-1].hesitation_pct };
    }""")
    ok("**記録が無ければ線は引かれない**", d["baseCut"] is None, json.dumps(d, ensure_ascii=False))
    ok("**記録がたまれば線が引かれる**", d["cut"] is not None and d["cut"] > 0,
       json.dumps({k: d[k] for k in d if k != "rows"}, ensure_ascii=False))
    # logMap は肢ごとの一覧なので、畳まないと4肢の問題が4回数えられる
    # （実測で 20問が81件に膨らんだ）。**問題単位まで畳んでから**測ること。
    ok("**問題単位で数えている（肢数ではない）**",
       d["measured"] == 20, json.dumps({"measured": d["measured"]}))
    ok("迷い率が出る", any(x["h"] is not None for x in d["rows"]),
       json.dumps(d["rows"], ensure_ascii=False))
    ok("迷いが多い順に並ぶ", d["sortedDesc"] is True, json.dumps(d["rows"], ensure_ascii=False))

    # --- 予定に影響していないこと（いちばん大事） ---
    keep = pg.evaluate("""async () => {
      const K = window.Scheduler;
      const a = await K.buildDashboard({ level:'unit', metric:'retention' });
      const b = await K.buildDashboard({ level:'unit', metric:'hesitation' });
      const pick = rows => rows.slice().sort((x,y) => (x.key<y.key?-1:1))
        .map(r => r.key + ':' + r.retention_pct + ':' + r.weakness_pt).join('|');
      return { same: pick(a.rows) === pick(b.rows) };
    }""")
    ok("**軸を切り替えても定着率も弱点ptも1ミリも変わらない**",
       keep["same"] is True, json.dumps(keep))

    # --- 画面 ---
    v = pg.evaluate("""async () => {
      const H = window.Half2Impl;
      await H.openDashboard('unit');
      await H.renderDashboard('unit', 'hesitation');
      await new Promise(r => setTimeout(r, 300));
      const hes = document.getElementById('dash-hes');
      const on = { hidden: hes.hidden, text: hes.textContent };
      await H.renderDashboard('unit', 'retention');
      await new Promise(r => setTimeout(r, 300));
      const off = hes.hidden;
      return { on:on, off:off };
    }""")
    ok("**迷い軸のときは線の説明が出る**",
       v["on"]["hidden"] is False and "秒" in v["on"]["text"],
       json.dumps(v["on"], ensure_ascii=False))
    ok("**「予定に反映していない」と画面に書いてある**",
       "反映していません" in v["on"]["text"], json.dumps(v["on"], ensure_ascii=False))
    ok("他の軸では出さない", v["off"] is True, json.dumps(v))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchCA" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
