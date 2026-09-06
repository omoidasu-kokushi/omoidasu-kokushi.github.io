# -*- coding: utf-8 -*-
"""test_case_series.py — V2.56 状況設定問題（連問）を続けて出す

利用者の指摘：「問106〜108まで答えよ、みたいな問題がある。
この場合はランダムだろうがなんだろうが連続出題してください」。

何が起きていたか：事例文は各問の stem に丸ごと入っているので単独でも
解けるが、3問がバラバラの日に出るため同じ300字を3回読まされていた。
本番は3問セットで解くので、練習の形が本番と違っていた。

ここで固定するのは4つ。
  ① 出典と問題文から case_key/case_no が機械的に導ける（作問側に列を足さない）
  ② 同じ事例の問題が隣り合う（問番号順）
  ③ 片割れしか選ばれなかったとき兄弟を引き入れる。ただし総数は変わらない
  ④ 誤検出しない（範囲がかけ離れた数字を事例と見なさない）
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright

R = []
def ok(name, cond, detail=""):
    R.append((bool(cond), name, detail))

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = open(os.path.join(base, "storage.js"), encoding="utf-8").read()
sc = open(os.path.join(base, "scheduler.js"), encoding="utf-8").read()
p1 = open(os.path.join(base, "20260815_main_part1_V1.38.js"), encoding="utf-8").read()
sw = open(os.path.join(base, "sw.js"), encoding="utf-8").read()
ix = open(os.path.join(base, "index.html"), encoding="utf-8").read()

ok("case_key を導く関数がある", "function caseInfoOf" in st)
ok("アトムへ非正規化してある（候補を畳んでも連問と分かる）",
   "case_key       : q.case_key || null" in st)
ok("並べ替えと引き入れが別々の関数になっている",
   "function orderCases" in sc and "function fillCaseSiblings" in sc)
ok("本日の復習は並べ替えだけ（兄弟を引き入れない）",
   "questions = orderCases(questions);" in sc and
   sc.count("picked = fillCaseSiblings(") == 1)
ok("出典行に何問目かを出す", "状況設定 ' + runPos.pos" in p1)
p2 = open(os.path.join(base, "20260815_main_part2_V1.45.js"), encoding="utf-8").read()
ok("取り込みレポートに束ねた数と束ねられない数の両方が出る",
   "連問）として束ねた問題" in p2 and "出典が無く束ねられない" in p2)

# 事例文（3問で共有される）
CASE = ("次の文を読み106〜108 の問いに答えよ。A さん（68 歳、男性）は妻と2人暮らし。"
        "3日前から発熱と咳嗽が続き、本日、呼吸困難のため救急外来を受診した。")
def q(no, correct_text):
    return {"source": "第114回 午前問%d" % no, "unit": "必修",
            "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
            "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
            "stem": CASE + "この時点の対応で正しいのはどれか。（設問%d）" % no,
            "atoms": [{"text": "誤りの肢%d" % no, "statement": "誤り", "explanation": "誤り。",
                       "is_correct": False, "tags": ["#呼吸困難"]},
                      {"text": correct_text, "statement": "正しい", "explanation": "正しい。",
                       "is_correct": True, "tags": ["#呼吸困難"]}]}

def filler(i):
    return {"source": "第113回 午前問%d" % i, "unit": "必修",
            "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
            "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
            "stem": "単独の問題%d。正しいのはどれか。" % i,
            "atoms": [{"text": "誤り%d" % i, "statement": "誤り", "explanation": "誤り。",
                       "is_correct": False, "tags": ["#単独%d" % i]},
                      {"text": "正しい%d" % i, "statement": "正しい", "explanation": "正しい。",
                       "is_correct": True, "tags": ["#単独%d" % i]}]}

# 誤検出よけ：数字はあるが事例の範囲としてありえない
FAR = {"source": "第113回 午後問9", "unit": "必修",
       "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
       "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
       "stem": "次の文を読み1〜99 の問いに答えよ。ありえない範囲。正しいのはどれか。",
       "atoms": [{"text": "誤り", "statement": "誤り", "explanation": "誤り。",
                  "is_correct": False, "tags": ["#far"]},
                 {"text": "正しい", "statement": "正しい", "explanation": "正しい。",
                  "is_correct": True, "tags": ["#far"]}]}

# 出典なしの連問（事例文の指紋で束ねる）
def noSrc(n):
    return {"unit": "必修", "major": "1. 健康の定義と理解", "medium": "A. 健康の定義",
            "rank": "S", "question_type": "single", "select_count": 1, "pool": "main",
            "stem": ("次の文を読み31〜32 の問いに答えよ。B さんの事例。まったく同じ事例文。"
                     "設問%d。正しいのはどれか。" % n),
            "atoms": [{"text": "誤りN%d" % n, "statement": "誤り", "explanation": "誤り。",
                       "is_correct": False, "tags": ["#nosrc"]},
                      {"text": "正しいN%d" % n, "statement": "正しい", "explanation": "正しい。",
                       "is_correct": True, "tags": ["#nosrc"]}]}

PAYLOAD = json.dumps({"questions":
    [q(106, "酸素投与を行う"), q(107, "動脈血ガス分析を行う"), q(108, "服薬指導を行う")] +
    [filler(i) for i in range(1, 13)] + [FAR, noSrc(31), noSrc(32)]},
    ensure_ascii=False)

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
      const a = pick('第114回 午前問106'), b = pick('第114回 午前問107'),
            c = pick('第114回 午前問108'), f = pick('第113回 午前問1'),
            far = pick('第113回 午後問9');
      const ns = qs.filter(x => /Bさんの事例|B さんの事例/.test(x.stem || ''));
      const at = await window.Storage.getAtomsByQuestion(a.q_id);
      return { case_rows: r.case_rows || 0,
               keys: [a.case_key, b.case_key, c.case_key],
               nos: [a.case_no, b.case_no, c.case_no],
               filler_key: f.case_key, far_key: far.case_key,
               nosrc: ns.map(x => x.case_key || null), nosrc_n: ns.length,
               orphan: r.case_orphan || 0,
               atom_key: at[0].case_key };
    }""", PAYLOAD)

    ok("3問が同じ case_key になる",
       len(set(d["keys"])) == 1 and d["keys"][0], json.dumps(d["keys"], ensure_ascii=False))
    ok("case_no に問番号が入る", d["nos"] == [106, 107, 108], json.dumps(d["nos"]))
    ok("連問でない問題は case_key を持たない", d["filler_key"] in (None, ""), str(d["filler_key"]))
    ok("範囲がかけ離れた数字は事例と見なさない（1〜99）",
       d["far_key"] in (None, ""), str(d["far_key"]))
    ok("出典が無い連問は束ねない（無関係な2問をくっつけない）",
       d["nosrc_n"] == 2 and all(not x for x in d["nosrc"]),
       json.dumps(d["nosrc"], ensure_ascii=False))
    ok("束ねられなかった連問をレポートで知らせる",
       d["orphan"] == 2, str(d["orphan"]))
    ok("アトムにも case_key が降りている（候補を畳んでも分かる）",
       d["atom_key"] == d["keys"][0], str(d["atom_key"]))
    ok("取り込みレポートが連問の数を出す（黙って束ねない）",
       d["case_rows"] == 3, str(d["case_rows"]))

    g = pg.evaluate("""() => {
      const K = window.Scheduler;
      const mk = (id, key, no) => ({ q_id: id, case_key: key, case_no: no });
      // わざと離して置く
      const list = [mk('x1', null), mk('a3', 'K1', 108), mk('x2', null),
                    mk('a1', 'K1', 106), mk('x3', null), mk('a2', 'K1', 107)];
      const out = K.orderCases(list).map(x => x.q_id);

      // 引き入れ：3問のうち1問しか選ばれていない
      const picked = [mk('a2', 'K1', 107), mk('y1', null), mk('y2', null),
                      mk('y3', null), mk('y4', null)];
      const all = picked.concat([mk('a1', 'K1', 106), mk('a3', 'K1', 108)]);
      const filled = K.fillCaseSiblings(picked, all, 5);
      const ids = filled.map(x => x.q_id);

      // 連問だけのキューは席が空かないので何も起きない
      const onlyCase = [mk('a1', 'K1', 106), mk('a2', 'K1', 107)];
      const onlyOut = K.fillCaseSiblings(onlyCase, onlyCase.concat([mk('a3', 'K1', 108)]), 2);

      return { out, ids, len: filled.length, kept: ids.indexOf('a2') >= 0,
               onlyLen: onlyOut.length,
               ordered: K.orderCases(filled).map(x => x.q_id) };
    }""")
    ok("同じ事例の問題が隣り合う",
       g["out"].index("a1") + 1 == g["out"].index("a2") and
       g["out"].index("a2") + 1 == g["out"].index("a3"), json.dumps(g["out"]))
    ok("並びは問番号順（106→107→108）",
       g["out"].index("a1") < g["out"].index("a2") < g["out"].index("a3"), json.dumps(g["out"]))
    ok("連問でない問題の順番は変わらない",
       [x for x in g["out"] if x.startswith("x")] == ["x1", "x2", "x3"], json.dumps(g["out"]))
    ok("片割れしか無いとき兄弟を引き入れる",
       "a1" in g["ids"] and "a3" in g["ids"], json.dumps(g["ids"]))
    ok("引き入れても総数は変わらない（模試の問数を壊さない）",
       g["len"] == 5, str(g["len"]))
    ok("席を空けるのは連問でない問題だけ（連問を追い出さない）",
       g["kept"], json.dumps(g["ids"]))
    ok("空ける席が無ければ何もしない", g["onlyLen"] == 2, str(g["onlyLen"]))
    ok("引き入れたあと並べ替えれば3問が続く",
       "".join(g["ordered"]).find("a1a2a3") >= 0, json.dumps(g["ordered"]))

    r2 = pg.evaluate("""async () => {
      const K = window.Scheduler;
      const q = await K.buildQueue({ mode: 'random', count: 10, shuffle: true, seed: 7 });
      const keys = q.questions.map(x => x.case_key || '-');
      // 同じ key が飛び飛びになっていないこと
      let broken = 0, seen = {};
      let prev = null;
      keys.forEach(k => {
        if (k === '-') { prev = k; return; }
        if (seen[k] && prev !== k) { broken++; }
        seen[k] = 1; prev = k;
      });
      return { n: q.questions.length, broken: broken, filled: q.case_filled,
               keys: keys };
    }""")
    ok("ランダム10問でも連問が飛び飛びにならない",
       r2["broken"] == 0, json.dumps(r2["keys"], ensure_ascii=False))
    ok("ランダムの出題数は指定どおり（10問）", r2["n"] == 10, str(r2["n"]))

    pos = pg.evaluate("""() => {
      const M = window.Main;
      const one = [{ q_id:'a1', case_key:'K1', case_no:106 }];
      const three = [{ q_id:'a1', case_key:'K1', case_no:106 },
                     { q_id:'a2', case_key:'K1', case_no:107 },
                     { q_id:'a3', case_key:'K1', case_no:108 }];
      return { one: M.casePositionIn(one, 0),
               mid: M.casePositionIn(three, 1),
               plain: M.casePositionIn([{ q_id:'z' }], 0) };
    }""")
    ok("キューに1問しか入っていなければ「状況設定 1/1」を出さない",
       pos["one"] is None, json.dumps(pos))
    ok("3問続くなら2問目は 2/3 と出る",
       pos["mid"] and pos["mid"]["pos"] == 2 and pos["mid"]["len"] == 3, json.dumps(pos))
    ok("連問でない問題には何も出さない", pos["plain"] is None, json.dumps(pos))
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
print("\n%d/%d  case_series" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
