#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチAX：取り込み量の見積もり（V1.73）

V1.60 で入れた「始める前に空き容量を見る」ガードは、問題数の代わりに
**改行の数**を数えていた。TSVは1行＝1問なので正しいが、整形済みJSONでは
1問が数十行になる。実測では 1,173問の整形JSON（indent 1）が 73,000行あり、
12KB/問で 約880MB と見積もられて「保存領域が足りません」と誤って拒否された。
逆に1行へ詰めたJSONは1問と数え、見積もりが過小になる。

このバッチは、見積もりが**形式によらず問題数に一致する**ことを固定する。
"""
import io, json, os, sys, glob as _g

APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
R = []

def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

def read(f):
    return io.open(os.path.join(APP, f), encoding="utf-8").read()

# ---------------------------------------------------------------- 静的検査
sjs = read("storage.js")
p2 = os.path.basename(sorted(_g.glob(os.path.join(APP, "*main_part2_V*.js")))[-1])
p2js = read(p2)

ok("storage.js に estimateImportRows がある", "function estimateImportRows(" in sjs)
ok("APIとして公開されている", "estimateImportRows : estimateImportRows" in sjs)
ok("形式の判定は importText と同じ規則（先頭が [ か {）",
   "head === '['" in sjs and "head === '{'" in sjs)
ok("バックアップ形式（stores＋schema_version）も数える",
   "data.stores && data.schema_version" in sjs)
ok("part2 は改行ではなく estimateImportRows を使う",
   "S.estimateImportRows(text)" in p2js)
ok("なぜ直したかがコードに残っている（再発防止）",
   "改行の数" in p2js and "保存領域が足りません" in p2js)
ok("12KB/問の見積もり定数は変えていない（V1.58の実測）",
   "var BYTES_PER_QUESTION = 12 * 1024;" in sjs)

# ---------------------------------------------------------------- 実行時検査
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=30000)
    pg.wait_for_timeout(1200)
    try:
        pg.click("#welcome-start", timeout=4000)
    except Exception:
        pass
    pg.wait_for_timeout(600)

    r = pg.evaluate("""() => {
      const E = window.Storage.estimateImportRows;
      const mkq = (i) => ({
        unit:"必修問題", major:"1. 健康に関する指標", medium:"A. 人口静態・人口動態",
        sub_item:"a. 総人口", rank:"B", source:null, pool:"main",
        question_type:"single", select_count:1, stem:"問題文"+i,
        overall_explanation:"解説".repeat(30),
        atoms:[1,2,3,4].map(k => ({ original_num:k, is_correct:k===1,
          text:"肢"+k, statement:"断定文"+k, explanation:"理由".repeat(10), tags:["#人口動態統計"] }))
      });
      const list3 = [1,2,3].map(mkq);
      const big   = Array.from({length:1173}, (_,i) => mkq(i));
      const pretty3 = JSON.stringify({questions:list3}, null, 1);
      const tsv = "a\\tb\\tc\\n\\nd\\te\\tf\\n\\n\\ng\\th\\ti\\n";
      return {
        pretty3      : E(pretty3),
        pretty3Lines : (pretty3.match(/\\n/g)||[]).length + 1,
        min3         : E(JSON.stringify({questions:list3})),
        array3       : E(JSON.stringify(list3)),
        single       : E(JSON.stringify(mkq(0))),
        backup       : E(JSON.stringify({schema_version:3, stores:{questions:list3, atoms:[]}})),
        bigPretty    : E(JSON.stringify({questions:big}, null, 1)),
        bigLines     : (JSON.stringify({questions:big}, null, 1).match(/\\n/g)||[]).length + 1,
        tsv          : E(tsv),
        broken       : E("{ではないJSON"),
        empty        : E(""),
        leadingWS    : E("\\n\\n  " + pretty3)
      };
    }""")

    ok("整形JSON（3問）＝3問と数える", r["pretty3"] == 3, json.dumps(r))
    ok("その整形JSONの行数は3ではない（旧実装なら誤る）", r["pretty3Lines"] > 20, str(r["pretty3Lines"]))
    ok("詰めたJSON（3問・改行なし）＝3問", r["min3"] == 3, str(r["min3"]))
    ok("配列形式（3問）＝3問", r["array3"] == 3, str(r["array3"]))
    ok("単体オブジェクト＝1問", r["single"] == 1, str(r["single"]))
    ok("バックアップ形式＝questions の件数", r["backup"] == 3, str(r["backup"]))
    ok("TSVは空行を除いた行数で数える", r["tsv"] == 3, str(r["tsv"]))
    ok("読めないJSONは0（取り込み本体が理由を添えて断る）", r["broken"] == 0, str(r["broken"]))
    ok("空文字は0", r["empty"] == 0, str(r["empty"]))
    ok("先頭の空白・改行があっても数えられる", r["leadingWS"] == 3, str(r["leadingWS"]))
    ok("1,173問の整形JSONを1173問と数える（回帰の本丸）",
       r["bigPretty"] == 1173, json.dumps({"est": r["bigPretty"], "lines": r["bigLines"]}))
    ok("旧実装ならその行数は数万行だった（誤判定の再現）",
       r["bigLines"] > 20000, str(r["bigLines"]))

    # 実際に取り込みが走るか（拒否されないこと）
    r2 = pg.evaluate("""async () => {
      const mkq = (i) => ({
        unit:"必修問題", major:"1. 健康に関する指標", medium:"A. 人口静態・人口動態",
        sub_item:"a. 総人口", rank:"B", source:"第111回 午前問"+(i+1), pool:"main",
        question_type:"single", select_count:1, stem:"見積もり回帰テスト用の問題文"+i,
        overall_explanation:"解説".repeat(40),
        atoms:[1,2,3,4].map(k => ({ original_num:k, is_correct:k===1,
          text:"肢"+k, statement:"断定文"+k, explanation:"理由".repeat(12), tags:["#人口動態統計"] }))
      });
      const txt = JSON.stringify({questions: Array.from({length:300}, (_,i)=>mkq(i))}, null, 1);
      const before = await window.Storage.countQuestions();
      const rows = window.Storage.estimateImportRows(txt);
      const room = await window.Storage.checkRoomFor(rows);
      const rep = await window.Storage.importText(txt);
      const after = await window.Storage.countQuestions();
      return { rows: rows, roomOk: !!(room.ok || room.unknown),
               imported: rep.imported, added: after - before,
               needMB: Math.round(room.need/1048576*10)/10 };
    }""")
    ok("300問の整形JSONで容量ガードを通過する", r2["roomOk"], json.dumps(r2))
    ok("必要量の見積もりが現実的（300問なら数MB台）",
       r2["needMB"] < 20, json.dumps(r2))
    ok("実際に300問が取り込まれる", r2["imported"] == 300 and r2["added"] == 300, json.dumps(r2))

    ok("実行時エラーなし", not errs, json.dumps(errs[:3], ensure_ascii=False))
    br.close()

bad = [x for x in R if not x[0]]
for good_, name, detail in R:
    print(("  ok  " if good_ else "  NG  ") + name + (("   << " + detail) if (detail and not good_) else ""))
print("\n%d/%d  batchAX" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
