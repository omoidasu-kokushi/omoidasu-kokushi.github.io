# -*- coding: utf-8 -*-
"""test_print_escape.py — 紙に出すときも取り込んだHTMLを素で入れない（V3.21）

【何が起きていたか（2026-09-15・実測）】
  DESIGN_DECISIONS 22-1（V1.84）は「取り込んだHTMLはそのまま画面へ入れない。
  解説はHTMLのまま描画するため <img onerror> が実行され、外部通信も出ていた。
  sanitizeExplanationHtml を必ず通す」と決めた。

  **間違いノート印刷（part2 noteItemHtml）だけ直っていなかった。**
  V1.84 はこの関数を触っている（`user_memo` に esc を足し「紙に出すときは必ず
  エスケープする」とコメントまで書いた）のに、**取り込んだ側は素のまま**だった。

  調査用の問題（stem・atom.text・atom.explanation に <img src=x onerror=…> を入れた
  1問）を取り込んで★を付け、`buildPrintSheet` を呼ぶと：
    ・`#print-sheet` の innerHTML に onerror が **3つ** 残る
    ・**3つとも実行される**（stem／atom_text／atom_exp）
  印刷シートは別窓ではなく **アプリ自身の文書**（body 直下・V1.70）へ入るので、
  アプリの出所で動く。同じ問題を解説画面で開いても発火しない（V1.84 が効いている）。

【直し方】
  ・文字として出すもの（why・num_code・分類のパンくず・問題文・肢の本文）→ esc
  ・書式を残したいもの（肢の解説。<b> が効いている）→ sanitizeExplanationHtml（許可リスト・img は不可）
  ・全体解説は元からタグを落としている（`replace(/<[^>]+>/g, ' ')`）。**紙面の量が変わるので触らない**（V1.74）

【ここで固定すること】
  ・取り込んだ <img onerror> が印刷シートで1つも実行されない
  ・印刷シートに**生きた** onerror 属性・<script>・img が1つも無い
    （エスケープすれば &lt;img … onerror=…&gt; は**文字として**残る。そこを見ない）
  ・**普通の解説の書式は紙でも生きる**（<b> は残る。エスケープで潰さない）
  ・問題文と肢の本文は文字として出る（タグが効かない）
  ・対照：同じ問題を解説画面で開いても発火しない（V1.84 が効いている）
"""
import os, sys, io, time
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import glob as _g
p2 = sorted(_g.glob(os.path.join(base, "*main_part2_V*.js")))[-1]
js2 = io.open(p2, encoding="utf-8").read()

seg = js2[js2.index("function noteItemHtml"):js2.index("function buildPrintSheet")]
ok("印刷シートが問題文をエスケープする", "esc(q.stem" in seg)
ok("印刷シートが肢の本文をエスケープする", "esc(a.text" in seg)
ok("印刷シートが肢の解説を通す（素で入れない）", "clean(a.explanation)" in seg)
ok("分類・見出しもエスケープする", "esc(q.num_code" in seg and "esc(item.why" in seg)
ok("clean は sanitizeExplanationHtml（無ければ esc に倒す）",
   "M.sanitizeExplanationHtml" in seg and "esc(String(h" in seg)
ok("全体解説は元のまま（紙面の量を変えない）", "replace(/<[^>]+>/g, ' ')" in seg)
ok("22-1 を引いている", "22-1" in seg)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")

RUN = """async () => {
  const S = window.Storage, M = window.Main, H = window.Half2;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const P = f => '<img src=x onerror="window.__HIT=(window.__HIT||[]);window.__HIT.push(\\'' + f + '\\')">';
  const q = {
    q_id: 'PRINTESC1', pool: 'main', source: '調査用', rank: 'S',
    num_code: '1-1-A-a' + P('num_code'), unit: '必修問題', major: '1. 健康に関する指標',
    medium: 'A. 人口静態・人口動態', sub_item: 'a. 総人口', unit_no: 1,
    stem: 'しらべ用の問題 ' + P('stem'),
    overall_explanation: '全体解説 ' + P('overall'),
    atoms: [
      { original_num: 1, text: '肢1 ' + P('atom_text'), statement: '肢1', is_correct: true,
        explanation: '肢1の<b>太字</b>解説 ' + P('atom_exp'), tags: ['#人口動態統計'] },
      { original_num: 2, text: '肢2', statement: '肢2', is_correct: false,
        explanation: '肢2の解説', tags: ['#人口動態統計'] }
    ]
  };
  await S.importText(JSON.stringify([q]), {});
  const atoms = (await S.getAllAtoms()).filter(a => a.q_id === 'PRINTESC1');
  await S.toggleQuestionStar('PRINTESC1');
  await S.toggleAtomStar(atoms[0].atom_id);

  window.__HIT = [];
  const r = await H.buildPrintSheet({ kind: 'star', starLv: '0', paper: 'A4',
                                      cols: '1', explain: 'all', limit: 0 });
  await wait(900);
  const sheet = document.getElementById('print-sheet');
  const html = sheet ? sheet.innerHTML : '';
  const out = {
    count: r.count,
    fired: (window.__HIT || []).slice(),
    /* 生きた属性・要素として残っていないか（文字として見えるのは正しい姿）。
       ここは「onerror という文字列が無い」ではない：エスケープすれば
       &lt;img … onerror=…&gt; は**文字として残る**。見るのは生きた要素のほう。 */
    live_onerror: sheet ? sheet.querySelectorAll('[onerror]').length : -1,
    live_script: sheet ? sheet.querySelectorAll('script').length : -1,
    raw_img_tag: (html.match(/<img/gi) || []).length,
    imgs: sheet ? sheet.querySelectorAll('img').length : -1,
    /* 普通の書式は生きているか */
    bold_kept: /<b>太字<\\/b>/.test(html),
    /* 問題文は文字として出ているか（タグが効いていない） */
    stem_as_text: html.indexOf('しらべ用の問題') >= 0 && html.indexOf('&lt;img') >= 0
  };
  /* 対照：解説画面では発火しない（V1.84） */
  window.__HIT = [];
  await M.startSession({ mode: 'random', count: 1, qIds: ['PRINTESC1'] });
  await wait(600);
  const c = M.state.current;
  if (c) { c.selected = [1]; M.confirmAnswer(); await wait(900); }
  out.fired_on_screen = (window.__HIT || []).slice();
  return out;
}"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 900}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    t0 = time.time()
    while time.time() - t0 < 60:
        if pg.evaluate("() => window.__INIT_DONE === true"): break
        pg.wait_for_timeout(200)
    r = pg.evaluate(RUN)
    ok("調査用の1問が印刷シートに載る", r["count"] >= 1, r["count"])
    ok("取り込んだ <img onerror> が1つも実行されない", not r["fired"], r["fired"])
    ok("生きた onerror 属性が1つも残らない", r["live_onerror"] == 0, r["live_onerror"])
    ok("生きた <script> が1つも残らない", r["live_script"] == 0, r["live_script"])
    ok("印刷シートに img が1つも作られない", r["imgs"] == 0, r["imgs"])
    ok("<img タグが1つも組み立てられない（文字として出るのは可）", r["raw_img_tag"] == 0, r["raw_img_tag"])
    ok("普通の書式（<b>）は紙でも生きる", r["bold_kept"], r["bold_kept"])
    ok("問題文は文字として出る（タグが効かない）", r["stem_as_text"], r["stem_as_text"])
    ok("対照：解説画面でも発火しない（V1.84）", not r["fired_on_screen"], r["fired_on_screen"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  print_escape" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
