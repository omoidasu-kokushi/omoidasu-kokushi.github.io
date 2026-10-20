# -*- coding: utf-8 -*-
"""test_import_audit.py — V3.23 黙って通ってしまう欠損を、取り込みレポートで数える

何が起きていたか（2026-10-20・配布JSON 過去問1197問の突き合わせ）：
取り込みは全部「成功」と出るのに、5件欠けていた。どれも警告が1つも出ない。

① 第114回 午前問41「一次救命処置〈BLS〉で回復体位はどれか。」
   肢が ①②③④ だけなのに image_url=null。図が無いので解答できない
② 第112回午後35・第113回午後21・第115回午前32 が欠番。
   1,200問あるはずが1,197問になっていた。誰も引き算していなかった
③ images/sentakushi/113_pm21.png があるのに、第113回午後問21 が無い

止めない。数えて report に残す（取り込みは通す）。このテストは3つの検出が
それぞれ効くこと・正しい問題を数えないこと・画像の一覧が3か所で揃っていることを固定する。
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()

# --- 画像の一覧は3か所（フォルダ・storage.js・sw.js）で揃っている ---
files = sorted(f for f in os.listdir(os.path.join(base, "images", "sentakushi")) if f.endswith(".png"))
m = re.search(r"var SENTAKUSHI_IMAGES = \[(.*?)\];", st, re.S)
in_st = sorted(re.findall(r"'([^']+\.png)'", m.group(1))) if m else []
in_sw = sorted(re.findall(r"\./images/sentakushi/([^']+\.png)", sw))
ok("storage.js に選択肢画像の一覧がある", bool(m))
ok("storage.js の一覧がフォルダの中身と同じ", in_st == files, "%s vs %s" % (in_st, files))
ok("sw.js の一覧もフォルダの中身と同じ（片方だけ直さない）", in_sw == files, "%s vs %s" % (in_sw, files))
ok("止めずに数える（取り込みの前に audit を呼ぶだけ）",
   "auditSourcesInto(payload, report);" in st and "function auditSourcesInto" in st)


def q(src, texts, stem="正しいのはどれか。", image_url=None):
    d = {"source": src, "unit": "必修", "major": "1. 健康の定義と理解",
         "medium": "A. 健康の定義", "sub_item": "a. 総人口",
         "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
         "stem": stem,
         "atoms": [{"text": t, "statement": "肢%d の文。" % (i + 1), "explanation": "",
                    "is_correct": i == 0, "tags": ["#衛生"]} for i, t in enumerate(texts)]}
    if image_url:
        d["image_url"] = image_url
    return d

CIRC = ["①", "②", "③", "④"]
BAD = [
    # ① 記号だけ・画像なし（数える）
    q("第114回 午前問41", CIRC, "一次救命処置〈BLS〉で回復体位はどれか。"),
    q("第114回 午前問42", ["1", "2", "3", "4"]),
    q("第114回 午前問43", ["a.", "b.", "c.", "d."]),
    # ① 記号だけでも画像がある（数えない）
    q("第114回 午前問39", CIRC, image_url="images/sentakushi/114_am39.png"),
    q("第114回 午前問44", CIRC, "[IMAGE: images/stem/114_am44.png] 図の部位はどれか。"),
    # ① 短いが本文として正しい（数えない：同梱の見本に実在する形）
    q("第114回 午前問40", ["5", "10", "30", "50"]),
    q("第114回 午前問45", ["胃", "肝臓", "膵臓", "大腸"]),
    q("第114回 午前問46", ["4", "5", "6", "7"]),
    # ② 欠番：112午後35・113午後21・115午前32（1問ずつ）＋113午後24〜25（続けて2問）
    q("第112回 午後問34", ["誤り", "正しい"]), q("第112回 午後問36", ["誤り", "正しい"]),
    q("第113回 午後問20", ["誤り", "正しい"]), q("第113回 午後問22", ["誤り", "正しい"]),
    q("第113回 午後問23", ["誤り", "正しい"]), q("第113回 午後問26", ["誤り", "正しい"]),
    q("第115回 午前問31", ["誤り", "正しい"]), q("第115回 午前問33", ["誤り", "正しい"]),
]
# ③ 画像の孤児：取り込みに出てくる回・午前／午後のうち、その番号の問題が無い画像
present = {}
for x in BAD:
    mm = re.search(r"第(\d+)回 (午前|午後)問(\d+)", x["source"])
    present.setdefault((mm.group(1), "am" if mm.group(2) == "午前" else "pm"), set()).add(int(mm.group(3)))
orphans = [f for f in files
           if (lambda g: g and (g.group(1), g.group(2)) in present
               and int(g.group(3)) not in present[(g.group(1), g.group(2))])
           (re.match(r"(\d+)_(am|pm)(\d+)\.png$", f))]

CLEAN = [q("第111回 午後問%d" % n, ["誤り", "正しい"]) for n in (1, 2, 3)]

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)
    pg.wait_for_function("window.__INIT_DONE === true", timeout=60000)

    imp = """async (t) => {
      const r = await window.Storage.importText(t);
      const qs = await window.Storage.getAllQuestions();
      const keep = ['noimg_symbol','noimg_symbol_examples','source_gaps','source_gap_missing',
                    'source_gap_examples','image_orphans','image_orphan_examples','ok','imported','parsed'];
      const o = {}; keep.forEach(k => { o[k] = r[k]; });
      o.has41 = qs.some(x => x.source === '第114回 午前問41');
      const meta = await window.Storage.getMeta('last_import_report');
      o.saved = !!meta && meta.noimg_symbol === r.noimg_symbol && meta.source_gaps === r.source_gaps;
      return o;
    }"""
    d = pg.evaluate(imp, json.dumps({"questions": BAD}, ensure_ascii=False))
    s = json.dumps(d, ensure_ascii=False)

    ok("① 記号だけで画像の無い問題を数える（①②③④・1234・a. b. c. d. の3問）",
       d["noimg_symbol"] == 3, s)
    ok("① 実例に第114回 午前問41 が出る",
       "第114回 午前問41" in (d["noimg_symbol_examples"] or []), s)
    ok("① image_url か [IMAGE: …] があれば数えない",
       not any(x in (d["noimg_symbol_examples"] or []) for x in ("第114回 午前問39", "第114回 午前問44")), s)
    ok("① 短いだけの正しい肢（5｜10｜30｜50・胃｜肝臓・4｜5｜6｜7）は数えない",
       not any(x in (d["noimg_symbol_examples"] or [])
               for x in ("第114回 午前問40", "第114回 午前問45", "第114回 午前問46")), s)
    ok("② 欠番を数える（続けて抜けたところは1か所）", d["source_gaps"] == 4, s)
    ok("② 抜けた問数も数える", d["source_gap_missing"] == 5, s)
    ok("② 実例に抜けた出典が出る",
       {"第112回 午後問35", "第113回 午後問21", "第115回 午前問32", "第113回 午後問24〜25"}
       <= set(d["source_gap_examples"] or []), s)
    ok("③ 画像はあるのに問題が無い本数を数える", d["image_orphans"] == len(orphans) and len(orphans) > 0,
       "%s / 期待 %s" % (s, orphans))
    ok("③ 実例に 113_pm21.png が出る",
       any(x.startswith("113_pm21.png") for x in (d["image_orphan_examples"] or [])), s)
    ok("③ 問題がある画像（114_am39・114_am41）は数えない",
       not any(x.startswith(("114_am39", "114_am41")) for x in (d["image_orphan_examples"] or [])), s)
    ok("止めない：取り込みは通る（全問入る）", d["ok"] is True and d["parsed"] == len(BAD), s)
    ok("止めない：解答不能な第114回 午前問41 もそのまま入る", d["has41"], s)
    ok("数えた結果が last_import_report に残る", d["saved"], s)

    c = pg.evaluate(imp, json.dumps({"questions": CLEAN}, ensure_ascii=False))
    s = json.dumps(c, ensure_ascii=False)
    ok("きれいなデータでは3つとも0", c["noimg_symbol"] == 0 and c["source_gaps"] == 0
       and c["image_orphans"] == 0, s)

    # TSV の経路でも同じ関数を通る（persistImportPayload の入口で数えている）
    tsv = pg.evaluate("""async () => {
      const r = await window.Storage.importText(SEED_QUESTIONS_TSV);
      return { has: typeof r.noimg_symbol === 'number' && typeof r.source_gaps === 'number'
                    && typeof r.image_orphans === 'number' };
    }""")
    ok("同梱の見本を取り込み直しても3つの数が出る", tsv["has"], json.dumps(tsv))

    ok("JSエラーが出ていない", len(errs) == 0, " / ".join(errs[:3]))
    br.close()

bad = [x for x in R if not x[0]]
for good, name, detail in R:
    print(("  ok  " if good else "  NG  ") + name + (("   << " + detail) if (detail and not good) else ""))
print("\n%d/%d  import_audit" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
