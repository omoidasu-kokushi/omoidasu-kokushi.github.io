# -*- coding: utf-8 -*-
"""test_atom_echo.py — 解説の頭にある「肢そのもの」の繰り返しを落とす（V2.78）

【見つけ方】V2.77 のレイアウトを実機で見ていて、本文がこうなっていた。

    ⇒誤り  ▸解説を見る
    ⇒誤り：① × 現在の総人口約1億2,400万人で… ⇒ 誤り：総人口は2008年を…

  「誤り」が3回、肢文が2回。生データはこの形だった。

    <br>① × 現在の総人口約1億2,400万人で…を維持する見込み
    ⇒ 誤り：総人口は2008年をピークに一貫して減少しており…

  画面に新しく足すものは「⇒ 誤り：」より後ろだけ。
    ①      … すでに .cx-num にある
    ×      … すでに .vd-chip にある
    肢文    … すでに .cx-text にある
    ⇒誤り： … prepareAtomExplanation が自分で足す

【実測（同梱シード453問・解説のある469肢）】
    ① × 肢文 ⇒ 誤り：理由   の形     245肢（52%）
    ② 誤り。理由             の形     118肢
    描画の正誤語 4回：51 → 1／2回：302 → 355

【切りすぎないための条件】
  ・落とす部分に**肢文が実際に入っている**こと（6字のウィンドウで確かめる）
  ・落とした残りが空にならないこと
  ・肢文が短いとき（「大腸菌」「否認」）は丸ごと一致のときだけ
  どれかを満たさなければ1文字も触らない。実測：切りすぎ0件。

ここで固定するのは、落とすべきものと**落としてはいけないもの**の両方。
"""
import io, json, os, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, str(detail)))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = base
js = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
ok("なぜ落とすのかが書いてある", "画面に新しく足すものは" in js or "肢の繰り返し" in js)
ok("切りすぎない条件が書いてある", "偶然の一致を避ける" in js)

