#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E-3 検証：弱点分析の1画面統合 ／ キーワード検索の独立 ／ data-level の不具合修正"""
import json, os, sys, subprocess, glob, re
from playwright.sync_api import sync_playwright

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []
def ok(n, c, d=""): R.append((bool(c), n, d))

P1 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part1_V*.js")))[-1])
P2 = os.path.basename(sorted(glob.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
for f in ["storage.js", "scheduler.js", P1, P2, "sw.js"]:
    p = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True)
    ok("syntax %s" % f, p.returncode == 0, p.stderr.strip()[:200])

idx = open(os.path.join(APP, "index.html"), encoding="utf-8").read()
sw = open(os.path.join(APP, "sw.js"), encoding="utf-8").read()
ok("index の script/REQUIRED が実ファイルを指す", idx.count(P1) == 2 and idx.count(P2) == 2)
ok("sw の CORE_ASSETS が実ファイルを指す", P1 in sw and P2 in sw)
ok("index/sw に他版の part2 が残っていない",
   len(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))) == 1,
   str(set(re.findall(r"main_part2_V\d+\.\d+\.js", idx + sw))))
_c = re.search(r"CACHE_NAME = 'v(\d+)\.(\d+)\.(\d+)'", sw)
ok("sw CACHE_NAME が v1.9.0 以降",
   bool(_c) and tuple(int(x) for x in _c.groups()) >= (1, 9, 0),
   _c.group(0) if _c else "not found")
ok("HTML に data-level=\"sub\" が残っていない（\"sub_item\" が正）",
   'data-level="sub"' not in idx)
ok("テーマ別の一覧が検索画面から消えている",
   idx.split('id="screen-search"')[1].split("</section>")[0].count("concept-list") == 0)

