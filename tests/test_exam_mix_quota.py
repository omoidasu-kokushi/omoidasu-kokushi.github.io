# -*- coding: utf-8 -*-
"""test_exam_mix_quota.py — 模試の単元配分・直前モードの混合比・いじわる模試の類似出題（V2.80）

【① 本番と同じ単元配分】
  これまでは全体からランダムに選んでいたので、60問の模試で
  成人が2問しか出ない、といったことが起こりえた（実測：必修11・成人9・人体8…）。

  第111〜115回の1,200問を機械集計した実測値（1回240問あたり）で枠を作る。
    必修 50.0（5回とも**正確に50問**）／成人 31.6／老年 21.6／小児 18.2
    基礎 17.6／母性 17.6／疾病 16.6／精神 16.6／在宅 13.4／人体 12.8
    健康支援 12.4／統合 11.6

  【問題そのものを①②③と固定しない理由】
    ・いじわる模試は弱点から組むので、そもそも固定できない
    ・固定すると mix（未見30%）も ranks:['S','A'] も効かなくなり、
      「どちらで受けますか」の選択が意味を失う
    ・フル模試8本ぶん（960問）は球が足りない（母性 要72/有70、疾病 要64/有56）

  途中で既存の不具合が1つ出た：枠どおり60問選んでも、あとから
  fillCaseSiblings（V2.56・連問の兄弟を引き入れる）が**別の単元の問題を
  押し出して**いた（必修14の枠が9問に、小児5の枠が8問に）。
  枠取りの段階で連問を兄弟ごと取るようにして解決。

【② 直前モードにも未見を1割】
  利用者の指摘：「全部見たことあるやつやんけ。こんなん解けて当然だろ」
  という感覚になってほしくない。初見が1問も無いと、点が取れても
  自分の実力なのか記憶なのかが分からない。
  未見 0% → 10%、そのぶん忘れかけ 45% → 35%（既習55%は動かさない）。

【③ いじわる模試は「同じ中項目の別問題」を当てる】
  これまでは弱点そのものを再出題していた。同じ問題を出すと、解けても
  「分かった」のか「覚えていた」のかが分からない。
  実測：同じ中項目に別の問題がある問題は 995/1,099（91%）。
  小項目だと 634/1,099（58%）しかないので、中項目で探す。
"""
import os, sys, io, json
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
sc = open(os.path.join(base, "scheduler.js"), encoding="utf-8").read()
ih = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("直前モードの未見は10%", "final: { fresh: 0.55, faded: 0.35, unseen: 0.10 }" in p2)
ok("なぜ未見を入れたかが書いてある", "解けて当然だろ" in p2)
ok("画面の説明にも初見が混ざると書いた", "初見も1割だけ混ざります" in ih)
ok("本番モードは変えていない", "real : { fresh: 0.25, faded: 0.45, unseen: 0.30 }" in p2)
ok("単元配分は実測値", "EXAM_UNIT_SHARE" in p2 and "'必修': 50.0" in p2)
ok("なぜ①②③に固定しないかが書いてある",
   "いじわる模試は弱点から組む" in sc and "いじわる模試は弱点から組むので固定できない" in p2)
ok("連問を枠内で取る（あとで押し出されないように）", "連問は兄弟ごと、この枠の中で取る" in sc)
ok("いじわる模試は類似問題に替える", "options.similar" in sc and "similar: true" in p2)
ok("替えたことを画面で言う", "同じ論点の別の問題に替えました" in p2)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
DIST = os.environ.get(
    "DIST_JSON",
    "/sessions/ecstatic-wizardly-dijkstra/mnt/owner/Desktop/国家試験対策室/"
    "過去問抽出_20260824/分類_令和5年版/out/20260908_配布_V1.05.json")

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context().new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(900)

    q = pg.evaluate("""() => {
      const H = window.Half2Impl;
      const s = n => Object.values(H.examUnitQuota(n)).reduce((a, b) => a + b, 0);
      return { q30: H.examUnitQuota(30), q60: H.examUnitQuota(60),
               sums: [s(30), s(60), s(120)] };
    }""")
    ok("枠の合計が問題数と一致する（余りが配分をぶらさない）",
       q["sums"] == [30, 60, 120], q["sums"])
    ok("必修がいちばん多い",
       q["q60"]["必修"] == max(q["q60"].values()), q["q60"])
    ok("ハーフ60の必修は14問（本番の50/240を按分）", q["q60"]["必修"] == 14, q["q60"]["必修"])

    if os.path.exists(DIST):
        txt = io.open(DIST, encoding="utf-8-sig").read()
        pg.evaluate("t => { window.__T = t; }", txt)
        pg.evaluate("async () => { await window.Storage.importText(window.__T); }")
        pg.evaluate("async () => { await window.Scheduler.refreshAll({recomputeWeakness:true}); }")
        r = pg.evaluate("""async () => {
          const K = window.Scheduler, H = window.Half2Impl;
          const q60 = H.examUnitQuota(60);
          const b = await K.buildQueue({ mode:'exam', count:60, applyGuard:false, shuffle:true,
            includeMock:true, mix:{fresh:.25,faded:.45,unseen:.30}, unitQuota:q60 });
          const by = {}; b.questions.forEach(x => { const u = x.unit||'?'; by[u]=(by[u]||0)+1; });
          const base = await K.buildQueue({mode:'exam',count:120,applyGuard:false,preferFrequent:true});
          const sim  = await K.buildQueue({mode:'exam',count:120,applyGuard:false,
                                           preferFrequent:true, similar:true});
          const med = x => { const s=new Set();
            x.questions.forEach(q2 => s.add([q2.unit,q2.major,q2.medium].join('|'))); return s; };
          const ma = med(base), mb = med(sim);
          let sameMed = 0; mb.forEach(x => { if (ma.has(x)) sameMed++; });
          const ids = new Set(base.questions.map(x => x.q_id));
          let sameQ = 0; sim.questions.forEach(x => { if (ids.has(x.q_id)) sameQ++; });
          return { n: b.questions.length, by: by, quota: q60,
                   swapped: sim.swapped_similar, sameQ: sameQ,
                   medA: ma.size, medB: mb.size, sameMed: sameMed };
        }""")
        diff = {u: r["by"].get(u, 0) - r["quota"][u] for u in r["quota"]}
        ok("組んだ60問が枠どおり", all(v == 0 for v in diff.values()), diff)
        ok("いじわる模試が類似に替えている（半分以上）",
           r["swapped"] >= 60, r["swapped"])
        ok("替えても弱点の中項目はそのまま（領域は動かさない）",
           r["sameMed"] == r["medB"], (r["sameMed"], r["medA"], r["medB"]))
        ok("替えたぶんは別の問題になっている",
           r["sameQ"] < 120, r["sameQ"])
    else:
        ok("（配布JSONが無いので実データの確認は省略）", True, DIST)

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  exam_mix_quota" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
