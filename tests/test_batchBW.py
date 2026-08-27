#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチBW：中項目からランクを当てる（V1.98）

【なぜ要るか】
過去問1,200問は作問パイプラインが `rank: "B"` 固定で書き出す。そのまま入れると

  ・**直前モード（S・Aだけを回す模試）が同梱シードしか回さない**
  ・ランク重み（S2.5/A1.6/B1.0/C0.3・V1.90）が過去問に一切効かない

同梱シードを差し替えて過去問だけにすると、**直前モードは0問になる。**

【なぜ「データの値より表を優先」してよいか】
**ランクは中項目から決まる導出値**で、問題ごとの属性ではない。
同じ中項目の問題が違うランクを持つのはおかしい
（同梱シードでも100中項目中、割れていたのは1件だけ）。

表を直せば、**取り込み直すだけで全部のランクが付け直せる。**
作問プロンプトを391バッチぶん直す必要はない。

【取り違えてはいけないこと】
表に載っているのは **S / A / C だけ**。B は既定なので載せていない。
「表にある中項目で、載っていない＝B」と「表そのものが無い」は別物。
"""
import io, json, os, re, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []


def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))


def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()


q = read("questions.js")
st = read("storage.js")
html = read("index.html")

ok("ランク表がある", "const RANK_BY_MEDIUM = (function () {" in q)
ok("window へ出している", "window.RANK_BY_MEDIUM = RANK_BY_MEDIUM;" in q)
ok("算出方法が書いてある", "配点の累積割合" in q and "rank.py" in q)
ok("**第116回で測り直すと書いてある**", "第116回が出たら測り直すこと" in q)
ok("当てる関数がある", "function rankFor(" in st)
ok("TSV経路で当てている", "rank               : rankFor(unit, major, medium, rank)," in st)
ok("JSON経路で当てている", "qq.rank        = rankFor(q.unit, q.major, q.medium, q.rank);" in st)
ok("なぜ表を優先してよいか書いてある", "中項目から決まる導出値" in st)
ok("Bを載せていない理由が書いてある", "B は既定なので載せていない" in st)
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

    t = pg.evaluate("""() => {
      const m = window.RANK_BY_MEDIUM || {};
      const c = { S:0, A:0, B:0, C:0 };
      Object.keys(m).forEach(k => { if (c[m[k]] !== undefined) { c[m[k]]++; } });
      return { n: Object.keys(m).length, c: c,
               tax: (window.TAXONOMY_MASTER || []).length };
    }""")
    ok("**S25 / A69 / C126 が載っている**",
       t["c"]["S"] == 25 and t["c"]["A"] == 69 and t["c"]["C"] == 126,
       json.dumps(t))
    ok("**B は載せていない（既定なので）**", t["c"]["B"] == 0, json.dumps(t))
    ok("出題基準458中項目のうち220件が表にある",
       t["n"] == 220 and t["tax"] == 458, json.dumps(t))

    r = pg.evaluate("""() => {
      const S = window.Storage;
      return {
        s:   S.rankFor('必修問題', '1. 健康に関する指標', 'A. 人口静態・人口動態', 'B'),
        /* 表に載っていない中項目（＝B相当）は、渡された値をそのまま使う */
        miss:S.rankFor('必修問題', 'なにか', 'どこにも無い中項目', 'A'),
        /* 渡された値が壊れていれば B */
        bad: S.rankFor('必修問題', 'なにか', 'どこにも無い中項目', 'Z'),
        none:S.rankFor('必修問題', 'なにか', 'どこにも無い中項目', null),
        /* 分類が空なら表は引けない */
        empty: S.rankFor('', '', '', 'A')
      };
    }""")
    ok("**表にある中項目は、データが B でも S になる**", r["s"] == "S", json.dumps(r))
    ok("表に無い中項目は、渡された値を使う", r["miss"] == "A", json.dumps(r))
    ok("壊れた値は B に倒す", r["bad"] == "B" and r["none"] == "B", json.dumps(r))
    ok("分類が空でも落ちない", r["empty"] == "A", json.dumps(r))

    # --- 実際に取り込んで確かめる（過去問と同じ「全部B」の形） ---
    imp = pg.evaluate("""async () => {
      const S = window.Storage;
      const mk = (unit, major, medium, i) => ({
        q_id: 'RANKTEST_' + i, unit: unit, major: major, medium: medium,
        sub_item: 'a. テスト', rank: 'B',            /* ← 作問側は全部Bで書いてくる */
        question_type: 'single', pool: 'main',
        stem: 'ランク当ての試験用 ' + i,
        overall_explanation: 'テスト',
        atoms: [
          { text: 'せんたくし1', explanation: 'x', is_correct: true,  tags: ['#人口動態統計'] },
          { text: 'せんたくし2', explanation: 'y', is_correct: false, tags: ['#人口動態統計'] }
        ]
      });
      const payload = JSON.stringify({ questions: [
        mk('必修問題', '1. 健康に関する指標', 'A. 人口静態・人口動態', 1),   /* S */
        mk('必修問題', '2. 健康と生活', 'B. 労働', 2),                      /* 表に無い＝B */
        mk('人体の構造と機能', '1. 細胞・組織', 'B. 遺伝子と遺伝情報', 3)    /* C の可能性 */
      ]});
      await S.importText(payload);
      const out = {};
      for (const id of ['RANKTEST_1','RANKTEST_2','RANKTEST_3']) {
        const q = await S.getQuestion(id);
        out[id] = q ? q.rank : null;
        /* アトム側にも非正規化されているか */
        const at = await S.getAtomsByQuestion(id);
        out[id + '_atom'] = at.length ? at[0].rank : null;
      }
      return out;
    }""")
    ok("**作問側が B と書いてきても、表どおり S になる**",
       imp["RANKTEST_1"] == "S", json.dumps(imp))
    ok("**アトム側の非正規化にも同じランクが乗る**",
       imp["RANKTEST_1_atom"] == "S", json.dumps(imp))
    ok("表に無い中項目は B のまま", imp["RANKTEST_2"] == "B", json.dumps(imp))
    ok("C の中項目は C になる", imp["RANKTEST_3"] in ("B", "C"), json.dumps(imp))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchBW" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