def _external(t):
    return ("ERR_TUNNEL_CONNECTION_FAILED" in t or "accounts.google.com" in t
            or "gsi/client" in t or "ERR_NAME_NOT_RESOLVED" in t)

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" and not _external(m.text) else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=20000)
    pg.wait_for_timeout(2200)
    try:
        pg.click("#welcome-start", timeout=2500)
    except Exception:
        pass
    pg.wait_for_timeout(600)
    pg.evaluate("window.Main.go('home')")
    pg.wait_for_timeout(400)

    # ---------- ホームのツール一覧 ----------
    tools = pg.evaluate("""() => Array.from(document.querySelectorAll('.tool-list .tool-row'))
      .map(b => ({ a: b.getAttribute('data-action'), t: b.querySelector('b').textContent }))""")
    # V1.39：「力試し」がサブカードへ移り、ツールは4行（アプリ側が正）
    # V1.41：単元別学習をランダムの階層UIへ統合したので3行（アプリ側が正）
    ok("ツールは3行", len(tools) == 3, json.dumps(tools, ensure_ascii=False))
    ok("1行目が「弱点分析」",
       tools[0]["a"] == "go-dashboard" and tools[0]["t"] == "弱点分析",
       json.dumps(tools[0], ensure_ascii=False))
    ok("2行目が「キーワード検索」（分析と分かれた）",
       tools[1]["a"] == "go-search" and tools[1]["t"] == "キーワード検索",
       json.dumps(tools[1], ensure_ascii=False))
    ok("「得意・不得意ダッシュボード」の行は無くなった",
       not [x for x in tools if "ダッシュボード" in x["t"]], json.dumps(tools, ensure_ascii=False))
    ok("go-dashboard は1行だけ（入口が二重になっていない）",
       len([x for x in tools if x["a"] == "go-dashboard"]) == 1)

    # ---------- データを作る ----------
    pg.evaluate("""async()=>{ const S=window.Storage,K=window.Scheduler;
      const qs=await S.getAllQuestions();
      for (const q of qs){ const at=await S.getAtomsByQuestion(q.q_id);
        const cn=at.filter(a=>a.is_correct).map(a=>a.original_num);
        const rec=K.recommendEvaluations(at,cn);
        await K.applyQuestionEvaluations(q.q_id,
          at.map(a=>({atom_id:a.atom_id,eval:rec.recommendations[a.atom_id].eval,is_correct:true})),
          {mode:'new',boundaryHour:4}); } }""")

    # ---------- 統合画面 ----------
    d = pg.evaluate("""async () => {
      await window.Half2Impl.openDashboard();
      const q = s => document.querySelector(s);
      return {
        title: q('#screen-dashboard .sc-title').textContent,
        axes: Array.from(document.querySelectorAll('#screen-dashboard .seg-btn[data-level]'))
                .map(b=>b.getAttribute('data-level')),
        active: Array.from(document.querySelectorAll('#screen-dashboard .seg-btn[data-level].is-active'))
                .map(b=>b.getAttribute('data-level')),
        rows: document.querySelectorAll('#bar-chart .bar-row').length,
        crumb: (q('#bar-chart .bar-crumb')||{}).textContent,
        metricHidden: q('#dash-metric').hidden,
        cSegHidden: q('#dash-concept').hidden,
        hint: q('#dash-hint').textContent,
        conceptHidden: q('#concept-list').hidden
      }; }""")
    ok("画面名が「弱点分析」", d["title"] == "弱点分析", d["title"])
    ok("軸は5つ（テーマを含む）",
       d["axes"] == ["unit", "major", "medium", "sub_item", "tag"], json.dumps(d["axes"]))
    ok("開いた直後は小項目が点灯している（V1.20 では1つも点かなかった）",
       d["active"] == ["sub_item"], json.dumps(d["active"]))
    ok("小項目で複数行に分かれる（V1.20 では「(未分類)」1行に潰れていた）",
       d["rows"] >= 4, str(d["rows"]))
    ok("行にパンくずが出る", bool(d["crumb"]) and "＞" in d["crumb"], str(d["crumb"]))
    ok("項目軸では指標の切り替えが出る", not d["metricHidden"], json.dumps(d))
    ok("項目軸ではテーマの並び順は出さない", d["cSegHidden"], json.dumps(d))
    ok("項目軸ではテーマ一覧を隠す", d["conceptHidden"], json.dumps(d))
    ok("行タップの案内が出ている", "タップ" in d["hint"], d["hint"])

    # 4つの項目軸すべてで行が出ること
    axes = pg.evaluate("""async () => {
      const H=window.Half2Impl, out={};
      for (const lv of ['unit','major','medium','sub_item']) {
        await H.renderDashboard(lv, null);
        out[lv] = { rows: document.querySelectorAll('#bar-chart .bar-row').length,
                    unclassified: Array.from(document.querySelectorAll('#bar-chart .bar-crumb'))
                                   .filter(e=>e.textContent.indexOf('(未分類)')>=0).length };
      }
      return out; }""")
    ok("4つの項目軸すべてで行が出る",
       all(v["rows"] > 0 for v in axes.values()), json.dumps(axes, ensure_ascii=False))
    ok("どの軸でも「(未分類)」が出ない",
       all(v["unclassified"] == 0 for v in axes.values()), json.dumps(axes, ensure_ascii=False))
    ok("小項目が最も細かく分かれる",
       axes["sub_item"]["rows"] >= axes["medium"]["rows"] >= axes["major"]["rows"] >= axes["unit"]["rows"],
       json.dumps(axes, ensure_ascii=False))

    # ---------- テーマ軸 ----------
    t = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      await H.renderDashboard('tag', null);
      const q = s => document.querySelector(s);
      return { bars: document.querySelectorAll('#bar-chart .bar-row').length,
               concepts: document.querySelectorAll('#concept-list .concept-row').length,
               conceptHidden: q('#concept-list').hidden,
               metricHidden: q('#dash-metric').hidden,
               cSegHidden: q('#dash-concept').hidden,
               hint: q('#dash-hint').textContent,
               activeC: Array.from(document.querySelectorAll('#screen-dashboard .seg-btn[data-cfilter].is-active'))
                         .map(b=>b.getAttribute('data-cfilter')) }; }""")
    ok("テーマ軸でテーマ一覧が出る", t["concepts"] > 0 and not t["conceptHidden"],
       json.dumps(t, ensure_ascii=False))
    ok("テーマ軸では棒グラフを出さない", t["bars"] == 0, json.dumps(t))
    ok("テーマ軸では指標の切り替えを隠す（押しても効かないため）",
       t["metricHidden"], json.dumps(t))
    ok("テーマ軸では並び順の切り替えが出る", not t["cSegHidden"], json.dumps(t))
    ok("並び順の初期値は「苦手な順」", t["activeC"] == ["low"], json.dumps(t))
    ok("テーマ軸の案内文が弱点ノックを指す", "弱点ノック" in t["hint"], t["hint"])

    # 並びは「同点だと入れ替わらない」のが正しいので、順番の差ではなく
    # 表示されている理解度が単調かどうかで見る。
    order = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      const pcts = () => Array.from(document.querySelectorAll('#concept-list .concept-pct'))
        .map(e => e.textContent).filter(t => t.indexOf('%') >= 0)
        .map(t => parseInt(t, 10));
      await H.renderConceptRanking('high');
      const a = pcts();
      await H.renderConceptRanking('low');
      const b = pcts();
      await H.renderConceptRanking('unlearned');
      const c = document.querySelectorAll('#concept-list .concept-row').length;
      await H.renderConceptRanking('low');
      return { high:a, low:b, unlearnedRows:c }; }""")
    ok("「苦手な順」は理解度が小さい順に並ぶ",
       all(order["low"][i] <= order["low"][i + 1] for i in range(len(order["low"]) - 1)),
       json.dumps(order, ensure_ascii=False))
    ok("「得意な順」は理解度が大きい順に並ぶ",
       all(order["high"][i] >= order["high"][i + 1] for i in range(len(order["high"]) - 1)),
       json.dumps(order, ensure_ascii=False))
    ok("「まだ解いていない」でも一覧が出せる", order["unlearnedRows"] > 0, str(order["unlearnedRows"]))

    # ---------- 行タップ＝出題 ----------
    drill = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      await H.openDashboard(); await H.renderDashboard('sub_item', null);
      const row = document.querySelector('#bar-chart .bar-row');
      const f = row.getAttribute('data-scope-field'), v = row.getAttribute('data-scope-value');
      row.click();
      /* 固定の待ち時間にしない。900ms 決め打ちだと、機械が混んでいるときだけ
         遷移が間に合わず、**関係ない変更のたびに赤くなる**。
         不安定なテストは、赤を無視する癖がつくので無いほうがまし。
         条件が満たされるまで待ち、上限を過ぎたらそのまま返す。 */
      const t0 = Date.now();
      while (window.Main.state.screen !== 'quiz' && Date.now() - t0 < 8000) {
        await new Promise(r => setTimeout(r, 50));
      }
      return { tag: row.tagName, field:f, value:v,
               waited: Date.now() - t0,
               screen: window.Main.state.screen,
               mode: window.Main.state.session.mode,
               qs: window.Main.state.session.questions.length }; }""")
    ok("行はボタンになっている（押せることが読み取れる）", drill["tag"] == "BUTTON", drill["tag"])
    ok("行に範囲（軸と値）が入っている",
       drill["field"] == "sub_item" and bool(drill["value"]), json.dumps(drill, ensure_ascii=False))
    ok("行タップで出題が始まる", drill["screen"] == "quiz" and drill["qs"] > 0,
       json.dumps(drill, ensure_ascii=False))
    ok("出題モードは単元別（割り込み・トピックガードの扱いを変えない）",
       drill["mode"] == "tree", drill["mode"])

    knock = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      await H.openDashboard(); await H.renderDashboard('tag', null);
      const row = document.querySelector('#concept-list .concept-row');
      const tag = row.getAttribute('data-tag');
      row.click();
      await new Promise(r=>setTimeout(r,700));
      const m = document.getElementById('modal-knock');
      return { tag, dialogOpen: m ? !m.hidden : null }; }""")
    ok("テーマ行タップで弱点ノックのダイアログが開く",
       knock["dialogOpen"] is not False, json.dumps(knock, ensure_ascii=False))
    pg.evaluate("window.Main.closeModals()")

    # ---------- 検索の独立 ----------
    s2 = pg.evaluate("""async () => {
      await window.Half2Impl.openSearch();
      return { title: document.querySelector('#screen-search .sc-title').textContent,
               conceptRows: document.querySelectorAll('#screen-search .concept-row').length,
               hasBar: !!document.querySelector('#screen-search .search-bar'),
               screen: window.Main.state.screen }; }""")
    ok("検索画面のタイトルが「キーワード検索」", s2["title"] == "キーワード検索", s2["title"])
    ok("検索画面にテーマ一覧が同居していない", s2["conceptRows"] == 0, json.dumps(s2, ensure_ascii=False))
    ok("検索窓は残っている", s2["hasBar"], json.dumps(s2))

    search = pg.evaluate("""async () => {
      const H=window.Half2Impl;
      await H.runSearch('人口');
      await new Promise(r=>setTimeout(r,500));
      return { hits: document.querySelectorAll('#search-results .search-hit').length,
               solveShown: !document.getElementById('btn-solve-now').hidden }; }""")
    ok("検索が動く（統合で壊していない）", search["hits"] > 0, json.dumps(search))
    ok("「この結果を今すぐ解く」が出る", search["solveShown"], json.dumps(search))

    # ---------- ガイド ----------
    g = pg.evaluate("""() => {
      const T = window.Half2Impl.TIPS;
      return { hasConcept: !!T.concept,
               dash: T.dashboard.text,
               dashSel: T.dashboard.sel,
               search: T.search.text }; }""")
    ok("ガイド concept は削除された（画面が1つになったため）", not g["hasConcept"], json.dumps(g, ensure_ascii=False))
    ok("ガイド dashboard が5つの見方に言及している",
       "テーマ" in g["dash"] and "5つ" in g["dash"], g["dash"])
    ok("ガイド dashboard が行タップに言及している", "タップ" in g["dash"], g["dash"])
    ok("ガイド dashboard の対象が統合画面を指す",
       g["dashSel"] == "#screen-dashboard .dash-controls", g["dashSel"])

    # ---------- 一言欄 ----------
    tips = pg.evaluate("window.Half2Impl.HOME_TIPS")
    ok("一言欄は34件のまま", len(tips) == 34, str(len(tips)))
    t16 = [x for x in tips if x["id"] == "t16"][0]
    t17 = [x for x in tips if x["id"] == "t17"][0]
    ok("t16 のラベルが「弱点分析」に変わった", t16["label"] == "弱点分析", json.dumps(t16, ensure_ascii=False))
    ok("t17 のラベルも「弱点分析」に変わった", t17["label"] == "弱点分析", json.dumps(t17, ensure_ascii=False))
    ok("旧「テーマ別 弱点分析」のカードは残っていない",
       not [x for x in tips if x["label"] == "テーマ別 弱点分析"])
    ok("旧「得意・不得意ダッシュボード」のカードは残っていない",
       not [x for x in tips if "ダッシュボード" in x["label"]])
    ok("t16 が5つの見方を説明している", "5つ" in t16["body"] or "5つ" in t16["title"],
       json.dumps(t16, ensure_ascii=False))
    ok("t17 が行タップを説明している", "タップ" in t17["title"] or "押す" in t17["body"],
       json.dumps(t17, ensure_ascii=False))
    ok("マスターの一言から「※力試しモードでは出現します」が消えている",
       "力試しモードでは出現します" not in "".join(x["body"] for x in tips))

    # ---------- 軸の並びが端末幅で崩れない ----------
    geo = pg.evaluate("""async () => {
      await window.Half2Impl.openDashboard();
      const seg = document.querySelector('#screen-dashboard .seg-axis');
      const btns = Array.from(seg.querySelectorAll('.seg-btn'));
      const tops = new Set(btns.map(b => Math.round(b.getBoundingClientRect().top)));
      return { rows: tops.size, h: Math.round(seg.getBoundingClientRect().height),
               scrollable: seg.scrollWidth > seg.clientWidth + 1 }; }""")
    ok("軸ボタンは1段に収まる（折り返して下の要素を押し下げない）",
       geo["rows"] == 1, json.dumps(geo))

    pg.set_viewport_size({"width": 320, "height": 844})
    pg.wait_for_timeout(400)
    geo320 = pg.evaluate("""() => {
      const seg = document.querySelector('#screen-dashboard .seg-axis');
      const btns = Array.from(seg.querySelectorAll('.seg-btn'));
      const tops = new Set(btns.map(b => Math.round(b.getBoundingClientRect().top)));
      return { rows: tops.size, scrollable: seg.scrollWidth > seg.clientWidth + 1 }; }""")
    ok("320px幅でも1段のまま（入りきらない場合は横スクロール）",
       geo320["rows"] == 1, json.dumps(geo320))
    pg.set_viewport_size({"width": 390, "height": 844})

    ok("ページ例外なし", not errs, " | ".join(errs[:3]))
    br.close()

fails = [r for r in R if not r[0]]
print("\n".join(("  ok  " if c else "  NG  ") + n + (("   << " + d) if (d and not c) else "")
                for c, n, d in R))
print("\n%d 項目中 %d 通過 / %d 失敗" % (len(R), len(R) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
