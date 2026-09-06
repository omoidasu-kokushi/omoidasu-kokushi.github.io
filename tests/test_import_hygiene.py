# -*- coding: utf-8 -*-
"""test_import_hygiene.py — V2.60 取り込みの入力ゆれを、分類と出典まで見る

今日の仕上げレーン342ファイルを実測して見つけた2つ。

① 分類にも助詞の英単語化けがある
     sub_item「筋収縮 of 機構」 ← 「筋収縮の機構」
   V2.54 の化け検出は stem・解説・肢しか見ていなかった。
   素通りした結果は「⚠出題基準に無い分類」としてだけ出るので、
   読んだ人は分類表のほうを疑う。原因を言わない警告は
   間違った場所を直させる。

② 出典に全角スペースが混ざる（17問）
     '第113回　　午後問104'
   効く場所が3つ：画面の出典表示／照合台帳との文字列一致／
   V2.56 の連問キー（case_key）の元。
   詰めるのは空白だけ。詰めた件数は必ず報告する（黙って直さない）。
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("化け検出が分類も見る", "q && q.sub_item" in st and "q && q.medium" in st)
ok("出典を詰める関数がある", "function tidySource" in st)
ok("詰めてから連問キーを作る（順番が逆だと空白ゆれで別の束になる）",
   st.index("function tidySource") < st.index("function caseInfoOf"))
ok("詰めた件数をレポートに出す", "source_tidied" in st and "出典の余分な空白を詰めた問題" in p2)
ok("化けは検出だけで自動修正しない（V2.54の判断を変えていない）",
   "garble_bad" in st and "garbleFix" not in st)

def q(src, sub, stem, tag="#衛生"):
    return {"source": src, "unit": "必修", "major": "1. 健康の定義と理解",
            "medium": "A. 健康の定義", "sub_item": sub,
            "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
            "stem": stem,
            "atoms": [{"text": "誤り", "statement": "誤り", "explanation": "誤り。",
                       "is_correct": False, "tags": [tag]},
                      {"text": "正しい", "statement": "正しい", "explanation": "正しい。",
                       "is_correct": True, "tags": [tag]}]}

CASE = "次の文を読み106〜108 の問いに答えよ。Aさん（68歳、男性）の事例。"
PAY = json.dumps({"questions": [
    # ① 分類が化けている（本文はきれい）
    q("第115回 午前問26", "筋収縮 of 機構", "衛生検査の問題。正しいのはどれか。"),
    # ② 出典に全角スペース2個。連問の片割れ
    q("第114回　　午前問106", "a. 総人口", CASE + "この時点の対応で正しいのはどれか。"),
    # ③ 同じ事例の兄弟。出典はきれい
    q("第114回 午前問107", "a. 総人口", CASE + "次に行う対応で正しいのはどれか。"),
    # ④ どこも化けていない・空白もきれい
    q("第113回 午前問1", "a. 総人口", "きれいな問題。正しいのはどれか。"),
]}, ensure_ascii=False)

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    d = pg.evaluate("""async (t) => {
      const r = await window.Storage.importText(t);
      const qs = await window.Storage.getAllQuestions();
      const pick = s => qs.find(x => x.source === s);
      const a = pick('第115回 午前問26');
      const b = pick('第114回 午前問106');
      const c = pick('第114回 午前問107');
      const e = pick('第113回 午前問1');
      const raw = qs.filter(x => /　/.test(x.source || '')).map(x => x.source);
      return { garble_bad: r.garble_bad || 0, garble_rows: r.garble_rows || 0,
               ex: r.garble_examples || [], tidied: r.source_tidied || 0,
               case_rows: r.case_rows || 0,
               tidiedFound: !!b, tidiedRaw: raw,
               keys: [b && b.case_key, c && c.case_key],
               nos: [b && b.case_no, c && c.case_no],
               cleanNoGarble: !!e, aSub: a && a.sub_item,
               ids: { b: b && b.q_id, c: c && c.q_id }, n: qs.length };
    }""", PAY)

    ok("分類の化けを数える（sub_item の of）", d["garble_bad"] >= 1,
       json.dumps(d, ensure_ascii=False)[:250])
    ok("実例に分類の化けが出る",
       any("筋収縮" in x for x in d["ex"]), json.dumps(d["ex"], ensure_ascii=False))
    ok("化けは直さずそのまま入る（検出だけ）", d["aSub"] == "筋収縮 of 機構", str(d["aSub"]))
    ok("出典の全角スペースを詰める", d["tidiedFound"], json.dumps(d, ensure_ascii=False)[:250])
    ok("詰め残しが1件も無い", d["tidiedRaw"] == [], json.dumps(d["tidiedRaw"], ensure_ascii=False))
    ok("詰めた件数を報告する（黙って直さない）", d["tidied"] == 1, str(d["tidied"]))
    ok("詰めた側も連問として束ねられる（空白ゆれで別の束にならない）",
       d["keys"][0] and d["keys"][0] == d["keys"][1], json.dumps(d["keys"], ensure_ascii=False))
    ok("問番号も拾えている", d["nos"] == [106, 107], json.dumps(d["nos"]))
    ok("連問の件数もレポートに出る", d["case_rows"] == 2, str(d["case_rows"]))
    ok("きれいな問題は化けに数えない", d["garble_rows"] <= 1, str(d["garble_rows"]))
    ok("兄弟が別レコードになっている（詰めても取り違えない）",
       d["ids"]["b"] and d["ids"]["c"] and d["ids"]["b"] != d["ids"]["c"],
       json.dumps(d["ids"], ensure_ascii=False))

    # 2回入れても増えない（詰めた出典で入れ直しても重複しない）
    d2 = pg.evaluate("""async (t) => {
      const r = await window.Storage.importText(t);
      const qs = await window.Storage.getAllQuestions();
      return { imported: r.imported, n: qs.length };
    }""", PAY)
    ok("同じデータをもう一度入れても増えない", d2["imported"] == 0 and d2["n"] == d["n"],
       json.dumps(d2))
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
print("\n%d/%d  import_hygiene" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
