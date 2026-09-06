# -*- coding: utf-8 -*-
"""test_garble_report.py — V2.54 助詞が英単語に化けた本文を取り込みで知らせる

利用者が実物で見つけた：「肝臓 is、体内の有害物質を無毒化し…」。
配布176問に23箇所（is 7・of 16）あった。
分類（V1.71）とタグ（V1.88）は数えていたのに、
**画面にそのまま出る本文**だけ誰も見ていなかった。

止めはしない（Quality of Life のような本物の英語と区別しきれない）。
数えて実例を出すところまでをここで固定する。
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

ok("検出関数がある", "function garbleCheckInto" in st)
ok("TSV経路から呼ばれる", "garbleCheckInto(report, built.question" in st)
ok("JSON経路から呼ばれる", "garbleCheckInto(report, qq" in st)
ok("取り込みレポートに出る", "助詞が英単語に化けている疑い" in p2)
ok("ブロックはしない（skipやerrorにしない）",
   "garble" not in st.split("report.skipped++")[0][-400:] if "report.skipped++" in st else True)

BAD = json.dumps({"questions": [{
    "source": "TEST 化けあり", "unit": "必修", "major": "1. 健康の定義と理解",
    "medium": "A. 健康の定義", "rank": "S", "question_type": "single", "select_count": 1,
    "pool": "main", "stem": "有害物質を無毒化し排泄する臓器はどれか。",
    "atoms": [
      {"text": "腎臓", "statement": "腎臓は尿を作る。", "explanation": "腎臓は尿を作る臓器である。",
       "is_correct": False, "tags": ["#肝臓の機能"]},
      {"text": "肝臓", "statement": "肝臓は解毒する。",
       "explanation": "肝臓 is、体内の有害物質を無毒化する。発達段階 of の組合せも同様。",
       "is_correct": True, "tags": ["#肝臓の機能"]}]}]}, ensure_ascii=False)

GOOD = BAD.replace("肝臓 is、体内の有害物質を無毒化する。発達段階 of の組合せも同様。",
                   "肝臓は、体内の有害物質を無毒化する。")
ENG = BAD.replace("肝臓 is、体内の有害物質を無毒化する。発達段階 of の組合せも同様。",
                  "Quality of Life を保つ視点が要る。")

URL = os.environ.get("APP_URL", "http://127.0.0.1:8900/index.html")
with sync_playwright() as p:
    br = p.chromium.launch(args=["--no-sandbox"])
    pg = br.new_context(viewport={"width": 390, "height": 844}).new_page()
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=60000)

    def imp(text):
        return pg.evaluate("""async (t) => {
          const r = await window.Storage.importText(t);
          return { garble_bad: r.garble_bad || 0, garble_rows: r.garble_rows || 0,
                   ex: r.garble_examples || [], imported: r.imported, skipped: r.skipped };
        }""", text)

    a = imp(BAD)
    ok("化けている本文を数える（is と of の2箇所）",
       a["garble_bad"] == 2, json.dumps(a, ensure_ascii=False))
    ok("何問に入っていたかも数える", a["garble_rows"] == 1, json.dumps(a, ensure_ascii=False))
    ok("実例を出す（どこが化けたか分かる）",
       a["ex"] and "肝臓" in a["ex"][0], json.dumps(a, ensure_ascii=False))
    ok("化けていても取り込みは止めない（数えるだけ）",
       a["imported"] + (a["skipped"] or 0) >= 1 and a["skipped"] == 0,
       json.dumps(a, ensure_ascii=False))

    b = imp(GOOD)
    ok("直してあるデータでは数えない", b["garble_bad"] == 0, json.dumps(b, ensure_ascii=False))

    c = imp(ENG)
    ok("本物の英語（Quality of Life）を誤検出しない",
       c["garble_bad"] == 0, json.dumps(c, ensure_ascii=False))
    br.close()

# --- 版は決め打ちしない ---
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
print("\n%d/%d  garble_report" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
