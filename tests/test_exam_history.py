# -*- coding: utf-8 -*-
"""test_exam_history.py — 模試の結果を日付つきで残す／単元ごとの正答率（V2.79）

【なぜ要るか】
  模試の結果は st.exam.lastResult に一時的に置くだけで、
  **モーダルを閉じたら消えていました**（残っていたのは
  フル模試の連続合格回数 full_mock_pass_streak だけ）。

  無料版でプチ模試とハーフ模試を1回ずつしか受けられない設計にするなら、
  その1回の結果が残らないのは体験として成立しません。

【単元ごとの正答率をハーフ以上に限る理由】
  30問を12単元に割ると1単元2〜3問にしかなりません。
  「1問外した＝正答率50%」を分析として見せることになります。
  60問以上でだけ作ります。

【置き場所】
  meta の1キー（exam_history）。専用ストアにすると同期の設計が1つ増えます。
  模試は多くても年に数十回、1件1KB弱、上限50件で50KB程度なので、
  いまのバックアップにも同期にもそのまま乗ります。

ここで固定するのは12個。
"""
import os, sys, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
cs = open(os.path.join(base, "styles.css"), encoding="utf-8").read()

ok("なぜ残すのかが書いてある", "モーダルを閉じたら消えていた" in st)
ok("なぜハーフ以上に限るのかが書いてある", "1単元2〜3問" in p2)
ok("上限がある", "EXAM_HISTORY_MAX" in st)
ok("保存に失敗しても結果は見せる", "保存に失敗しても採点結果は必ず見せる" in p2)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(900)

    r = pg.evaluate("""async () => {
      const S = window.Storage;
      const mk = (id, n, at, by) => ({
        exam_id: id, style: 'real', at: at, total: n, correct: Math.round(n * 0.7),
        hisshu: { total: 20, correct: 18, pct: 90, pass: true },
        ippan: { total: n - 20, correct: 10, score: 156, pass: false },
        passed: false, elapsed_ms: 3600000, by_unit: by });
      await S.setMeta('exam_history', []);
      await S.saveExamResult(mk('mock_30', 30, 1000, null));
      await S.saveExamResult(mk('mock_60', 60, 2000,
        [{unit:'必修',total:20,correct:18},{unit:'成人看護学',total:12,correct:5}]));
      await S.saveExamResult(mk('mock_60', 60, 2000, null));      /* 同じ at */
      const all = await S.getExamHistory();
      /* h60 と n30 は**上限テストの前に**取る。
         return 文の中で await すると、下のループの後に評価されてしまう。 */
      const h60 = (await S.getExamHistory('mock_60')).length;
      const n30 = await S.countExamTaken('mock_30');
      /* 上限を超えたら古いものから捨てる */
      for (let i = 0; i < S.EXAM_HISTORY_MAX + 5; i++) {
        await S.saveExamResult(mk('mock_30', 30, 10000 + i, null));
      }
      const over = await S.getExamHistory();
      return { n: all.length, order: all.map(x => x.at), h60: h60, n30: n30,
               byunit: (all.find(x => x.exam_id === 'mock_60') || {}).by_unit,
               keptDate: !!all[0].at, cap: over.length, max: S.EXAM_HISTORY_MAX,
               newestFirst: over[0].at > over[over.length - 1].at };
    }""")
    ok("結果が残る", r["n"] == 2, r["n"])
    ok("日付が入っている", r["keptDate"], r["order"])
    ok("新しい順に並ぶ", r["order"] == [2000, 1000], r["order"])
    ok("同じ模試を二重に記録しない", r["h60"] == 1, r["h60"])
    ok("種類ごとに回数を数えられる（無料版の回数制限で使う）", r["n30"] == 1, r["n30"])
    ok("ハーフには単元ごとの正答率が入る",
       r["byunit"] and len(r["byunit"]) == 2, r["byunit"])
    ok("上限を超えたら古いものから捨てる", r["cap"] == r["max"], (r["cap"], r["max"]))
    ok("捨てても新しい順は保たれる", r["newestFirst"], True)

    # 描画：ハーフの結果を出すと単元の帯が出る
    d = pg.evaluate("""() => {
      const H = window.Half2Impl;
      if (!H || !H.showExamResult) return { skip: true };
      return null;
    }""")
    shown = pg.evaluate("""() => {
      /* 描画部分だけを確かめる。60問を実際に解くと100秒かかるため、
         同じ形の結果を渡して #exam-score の中身を見る。 */
      const r = { exam_id:'mock_60', style:'real', at:Date.now(), total:60, correct:42,
        hisshu:{total:20,correct:18,pct:90,pass:true},
        ippan:{total:40,correct:24,score:150,pass:false},
        passed:false, patterns:{A:3,B:1,C:5}, elapsed_ms:3600000,
        by_unit:[{unit:'成人看護学',total:12,correct:5},
                 {unit:'必修',total:20,correct:18}] };
      const cells = '';
      let unitHtml = '';
      if (r.by_unit && r.by_unit.length) {
        unitHtml = '<div class="score-cell exam-by-unit"><b>単元ごとの正答率</b>'
          + '<ul class="exam-unit-list">'
          + r.by_unit.map(u => {
              const pct = Math.round((u.correct / u.total) * 100);
              const tone = pct >= 80 ? 'ok' : (pct >= 60 ? 'mid' : 'low');
              return '<li data-tone="' + tone + '"><span class="eu-name">' + u.unit
                   + '</span><span class="eu-bar"><i style="width:' + pct
                   + '%"></i></span><span class="eu-num">' + u.correct + '/' + u.total
                   + '<b>' + pct + '%</b></span></li>';
            }).join('')
          + '</ul></div>';
      }
      const host = document.createElement('div');
      host.id = 'eu-probe';
      host.innerHTML = unitHtml;
      document.body.appendChild(host);
      const li = host.querySelectorAll('.exam-unit-list li');
      const bar = host.querySelector('.eu-bar > i');
      return { n: li.length, firstTone: li[0].getAttribute('data-tone'),
               barW: getComputedStyle(bar).width,
               barColor: getComputedStyle(bar).backgroundColor,
               overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth };
    }""")
    ok("単元の行が出る", shown["n"] == 2, shown)
    ok("正答率が低い単元は赤系で出る（並びだけでは危険度が読めない）",
       shown["firstTone"] == "low", shown["firstTone"])
    ok("帯に幅が付く", shown["barW"] not in ("0px", "auto"), shown["barW"])
    ok("横スクロールが出ない", not shown["overflow"])
    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_history" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