CASES = [
    # (肢の本文, 生の解説, 期待, 説明)
    ("現在の総人口約1億2,400万人で2050年まで同水準を維持する見込み",
     "<br>① × 現在の総人口約1億2,400万人で2050年まで同水準を維持する見込み"
     " ⇒ 誤り：総人口は2008年をピークに減少している。",
     "総人口は2008年をピークに減少している。", "① × 肢文 ⇒ 誤り： を落とす"),

    ("臍帯には、2本の臍静脈と1本の臍動脈が通っており、臍静脈内には静脈血が流れている。",
     "<br>① × 2本の臍静脈と1本の臍動脈が通っており、臍静脈内には静脈血が流れている。"
     " ⇒ 誤り：臍帯の構造は1本の臍静脈と2本の臍動脈である。",
     "臍帯の構造は1本の臍静脈と2本の臍動脈である。", "肢文の頭が省かれていても落とす"),

    ("大腸菌", "<br>① ○ 大腸菌 ⇒ 正解：検出されないことと規定されているため。",
     "検出されないことと規定されているため。", "短い肢文でも落とす（丸ごと一致）"),

    ("患者に対する具体的な看護ケアの実施スケジュールを決定する",
     "②誤り。患者に対する具体的な看護ケアの実施スケジュールを決定するステップは"
     "「計画立案」であるため誤り。",
     "患者に対する具体的な看護ケアの実施スケジュールを決定するステップは"
     "「計画立案」であるため誤り。", "⇒が無い「②誤り。」の形も番号と正誤語を落とす"),

    # --- 落としてはいけないもの ---
    ("あ", "<br>① × あ ⇒ 誤り：", "<br>① × あ ⇒ 誤り：",
     "落とすと空になるなら触らない"),

    ("まったく関係のない選択肢の本文がここにある",
     "<br>① × ぜんぜん違う話をしている文 ⇒ 誤り：理由はこう。",
     "<br>① × ぜんぜん違う話をしている文 ⇒ 誤り：理由はこう。",
     "肢文が入っていなければ触らない（理由の中の ⇒誤り： を切らない）"),

    ("血圧の測定", "上腕動脈で測る。⇒ 誤り：という記述が理由の途中にある場合。",
     "上腕動脈で測る。⇒ 誤り：という記述が理由の途中にある場合。",
     "先頭が番号でなければ触らない"),

    ("心電図", "心電図はP波・QRS波・T波からなる。",
     "心電図はP波・QRS波・T波からなる。", "ふつうの解説は1文字も変えない"),
]

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context().new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_timeout(800)

    for text, raw, want, why in CASES:
        got = pg.evaluate("""([t, e]) => {
          const M = window.Main;
          return M.stripAtomLead(M.stripAtomEcho(e, {text: t}));
        }""", [text, raw])
        ok(why, got.strip() == want.strip(), "得 %r / 期 %r" % (got[:70], want[:70]))

    # 実データでの効き目と、切りすぎが無いこと
    # V2.89（2026-09-09）：同梱シードを必修249問へ入れ替えた（利用者裁定）。
    # 過去問の解説には「①×⇒誤り：」の echo がそもそも無いので、
    # 新シードで測ると「1件も落ちない」（実測 0/1005）。**仕組みが壊れたのではなく、
    # 測る相手がきれいになった**。echo の切り落としは上の固定ケースで見ている。
    # 実データでの効き目は、echo を持っている **退避した旧シード** で測り続ける。
    OLD = os.path.join(APP, "sample", "20260909_旧同梱シード_自由作問453問_V1.00.txt")
    ok("旧シードを消さずに退避してある", os.path.exists(OLD), OLD)
    old_tsv = io.open(OLD, encoding="utf-8").read()
    r = pg.evaluate("""async (tsv) => {
      const S = window.Storage, M = window.Main;
      await S.importText(tsv, {});
      const qs = await S.getAllQuestions();
      /* 旧シードの問題だけを見る（出典が無いのが旧シード） */
      const old = new Set(qs.filter(q => !q.source).map(q => q.q_id));
      const atoms = (await S.getAllAtoms()).filter(a => old.has(a.q_id));
      let n = 0, cut = 0, tooShort = 0; const dist = {};
      const plain = x => x.replace(/<[^>]*>/g, '').trim();
      for (const a of atoms) {
        const e = (a.explanation || '').trim(); if (!e) continue;
        n++;
        const af = M.stripAtomLead(M.stripAtomEcho(e, a));
        if (af !== e) { cut++; if (plain(af).length < 12) tooShort++; }
        const k = (M.renderAtomBody(a).match(/(誤り|正解)/g) || []).length;
        dist[k] = (dist[k] || 0) + 1;
      }
      return { n, cut, tooShort, dist };
    }""", old_tsv)
    # 件数そのものは、起動の速さでシードの取り込みがどこまで進んでいるかに左右される
    # （単独実行では 363肢、連続実行では 169肢を見た）。数ではなく**割合**で見る。
    ok("解説のある肢の3割以上で落ちている（旧シード）",
       r["n"] > 0 and r["cut"] / r["n"] >= 0.3, "%d/%d" % (r["cut"], r["n"]))
    ok("落としすぎて意味を失ったものが無い", r["tooShort"] == 0, str(r["tooShort"]))
    ok("正誤語が4回以上出る肢が5件以下（V2.77 では51件）",
       sum(v for k, v in r["dist"].items() if int(k) >= 4) <= 5,
       json.dumps(r["dist"], ensure_ascii=False))
    ok("正誤語2回（正常）がいちばん多い（旧シード）",
       r["dist"].get("2", 0) > r["dist"].get("3", 0),
       json.dumps(r["dist"], ensure_ascii=False))

    # 新しい同梱シード（過去問）側でも、切りすぎ・出しすぎが無いことを見る
    r2 = pg.evaluate("""async () => {
      const S = window.Storage, M = window.Main;
      const qs = await S.getAllQuestions();
      const now = new Set(qs.filter(q => q.source).map(q => q.q_id));
      const atoms = (await S.getAllAtoms()).filter(a => now.has(a.q_id));
      let n = 0, tooShort = 0; const dist = {};
      const plain = x => x.replace(/<[^>]*>/g, '').trim();
      for (const a of atoms) {
        const e = (a.explanation || '').trim(); if (!e) continue;
        n++;
        const af = M.stripAtomLead(M.stripAtomEcho(e, a));
        if (af !== e && plain(af).length < 12) { tooShort++; }
        const k = (M.renderAtomBody(a).match(/(誤り|正解)/g) || []).length;
        dist[k] = (dist[k] || 0) + 1;
      }
      return { n, tooShort, dist };
    }""")
    ok("過去問シードでも切りすぎが無い", r2["n"] > 0 and r2["tooShort"] == 0,
       json.dumps(r2, ensure_ascii=False))
    ok("過去問シードでも正誤語が4回以上の肢は5件以下",
       sum(v for k, v in r2["dist"].items() if int(k) >= 4) <= 5,
       json.dumps(r2["dist"], ensure_ascii=False))

    ok("JSエラーが出ていない", not errs, errs[:2])
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + ("" if good else "   << " + detail))
print("\n%d/%d  atom_echo" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
